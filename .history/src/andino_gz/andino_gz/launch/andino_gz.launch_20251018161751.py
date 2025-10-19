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
        description='Robots to spawn, multiple robots can be stated separated by a ; '
    )
    gui_config_arg = DeclareLaunchArgument(
        'gui_config', default_value='default.config',
        description='Name of the gui configuration file to load.'
    )
    nav2_arg = DeclareLaunchArgument('nav2', default_value='True', description='Enable Nav2 Bringup.')
    map_name_arg = DeclareLaunchArgument(
        'map', default_value="office",
        description='Name of the map to load. It should match the world_name.'
    )
    params_file_arg = DeclareLaunchArgument(
        'params_file',
        default_value=PathJoinSubstitution([pkg_andino_gz, 'config', 'nav2_params.yaml']),
        description='Nav2 configuration file for all launched nodes.'
    )

    initpose_x_arg = DeclareLaunchArgument(
        'initpose_x', default_value='0.0', description='Initial pose X in map frame.'
    )
    initpose_y_arg = DeclareLaunchArgument(
        'initpose_y', default_value='0.0', description='Initial pose Y in map frame.'
    )
    initpose_yaw_deg_arg = DeclareLaunchArgument(
        'initpose_yaw_deg', default_value='0.0', description='Initial yaw (degrees) in map frame.'
    )

    rviz = LaunchConfiguration('rviz')
    ros_bridge = LaunchConfiguration('ros_bridge')
    world_name = LaunchConfiguration('world_name')
    map_name = LaunchConfiguration('map')
    gui_config = LaunchConfiguration('gui_config')
    nav2_flag = LaunchConfiguration('nav2')
    params_file = LaunchConfiguration('params_file')

    initpose_x = LaunchConfiguration('initpose_x')
    initpose_y = LaunchConfiguration('initpose_y')
    initpose_yaw_deg = LaunchConfiguration('initpose_yaw_deg')

    world_path = PathJoinSubstitution([pkg_andino_gz, 'worlds', world_name])
    gui_config_path = PathJoinSubstitution([pkg_andino_gz, 'config_gui', gui_config])
    map_path = PathJoinSubstitution([pkg_andino_gz, 'maps', map_name, TextJoin(substitutions=[map_name, '.yaml'])])

    log_world_path = LogInfo(msg=TextJoin(substitutions=["World path: ", world_path]))
    log_map_path = LogInfo(msg=TextJoin(substitutions=["Map path: ", map_path]))

    gz_args = TextJoin(
        substitutions=[
            world_path,
            TextJoin(substitutions=["--gui-config", gui_config_path], separator=' '),
        ],
        separator=' ',
    )

    base_group = GroupAction(
        scoped=True, forwarding=False,
        launch_configurations={
            'ros_bridge': ros_bridge,
            'world_name': world_name,
            'gui_config': gui_config,
        },
        actions=[
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')
                ),
                launch_arguments={'gz_args': gz_args}.items(),
            ),
            Node(
                package='ros_gz_bridge',
                executable='parameter_bridge',
                arguments=['/clock@rosgraph_msgs/msg/Clock@gz.msgs.Clock'],
                output='screen',
                namespace='andino_gz_sim',
                condition=IfCondition(ros_bridge),
            ),
        ]
    )

    static_tf_gz_to_world = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='tf_gazebo_world_to_world',
        arguments=['0', '0', '0', '0', '0', '0', 'gazebo_world', 'world'],
        output='screen'
    )

    static_tf_world_to_map = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='tf_world_to_map',
        arguments=['0', '0', '0', '0', '0', '0', 'world', 'map'],
        output='screen'
    )

    robots_list = ParseMultiRobotPose('robots').value()
    log_robots_by_user = LogInfo(msg="Robots provided by user.")
    if (robots_list == {}):
        log_robots_by_user = LogInfo(msg="No robots provided, using default:")
        robots_list = {"andino": {"x": 0., "y": 0., "z": 0.1, "yaw": 0.}}
    log_number_robots = LogInfo(msg="Robots to spawn: " + str(robots_list))

    spawn_robots_group = []
    more_than_one_robot = PythonExpression([TextSubstitution(text=str(len(robots_list.keys()))), ' > 1'])
    one_robot = PythonExpression([TextSubstitution(text=str(len(robots_list.keys()))), ' == 1'])

    for robot_name in robots_list:
        init_pose = robots_list[robot_name]

        robots_group = GroupAction(
            scoped=True, forwarding=False,
            launch_configurations={
                'rviz': rviz,
                'ros_bridge': ros_bridge,
                'nav2': nav2_flag,
            },
            actions=[
                LogInfo(msg="Group for robot: " + robot_name),

                PushRosNamespace(
                    condition=IfCondition(more_than_one_robot),
                    namespace=robot_name
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
                            condition=IfCondition(PythonExpression([rviz, ' and ', LaunchConfiguration('nav2')])),
                            package='rviz2',
                            executable='rviz2',
                            arguments=['-d', os.path.join(pkg_andino_gz, 'rviz', 'andino_gz_nav2.rviz')],
                            parameters=[{'use_sim_time': True}],
                            remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
                            output='screen',
                            additional_env={
                                'LIBGL_ALWAYS_SOFTWARE': '1',
                                'QT_QPA_PLATFORM': 'xcb'
                            }
                        )
                    ]
                ),

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
                            additional_env={
                                'LIBGL_ALWAYS_SOFTWARE': '1',
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
            ]
        )

        nav_group = GroupAction(
            scoped=True, forwarding=False,
            launch_configurations={
                'rviz': rviz,
                'ros_bridge': ros_bridge,
                'map': map_path,
                'params_file': params_file,
                'nav2': nav2_flag,
            },
            actions=[
                SetRemap(src='/global_costmap/scan', dst='/scan', condition=IfCondition(PythonExpression([one_robot, ' and ', LaunchConfiguration('nav2')]))),
                SetRemap(src='/local_costmap/scan', dst='/scan', condition=IfCondition(PythonExpression([one_robot, ' and ', LaunchConfiguration('nav2')]))),

                SetRemap(src='/' + robot_name + '/global_costmap/scan', dst='/' + robot_name + '/scan', condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', LaunchConfiguration('nav2')]))),
                SetRemap(src='/' + robot_name + '/local_costmap/scan', dst='/' + robot_name + '/scan', condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', LaunchConfiguration('nav2')]))),

                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')
                    ),
                    launch_arguments={
                        'map': map_path,
                        'autostart': 'True',
                        'use_sim_time': 'True',
                        'params_file': LaunchConfiguration('params_file'),
                    }.items(),
                    condition=IfCondition(PythonExpression([one_robot, ' and ', LaunchConfiguration('nav2')])),
                ),

                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')
                    ),
                    launch_arguments={
                        'namespace': robot_name,
                        'use_namespace': 'True',
                        'map': map_path,
                        'autostart': 'True',
                        'use_sim_time': 'True',
                        'params_file': LaunchConfiguration('params_file'),
                    }.items(),
                    condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', LaunchConfiguration('nav2')])),
                ),
            ]
        )

        spawn_robots_group.append(robots_group)
        spawn_robots_group.append(nav_group)

    auto_initial_pose = TimerAction(
        period=20.0,
        actions=[
            ExecuteProcess(
                cmd=[
                    'python3', '-c',
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

    clear_costmaps = TimerAction(
        period=22.0,
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

    ld = LaunchDescription()
    ld.add_action(log_robots_by_user)
    ld.add_action(log_number_robots)

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

    ld.add_action(log_world_path)
    ld.add_action(log_map_path)
    ld.add_action(base_group)

    ld.add_action(static_tf_gz_to_world)
    ld.add_action(static_tf_world_to_map)

    for group in spawn_robots_group:
        ld.add_action(group)

    ld.add_action(auto_initial_pose)
    ld.add_action(clear_costmaps)

    return ld
