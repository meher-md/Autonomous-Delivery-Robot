from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
import os

def generate_launch_description():
    rosbridge_port = LaunchConfiguration('rosbridge_port', default='9090')
    web_video_port = LaunchConfiguration('web_video_port', default='8080')
    start_slam     = LaunchConfiguration('start_slam', default='false')
    start_map_http = LaunchConfiguration('start_map_http', default='false')
    map_http_port  = LaunchConfiguration('map_http_port', default='8070')
    camera_topic   = LaunchConfiguration('camera_topic', default='/image_raw')

    rosbridge = Node(
        package='rosbridge_server',
        executable='rosbridge_websocket',
        name='rosbridge_websocket',
        parameters=[{'port': rosbridge_port}],
        output='screen'
    )

    web_video = Node(
        package='web_video_server',
        executable='web_video_server',
        name='web_video_server',
        parameters=[{'port': web_video_port}],
        output='screen'
    )

    #  SLAM Toolbox
    slam = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                os.environ.get('AMENT_PREFIX_PATH', '').split(':')[0],
                'share', 'slam_toolbox', 'launch', 'online_async_launch.py'
            )
        ),
        condition=IfCondition(start_slam)
    )

    # Map HTTP Bridge
    map_http = Node(
        package='map_http_bridge',
        executable='map_http_bridge',
        name='map_http_bridge',
        parameters=[{'port': map_http_port, 'topic': '/map'}],
        condition=IfCondition(start_map_http),
        output='screen'
    )

    return LaunchDescription([
        DeclareLaunchArgument('rosbridge_port', default_value='9090'),
        DeclareLaunchArgument('web_video_port', default_value='8080'),
        DeclareLaunchArgument('start_slam', default_value='false'),
        DeclareLaunchArgument('start_map_http', default_value='false'),
        DeclareLaunchArgument('map_http_port', default_value='8070'),
        DeclareLaunchArgument('camera_topic', default_value='/image_raw'),
        rosbridge,
        web_video,
        slam,
        map_http
    ])
