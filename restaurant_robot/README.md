# Standalone Restaurant Delivery Robot Simulation

This branch implements the Webots-only navigation baseline from `PRD.md`. The code intentionally avoids ROS, ROS 2, Nav2, Gazebo, ROS TF, topics, services, actions, and launch files.

Current implemented slice:

- Lightweight internal navigation data structures.
- Hardware abstraction interface for Webots now and real robot hardware later.
- Occupancy grid with `0 = free`, `100 = occupied`, `255 = unknown`.
- Obstacle inflation, with planner clearance above the PRD's 0.30 m effective radius.
- 8-connected A* planner with no diagonal corner cutting.
- Line-of-sight waypoint simplification.
- Pure Pursuit controller.
- Differential-drive velocity conversion.
- Wheel encoder plus IMU-yaw odometry.
- Webots TurtleBot3 Burger extension slot with `LDS-01` LiDAR, `inertial unit`, and `imu gyro`.
- Scan-to-map localization boundary with a coarse LiDAR endpoint matcher for disturbance tests.
- Optional Ceres-backed scan-to-map mapping backend behind the same `ISlamBackend` boundary.
- Dynamic obstacle detection from LiDAR returns in mapped free space.
- Local obstacle map with timeout decay.
- Safety supervisor with normal, caution, stop, and emergency-stop states.
- Kitchen -> Table -> Home delivery mission manager.
- Navigator coordinator that ties mission goals, A*, Pure Pursuit, safety override, persistent-blockage timers, stuck detection, and replanning together.
- JSON/PGM occupancy-grid persistence and CSV run logging.
- Headless scenario runner for mission success, clearance, replanning, final accuracy, and collision metrics.
- Webots supervisor metrics with dynamic-obstacle clearance count and contact-point collision count.
- Webots Display debug view for occupancy map, LiDAR hits, dynamic hits, current path, Pure Pursuit target, active goal, robot pose, heading, safety zones, and safety state, with PNG snapshot export for automated runs.
- Prototype 9 m x 9 m restaurant map with kitchen, five table destinations, boundaries, table obstacles, chairs, and a corridor divider.

Build and test:

```bash
cmake -S . -B build
cmake --build build
ctest --test-dir build --output-on-failure
```

Run a headless mission metric check:

```bash
./build/restaurant_robot/run_headless_scenario TABLE_3
```

Generate occupancy-grid map artifacts:

```bash
./build/restaurant_robot/generate_map_artifacts build/restaurant_robot/generated_restaurant_map
./build/restaurant_robot/generate_map_artifacts build/restaurant_robot/ceres_generated_restaurant_map ceres_scan_match
bash restaurant_robot/scripts/run_webots_mapping.sh 10
SLAM_BACKEND=ceres_scan_match bash restaurant_robot/scripts/run_webots_mapping.sh 10
```

The default mapping backend is `known_pose`. When Ceres is available at configure time, `SLAM_BACKEND=ceres_scan_match` enables scan-to-current-map pose refinement before each LiDAR ray insertion. This is external-library scan matching, not graph SLAM or loop closure.

Manual Webots mapping:

```bash
bash restaurant_robot/scripts/run_webots_manual_mapping.sh
```

Controls in the Webots window are `W/A/S/D` or arrow keys to drive, `Space` to stop, `M` to save the current map checkpoint, and `Q` to quit the controller. The default output is `build/restaurant_robot/manual_restaurant_map.json` and `.pgm`. Manual mode does not save on exit unless `M` was pressed.

GUI control:

```bash
bash restaurant_robot/scripts/run_webots_gui_control.sh
```

This starts Webots and a small Tkinter control window using `build/restaurant_robot/control_command.txt` as the command bridge. The GUI can switch between `Auto` and `Manual`, choose `TABLE_1` through `TABLE_5`, drive manually, save a map checkpoint, emergency-stop, clear, or quit the robot controller. During manual mapping, the Webots `debug display` device shows the live LiDAR-built occupancy map; yellow points are current LiDAR hits and the grid updates as you drive.

Continue mapping from an earlier checkpoint:

```bash
MAP_INPUT_JSON=build/restaurant_robot/manual_restaurant_map.json bash restaurant_robot/scripts/run_webots_gui_control.sh
```

Navigate using a saved manual map:

```bash
MAP_INPUT_JSON=build/restaurant_robot/manual_restaurant_map.json bash restaurant_robot/scripts/run_webots_scenario.sh none 240
```

The saved map replaces the hand-coded occupancy grid, while the existing `HOME`, `KITCHEN`, and `TABLE_1` through `TABLE_5` goal labels remain available. In the Webots window, pressing number keys `1` through `5` changes the requested table live.

Run a Webots batch scenario:

```bash
bash restaurant_robot/scripts/run_webots_scenario.sh person_crossing 45
bash restaurant_robot/scripts/run_webots_scenario.sh stationary_blockage 18
bash restaurant_robot/scripts/run_webots_scenario.sh moving_crowd 45
bash restaurant_robot/scripts/run_webots_scenario.sh destination_change 45
bash restaurant_robot/scripts/run_webots_scenario.sh emergency_stop 8
bash restaurant_robot/scripts/run_webots_scenario.sh chair_moved 18
bash restaurant_robot/scripts/run_webots_scenario.sh blocked_corridor 18
bash restaurant_robot/scripts/run_webots_scenario.sh localization_disturbance 9
```

Export a debug display snapshot from a Webots batch run:

```bash
DEBUG_EXPORT_PATH=/tmp/restaurant_debug_snapshot.png bash restaurant_robot/scripts/run_webots_scenario.sh person_crossing 4
```

Run the current automated acceptance suite:

```bash
bash restaurant_robot/scripts/run_acceptance_suite.sh
```

Webots integration is being kept at the hardware boundary. The controller should read Webots LiDAR, encoders, and IMU through a `WebotsHardware` implementation, then call the same core library tested here.

Current acceptance progress is tracked in [docs/acceptance_progress.md](docs/acceptance_progress.md).
