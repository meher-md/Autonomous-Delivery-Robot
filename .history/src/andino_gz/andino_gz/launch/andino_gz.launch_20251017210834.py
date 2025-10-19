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
from launch_ros.actions import Node, PushRosNamespace
from nav2_common.launch import ParseMultiRobotPose

# ---------- small helper ----------
def text_join(parts, sep=' '):
    return TextSubstitution(text=sep.join(str(p) for p in parts))

def generate_launch_description():
    pkg_andino_gz   = get_package_share_directory('andino_gz')
    pkg_nav2_bringup = get_package_share_directory('nav2_bringup')
    pkg_ros_gz_sim  = get_package_share_directory('ros_gz_sim')

    # ---------------- Launch Args ----------------
    ros_bridge_arg = DeclareLaunchArgument(
        'ros_bridge', default_value='True', description='Run ROS<->GZ bridge(s).'
    )
    rviz_arg = DeclareLaunchArgument(
        'rviz', default_value='True', description='Start RViz.'
    )
    world_name_arg = DeclareLaunchArgument(
        'world_name', default_value='populated_office.sdf',
        description='World SDF to load (e.g. office.sdf).'
    )
    robots_arg = DeclareLaunchArgument(
        'robots',
        default_value="andino={x: 0., y: 0., z: 0.1, yaw: 0.};",
        description='Robots to spawn, separated by ";".'
    )
    gui_config_arg = DeclareLaunchArgument(
        'gui_config', default_value='default.config',
        description='Ignition GUI config file.'
    )
    nav2_arg = DeclareLaunchArgument(
        'nav2', default_value='True', description='Enable Nav2 bringup.'
    )
    map_name_arg = DeclareLaunchArgument(
        'map', default_value='office',
        description='Map folder name (must match world).'
    )
    params_file_arg = DeclareLaunchArgument(
        'params_file',
        default_value=PathJoinSubstitution([pkg_andino_gz, 'config', 'nav2_params.yaml']),
        description='Nav2 params file.'
    )

    # Initial pose (map frame)
    initpose_x_arg = DeclareLaunchArgument('initpose_x', default_value='0.0', description='Initial X (map).')
    initpose_y_arg = DeclareLaunchArgument('initpose_y', default_value='0.0', description='Initial Y (map).')
    initpose_yaw_deg_arg = DeclareLaunchArgument('initpose_yaw_deg', default_value='0.0', description='Initial yaw deg (map).')

    # ---------------- Launch Configs ----------------
    rviz        = LaunchConfiguration('rviz')
    ros_bridge  = LaunchConfiguration('ros_bridge')
    world_name  = LaunchConfiguration('world_name')
    map_name    = LaunchConfiguration('map')
    gui_config  = LaunchConfiguration('gui_config')
    nav2_flag   = LaunchConfiguration('nav2')
    params_file = LaunchConfiguration('params_file')

    initpose_x      = LaunchConfiguration('initpose_x')
    initpose_y      = LaunchConfiguration('initpose_y')
    initpose_yawdeg = LaunchConfiguration('initpose_yaw_deg')

    # ---------------- Paths ----------------
    world_path      = PathJoinSubstitution([pkg_andino_gz, 'worlds', world_name])
    gui_config_path = PathJoinSubstitution([pkg_andino_gz, 'config_gui', gui_config])
    map_path        = PathJoinSubstitution([pkg_andino_gz, 'maps', map_name, text_join([map_name, '.yaml'], '')])

    log_world_path = LogInfo(msg=text_join(["World path: ", world_path]))
    log_map_path   = LogInfo(msg=text_join(["Map path: ", map_path]))

    # ---------------- Global env (LOCAL ONLY + stable GL) ----------------
    env_local_only = SetEnvironmentVariable('ROS_LOCALHOST_ONLY', '1')  # keep all traffic on loopback
    env_gl_soft    = SetEnvironmentVariable('LIBGL_ALWAYS_SOFTWARE', '1')
    env_qt_xcb     = SetEnvironmentVariable('QT_QPA_PLATFORM', 'xcb')

    # ---------------- Gazebo Sim ----------------
    gz_args = text_join([world_path, text_join(["--gui-config", gui_config_path])])
    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={'gz_args': gz_args}.items(),
    )

    # ---------------- Static TF fix ----------------
    # IMPORTANT: publish ONLY world -> map (identity). Do NOT publish odom->world or similar.
    static_tf_world_to_map = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='tf_world_to_map',
        arguments=['0', '0', '0', '0', '0', '0', 'world', 'map'],  # parent=world, child=map
        output='screen'
    )

    # ---------------- Robots + Nav2 ----------------
    robots_list = ParseMultiRobotPose('robots').value()
    log_robots_by_user = LogInfo(msg="Robots provided by user.")
    if robots_list == {}:
        log_robots_by_user = LogInfo(msg="No robots provided, using default.")
        robots_list = {"andino": {"x": 0., "y": 0., "z": 0.1, "yaw": 0.}}

    log_number_robots = LogInfo(msg="Robots to spawn: " + str(robots_list))
    spawn_groups = []

    more_than_one = PythonExpression([TextSubstitution(text=str(len(robots_list.keys()))), ' > 1'])
    one_robot     = PythonExpression([TextSubstitution(text=str(len(robots_list.keys()))), ' == 1'])

    for robot_name, pose in robots_list.items():
        group_spawn = GroupAction(
            scoped=True, forwarding=False,
            launch_configurations={
                'rviz': rviz,
                'ros_bridge': ros_bridge,
                'nav2': nav2_flag,
            },
            actions=[
                LogInfo(msg="Group for robot: " + robot_name),

                # Namespace only if multi-robot
                PushRosNamespace(
                    condition=IfCondition(more_than_one),
                    namespace=robot_name
                ),

                # Spawn robot in Gazebo
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(pkg_andino_gz, 'launch', 'include', 'spawn_robot.launch.py')
                    ),
                    launch_arguments={
                        'entity': robot_name,
                        'initial_pose_x': str(pose['x']),
                        'initial_pose_y': str(pose['y']),
                        'initial_pose_z': str(pose['z']),
                        'initial_pose_yaw': str(pose['yaw']),
                        'robot_description_topic': 'robot_description',
                        'use_sim_time': 'true',
                    }.items(),
                ),

                # RViz with Nav2 layout (software rendering to avoid GL crash)
                TimerAction(
                    period=5.0,
                    actions=[
                        Node(
                            condition=IfCondition(PythonExpression([rviz, ' and ', LaunchConfiguration('nav2')])),
                            package='rviz2',
                            executable='rviz2',
                            arguments=['-d', os.path.join(pkg_andino_gz, 'rviz', 'andino_gz_nav2.rviz')],
                            parameters=[{'use_sim_time': True}],
                            remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
                            output='screen',
                            additional_env={'LIBGL_ALWAYS_SOFTWARE': '1', 'QT_QPA_PLATFORM': 'xcb'}
                        )
                    ]
                ),

                # RViz without Nav2 (fallback layout)
                TimerAction(
                    period=5.0,
                    actions=[
                        Node(
                            condition=IfCondition(PythonExpression([rviz, ' and not ', LaunchConfiguration('nav2')])),
                            package='rviz2',
                            executable='rviz2',
                            arguments=['-d', os.path.join(pkg_andino_gz, 'rviz', 'andino_gz.rviz')],
                            parameters=[{'use_sim_time': True}],
                            remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
                            output='screen',
                            additional_env={'LIBGL_ALWAYS_SOFTWARE': '1', 'QT_QPA_PLATFORM': 'xcb'}
                        )
                    ]
                ),

                # Per-robot Gazebo<->ROS bridges (includes TF, odom, scan, etc.)
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(pkg_andino_gz, 'launch', 'include', 'gz_ros_bridge.launch.py')
                    ),
                    launch_arguments={'entity': robot_name}.items(),
                    condition=IfCondition(ros_bridge),
                ),
            ]
        )

        # Nav2 bringup (single or multi robot)
        group_nav2 = GroupAction(
            scoped=True, forwarding=False,
            launch_configurations={
                'rviz': rviz,
                'ros_bridge': ros_bridge,
                'map': map_path,
                'params_file': params_file,
                'nav2': nav2_flag,
            },
            actions=[
                # Remap scans for single robot
                Node(
                    package='nav2_util',
                    executable='empty_server',  # placeholder no-op; remaps below are applied by bringup include
                    name='noop_single',
                    condition=IfCondition(PythonExpression([one_robot, ' and ', LaunchConfiguration('nav2')])),
                    remappings=[
                        ('/global_costmap/scan', '/scan'),
                        ('/local_costmap/scan', '/scan')
                    ],
                    output='screen',
                    parameters=[{'use_sim_time': True}],
                ),

                # Nav2 bringup single robot
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')
                    ),
                    launch_arguments={
                        'map': LaunchConfiguration('map'),
                        'autostart': 'True',
                        'use_sim_time': 'True',
                        'params_file': LaunchConfiguration('params_file'),
                    }.items(),
                    condition=IfCondition(PythonExpression([one_robot, ' and ', LaunchConfiguration('nav2')])),
                ),

                # Nav2 bringup multi-robot (namespaced)
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')
                    ),
                    launch_arguments={
                        'namespace': robot_name,
                        'use_namespace': 'True',
                        'map': LaunchConfiguration('map'),
                        'autostart': 'True',
                        'use_sim_time': 'True',
                        'params_file': LaunchConfiguration('params_file'),
                    }.items(),
                    condition=IfCondition(PythonExpression([more_than_one, ' and ', LaunchConfiguration('nav2')])),
                ),
            ]
        )

        spawn_groups.append(group_spawn)
        spawn_groups.append(group_nav2)

    # ---------------- Auto initial pose (publish in map) ----------------
    # Use FastRTPS for this tiny one-shot node to avoid CycloneDDS participant index issue.
    auto_initial_pose = TimerAction(
        period=10.0,
        actions=[
            ExecuteProcess(
                cmd=[
                    'python3', '-c',
                    (
                        'import rclpy, math, sys, time\n'
                        'from geometry_msgs.msg import PoseWithCovarianceStamped\n'
                        'from rclpy.node import Node\n'
                        'rclpy.init()\n'
                        'n = Node("auto_initialpose")\n'
                        'p = n.create_publisher(PoseWithCovarianceStamped, "/initialpose", 10)\n'
                        'x=float(sys.argv[1]); y=float(sys.argv[2]); yaw=float(sys.argv[3])\n'
                        'qz=math.sin(math.radians(yaw)/2.0); qw=math.cos(math.radians(yaw)/2.0)\n'
                        'm=PoseWithCovarianceStamped()\n'
                        'm.header.frame_id="map"\n'
                        'm.pose.pose.position.x=x; m.pose.pose.position.y=y\n'
                        'm.pose.pose.orientation.z=qz; m.pose.pose.orientation.w=qw\n'
                        'm.pose.covariance[0]=0.25; m.pose.covariance[7]=0.25; m.pose.covariance[35]=0.05\n'
                        't_end = time.time() + 3.0\n'
                        'while rclpy.ok() and time.time() < t_end:\n'
                        '    m.header.stamp = n.get_clock().now().to_msg()\n'
                        '    p.publish(m)\n'
                        '    time.sleep(0.05)\n'
                        'n.get_logger().info(f"Initial pose: x={x:.2f}, y={y:.2f}, yaw={yaw:.1f}")\n'
                        'rclpy.shutdown()\n'
                    ),
                    initpose_x, initpose_y, initpose_yawdeg
                ],
                output='screen',
                additional_env={
                    'ROS_LOCALHOST_ONLY': '1',
                    # Force a different RMW for this one-shot publisher to avoid CycloneDDS participant clash
                    'RMW_IMPLEMENTATION': 'rmw_fastrtps_cpp'
                },
            )
        ]
    )

    # ---------------- Clear costmaps after pose ----------------
    clear_costmaps = TimerAction(
        period=13.0,
        actions=[
            ExecuteProcess(
                cmd=['/bin/bash', '-lc', 'ros2 service call /global_costmap/clear_entirely_global_costmap std_srvs/srv/Empty "{}"'],
                output='screen'
            ),
            ExecuteProcess(
                cmd=['/bin/bash', '-lc', 'ros2 service call /local_costmap/clear_entirely_local_costmap std_srvs/srv/Empty "{}"'],
                output='screen'
            ),
        ]
    )

    # ---------------- Launch Description ----------------
    ld = LaunchDescription()

    # Global env
    ld.add_action(env_local_only)
    ld.add_action(env_gl_soft)
    ld.add_action(env_qt_xcb)

    # Args
    ld.add_action(ros_bridge_arg)
    ld.add_action(rviz_arg)
    ld.add_action(world_name_arg)
    ld.add_action(robots_arg)
    ld.add_action(gui_config_arg)
    ld.add_action(nav2_arg)
    ld.add_action(map_name_arg)
    ld.add_action(params_file_arg)
    ld.add_action(initpose_x_arg)
    ld.add_action(initpose_y_arg)
    ld.add_action(initpose_yaw_deg_arg)

    # Logs
    ld.add_action(log_world_path)
    ld.add_action(log_map_path)
    ld.add_action(log_robots_by_user)
    ld.add_action(log_number_robots)

    # Sim + TF
    ld.add_action(gz_sim)
    ld.add_action(static_tf_world_to_map)

    # Robots + Nav2
    for g in spawn_groups:
        ld.add_action(g)

    # Automation (pose + clear)
    ld.add_action(auto_initial_pose)
    ld.add_action(clear_costmaps)

    return ld
