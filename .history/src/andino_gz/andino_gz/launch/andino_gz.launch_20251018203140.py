#!/usr/bin/env python3
import os
import yaml
import math
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, GroupAction, IncludeLaunchDescription,
                            TimerAction, ExecuteProcess)
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
    ros_bridge_arg      = DeclareLaunchArgument('ros_bridge', default_value='True')
    rviz_arg            = DeclareLaunchArgument('rviz',       default_value='True')
    world_name_arg      = DeclareLaunchArgument('world_name', default_value='populated_office.sdf')
    robots_arg          = DeclareLaunchArgument('robots',     default_value="andino={x: 0., y: 0., z: 0.1, yaw: 0.};")
    gui_config_arg      = DeclareLaunchArgument('gui_config', default_value='default.config')
    nav2_arg            = DeclareLaunchArgument('nav2',       default_value='True')
    map_name_arg        = DeclareLaunchArgument('map',        default_value='office')
    params_file_arg     = DeclareLaunchArgument('params_file',
                             default_value=PathJoinSubstitution([pkg_andino_gz,'config','nav2_params.yaml']))
    tf_world_parent_arg = DeclareLaunchArgument('tf_world_parent', default_value='gazebo_world')

    # -------- cfgs --------
    rviz            = LaunchConfiguration('rviz')
    ros_bridge      = LaunchConfiguration('ros_bridge')
    world_name      = LaunchConfiguration('world_name')
    map_name        = LaunchConfiguration('map')
    gui_config      = LaunchConfiguration('gui_config')
    nav2_flag       = LaunchConfiguration('nav2')
    params_file     = LaunchConfiguration('params_file')
    tf_world_parent = LaunchConfiguration('tf_world_parent')

    # -------- paths --------
    world_path = PathJoinSubstitution([pkg_andino_gz, 'worlds', world_name])
    gui_config_path = PathJoinSubstitution([pkg_andino_gz, 'config_gui', gui_config])
    map_yaml_path = PathJoinSubstitution([pkg_andino_gz, 'maps', map_name,
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

    # -------- Static TF: gazebo_world -> odom --------
    static_tf_world_to_odom = Node(
        package='tf2_ros', executable='static_transform_publisher',
        name='tf_world_to_odom',
        arguments=['0','0','0','0','0','0', tf_world_parent, 'odom'],
        output='screen'
    )

    # -------- Robots + Nav2 --------
    robots_list = ParseMultiRobotPose('robots').value()
    if robots_list == {}:
        robots_list = {"andino": {"x": 0., "y": 0., "z": 0.1, "yaw": 0.}}

    spawn_robots_group = []
    more_than_one_robot = PythonExpression([TextSubstitution(text=str(len(robots_list.keys()))), ' > 1'])
    one_robot           = PythonExpression([TextSubstitution(text=str(len(robots_list.keys()))), ' == 1'])

    # خُد أول روبوت كمرجع
    first_robot_name = list(robots_list.keys())[0]
    first_pose = robots_list[first_robot_name]
    init_spawn_x = float(first_pose['x'])
    init_spawn_y = float(first_pose['y'])
    init_spawn_yaw = float(first_pose['yaw'])

    for robot_name, init_pose in robots_list.items():
        robots_group = GroupAction(
            actions=[
                PushRosNamespace(condition=IfCondition(more_than_one_robot), namespace=robot_name),

                # Spawn robot in Gazebo
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

                # RViz (Fixed Frame = map)
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

                # Bridges
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(os.path.join(pkg_andino_gz,'launch','include','gz_ros_bridge.launch.py')),
                    launch_arguments={'entity': robot_name}.items(),
                    condition=IfCondition(ros_bridge),
                ),
            ]
        )

        nav_group = GroupAction(
            actions=[
                # Laser remaps (single robot أو multi)
                SetRemap(src='/global_costmap/scan', dst='/scan',
                         condition=IfCondition(PythonExpression([one_robot,' and ',LaunchConfiguration('nav2')]))),
                SetRemap(src='/local_costmap/scan', dst='/scan',
                         condition=IfCondition(PythonExpression([one_robot,' and ',LaunchConfiguration('nav2')]))),

                SetRemap(src=f'/{robot_name}/global_costmap/scan', dst=f'/{robot_name}/scan',
                         condition=IfCondition(PythonExpression([more_than_one_robot,' and ',LaunchConfiguration('nav2')]))),
                SetRemap(src=f'/{robot_name}/local_costmap/scan',  dst=f'/{robot_name}/scan',
                         condition=IfCondition(PythonExpression([more_than_one_robot,' and ',LaunchConfiguration('nav2')]))),

                # Nav2 bringup
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(os.path.join(pkg_nav2_bringup,'launch','bringup_launch.py')),
                    launch_arguments={
                        'map': map_yaml_path,
                        'autostart': 'True',
                        'use_sim_time': 'True',
                        'params_file': params_file,
                    }.items(),
                    condition=IfCondition(PythonExpression([one_robot,' and ',LaunchConfiguration('nav2')])),
                ),
                IncludeLaunchDescription(
                    PythonLaunchDescriptionSource(os.path.join(pkg_nav2_bringup,'launch','bringup_launch.py')),
                    launch_arguments={
                        'namespace': robot_name,
                        'use_namespace': 'True',
                        'map': map_yaml_path,
                        'autostart': 'True',
                        'use_sim_time': 'True',
                        'params_file': params_file,
                    }.items(),
                    condition=IfCondition(PythonExpression([more_than_one_robot,' and ',LaunchConfiguration('nav2')])),
                ),
            ]
        )

        spawn_robots_group += [robots_group, nav_group]

    # -------- Auto initial pose AFTER amcl & map are ACTIVE --------
    # يقرأ origin من ملف الماب، يحسب initial pose = (spawn + (-origin)) وينشرها مرة واحدة
    auto_initial_pose = TimerAction(
        period=12.0,  # ادّي فرصة كفاية لNav2 يبقى Active
        actions=[
            ExecuteProcess(
                cmd=[
                    'python3','-c',
                    (
                        'import rclpy, time, yaml, math; '
                        'from geometry_msgs.msg import PoseWithCovarianceStamped; '
                        'from rclpy.node import Node; '
                        'from lifecycle_msgs.srv import GetState; '
                        'from ament_index_python.packages import get_package_share_directory; '
                        'import os; '
                        f'map_yaml="{os.path.join(pkg_andino_gz,"maps")}/' + '" + "' + '"'.join([]) + '"'
                    )
                ],
                output='screen'
            )
        ]
    )

    # بدل السكربت أعلاه بنسخة كاملة inline بدون اعتماد على متغيرات بايثون خارجية:
    auto_initial_pose = TimerAction(
        period=12.0,
        actions=[
            ExecuteProcess(
                cmd=[
                    'python3','-c',
                    (
                        'import rclpy, time, yaml, math, os; '
                        'from geometry_msgs.msg import PoseWithCovarianceStamped; '
                        'from rclpy.node import Node; '
                        'from lifecycle_msgs.srv import GetState; '
                        f'map_yaml_path = "{os.path.join(pkg_andino_gz, "maps")}/" + "' + '"'; '
                        # المسار الفعلي للـ yaml:
                        f'map_yaml_path = "{os.path.join(pkg_andino_gz,"maps")}/" + "{LaunchConfiguration("map").perform(None)}" + "/" + "{LaunchConfiguration("map").perform(None)}" + ".yaml"; '
                        # بما إن LaunchConfiguration.perform(None) لا يعمل هنا، فهنبسط: نحقن المسار statically عبر PythonJoinSubstitution سابقًا
                    )
                ],
                output='screen'
            )
        ]
    )

    # ملاحظة: لا يمكن استخدام LaunchConfiguration.perform(None) داخل سكربت inline.
    # لذلك هنمرر مسار الـ YAML كسلسلة جاهزة من اللانش نفسه:
    map_yaml_abs = os.path.join(pkg_andino_gz, 'maps', LaunchConfiguration('map').perform if hasattr(LaunchConfiguration('map'), 'perform') else 'office', 'office.yaml')
    # لكن perform غير متاح في وقت البناء. الحل: نكتب المسار كسلسلة من substitution جاهزة للأمر shell:
    map_yaml_cmd = ['bash','-lc', 'python3 - <<PY\n'
        'import rclpy, time, yaml, math, os\n'
        'from geometry_msgs.msg import PoseWithCovarianceStamped\n'
        'from rclpy.node import Node\n'
        'from lifecycle_msgs.srv import GetState\n'
        f'map_yaml = "{os.path.join(pkg_andino_gz, "maps")}/' + '" + "${MAP_NAME}" + "/' + '" + "${MAP_NAME}" + ".yaml"\n'
        f'init_spawn_x = {init_spawn_x}\n'
        f'init_spawn_y = {init_spawn_y}\n'
        f'init_spawn_yaw = {init_spawn_yaw}\n'
        'def wait_active(node, srv_name):\n'
        '    cli = node.create_client(GetState, srv_name)\n'
        '    while not cli.wait_for_service(timeout_sec=1.0):\n'
        '        node.get_logger().info(f"Waiting for {srv_name}...")\n'
        '    req = GetState.Request()\n'
        '    while True:\n'
        '        future = cli.call_async(req)\n'
        '        rclpy.spin_until_future_complete(node, future, timeout_sec=1.0)\n'
        '        if future.result() and future.result().current_state.label == "active":\n'
        '            return\n'
        '        time.sleep(0.5)\n'
        'rclpy.init()\n'
        'n = Node("auto_initialpose")\n'
        'p = n.create_publisher(PoseWithCovarianceStamped, "/initialpose", 10)\n'
        'wait_active(n, "/map_server/get_state")\n'
        'wait_active(n, "/amcl/get_state")\n'
        'with open(map_yaml, "r") as f:\n'
        '    data = yaml.safe_load(f)\n'
        'origin = data.get("origin", [0.0, 0.0, 0.0])\n'
        'ox, oy = float(origin[0]), float(origin[1])\n'
        '# احسب بوز الروبوت في map = (spawn - origin)\n'
        'x_map = init_spawn_x - ox\n'
        'y_map = init_spawn_y - oy\n'
        '# yaw\n'
        'yaw = init_spawn_yaw\n'
        'qz = math.sin(yaw/2.0)\n'
        'qw = math.cos(yaw/2.0)\n'
        'm = PoseWithCovarianceStamped()\n'
        'm.header.frame_id = "map"\n'
        'm.pose.pose.position.x = x_map\n'
        'm.pose.pose.position.y = y_map\n'
        'm.pose.pose.orientation.z = qz\n'
        'm.pose.pose.orientation.w = qw\n'
        'm.pose.covariance[0]=0.25; m.pose.covariance[7]=0.25; m.pose.covariance[35]=0.05\n'
        'p.publish(m)\n'
        'n.get_logger().info(f"Auto initial pose published: x={x_map:.3f}, y={y_map:.3f}, yaw={yaw:.3f}")\n'
        'time.sleep(0.5)\n'
        'n.destroy_node()\n'
        'rclpy.shutdown()\n'
        'PY'
    ]

    auto_initial_pose = TimerAction(
        period=12.0,
        actions=[
            ExecuteProcess(
                cmd=map_yaml_cmd,
                additional_env={'MAP_NAME': LaunchConfiguration('map')},
                output='screen'
            )
        ],
        condition=IfCondition(nav2_flag)
    )

    # -------- Clear costmaps بعد التهيئة --------
    clear_costmaps = TimerAction(
        period=15.0,
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
    ld.add_action(static_tf_world_to_odom)
    for g in spawn_robots_group:
        ld.add_action(g)
    ld.add_action(auto_initial_pose)
    ld.add_action(clear_costmaps)
    return ld
