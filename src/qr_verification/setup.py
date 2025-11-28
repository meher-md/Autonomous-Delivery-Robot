from setuptools import find_packages, setup

package_name = 'qr_verification'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Jack',
    maintainer_email='jack@you.com',
    description='QR Verification Package that generates and scans a QR Code',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'qr_generator = qr_verification.qr_generator:main',
            'qr_scanner = qr_verification.qr_scanner:main',
            'monitor_qr_scanner = qr_verification.monitor_qr_scanner:main',
        ],
    },
)
