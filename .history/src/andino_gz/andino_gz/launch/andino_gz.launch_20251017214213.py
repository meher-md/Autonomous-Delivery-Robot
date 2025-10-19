#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, ExecuteProcess, OpaqueFunction
from launch.substitutions import LaunchConfiguration, TextSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch.substitutions import PathJoinSubstitution, PythonExpression

def generate_launch_description():

    # ----------------------- Launch args -----------------------
    nav2_arg      = DeclareLaunchArgument('nav2',      default_value='True')
    world_name_arg= DeclareLaunchArgument('world_name',default_value='office.sdf')
    map_arg       = DeclareLaunchArgument('map',       default_value='office')

    pkg_share = FindPackageShare('andino_gz')

    world_path = PathJoinSubstitution([
        pkg_share, 'worlds', LaunchConfiguration('world_name')
    ])

    # maps/<map>/<map>.yaml  (مثال: maps/office/office.yaml)
    map_yaml = PathJoinSubstitution([
        pkg_share,
        'maps',
        LaunchConfiguration('map'),
        # نبني "office.yaml" من اسم الخريطة
        PythonExpression(["'", "", "'"]),  # عنصر وهمي لتسهيل الانضمام
    ])
    # فوق عملنا عنصر وهمي، فنبني اسم الملف بصيغة python داخل map_server param تحت

    # GUI config (اختياري)
    gui_cfg = PathJoinSubstitution([pkg_share, 'config_gui', 'default.config'])

    # ----------------------- Gazebo (Ignition) -----------------------
    ign_gazebo = ExecuteProcess(
        cmd=['ign', 'gazebo', world_path, '--gui-config', gui_cfg, '--force-version', '6'],
        output='screen'
    )

    # ----------------------- TF: gazebo_world -> map (هوية) -----------------------
    tf_world_map = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='tf_gazebo_world_to_map',
        arguments=['0', '0', '0', '0', '0', '0', 'gazebo_world', 'map'],
        output='screen',
        parameters=[{'use_sim_time': True}],
        env={'ROS_LOCALHOST_ONLY': '1'}
    )

    # ----------------------- Robot State Publisher -----------------------
    # نتوقع أن andino_gz بيولّد robot_description (xacro/urdf) من حِتّة تانية داخل الباكدج.
    # لو عندك xacro محدد، بدّله تحت في 'command' كما يلزم.
    robot_state_pub = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{'use_sim_time': True}],
        remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')]
    )

    # ----------------------- Spawn entity in Gazebo من robot_description -----------------------
    spawn_andino = Node(
        package='ros_gz_sim',
        executable='create',
        name='create',
        output='screen',
        arguments=[
            '-name', 'andino',
            '-topic', 'robot_description',
            '-x', '0.0', '-y', '0.0', '-z', '0.1',
            '-R', '0', '-P', '0', '-Y', '0.0'
        ],
        parameters=[{'use_sim_time': True}],
        env={'ROS_LOCALHOST_ONLY': '1'}
    )

    # ----------------------- ros_gz_bridge (الحد الأدنى) -----------------------
    # عدّل أو زوّد بريجات حسب مواضيعك الفعلية
    gz_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='andino_gz_sim.ros_gz_bridge',
        output='screen',
        parameters=[{
            'config': [
                # Clock
                {'topic_name': '/clock', 'ros_type_name': 'rosgraph_msgs/msg/Clock', 'gz_type_name': 'gz.msgs.Clock', 'direction': 'GZ_TO_ROS'},
                # LaserScan
                {'topic_name': '/scan',  'ros_type_name': 'sensor_msgs/msg/LaserScan', 'gz_type_name': 'gz.msgs.LaserScan', 'direction': 'GZ_TO_ROS'},
                # Cmd vel
                {'topic_name': '/cmd_vel', 'ros_type_name': 'geometry_msgs/msg/Twist', 'gz_type_name': 'gz.msgs.Twist', 'direction': 'ROS_TO_GZ'},
                # Odometry (لو بلجن جازيبوا بيطلعها)
                {'topic_name': '/model/andino/odometry', 'ros_type_name': 'nav_msgs/msg/Odometry', 'gz_type_name': 'gz.msgs.Odometry', 'direction': 'GZ_TO_ROS'},
                # TF
                {'topic_name': '/tf', 'ros_type_name': 'tf2_msgs/msg/TFMessage', 'gz_type_name': 'gz.msgs.Pose_V', 'direction': 'BIDIRECTIONAL'},
            ]
        }],
        remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
        env={'ROS_LOCALHOST_ONLY': '1'}
    )

    # ----------------------- إصلاح محوَّل الأودوم (المهم) -----------------------
    # هنا بنجبر الإطار الأب يكون "odom" دايمًا، حتى لو رسالة الأودوم جايه frame_id=world
    odom_to_tf = ExecuteProcess(
        cmd=[
            'python3', '-c',
            (
                'import rclpy, sys\n'
                'from rclpy.node import Node\n'
                'from nav_msgs.msg import Odometry\n'
                'from geometry_msgs.msg import TransformStamped\n'
                'from tf2_ros import TransformBroadcaster\n'
                'topic=sys.argv[1]\n'
                'rclpy.init()\n'
                'n=Node("odom_to_tf")\n'
                'br=TransformBroadcaster(n)\n'
                'def cb(msg):\n'
                '    t=TransformStamped()\n'
                '    t.header.stamp = msg.header.stamp\n'
                '    t.header.frame_id = "odom"  # <<<< نُثبِّت الأب odom هنا\n'
                '    t.child_frame_id = (msg.child_frame_id or "base_link")\n'
                '    t.transform.translation.x = msg.pose.pose.position.x\n'
                "    t.transform.translation.y = msg.pose.pose.position.y\n"
                "    t.transform.translation.z = msg.pose.pose.position.z\n"
                '    t.transform.rotation = msg.pose.pose.orientation\n'
                '    br.sendTransform(t)\n'
                'n.create_subscription(Odometry, topic, cb, 10)\n'
                'rclpy.spin(n)\n'
            ),
            # غيّر السطر ده لو موضوع الأودوم مختلف عندك:
            '/model/andino/odometry'
        ],
        output='screen',
        additional_env={'ROS_LOCALHOST_ONLY': '1'}
    )

    # ----------------------- Nav2 stack -----------------------
    # مانيجر اللايف سايكل + عقد Nav2 الأساسية
    # بنمرر مسار الخريطة كـ yaml_filename باستخدام PythonExpression عشان نكوّن "<map>.yaml"
    map_server = Node(
        package='nav2_map_server',
        executable='map_server',
        name='map_server',
        output='screen',
        parameters=[{
            'use_sim_time': True,
            'yaml_filename': PythonExpression([
                '"', '',
                '" + "', PathJoinSubstitution([pkg_share, 'maps', LaunchConfiguration('map')]).perform({}),
                '/" + "', LaunchConfiguration('map'), '".replace(" ','") + ".yaml"'  # لن يُقيَّم هنا؛ fallback تحت
            ])
        }],
    )
    # ملاحظة: في بعض البيئات PythonExpression أعلاه ممكن ما يشتغل بسبب قيود substitutions.
    # إن حصل كده، ببساطة غيّر السطر السابق إلى:
    # parameters=[{'use_sim_time': True,
    #              'yaml_filename': PathJoinSubstitution([pkg_share, 'maps', LaunchConfiguration('map'),
    #                                                   TextSubstitution(text='office.yaml')])}]

    amcl = Node(
        package='nav2_amcl',
        executable='amcl',
        name='amcl',
        output='screen',
        parameters=[{'use_sim_time': True}],
        remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')]
    )

    controller_server = Node(
        package='nav2_controller', executable='controller_server',
        name='controller_server', output='screen',
        parameters=[{'use_sim_time': True}]
    )
    planner_server = Node(
        package='nav2_planner', executable='planner_server',
        name='planner_server', output='screen',
        parameters=[{'use_sim_time': True}]
    )
    smoother_server = Node(
        package='nav2_smoother', executable='smoother_server',
        name='smoother_server', output='screen',
        parameters=[{'use_sim_time': True}]
    )
    bt_navigator = Node(
        package='nav2_bt_navigator', executable='bt_navigator',
        name='bt_navigator', output='screen',
        parameters=[{'use_sim_time': True}]
    )
    lifecycle_mgr = Node(
        package='nav2_lifecycle_manager', executable='lifecycle_manager',
        name='lifecycle_manager_navigation', output='screen',
        parameters=[{
            'use_sim_time': True,
            'autostart': True,
            'node_names': [
                'map_server',
                'amcl',
                'controller_server',
                'planner_server',
                'smoother_server',
                'bt_navigator'
            ]
        }]
    )

    # ----------------------- RViz (اختياري) -----------------------
    rviz_cfg = PathJoinSubstitution([pkg_share, 'rviz', 'andino_gz_nav2.rviz'])
    rviz = Node(
        package='rviz2', executable='rviz2', name='rviz2',
        arguments=['-d', rviz_cfg],
        output='screen',
        parameters=[{'use_sim_time': True}],
        remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')]
    )

    # ----------------------- تجميع الكل -----------------------
    ld = LaunchDescription()
    ld.add_action(nav2_arg)
    ld.add_action(world_name_arg)
    ld.add_action(map_arg)

    ld.add_action(ign_gazebo)
    ld.add_action(tf_world_map)
    ld.add_action(robot_state_pub)
    ld.add_action(spawn_andino)
    ld.add_action(gz_bridge)
    ld.add_action(odom_to_tf)

    # Nav2 group
    ld.add_action(GroupAction([
        map_server,
        amcl,
        controller_server,
        planner_server,
        smoother_server,
        bt_navigator,
        lifecycle_mgr,
        rviz
    ]))

    return ld
