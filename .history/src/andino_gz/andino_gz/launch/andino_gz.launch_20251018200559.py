#!/usr/bin/env python3
import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, GroupAction, IncludeLaunchDescription,
                            LogInfo, TimerAction, ExecuteProcess)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (LaunchConfiguration, PathJoinSubstitution,
                                  PythonExpression, TextSubstitution)
from launch_ros.actions import Node, PushRosNamespace, SetRemap
from nav2_common.launch import ParseMultiRobotPose
from andino_gz.launch_tools.substitutions import TextJoin

def generate_launch_description():
    pkg_andino_gz = get_package_share_directory('andino_gz')
    pkg_nav2_bringup = get_package_share_directory('nav2_bringup')

    # -------- args --------
    ros_bridge_arg = DeclareLaunchArgument('ros_bridge', default_value='True')
    rviz_arg       = DeclareLaunchArgument('rviz',       default_value='True')
    world_name_arg = DeclareLaunchArgument('world_name', default_value='populated_office.sdf')
    robots_arg     = DeclareLaunchArgument('robots',     default_value="andino={x: 0., y: 0., z: 0.1, yaw: 0.};")
    gui_config_arg = DeclareLaunchArgument('gui_config', default_value='default.config')
    nav2_arg       = DeclareLaunchArgument('nav2',       default_value='True')
    map_name_arg   = DeclareLaunchArgument('map',        default_value='office')
    params_file_arg= DeclareLaunchArgument('params_file',
                         default_value=PathJoinSubstitution([pkg_andino_gz,'config','nav2_params.yaml']))
    tf_world_parent_arg = DeclareLaunchArgument('tf_world_parent', default_value='gazebo_world')

    # -------- cfgs --------
    rviz = LaunchConfiguration('rviz')
    ros_bridge = LaunchConfiguration('ros_bridge')
    world_name = LaunchConfiguration('world_name')
    map_name   = LaunchConfiguration('map')
    gui_config = LaunchConfiguration('gui_config')
    nav2_flag  = LaunchConfiguration('nav2')
    params_file= LaunchConfiguration('params_file')
    tf_world_parent = LaunchConfiguration('tf_world_parent')

    # -------- paths --------
    world_path = PathJoinSubstitution([pkg_andino_gz, 'worlds', world_name])
    gui_config_path = PathJoinSubstitution([pkg_andino_gz, 'config_gui', gui_config])
    map_path = PathJoinSubstitution([pkg_andino_gz, 'maps', map_name,
                                     TextJoin(substitutions=[map_name, '.yaml'])])

    # -------- Gazebo --------
    gz_args = TextJoin(
        substitutions=[ world_path,
                        TextJoin(substitutions=['--gui-config', gui_config_path], separator=' ') ],
        separator=' ')

    base_group = GroupAction(
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(get_package_share_directory('ros_gz_sim'),'launch','gz_sim.launch.py')),
                launch_arguments={'gz_args': gz_args}.items(),
            ),
            Node(  # clock bridge
                package='ros_gz_bridge', executable='parameter_bridge',
                arguments=['/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock]'],
                output='screen', namespace='andino_gz_sim',
                condition=IfCondition(ros_bridge),
            ),
        ]
    )

    # -------- Static TFs: gazebo_world -> map -> odom --------
    static_tf_world_to_map = Node(
        package='tf2_ros', executable='static_transform_publisher',
        name='tf_world_to_map',
        arguments=['0','0','0','0','0','0', tf_world_parent, 'map'],
        output='screen'
    )

    static_tf_map_to_odom = Node(
        package='tf2_ros', executable='static_transform_publisher',
        name='tf_map_to_odom',
        arguments=['0','0','0','0','0','0','map','odom'],
        output='screen'
    )

    # -------- Robots + Nav2 --------
    robots_list = ParseMultiRobotPose('robots').value()
    if robots_list == {}:
        robots_list = {"andino": {"x": 0., "y": 0., "z": 0.1, "yaw": 0.}}

    spawn_robots_group = []
    more_than_one_robot = PythonExpression([TextSubstitution(text=str(len(robots_list.keys()))), ' > 1'])
    one_robot           = PythonExpression([TextSubstitution(text=str(len(robots_list.keys()))), ' == 1'])

    # first robot for initial pose
    first_robot_name = list(robots_list.keys())[0]
    first_pose = robots_list[first_robot_name]
    initpose_x = str(first_pose['x'])
    initpose_y = str(first_pose['y'])
    initpose_yaw_deg = str(first_pose['yaw'] * 180.0/3.141592653589793 if abs(first_pose['yaw'])>3.141/360 else first_pose['yaw'])

    for robot_name, init_pose in robots_list.items():
        robots_group = GroupAction(
            actions=[
                PushRosNamespace(condition=IfCondition(more_than_one_robot), namespace=robot_name),

                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(os.path.join(pkg_andino_gz,'launch','include','spawn_robot.launch.py')),
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
                            condition=IfCondition(PythonExpression([rviz, ' and ', LaunchConfiguration('nav2')])),
                            package='rviz2', executable='rviz2',
                            arguments=['-f','map','-d', os.path.join(pkg_andino_gz,'rviz','andino_gz_nav2.rviz')],
                            parameters=[{'use_sim_time': True}],
                            remappings=[('/tf','tf'),('/tf_static','tf_static')],
                            output='screen',
                            additional_env={'LIBGL_ALWAYS_SOFTWARE':'1','QT_XCB_GL_INTEGRATION':'none','QT_QPA_PLATFORM':'xcb'}
                        )
                    ]
                ),

                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(os.path.join(pkg_andino_gz,'launch','include','gz_ros_bridge.launch.py')),
                    launch_arguments={'entity': robot_name}.items(),
                    condition=IfCondition(ros_bridge),
                ),
            ]
        )

        nav_group = GroupAction(
            actions=[
                SetRemap(src='/global_costmap/scan', dst='/scan',
                         condition=IfCondition(PythonExpression([one_robot,' and ',LaunchConfiguration('nav2')]))),
                SetRemap(src='/local_costmap/scan', dst='/scan',
                         condition=IfCondition(PythonExpression([one_robot,' and ',LaunchConfiguration('nav2')]))),

                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(os.path.join(pkg_nav2_bringup,'launch','bringup_launch.py')),
                    launch_arguments={
                        'map': map_path,
                        'autostart': 'True',
                        'use_sim_time': 'True',
                        'params_file': params_file,
                    }.items(),
                    condition=IfCondition(PythonExpression([one_robot,' and ',LaunchConfiguration('nav2')])),
                ),
            ]
        )

        spawn_robots_group += [robots_group, nav_group]

    # -------- Auto initial pose + clear costmaps --------
    auto_initial_pose = TimerAction(
        period=8.0,
        actions=[
            ExecuteProcess(
                cmd=[
                    'python3','-c',
                    (
                        'import rclpy, math; '
                        'from geometry_msgs.msg import PoseWithCovarianceStamped; '
                        'from rclpy.node import Node; '
                        'rclpy.init(); n=Node("auto_initialpose"); '
                        'p=n.create_publisher(PoseWithCovarianceStamped,"/initialpose",10); '
                        f'x=float("{initpose_x}"); y=float("{initpose_y}"); yaw_deg=float("{initpose_yaw_deg}"); '
                        'qz=math.sin(math.radians(yaw_deg)/2.0); '
                        'qw=math.cos(math.radians(yaw_deg)/2.0); '
                        'm=PoseWithCovarianceStamped(); m.header.frame_id="map"; '
                        'm.pose.pose.position.x=x; m.pose.pose.position.y=y; '
                        'm.pose.pose.orientation.z=qz; m.pose.pose.orientation.w=qw; '
                        'm.pose.covariance[0]=0.25; m.pose.covariance[7]=0.25; m.pose.covariance[35]=0.05; '
                        'p.publish(m); n.get_logger().info("✅ Auto initial pose sent"); '
                        'rclpy.shutdown();'
                    )
                ],
                output='screen'
            )
        ]
    )

    clear_costmaps = TimerAction(
        period=12.0,
        actions=[
            ExecuteProcess(cmd=['/bin/bash','-lc',
                'ros2 service call /global_costmap/clear_entirely_global_costmap std_srvs/srv/Empty "{}"'], output='screen'),
            ExecuteProcess(cmd=['/bin/bash','-lc',
                'ros2 service call /local_costmap/clear_entirely_local_costmap std_srvs/srv/Empty "{}"'],  output='screen'),
        ],
        condition=IfCondition(nav2_flag)
    )

    # -------- assemble --------
    ld = LaunchDescription()
    for a in (ros_bridge_arg, rviz_arg, world_name_arg, robots_arg, gui_config_arg,
              nav2_arg, map_name_arg, params_file_arg, tf_world_parent_arg):
        ld.add_action(a)

    ld.add_action(base_group)
    ld.add_action(static_tf_world_to_map)
    ld.add_action(static_tf_map_to_odom)
    for g in spawn_robots_group:
        ld.add_action(g)
    ld.add_action(auto_initial_pose)
    ld.add_action(clear_costmaps)
    return ld
