from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(package='andino_mobile_bridge', executable='mobile_bridge', name='mobile_bridge')
    ])
