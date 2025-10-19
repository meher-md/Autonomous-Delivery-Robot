#!/usr/bin/env python3

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    LogInfo,
    TimerAction,
    ExecuteProcess,
    SetEnvironmentVariable,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
    TextSubstitution,
)
from launch_ros.actions import Node, PushRosNamespace, SetRemap

from nav2_common.launch import ParseMultiRobotPose
from andino_gz.launch_tools.substitutions import TextJoin


def generate_launch_description():
    pkg_andino_gz = get_package_share_directory('andino_gz')
    pkg_nav2_bringup = get_package_share_directory('nav2_bringup')
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')

    # ---------------- Launch Args ----------------
    ros_bridge_arg = DeclareLaunchArgument(
        'ros_bridge', default_value='True', description='Run ROS bridge node.'
    )
    rviz_arg = DeclareLaunchArgument('rviz', default_value='True', description='Start RViz.')
    world_name_arg = DeclareLaunchArgument(
        'world_name', default_value='populated_office.sdf',
        description='Name of the world to load. Match with map if using Nav2.'
    )
    robots_arg = DeclareLaunchArgument(
        'robots', default_value="andino={x: 0., y: 0., z: 0.1, yaw: 0.};",
        description='Robots to spawn, separated by semicolons.'
    )
    gui_config_arg = DeclareLaunchArgument(
        'gui_config', default_value='default.config',
        description='Gazebo GUI configuration file.'
    )
    nav2_arg = DeclareLaunchArgument('nav2', default_value='True', description='Enable Nav2 Bringup.')
    map_name_arg = DeclareLaunchArgument(
        'map', default_value="office",
        description='Map name (must match the world).'
    )
    params_file_arg = DeclareLaunchArgument(
        'params_file',
        default_value=PathJoinSubstitution([pkg_andino_gz, 'config', 'nav2_params.yaml']),
        description='Nav2 params YAML.'
    )

    # Optional: manual override for initial pose (map frame)
    # "__spawn__" = استخدم إحداثيات السبان بعد تحويل world->map تلقائياً باستخدام origin من الـ YAML
    initpose_x_arg = DeclareLaunchArgument('initpose_x', default_value='__spawn__',
                                           description='Initial X in map. "__spawn__" -> use spawn value (converted).')
    initpose_y_arg = DeclareLaunchArgument('initpose_y', default_value='__spawn__',
                                           description='Initial Y in map. "__spawn__" -> use spawn value (converted).')
    initpose_yaw_deg_arg = DeclareLaunchArgument('initpose_yaw_deg', default_value='__spawn__',
                                                 description='Initial yaw(deg) in map. "__spawn__" -> use spawn value.')

    # ---------------- Launch Configs ----------------
    rviz        = LaunchConfiguration('rviz')
    ros_bridge  = LaunchConfiguration('ros_bridge')
    world_name  = LaunchConfiguration('world_name')
    map_name    = LaunchConfiguration('map')
    gui_config  = LaunchConfiguration('gui_config')
    nav2_flag   = LaunchConfiguration('nav2')
    params_file = LaunchConfiguration('params_file')

    initpose_x       = LaunchConfiguration('initpose_x')
    initpose_y       = LaunchConfiguration('initpose_y')
    initpose_yaw_deg = LaunchConfiguration('initpose_yaw_deg')

    # ---------------- Paths ----------------
    world_path = PathJoinSubstitution([pkg_andino_gz, 'worlds', world_name])
    gui_config_path = PathJoinSubstitution([pkg_andino_gz, 'config_gui', gui_config])
    map_yaml_path = PathJoinSubstitution([pkg_andino_gz, 'maps', map_name, TextJoin(substitutions=[map_name, '.yaml'])])

    log_world_path = LogInfo(msg=TextJoin(substitutions=["World path: ", world_path]))
    log_map_path   = LogInfo(msg=TextJoin(substitutions=["Map path:   ", map_yaml_path]))

    # ---------------- Gazebo ----------------
    gz_args = TextJoin(
        substitutions=[world_path, TextJoin(substitutions=["--gui-config", gui_config_path], separator=' ')],
        separator=' ',
    )

    base_group = GroupAction(
        actions=[
            # تشغيل RViz/Gazebo بريندر سوفت داخل الكونتينر لتفادي GLSL
            SetEnvironmentVariable('LIBGL_ALWAYS_SOFTWARE', '1'),

            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')),
                launch_arguments={'gz_args': gz_args}.items(),
            ),

            # ROS Bridge for /clock
            Node(
                package='ros_gz_bridge',
                executable='parameter_bridge',
                arguments=['/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock'],
                output='screen',
                namespace='andino_gz_sim',
                condition=IfCondition(ros_bridge),
            ),
        ]
    )

    # ---------------- Robots + Nav2 ----------------
    robots_list = ParseMultiRobotPose('robots').value()
    if robots_list == {}:
        robots_list = {"andino": {"x": 0., "y": 0., "z": 0.1, "yaw": 0.}}

    nrobots = len(robots_list)
    more_than_one = PythonExpression([TextSubstitution(text=str(nrobots)), ' > 1'])
    one_robot     = PythonExpression([TextSubstitution(text=str(nrobots)), ' == 1'])

    spawn_groups = []

    for robot_name, spawn in robots_list.items():
        # for namespaced initialpose topic
        ns_initialpose_topic = '/' + robot_name + '/initialpose'

        robots_group = GroupAction(
            actions=[
                LogInfo(msg=f"Group for robot: {robot_name}"),

                PushRosNamespace(condition=IfCondition(more_than_one), namespace=robot_name),

                # Spawn the robot (Gazebo world frame)
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(pkg_andino_gz, 'launch', 'include', 'spawn_robot.launch.py')
                    ),
                    launch_arguments={
                        'entity': robot_name,
                        'initial_pose_x': str(spawn['x']),
                        'initial_pose_y': str(spawn['y']),
                        'initial_pose_z': str(spawn['z']),
                        'initial_pose_yaw': str(spawn['yaw']),
                        'robot_description_topic': 'robot_description',
                        'use_sim_time': 'true',
                    }.items(),
                ),

                # Robot State Publisher
                Node(
                    package='robot_state_publisher',
                    executable='robot_state_publisher',
                    name='robot_state_publisher',
                    output='screen',
                    parameters=[{'use_sim_time': True}],
                    remappings=[('robot_description', 'robot_description')],
                ),

                # RViz (Nav2 layout) — software rendering
                TimerAction(
                    period=5.0,
                    actions=[
                        Node(
                            condition=IfCondition(PythonExpression([rviz, ' and ', nav2_flag])),
                            package='rviz2',
                            executable='rviz2',
                            arguments=['-d', os.path.join(pkg_andino_gz, 'rviz', 'andino_gz_nav2.rviz')],
                            parameters=[{'use_sim_time': True}],
                            remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
                            output='screen',
                            additional_env={'LIBGL_ALWAYS_SOFTWARE': '1', 'QT_QPA_PLATFORM': 'xcb'},
                        ),
                        Node(
                            condition=IfCondition(PythonExpression([rviz, ' and not ', nav2_flag])),
                            package='rviz2',
                            executable='rviz2',
                            arguments=['-d', os.path.join(pkg_andino_gz, 'rviz', 'andino_gz.rviz')],
                            parameters=[{'use_sim_time': True}],
                            remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
                            output='screen',
                            additional_env={'LIBGL_ALWAYS_SOFTWARE': '1', 'QT_QPA_PLATFORM': 'xcb'},
                        )
                    ]
                ),

                # Per-robot Gazebo<->ROS bridges
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(pkg_andino_gz, 'launch', 'include', 'gz_ros_bridge.launch.py')
                    ),
                    launch_arguments={'entity': robot_name}.items(),
                    condition=IfCondition(ros_bridge),
                ),
            ]
        )

        # Nav2 group
        nav_group = GroupAction(
            actions=[
                # Lidar remaps
                SetRemap(src='/global_costmap/scan', dst='/scan',
                         condition=IfCondition(PythonExpression([one_robot, ' and ', nav2_flag]))),
                SetRemap(src='/local_costmap/scan', dst='/scan',
                         condition=IfCondition(PythonExpression([one_robot, ' and ', nav2_flag]))),
                SetRemap(src='/' + robot_name + '/global_costmap/scan', dst='/' + robot_name + '/scan',
                         condition=IfCondition(PythonExpression([more_than_one, ' and ', nav2_flag]))),
                SetRemap(src='/' + robot_name + '/local_costmap/scan', dst='/' + robot_name + '/scan',
                         condition=IfCondition(PythonExpression([more_than_one, ' and ', nav2_flag]))),

                # Nav2 bringup
                TimerAction(
                    period=8.0,
                    actions=[
                        IncludeLaunchDescription(
                            PythonLaunchDescriptionSource(
                                os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')
                            ),
                            launch_arguments={
                                'map': map_yaml_path,
                                'autostart': 'True',
                                'use_sim_time': 'True',
                                'params_file': params_file,
                            }.items(),
                            condition=IfCondition(PythonExpression([one_robot, ' and ', nav2_flag])),
                        ),
                        IncludeLaunchDescription(
                            PythonLaunchDescriptionSource(
                                os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')
                            ),
                            launch_arguments={
                                'namespace': robot_name,
                                'use_namespace': 'True',
                                'map': map_yaml_path,
                                'autostart': 'True',
                                'use_sim_time': 'True',
                                'params_file': params_file,
                            }.items(),
                            condition=IfCondition(PythonExpression([more_than_one, ' and ', nav2_flag])),
                        ),
                    ]
                ),

                # -------- Auto initialpose (world -> map باستخدام origin من YAML) --------
                TimerAction(
                    period=10.0,
                    actions=[
                        ExecuteProcess(
                            cmd=[
                                'python3', '-c',
                                (
                                    'import rclpy, math, os, yaml; '
                                    'from geometry_msgs.msg import PoseWithCovarianceStamped; '
                                    'from rclpy.node import Node; '
                                    'rclpy.init(); '
                                    'topic=os.environ["TOPIC"]; '
                                    'xw=float(os.environ["SPAWN_X"]); '
                                    'yw=float(os.environ["SPAWN_Y"]); '
                                    'yaw=float(os.environ["SPAWN_YAW"]); '  # rad
                                    'yaml_path=os.environ["MAP_YAML"]; '
                                    'x_arg=os.environ.get("INITPOSE_X","__spawn__"); '
                                    'y_arg=os.environ.get("INITPOSE_Y","__spawn__"); '
                                    'yawd_arg=os.environ.get("INITPOSE_YAWD","__spawn__"); '
                                    # اقرأ origin من YAML
                                    'ox=0.0; oy=0.0; '
                                    'try:\n'
                                    '  with open(yaml_path,"r") as f:\n'
                                    '    info=yaml.safe_load(f) or {};\n'
                                    '    if isinstance(info.get("origin",None),(list,tuple)) and len(info["origin"])>=2:\n'
                                    '      ox=float(info["origin"][0]); oy=float(info["origin"][1]);\n'
                                    'except Exception:\n'
                                    '  pass\n'
                                    # تحويل world -> map
                                    'xm = xw - ox; ym = yw - oy; '
                                    # السماح بالـ override
                                    'if x_arg!="__spawn__": xm=float(x_arg); '
                                    'if y_arg!="__spawn__": ym=float(y_arg); '
                                    'if yawd_arg!="__spawn__": yaw=math.radians(float(yawd_arg)); '
                                    'n=Node("auto_initialpose"); '
                                    'p=n.create_publisher(PoseWithCovarianceStamped, topic, 10); '
                                    'qz=math.sin(yaw/2.0); qw=math.cos(yaw/2.0); '
                                    'm=PoseWithCovarianceStamped(); m.header.frame_id="map"; '
                                    'm.pose.pose.position.x=xm; m.pose.pose.position.y=ym; '
                                    'm.pose.pose.orientation.z=qz; m.pose.pose.orientation.w=qw; '
                                    'm.pose.covariance[0]=0.25; m.pose.covariance[7]=0.25; m.pose.covariance[35]=0.05; '
                                    'p.publish(m); '
                                    'n.get_logger().info(f"[auto_initialpose] world=({xw:.2f},{yw:.2f}) origin=({ox:.2f},{oy:.2f}) -> map=({xm:.2f},{ym:.2f}) yaw={yaw:.2f}rad"); '
                                    'rclpy.shutdown()'
                                )
                            ],
                            output='screen',
                            additional_env={
                                'TOPIC': (ns_initialpose_topic if nrobots > 1 else '/initialpose'),
                                'SPAWN_X': str(spawn['x']),
                                'SPAWN_Y': str(spawn['y']),
                                'SPAWN_YAW': str(spawn['yaw']),
                                'MAP_YAML': map_yaml_path,
                                'INITPOSE_X': initpose_x,
                                'INITPOSE_Y': initpose_y,
                                'INITPOSE_YAWD': initpose_yaw_deg,
                            }
                        )
                    ]
                ),

                # Clear costmaps بعد 2s من نشر الـ pose
                TimerAction(
                    period=12.0,
                    actions=[
                        ExecuteProcess(
                            cmd=['/bin/bash','-lc',
                                 ('ros2 service call '
                                  + ('/' + robot_name if nrobots > 1 else '')
                                  + '/global_costmap/clear_entirely_global_costmap std_srvs/srv/Empty "{}"')],
                            output='screen'
                        ),
                        ExecuteProcess(
                            cmd=['/bin/bash','-lc',
                                 ('ros2 service call '
                                  + ('/' + robot_name if nrobots > 1 else '')
                                  + '/local_costmap/clear_entirely_local_costmap std_srvs/srv/Empty "{}"')],
                            output='screen'
                        ),
                    ]
                ),
            ]
        )

        spawn_groups += [robots_group, nav_group]

    # ---------------- Launch Description ----------------
    ld = LaunchDescription()

    for a in (ros_bridge_arg, rviz_arg, world_name_arg, robots_arg, gui_config_arg,
              nav2_arg, map_name_arg, params_file_arg, initpose_x_arg, initpose_y_arg, initpose_yaw_deg_arg):
        ld.add_action(a)

    ld.add_action(log_world_path)
    ld.add_action(log_map_path)
    ld.add_action(base_group)

    # مفيش أي static TF بيتنشر هنا. خلي Fixed Frame في RViz = "map".

    for g in spawn_groups:
        ld.add_action(g)

    return ld
