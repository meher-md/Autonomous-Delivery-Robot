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

    # ---------------------------
    # Launch arguments (core)
    # ---------------------------
    ros_bridge_arg = DeclareLaunchArgument(
        'ros_bridge', default_value='True', description='Run ROS bridge node.')
    rviz_arg = DeclareLaunchArgument(
        'rviz', default_value='True', description='Start RViz.')
    world_name_arg = DeclareLaunchArgument(
        'world_name', default_value='populated_office.sdf',
        description='World to load. Should match the map used by Nav2.')
    robots_arg = DeclareLaunchArgument(
        'robots',
        default_value="andino={x: 0., y: 0., z: 0.1, yaw: 0.};",
        description='Robots to spawn; entries separated by ";".')
    gui_config_arg = DeclareLaunchArgument(
        'gui_config', default_value='default.config',
        description='GUI config file for Gazebo.')
    nav2_arg = DeclareLaunchArgument(
        'nav2', default_value='False', description='Enable Nav2 bringup.')
    map_name_arg = DeclareLaunchArgument(
        'map', default_value='office',
        description='Map name (must match world).')
    params_file_arg = DeclareLaunchArgument(
        'params_file',
        default_value=PathJoinSubstitution([pkg_andino_gz, 'config', 'nav2_params.yaml']),
        description='Path to Nav2 parameter file.')

    # ---------------------------
    # Automation options
    # ---------------------------
    auto_initpose_arg = DeclareLaunchArgument(
        'auto_initialpose', default_value='True',
        description='Automatically publish /initialpose after Nav2 starts.')
    initialpose_delay_arg = DeclareLaunchArgument(
        'initialpose_delay', default_value='6.0',
        description='Seconds to wait before publishing /initialpose.')
    auto_clear_costmaps_arg = DeclareLaunchArgument(
        'auto_clear_costmaps', default_value='True',
        description='Automatically clear local/global costmaps after /initialpose.')

    # Allow overriding initial pose from CLI (instead of spawn pose)
    initpose_override_arg = DeclareLaunchArgument(
        'initpose_override', default_value='False',
        description='Override spawn pose for /initialpose.')
    initpose_x_arg = DeclareLaunchArgument(
        'initpose_x', default_value='0.0',
        description='Initial pose X (map frame).')
    initpose_y_arg = DeclareLaunchArgument(
        'initpose_y', default_value='0.0',
        description='Initial pose Y (map frame).')
    initpose_yaw_deg_arg = DeclareLaunchArgument(
        'initpose_yaw_deg', default_value='0.0',
        description='Initial yaw in degrees (map frame).')

    # ---------------------------
    # Launch configurations
    # ---------------------------
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

    # ---------------------------
    # Paths
    # ---------------------------
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

    # ---------------------------
    # Base group: Gazebo + /clock bridge
    # ---------------------------
    base_group = GroupAction(
        actions=[
            # Gazebo Sim
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')
                ),
                launch_arguments={'gz_args': gz_args}.items(),
            ),
            # ROS clock bridge
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

    # ---------------------------
    # Parse robots list (single or multi)
    # ---------------------------
    robots_list = ParseMultiRobotPose('robots').value()
    if robots_list == {}:
        robots_list = {"andino": {"x": 0., "y": 0., "z": 0.1, "yaw": 0.}}

    log_number_robots = LogInfo(msg="Robots to spawn: " + str(robots_list))
    spawn_robots_group = []

    # Helper conditions for multi-robot remaps (same style as original)
    more_than_one_robot = PythonExpression([TextSubstitution(text=str(len(robots_list.keys()))), ' > 1'])
    one_robot = PythonExpression([TextSubstitution(text=str(len(robots_list.keys()))), ' == 1'])

    # ---------------------------
    # Build per-robot groups
    # ---------------------------
    for robot_name, spawn in robots_list.items():
        # Initial pose to publish: either override from CLI or spawn pose
        init_x_expr = PythonExpression(
            [f"({initpose_override} == 'True' or {initpose_override} == 'true') ? {initpose_x} : '{spawn['x']}'"]
        )
        init_y_expr = PythonExpression(
            [f"({initpose_override} == 'True' or {initpose_override} == 'true') ? {initpose_y} : '{spawn['y']}'"]
        )
        # yaw: if override, convert from deg to rad at runtime; else use spawn['yaw'] (already rad)
        yaw_rad_expr = PythonExpression(
            [f\"( {initpose_override} == 'True' or {initpose_override} == 'true') ",
             f"? ( {initpose_yaw_deg} * 3.141592653589793 / 180.0 ) ",
             f": '{spawn['yaw']}'\"]
        )

        # Build /initialpose message as a single YAML string using PythonExpression for z,w
        qz_expr = PythonExpression([f'sin(({yaw_rad_expr})/2.0)'])
        qw_expr = PythonExpression([f'cos(({yaw_rad_expr})/2.0)'])

        initialpose_yaml = PythonExpression([
            "'{header: {frame_id: map}, pose: {pose: {position: {x: ', ",
            init_x_expr,
            "', y: ', ",
            init_y_expr,
            ", ', z: 0.0}, orientation: {z: ', ",
            qz_expr,
            ", ', w: ', ",
            qw_expr,
            ",'}}, covariance: [0.25, 0, 0, 0, 0, 0, 0, 0.25, 0, 0, 0, 0, 0, 0, 0.0685, 0, 0, 0, 0, 0, 0, 0.0685, 0, 0, 0, 0, 0, 0, 0.0685, 0, 0, 0, 0, 0, 0, 0.05]}}'"
        ])

        # -----------------------
        # Group: robot + rviz + per-robot bridge
        # -----------------------
        robots_group = GroupAction(
            actions=[
                LogInfo(msg=f"Group for robot: {robot_name}"),
                PushRosNamespace(namespace=robot_name, ),
                # Spawn robot
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
                # RViz with Nav2
                Node(
                    condition=IfCondition(PythonExpression([rviz, ' and ', LaunchConfiguration('nav2')])),
                    package='rviz2',
                    executable='rviz2',
                    arguments=['-d', os.path.join(pkg_andino_gz, 'rviz', 'andino_gz_nav2.rviz')],
                    parameters=[{'use_sim_time': True}],
                    remappings=[
                        ('/tf', 'tf'),
                        ('/tf_static', 'tf_static'),
                    ],
                ),
                # RViz without Nav2
                Node(
                    condition=IfCondition(PythonExpression([rviz, ' and not ', LaunchConfiguration('nav2')])),
                    package='rviz2',
                    executable='rviz2',
                    arguments=['-d', os.path.join(pkg_andino_gz, 'rviz', 'andino_gz.rviz')],
                    parameters=[{'use_sim_time': True}],
                    remappings=[
                        ('/tf', 'tf'),
                        ('/tf_static', 'tf_static'),
                    ],
                ),
                # per-robot gz-ros bridge
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(pkg_andino_gz, 'launch', 'include', 'gz_ros_bridge.launch.py')
                    ),
                    launch_arguments={'entity': robot_name}.items(),
                    condition=IfCondition(LaunchConfiguration('ros_bridge')),
                ),
            ]
        )

        # -----------------------
        # Group: Nav2 + auto initialpose + auto clear
        # -----------------------
        nav_group = GroupAction(
            actions=[
                # Remap scans for multi-robot (same behavior as original)
                SetRemap(
                    src='/' + robot_name + '/global_costmap/scan', dst='/' + robot_name + '/scan',
                    condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', LaunchConfiguration('nav2')]))),
                SetRemap(
                    src='/' + robot_name + '/local_costmap/scan', dst='/' + robot_name + '/scan',
                    condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', LaunchConfiguration('nav2')]))),

                # Nav2 bringup (multi-robot namespace)
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')),
                    launch_arguments={
                        'namespace': robot_name,
                        'use_namespace': 'True',
                        'map': LaunchConfiguration('map'),
                        'autostart': 'True',
                        'use_sim_time': 'True',
                        'params_file': LaunchConfiguration('params_file'),
                    }.items(),
                    condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', LaunchConfiguration('nav2')])),
                ),

                # Remaps for single-robot
                SetRemap(src='/global_costmap/scan', dst='/scan',
                         condition=IfCondition(PythonExpression([one_robot, ' and ', LaunchConfiguration('nav2')]))),
                SetRemap(src='/local_costmap/scan', dst='/scan',
                         condition=IfCondition(PythonExpression([one_robot, ' and ', LaunchConfiguration('nav2')]))),

                # Nav2 bringup (single-robot)
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')),
                    launch_arguments={
                        'map': LaunchConfiguration('map'),
                        'autostart': 'True',
                        'use_sim_time': 'True',
                        'params_file': LaunchConfiguration('params_file'),
                    }.items(),
                    condition=IfCondition(PythonExpression([one_robot, ' and ', LaunchConfiguration('nav2')])),
                ),

                # Auto initialpose: publish once on relative topic "initialpose"
                TimerAction(
                    period=initialpose_delay,
                    actions=[
                        Node(
                            condition=IfCondition(PythonExpression([auto_initialpose, ' and ', LaunchConfiguration('nav2')])),
                            package='ros2topic',
                            executable='ros2topic',
                            name=f'{robot_name}_initialpose_publisher',
                            arguments=[
                                'pub', '--once', 'initialpose', 'geometry_msgs/PoseWithCovarianceStamped',
                                initialpose_yaml
                            ],
                            output='screen'
                        )
                    ]
                ),

                # Auto clear costmaps shortly after initial pose
                TimerAction(
                    period=PythonExpression([initialpose_delay, ' + 2.0']),
                    actions=[
                        Node(
                            condition=IfCondition(PythonExpression([auto_clear_costmaps, ' and ', LaunchConfiguration('nav2')])),
                            package='ros2service',
                            executable='ros2service',
                            name=f'{robot_name}_clear_global_costmap',
                            arguments=[
                                'call', 'global_costmap/clear_entirely_global_costmap',
                                'std_srvs/srv/Empty', '{}'
                            ],
                            output='screen'
                        ),
                        Node(
                            condition=IfCondition(PythonExpression([auto_clear_costmaps, ' and ', LaunchConfiguration('nav2')])),
                            package='ros2service',
                            executable='ros2service',
                            name=f'{robot_name}_clear_local_costmap',
                            arguments=[
                                'call', 'local_costmap/clear_entirely_local_costmap',
                                'std_srvs/srv/Empty', '{}'
                            ],
                            output='screen'
                        ),
                    ]
                ),
            ]
        )

        spawn_robots_group.append(robots_group)
        spawn_robots_group.append(nav_group)

    # ---------------------------
    # Final launch description
    # ---------------------------
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
    ld.add_action(initialpose_delay_arg)
    ld.add_action(auto_clear_costmaps_arg)
    ld.add_action(initpose_override_arg)
    ld.add_action(initpose_x_arg)
    ld.add_action(initpose_y_arg)
    ld.add_action(initpose_yaw_deg_arg)
    # Logs & base
    ld.add_action(log_world_path)
    ld.add_action(log_map_path)
    ld.add_action(base_group)
    # Robots
    ld.add_action(log_number_robots)
    for group in spawn_robots_group:
        ld.add_action(group)
    return ld
