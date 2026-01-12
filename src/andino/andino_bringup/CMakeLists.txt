cmake_minimum_required(VERSION 3.8)
project(andino_bringup)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY
    config
    launch
    rviz
  DESTINATION
    share/${PROJECT_NAME}
)

install(
  PROGRAMS
    scripts/range_to_laserscan.py
  DESTINATION
    lib/${PROJECT_NAME}
)

ament_package()
