#!/usr/bin/env python3
import os
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
    pkg_andino_gz = get_package_share_directory('andino_gz')
    pkg_nav2_bringup = get_package_share_directory('nav2_bringup')
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')

    # ----------------- arguments -----------------
    ros_bridge_arg      = DeclareLaunchArgument('ros_bridge', default_value='True')
    rviz_arg            = DeclareLaunchArgument('rviz',       default_value='True')
    world_name_arg      = DeclareLaunchArgument('world_name', default_value='populated_office.sdf')
    robots_arg          = DeclareLaunchArgument('robots',     default_value="andino={x: 0., y: 0., z: 0.1, yaw: 0.};")
    gui_config_arg      = DeclareLaunchArgument('gui_config', default_value='default.config')
    nav2_arg            = DeclareLaunchArgument('nav2',       default_value='True')
    map_name_arg        = DeclareLaunchArgument('map',        default_value='office')
    params_file_arg     = DeclareLaunchArgument(
        'params_file',
        default_value=PathJoinSubstitution([pkg_andino_gz, 'config', 'nav2_params.yaml'])
    )

    # التحويل world->map (اضبطهم بالقيم اللي قستها من AMCL)
    offset_x_arg   = DeclareLaunchArgument('map_offset_x',   default_value='0.53805135')
    offset_y_arg   = DeclareLaunchArgument('map_offset_y',   default_value='0.31841763')
    offset_yaw_arg = DeclareLaunchArgument('map_offset_yaw', default_value='0.00934625')  # راديان ~ 0.536°

    publish_world_map_tf_arg = DeclareLaunchArgument('publish_world_map_tf', default_value='True')

    # ----------------- configurations -----------------
    ros_bridge   = LaunchConfiguration('ros_bridge')
    rviz         = LaunchConfiguration('rviz')
    world_name   = LaunchConfiguration('world_name')
    gui_config   = LaunchConfiguration('gui_config')
    nav2_flag    = LaunchConfiguration('nav2')
    map_name     = LaunchConfiguration('map')
    params_file  = LaunchConfiguration('params_file')

    offset_x     = LaunchConfiguration('map_offset_x')
    offset_y     = LaunchConfiguration('map_offset_y')
    offset_yaw   = LaunchConfiguration('map_offset_yaw')
    do_world_map = LaunchConfiguration('publish_world_map_tf')

    # ----------------- paths -----------------
    world_path      = PathJoinSubstitution([pkg_andino_gz, 'worlds', world_name])
    gui_config_path = PathJoinSubstitution([pkg_andino_gz, 'config_gui', gui_config])
    map_yaml_path   = PathJoinSubstitution([
        pkg_andino_gz, 'maps', map_name,
        TextJoin(substitutions=[map_name, '.yaml'])
    ])

    # ----------------- Gazebo (gz_sim) -----------------
    gz_args = TextJoin(
        substitutions=[
            world_path,
            TextJoin(substitutions=['--gui-config', gui_config_path], separator=' ')
        ],
        separator=' '
    )

    base_group = GroupAction([
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
            ),
            launch_arguments={'gz_args': gz_args}.items(),
        ),
        # clock bridge (so /use_sim_time works)
        Node(
            package='ros_gz_bridge', executable='parameter_bridge',
            arguments=['/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock]'],
            output='screen', namespace='andino_gz_sim',
            condition=IfCondition(ros_bridge),
        ),
    ])

    # ----------------- robots & Nav2 -----------------
    robots_list = ParseMultiRobotPose('robots').value()
    if not robots_list:
        robots_list = {"andino": {"x": 0., "y": 0., "z": 0.1, "yaw": 0.}}

    spawn_robots_group = []
    more_than_one_robot = PythonExpression([TextSubstitution(text=str(len(robots_list.keys()))), ' > 1'])
    one_robot           = PythonExpression([TextSubstitution(text=str(len(robots_list.keys()))), ' == 1'])

    # Keep the first robot's spawn pose to compute /initialpose later
    first_robot_name = list(robots_list.keys())[0]
    first_pose = robots_list[first_robot_name]
    init_spawn_x = float(first_pose['x'])
    init_spawn_y = float(first_pose['y'])
    init_spawn_yaw = float(first_pose['yaw'])

    for robot_name, init_pose in robots_list.items():
        robots_group = GroupAction([
            PushRosNamespace(condition=IfCondition(more_than_one_robot), namespace=robot_name),

            # Spawn robot in Gazebo
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

            # RViz (Fixed Frame = map)
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

            # ROS <-> GZ bridges for this robot
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(pkg_andino_gz, 'launch', 'include', 'gz_ros_bridge.launch.py')
                ),
                launch_arguments={'entity': robot_name}.items(),
                condition=IfCondition(ros_bridge),
            ),
        ])

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

            # Nav2 bringup (single robot)
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

            # Nav2 bringup (multi robot)
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

    # -------- static TF: gazebo_world -> map (من داخل الـ launch) --------
    static_world_map = Node(
        package='tf2_ros', executable='static_transform_publisher',
        # x y z  roll pitch yaw  parent child
        arguments=[offset_x, offset_y, '0', '0', '0', offset_yaw, 'gazebo_world', 'map'],
        output='screen',
        condition=IfCondition(do_world_map)
    )

    # -------- /initialpose = (spawn + offsets) بعد تفعيل map_server و amcl --------
    align_and_init_script = r'''
import os, time, math, rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseWithCovarianceStamped
from lifecycle_msgs.srv import GetState

SPAWN_X   = float(os.environ['SPAWN_X'])
SPAWN_Y   = float(os.environ['SPAWN_Y'])
SPAWN_YAW = float(os.environ['SPAWN_YAW'])
OFF_X     = float(os.environ['OFF_X'])
OFF_Y     = float(os.environ['OFF_Y'])
OFF_YAW   = float(os.environ['OFF_YAW'])

def wait_active(node, srv):
    cli = node.create_client(GetState, srv)
    while not cli.wait_for_service(timeout_sec=1.0):
        pass
    req = GetState.Request()
    while rclpy.ok():
        fut = cli.call_async(req)
        rclpy.spin_until_future_complete(node, fut, timeout_sec=1.0)
        if fut.result() and fut.result().current_state.label == "active":
            return
        time.sleep(0.2)

rclpy.init()
n = Node("publish_initialpose_with_offsets")

# 1) ensure lifecycle nodes are active
wait_active(n, "/map_server/get_state")
wait_active(n, "/amcl/get_state")

# 2) publish /initialpose in map = spawn + offsets
x_map = SPAWN_X + OFF_X
y_map = SPAWN_Y + OFF_Y
yaw_map = SPAWN_YAW + OFF_YAW
qz = math.sin(yaw_map/2.0)
qw = math.cos(yaw_map/2.0)

pub = n.create_publisher(PoseWithCovarianceStamped, "/initialpose", 10)
time.sleep(0.5)
msg = PoseWithCovarianceStamped()
msg.header.frame_id = "map"
msg.pose.pose.position.x = x_map
msg.pose.pose.position.y = y_map
msg.pose.pose.orientation.z = qz
msg.pose.pose.orientation.w = qw
msg.pose.covariance[0]=0.25; msg.pose.covariance[7]=0.25; msg.pose.covariance[35]=0.05
for _ in range(6):
    pub.publish(msg)
    time.sleep(0.15)

n.get_logger().info(f"/initialpose (map) = (spawn {SPAWN_X:.3f},{SPAWN_Y:.3f},{SPAWN_YAW:.3f}) + off ({OFF_X:.3f},{OFF_Y:.3f},{OFF_YAW:.3f}) -> ({x_map:.3f},{y_map:.3f},{yaw_map:.3f})")
n.destroy_node(); rclpy.shutdown()
'''

    auto_align_and_init = TimerAction(
        period=12.0,
        actions=[
            ExecuteProcess(
                cmd=['python3', '-c', align_and_init_script],
                output='screen',
                additional_env={
                    'SPAWN_X':   str(init_spawn_x),
                    'SPAWN_Y':   str(init_spawn_y),
                    'SPAWN_YAW': str(init_spawn_yaw),
                    'OFF_X':     offset_x.perform({}),
                    'OFF_Y':     offset_y.perform({}),
                    'OFF_YAW':   offset_yaw.perform({}),
                },
            )
        ],
        condition=IfCondition(nav2_flag)
    )

    # ----------------- Clear costmaps (optional) -----------------
    clear_costmaps = TimerAction(
        period=16.0,
        actions=[
            ExecuteProcess(
                cmd=['/bin/bash','-lc',
                     'ros2 service call /global_costmap/clear_entirely_global_costmap std_srvs/srv/Empty "{}"'],
                output='screen'
            ),
            ExecuteProcess(
                cmd=['/bin/bash','-lc',
                     'ros2 service call /local_costmap/clear_entirely_local_costmap std_srvs/srv/Empty "{}"'],
                output='screen'
            ),
        ],
        condition=IfCondition(nav2_flag)
    )

    # ----------------- assemble -----------------
    ld = LaunchDescription()
    for a in (ros_bridge_arg, rviz_arg, world_name_arg, robots_arg,
              gui_config_arg, nav2_arg, map_name_arg, params_file_arg,
              offset_x_arg, offset_y_arg, offset_yaw_arg, publish_world_map_tf_arg):
        ld.add_action(a)

    ld.add_action(base_group)
    for g in spawn_robots_group:
        ld.add_action(g)

    # أولاً ننشر تحويل world->map، ثم ننشر initialpose بعد ما Nav2 يبقى Active
    ld.add_action(static_world_map)
    ld.add_action(auto_align_and_init)
    ld.add_action(clear_costmaps)

    return ld
