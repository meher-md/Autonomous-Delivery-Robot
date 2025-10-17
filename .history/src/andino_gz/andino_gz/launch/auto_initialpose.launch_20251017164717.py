from launch import LaunchDescription
from launch.actions import TimerAction
from launch_ros.actions import Node

def generate_launch_description():
    # Node that publishes the initial pose
    initial_pose_pub = Node(
        package='ros2topic',
        executable='ros2topic',
        name='initialpose_publisher',
        arguments=[
            'pub', '--once', '/initialpose', 'geometry_msgs/PoseWithCovarianceStamped',
            '{header: {frame_id: map}, '
            'pose: {pose: {position: {x: 0.0, y: 0.0, z: 0.0}, '
            'orientation: {z: 0.0, w: 1.0}}, '
            'covariance: [0.25, 0, 0, 0, 0, 0, '
            '0, 0.25, 0, 0, 0, 0, '
            '0, 0, 0.0685, 0, 0, 0, '
            '0, 0, 0, 0.0685, 0, 0, '
            '0, 0, 0, 0, 0.0685, 0, '
            '0, 0, 0, 0, 0, 0.05]}'
        ],
        output='screen'
    )

    # Wait 6 seconds after launch before publishing (to let AMCL become active)
    delayed_initial_pose = TimerAction(
        period=6.0,
        actions=[initial_pose_pub]
    )

    return LaunchDescription([delayed_initial_pose])
