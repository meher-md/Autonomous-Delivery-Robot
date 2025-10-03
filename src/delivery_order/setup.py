from setuptools import setup

package_name = 'delivery_order'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/delivery_order.launch.py']),
        ('share/' + package_name + '/config', ['config/waypoints.yaml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Your Name',
    maintainer_email='you@example.com',
    description='Navigate to order address and verify QR from camera',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'order_node = delivery_order.order_node:main',
        ],
    },
)
