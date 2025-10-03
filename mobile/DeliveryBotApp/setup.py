from setuptools import setup

package_name = 'delivery_qr'

setup(
    name=package_name,
    version='0.0.1',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/srv', ['srv/GenerateQr.srv']),
    ],
    install_requires=['setuptools', 'qrcode[pil]'],
    zip_safe=True,
    maintainer='Your Name',
    maintainer_email='you@example.com',
    description='QR code generator service for delivery orders',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'qr_generator_node = delivery_qr.qr_generator_node:main',
        ],
    },
)
