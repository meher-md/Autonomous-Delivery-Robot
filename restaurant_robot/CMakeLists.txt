cmake_minimum_required(VERSION 3.16)

project(restaurant_robot LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

option(RESTAURANT_ROBOT_ENABLE_CERES_SCAN_MATCHING "Build optional Ceres scan-matching SLAM backend" ON)
if(RESTAURANT_ROBOT_ENABLE_CERES_SCAN_MATCHING)
    find_package(Ceres QUIET)
endif()

option(RESTAURANT_ROBOT_ENABLE_MRPT_GRAPHSLAM "Detect MRPT graph-SLAM development packages" ON)
if(RESTAURANT_ROBOT_ENABLE_MRPT_GRAPHSLAM)
    find_package(MRPT QUIET COMPONENTS graphslam slam maps obs poses)
endif()

add_library(restaurant_robot_nav
    src/planning/occupancy_grid.cpp
    src/planning/inflation.cpp
    src/planning/astar.cpp
    src/planning/path_smoothing.cpp
    src/control/differential_drive.cpp
    src/control/pure_pursuit.cpp
    src/estimation/odometry.cpp
    src/estimation/localization.cpp
    src/obstacle/local_obstacle_map.cpp
    src/obstacle/dynamic_obstacle_detector.cpp
    src/safety/safety_supervisor.cpp
    src/mission/delivery_manager.cpp
    src/mapping/restaurant_map_factory.cpp
    src/mapping/map_io.cpp
    src/mapping/occupancy_ray_mapper.cpp
    src/mapping/slam_backend.cpp
    src/logging/run_logger.cpp
    src/navigation/navigator.cpp
    src/simulation/scenario_runner.cpp
)

if(Ceres_FOUND)
    target_sources(restaurant_robot_nav PRIVATE src/mapping/ceres_scan_match_backend.cpp)
    target_link_libraries(restaurant_robot_nav PUBLIC Ceres::ceres)
    target_compile_definitions(restaurant_robot_nav PUBLIC RESTAURANT_ROBOT_HAS_CERES=1)
endif()

if(MRPT_FOUND)
    message(STATUS "MRPT found; graph-SLAM backend integration hook is available for implementation.")
else()
    message(STATUS "MRPT graph-SLAM packages not found; mrpt_graphslam backend will report unavailable.")
endif()

target_include_directories(restaurant_robot_nav
    PUBLIC
        ${CMAKE_CURRENT_SOURCE_DIR}/include
)

target_compile_options(restaurant_robot_nav PRIVATE -Wall -Wextra -Wpedantic)

add_executable(restaurant_robot_tests
    tests/navigation_core_tests.cpp
)

target_link_libraries(restaurant_robot_tests PRIVATE restaurant_robot_nav)

add_executable(run_headless_scenario
    tools/run_headless_scenario.cpp
)

target_link_libraries(run_headless_scenario PRIVATE restaurant_robot_nav)

add_executable(generate_map_artifacts
    tools/generate_map_artifacts.cpp
)

target_link_libraries(generate_map_artifacts PRIVATE restaurant_robot_nav)

set(WEBOTS_HOME_DEFAULT "/usr/local/webots")
set(WEBOTS_HOME "$ENV{WEBOTS_HOME}" CACHE PATH "Path to Webots installation")
if(NOT WEBOTS_HOME)
    set(WEBOTS_HOME "${WEBOTS_HOME_DEFAULT}")
endif()

set(WEBOTS_CPP_INCLUDE "${WEBOTS_HOME}/include/controller/cpp")
set(WEBOTS_C_INCLUDE "${WEBOTS_HOME}/include/controller/c")
set(WEBOTS_CPP_LIBRARY "${WEBOTS_HOME}/lib/controller/libCppController.so")
set(WEBOTS_C_LIBRARY "${WEBOTS_HOME}/lib/controller/libController.so")

if(EXISTS "${WEBOTS_CPP_INCLUDE}/webots/Robot.hpp" AND
   EXISTS "${WEBOTS_CPP_LIBRARY}" AND
   EXISTS "${WEBOTS_C_LIBRARY}")
    add_executable(restaurant_delivery_controller
        simulator/controllers/restaurant_delivery_controller/main.cpp
    )
    target_compile_definitions(restaurant_delivery_controller PRIVATE WEBOTS_CONTROLLER)
    target_include_directories(restaurant_delivery_controller PRIVATE
        "${WEBOTS_CPP_INCLUDE}"
        "${WEBOTS_C_INCLUDE}"
    )
    target_link_libraries(restaurant_delivery_controller PRIVATE
        restaurant_robot_nav
        "${WEBOTS_CPP_LIBRARY}"
        "${WEBOTS_C_LIBRARY}"
    )
    set_target_properties(restaurant_delivery_controller PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/simulator/controllers/restaurant_delivery_controller"
        BUILD_RPATH "${WEBOTS_HOME}/lib/controller"
    )

    add_executable(restaurant_scenario_supervisor
        simulator/controllers/restaurant_scenario_supervisor/main.cpp
    )
    target_compile_definitions(restaurant_scenario_supervisor PRIVATE WEBOTS_CONTROLLER)
    target_include_directories(restaurant_scenario_supervisor PRIVATE
        "${WEBOTS_CPP_INCLUDE}"
        "${WEBOTS_C_INCLUDE}"
    )
    target_link_libraries(restaurant_scenario_supervisor PRIVATE
        "${WEBOTS_CPP_LIBRARY}"
        "${WEBOTS_C_LIBRARY}"
    )
    set_target_properties(restaurant_scenario_supervisor PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}/simulator/controllers/restaurant_scenario_supervisor"
        BUILD_RPATH "${WEBOTS_HOME}/lib/controller"
    )
endif()

enable_testing()
add_test(NAME restaurant_robot_tests COMMAND restaurant_robot_tests)

find_program(WEBOTS_EXECUTABLE webots)
if(WEBOTS_EXECUTABLE AND TARGET restaurant_delivery_controller AND TARGET restaurant_scenario_supervisor)
    add_test(
        NAME webots_person_crossing_smoke
        COMMAND bash -lc
            "SCENARIO=person_crossing MAX_TIME=4 timeout 10s ${WEBOTS_EXECUTABLE} --batch --no-rendering --mode=fast --stdout --stderr ${CMAKE_CURRENT_SOURCE_DIR}/simulator/worlds/restaurant_delivery.wbt"
    )
    set_tests_properties(webots_person_crossing_smoke PROPERTIES
        PASS_REGULAR_EXPRESSION "collision_count=0"
        TIMEOUT 15
    )
endif()
