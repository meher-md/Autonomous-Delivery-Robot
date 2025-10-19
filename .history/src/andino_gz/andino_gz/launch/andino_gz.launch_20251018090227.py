#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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
    pkg_andino_gz    = get_package_share_directory('andino_gz')
    pkg_nav2_bringup = get_package_share_directory('nav2_bringup')
    pkg_ros_gz_sim   = get_package_share_directory('ros_gz_sim')

    # ---------------- Launch Args ----------------
    ros_bridge_arg = DeclareLaunchArgument('ros_bridge', default_value='True',
                                           description='Run ROS–Gazebo bridge.')
    rviz_arg       = DeclareLaunchArgument('rviz', default_value='True', description='Start RViz.')
    world_name_arg = DeclareLaunchArgument('world_name', default_value='office.sdf',
                                           description='World file (should match the map).')
    robots_arg     = DeclareLaunchArgument(
        'robots',
        default_value="andino={x: 0., y: 0., z: 0.1, yaw: 0.};",
        description='Robots to spawn; separate multiple with semicolons.'
    )
    gui_config_arg = DeclareLaunchArgument('gui_config', default_value='default.config',
                                           description='Gazebo GUI configuration file.')
    nav2_arg       = DeclareLaunchArgument('nav2', default_value='True', description='Enable Nav2.')
    map_name_arg   = DeclareLaunchArgument('map', default_value='office',
                                           description='Map folder under andino_gz/maps/<map>/<map>.yaml')
    params_file_arg = DeclareLaunchArgument(
        'params_file',
        default_value=PathJoinSubstitution([pkg_andino_gz, 'config', 'nav2_params.yaml']),
        description='Nav2 parameters YAML.'
    )

    # Initial pose (map frame)
    initpose_x_arg       = DeclareLaunchArgument('initpose_x',       default_value='0.0')
    initpose_y_arg       = DeclareLaunchArgument('initpose_y',       default_value='0.0')
    initpose_yaw_deg_arg = DeclareLaunchArgument('initpose_yaw_deg', default_value='0.0')

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
    world_path      = PathJoinSubstitution([pkg_andino_gz, 'worlds', world_name])
    gui_config_path = PathJoinSubstitution([pkg_andino_gz, 'config_gui', gui_config])
    # مسار الـ YAML الكامل
    map_yaml_path   = PathJoinSubstitution([pkg_andino_gz, 'maps', map_name,
                                            TextJoin(substitutions=[map_name, '.yaml'])])

    log_world_path = LogInfo(msg=TextJoin(substitutions=["World path: ", world_path]))
    log_map_path   = LogInfo(msg=TextJoin(substitutions=["Map YAML:   ", map_yaml_path]))

    # ---------------- Gazebo ----------------
    gz_args = TextJoin(
        substitutions=[world_path, TextJoin(substitutions=["--gui-config", gui_config_path], separator=' ')],
        separator=' ',
    )

    base_group = GroupAction(
        scoped=True, forwarding=False,
        actions=[
            # لتفادي مشاكل GL داخل الكونتينر
            SetEnvironmentVariable('LIBGL_ALWAYS_SOFTWARE', '1'),

            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')),
                launch_arguments={'gz_args': gz_args}.items(),
            ),

            # Bridge للـ /clock
            Node(
                package='ros_gz_bridge', executable='parameter_bridge',
                arguments=['/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock'],
                output='screen', namespace='andino_gz_sim', condition=IfCondition(ros_bridge),
            ),
        ]
    )

    # ---------------- TF ثابت: خلي map == world ----------------
    static_tf_map_to_world = Node(
        package='tf2_ros', executable='static_transform_publisher', name='tf_map_to_world',
        arguments=['0','0','0','0','0','0','map','world'], output='screen'
    )
    # مفيش أي static TF لِـ odom هنا. odom->base_link ييجي من بلجن السير في جازيبو،
    # و map->odom من AMCL داخل Nav2.

    # ---------------- Robots + Nav2 ----------------
    robots_list = ParseMultiRobotPose('robots').value()
    if robots_list == {}:
        robots_list = {"andino": {"x": 0., "y": 0., "z": 0.1, "yaw": 0.}}

    spawn_groups = []
    more_than_one = PythonExpression([TextSubstitution(text=str(len(robots_list.keys()))), ' > 1'])
    one_robot     = PythonExpression([TextSubstitution(text=str(len(robots_list.keys()))), ' == 1'])

    # شوية تأخير عشان TF و /clock يستقروا
    rviz_delay = 5.0
    nav2_delay = 8.0

    for robot_name, init_pose in robots_list.items():

        robot_group = GroupAction(
            scoped=True, forwarding=False,
            actions=[
                PushRosNamespace(condition=IfCondition(more_than_one), namespace=robot_name),

                # Spawn الروبوت في جازيبو
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(os.path.join(pkg_andino_gz, 'launch', 'include', 'spawn_robot.launch.py')),
                    launch_arguments={
                        'entity': robot_name,
                        'initial_pose_x': str(init_pose['x']),
                        'initial_pose_y': str(init_pose['y']),
                        'initial_pose_z': str(init_pose['z']),
                        'initial_pose_yaw': str(init_pose['yaw']),
                        'robot_description_topic': 'robot_description',
                        'use_sim_time': 'true',
                    }.items(),
                ),

                # Robot State Publisher (TF للّينكات)
                Node(
                    package='robot_state_publisher', executable='robot_state_publisher',
                    name='robot_state_publisher', output='screen',
                    parameters=[{'use_sim_time': True}],
                    remappings=[('robot_description', 'robot_description')],
                ),

                # RViz (Nav2)
                TimerAction(
                    period=rviz_delay,
                    actions=[
                        Node(
                            condition=IfCondition(PythonExpression([rviz, ' and ', nav2_flag])),
                            package='rviz2', executable='rviz2',
                            arguments=['-d', os.path.join(pkg_andino_gz, 'rviz', 'andino_gz_nav2.rviz')],
                            parameters=[{'use_sim_time': True}],
                            remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
                            output='screen',
                            additional_env={'QT_QPA_PLATFORM': 'xcb', 'LIBGL_ALWAYS_SOFTWARE': '1'}
                        )
                    ]
                ),

                # Bridgeات للروبوت (لو مفعّل)
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(os.path.join(pkg_andino_gz, 'launch', 'include', 'gz_ros_bridge.launch.py')),
                    launch_arguments={'entity': robot_name}.items(),
                    condition=IfCondition(LaunchConfiguration('ros_bridge')),
                ),
            ]
        )

        nav_group = GroupAction(
            scoped=True, forwarding=False,
            actions=[
                # Remap للّيدار
                SetRemap(src='/global_costmap/scan', dst='/scan',
                         condition=IfCondition(PythonExpression([one_robot, ' and ', nav2_flag]))),
                SetRemap(src='/local_costmap/scan', dst='/scan',
                         condition=IfCondition(PythonExpression([one_robot, ' and ', nav2_flag]))),
                SetRemap(src='/' + robot_name + '/global_costmap/scan', dst='/' + robot_name + '/scan',
                         condition=IfCondition(PythonExpression([more_than_one, ' and ', nav2_flag]))),
                SetRemap(src='/' + robot_name + '/local_costmap/scan', dst='/' + robot_name + '/scan',
                         condition=IfCondition(PythonExpression([more_than_one, ' and ', nav2_flag]))),

                # Nav2 bringup (مرّر YAML الكامل للـ map)
                TimerAction(
                    period=nav2_delay,
                    actions=[
                        IncludeLaunchDescription(
                            PythonLaunchDescriptionSource(os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')),
                            launch_arguments={
                                'map': map_yaml_path,
                                'autostart': 'True',
                                'use_sim_time': 'True',
                                'params_file': params_file,
                            }.items(),
                            condition=IfCondition(PythonExpression([one_robot, ' and ', nav2_flag])),
                        ),
                        IncludeLaunchDescription(
                            PythonLaunchDescriptionSource(os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')),
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
            ]
        )

        spawn_groups += [robot_group, nav_group]

    # ---------------- Auto initial pose + clear costmaps ----------------
    auto_initial_pose = TimerAction(
        period=10.0,
        actions=[
            ExecuteProcess(
                cmd=[
                    'python3','-c',
                    (
                        'import rclpy, math, sys; '
                        'from geometry_msgs.msg import PoseWithCovarianceStamped; '
                        'from rclpy.node import Node; '
                        'rclpy.init(); '
                        'n=Node("auto_initialpose"); '
                        'p=n.create_publisher(PoseWithCovarianceStamped,"/initialpose",10); '
                        'x=float(sys.argv[1]); y=float(sys.argv[2]); yaw_deg=float(sys.argv[3]); '
                        'qz=math.sin(math.radians(yaw_deg)/2.0); '
                        'qw=math.cos(math.radians(yaw_deg)/2.0); '
                        'm=PoseWithCovarianceStamped(); '
                        'm.header.frame_id="map"; '
                        'm.pose.pose.position.x=x; m.pose.pose.position.y=y; '
                        'm.pose.pose.orientation.z=qz; m.pose.pose.orientation.w=qw; '
                        'm.pose.covariance[0]=0.25; m.pose.covariance[7]=0.25; m.pose.covariance[35]=0.05; '
                        'p.publish(m); '
                        'n.get_logger().info(f"Auto initial pose published: x={x:.3f}, y={y:.3f}, yaw_deg={yaw_deg:.1f}"); '
                        'rclpy.shutdown()'
                    ),
                    initpose_x, initpose_y, initpose_yaw_deg
                ],
                output='screen'
            )
        ]
    )

    clear_costmaps_once = TimerAction(
        period=nav2_delay + 4.0,  # بعد ما العقد تقوم
        actions=[
            ExecuteProcess(
                cmd=['/bin/bash','-lc','ros2 service call /global_costmap/clear_entirely_global_costmap std_srvs/srv/Empty "{}"'],
                output='screen'
            ),
            ExecuteProcess(
                cmd=['/bin/bash','-lc','ros2 service call /local_costmap/clear_entirely_local_costmap std_srvs/srv/Empty "{}"'],
                output='screen'
            ),
        ]
    )

    # ---------------- Launch Description ----------------
    ld = LaunchDescription()

    # args
    for a in (ros_bridge_arg, rviz_arg, world_name_arg, robots_arg, gui_config_arg,
              nav2_arg, map_name_arg, params_file_arg, initpose_x_arg, initpose_y_arg, initpose_yaw_deg_arg):
        ld.add_action(a)

    # logs + gazebo
    ld.add_action(log_world_path)
    ld.add_action(log_map_path)
    ld.add_action(base_group)

    # TF الثابت
    ld.add_action(static_tf_map_to_world)

    # الروبوتات + Nav2
    for g in spawn_groups:
        ld.add_action(g)

    # أوتوميشن بدء
    ld.add_action(auto_initial_pose)
    ld.add_action(clear_costmaps_once)

    return ld
