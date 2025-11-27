from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    # ---------- Launch args ----------
    rosbridge_port = LaunchConfiguration('rosbridge_port', default='9090')
    web_video_port = LaunchConfiguration('web_video_port', default='8080')
    start_slam     = LaunchConfiguration('start_slam', default='false')
    start_map_http = LaunchConfiguration('start_map_http', default='false')
    map_http_port  = LaunchConfiguration('map_http_port', default='8070')
    camera_topic   = LaunchConfiguration('camera_topic', default='/image_raw')

    # app_goal_gateway params
    pkg_share    = get_package_share_directory('andino_gz')
    default_yaml = os.path.join(pkg_share, 'config', 'named_poses.yaml')
    yaml_path    = LaunchConfiguration('yaml_path', default=default_yaml)
    frame_id     = LaunchConfiguration('frame_id', default='map')
    topic_goal_name   = LaunchConfiguration('topic_goal_name', default='/app/goal_name')
    topic_goal_cancel = LaunchConfiguration('topic_goal_cancel', default='/app/goal_cancel')
    topic_status      = LaunchConfiguration('topic_status', default='/app/goal_status')
    server_timeout    = LaunchConfiguration('server_timeout', default='8.0')
    fuzzy_cutoff      = LaunchConfiguration('fuzzy_cutoff', default='0.7')

    # ---------- Nodes ----------
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

    # app_goal_gateway: listens to /app/goal_name and sends Nav2 NavigateToPose
    app_goal_gateway = Node(
        package='andino_gz',
        executable='app_goal_gateway.py',
        name='app_goal_gateway',
        parameters=[{
            'yaml_path': yaml_path,
            'frame_id': frame_id,
            'topic_goal_name': topic_goal_name,
            'topic_goal_cancel': topic_goal_cancel,
            'topic_status': topic_status,
            'server_timeout': server_timeout,
            'fuzzy_cutoff': fuzzy_cutoff
        }],
        output='screen'
    )

    # Start QR generator + scanner (generate QR PNGs and scan via Pi camera)
    qr_generator = Node(package='qr_verification', executable='qr_generator', name='qr_generator')
    qr_scanner = Node(package='qr_verification', executable='qr_scanner', name='qr_scanner')

    # ---------- LaunchDescription ----------
    return LaunchDescription([
        # existing args
        DeclareLaunchArgument('rosbridge_port', default_value='9090'),
        DeclareLaunchArgument('web_video_port', default_value='8080'),
        DeclareLaunchArgument('start_slam', default_value='false'),
        DeclareLaunchArgument('start_map_http', default_value='false'),
        DeclareLaunchArgument('map_http_port', default_value='8070'),
        DeclareLaunchArgument('camera_topic', default_value='/image_raw'),

        # gateway args
        DeclareLaunchArgument('yaml_path', default_value=default_yaml),
        DeclareLaunchArgument('frame_id', default_value='map'),
        DeclareLaunchArgument('topic_goal_name', default_value='/app/goal_name'),
        DeclareLaunchArgument('topic_goal_cancel', default_value='/app/goal_cancel'),
        DeclareLaunchArgument('topic_status', default_value='/app/goal_status'),
        DeclareLaunchArgument('server_timeout', default_value='8.0'),
        DeclareLaunchArgument('fuzzy_cutoff', default_value='0.7'),

        rosbridge,
        web_video,
        slam,
        map_http,
        app_goal_gateway,
        qr_generator,
        qr_scanner
    ])
