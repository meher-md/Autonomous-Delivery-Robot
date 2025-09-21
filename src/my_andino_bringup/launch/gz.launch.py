from launch import LaunchDescription
from launch.actions import ExecuteProcess, TimerAction, SetEnvironmentVariable
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory
import os

def generate_launch_description():
    # مسار الحزمة وملفات URDF والميشات
    pkg_share = get_package_share_directory('my_andino_description')
    urdf_file = os.path.join(pkg_share, 'urdf', 'Delivery.urdf')
    meshes_path = os.path.join(pkg_share, 'meshes')

    return LaunchDescription([

        # إضافة مسار الميشات لـ Ignition Gazebo
        SetEnvironmentVariable(
            name='GAZEBO_MODEL_PATH',
            value=meshes_path
        ),

        # تشغيل Ignition Gazebo
        ExecuteProcess(
            cmd=['ign', 'gazebo', '-r', 'empty.sdf'],
            output='screen'
        ),

        # Spawn الروبوت بعد 3 ثواني للتأكد من جاهزية Gazebo
        TimerAction(
            period=3.0,
            actions=[
                ExecuteProcess(
                    cmd=['ros2', 'run', 'ros_ign_gazebo', 'create',
                         '-name', 'andino',
                         '-topic', '/robot_description'],
                    output='screen'
                )
            ]
        ),

        # تشغيل robot_state_publisher مع استخدام URDF من package://
        Node(
            package='robot_state_publisher',
            executable='robot_state_publisher',
            name='robot_state_publisher',
            output='screen',
            parameters=[{'use_sim_time': True, 'robot_description': open(urdf_file).read()}]
        ),

        # تشغيل RViz
        Node(
            package='rviz2',
            executable='rviz2',
            name='rviz2',
            output='screen'
        )
    ])
