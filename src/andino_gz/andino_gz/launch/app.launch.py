from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    port = LaunchConfiguration('port')
    address = LaunchConfiguration('address')

    return LaunchDescription([
        # باراميترز الاتصال
        DeclareLaunchArgument('port', default_value='9090'),
        DeclareLaunchArgument('address', default_value='127.0.0.1'),

        # rosbridge websocket
        Node(
            package='rosbridge_server',
            executable='rosbridge_websocket',
            name='rosbridge_websocket',
            output='screen',
            parameters=[{'port': port, 'address': address}],
        ),

        # rosapi (مفيد لاستكشاف التوبيكس/الـ types من الموبايل)
        Node(
            package='rosapi',
            executable='rosapi_node',
            name='rosapi',
            output='screen',
        ),
    ])
