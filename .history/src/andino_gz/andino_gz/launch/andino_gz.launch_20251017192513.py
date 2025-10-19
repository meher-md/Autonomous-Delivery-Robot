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

    # ---------------- Launch Args ----------------
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

    # Initial pose arguments (map frame)
    initpose_x_arg = DeclareLaunchArgument(
        'initpose_x', default_value='0.0', description='Initial pose X in map frame.'
    )
    initpose_y_arg = DeclareLaunchArgument(
        'initpose_y', default_value='0.0', description='Initial pose Y in map frame.'
    )
    initpose_yaw_deg_arg = DeclareLaunchArgument(
        'initpose_yaw_deg', default_value='0.0', description='Initial yaw (degrees) in map frame.'
    )

    # ---------------- Launch Configs ----------------
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

    # ---------------- Paths ----------------
    world_path = PathJoinSubstitution([pkg_andino_gz, 'worlds', world_name])
    gui_config_path = PathJoinSubstitution([pkg_andino_gz, 'config_gui', gui_config])
    map_path = PathJoinSubstitution([pkg_andino_gz, 'maps', map_name, TextJoin(substitutions=[map_name, '.yaml'])])

    log_world_path = LogInfo(msg=TextJoin(substitutions=["World path: ", world_path]))
    log_map_path = LogInfo(msg=TextJoin(substitutions=["Map path: ", map_path]))

    # ---------------- Gazebo ----------------
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
            # Gazebo Sim
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')
                ),
                launch_arguments={'gz_args': gz_args}.items(),
            ),
            # ROS Bridge for /clock
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

    # ---------------- Static TF (connect world->odom tree) ----------------
    # NOTE: الاتجاه الصحيح parent -> child
    static_tf_gz = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='tf_gazebo_world_to_odom',
        arguments=['0', '0', '0', '0', '0', '0', 'gazebo_world', 'odom'],
        output='screen'
    )

    static_tf_world = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='tf_world_to_odom',
        arguments=['0', '0', '0', '0', '0', '0', 'world', 'odom'],
        output='screen'
    )

    # ---------------- Robots + Nav2 ----------------
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

                # Spawn the robot
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

                # RViz with Nav2 (delayed + software rendering لتفادي كراش GL)
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

                # RViz بدون Nav2 (برضه software rendering)
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

                # Per-robot Gazebo<->ROS bridges
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
                # Remap scan topics (single robot case)
                SetRemap(src='/global_costmap/scan', dst='/scan', condition=IfCondition(PythonExpression([one_robot, ' and ', LaunchConfiguration('nav2')]))),
                SetRemap(src='/local_costmap/scan', dst='/scan', condition=IfCondition(PythonExpression([one_robot, ' and ', LaunchConfiguration('nav2')]))),

                # Remap for multi-robot (namespaced)
                SetRemap(src='/' + robot_name + '/global_costmap/scan', dst='/' + robot_name + '/scan', condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', LaunchConfiguration('nav2')]))),
                SetRemap(src='/' + robot_name + '/local_costmap/scan', dst='/' + robot_name + '/scan', condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', LaunchConfiguration('nav2')]))),

                # Nav2 bringup (single robot)
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

                # Nav2 bringup (multi-robot)
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
            ]
        )

        spawn_robots_group.append(robots_group)
        spawn_robots_group.append(nav_group)

    # ---------------- Auto initial pose (wait AMCL ACTIVE) ----------------
    auto_initial_pose = TimerAction(
        period=10.0,  # wait until Nav2 + TF likely ready
        actions=[
            ExecuteProcess(
                cmd=[
                    'python3', '-c',
                    (
                        'import rclpy, math, sys, time; '
                        'from geometry_msgs.msg import PoseWithCovarianceStamped; '
                        'from lifecycle_msgs.srv import GetState; '
                        'rclpy.init(); '
                        'node=rclpy.create_node("auto_initialpose_wait_amcl"); '
                        'cli=node.create_client(GetState, "/amcl/get_state"); '
                        'while not cli.wait_for_service(timeout_sec=1.0): '
                        '  node.get_logger().info("Waiting for /amcl to come up..."); '
                        'req=GetState.Request(); '
                        'state_id=-1; '
                        'while state_id!=3: '  # 3 = ACTIVE
                        '  future=cli.call_async(req); '
                        '  rclpy.spin_until_future_complete(node, future); '
                        '  if future.result() is None: time.sleep(0.5); continue; '
                        '  state_id=future.result().current_state.id; '
                        '  if state_id!=3: time.sleep(0.5); '
                        'node.get_logger().info("AMCL is ACTIVE. Publishing initial pose..."); '
                        'pub=node.create_publisher(PoseWithCovarianceStamped, "/initialpose", 10); '
                        'x=float(sys.argv[1]); y=float(sys.argv[2]); yaw_deg=float(sys.argv[3]); '
                        'qz=math.sin(math.radians(yaw_deg)/2.0); '
                        'qw=math.cos(math.radians(yaw_deg)/2.0); '
                        'msg=PoseWithCovarianceStamped(); '
                        'msg.header.frame_id="map"; '
                        'msg.pose.pose.position.x=x; msg.pose.pose.position.y=y; '
                        'msg.pose.pose.orientation.z=qz; msg.pose.pose.orientation.w=qw; '
                        'msg.pose.covariance[0]=0.25; msg.pose.covariance[7]=0.25; msg.pose.covariance[35]=0.05; '
                        'for i in range(10): '
                        '  pub.publish(msg); '
                        '  node.get_logger().info(f"Initial pose #{i+1}/10"); '
                        '  time.sleep(0.2); '
                        'node.get_logger().info("Done publishing initial pose."); '
                        'rclpy.shutdown()'
                    ),
                    initpose_x, initpose_y, initpose_yaw_deg
                ],
                output='screen'
            )
        ]
    )

    # ---------------- Clear costmaps (wait for services) ----------------
    clear_costmaps = TimerAction(
        period=13.0,  # بعد نشر الـ pose
        actions=[
            ExecuteProcess(
                cmd=[
                    'python3','-c',
                    (
                        'import rclpy,time; from rclpy.node import Node; '
                        'from std_srvs.srv import Empty; '
                        'rclpy.init(); n=Node("clear_costmaps_once"); '
                        'def call(name): '
                        '  cli=n.create_client(Empty,name); '
                        '  while not cli.wait_for_service(timeout_sec=1.0): '
                        '    n.get_logger().info(f"Waiting for {name}..."); '
                        '  req=Empty.Request(); fut=cli.call_async(req); '
                        '  rclpy.spin_until_future_complete(n,fut); '
                        '  n.get_logger().info(f"Called {name}"); '
                        'call("/global_costmap/clear_entirely_global_costmap"); '
                        'call("/local_costmap/clear_entirely_local_costmap"); '
                        'rclpy.shutdown();'
                    )
                ],
                output='screen'
            )
        ]
    )

    # ---------------- Launch Description ----------------
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

    # Static TF fix (parent -> child)
    ld.add_action(static_tf_gz)
    ld.add_action(static_tf_world)

    # Robots + Nav2
    for group in spawn_robots_group:
        ld.add_action(group)

    # Automation
    ld.add_action(auto_initial_pose)
    ld.add_action(clear_costmaps)

    return ld
