from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(package='andino_mobile_bridge', executable='mobile_bridge', name='mobile_bridge'),
        Node(package='andino_mobile_bridge', executable='topic_monitor', name='topic_monitor'),
        Node(package='andino_mobile_bridge', executable='phone_qr_sender', name='phone_qr_sender'),
        # NEW: QR generator + scanner
        Node(package='andino_mobile_bridge', executable='qr_generator', name='qr_generator'),
        Node(package='andino_mobile_bridge', executable='qr_scanner', name='qr_scanner'),
    ])
