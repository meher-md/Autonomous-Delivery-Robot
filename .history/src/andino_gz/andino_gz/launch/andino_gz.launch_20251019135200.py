#!/usr/bin/env python3
import os
import math

from ament_index_python.packages import get_package_share_directory

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument, GroupAction, IncludeLaunchDescription,
    TimerAction, ExecuteProcess
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import (
    LaunchConfiguration, PathJoinSubstitution, PythonExpression, TextSubstitution
)
from launch_ros.actions import Node, PushRosNamespace, SetRemap
from nav2_common.launch import ParseMultiRobotPose
from andino_gz.launch_tools.substitutions import TextJoin


def generate_launch_description():
    pkg_andino_gz    = get_package_share_directory('andino_gz')
    pkg_nav2_bringup = get_package_share_directory('nav2_bringup')
    pkg_ros_gz_sim   = get_package_share_directory('ros_gz_sim')

    # ----------------- launch args -----------------
    ros_bridge_arg    = DeclareLaunchArgument('ros_bridge',  default_value='True')
    rviz_arg          = DeclareLaunchArgument('rviz',        default_value='True')
    world_name_arg    = DeclareLaunchArgument('world_name',  default_value='populated_office.sdf')
    robots_arg        = DeclareLaunchArgument('robots',      default_value="andino={x: 0., y: 0., z: 0.1, yaw: 0.};")
    gui_config_arg    = DeclareLaunchArgument('gui_config',  default_value='default.config')
    nav2_arg          = DeclareLaunchArgument('nav2',        default_value='True')
    map_name_arg      = DeclareLaunchArgument('map',         default_value='office')
    params_file_arg   = DeclareLaunchArgument(
        'params_file',
        default_value=PathJoinSubstitution([pkg_andino_gz, 'config', 'nav2_params.yaml'])
    )
    # optional: publish /initialpose automatically based on the spawn pose of the first robot
    auto_initpose_arg = DeclareLaunchArgument('publish_initialpose', default_value='True')

    ros_bridge   = LaunchConfiguration('ros_bridge')
    rviz         = LaunchConfiguration('rviz')
    world_name   = LaunchConfiguration('world_name')
    gui_config   = LaunchConfiguration('gui_config')
    nav2_flag    = LaunchConfiguration('nav2')
    map_name     = LaunchConfiguration('map')
    params_file  = LaunchConfiguration('params_file')
    publish_init = LaunchConfiguration('publish_initialpose')

    world_path      = PathJoinSubstitution([pkg_andino_gz, 'worlds', world_name])
    gui_config_path = PathJoinSubstitution([pkg_andino_gz, 'config_gui', gui_config])
    map_yaml_path   = PathJoinSubstitution([pkg_andino_gz, 'maps', map_name, TextJoin([map_name, '.yaml'])])

    # ----------------- Gazebo (gz sim) -----------------
    gz_args = TextJoin(
        substitutions=[
            world_path,
            TextJoin(substitutions=['--gui-config', gui_config_path], separator=' ')
        ],
        separator=' '
    )

    base_group = GroupAction([
        # Start Gazebo
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
            ),
            launch_arguments={'gz_args': gz_args}.items(),
        ),

        # Optional: bridge /clock (order: GZ type -> ROS type)
        # If your environment already provides /clock, this can be kept enabled safely.
        Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            # One-direction bridge GZ->ROS
            # Note: both of the following syntaxes are supported depending on bridge version.
            # Keep the first; if your distro needs the second, switch as needed.
            arguments=[
                '/clock@gz.msgs.Clock@rosgraph_msgs/msg/Clock'
            ],
            output='screen',
            namespace='andino_gz_sim',
            condition=IfCondition(ros_bridge),
        ),
    ])

    # ----------------- robots & Nav2 -----------------
    robots_list = ParseMultiRobotPose('robots').value() or {"andino": {"x": 0., "y": 0., "z": 0.1, "yaw": 0.}}
    spawn_robots_group = []
    more_than_one_robot = PythonExpression([TextSubstitution(text=str(len(robots_list))), ' > 1'])
    one_robot           = PythonExpression([TextSubstitution(text=str(len(robots_list))), ' == 1'])

    # First robot (used by the auto /initialpose publisher)
    first_robot_name = list(robots_list.keys())[0]
    first_pose       = robots_list[first_robot_name]
    init_spawn_x     = float(first_pose['x'])
    init_spawn_y     = float(first_pose['y'])
    init_spawn_yaw   = float(first_pose['yaw'])

    for robot_name, init_pose in robots_list.items():
        robots_group = GroupAction([
            # Namespace only if we have more than one robot
            PushRosNamespace(condition=IfCondition(more_than_one_robot), namespace=robot_name),

            # LIDAR fixed transform (base_link -> rplidar_laser_link)
            Node(
                package='tf2_ros',
                executable='static_transform_publisher',
                name='rplidar_tf_pub',
                # x y z roll pitch yaw  (old-style is OK on Humble)
                arguments=['0.1', '0.0', '0.1', '0', '0', '0', 'base_link', 'rplidar_laser_link'],
                output='screen'
            ),

            # Spawn robot into Gazebo
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

            # Start RViz after a short delay (optional)
            TimerAction(
                period=5.0,
                actions=[
                    Node(
                        condition=IfCondition(PythonExpression([rviz, ' and ', nav2_flag])),
                        package='rviz2', executable='rviz2',
                        arguments=['-f', 'map',
                                   '-d', os.path.join(pkg_andino_gz, 'rviz', 'andino_gz_nav2.rviz')],
                        parameters=[{'use_sim_time': True}],
                        remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
                        output='screen',
                        additional_env={
                            'LIBGL_ALWAYS_SOFTWARE': '1',
                            'QT_XCB_GL_INTEGRATION': 'none',
                            'QT_QPA_PLATFORM': 'xcb'
                        }
                    )
                ]
            ),

            # Bridges for this robot (includes TF, odometry, sensors, cmd_vel, etc.)
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(pkg_andino_gz, 'launch', 'include', 'gz_ros_bridge.launch.py')
                ),
                launch_arguments={'entity': robot_name}.items(),
                condition=IfCondition(ros_bridge),
            ),
        ])

        # Nav2 bringup (+ scan remaps for single/multi robot)
        nav_group = GroupAction([
            # Laser remaps (single robot)
            SetRemap(src='/global_costmap/scan', dst='/scan',
                     condition=IfCondition(PythonExpression([one_robot, ' and ', nav2_flag]))),
            SetRemap(src='/local_costmap/scan', dst='/scan',
                     condition=IfCondition(PythonExpression([one_robot, ' and ', nav2_flag]))),

            # Laser remaps (multi robot)
            SetRemap(src=f'/{robot_name}/global_costmap/scan', dst=f'/{robot_name}/scan',
                     condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', nav2_flag]))),
            SetRemap(src=f'/{robot_name}/local_costmap/scan',  dst=f'/{robot_name}/scan',
                     condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', nav2_flag]))),

            # Nav2 (single robot)
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(pkg_nav2_bringup, 'launch', 'bringup_launch.py')
                ),
                launch_arguments={
                    'map': map_yaml_path,
                    'autostart': 'True',
                    'use_sim_time': 'True',
                    'params_file': params_file,
                }.items(),
                condition=IfCondition(PythonExpression([one_robot, ' and ', nav2_flag])),
            ),

            # Nav2 (multi robot)
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
                    'params_file': params_file,
                }.items(),
                condition=IfCondition(PythonExpression([more_than_one_robot, ' and ', nav2_flag])),
            ),
        ])

        spawn_robots_group += [robots_group, nav_group]

    # ----------------- auto /initialpose (optional) -----------------
    auto_initpose = TimerAction(
        period=10.0,
        actions=[
            ExecuteProcess(
                cmd=['python3', '-c', f"""
import rclpy, time, math
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped
rclpy.init()
n=Node('auto_initialpose')
pub=n.create_publisher(PoseWithCovarianceStamped,'/initialpose',10)
time.sleep(0.5)
msg=PoseWithCovarianceStamped()
msg.header.frame_id='map'
msg.pose.pose.position.x={init_spawn_x}
msg.pose.pose.position.y={init_spawn_y}
msg.pose.pose.orientation.z=math.sin({init_spawn_yaw}/2.0)
msg.pose.pose.orientation.w=math.cos({init_spawn_yaw}/2.0)
msg.pose.covariance[0]=0.25; msg.pose.covariance[7]=0.25; msg.pose.covariance[35]=0.05
for _ in range(6):
    pub.publish(msg); time.sleep(0.2)
rclpy.shutdown()
"""],
                output='screen'
            )
        ],
        condition=IfCondition(PythonExpression([nav2_flag, ' and ', publish_init]))
    )

    # ----------------- post-bringup utilities -----------------
    # Clear costmaps once Nav2 is up, to avoid stale obstacles
    clear_costmaps = TimerAction(
        period=18.0,
        actions=[
            ExecuteProcess(
                cmd=['/bin/bash','-lc','ros2 service call /global_costmap/clear_entirely_global_costmap std_srvs/srv/Empty "{}"'],
                output='screen'
            ),
            ExecuteProcess(
                cmd=['/bin/bash','-lc','ros2 service call /local_costmap/clear_entirely_local_costmap std_srvs/srv/Empty "{}"'],
                output='screen'
            ),
        ],
        condition=IfCondition(nav2_flag)
    )

    # ----------------- assemble description -----------------
    ld = LaunchDescription()
    for a in (
        ros_bridge_arg, rviz_arg, world_name_arg, robots_arg,
        gui_config_arg, nav2_arg, map_name_arg, params_file_arg, auto_initpose_arg
    ):
        ld.add_action(a)

    ld.add_action(base_group)
    for g in spawn_robots_group:
        ld.add_action(g)
    ld.add_action(auto_initpose)
    ld.add_action(clear_costmaps)

    return ld
