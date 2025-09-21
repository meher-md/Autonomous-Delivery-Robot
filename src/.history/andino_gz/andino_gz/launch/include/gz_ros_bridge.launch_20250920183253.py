#!/usr/bin/env python3

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution, Command, TextSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    # ---- Args (including ultrasonic)
    entity_arg            = DeclareLaunchArgument('entity', default_value='andino', description='Entity name')
    initial_pose_x_arg    = DeclareLaunchArgument('initial_pose_x', default_value='0.0')
    initial_pose_y_arg    = DeclareLaunchArgument('initial_pose_y', default_value='0.0')
    initial_pose_z_arg    = DeclareLaunchArgument('initial_pose_z', default_value='0.1')
    initial_pose_yaw_arg  = DeclareLaunchArgument('initial_pose_yaw', default_value='0.0')
    robot_desc_topic_arg  = DeclareLaunchArgument('robot_description_topic', default_value='robot_description')
    use_sim_time_arg      = DeclareLaunchArgument('use_sim_time', default_value='true')
    # NEW: accept toggle from parent
    use_ultrasonic_arg    = DeclareLaunchArgument('use_ultrasonic', default_value='True',
                               description='Enable/disable ultrasonic sensor in xacro.')

    # ---- LaunchConfigurations
    entity           = LaunchConfiguration('entity')
    initial_pose_x   = LaunchConfiguration('initial_pose_x')
    initial_pose_y   = LaunchConfiguration('initial_pose_y')
    initial_pose_z   = LaunchConfiguration('initial_pose_z')
    initial_pose_yaw = LaunchConfiguration('initial_pose_yaw')
    robot_desc_topic = LaunchConfiguration('robot_description_topic')
    use_sim_time     = LaunchConfiguration('use_sim_time')
    use_ultrasonic   = LaunchConfiguration('use_ultrasonic')

    # ---- Paths
    andino_desc_share = FindPackageShare('andino_description')
    xacro_file = PathJoinSubstitution([andino_desc_share, 'urdf', 'andino.urdf.xacro'])

    # ---- xacro -> URDF (pass use_ultrasonic)
    urdf_cmd = Command([
        'xacro ', xacro_file,
        ' use_ultrasonic:=', use_ultrasonic
    ])

    # ---- robot_state_publisher with the same URDF
    rsp_node = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name=[entity, TextSubstitution(text='_rsp')],
        output='screen',
        parameters=[{
            'robot_description': urdf_cmd,
            'use_sim_time': use_sim_time
        }],
        remappings=[('robot_description', robot_desc_topic)]
    )

    # ---- URDF -> SDF, then spawn into gz sim (use -string)
    sdf_cmd = Command(['gz sdf -p ', urdf_cmd])

    spawn_proc = ExecuteProcess(
        cmd=[
            'ros2', 'run', 'ros_gz_sim', 'create',
            '-name', entity,
            '-string', sdf_cmd,
            '-x', initial_pose_x,
            '-y', initial_pose_y,
            '-z', initial_pose_z,
            '-Y', initial_pose_yaw,
        ],
        output='screen'
    )

    return LaunchDescription([
        entity_arg, initial_pose_x_arg, initial_pose_y_arg, initial_pose_z_arg, initial_pose_yaw_arg,
        robot_desc_topic_arg, use_sim_time_arg, use_ultrasonic_arg,
        rsp_node, spawn_proc
    ])
