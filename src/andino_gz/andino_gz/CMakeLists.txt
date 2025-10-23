set(CMAKE_SUPPRESS_DEVELOPER_WARNINGS 1 CACHE INTERNAL "No dev warnings")
cmake_minimum_required(VERSION 3.7)
project(andino_gz)

find_package(gazebo QUIET)
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

# If the Python package directory andino_gz/ contains __init__.py, keep this.
# If not, you can comment it out safely.
ament_python_install_package("andino_gz")

# Install shared resources
install(
  DIRECTORY
    config
    config_gui
    models
    launch
    maps
    rviz
    urdf
    worlds
  DESTINATION
    share/${PROJECT_NAME}/
)

# Environment hooks
ament_environment_hooks("${CMAKE_CURRENT_SOURCE_DIR}/env-hooks/${PROJECT_NAME}.dsv.in")
ament_environment_hooks("${CMAKE_CURRENT_SOURCE_DIR}/env-hooks/${PROJECT_NAME}.sh.in")

# Install Python executables (usable via `ros2 run andino_gz <file>.py`)
install(PROGRAMS
  scripts/goal_name.py
  scripts/go_menu.py
  scripts/app_goal_gateway.py
  DESTINATION lib/${PROJECT_NAME}
)

ament_package()

