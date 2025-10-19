#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# English comments only.

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
    ExecuteProcess,
    SetEnvironmentVariable,
)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, TextSubstitution
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory


def generate_launch_description():
    # =========================
    # Packages and paths
    # =========================
    andino_pkg = get_package_share_directory('andino_gz')        # change if your package name differs
    nav2_bringup_pkg = get_package_share_directory('nav2_bringup')

    world_sdf = PathJoinSubstitution([andino_pkg, 'worlds', 'office.sdf'])
    rviz_cfg  = PathJoinSubstitution([andino_pkg, 'rviz', 'andino_gz_nav2.rviz'])
    map_yaml  = PathJoinSubstitution([andino_pkg, 'maps', 'office', 'office.yaml'])
    nav2_params = PathJoinSubstitution([andino_pkg, 'config', 'nav2_params.yaml'])  # change if your params file lives elsewhere

    # =========================
    # Tunable launch arguments
    # =========================
    use_sim_time   = LaunchConfiguration('use_sim_time', default='true')
    autostart      = LaunchConfiguration('autostart',    default='true')
    use_composition = LaunchConfiguration('use_composition', default='true')

    # Initial pose (meters and yaw in degrees)
    initpose_x = LaunchConfiguration('init_x', default='0.0')
    initpose_y = LaunchConfiguration('init_y', default='0.0')
    initpose_yaw_deg = LaunchConfiguration('init_yaw_deg', default='0.0')

    # =========================
    # Environment (helps avoid multicast / GL issues)
    # =========================
    env_local_only = SetEnvironmentVariable('ROS_LOCALHOST_ONLY', '1')
    # If RViz crashes on your machine, uncomment the next line to force software GL:
    # env_soft_gl = SetEnvironmentVariable('LIBGL_ALWAYS_SOFTWARE', '1')

    # =========================
    # Ignition Gazebo
    # =========================
    ign_gazebo = ExecuteProcess(
        cmd=[
            'ign', 'gazebo',
            world_sdf,
            '--gui-config', PathJoinSubstitution([andino_pkg, 'config_gui', 'default.config']),
            '--force-version', '6'
        ],
        output='screen'
    )

    # =========================
    # ros_gz_bridge – parameter_bridge
    # Topics based on your logs
    # NOTE:
    # - We use the GZ topic name in the argument and remap it to the ROS name.
    # - This avoids confusion and matches your previous log outputs.
    # =========================
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='parameter_bridge',
        output='screen',
        arguments=[
            # Odometry (GZ -> ROS)  : /model/andino/odometry -> odom
            '/model/andino/odometry@nav_msgs/msg/Odometry@gz.msgs.Odometry',

            # TF (GZ -> ROS)        : /model/andino/pose -> tf
            '/model/andino/pose@tf2_msgs/msg/TFMessage@gz.msgs.Pose_V',

            # Joint states (GZ -> ROS)
            '/world/gazebo_world/model/andino/joint_state@sensor_msgs/msg/JointState@gz.msgs.Model',

            # Camera (GZ -> ROS)
            '/world/gazebo_world/model/andino/link/base_link/sensor/camera/camera_info'
            '@sensor_msgs/msg/CameraInfo@gz.msgs.CameraInfo',
            '/world/gazebo_world/model/andino/link/base_link/sensor/camera/image'
            '@sensor_msgs/msg/Image@gz.msgs.Image',

            # Lidar / scan (GZ -> ROS)
            '/world/gazebo_world/model/andino/link/base_link/sensor/sensor_ray_front/scan'
            '@sensor_msgs/msg/LaserScan@gz.msgs.LaserScan',
            '/world/gazebo_world/model/andino/link/base_link/sensor/sensor_ray_front/scan/points'
            '@sensor_msgs/msg/PointCloud2@gz.msgs.PointCloudPacked',

            # IMU (GZ -> ROS)
            '/imu/data@sensor_msgs/msg/Imu@gz.msgs.IMU',

            # cmd_vel (ROS -> GZ) : publish ROS /cmd_vel to GZ /model/andino/cmd_vel
            # Use the GZ topic in the argument and remap to ROS "cmd_vel".
            '/model/andino/cmd_vel@geometry_msgs/msg/Twist@gz.msgs.Twist',
        ],
        parameters=[{'use_sim_time': use_sim_time}],
        remappings=[
            # GZ -> ROS remaps
            ('/model/andino/odometry', 'odom'),
            ('/model/andino/pose', 'tf'),
            ('/world/gazebo_world/model/andino/joint_state', 'joint_states'),
            ('/world/gazebo_world/model/andino/link/base_link/sensor/camera/camera_info', 'camera_info'),
            ('/world/gazebo_world/model/andino/link/base_link/sensor/camera/image', 'image_raw'),
            ('/world/gazebo_world/model/andino/link/base_link/sensor/sensor_ray_front/scan', 'scan'),
            ('/world/gazebo_world/model/andino/link/base_link/sensor/sensor_ray_front/scan/points', 'scan/points'),

            # ROS -> GZ remap for velocity command
            ('/model/andino/cmd_vel', 'cmd_vel'),
        ]
    )

    # =========================
    # Robot State Publisher (URDF/Xacro if any)
    # =========================
    robot_state_pub = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}]
    )

    # =========================
    # Nav2 Bringup (in a composed container)
    # Do NOT publish static map->odom TF; AMCL will provide it after initial pose.
    # =========================
    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            [nav2_bringup_pkg, '/launch/bringup_launch.py']
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
            'autostart': autostart,
            'use_composition': use_composition,
            'map': map_yaml,
            'params_file': nav2_params
        }.items()
    )

    # =========================
    # RViz
    # =========================
    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_cfg],
        parameters=[{'use_sim_time': use_sim_time}]
    )

    # =========================
    # Auto initial pose (multi-line Python, no SyntaxError)
    # Publishes for a few seconds after bringup.
    # =========================
    auto_initial_pose = TimerAction(
        period=18.0,
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
                        'x=float(sys.argv[1]); y=float(sys.argv[2]); yaw_deg=float(sys.argv[3])\n'
                        'qz=math.sin(math.radians(yaw_deg)/2.0); qw=math.cos(math.radians(yaw_deg)/2.0)\n'
                        'm=PoseWithCovarianceStamped()\n'
                        'm.header.frame_id="map"\n'
                        'm.pose.pose.position.x=x; m.pose.pose.position.y=y\n'
                        'm.pose.pose.orientation.z=qz; m.pose.pose.orientation.w=qw\n'
                        'm.pose.covariance[0]=0.25; m.pose.covariance[7]=0.25; m.pose.covariance[35]=0.05\n'
                        't_end = time.time() + 6.0\n'
                        'while rclpy.ok() and time.time() < t_end:\n'
                        '    m.header.stamp = n.get_clock().now().to_msg()\n'
                        '    p.publish(m)\n'
                        '    time.sleep(0.05)\n'
                        'n.get_logger().info(f"Auto initial pose burst: x={x:.3f}, y={y:.3f}, yaw_deg={yaw_deg:.1f}")\n'
                        'rclpy.shutdown()\n'
                    ),
                    initpose_x, initpose_y, initpose_yaw_deg
                ],
                output='screen',
                additional_env={'ROS_LOCALHOST_ONLY': '1'},
            )
        ]
    )

    # =========================
    # Declare arguments (so you can override from CLI)
    # =========================
    declare_use_sim_time = DeclareLaunchArgument('use_sim_time', default_value='true')
    declare_autostart    = DeclareLaunchArgument('autostart', default_value='true')
    declare_use_comp     = DeclareLaunchArgument('use_composition', default_value='true')

    declare_init_x   = DeclareLaunchArgument('init_x', default_value=TextSubstitution(text='0.0'))
    declare_init_y   = DeclareLaunchArgument('init_y', default_value=TextSubstitution(text='0.0'))
    declare_init_yaw = DeclareLaunchArgument('init_yaw_deg', default_value=TextSubstitution(text='0.0'))

    # =========================
    # Build LaunchDescription
    # =========================
    return LaunchDescription([
        env_local_only,
        # env_soft_gl,  # uncomment if needed

        declare_use_sim_time, declare_autostart, declare_use_comp,
        declare_init_x, declare_init_y, declare_init_yaw,

        ign_gazebo,
        bridge,
        robot_state_pub,
        nav2,
        rviz,

        auto_initial_pose,
    ])
