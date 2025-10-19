#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction, ExecuteProcess, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, TextSubstitution
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    # =========================
    # الملفات والمسارات
    # =========================
    andino_pkg = get_package_share_directory('andino_gz')  # عدّل لو اسم الحزمة مختلف
    nav2_bringup_pkg = get_package_share_directory('nav2_bringup')

    world_sdf = PathJoinSubstitution([andino_pkg, 'worlds', 'office.sdf'])
    rviz_cfg  = PathJoinSubstitution([andino_pkg, 'rviz', 'andino_gz_nav2.rviz'])
    map_yaml  = PathJoinSubstitution([andino_pkg, 'maps', 'office', 'office.yaml'])
    nav2_params = PathJoinSubstitution([andino_pkg, 'config', 'nav2_params.yaml'])  # عدّل لو ملفك في مكان آخر

    # =========================
    # بارامترات قابلة للتغيير
    # =========================
    use_sim_time = LaunchConfiguration('use_sim_time', default='true')
    autostart    = LaunchConfiguration('autostart',    default='true')
    use_composition = LaunchConfiguration('use_composition', default='true')

    # initial pose (بوحدة متر ودرجة Yaw)
    initpose_x = LaunchConfiguration('init_x', default='0.0')
    initpose_y = LaunchConfiguration('init_y', default='0.0')
    initpose_yaw_deg = LaunchConfiguration('init_yaw_deg', default='0.0')

    # =========================
    # بيئة ROS محلية (تقلل مشاكل الشبكة)
    # =========================
    env_local_only = SetEnvironmentVariable('ROS_LOCALHOST_ONLY', '1')

    # =========================
    # تشغيل Ignition Gazebo
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
    # (الموضوعات مبنية على اللوج عندك)
    # =========================
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='parameter_bridge',
        output='screen',
        arguments=[
            # Odom & TF
            '/model/andino/odometry@nav_msgs/msg/Odometry@gz.msgs.Odometry',
            '/model/andino/pose@tf2_msgs/msg/TFMessage@gz.msgs.Pose_V',
            # Joint states
            '/world/gazebo_world/model/andino/joint_state@sensor_msgs/msg/JointState@gz.msgs.Model',
            # Camera
            '/world/gazebo_world/model/andino/link/base_link/sensor/camera/camera_info'
            '@sensor_msgs/msg/CameraInfo@gz.msgs.CameraInfo',
            '/world/gazebo_world/model/andino/link/base_link/sensor/camera/image'
            '@sensor_msgs/msg/Image@gz.msgs.Image',
            # Lidar / scan
            '/world/gazebo_world/model/andino/link/base_link/sensor/sensor_ray_front/scan'
            '@sensor_msgs/msg/LaserScan@gz.msgs.LaserScan',
            '/world/gazebo_world/model/andino/link/base_link/sensor/sensor_ray_front/scan/points'
            '@sensor_msgs/msg/PointCloud2@gz.msgs.PointCloudPacked',
            # IMU
            '/imu/data@sensor_msgs/msg/Imu@gz.msgs.IMU',
            # اختياري: ألترسونك مبرج إلى /ultrasonic/scan
            '/world/gazebo_world/model/andino/link/base_link/sensor/sensor_ray_front/scan'
            '[/ultrasonic/scan]@sensor_msgs/msg/LaserScan@gz.msgs.LaserScan',
            # cmd_vel إلى Gazebo
            'geometry_msgs/msg/Twist@/model/andino/cmd_vel@gz.msgs.Twist'
        ],
        parameters=[{'use_sim_time': use_sim_time}],
        remappings=[
            ('/model/andino/odometry', 'odom'),
            ('/model/andino/pose', 'tf'),
            ('/world/gazebo_world/model/andino/joint_state', 'joint_states'),
            # الكاميرا
            ('/world/gazebo_world/model/andino/link/base_link/sensor/camera/camera_info', 'camera_info'),
            ('/world/gazebo_world/model/andino/link/base_link/sensor/camera/image', 'image_raw'),
            # الليدار
            ('/world/gazebo_world/model/andino/link/base_link/sensor/sensor_ray_front/scan', 'scan'),
            ('/world/gazebo_world/model/andino/link/base_link/sensor/sensor_ray_front/scan/points', 'scan/points'),
        ]
    )

    # =========================
    # ناشر TF ثابت (اختياري): odom -> world
    # يساعد على ربط الأشجار لو لسه العالم مسمي الإطار world/gazebo_world
    # =========================
    static_tf_odom_world = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_tf_odom_world',
        arguments=['0', '0', '0', '0', '0', '0', 'odom', 'world'],
        output='screen'
    )

    # =========================
    # Robot State Publisher (لو عندك URDF/Xacro)
    # =========================
    # لو الحزمة تنشره تلقائيًا يمكنك حذف هذا النود.
    # هنا نتركه مع use_sim_time فقط.
    robot_state_pub = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{'use_sim_time': use_sim_time}]
    )

    # =========================
    # Nav2 Bringup (كل العقد داخل container)
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
    # نشر initial pose (الإصلاح: كود بايثون multi-line)
    # يتأخر قليلًا بعد تشغيل Nav2/Gazebo.
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
    # تعريف وسائط للتغيير السريع
    # =========================
    declare_use_sim_time = DeclareLaunchArgument('use_sim_time', default_value='true')
    declare_autostart    = DeclareLaunchArgument('autostart', default_value='true')
    declare_use_comp     = DeclareLaunchArgument('use_composition', default_value='true')

    declare_init_x   = DeclareLaunchArgument('init_x', default_value=TextSubstitution(text='0.0'))
    declare_init_y   = DeclareLaunchArgument('init_y', default_value=TextSubstitution(text='0.0'))
    declare_init_yaw = DeclareLaunchArgument('init_yaw_deg', default_value=TextSubstitution(text='0.0'))

    # =========================
    # تجميع الـ LaunchDescription
    # =========================
    return LaunchDescription([
        env_local_only,

        declare_use_sim_time, declare_autostart, declare_use_comp,
        declare_init_x, declare_init_y, declare_init_yaw,

        ign_gazebo,
        bridge,
        static_tf_odom_world,
        robot_state_pub,
        nav2,
        rviz,

        auto_initial_pose,
    ])
