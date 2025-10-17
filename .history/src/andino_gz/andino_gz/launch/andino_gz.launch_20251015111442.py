#!/usr/bin/env python3

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    LogInfo,
    TimerAction
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    PythonExpression,
    TextSubstitution
)
from launch_ros.actions import Node, PushRosNamespace, SetRemap
from nav2_common.launch import ParseMultiRobotPose
from andino_gz.launch_tools.substitutions import TextJoin


def generate_launch_description():
    pkg_andino_gz = get_package_share_directory('andino_gz')
    pkg_nav2_bringup = get_package_share_directory('nav2_bringup')

    # ====== Launch Args ======
    ros_bridge_arg = DeclareLaunchArgument('ros_bridge', default_value='True')
    rviz_arg = DeclareLaunchArgument('rviz', default_value='True')
    world_arg = DeclareLaunchArgument('world_name', default_value='populated_office.sdf')
    robots_arg = DeclareLaunchArgument('robots', default_value="andino={x: 0., y: 0., z: 0.1, yaw: 0.};")
    gui_config_arg = DeclareLaunchArgument('gui_config', default_value='default.config')
    nav2_arg = DeclareLaunchArgument('nav2', default_value='True')
    map_arg = DeclareLaunchArgument('map', default_value='office')
    params_file_arg = DeclareLaunchArgument(
        'params_file',
        default_value=PathJoinSubstitution([pkg_andino_gz, 'config', 'nav2_params.yaml'])
    )

    # ====== Configs ======
    rviz = LaunchConfiguration('rviz')
    world = LaunchConfiguration('world_name')
    gui_config = LaunchConfiguration('gui_config')
    ros_bridge = LaunchConfiguration('ros_bridge')
    nav2_flag = LaunchConfiguration('nav2')
    params_file = LaunchConfiguration('params_file')
    map_name = LaunchConfiguration('map')

    # ====== Paths ======
    world_path = PathJoinSubstitution([pkg_andino_gz, 'worlds', world])
    gui_config_path = PathJoinSubstitution([pkg_andino_gz, 'config_gui', gui_config])
    map_path = PathJoinSubstitution([pkg_andino_gz, 'maps', map_name, TextJoin(substitutions=[map_name, '.yaml'])])

    log_world_path = LogInfo(msg=TextJoin(substitutions=["World path: ", world_path]))
    log_map_path = LogInfo(msg=TextJoin(substitutions=["Map path: ", map_path]))

    # ====== Gazebo ======
    gz_args = TextJoin(substitutions=[
        world_path,
        TextJoin(substitutions=["--gui-config", gui_config_path], separator=' ')
    ], separator=' ')

    base_group = GroupAction(actions=[
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')
            ),
            launch_arguments={'gz_args': gz_args}.items(),
        ),
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            arguments=['/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock'],
            output='screen',
            namespace='andino_gz_sim',
            condition=IfCondition(ros_bridge),
        ),
    ])

    # ====== Robots ======
    robots_list = ParseMultiRobotPose('robots').value()
    if (robots_list == {}):
        robots_list = {"andino": {"x": 0., "y": 0., "z": 0.1, "yaw": 0.}}

    spawn_robots_group = []
    for robot_name in robots_list:
        init_pose = robots_list[robot_name]

        robots_group = GroupAction(actions=[
            LogInfo(msg="Launching robot: " + robot_name),
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
                    'use_sim_time': 'true',
                }.items(),
            ),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(pkg_andino_gz, 'launch', 'include', 'gz_ros_bridge.launch.py')
                ),
                launch_arguments={'entity': robot_name}.items(),
                condition=IfCondition(ros_bridge),
            ),

            # Run RViz after delay to avoid crash
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
                        output='screen'
                    )
                ]
            ),
        ])

        # Nav2 bringup
        nav_group = GroupAction(actions=[
            SetRemap(src='/global_costmap/scan', dst='/scan'),
            SetRemap(src='/local_costmap/scan', dst='/scan'),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')
                ),
                launch_arguments={
                    'map': map_path,
                    'autostart': 'True',
                    'use_sim_time': 'True',
                    'params_file': params_file,
                }.items(),
                condition=IfCondition(nav2_flag),
            )
        ])

        spawn_robots_group.append(robots_group)
        spawn_robots_group.append(nav_group)

    # ====== Auto Initial Pose Publisher ======
    auto_pose = TimerAction(
        period=10.0,  # wait until nav2 & tf are ready
        actions=[
            Node(
                package='rclpy',
                executable='executables',
                name='auto_initial_pose',
                output='screen',
                parameters=[{'use_sim_time': True}],
                # Inline Python node
                exec_name='python3',
                arguments=['-c', """
import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped
from rclpy.node import Node
rclpy.init()
node = rclpy.create_node('auto_initial_pose')
pub = node.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)
msg = PoseWithCovarianceStamped()
msg.header.frame_id = 'map'
msg.pose.pose.position.x = 0.0
msg.pose.pose.position.y = 0.0
msg.pose.pose.orientation.w = 1.0
msg.pose.covariance[0] = 0.25
msg.pose.covariance[7] = 0.25
msg.pose.covariance[35] = 0.1
pub.publish(msg)
node.get_logger().info('✅ Auto initial pose published')
rclpy.shutdown()
                """]
            )
        ]
    )

    # ====== Launch Description ======
    ld = LaunchDescription()
    ld.add_action(ros_bridge_arg)
    ld.add_action(rviz_arg)
    ld.add_action(world_arg)
    ld.add_action(robots_arg)
    ld.add_action(gui_config_arg)
    ld.add_action(nav2_arg)
    ld.add_action(map_arg)
    ld.add_action(params_file_arg)
    ld.add_action(log_world_path)
    ld.add_action(log_map_path)
    ld.add_action(base_group)
    for group in spawn_robots_group:
        ld.add_action(group)
    ld.add_action(auto_pose)

    return ld
