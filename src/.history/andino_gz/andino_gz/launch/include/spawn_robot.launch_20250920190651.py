#!/usr/bin/env python3
"""Spawn an Andino robot in Gazebo (gz sim) and launch robot_state_publisher.

Pipeline:
  1) xacro -> /tmp/andino_urdf.xml
  2) gz sdf -p /tmp/andino_urdf.xml -> /tmp/andino_model.sdf
  3) spawn from SDF file
  4) robot_state_publisher reads URDF (as string) from the temp file
"""

from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    ExecuteProcess,
    RegisterEventHandler,
)
from launch.event_handlers import OnProcessExit
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    TextSubstitution,
    Command,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    # ---------- Args ----------
    entity_arg           = DeclareLaunchArgument('entity', default_value='andino', description='Robot entity name.')
    initial_pose_x_arg   = DeclareLaunchArgument('initial_pose_x', default_value='0.0')
    initial_pose_y_arg   = DeclareLaunchArgument('initial_pose_y', default_value='0.0')
    initial_pose_z_arg   = DeclareLaunchArgument('initial_pose_z', default_value='0.1')
    initial_pose_yaw_arg = DeclareLaunchArgument('initial_pose_yaw', default_value='0.0')
    robot_desc_topic_arg = DeclareLaunchArgument('robot_description_topic', default_value='robot_description')
    rsp_frequency_arg    = DeclareLaunchArgument('rsp_frequency', default_value='30.0')
    use_sim_time_arg     = DeclareLaunchArgument('use_sim_time', default_value='true')
    use_ultrasonic_arg   = DeclareLaunchArgument('use_ultrasonic', default_value='True',
                             description='Enable/disable ultrasonic sensor in xacro.')

    # ---------- LCs ----------
    entity           = LaunchConfiguration('entity')
    initial_pose_x   = LaunchConfiguration('initial_pose_x')
    initial_pose_y   = LaunchConfiguration('initial_pose_y')
    initial_pose_z   = LaunchConfiguration('initial_pose_z')
    initial_pose_yaw = LaunchConfiguration('initial_pose_yaw')
    robot_desc_topic = LaunchConfiguration('robot_description_topic')
    rsp_frequency    = LaunchConfiguration('rsp_frequency')
    use_sim_time     = LaunchConfiguration('use_sim_time')
    use_ultrasonic   = LaunchConfiguration('use_ultrasonic')

    # ---------- Paths ----------
    xacro_file = PathJoinSubstitution([FindPackageShare('andino_gz'), 'urdf', 'andino_gz.urdf.xacro'])
    # ثابتة لتجنّب مشاكل ضمّ النصوص
    urdf_path = TextSubstitution(text='/tmp/andino_urdf.xml')
    sdf_path  = TextSubstitution(text='/tmp/andino_model.sdf')

    # ---------- 1) Generate URDF file with xacro -o ----------
    gen_urdf_proc = ExecuteProcess(
        cmd=[
            'xacro',
            xacro_file,
            'use_fixed_caster:=false',
            TextSubstitution(text='use_ultrasonic:='), use_ultrasonic,
            '-o', urdf_path
        ],
        output='screen'
    )

    # ---------- robot_state_publisher (will start AFTER URDF is generated) ----------
    urdf_string_cmd = Command(['cat ', urdf_path])
    rsp_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='both',
        parameters=[{
            'use_sim_time': use_sim_time,
            'publish_frequency': rsp_frequency,
            'robot_description': ParameterValue(urdf_string_cmd, value_type=str),
        }],
        remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
    )

    # ---------- 2) Convert URDF -> SDF file (runs AFTER URDF generation) ----------
    gen_sdf_proc = ExecuteProcess(
        cmd=[
            'bash', '-lc',
            Command(['gz sdf -p ', urdf_path, ' > ', sdf_path])
        ],
        output='screen'
    )

    # ---------- 3) Spawn from SDF file (runs AFTER SDF generation) ----------
    spawn_proc = ExecuteProcess(
        cmd=[
            'ros2', 'run', 'ros_gz_sim', 'create',
            '-name', entity,
            '-file', sdf_path,
            '-x', initial_pose_x,
            '-y', initial_pose_y,
            '-z', initial_pose_z,
            '-R', '0', '-P', '0',
            '-Y', initial_pose_yaw,
        ],
        output='screen'
    )

    # Order: gen_urdf -> (rsp_node + gen_sdf) -> spawn
    on_urdf_done = RegisterEventHandler(
        OnProcessExit(target_action=gen_urdf_proc, on_exit=[rsp_node, gen_sdf_proc])
    )
    on_sdf_done = RegisterEventHandler(
        OnProcessExit(target_action=gen_sdf_proc, on_exit=[spawn_proc])
    )

    return LaunchDescription([
        # args
        entity_arg, initial_pose_x_arg, initial_pose_y_arg, initial_pose_z_arg, initial_pose_yaw_arg,
        robot_desc_topic_arg, rsp_frequency_arg, use_sim_time_arg, use_ultrasonic_arg,
        # pipeline
        gen_urdf_proc,
        on_urdf_done,
        on_sdf_done,
    ])
