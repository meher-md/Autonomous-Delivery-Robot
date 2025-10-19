#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, GroupAction, IncludeLaunchDescription,
    TimerAction, ExecuteProcess
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

    # ----------------- args -----------------
    ros_bridge_arg  = DeclareLaunchArgument('ros_bridge',  default_value='True')
    rviz_arg        = DeclareLaunchArgument('rviz',        default_value='True')
    world_name_arg  = DeclareLaunchArgument('world_name',  default_value='populated_office.sdf')
    robots_arg      = DeclareLaunchArgument('robots',      default_value="andino={x: 0., y: 0., z: 0.1, yaw: 0.};")
    gui_config_arg  = DeclareLaunchArgument('gui_config',  default_value='default.config')
    nav2_arg        = DeclareLaunchArgument('nav2',        default_value='True')
    map_name_arg    = DeclareLaunchArgument('map',         default_value='office')
    params_file_arg = DeclareLaunchArgument(
        'params_file',
        default_value=PathJoinSubstitution([pkg_andino_gz, 'config', 'nav2_params.yaml'])
    )

    ros_bridge  = LaunchConfiguration('ros_bridge')
    rviz        = LaunchConfiguration('rviz')
    world_name  = LaunchConfiguration('world_name')
    gui_config  = LaunchConfiguration('gui_config')
    nav2_flag   = LaunchConfiguration('nav2')
    map_name    = LaunchConfiguration('map')
    params_file = LaunchConfiguration('params_file')

    world_path      = PathJoinSubstitution([pkg_andino_gz, 'worlds', world_name])
    gui_config_path = PathJoinSubstitution([pkg_andino_gz, 'config_gui', gui_config])
    map_yaml_path   = PathJoinSubstitution([pkg_andino_gz, 'maps', map_name, TextJoin([map_name, '.yaml'])])

    # ----------------- Gazebo -----------------
    gz_args = TextJoin(
        substitutions=[
            world_path,
            TextJoin(substitutions=['--gui-config', gui_config_path], separator=' ')
        ],
        separator=' '
    )

    base_group = GroupAction([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
            ),
            launch_arguments={'gz_args': gz_args}.items(),
        ),
        Node(
            package='ros_gz_bridge', executable='parameter_bridge',
            arguments=['/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock]'],
            output='screen', namespace='andino_gz_sim',
            condition=IfCondition(ros_bridge),
        ),
    ])

    # ----------------- robots & Nav2 -----------------
    robots_list = ParseMultiRobotPose('robots').value() or {"andino": {"x": 0., "y": 0., "z": 0.1, "yaw": 0.}}
    spawn_robots_group = []
    more_than_one_robot = PythonExpression([TextSubstitution(text=str(len(robots_list))), ' > 1'])
    one_robot           = PythonExpression([TextSubstitution(text=str(len(robots_list))), ' == 1'])

    first_robot_name = list(robots_list.keys())[0]
    first_pose = robots_list[first_robot_name]
    init_spawn_x = float(first_pose['x'])
    init_spawn_y = float(first_pose['y'])
    init_spawn_yaw = float(first_pose['yaw'])

    for robot_name, init_pose in robots_list.items():
        robots_group = GroupAction([
            PushRosNamespace(condition=IfCondition(more_than_one_robot), namespace=robot_name),

            # ---- static transform for LIDAR (base_link -> rplidar_laser_link) ----
            Node(
                package='tf2_ros',
                executable='static_transform_publisher',
                name='rplidar_tf_pub',
                arguments=['0.1', '0.0', '0.1', '0', '0', '0', 'base_link', 'rplidar_laser_link'],
                output='screen'
            ),

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

            TimerAction(
                period=5.0,
                actions=[
                    Node(
                        condition=IfCondition(PythonExpression([rviz, ' and ', nav2_flag])),
                        package='rviz2', executable='rviz2',
                        arguments=['-f', 'map',
                                   '-d', os.path.join(pkg_andino_gz, 'rviz', 'andino_gz_nav2.rviz')],
                        parameters=[{'use_sim_time': True}],
                        remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
                        output='screen',
                        additional_env={
                            'LIBGL_ALWAYS_SOFTWARE': '1',
                            'QT_XCB_GL_INTEGRATION': 'none',
                            'QT_QPA_PLATFORM': 'xcb'
                        }
                    )
                ]
            ),

            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(pkg_andino_gz, 'launch', 'include', 'gz_ros_bridge.launch.py')
                ),
                launch_arguments={'entity': robot_name}.items(),
                condition=IfCondition(ros_bridge),
            ),
        ])

        nav_group = GroupAction([
            # ---- scan remaps (single robot) ----
            SetRemap(src='/global_costmap/scan', dst='/scan',
                     condition=IfCondition(PythonExpression([one_robot, ' and ', nav2_flag]))),
            SetRemap(src='/local_costmap/scan', dst='/scan',
                     condition=IfCondition(PythonExpression([one_robot, ' and ', nav2_flag]))),

            # ---- scan remaps (multi robot) ----
            SetRemap(src=f'/{robot_name}/global_costmap/scan', dst=f'/{robot_name}/scan',
                     condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', nav2_flag]))),
            SetRemap(src=f'/{robot_name}/local_costmap/scan',  dst=f'/{robot_name}/scan',
                     condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', nav2_flag]))),

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
        ])

        spawn_robots_group += [robots_group, nav_group]

    # ----------------- Static TF: gazebo_world -> map  (طريقة A) -----------------
    # origin: [-17.2, -5.2, 0]  ==> translation = (+17.2, +5.2, 0), yaw = 0
    static_world_map_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='world_to_map_tf',
        arguments=['17.2', '5.2', '0', '0', '0', '0', 'gazebo_world', 'map'],
        output='screen',
        condition=IfCondition(nav2_flag),
    )

    # ----------------- auto-initialpose after map_server & amcl become active -----------------
    # يحسب initialpose في إطار map بناءً على إحداثيات سبون أول روبوت + (17.2, 5.2)
    # yaw_map = yaw0 (لأن yaw origin = 0)
    align_and_init = TimerAction(
        period=12.0,
        actions=[
            ExecuteProcess(
                cmd=[
                    '/bin/bash', '-c',
                    (
                        'python3 - <<EOF\n'
                        'import time, math, rclpy\n'
                        'from rclpy.node import Node\n'
                        'from geometry_msgs.msg import PoseWithCovarianceStamped\n'
                        'from lifecycle_msgs.srv import GetState\n'
                        'from std_msgs.msg import Header\n'
                        '\n'
                        f'X0 = {init_spawn_x}\n'
                        f'Y0 = {init_spawn_y}\n'
                        f'YAW0 = {init_spawn_yaw}\n'
                        'DX = 17.2\n'
                        'DY = 5.2\n'
                        '\n'
                        'def wait_active(n, name, timeout=30.0):\n'
                        '  cli = n.create_client(GetState, f"/{name}/get_state")\n'
                        '  end = time.time()+timeout\n'
                        '  while time.time()<end and rclpy.ok():\n'
                        '    if cli.wait_for_service(timeout_sec=2.0):\n'
                        '      req = GetState.Request()\n'
                        '      fut = cli.call_async(req)\n'
                        '      rclpy.spin_until_future_complete(n, fut, timeout_sec=3.0)\n'
                        '      if fut.result() and fut.result().current_state.id == 3:\n'
                        '        return True\n'
                        '    time.sleep(0.5)\n'
                        '  return False\n'
                        '\n'
                        'rclpy.init()\n'
                        'n = Node("auto_initialpose")\n'
                        'n.set_parameters([n.declare_parameter("use_sim_time", True)])\n'
                        '\n'
                        '# انتظر تفعيل map_server و amcl\n'
                        'wait_active(n, "map_server")\n'
                        'wait_active(n, "amcl")\n'
                        'time.sleep(0.5)\n'
                        '\n'
                        'x_map = X0 + DX\n'
                        'y_map = Y0 + DY\n'
                        'yaw_map = YAW0\n'
                        'qz = math.sin(yaw_map/2.0)\n'
                        'qw = math.cos(yaw_map/2.0)\n'
                        '\n'
                        'pub = n.create_publisher(PoseWithCovarianceStamped, "/initialpose", 10)\n'
                        'msg = PoseWithCovarianceStamped()\n'
                        'msg.header = Header(frame_id="map")\n'
                        'msg.pose.pose.position.x = x_map\n'
                        'msg.pose.pose.position.y = y_map\n'
                        'msg.pose.pose.orientation.z = qz\n'
                        'msg.pose.pose.orientation.w = qw\n'
                        'msg.pose.covariance[0] = 0.25\n'
                        'msg.pose.covariance[7] = 0.25\n'
                        'msg.pose.covariance[35] = 0.05\n'
                        'for _ in range(8):\n'
                        '  pub.publish(msg)\n'
                        '  rclpy.spin_once(n, timeout_sec=0.1)\n'
                        '  time.sleep(0.15)\n'
                        '\n'
                        'rclpy.shutdown()\n'
                        'EOF'
                    )
                ],
                output='screen'
            )
        ],
        condition=IfCondition(nav2_flag)
    )

    clear_costmaps = TimerAction(
        period=20.0,
        actions=[
            ExecuteProcess(cmd=['ros2', 'service', 'call', '/global_costmap/clear_entirely_global_costmap', 'std_srvs/srv/Empty', '{}'], output='screen'),
            ExecuteProcess(cmd=['ros2', 'service', 'call', '/local_costmap/clear_entirely_local_costmap', 'std_srvs/srv/Empty', '{}'], output='screen'),
        ],
        condition=IfCondition(nav2_flag)
    )

    # ----------------- assemble -----------------
    ld = LaunchDescription()
    for a in (ros_bridge_arg, rviz_arg, world_name_arg, robots_arg,
              gui_config_arg, nav2_arg, map_name_arg, params_file_arg):
        ld.add_action(a)

    ld.add_action(base_group)
    for g in spawn_robots_group:
        ld.add_action(g)

    # طريقة A: اربط world<->map وثبّت الـTF + initialpose
    ld.add_action(static_world_map_tf)
    ld.add_action(align_and_init)

    ld.add_action(clear_costmaps)

    return ld
