#!/usr/bin/env python3

import os from ament_index_python.packages import get_package_share_directory from launch import LaunchDescription from launch.actions import ( DeclareLaunchArgument, GroupAction, IncludeLaunchDescription, LogInfo, TimerAction, ExecuteProcess, ) from launch.conditions import IfCondition from launch.launch_description_sources import PythonLaunchDescriptionSource from launch.substitutions import ( LaunchConfiguration, PathJoinSubstitution, PythonExpression, TextSubstitution, ) from launch_ros.actions import Node, PushRosNamespace, SetRemap

from nav2_common.launch import ParseMultiRobotPose from andino_gz.launch_tools.substitutions import TextJoin

def generate_launch_description(): pkg_andino_gz = get_package_share_directory('andino_gz') pkg_nav2_bringup = get_package_share_directory('nav2_bringup')
# ---------------- Launch Args ----------------
ros_bridge_arg = DeclareLaunchArgument(
    &apos;ros_bridge&apos;, default_value=&apos;True&apos;, description=&apos;Run ROS bridge node.&apos;
)
rviz_arg = DeclareLaunchArgument(&apos;rviz&apos;, default_value=&apos;True&apos;, description=&apos;Start RViz.&apos;)
world_name_arg = DeclareLaunchArgument(
    &apos;world_name&apos;, default_value=&apos;populated_office.sdf&apos;,
    description=&apos;Name of the world to load. Match with map if using Nav2.&apos;
)
robots_arg = DeclareLaunchArgument(
    &apos;robots&apos;, default_value=&quot;andino={x: 0., y: 0., z: 0.1, yaw: 0.};&quot;,
    description=&apos;Robots to spawn, multiple robots can be stated separated by a ; &apos;
)
gui_config_arg = DeclareLaunchArgument(
    &apos;gui_config&apos;, default_value=&apos;default.config&apos;,
    description=&apos;Name of the gui configuration file to load.&apos;
)
nav2_arg = DeclareLaunchArgument(&apos;nav2&apos;, default_value=&apos;True&apos;, description=&apos;Enable Nav2 Bringup.&apos;)
map_name_arg = DeclareLaunchArgument(
    &apos;map&apos;, default_value=&quot;office&quot;,
    description=&apos;Name of the map to load. It should match the world_name.&apos;
)
params_file_arg = DeclareLaunchArgument(
    &apos;params_file&apos;,
    default_value=PathJoinSubstitution([pkg_andino_gz, &apos;config&apos;, &apos;nav2_params.yaml&apos;]),
    description=&apos;Nav2 configuration file for all launched nodes.&apos;
)

# Initial pose arguments (map frame)
initpose_x_arg = DeclareLaunchArgument(
    &apos;initpose_x&apos;, default_value=&apos;0.0&apos;, description=&apos;Initial pose X in map frame.&apos;
)
initpose_y_arg = DeclareLaunchArgument(
    &apos;initpose_y&apos;, default_value=&apos;0.0&apos;, description=&apos;Initial pose Y in map frame.&apos;
)
initpose_yaw_deg_arg = DeclareLaunchArgument(
    &apos;initpose_yaw_deg&apos;, default_value=&apos;0.0&apos;, description=&apos;Initial yaw (degrees) in map frame.&apos;
)

# ---------------- Launch Configs ----------------
rviz = LaunchConfiguration(&apos;rviz&apos;)
ros_bridge = LaunchConfiguration(&apos;ros_bridge&apos;)
world_name = LaunchConfiguration(&apos;world_name&apos;)
map_name = LaunchConfiguration(&apos;map&apos;)
gui_config = LaunchConfiguration(&apos;gui_config&apos;)
nav2_flag = LaunchConfiguration(&apos;nav2&apos;)
params_file = LaunchConfiguration(&apos;params_file&apos;)

initpose_x = LaunchConfiguration(&apos;initpose_x&apos;)
initpose_y = LaunchConfiguration(&apos;initpose_y&apos;)
initpose_yaw_deg = LaunchConfiguration(&apos;initpose_yaw_deg&apos;)

# ---------------- Paths ----------------
world_path = PathJoinSubstitution([pkg_andino_gz, &apos;worlds&apos;, world_name])
gui_config_path = PathJoinSubstitution([pkg_andino_gz, &apos;config_gui&apos;, gui_config])
map_path = PathJoinSubstitution([pkg_andino_gz, &apos;maps&apos;, map_name, TextJoin(substitutions=[map_name, &apos;.yaml&apos;])])

log_world_path = LogInfo(msg=TextJoin(substitutions=[&quot;World path: &quot;, world_path]))
log_map_path = LogInfo(msg=TextJoin(substitutions=[&quot;Map path: &quot;, map_path]))

# ---------------- Gazebo ----------------
gz_args = TextJoin(
    substitutions=[
        world_path,
        TextJoin(substitutions=[&quot;--gui-config&quot;, gui_config_path], separator=&apos; &apos;),
    ],
    separator=&apos; &apos;,
)

base_group = GroupAction(
    scoped=True, forwarding=False,
    launch_configurations={
        &apos;ros_bridge&apos;: ros_bridge,
        &apos;world_name&apos;: world_name,
        &apos;gui_config&apos;: gui_config,
    },
    actions=[
        # Gazebo Sim
        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(get_package_share_directory(&apos;ros_gz_sim&apos;), &apos;launch&apos;, &apos;gz_sim.launch.py&apos;)
            ),
            launch_arguments={&apos;gz_args&apos;: gz_args}.items(),
        ),
        # ROS Bridge for /clock
        Node(
            package=&apos;ros_gz_bridge&apos;,
            executable=&apos;parameter_bridge&apos;,
            arguments=[&apos;/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock&apos;],
            output=&apos;screen&apos;,
            namespace=&apos;andino_gz_sim&apos;,
            condition=IfCondition(ros_bridge),
        ),
    ]
)

# ---------------- Static TF fix ----------------
# IMPORTANT:
# We REMOVE the old static TF publishers that connected odom-&gt;world and odom-&gt;gazebo_world
# because they break the TF tree (Nav2 expects map-&gt;odom from AMCL and odom-&gt;base_link from odometry).
# Instead, we PUBLISH ONLY ONE identity transform from Gazebo&apos;s world frame to the Nav2 map frame.
# This makes Gazebo&apos;s world coincide with Nav2&apos;s map.
static_tf_gazebo_world_to_map = Node(
    package=&apos;tf2_ros&apos;,
    executable=&apos;static_transform_publisher&apos;,
    name=&apos;tf_gazebo_world_to_map&apos;,
    arguments=[&apos;0&apos;, &apos;0&apos;, &apos;0&apos;, &apos;0&apos;, &apos;0&apos;, &apos;0&apos;, &apos;gazebo_world&apos;, &apos;map&apos;],  # parent=gazebo_world, child=map
    output=&apos;screen&apos;
)

# ---------------- Robots + Nav2 ----------------
robots_list = ParseMultiRobotPose(&apos;robots&apos;).value()
log_robots_by_user = LogInfo(msg=&quot;Robots provided by user.&quot;)
if (robots_list == {}):
    log_robots_by_user = LogInfo(msg=&quot;No robots provided, using default:&quot;)
    robots_list = {&quot;andino&quot;: {&quot;x&quot;: 0., &quot;y&quot;: 0., &quot;z&quot;: 0.1, &quot;yaw&quot;: 0.}}
log_number_robots = LogInfo(msg=&quot;Robots to spawn: &quot; + str(robots_list))

spawn_robots_group = []
more_than_one_robot = PythonExpression([TextSubstitution(text=str(len(robots_list.keys()))), &apos; &gt; 1&apos;])
one_robot = PythonExpression([TextSubstitution(text=str(len(robots_list.keys()))), &apos; == 1&apos;])

for robot_name in robots_list:
    init_pose = robots_list[robot_name]

    robots_group = GroupAction(
        scoped=True, forwarding=False,
        launch_configurations={
            &apos;rviz&apos;: rviz,
            &apos;ros_bridge&apos;: ros_bridge,
            &apos;nav2&apos;: nav2_flag,
        },
        actions=[
            LogInfo(msg=&quot;Group for robot: &quot; + robot_name),

            PushRosNamespace(
                condition=IfCondition(more_than_one_robot),
                namespace=robot_name
            ),

            # Spawn the robot
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(pkg_andino_gz, &apos;launch&apos;, &apos;include&apos;, &apos;spawn_robot.launch.py&apos;)
                ),
                launch_arguments={
                    &apos;entity&apos;: robot_name,
                    &apos;initial_pose_x&apos;: str(init_pose[&apos;x&apos;]),
                    &apos;initial_pose_y&apos;: str(init_pose[&apos;y&apos;]),
                    &apos;initial_pose_z&apos;: str(init_pose[&apos;z&apos;]),
                    &apos;initial_pose_yaw&apos;: str(init_pose[&apos;yaw&apos;]),
                    &apos;robot_description_topic&apos;: &apos;robot_description&apos;,
                    &apos;use_sim_time&apos;: &apos;true&apos;,
                }.items(),
            ),

            # RViz with Nav2 (delayed + software rendering to avoid GL crash)
            TimerAction(
                period=5.0,
                actions=[
                    Node(
                        condition=IfCondition(PythonExpression([rviz, &apos; and &apos;, LaunchConfiguration(&apos;nav2&apos;)])),
                        package=&apos;rviz2&apos;,
                        executable=&apos;rviz2&apos;,
                        arguments=[&apos;-d&apos;, os.path.join(pkg_andino_gz, &apos;rviz&apos;, &apos;andino_gz_nav2.rviz&apos;)],
                        parameters=[{&apos;use_sim_time&apos;: True}],
                        remappings=[(&apos;/tf&apos;, &apos;tf&apos;), (&apos;/tf_static&apos;, &apos;tf_static&apos;)],
                        output=&apos;screen&apos;,
                        additional_env={
                            &apos;LIBGL_ALWAYS_SOFTWARE&apos;: &apos;1&apos;,
                            &apos;QT_QPA_PLATFORM&apos;: &apos;xcb&apos;
                        }
                    )
                ]
            ),

            # RViz without Nav2 (also software rendering)
            TimerAction(
                period=5.0,
                actions=[
                    Node(
                        condition=IfCondition(PythonExpression([rviz, &apos; and not &apos;, LaunchConfiguration(&apos;nav2&apos;)])),
                        package=&apos;rviz2&apos;,
                        executable=&apos;rviz2&apos;,
                        arguments=[&apos;-d&apos;, os.path.join(pkg_andino_gz, &apos;rviz&apos;, &apos;andino_gz.rviz&apos;)],
                        parameters=[{&apos;use_sim_time&apos;: True}],
                        remappings=[(&apos;/tf&apos;, &apos;tf&apos;), (&apos;/tf_static&apos;, &apos;tf_static&apos;)],
                        output=&apos;screen&apos;,
                        additional_env={
                            &apos;LIBGL_ALWAYS_SOFTWARE&apos;: &apos;1&apos;,
                            &apos;QT_QPA_PLATFORM&apos;: &apos;xcb&apos;
                        }
                    )
                ]
            ),

            # Per-robot Gazebo&lt;-&gt;ROS bridges
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(pkg_andino_gz, &apos;launch&apos;, &apos;include&apos;, &apos;gz_ros_bridge.launch.py&apos;)
                ),
                launch_arguments={&apos;entity&apos;: robot_name}.items(),
                condition=IfCondition(ros_bridge),
            ),
        ]
    )

    nav_group = GroupAction(
        scoped=True, forwarding=False,
        launch_configurations={
            &apos;rviz&apos;: rviz,
            &apos;ros_bridge&apos;: ros_bridge,
            &apos;map&apos;: map_path,
            &apos;params_file&apos;: params_file,
            &apos;nav2&apos;: nav2_flag,
        },
        actions=[
            # Remap scan topics (single robot case)
            SetRemap(src=&apos;/global_costmap/scan&apos;, dst=&apos;/scan&apos;, condition=IfCondition(PythonExpression([one_robot, &apos; and &apos;, LaunchConfiguration(&apos;nav2&apos;)]))),
            SetRemap(src=&apos;/local_costmap/scan&apos;, dst=&apos;/scan&apos;, condition=IfCondition(PythonExpression([one_robot, &apos; and &apos;, LaunchConfiguration(&apos;nav2&apos;)]))),

            # Remap for multi-robot (namespaced)
            SetRemap(src=&apos;/&apos; + robot_name + &apos;/global_costmap/scan&apos;, dst=&apos;/&apos; + robot_name + &apos;/scan&apos;, condition=IfCondition(PythonExpression([more_than_one_robot, &apos; and &apos;, LaunchConfiguration(&apos;nav2&apos;)]))),
            SetRemap(src=&apos;/&apos; + robot_name + &apos;/local_costmap/scan&apos;, dst=&apos;/&apos; + robot_name + &apos;/scan&apos;, condition=IfCondition(PythonExpression([more_than_one_robot, &apos; and &apos;, LaunchConfiguration(&apos;nav2&apos;)]))),

            # Nav2 bringup (single robot)
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(pkg_nav2_bringup, &apos;launch&apos;, &apos;bringup_launch.py&apos;)
                ),
                launch_arguments={
                    &apos;map&apos;: LaunchConfiguration(&apos;map&apos;),
                    &apos;autostart&apos;: &apos;True&apos;,
                    &apos;use_sim_time&apos;: &apos;True&apos;,
                    &apos;params_file&apos;: LaunchConfiguration(&apos;params_file&apos;),
                }.items(),
                condition=IfCondition(PythonExpression([one_robot, &apos; and &apos;, LaunchConfiguration(&apos;nav2&apos;)])),
            ),

            # Nav2 bringup (multi-robot)
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(pkg_nav2_bringup, &apos;launch&apos;, &apos;bringup_launch.py&apos;)
                ),
                launch_arguments={
                    &apos;namespace&apos;: robot_name,
                    &apos;use_namespace&apos;: &apos;True&apos;,
                    &apos;map&apos;: LaunchConfiguration(&apos;map&apos;),
                    &apos;autostart&apos;: &apos;True&apos;,
                    &apos;use_sim_time&apos;: &apos;True&apos;,
                    &apos;params_file&apos;: LaunchConfiguration(&apos;params_file&apos;),
                }.items(),
                condition=IfCondition(PythonExpression([more_than_one_robot, &apos; and &apos;, LaunchConfiguration(&apos;nav2&apos;)])),
            ),
        ]
    )

    spawn_robots_group.append(robots_group)
    spawn_robots_group.append(nav_group)

# ---------------- Auto initial pose &amp; clear costmaps ----------------
auto_initial_pose = TimerAction(
    period=10.0,  # wait until Nav2 + TF ready
    actions=[
        ExecuteProcess(
            cmd=[
                &apos;python3&apos;, &apos;-c&apos;,
                # Publish PoseWithCovarianceStamped on /initialpose with (x,y,yaw_deg)
                (
                    &apos;import rclpy, math, sys; &apos;
                    &apos;from geometry_msgs.msg import PoseWithCovarianceStamped; &apos;
                    &apos;from rclpy.node import Node; &apos;
                    &apos;rclpy.init(); &apos;
                    &apos;n=Node(&quot;auto_initialpose&quot;); &apos;
                    &apos;p=n.create_publisher(PoseWithCovarianceStamped,&quot;/initialpose&quot;,10); &apos;
                    &apos;x=float(sys.argv[1]); y=float(sys.argv[2]); yaw_deg=float(sys.argv[3]); &apos;
                    &apos;qz=math.sin(math.radians(yaw_deg)/2.0); &apos;
                    &apos;qw=math.cos(math.radians(yaw_deg)/2.0); &apos;
                    &apos;m=PoseWithCovarianceStamped(); &apos;
                    &apos;m.header.frame_id=&quot;map&quot;; &apos;
                    &apos;m.pose.pose.position.x=x; m.pose.pose.position.y=y; &apos;
                    &apos;m.pose.pose.orientation.z=qz; m.pose.pose.orientation.w=qw; &apos;
                    &apos;m.pose.covariance[0]=0.25; m.pose.covariance[7]=0.25; m.pose.covariance[35]=0.05; &apos;
                    &apos;p.publish(m); &apos;
                    &apos;n.get_logger().info(f&quot;Auto initial pose published: x={x:.3f}, y={y:.3f}, yaw_deg={yaw_deg:.1f}&quot;); &apos;
                    &apos;rclpy.shutdown()&apos;
                ),
                initpose_x, initpose_y, initpose_yaw_deg
            ],
            output=&apos;screen&apos;
        )
    ]
)

clear_costmaps = TimerAction(
    period=12.0,  # ~2s after initial pose
    actions=[
        ExecuteProcess(
            cmd=[&apos;/bin/bash&apos;, &apos;-lc&apos;, &apos;ros2 service call /global_costmap/clear_entirely_global_costmap std_srvs/srv/Empty &quot;{}&quot;&apos;],
            output=&apos;screen&apos;
        ),
        ExecuteProcess(
            cmd=[&apos;/bin/bash&apos;, &apos;-lc&apos;, &apos;ros2 service call /local_costmap/clear_entirely_local_costmap std_srvs/srv/Empty &quot;{}&quot;&apos;],
            output=&apos;screen&apos;
        ),
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

# Static TF fix (ONLY gazebo_world -&gt; map). We DO NOT add odom-&gt;world or odom-&gt;gazebo_world.
ld.add_action(static_tf_gazebo_world_to_map)

# Robots + Nav2
for group in spawn_robots_group:
    ld.add_action(group)

# Automation
ld.add_action(auto_initial_pose)
ld.add_action(clear_costmaps)

return ld