#!/usr/bin/env python3

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch_ros.actions import Node
from launch.substitutions import LaunchConfiguration

from nav2_common.launch import ReplaceString


def generate_launch_description():
    pkg_andino_gz = get_package_share_directory('andino_gz')
    bridge_config_file_path = os.path.join(pkg_andino_gz, 'config', 'bridge_config.yaml')

    # Arguments
    entity_arg = DeclareLaunchArgument(
        'entity', default_value='andino',
        description='Name of the entity to bridge with Gazebo.'
    )
    use_ultrasonic_arg = DeclareLaunchArgument(
        'use_ultrasonic', default_value='True',
        description='Enable/disable ultrasonic LaserScan bridge on /ultrasonic/scan.'
    )

    entity = LaunchConfiguration('entity')
    use_ultrasonic = LaunchConfiguration('use_ultrasonic')

    # Replace <entity> placeholder in the bridge config
    bridge_config = ReplaceString(
        source_file=bridge_config_file_path,
        replacements={'<entity>': entity},
    )

    # Main bridge using the YAML config
    bridge_node = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        output='screen',
        parameters=[{'config_file': bridge_config}],
    )

    # Optional: explicit ultrasonic bridge (single-beam LaserScan from gz)
    ultrasonic_bridge_node = Node(
        condition=IfCondition(use_ultrasonic),
        package='ros_gz_bridge',
        executable='parameter_bridge',
        output='screen',
        arguments=[
            '/ultrasonic/scan@sensor_msgs/msg/LaserScan@gz.msgs.LaserScan'
        ],
    )

    return LaunchDescription([
        entity_arg,
        use_ultrasonic_arg,
        bridge_node,
        ultrasonic_bridge_node,
    ])
