from setuptools import setup
from glob import glob
import os

package_name = 'deliverybot_bringup'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],

    # ------------------------------------------------------------------
    # Files to install into share/<package> during colcon build install
    # ------------------------------------------------------------------
    data_files=[
        # Required for ament to index the package
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),

        # Install package.xml
        ('share/' + package_name, ['package.xml']),

        # Install launch files
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),

        # --------------------------------------------------------------
        # Install CERTIFICATES (NEW – makes SSL permanent & portable)
        # Copies cert.pem + key.pem into:
        #   install/<pkg>/share/<pkg>/certs/
        # --------------------------------------------------------------
        ('share/' + package_name + '/certs', [
            'certs/cert.pem',
            'certs/key.pem',
        ]),
    ],

    install_requires=['setuptools'],
    zip_safe=True,

    maintainer='mo',
    maintainer_email='mo@example.com',

    description='Bringup for DeliveryBot app (rosbridge + web_video + optional SLAM/Map HTTP)',
    license='Apache-2.0',

    tests_require=['pytest'],

    entry_points={
        'console_scripts': [],
    },
)

