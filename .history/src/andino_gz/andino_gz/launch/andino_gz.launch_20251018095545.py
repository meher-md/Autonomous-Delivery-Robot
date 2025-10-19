#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import yaml
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
    OpaqueFunction,
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

    # ---------------- Launch Arguments ----------------
    ros_bridge_arg = DeclareLaunchArgument(
        'ros_bridge', default_value='True', description='Run ROS–Gazebo bridge.'
    )
    rviz_arg = DeclareLaunchArgument('rviz', default_value='True', description='Start RViz.')
    world_name_arg = DeclareLaunchArgument(
        'world_name', default_value='office.sdf',
        description='World file (should match the map).'
    )
    robots_arg = DeclareLaunchArgument(
        'robots',
        default_value="andino={x: 0., y: 0., z: 0.1, yaw: 0.};",
        description='Robots to spawn; separate multiple with semicolons.'
    )
    gui_config_arg = DeclareLaunchArgument(
        'gui_config', default_value='default.config',
        description='Gazebo GUI configuration file.'
    )
    nav2_arg = DeclareLaunchArgument('nav2', default_value='True', description='Enable Nav2.')
    map_name_arg = DeclareLaunchArgument(
        'map', default_value='office',
        description='Map folder under andino_gz/maps/<map>/<map>.yaml'
    )
    params_file_arg = DeclareLaunchArgument(
        'params_file',
        default_value=PathJoinSubstitution([pkg_andino_gz, 'config', 'nav2_params.yaml']),
        description='Nav2 parameters YAML.'
    )
    # Optional: auto initialpose
    auto_initpose_arg = DeclareLaunchArgument(
        'auto_initpose', default_value='True',
        description='Auto-publish initial pose(s) to AMCL equal to Gazebo spawn.'
    )

    # NEW: كيف نضبط علاقة map↔world
    map_world_align_arg = DeclareLaunchArgument(
        'map_world_align',
        default_value='use_map_origin',  # أو identity
        description="use_map_origin: اجعل map->world يساوي origin من الـ YAML. identity: اجعلها (0,0,0)."
    )

    # ---------------- Launch Configurations ----------------
    rviz        = LaunchConfiguration('rviz')
    ros_bridge  = LaunchConfiguration('ros_bridge')
    world_name  = LaunchConfiguration('world_name')
    map_name    = LaunchConfiguration('map')
    gui_config  = LaunchConfiguration('gui_config')
    nav2_flag   = LaunchConfiguration('nav2')
    params_file = LaunchConfiguration('params_file')
    auto_initpose = LaunchConfiguration('auto_initpose')
    map_world_align = LaunchConfiguration('map_world_align')

    # ---------------- Paths ----------------
    world_path      = PathJoinSubstitution([pkg_andino_gz, 'worlds', world_name])
    gui_config_path = PathJoinSubstitution([pkg_andino_gz, 'config_gui', gui_config])
    map_yaml_path   = PathJoinSubstitution([
        pkg_andino_gz, 'maps', map_name, TextJoin(substitutions=[map_name, '.yaml'])
    ])

    log_world_path = LogInfo(msg=TextJoin(substitutions=["World path: ", world_path]))
    log_map_path   = LogInfo(msg=TextJoin(substitutions=["Map YAML:   ", map_yaml_path]))

    # ---------------- Gazebo ----------------
    gz_args = TextJoin(
        substitutions=[
            world_path,
            TextJoin(substitutions=["--gui-config", gui_config_path], separator=' ')
        ],
        separator=' ',
    )

    base_group = GroupAction(
        actions=[
            # Stable RViz / GUI inside containers (software rendering)
            SetEnvironmentVariable('LIBGL_ALWAYS_SOFTWARE', '1'),

            # Gazebo Sim
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
                ),
                launch_arguments={'gz_args': gz_args}.items(),
            ),

            # Bridge /clock from Gazebo to ROS
            Node(
                package='ros_gz_bridge', executable='parameter_bridge',
                arguments=['/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock'],
                output='screen', namespace='andino_gz_sim',
                condition=IfCondition(ros_bridge),
            ),
        ]
    )

    # ---------------- Static TF map↔world (مُعدّل) ----------------
    # نستخدم OpaqueFunction لقراءة ملف الـ YAML بعد حل الـ substitutions.
    def _make_static_tf(context):
        align_mode = map_world_align.perform(context)
        yaml_path = map_yaml_path.perform(context)

        x_off, y_off = 0.0, 0.0
        if align_mode == 'use_map_origin':
            try:
                with open(yaml_path, 'r') as f:
                    info = yaml.safe_load(f) or {}
                origin = info.get('origin', [0.0, 0.0, 0.0])
                # origin: [x, y, yaw] حسب مواصفات map_server
                x_off = float(origin[0])
                y_off = float(origin[1])
            except Exception as e:
                # لو فشل القراءة نرجع للهوية ونطبع لوج
                return [LogInfo(msg=f"[map_world_align] Failed to read origin from {yaml_path}: {e}"),
                        Node(
                            package='tf2_ros', executable='static_transform_publisher',
                            name='tf_map_to_world',
                            arguments=['0','0','0','0','0','0','map','world'],
                            output='screen'
                        )]

        return [
            LogInfo(msg=f"[map_world_align] map->world translation set to ({x_off:.3f}, {y_off:.3f}, 0.0)"),
            Node(
                package='tf2_ros', executable='static_transform_publisher',
                name='tf_map_to_world',
                # x y z roll pitch yaw parent child
                arguments=[str(x_off), str(y_off), '0', '0','0','0','map','world'],
                output='screen'
            )
        ]

    static_tf_setup = OpaqueFunction(function=_make_static_tf)

    # ---------------- Robots + Nav2 ----------------
    robots_list = ParseMultiRobotPose('robots').value()
    if robots_list == {}:
        robots_list = {"andino": {"x": 0., "y": 0., "z": 0.1, "yaw": 0.}}

    spawn_groups = []
    nrobots = len(robots_list.keys())
    more_than_one = PythonExpression([TextSubstitution(text=str(nrobots)), ' > 1'])
    one_robot     = PythonExpression([TextSubstitution(text=str(nrobots)), ' == 1'])

    # Small delays so TF/clock settle
    rviz_delay = 5.0
    nav2_delay = 8.0

    for robot_name, init_pose in robots_list.items():
        # Compose the namespaced initialpose topic if multi-robot
        ns_initialpose_topic = '/' + robot_name + '/initialpose'

        robot_group = GroupAction(
            actions=[
                PushRosNamespace(condition=IfCondition(more_than_one), namespace=robot_name),

                # Spawn the robot in Gazebo (world frame)
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(pkg_andino_gz, 'launch', 'include', 'spawn_robot.launch.py')
                    ),
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

                # Robot State Publisher (TFs of links/sensors)
                Node(
                    package='robot_state_publisher',
                    executable='robot_state_publisher',
                    name='robot_state_publisher',
                    output='screen',
                    parameters=[{'use_sim_time': True}],
                    remappings=[('robot_description', 'robot_description')],
                ),

                # RViz (Nav2 layout)
                TimerAction(
                    period=rviz_delay,
                    actions=[
                        Node(
                            condition=IfCondition(PythonExpression([rviz, ' and ', nav2_flag])),
                            package='rviz2',
                            executable='rviz2',
                            arguments=['-d', os.path.join(pkg_andino_gz, 'rviz', 'andino_gz_nav2.rviz')],
                            parameters=[{'use_sim_time': True}],
                            remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
                            output='screen',
                            additional_env={'QT_QPA_PLATFORM': 'xcb', 'LIBGL_ALWAYS_SOFTWARE': '1'}
                        )
                    ]
                ),

                # Per-robot Gazebo↔ROS bridges
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(pkg_andino_gz, 'launch', 'include', 'gz_ros_bridge.launch.py')
                    ),
                    launch_arguments={'entity': robot_name}.items(),
                    condition=IfCondition(ros_bridge),
                ),
            ]
        )

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

                # Nav2 bringup (pass FULL map YAML path)
                TimerAction(
                    period=nav2_delay,
                    actions=[
                        # Single robot
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
                        # Multi-robot (namespaced)
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

                # Auto-publish initial pose to AMCL equal to Gazebo spawn
                TimerAction(
                    period=nav2_delay + 2.0,
                    actions=[
                        ExecuteProcess(
                            condition=IfCondition(auto_initpose),
                            cmd=[
                                'python3','-c',
                                (
                                    'import rclpy, math, sys; '
                                    'from geometry_msgs.msg import PoseWithCovarianceStamped; '
                                    'from rclpy.node import Node; '
                                    'rclpy.init(); '
                                    'n=Node("auto_initialpose_%s"); ' % robot_name +
                                    'p=n.create_publisher(PoseWithCovarianceStamped,"' +
                                    (ns_initialpose_topic if nrobots > 1 else '/initialpose') +
                                    '",10); '
                                    f'x={{x}}; y={{y}}; yaw={{yaw}}; '.format(
                                        x=float(init_pose["x"]), y=float(init_pose["y"]), yaw=float(init_pose["yaw"])
                                    ) +
                                    'qz=math.sin(yaw/2.0); qw=math.cos(yaw/2.0); '
                                    'm=PoseWithCovarianceStamped(); '
                                    'm.header.frame_id="map"; '
                                    'm.pose.pose.position.x=x; m.pose.pose.position.y=y; '
                                    'm.pose.pose.orientation.z=qz; m.pose.pose.orientation.w=qw; '
                                    'm.pose.covariance[0]=0.25; m.pose.covariance[7]=0.25; m.pose.covariance[35]=0.05; '
                                    'p.publish(m); '
                                    'n.get_logger().info(f"[auto_initialpose] {x=}, {y=}, yaw(rad)={yaw:.3f}"); '
                                    'rclpy.shutdown()'
                                ),
                            ],
                            output='screen'
                        )
                    ]
                ),

                # One-shot clear costmaps shortly after AMCL gets the pose
                TimerAction(
                    period=nav2_delay + 4.0,
                    actions=[
                        ExecuteProcess(
                            cmd=['/bin/bash','-lc',
                                 'ros2 service call /global_costmap/clear_entirely_global_costmap std_srvs/srv/Empty "{}"'],
                            output='screen'
                        ),
                        ExecuteProcess(
                            cmd=['/bin/bash','-lc',
                                 'ros2 service call /local_costmap/clear_entirely_local_costmap std_srvs/srv/Empty "{}"'],
                            output='screen'
                        ),
                    ]
                ),
            ]
        )

        spawn_groups += [robot_group, nav_group]

    # ---------------- Launch Description ----------------
    ld = LaunchDescription()

    # Declare args
    for a in (ros_bridge_arg, rviz_arg, world_name_arg, robots_arg, gui_config_arg,
              nav2_arg, map_name_arg, params_file_arg, auto_initpose_arg, map_world_align_arg):
        ld.add_action(a)

    # Logs + Gazebo
    ld.add_action(log_world_path)
    ld.add_action(log_map_path)
    ld.add_action(base_group)

    # TF fix (map relative to world من الـ YAML أو هوية)
    ld.add_action(static_tf_setup)

    # Robots + Nav2
    for g in spawn_groups:
        ld.add_action(g)

    return ld
