#!/usr/bin/env python3

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription, LogInfo, TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, PythonExpression, TextSubstitution
from launch_ros.actions import Node, PushRosNamespace, SetRemap

from nav2_common.launch import ParseMultiRobotPose
from andino_gz.launch_tools.substitutions import TextJoin


def generate_launch_description():
    pkg_andino_gz = get_package_share_directory('andino_gz')
    pkg_nav2_bringup = get_package_share_directory('nav2_bringup')

    # =========================
    # Core Launch Arguments
    # =========================
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
    nav2_arg = DeclareLaunchArgument(
        'nav2', default_value='False', description='Enable Nav2 Bringup.'
    )
    map_name_arg = DeclareLaunchArgument(
        'map', default_value="office",
        description='Name of the map to load. It should match the world_name.'
    )
    params_file_arg = DeclareLaunchArgument(
        'params_file',
        default_value=PathJoinSubstitution([pkg_andino_gz, 'config', 'nav2_params.yaml']),
        description='Nav2 configuration. Full path to the ROS2 parameters file to use for all launched nodes'
    )

    # =========================
    # Nav fixes / automation args
    # =========================
    world_frame_arg = DeclareLaunchArgument(
        'world_frame', default_value='gazebo_world',
        description='Gazebo world frame (gazebo_world or world). Used to publish static TF odom->world_frame.'
    )
    auto_initialpose_arg = DeclareLaunchArgument(
        'auto_initialpose', default_value='True',
        description='Auto-publish /initialpose after Nav2 starts.'
    )
    initialpose_delay_arg = DeclareLaunchArgument(
        'initialpose_delay', default_value='6.0',
        description='Seconds to wait before publishing /initialpose.'
    )
    auto_clear_costmaps_arg = DeclareLaunchArgument(
        'auto_clear_costmaps', default_value='True',
        description='Auto clear costmaps after initial pose.'
    )
    initpose_x_arg = DeclareLaunchArgument('initpose_x', default_value='0.0', description='Initial pose X (map frame)')
    initpose_y_arg = DeclareLaunchArgument('initpose_y', default_value='0.0', description='Initial pose Y (map frame)')
    initpose_yaw_deg_arg = DeclareLaunchArgument('initpose_yaw_deg', default_value='0.0', description='Initial yaw in degrees (map frame)')

    # =========================
    # LaunchConfigurations
    # =========================
    rviz = LaunchConfiguration('rviz')
    ros_bridge = LaunchConfiguration('ros_bridge')
    world_name = LaunchConfiguration('world_name')
    map_name = LaunchConfiguration('map')
    gui_config = LaunchConfiguration('gui_config')
    gui_config_path = PathJoinSubstitution([pkg_andino_gz, 'config_gui', gui_config])
    nav2_flag = LaunchConfiguration('nav2')
    params_file = LaunchConfiguration('params_file')

    world_frame = LaunchConfiguration('world_frame')
    auto_initialpose = LaunchConfiguration('auto_initialpose')
    initialpose_delay = LaunchConfiguration('initialpose_delay')
    auto_clear_costmaps = LaunchConfiguration('auto_clear_costmaps')
    initpose_x = LaunchConfiguration('initpose_x')
    initpose_y = LaunchConfiguration('initpose_y')
    initpose_yaw_deg = LaunchConfiguration('initpose_yaw_deg')

    # =========================
    # Paths & logs
    # =========================
    world_path = PathJoinSubstitution([pkg_andino_gz, 'worlds', world_name])
    log_world_path = LogInfo(msg=TextJoin(substitutions=["World path: ", world_path]))
    map_path = PathJoinSubstitution([pkg_andino_gz, 'maps', map_name, TextJoin(substitutions=[map_name, '.yaml'])])
    log_map_path = LogInfo(msg=TextJoin(substitutions=["Map path: ", map_path]))

    # Gazebo arguments
    gz_args = TextJoin(
        substitutions=[
            world_path,
            TextJoin(substitutions=["--gui-config", gui_config_path], separator=' '),
        ],
        separator=' ',
    )

    # =========================
    # Base group: Gazebo + /clock bridge
    # =========================
    base_group = GroupAction(
        scoped=True, forwarding=False,
        launch_configurations={
            'ros_bridge': ros_bridge,
            'world_name': world_name,
            'gui_config': gui_config,
        },
        actions=[
            # Gazebo Sim
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')
                ),
                launch_arguments={'gz_args': gz_args}.items(),
            ),
            # ROS Bridge for generic Gazebo stuff
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

    # =========================
    # Static TF: odom -> world_frame
    # (complete the chain map->odom->base_link when Gazebo publishes world->base_link)
    # =========================
    static_tf_node = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='odom_world_tf',
        arguments=['0', '0', '0', '0', '0', '0', 'odom', world_frame],
        output='screen'
    )

    # =========================
    # Robots handling
    # =========================
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
                    namespace=robot_name),

                # Spawn the robot and the Robot State Publisher node.
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

                # RViz with nav2
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
                # RViz without nav2
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

                # Run ros_gz bridge
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(pkg_andino_gz, 'launch', 'include', 'gz_ros_bridge.launch.py')
                    ),
                    launch_arguments={
                        'entity': robot_name,
                    }.items(),
                    condition=IfCondition(LaunchConfiguration('ros_bridge')),
                ),
            ]
        )

        # Nav2 Bringup (supports single/multi with remaps)
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
                # Remapping scan topics for Nav2 when multiple robots
                SetRemap(src='/' + robot_name + '/global_costmap/scan', dst='/' + robot_name + '/scan',
                         condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', LaunchConfiguration('nav2')]))),
                SetRemap(src='/' + robot_name + '/local_costmap/scan', dst='/' + robot_name + '/scan',
                         condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', LaunchConfiguration('nav2')]))),

                # Nav2 Bringup for multiple robots
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
                    condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', LaunchConfiguration('nav2')])),
                ),

                # Remaps for single robot
                SetRemap(src='/global_costmap/scan', dst='/scan',
                         condition=IfCondition(PythonExpression([one_robot, ' and ', LaunchConfiguration('nav2')]))),
                SetRemap(src='/local_costmap/scan', dst='/scan',
                         condition=IfCondition(PythonExpression([one_robot, ' and ', LaunchConfiguration('nav2')]))),

                # Nav2 Bringup for single robot
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
            ]
        )

        spawn_robots_group.append(robots_group)
        spawn_robots_group.append(nav_group)

    # =========================
    # Auto initial pose publishing (single-robot common case)
    # Uses ros2topic to avoid rclpy libexec issues.
    # =========================
    auto_initial_pose = TimerAction(
        period=PythonExpression([initialpose_delay]),
        actions=[
            Node(
                condition=IfCondition(PythonExpression([nav2_flag, ' and ', auto_initialpose])),
                package='ros2topic',
                executable='ros2topic',
                name='auto_initial_pose_pub',
                output='screen',
                arguments=[
                    'pub', '--once', '/initialpose', 'geometry_msgs/PoseWithCovarianceStamped',
                    PythonExpression([
                        "'{header: {frame_id: map}, pose: {pose: {position: {x: ', ", initpose_x, ", ' , y: ', ",
                        initpose_y, ", ' , z: 0.0}, orientation: {z: ', ",
                        "str(__import__(\"math\").sin(((", initpose_yaw_deg, ")*__import__(\"math\").pi/180.0)/2.0))",
                        ", ' , w: ', ",
                        "str(__import__(\"math\").cos(((", initpose_yaw_deg, ")*__import__(\"math\").pi/180.0)/2.0))",
                        ", '}}, covariance: [0.25,0,0,0,0,0, 0,0.25,0,0,0,0, 0,0,0.0685,0,0,0, 0,0,0,0.0685,0,0, 0,0,0,0,0.0685,0, 0,0,0,0,0,0.05]}}'"
                    ])
                ]
            )
        ]
    )

    # =========================
    # Auto clear costmaps after initial pose
    # =========================
    clear_costmaps = TimerAction(
        period=PythonExpression([initialpose_delay, ' + 2.0']),
        actions=[
            Node(
                condition=IfCondition(PythonExpression([nav2_flag, ' and ', auto_clear_costmaps])),
                package='ros2service',
                executable='ros2service',
                name='clear_global_costmap',
                arguments=['call', '/global_costmap/clear_entirely_global_costmap', 'std_srvs/srv/Empty', '{}'],
                output='screen'
            ),
            Node(
                condition=IfCondition(PythonExpression([nav2_flag, ' and ', auto_clear_costmaps])),
                package='ros2service',
                executable='ros2service',
                name='clear_local_costmap',
                arguments=['call', '/local_costmap/clear_entirely_local_costmap', 'std_srvs/srv/Empty', '{}'],
                output='screen'
            ),
        ]
    )

    # =========================
    # Assemble LaunchDescription
    # =========================
    ld = LaunchDescription()

    # Core args
    ld.add_action(ros_bridge_arg)
    ld.add_action(rviz_arg)
    ld.add_action(world_name_arg)
    ld.add_action(robots_arg)
    ld.add_action(gui_config_arg)
    ld.add_action(nav2_arg)
    ld.add_action(map_name_arg)
    ld.add_action(params_file_arg)

    # Nav fixes args
    ld.add_action(world_frame_arg)
    ld.add_action(auto_initialpose_arg)
    ld.add_action(initialpose_delay_arg)
    ld.add_action(auto_clear_costmaps_arg)
    ld.add_action(initpose_x_arg)
    ld.add_action(initpose_y_arg)
    ld.add_action(initpose_yaw_deg_arg)

    # Logs + base + static TF
    ld.add_action(log_world_path)
    ld.add_action(log_map_path)
    ld.add_action(base_group)
    ld.add_action(static_tf_node)

    # Robots + nav2 groups
    ld.add_action(log_robots_by_user)
    ld.add_action(log_number_robots)
    for group in spawn_robots_group:
        ld.add_action(group)

    # Automation: initial pose + clear costmaps
    ld.add_action(auto_initial_pose)
    ld.add_action(clear_costmaps)

    return ld
