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
from launch_ros.actions import Node, PushRosNamespace, SetRemap

from nav2_common.launch import ParseMultiRobotPose
# util موجودة في الباكدج بتاعك
from andino_gz.launch_tools.substitutions import TextJoin


def generate_launch_description():
    pkg_andino_gz     = get_package_share_directory('andino_gz')
    pkg_nav2_bringup  = get_package_share_directory('nav2_bringup')
    pkg_ros_gz_sim    = get_package_share_directory('ros_gz_sim')

    # ---------------- Launch Args ----------------
    ros_bridge_arg = DeclareLaunchArgument(
        'ros_bridge', default_value='True', description='Run ROS-GZ bridge node.'
    )
    rviz_arg = DeclareLaunchArgument('rviz', default_value='True', description='Start RViz.')

    # IMPORTANT: world-name لازم يتوافق مع الخريطة
    world_name_arg = DeclareLaunchArgument(
        'world_name', default_value='office.sdf',
        description='World file to load (should match the map).'
    )

    robots_arg = DeclareLaunchArgument(
        'robots', default_value="andino={x: 0., y: 0., z: 0.1, yaw: 0.};",
        description='Robots to spawn; multiple robots can be separated by a semicolon.'
    )

    gui_config_arg = DeclareLaunchArgument(
        'gui_config', default_value='default.config',
        description='GUI configuration file for Gazebo.'
    )

    nav2_arg = DeclareLaunchArgument('nav2', default_value='True', description='Enable Nav2 bringup.')

    # اسم فولدر الخريطة (داخل andino_gz/maps/<map_name>/map_name.yaml)
    map_name_arg = DeclareLaunchArgument(
        'map', default_value='office',
        description='Map subfolder under andino_gz/maps/ (e.g. office, warehouse...).'
    )

    params_file_arg = DeclareLaunchArgument(
        'params_file',
        default_value=PathJoinSubstitution([pkg_andino_gz, 'config', 'nav2_params.yaml']),
        description='Nav2 configuration file (applies to all Nav2 nodes).'
    )

    # Initial pose (في إطار map)
    initpose_x_arg       = DeclareLaunchArgument('initpose_x',       default_value='0.0')
    initpose_y_arg       = DeclareLaunchArgument('initpose_y',       default_value='0.0')
    initpose_yaw_deg_arg = DeclareLaunchArgument('initpose_yaw_deg', default_value='0.0')

    # ---------------- Launch Configs ----------------
    rviz        = LaunchConfiguration('rviz')
    ros_bridge  = LaunchConfiguration('ros_bridge')
    world_name  = LaunchConfiguration('world_name')
    map_name    = LaunchConfiguration('map')
    gui_config  = LaunchConfiguration('gui_config')
    nav2_flag   = LaunchConfiguration('nav2')
    params_file = LaunchConfiguration('params_file')

    initpose_x       = LaunchConfiguration('initpose_x')
    initpose_y       = LaunchConfiguration('initpose_y')
    initpose_yaw_deg = LaunchConfiguration('initpose_yaw_deg')

    # ---------------- Paths ----------------
    world_path      = PathJoinSubstitution([pkg_andino_gz, 'worlds', world_name])
    gui_config_path = PathJoinSubstitution([pkg_andino_gz, 'config_gui', gui_config])

    # نبني مسار الـ YAML كامل للـ map_server
    map_yaml_path = PathJoinSubstitution([
        pkg_andino_gz, 'maps', map_name,
        TextJoin(substitutions=[map_name, '.yaml'])
    ])

    log_world_path = LogInfo(msg=TextJoin(substitutions=["World path: ", world_path]))
    log_map_path   = LogInfo(msg=TextJoin(substitutions=["Map YAML:   ", map_yaml_path]))

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
            # لتفادي مشاكل OpenGL داخل الكونتينر
            SetEnvironmentVariable('LIBGL_ALWAYS_SOFTWARE', '1'),

            # Gazebo Sim
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
                ),
                launch_arguments={'gz_args': gz_args}.items(),
            ),

            # ROS-GZ bridge للـ /clock
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

    # ---------------- Static TF: map = world ----------------
    static_tf_map_to_world = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='tf_map_to_world',
        # x y z roll pitch yaw parent child
        arguments=['0', '0', '0', '0', '0', '0', 'map', 'world'],
        output='screen'
    )

    # ---------------- Robots + Nav2 ----------------
    robots_list = ParseMultiRobotPose('robots').value()
    log_robots_by_user = LogInfo(msg="Robots provided by user.")
    if robots_list == {}:
        log_robots_by_user = LogInfo(msg="No robots provided, using default:")
        robots_list = {"andino": {"x": 0., "y": 0., "z": 0.1, "yaw": 0.}}
    log_number_robots = LogInfo(msg="Robots to spawn: " + str(robots_list))

    spawn_robots_group = []
    more_than_one_robot = PythonExpression([TextSubstitution(text=str(len(robots_list.keys()))), ' > 1'])
    one_robot           = PythonExpression([TextSubstitution(text=str(len(robots_list.keys()))), ' == 1'])

    # نسيب الزمن و TF يستقروا شوية
    rviz_delay = 5.0
    nav2_delay = 8.0

    for robot_name in robots_list:
        init_pose = robots_list[robot_name]

        # ---------------- مجموعة السبون و الـ TFs بتاعة الروبوت ----------------
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

                # Spawn الروبوت (SDF)
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

                # Robot State Publisher
                Node(
                    package='robot_state_publisher',
                    executable='robot_state_publisher',
                    name='robot_state_publisher',
                    output='screen',
                    parameters=[{'use_sim_time': True}],
                    remappings=[('robot_description', 'robot_description')],
                ),

                # EKF بدري عشان ينشر odom->base_link
                Node(
                    package='robot_localization',
                    executable='ekf_node',
                    name='ekf_odom',
                    output='screen',
                    parameters=[{
                        'use_sim_time': True,
                        'frequency': 30.0,
                        'two_d_mode': True,
                        'publish_tf': True,

                        'map_frame': 'map',
                        'odom_frame': 'odom',
                        'base_link_frame': 'base_link',
                        'world_frame': 'odom',

                        # مصدر الأودوم
                        'odom0': 'odom',
                        'odom0_config': [True, True, False,
                                         False, False, True,
                                         True, True, False,
                                         False, False, True,
                                         False, False, False],
                        'odom0_differential': False,
                        'odom0_queue_size': 10,

                        # IMU
                        'imu0': '/imu/data',
                        'imu0_config':  [False, False, False,
                                         False, False, True,
                                         False, False, False,
                                         False, False, True,
                                         False, False, False],
                        'imu0_remove_gravitational_acceleration': True,
                        'imu0_queue_size': 50
                    }],
                ),

                # RViz (Nav2)
                TimerAction(
                    period=rviz_delay,
                    actions=[
                        Node(
                            condition=IfCondition(PythonExpression([rviz, ' and ', LaunchConfiguration('nav2')])),
                            package='rviz2',
                            executable='rviz2',
                            arguments=['-d', os.path.join(pkg_andino_gz, 'rviz', 'andino_gz_nav2.rviz')],
                            parameters=[{'use_sim_time': True}],
                            remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
                            output='screen',
                            additional_env={'QT_QPA_PLATFORM': 'xcb'}
                        )
                    ]
                ),

                # RViz (بدون Nav2)
                TimerAction(
                    period=rviz_delay,
                    actions=[
                        Node(
                            condition=IfCondition(PythonExpression([rviz, ' and not ', LaunchConfiguration('nav2')])),
                            package='rviz2',
                            executable='rviz2',
                            arguments=['-d', os.path.join(pkg_andino_gz, 'rviz', 'andino_gz.rviz')],
                            parameters=[{'use_sim_time': True}],
                            remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
                            output='screen',
                            additional_env={'QT_QPA_PLATFORM': 'xcb'}
                        )
                    ]
                ),

                # جسور Gazebo<->ROS الخاصة بالروبوت
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(
                        os.path.join(pkg_andino_gz, 'launch', 'include', 'gz_ros_bridge.launch.py')
                    ),
                    launch_arguments={'entity': robot_name}.items(),
                    condition=IfCondition(ros_bridge),
                ),
            ]
        )

        # ---------------- مجموعة Nav2 ----------------
        nav_group = GroupAction(
            scoped=True, forwarding=False,
            launch_configurations={
                'rviz': rviz,
                'ros_bridge': ros_bridge,
                'map': map_yaml_path,      # هنا بنمرر مسار YAML نفسه
                'params_file': params_file,
                'nav2': nav2_flag,
            },
            actions=[
                # Remap للـ scan (روبوت واحد)
                SetRemap(src='/global_costmap/scan', dst='/scan',
                         condition=IfCondition(PythonExpression([one_robot, ' and ', LaunchConfiguration('nav2')]))),
                SetRemap(src='/local_costmap/scan', dst='/scan',
                         condition=IfCondition(PythonExpression([one_robot, ' and ', LaunchConfiguration('nav2')]))),

                # Remap في حالة تعدد الروبوتات
                SetRemap(src='/' + robot_name + '/global_costmap/scan', dst='/' + robot_name + '/scan',
                         condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', LaunchConfiguration('nav2')]))),
                SetRemap(src='/' + robot_name + '/local_costmap/scan', dst='/' + robot_name + '/scan',
                         condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', LaunchConfiguration('nav2')]))),

                # Nav2 bringup بعد تأخير بسيط
                TimerAction(
                    period=nav2_delay,
                    actions=[
                        # روبوت واحد
                        IncludeLaunchDescription(
                            PythonLaunchDescriptionSource(
                                os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')
                            ),
                            launch_arguments={
                                'map': map_yaml_path,   # ← YAML مباشرة
                                'autostart': 'True',
                                'use_sim_time': 'True',
                                'params_file': LaunchConfiguration('params_file'),
                            }.items(),
                            condition=IfCondition(PythonExpression([one_robot, ' and ', LaunchConfiguration('nav2')])),
                        ),
                        # تعدد روبوتات
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
                                'params_file': LaunchConfiguration('params_file'),
                            }.items(),
                            condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', LaunchConfiguration('nav2')])),
                        ),
                    ]
                ),

                # -------- ضبط باراميترات سريعة (بعد ما كل عقد Nav2 تبقى Active) --------
                # * من غير تعديل YAML *
                TimerAction(
                    period=nav2_delay + 6.0,   # بعد التفعيل
                    actions=[
                        # سرعات أهدى لتفادي الاصطدام
                        ExecuteProcess(cmd=['/bin/bash','-lc',
                            'ros2 param set /controller_server FollowPath.max_vel_x 0.25 || true'], output='screen'),
                        ExecuteProcess(cmd=['/bin/bash','-lc',
                            'ros2 param set /controller_server FollowPath.max_vel_theta 0.8 || true'], output='screen'),
                        ExecuteProcess(cmd=['/bin/bash','-lc',
                            'ros2 param set /controller_server FollowPath.acc_lim_x 0.5 || true'], output='screen'),
                        ExecuteProcess(cmd=['/bin/bash','-lc',
                            'ros2 param set /controller_server FollowPath.acc_lim_theta 1.0 || true'], output='screen'),
                        # عينات DWB (اسم البارام صحيح vtheta_samples)
                        ExecuteProcess(cmd=['/bin/bash','-lc',
                            'ros2 param set /controller_server FollowPath.vx_samples 10 || true'], output='screen'),
                        ExecuteProcess(cmd=['/bin/bash','-lc',
                            'ros2 param set /controller_server FollowPath.vtheta_samples 20 || true'], output='screen'),
                        # تضخيم أكبر شوية في الكوستمابس
                        ExecuteProcess(cmd=['/bin/bash','-lc',
                            'ros2 param set /local_costmap  inflation_layer.inflation_radius 0.35 || true'], output='screen'),
                        ExecuteProcess(cmd=['/bin/bash','-lc',
                            'ros2 param set /global_costmap inflation_layer.inflation_radius 0.55 || true'], output='screen'),
                        # تساهل هدف معقول
                        ExecuteProcess(cmd=['/bin/bash','-lc',
                            'ros2 param set /controller_server general_goal_checker.xy_goal_tolerance 0.20 || true'], output='screen'),
                        ExecuteProcess(cmd=['/bin/bash','-lc',
                            'ros2 param set /controller_server general_goal_checker.yaw_goal_tolerance 0.25 || true'], output='screen'),
                    ]
                ),
            ]
        )

        spawn_robots_group.append(robots_group)
        spawn_robots_group.append(nav_group)

    # ---------------- Auto initial pose ----------------
    auto_initial_pose = TimerAction(
        period=10.0,
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

    # ---------------- Clear costmaps (مرة واحدة بعد الإقلاع) ----------------
    clear_costmaps_once = TimerAction(
        period=nav2_delay + 4.0,
        actions=[
            ExecuteProcess(
                cmd=['/bin/bash', '-lc',
                     'ros2 service call /global_costmap/clear_entirely_global_costmap std_srvs/srv/Empty "{}"'],
                output='screen'
            ),
            ExecuteProcess(
                cmd=['/bin/bash', '-lc',
                     'ros2 service call /local_costmap/clear_entirely_local_costmap std_srvs/srv/Empty "{}"'],
                output='screen'
            ),
        ]
    )

    # ---------------- Launch Description ----------------
    ld = LaunchDescription()

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

    # Logs + Gazebo + TF map->world
    ld.add_action(log_world_path)
    ld.add_action(log_map_path)
    ld.add_action(base_group)
    ld.add_action(static_tf_map_to_world)

    # Robots + Nav2
    ld.add_action(LogInfo(msg="Robots to spawn: " + str(robots_list)))
    for group in spawn_robots_group:
        ld.add_action(group)

    # Auto init pose + clear costmaps
    ld.add_action(auto_initial_pose)
    ld.add_action(clear_costmaps_once)

    return ld
