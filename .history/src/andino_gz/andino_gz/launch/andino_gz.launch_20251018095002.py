#!/usr/bin/env python3

import os, yaml
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, GroupAction, IncludeLaunchDescription, LogInfo,
    TimerAction, ExecuteProcess, SetEnvironmentVariable
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    LaunchConfiguration, PathJoinSubstitution, PythonExpression, TextSubstitution
)
from launch_ros.actions import Node, PushRosNamespace, SetRemap

from nav2_common.launch import ParseMultiRobotPose
from andino_gz.launch_tools.substitutions import TextJoin


def generate_launch_description():
    pkg_andino_gz    = get_package_share_directory('andino_gz')
    pkg_nav2_bringup = get_package_share_directory('nav2_bringup')
    pkg_ros_gz_sim   = get_package_share_directory('ros_gz_sim')

    # ---------------- Args ----------------
    ros_bridge_arg = DeclareLaunchArgument('ros_bridge', default_value='True', description='Run ROS bridge node.')
    rviz_arg       = DeclareLaunchArgument('rviz',       default_value='True', description='Start RViz.')
    world_name_arg = DeclareLaunchArgument('world_name', default_value='populated_office.sdf', description='World file (match map).')
    robots_arg     = DeclareLaunchArgument('robots',     default_value="andino={x: 0., y: 0., z: 0.1, yaw: 0.};", description='Robots to spawn.')
    gui_config_arg = DeclareLaunchArgument('gui_config', default_value='default.config', description='Gazebo GUI config.')
    nav2_arg       = DeclareLaunchArgument('nav2',       default_value='True', description='Enable Nav2 Bringup.')
    map_name_arg   = DeclareLaunchArgument('map',        default_value="office", description='Map name (must match world).')
    params_file_arg= DeclareLaunchArgument('params_file',
                        default_value=PathJoinSubstitution([pkg_andino_gz, 'config', 'nav2_params.yaml']),
                        description='Nav2 params YAML.')

    # Optional manual override (map frame). "__spawn__" = استخدم تحويل السبان تلقائيًا
    initpose_x_arg       = DeclareLaunchArgument('initpose_x',       default_value='__spawn__')
    initpose_y_arg       = DeclareLaunchArgument('initpose_y',       default_value='__spawn__')
    initpose_yaw_deg_arg = DeclareLaunchArgument('initpose_yaw_deg', default_value='__spawn__')

    # ---------------- LCs ----------------
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
    world_path      = PathJoinSubstitution([pkg_andino_gz, 'worlds', world_name])
    gui_config_path = PathJoinSubstitution([pkg_andino_gz, 'config_gui', gui_config])
    map_yaml_path   = PathJoinSubstitution([pkg_andino_gz, 'maps', map_name, TextJoin(substitutions=[map_name, '.yaml'])])

    log_world_path = LogInfo(msg=TextJoin(substitutions=["World path: ", world_path]))
    log_map_path   = LogInfo(msg=TextJoin(substitutions=["Map path:   ", map_yaml_path]))

    # ---------------- Gazebo ----------------
    gz_args = TextJoin(
        substitutions=[world_path, TextJoin(substitutions=["--gui-config", gui_config_path], separator=' ')],
        separator=' ',
    )
    base_group = GroupAction(actions=[
        SetEnvironmentVariable('LIBGL_ALWAYS_SOFTWARE', '1'),  # RViz/Gazebo داخل كونتينر
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')),
            launch_arguments={'gz_args': gz_args}.items(),
        ),
        Node(
            package='ros_gz_bridge', executable='parameter_bridge',
            arguments=['/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock'],
            output='screen', namespace='andino_gz_sim',
            condition=IfCondition(ros_bridge),
        ),
    ])

    # ---------------- Robots + Nav2 ----------------
    robots = ParseMultiRobotPose('robots').value() or {"andino": {"x": 0., "y": 0., "z": 0.1, "yaw": 0.}}
    nrobots = len(robots)
    more_than_one = PythonExpression([TextSubstitution(text=str(nrobots)), ' > 1'])
    one_robot     = PythonExpression([TextSubstitution(text=str(nrobots)), ' == 1'])

    # اقرأ origin من الـ YAML: origin = [x_off, y_off, yaw]
    # دي بتربط صورة الخريطة بإطار map. بنستخدمها لتبديل (world->map) للـ initial pose فقط.
    origin_x, origin_y = 0.0, 0.0
    try:
        yaml_path = os.path.join(pkg_andino_gz, 'maps', LaunchConfiguration('map').perform({'map': map_name.perform({})}), f"{map_name.perform({})}.yaml")
    except Exception:
        # لما LaunchConfiguration مش متاحة هنا: حمّل مباشرة من المسار المُركّب
        yaml_path = None
    # قراءة آمنة عند وقت الـ generate (لو المسار المباشر غير متاح عبر LC نقرأ لاحقاً داخل python -c)
    if yaml_path and os.path.exists(yaml_path):
        try:
            with open(yaml_path, 'r') as f:
                info = yaml.safe_load(f) or {}
                if isinstance(info.get('origin', None), (list, tuple)) and len(info['origin']) >= 2:
                    origin_x, origin_y = float(info['origin'][0]), float(info['origin'][1])
        except Exception:
            pass

    spawn_groups = []

    for name, sp in robots.items():
        ns_initialpose_topic = '/' + name + '/initialpose'

        robots_group = GroupAction(actions=[
            LogInfo(msg=f"Group for robot: {name}"),

            PushRosNamespace(condition=IfCondition(more_than_one), namespace=name),

            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(os.path.join(pkg_andino_gz, 'launch', 'include', 'spawn_robot.launch.py')),
                launch_arguments={
                    'entity': name,
                    'initial_pose_x': str(sp['x']),
                    'initial_pose_y': str(sp['y']),
                    'initial_pose_z': str(sp['z']),
                    'initial_pose_yaw': str(sp['yaw']),
                    'robot_description_topic': 'robot_description',
                    'use_sim_time': 'true',
                }.items(),
            ),

            Node(
                package='robot_state_publisher', executable='robot_state_publisher',
                name='robot_state_publisher', output='screen',
                parameters=[{'use_sim_time': True}],
                remappings=[('robot_description', 'robot_description')],
            ),

            TimerAction(period=5.0, actions=[
                Node(
                    condition=IfCondition(PythonExpression([rviz, ' and ', nav2_flag])),
                    package='rviz2', executable='rviz2',
                    arguments=['-d', os.path.join(pkg_andino_gz, 'rviz', 'andino_gz_nav2.rviz')],
                    parameters=[{'use_sim_time': True}],
                    remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
                    output='screen',
                    additional_env={'LIBGL_ALWAYS_SOFTWARE': '1', 'QT_QPA_PLATFORM': 'xcb'}
                ),
                Node(
                    condition=IfCondition(PythonExpression([rviz, ' and not ', nav2_flag])),
                    package='rviz2', executable='rviz2',
                    arguments=['-d', os.path.join(pkg_andino_gz, 'rviz', 'andino_gz.rviz')],
                    parameters=[{'use_sim_time': True}],
                    remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
                    output='screen',
                    additional_env={'LIBGL_ALWAYS_SOFTWARE': '1', 'QT_QPA_PLATFORM': 'xcb'}
                )
            ]),

            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(os.path.join(pkg_andino_gz, 'launch', 'include', 'gz_ros_bridge.launch.py')),
                launch_arguments={'entity': name}.items(),
                condition=IfCondition(ros_bridge),
            ),
        ])

        nav_group = GroupAction(actions=[
            SetRemap(src='/global_costmap/scan', dst='/scan', condition=IfCondition(PythonExpression([one_robot, ' and ', nav2_flag]))),
            SetRemap(src='/local_costmap/scan',  dst='/scan', condition=IfCondition(PythonExpression([one_robot, ' and ', nav2_flag]))),
            SetRemap(src='/' + name + '/global_costmap/scan', dst='/' + name + '/scan', condition=IfCondition(PythonExpression([more_than_one, ' and ', nav2_flag]))),
            SetRemap(src='/' + name + '/local_costmap/scan',  dst='/' + name + '/scan', condition=IfCondition(PythonExpression([more_than_one, ' and ', nav2_flag]))),

            TimerAction(period=8.0, actions=[
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')),
                    launch_arguments={'map': map_yaml_path, 'autostart': 'True', 'use_sim_time': 'True', 'params_file': params_file}.items(),
                    condition=IfCondition(PythonExpression([one_robot, ' and ', nav2_flag])),
                ),
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')),
                    launch_arguments={'namespace': name, 'use_namespace': 'True', 'map': map_yaml_path, 'autostart': 'True', 'use_sim_time': 'True', 'params_file': params_file}.items(),
                    condition=IfCondition(PythonExpression([more_than_one, ' and ', nav2_flag])),
                ),
            ]),

            # ---------- Auto initialpose (world -> map باستخدام origin) ----------
            TimerAction(period=10.0, actions=[
                ExecuteProcess(
                    cmd=[
                        'python3','-c',
                        (
                            'import rclpy, math, os, yaml; '
                            'from geometry_msgs.msg import PoseWithCovarianceStamped; '
                            'from rclpy.node import Node; '
                            'rclpy.init(); '
                            'topic=os.environ["TOPIC"]; '
                            'xw=float(os.environ["SPAWN_X"]); '
                            'yw=float(os.environ["SPAWN_Y"]); '
                            'yaw=float(os.environ["SPAWN_YAW"]); '
                            'yaml_path=os.environ["MAP_YAML"]; '
                            'x_arg=os.environ.get("INITPOSE_X","__spawn__"); '
                            'y_arg=os.environ.get("INITPOSE_Y","__spawn__"); '
                            'yawd_arg=os.environ.get("INITPOSE_YAWD","__spawn__"); '
                            # اقرأ origin من الـ YAML
                            'ox=0.0; oy=0.0; '
                            'try:\n'
                            '  with open(yaml_path,"r") as f:\n'
                            '    info=yaml.safe_load(f) or {};\n'
                            '    if isinstance(info.get("origin",None),(list,tuple)) and len(info["origin"])>=2:\n'
                            '      ox=float(info["origin"][0]); oy=float(info["origin"][1]);\n'
                            'except Exception as e:\n'
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
                        'TOPIC': (ns_initialpose_topic if nrobots>1 else '/initialpose'),
                        'SPAWN_X': str(sp['x']),
                        'SPAWN_Y': str(sp['y']),
                        'SPAWN_YAW': str(sp['yaw']),
                        'MAP_YAML': map_yaml_path.perform({}),
                        'INITPOSE_X': initpose_x,
                        'INITPOSE_Y': initpose_y,
                        'INITPOSE_YAWD': initpose_yaw_deg,
                    }
                )
            ]),

            # مسح الـ costmaps بعد الـ pose
            TimerAction(period=12.0, actions=[
                ExecuteProcess(cmd=['/bin/bash','-lc',
                                    ('ros2 service call '
                                     + ('/' + name if nrobots>1 else '')
                                     + '/global_costmap/clear_entirely_global_costmap std_srvs/srv/Empty "{}"')],
                              output='screen'),
                ExecuteProcess(cmd=['/bin/bash','-lc',
                                    ('ros2 service call '
                                     + ('/' + name if nrobots>1 else '')
                                     + '/local_costmap/clear_entirely_local_costmap std_srvs/srv/Empty "{}"')],
                              output='screen'),
            ]),
        ])

        spawn_groups += [robots_group, nav_group]

    # ---------------- Launch Description ----------------
    ld = LaunchDescription()
    for a in (ros_bridge_arg, rviz_arg, world_name_arg, robots_arg, gui_config_arg,
              nav2_arg, map_name_arg, params_file_arg,
              initpose_x_arg, initpose_y_arg, initpose_yaw_deg_arg):
        ld.add_action(a)

    ld.add_action(log_world_path)
    ld.add_action(log_map_path)
    ld.add_action(base_group)

    for g in spawn_groups:
        ld.add_action(g)

    return ld
