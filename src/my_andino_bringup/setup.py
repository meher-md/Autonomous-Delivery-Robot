from setuptools import setup, find_packages

package_name = 'my_andino_bringup'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        # تسجيل الباكدج في ament_index
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        # ملف package.xml
        ('share/' + package_name, ['package.xml']),
        # تضمين ملف launch الجديد
        ('share/' + package_name + '/launch', [
            'launch/gz.launch.py',
        ]),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='mo',
    maintainer_email='mohamed.bn.nasser2001@gmail.com',
    description='Bringup package for Andino robot',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [],
    },
)
