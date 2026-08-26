# Acceptance Progress

Current branch: `webots-sim`

Verified commands:

```bash
cmake -S . -B build
cmake --build build
./build/restaurant_robot/run_headless_scenario TABLE_3
./build/restaurant_robot/run_headless_scenario TABLE_1 3000
./build/restaurant_robot/run_headless_scenario TABLE_5 3000
./build/restaurant_robot/generate_map_artifacts build/restaurant_robot/generated_restaurant_map
./build/restaurant_robot/generate_map_artifacts build/restaurant_robot/ceres_generated_restaurant_map ceres_scan_match
bash restaurant_robot/scripts/run_webots_mapping.sh 8
SLAM_BACKEND=ceres_scan_match bash restaurant_robot/scripts/run_webots_mapping.sh 8
ctest --test-dir build --output-on-failure
bash restaurant_robot/scripts/run_webots_scenario.sh none 240
DEBUG_EXPORT_PATH=/tmp/restaurant_debug_snapshot.png bash restaurant_robot/scripts/run_webots_scenario.sh person_crossing 4
bash restaurant_robot/scripts/run_acceptance_suite.sh
```

Latest headless metric sample:

```text
scenario_goal=TABLE_3
mission_success=true
collision_count=0
replanning_events=0
minimum_obstacle_distance_m=6
final_goal_error_m=0.214464
final_pose_x=1.00789
final_pose_y=0.852681
final_pose_theta=-3.12086
elapsed_time_s=60.3
steps=603
```

Latest headless multiple-destination sample:

```text
TABLE_1 mission_success=true collision_count=0 final_goal_error_m=0.21408
TABLE_3 mission_success=true collision_count=0 final_goal_error_m=0.214464
TABLE_5 mission_success=true collision_count=0 final_goal_error_m=0.215472
```

Latest full Webots mission sample:

```text
scenario=none
mission_success=true
requested_destination=TABLE_3
final_home_error_m=0.218852
final_pose_x=0.982839
final_pose_y=0.920276
final_pose_theta=-2.89517
replanning_events=2
elapsed_time_s=105.088
collision_count=0
```

Webots smoke test:

```text
webots_person_crossing_smoke: passed
contact_collision_count=0
clearance_collision_count=0
collision_count=0
```

Latest generated map artifact sample:

```text
map_json=build/restaurant_robot/generated_restaurant_map.json
map_pgm=build/restaurant_robot/generated_restaurant_map.pgm
slam_backend=known_pose_ray_mapper
free_cells=26948
occupied_cells=442
unknown_cells=5010
```

Latest Ceres scan-match generated map artifact sample:

```text
map_json=build/restaurant_robot/ceres_generated_restaurant_map.json
map_pgm=build/restaurant_robot/ceres_generated_restaurant_map.pgm
slam_backend=ceres_scan_match_ray_mapper
free_cells=26215
occupied_cells=875
unknown_cells=5310
```

Latest Webots LiDAR mapping artifact sample:

```text
map_json=build/restaurant_robot/webots_generated_map.json
map_pgm=build/restaurant_robot/webots_generated_map.pgm
map_saved=true
```

Latest Webots Ceres LiDAR mapping sample:

```text
mapping_mode=true
slam_backend=ceres_scan_match_ray_mapper
map_json=/home/meher1087/delivery_robot_ws_clean/build/restaurant_robot/webots_generated_map.json
map_pgm=/home/meher1087/delivery_robot_ws_clean/build/restaurant_robot/webots_generated_map.pgm
map_saved=true
```

Latest debug visualization export sample:

```text
debug_snapshot=/tmp/restaurant_debug_snapshot_targeted.png
debug_snapshot_saved=true
/tmp/restaurant_debug_snapshot_targeted.png: PNG image data, 512 x 512, 8-bit/color RGBA, non-interlaced
```

Manual Webots scenario runs completed:

```bash
bash restaurant_robot/scripts/run_webots_scenario.sh person_crossing 12
bash restaurant_robot/scripts/run_webots_scenario.sh stationary_blockage 18
bash restaurant_robot/scripts/run_webots_scenario.sh chair_moved 18
bash restaurant_robot/scripts/run_webots_scenario.sh blocked_corridor 18
bash restaurant_robot/scripts/run_webots_scenario.sh moving_crowd 12
bash restaurant_robot/scripts/run_webots_scenario.sh destination_change 8
bash restaurant_robot/scripts/run_webots_scenario.sh emergency_stop 7
bash restaurant_robot/scripts/run_webots_scenario.sh localization_disturbance 9
bash restaurant_robot/scripts/run_webots_scenario.sh none 240
DEBUG_EXPORT_PATH=/tmp/restaurant_debug_snapshot.png bash restaurant_robot/scripts/run_webots_scenario.sh person_crossing 4
```

Observed Webots results:

| Scenario | Duration | Collision count | Navigation observation |
| --- | ---: | ---: | --- |
| person_crossing | 12 s | 0 | Robot entered CAUTION and reduced speed while proxy crossed near route. |
| stationary_blockage | 18 s | 0 | Robot stopped, persistent-blockage timer triggered replan events. |
| chair_moved | 18 s | 0 | Chair proxy moved into route; robot stopped and recorded replan events. |
| blocked_corridor | 18 s | 0 | Corridor proxy group blocked route; robot stopped and recorded replan events. |
| moving_crowd | 12 s | 0 | Robot maintained normal/caution behavior with no collision. |
| destination_change | 8 s | 0 | Requested destination started as TABLE_2 and switched to TABLE_4 at t=6.048 s. |
| emergency_stop | 7 s | 0 | ESTOP at t=4.0 s produced v=0 and w=0 at t=4.032 s with EMERGENCY_STOP state. |
| localization_disturbance | 9 s | 0 | Disturbed odometry was corrected so estimated pose ended closer to supervisor ground truth. |
| none | 240 s | 0 | Full Kitchen -> TABLE_3 -> Home Webots mission completed at t=105.088 s. |

Scenario supervisor metrics now log:

```text
timestamp,scenario,robot_x,robot_y,min_dynamic_clearance,collision_count,clearance_collision_count,contact_collision_count,contact_point_count
```

`collision_count` is the combined scenario count from dynamic-obstacle clearance violations and Webots contact points above the floor-contact band.

Implemented PRD coverage:

- Webots world with restaurant boundaries, kitchen, five tables, corridor divider, and dynamic proxies.
- TurtleBot3 Burger with 2D LiDAR, wheel encoders, inertial unit, and gyro.
- Direct Webots C++ controller API, no ROS/ROS 2/Nav2/Gazebo messaging.
- Hardware abstraction, odometry, scan-map localization boundary, occupancy grid, inflation, A*, path simplification, Pure Pursuit, dynamic obstacle map, safety supervisor, replanning, and mission FSM.
- CSV telemetry for robot run and supervisor scenario metrics.
- Headless and Webots smoke tests.
- Runtime mission command path through `GOAL_TABLE` and Webots `customData` for destination changes.
- Runtime emergency stop through Webots `customData`, verified to zero motion in the next control cycle.
- Webots Display debug visualization for static occupancy map, LiDAR hit points, dynamic hits in mapped free space, active path, Pure Pursuit target, goal, pose, heading, safety region, and safety state.
- Webots Display debug visualization PNG export through `DEBUG_EXPORT_PATH`, covered by the automated acceptance suite.
- Automated acceptance script covering core tests, headless TABLE_1/TABLE_3/TABLE_5, person crossing, debug snapshot export, stationary blockage, chair moved into route, blocked corridor, moving crowd, destination change, emergency stop, and localization disturbance.
- Full empty Webots Kitchen -> TABLE_3 -> Home mission, verified with zero collisions and final home error under 0.22 m.
- Occupancy ray-mapping backend and map artifact generator producing `restaurant_map.json`/`.pgm` style outputs from LiDAR scans and known pose.
- Webots `OPERATING_MODE=MAPPING` path that saves map artifacts from actual simulated LiDAR scans.
- `ISlamBackend` interface with a default known-pose mapper and optional Ceres scan-to-current-map backend.

Remaining PRD gaps:

- Full graph-SLAM or loop-closure integration. The optional Ceres backend performs external-library scan matching against the current map, but it is not a pose graph SLAM system.
- Additional long-duration Webots mission permutations beyond the default TABLE_3 run can be added to the automated suite.
- Debug visualization export currently produces PNG snapshots; video export is not automated.
