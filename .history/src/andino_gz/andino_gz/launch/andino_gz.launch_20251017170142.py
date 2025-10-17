#!/usr/bin/env python3

import os
import math
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    GroupAction,
    IncludeLaunchDescription,
    LogInfo,
    TimerAction,
    OpaqueFunction,
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
)
from launch_ros.actions import Node, PushRosNamespace
from nav2_common.launch import ParseMultiRobotPose
from andino_gz.launch_tools.substitutions import TextJoin


def generate_launch_description():
    pkg_andino_gz = get_package_share_directory('andino_gz')
    pkg_nav2_bringup = get_package_share_directory('nav2_bringup')

    # Core launch args
    ros_bridge_arg = DeclareLaunchArgument('ros_bridge', default_value='True', description='Run ROS bridge node.')
    rviz_arg = DeclareLaunchArgument('rviz', default_value='True', description='Start RViz.')
    world_name_arg = DeclareLaunchArgument('world_name', default_value='populated_office.sdf', description='World to load.')
    robots_arg = DeclareLaunchArgument(
        'robots',
        default_value="andino={x: 0., y: 0., z: 0.1, yaw: 0.};",
        description='Robots to spawn; separate multiple entries by ";"',
    )
    gui_config_arg = DeclareLaunchArgument('gui_config', default_value='default.config', description='GUI config file.')
    nav2_arg = DeclareLaunchArgument('nav2', default_value='False', description='Enable Nav2 bringup.')
    map_name_arg = DeclareLaunchArgument('map', default_value='office', description='Map name (should match world).')
    params_file_arg = DeclareLaunchArgument(
        'params_file',
        default_value=PathJoinSubstitution([pkg_andino_gz, 'config', 'nav2_params.yaml']),
        description='Path to Nav2 parameter file.',
    )

    # Automation options
    auto_initpose_arg = DeclareLaunchArgument('auto_initialpose', default_value='True', description='Auto publish /initialpose.')
    initpose_delay_arg = DeclareLaunchArgument('initialpose_delay', default_value='6.0', description='Delay before publishing /initialpose (seconds).')
    auto_clear_costmaps_arg = DeclareLaunchArgument('auto_clear_costmaps', default_value='True', description='Auto clear costmaps after /initialpose.')

    # NEW: initial pose override from command line
    initpose_override_arg = DeclareLaunchArgument('initpose_override', default_value='False', description='Override spawn pose for /initialpose.')
    initpose_x_arg = DeclareLaunchArgument('initpose_x', default_value='0.0', description='Initial pose X (map frame).')
    initpose_y_arg = DeclareLaunchArgument('initpose_y', default_value='0.0', description='Initial pose Y (map frame).')
    initpose_yaw_deg_arg = DeclareLaunchArgument('initpose_yaw_deg', default_value='0.0', description='Initial yaw in degrees (map frame).')

    # LaunchConfigurations
    rviz = LaunchConfiguration('rviz')
    ros_bridge = LaunchConfiguration('ros_bridge')
    world_name = LaunchConfiguration('world_name')
    map_name = LaunchConfiguration('map')
    gui_config = LaunchConfiguration('gui_config')
    nav2_flag = LaunchConfiguration('nav2')
    params_file = LaunchConfiguration('params_file')

    auto_initialpose = LaunchConfiguration('auto_initialpose')
    initialpose_delay = LaunchConfiguration('initialpose_delay')
    auto_clear_costmaps = LaunchConfiguration('auto_clear_costmaps')

    initpose_override = LaunchConfiguration('initpose_override')
    initpose_x = LaunchConfiguration('initpose_x')
    initpose_y = LaunchConfiguration('initpose_y')
    initpose_yaw_deg = LaunchConfiguration('initpose_yaw_deg')

    # Paths
    world_path = PathJoinSubstitution([pkg_andino_gz, 'worlds', world_name])
    map_path = PathJoinSubstitution([pkg_andino_gz, 'maps', map_name, TextJoin(substitutions=[map_name, '.yaml'])])
    gui_config_path = PathJoinSubstitution([pkg_andino_gz, 'config_gui', gui_config])

    log_world_path = LogInfo(msg=TextJoin(substitutions=["World path: ", world_path]))
    log_map_path = LogInfo(msg=TextJoin(substitutions=["Map path: ", map_path]))

    gz_args = TextJoin(
        substitutions=[
            world_path,
            TextJoin(substitutions=["--gui-config", gui_config_path], separator=' '),
        ],
        separator=' ',
    )

    # Base group: Gazebo + /clock bridge
    base_group = GroupAction(
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
                arguments=['/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock'],
                output='screen',
                namespace='andino_gz_sim',
                condition=IfCondition(ros_bridge),
            ),
        ]
    )

    # Build robots + nav2 dynamically (need to read LaunchConfigurations)
    def _build_groups(context):
        actions = []

        # Resolve substitutions at runtime
        nav2_on = nav2_flag.perform(context).lower() in ('1', 'true', 'yes')
        auto_init_on = auto_initialpose.perform(context).lower() in ('1', 'true', 'yes')
        auto_clear_on = auto_clear_costmaps.perform(context).lower() in ('1', 'true', 'yes')
        init_override = initpose_override.perform(context).lower() in ('1', 'true', 'yes')
        delay_s = float(initialpose_delay.perform(context))
        override_x = float(initpose_x.perform(context))
        override_y = float(initpose_y.perform(context))
        override_yaw_deg = float(initpose_yaw_deg.perform(context))

        # Parse robots list
        robots_list = ParseMultiRobotPose('robots').value()
        if robots_list == {}:
            robots_list = {"andino": {"x": 0., "y": 0., "z": 0.1, "yaw": 0.}}

        actions.append(LogInfo(msg=f"Robots to spawn: {robots_list}"))

        for robot_name, spawn in robots_list.items():
            # Decide initial pose to publish:
            if init_override:
                x = override_x
                y = override_y
                yaw_rad = math.radians(override_yaw_deg)
            else:
                x = float(spawn['x'])
                y = float(spawn['y'])
                yaw_rad = float(spawn['yaw'])

            qz = math.sin(yaw_rad / 2.0)
            qw = math.cos(yaw_rad / 2.0)

            initialpose_yaml = (
                f"{{header: {{frame_id: map}}, "
                f"pose: {{pose: {{position: {{x: {x}, y: {y}, z: 0.0}}, "
                f"orientation: {{z: {qz}, w: {qw}}}}}, "
                "covariance: [0.25, 0, 0, 0, 0, 0, "
                "0, 0.25, 0, 0, 0, 0, "
                "0, 0, 0.0685, 0, 0, 0, "
                "0, 0, 0, 0.0685, 0, 0, "
                "0, 0, 0, 0, 0.0685, 0, "
                "0, 0, 0, 0, 0, 0.05]}}"
            )

            # Per-robot group: namespace + spawn + RViz + bridge
            robots_group = GroupAction(
                actions=[
                    LogInfo(msg=f"Spawning robot: {robot_name}"),
                    PushRosNamespace(namespace=robot_name),
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
                            'use_sim_time': 'true',
                        }.items(),
                    ),
                    # RViz (Nav2 or basic)
                    Node(
                        condition=IfCondition(str(nav2_on)),
                        package='rviz2',
                        executable='rviz2',
                        arguments=['-d', os.path.join(pkg_andino_gz, 'rviz', 'andino_gz_nav2.rviz')],
                        parameters=[{'use_sim_time': True}],
                    ),
                    Node(
                        condition=IfCondition(str(not nav2_on)),
                        package='rviz2',
                        executable='rviz2',
                        arguments=['-d', os.path.join(pkg_andino_gz, 'rviz', 'andino_gz.rviz')],
                        parameters=[{'use_sim_time': True}],
                    ),
                    # ros_gz bridge per robot
                    IncludeLaunchDescription(
                        PythonLaunchDescriptionSource(
                            os.path.join(pkg_andino_gz, 'launch', 'include', 'gz_ros_bridge.launch.py')
                        ),
                        launch_arguments={'entity': robot_name}.items(),
                        condition=IfCondition(LaunchConfiguration('ros_bridge')),
                    ),
                ]
            )

            # Nav2 group + automation
            nav_actions = [
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')),
                    launch_arguments={
                        'map': map_path,
                        'autostart': 'True',
                        'use_sim_time': 'True',
                        'params_file': LaunchConfiguration('params_file'),
                        # For single-robot we don't pass namespace; for multi-robot user can run multiple.
                    }.items(),
                    condition=IfCondition(LaunchConfiguration('nav2')),
                ),
            ]

            # Auto publish initial pose
            nav_actions.append(
                TimerAction(
                    period=delay_s,
                    actions=[
                        Node(
                            condition=IfCondition(str(nav2_on and auto_init_on)),
                            package='ros2topic',
                            executable='ros2topic',
                            name=f'{robot_name}_initialpose_publisher',
                            # Relative topic "initialpose" so it works with namespace
                            arguments=[
                                'pub', '--once', 'initialpose', 'geometry_msgs/PoseWithCovarianceStamped',
                                initialpose_yaml
                            ],
                            output='screen'
                        )
                    ]
                )
            )

            # Optional: clear costmaps after initial pose
            nav_actions.append(
                TimerAction(
                    period=delay_s + 2.0,
                    actions=[
                        Node(
                            condition=IfCondition(str(nav2_on and auto_clear_on)),
                            package='ros2service',
                            executable='ros2service',
                            name=f'{robot_name}_clear_global_costmap',
                            arguments=['call', 'global_costmap/clear_entirely_global_costmap', 'std_srvs/srv/Empty', '{}'],
                            output='screen'
                        ),
                        Node(
                            condition=IfCondition(str(nav2_on and auto_clear_on)),
                            package='ros2service',
                            executable='ros2service',
                            name=f'{robot_name}_clear_local_costmap',
                            arguments=['call', 'local_costmap/clear_entirely_local_costmap', 'std_srvs/srv/Empty', '{}'],
                            output='screen'
                        ),
                    ]
                )
            )

            nav_group = GroupAction(actions=nav_actions)

            actions.append(robots_group)
            actions.append(nav_group)

        return actions

    # Build final launch description
    ld = LaunchDescription()
    # Declare args
    ld.add_action(ros_bridge_arg)
    ld.add_action(rviz_arg)
    ld.add_action(world_name_arg)
    ld.add_action(robots_arg)
    ld.add_action(gui_config_arg)
    ld.add_action(nav2_arg)
    ld.add_action(map_name_arg)
    ld.add_action(params_file_arg)
    ld.add_action(auto_initpose_arg)
    ld.add_action(initpose_delay_arg)
    ld.add_action(auto_clear_costmaps_arg)
    ld.add_action(initpose_override_arg)
    ld.add_action(initpose_x_arg)
    ld.add_action(initpose_y_arg)
    ld.add_action(initpose_yaw_deg_arg)

    # Logs and base bringup
    ld.add_action(LogInfo(msg=TextJoin(substitutions=["World path: ", world_path])))
    ld.add_action(LogInfo(msg=TextJoin(substitutions=["Map path: ", map_path])))
    ld.add_action(base_group)

    # Build robot + nav2 actions with evaluated configs
    ld.add_action(OpaqueFunction(function=_build_groups))

    return ld
