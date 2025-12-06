from setuptools import setup
import os

package_name = 'map_info'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],  # this is the inner "map_info" folder
    data_files=[
        # Standard ament resource index entry
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),

        # Install package.xml so `ros2 pkg` can see the package
        ('share/' + package_name, ['package.xml']),

        # Install the default named poses YAML next to package.xml
        ('share/' + package_name, ['named_poses.yaml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='mo',
    maintainer_email='you@example.com',  # optional, put your email or leave as is
    description='Named pose tools for DeliveryBot (goal_name, go_menu, app_goal_gateway).',
    license='TODO',  # set your license if you want
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            # Expose these as `ros2 run map_info <name>`
            'goal_name = map_info.goal_name:main',
            'go_menu = map_info.go_menu:main',
            'app_goal_gateway = map_info.app_goal_gateway:main',
        ],
    },
)

