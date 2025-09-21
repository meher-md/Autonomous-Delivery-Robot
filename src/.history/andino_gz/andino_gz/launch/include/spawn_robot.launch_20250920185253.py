#!/usr/bin/env python3
"""Spawn an Andino robot in Gazebo (gz sim) and launch robot_state_publisher.

Generates URDF from xacro at launch time, passes `use_ultrasonic`,
converts URDF->SDF on the fly, and spawns with `-string`.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import (
    LaunchConfiguration,
    PathJoinSubstitution,
    Command,
    TextSubstitution,
)
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    # ---------- Launch args ----------
    entity_arg           = DeclareLaunchArgument('entity', default_value='andino', description='Robot entity name.')
    initial_pose_x_arg   = DeclareLaunchArgument('initial_pose_x', default_value='0.0')
    initial_pose_y_arg   = DeclareLaunchArgument('initial_pose_y', default_value='0.0')
    initial_pose_z_arg   = DeclareLaunchArgument('initial_pose_z', default_value='0.1')
    initial_pose_yaw_arg = DeclareLaunchArgument('initial_pose_yaw', default_value='0.0')
    robot_desc_topic_arg = DeclareLaunchArgument('robot_description_topic', default_value='robot_description')
    rsp_frequency_arg    = DeclareLaunchArgument('rsp_frequency', default_value='30.0')
    use_sim_time_arg     = DeclareLaunchArgument('use_sim_time', default_value='true')
    use_ultrasonic_arg   = DeclareLaunchArgument(
        'use_ultrasonic', default_value='True',
        description='Enable/disable ultrasonic sensor in xacro.'
    )

    # ---------- Launch configurations ----------
    entity           = LaunchConfiguration('entity')
    initial_pose_x   = LaunchConfiguration('initial_pose_x')
    initial_pose_y   = LaunchConfiguration('initial_pose_y')
    initial_pose_z   = LaunchConfiguration('initial_pose_z')
    initial_pose_yaw = LaunchConfiguration('initial_pose_yaw')
    robot_desc_topic = LaunchConfiguration('robot_description_topic')  # (kept for API compatibility)
    rsp_frequency    = LaunchConfiguration('rsp_frequency')
    use_sim_time     = LaunchConfiguration('use_sim_time')
    use_ultrasonic   = LaunchConfiguration('use_ultrasonic')

    # ---------- Paths ----------
    xacro_file = PathJoinSubstitution([
        FindPackageShare('andino_gz'), 'urdf', 'andino_gz.urdf.xacro'
    ])

    # ---------- xacro -> URDF (pass use_ultrasonic) ----------
    urdf_cmd = Command([
        'xacro', xacro_file,
        'use_fixed_caster:=false',
        'use_ultrasonic:=', use_ultrasonic
    ])

    # robot_state_publisher with the same URDF (force string type)
    rsp_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='both',
        parameters=[{
            'use_sim_time': use_sim_time,
            'publish_frequency': rsp_frequency,
            'robot_description': ParameterValue(urdf_cmd, value_type=str),
        }],
        remappings=[('/tf', 'tf'), ('/tf_static', 'tf_static')],
    )

    # ---------- URDF -> SDF then spawn with -string ----------
    sdf_cmd = Command(['gz', 'sdf', '-p', urdf_cmd])

    spawn_proc = ExecuteProcess(
        cmd=[
            'ros2', 'run', 'ros_gz_sim', 'create',
            '-name', entity,
            '-string', sdf_cmd,
            '-x', initial_pose_x,
            '-y', initial_pose_y,
            '-z', initial_pose_z,
            '-R', '0', '-P', '0',
            '-Y', initial_pose_yaw,
        ],
        output='screen'
    )

    return LaunchDescription([
        entity_arg, initial_pose_x_arg, initial_pose_y_arg, initial_pose_z_arg, initial_pose_yaw_arg,
        robot_desc_topic_arg, rsp_frequency_arg, use_sim_time_arg, use_ultrasonic_arg,
        rsp_node, spawn_proc
    ])
