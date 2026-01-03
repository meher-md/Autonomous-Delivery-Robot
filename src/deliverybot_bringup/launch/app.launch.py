from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare
from ament_index_python.packages import get_package_share_directory
import os


def generate_launch_description():
    # ---------- Launch args: generic app settings ----------
    # Websocket / video / map HTTP ports and basic flags
    rosbridge_port = LaunchConfiguration('rosbridge_port', default='9090')
    web_video_port = LaunchConfiguration('web_video_port', default='8080')
    start_slam     = LaunchConfiguration('start_slam', default='false')
    start_map_http = LaunchConfiguration('start_map_http', default='false')
    map_http_port  = LaunchConfiguration('map_http_port', default='8070')
    camera_topic   = LaunchConfiguration('camera_topic', default='/camera/image_raw/compressed')

    # ---------- SSL params for rosbridge ----------
    # Default: SSL enabled (wss://) using certs shipped inside the package
    # This makes the setup portable across machines (no hard-coded /home/user paths).
    pkg_share_deliverybot = FindPackageShare('deliverybot_bringup')

    rosbridge_ssl = LaunchConfiguration('rosbridge_ssl', default='true')

    rosbridge_certfile = LaunchConfiguration(
        'rosbridge_certfile',
        default=PathJoinSubstitution([
            pkg_share_deliverybot, 'certs', 'cert.pem'
        ])
    )

    rosbridge_keyfile = LaunchConfiguration(
        'rosbridge_keyfile',
        default=PathJoinSubstitution([
            pkg_share_deliverybot, 'certs', 'key.pem'
        ])
    )

    # ---------- app_goal_gateway params ----------
    # Use map_info package for named poses instead of andino_gz
    pkg_share_map_info = get_package_share_directory('map_info')

    # YAML is installed into the share/map_info directory
    default_yaml = os.path.join(pkg_share_map_info, 'named_poses.yaml')
    yaml_path           = LaunchConfiguration('yaml_path', default=default_yaml)
    frame_id            = LaunchConfiguration('frame_id', default='map')
    topic_goal_name     = LaunchConfiguration('topic_goal_name', default='/app/goal_name')
    topic_goal_cancel = LaunchConfiguration('topic_goal_cancel', default='/app/goal_cancel')
    topic_status      = LaunchConfiguration('topic_status', default='/app/goal_status')
    server_timeout    = LaunchConfiguration('server_timeout', default='8.0')
    fuzzy_cutoff      = LaunchConfiguration('fuzzy_cutoff', default='0.7')

    # ---------- Nodes ----------

    # WebSocket bridge for external apps (e.g. Android app / web UI).
    # Exposes ROS topics/services/actions over rosbridge protocol (JSON over WebSocket).
    rosbridge = Node(
        package='rosbridge_server',
        executable='rosbridge_websocket',
        name='rosbridge_websocket',
        parameters=[{
            'port': rosbridge_port,
            'ssl': rosbridge_ssl,
            'certfile': rosbridge_certfile,
            'keyfile': rosbridge_keyfile,
        }],
        output='screen'
    )

    # Web video server for streaming camera images via HTTP (e.g. /stream?topic=/image_raw).
    web_video = Node(
        package='web_video_server',
        executable='web_video_server',
        name='web_video_server',
        parameters=[{
            'port': web_video_port,
            'default_transport': 'compressed'
        }],
        output='screen'
    )

    # SLAM Toolbox (optional): used for online mapping when start_slam:=true
    slam = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(
                os.environ.get('AMENT_PREFIX_PATH', '').split(':')[0],
                'share', 'slam_toolbox', 'launch', 'online_async_launch.py'
            )
        ),
        condition=IfCondition(start_slam)
    )

    # Map HTTP Bridge (optional): exposes /map over HTTP for debugging / visualization.
    map_http = Node(
        package='map_http_bridge',
        executable='map_http_bridge',
        name='map_http_bridge',
        parameters=[{'port': map_http_port, 'topic': '/map'}],
        condition=IfCondition(start_map_http),
        output='screen'
    )

    # app_goal_gateway: listens to /app/goal_name and sends Nav2 NavigateToPose goals.
    # Uses fuzzy matching on named poses from named_poses.yaml.
    app_goal_gateway = Node(
        package='map_info',              # new package providing the gateway
        executable='app_goal_gateway',    # console_script entry point (no .py)
        name='app_goal_gateway',
        parameters=[{
            'yaml_path': yaml_path,
            'frame_id': frame_id,
            'topic_goal_name': topic_goal_name,
            'topic_goal_cancel': topic_goal_cancel,
            'topic_status': topic_status,
            'server_timeout': server_timeout,
            'fuzzy_cutoff': fuzzy_cutoff,
        }],
        output='screen'
    )

    # Start QR generator + scanner (generate QR PNGs and scan via camera).
    # Used for order verification / delivery confirmation.
    qr_generator = Node(
        package='qr_verification',
        executable='qr_generator',
        name='qr_generator'
    )

    qr_scanner = Node(
        package='qr_verification',
        executable='qr_scanner',
        name='qr_scanner'
    )

    # NEW: YOLO Like Detector Node
    like_detector = Node(
        package='yolo_like_detector',       # اسم حزمة YOLO
        executable='like_detector_node',    # اسم executable (كما في like_detector.py)
        name='like_detector_node',
        output='screen'
    )

    # ---------- LaunchDescription ----------
    # All launch arguments + nodes are registered here.
    return LaunchDescription([
        # Generic app arguments
        DeclareLaunchArgument('rosbridge_port', default_value='9090'),
        DeclareLaunchArgument('web_video_port', default_value='8080'),
        DeclareLaunchArgument('start_slam', default_value='false'),
        DeclareLaunchArgument('start_map_http', default_value='false'),
        DeclareLaunchArgument('map_http_port', default_value='8070'),
        DeclareLaunchArgument('camera_topic', default_value='/image_raw/compressed'),

        # SSL args for rosbridge (portable defaults using package-relative paths)
        DeclareLaunchArgument('rosbridge_ssl', default_value='true'),
        DeclareLaunchArgument(
            'rosbridge_certfile',
            default_value=PathJoinSubstitution([
                pkg_share_deliverybot, 'certs', 'cert.pem'
            ])
        ),
        DeclareLaunchArgument(
            'rosbridge_keyfile',
            default_value=PathJoinSubstitution([
                pkg_share_deliverybot, 'certs', 'key.pem'
            ])
        ),

        # Gateway / navigation args
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
        qr_scanner,
        like_detector
    ])
