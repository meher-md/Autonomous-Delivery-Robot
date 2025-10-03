from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='delivery_order',
            executable='order_node',
            name='delivery_order_node',
            output='screen',
            parameters=[{'waypoints_yaml': 'package://delivery_order/config/waypoints.yaml',
                         'image_topic': '/image_raw',
                         'qr_timeout_sec': 20.0}],
        )
    ])
