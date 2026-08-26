
# Product Requirements Document

## 1. Product Name

**Standalone Restaurant Delivery Robot Navigation Simulation**

---

## 2. Objective

Develop a fully autonomous restaurant-delivery mobile robot simulation in **Webots** without ROS, ROS 2, Nav2, Gazebo, or ROS messaging.

The system shall demonstrate that a differential-drive robot equipped with:

* 2D LiDAR
* wheel encoders
* IMU

can autonomously:

1. create or load a restaurant map,
2. estimate its position,
3. receive a destination such as Table 1 or Table 5,
4. calculate a route,
5. follow the route,
6. detect people and other dynamic obstacles,
7. slow down or stop safely,
8. replan when the route remains blocked,
9. reach the destination,
10. return to the kitchen/home position.

The software architecture must remain sufficiently modular so that the same navigation software can later be connected to the physical restaurant-delivery robot.

---

# 3. Core Design Philosophy

The project shall intentionally avoid large robotics frameworks.

The navigation pipeline shall be:

**Webots Sensors
→ SLAM / Localization
→ Occupancy Grid
→ A* Global Planner
→ Pure Pursuit Path Tracker
→ Dynamic Obstacle Detection
→ Safety Supervisor
→ Replanning
→ Differential-Drive Controller**

The system shall use standalone algorithms and libraries only where useful.

Custom implementation is preferred for simple algorithms.

External libraries shall primarily be used for computationally difficult functionality such as:

* SLAM
* scan matching
* localization

---

# 4. Explicitly Out of Scope

The first version shall NOT use:

* ROS
* ROS 2
* Nav2
* Gazebo
* Behavior Trees
* ROS TF
* ROS topics
* ROS services
* ROS actions
* ROS launch files
* ROS parameter servers
* Nav2 costmaps
* Nav2 planner server
* Nav2 controller server
* Nav2 lifecycle manager
* fleet management
* cloud connectivity
* mobile application
* computer vision
* semantic person recognition
* machine learning-based navigation

These features may be introduced later if genuinely required.

---

# 5. Simulation Platform

## 5.1 Simulator

**Webots**

The simulator shall provide:

* robot physics,
* wheel-ground interaction,
* differential-drive motors,
* LiDAR simulation,
* encoder simulation,
* IMU simulation,
* collision physics,
* restaurant environment,
* dynamic pedestrians,
* tables,
* walls,
* chairs,
* kitchen area.

Webots supports its own robot Controller API, so ROS is not required for controlling the simulation. Webots also provides reusable PROTO robot models, including TurtleBot3 Burger.

---

# 6. Baseline Robot

## 6.1 Selected Robot

**TurtleBot3 Burger**

Use the stock Webots model initially.

Reason:

* differential-drive architecture,
* compact indoor robot,
* 360° LiDAR,
* wheel motors,
* encoder-capable wheel joints,
* inertial sensing,
* well-established simulation model,
* structurally similar to the intended restaurant robot from a navigation perspective.

A commonly used Webots TurtleBot3 configuration includes a 360° Robotis LDS-01 LiDAR and IMU sensing.

The physical geometry of the final restaurant robot is NOT required in Phase 1.

---

# 7. Required Simulated Sensors

## 7.1 2D LiDAR

Required output:

```text
range[0 ... N-1]
angle_min
angle_max
angular_resolution
maximum_range
timestamp
```

Purpose:

* mapping,
* localization,
* obstacle detection,
* safety stopping,
* dynamic obstacle detection.

Recommended simulated scan:

**360° horizontal field of view**

---

## 7.2 Wheel Encoders

Required measurements:

```text
left_wheel_angle
right_wheel_angle
```

Derived quantities:

```text
left_wheel_velocity
right_wheel_velocity
robot_linear_displacement
robot_heading_change
```

Wheel odometry shall estimate:

```text
x
y
theta
```

---

# 8. Differential-Drive Kinematics

For wheel velocities:

```text
vL = left wheel linear velocity
vR = right wheel linear velocity
L = wheel separation
```

Robot velocity:

```text
v = (vR + vL) / 2
```

Angular velocity:

```text
ω = (vR - vL) / L
```

Wheel commands:

```text
vR = v + ωL/2

vL = v - ωL/2
```

This interface shall later allow the simulated motors to be replaced by the actual robot motor controller.

---

# 9. IMU

Required measurements:

```text
yaw
yaw_rate
angular_velocity
optional acceleration
```

Purpose:

* improve heading estimation,
* compensate encoder drift,
* stabilize odometry.

The first implementation may use:

**wheel odometry + IMU yaw fusion**

rather than implementing a sophisticated sensor fusion system.

---

# 10. Software Architecture

The proposed application architecture is:

```text
┌────────────────────────────┐
│          WEBOTS            │
│                            │
│ LiDAR   Encoders   IMU     │
│ Motors                     │
└─────────────┬──────────────┘
              │
              ▼
┌────────────────────────────┐
│ Sensor Interface           │
└─────────────┬──────────────┘
              │
              ▼
┌────────────────────────────┐
│ Odometry / Pose Estimator  │
└─────────────┬──────────────┘
              │
              ▼
┌────────────────────────────┐
│ SLAM / Localization        │
└─────────────┬──────────────┘
              │
        Pose + Map
              │
              ▼
┌────────────────────────────┐
│ A* Global Planner          │
└─────────────┬──────────────┘
              │
            Path
              │
              ▼
┌────────────────────────────┐
│ Pure Pursuit Controller    │
└─────────────┬──────────────┘
              │
            v, ω
              │
              ▼
┌────────────────────────────┐
│ Dynamic Obstacle Layer     │
└─────────────┬──────────────┘
              │
              ▼
┌────────────────────────────┐
│ Safety Supervisor          │
└─────────────┬──────────────┘
              │
              ▼
┌────────────────────────────┐
│ Wheel Velocity Controller  │
└─────────────┬──────────────┘
              │
              ▼
          WEBOTS MOTORS
```

---

# 11. Internal Data Structures

ROS message formats shall NOT be used.

Create lightweight internal structures.

Example:

```cpp
struct Pose2D {
    double x;
    double y;
    double theta;
};
```

```cpp
struct LaserScan {
    std::vector<double> ranges;
    double angle_min;
    double angle_increment;
    double max_range;
};
```

```cpp
struct VelocityCommand {
    double linear;
    double angular;
};
```

```cpp
struct Point2D {
    double x;
    double y;
};
```

```cpp
struct Path {
    std::vector<Point2D> points;
};
```

```cpp
struct OccupancyGrid {
    int width;
    int height;
    double resolution;
    Point2D origin;
    std::vector<uint8_t> cells;
};
```

This abstraction is important because later:

```text
WebotsSensorInterface
```

can simply be replaced by:

```text
RealRobotSensorInterface
```

without changing the planner or controller.

---

# 12. Navigation Operating Modes

The robot shall support four principal operating states.

```text
MAPPING
LOCALIZATION
NAVIGATION
DELIVERY
```

---

# 13. Mapping Mode

## 13.1 Objective

Generate a 2D occupancy-grid map of the restaurant.

The robot may initially be:

* manually driven,
* keyboard controlled,
* or commanded through predetermined exploration points.

SLAM produces:

```text
robot pose
+
occupancy grid
```

The final map shall be saved.

Example:

```text
restaurant_map.bin
restaurant_map.png
restaurant_map.json
```

---

# 14. Standalone SLAM Requirement

Do NOT implement SLAM from scratch.

The project shall investigate and integrate an appropriate standalone 2D SLAM library.

Candidate algorithm families include:

* scan-matching SLAM,
* particle-filter SLAM,
* graph-based 2D SLAM.

Selection criteria:

| Requirement              |  Priority |
| ------------------------ | --------: |
| Runs without ROS         | Mandatory |
| C++ integration          |      High |
| Supports 2D LiDAR        | Mandatory |
| Provides occupancy map   | Mandatory |
| Provides robot pose      | Mandatory |
| Lightweight dependencies |      High |
| Active/maintainable code |      High |
| Easy Webots integration  |      High |

---

# 15. Map Representation

Use standard occupancy values:

```text
0   = free
100 = occupied
255 = unknown
```

Recommended initial resolution:

**0.05 m/cell**

Example:

```text
20 m × 20 m restaurant
```

would result in:

```text
400 × 400 cells
```

which is computationally trivial for A*.

---

# 16. Localization Mode

After the restaurant map has been created, normal operation should NOT continuously rebuild the map.

Normal operation:

```text
Saved Map
+
LiDAR
+
Wheel Odometry
+
IMU
        ↓
Localization
        ↓
x, y, theta
```

Required pose accuracy for simulation target:

**≤ approximately 10 cm positional error**

and:

**≤ approximately 5° heading error**

under normal operating conditions.

These are prototype engineering targets, not safety certification requirements.

---

# 17. Restaurant Environment

The simulated restaurant shall contain:

* kitchen,
* serving/loading station,
* dining area,
* tables,
* chairs,
* walls,
* corridors,
* customer movement space,
* robot home position.

Minimum destination set:

```text
HOME
KITCHEN
TABLE_1
TABLE_2
TABLE_3
TABLE_4
TABLE_5
```

Each destination shall correspond to:

```text
x
y
theta
```

Example:

```text
TABLE_3 = {4.25, 2.10, 1.57}
```

---

# 18. Global Planner

## Algorithm

**A***

Input:

```text
OccupancyGrid
start pose
destination
```

Output:

```text
collision-free grid path
```

---

# 19. Obstacle Inflation

A* must NOT plan directly beside walls.

Occupancy cells shall be inflated according to robot radius.

Example:

```text
Robot radius          = 0.18 m
Safety allowance      = 0.12 m
Effective radius      = 0.30 m
```

Every occupied map cell shall therefore produce approximately a:

**0.30 m exclusion region.**

This prevents the center of the robot from being routed too close to tables or walls.

---

# 20. A* Cost Function

Standard:

```text
f(n) = g(n) + h(n)
```

where:

```text
g(n) = path cost
h(n) = heuristic distance to goal
```

Euclidean or octile-distance heuristic may be used.

8-connected movement is preferred.

---

# 21. Path Simplification

Raw A* paths may contain hundreds of grid points.

Therefore:

```text
A* path
    ↓
Line-of-sight simplification
    ↓
Waypoint reduction
    ↓
Optional smoothing
```

Example:

```text
300 grid cells
↓
15 useful waypoints
```

This improves Pure Pursuit performance.

---

# 22. Path Tracker

## Algorithm

**Pure Pursuit**

Input:

```text
robot pose
planned path
look-ahead distance
```

Output:

```text
linear velocity v
angular velocity ω
```

---

# 23. Pure Pursuit Look-Ahead

Initial value:

```text
0.3 – 0.6 m
```

Later use velocity-dependent look-ahead:

```text
Ld = Lmin + k × velocity
```

so:

* low speed → small look-ahead,
* high speed → larger look-ahead.

---

# 24. Velocity Limits

Initial restaurant speeds:

```text
Maximum normal velocity:
0.4 m/s
```

Near people:

```text
0.15–0.25 m/s
```

Approaching destination:

```text
0.10–0.15 m/s
```

Emergency/safety state:

```text
0 m/s
```

These are prototype simulation parameters and shall remain configurable.

---

# 25. Dynamic Obstacle Detection

Dynamic obstacles include:

* people,
* chairs moved into route,
* carts,
* boxes,
* other robots.

The system does NOT initially need to classify them.

Anything detected by LiDAR in free mapped space may be treated as a temporary obstacle.

Therefore:

```text
Static map says FREE
+
LiDAR says OCCUPIED
=
Dynamic obstacle
```

---

# 26. Local Obstacle Representation

Maintain a temporary local obstacle map surrounding the robot.

Example size:

```text
4 m × 4 m
```

or:

```text
6 m × 6 m
```

Updated continuously from LiDAR.

Dynamic obstacles shall decay after they disappear.

Example:

```text
obstacle_timeout = 1–3 seconds
```

---

# 27. Safety Zones

The robot shall maintain three configurable safety regions.

## Zone A — Normal

```text
Obstacle distance > 1.0 m
```

Robot:

```text
normal speed
```

---

## Zone B — Caution

Example:

```text
0.5–1.0 m
```

Robot:

```text
reduce velocity
```

---

## Zone C — Stop

Example:

```text
<0.4–0.5 m
```

Robot:

```text
v = 0
ω = 0
```

Exact values shall be configurable and validated in simulation.

---

# 28. Direction-Dependent Safety

Safety distance should be larger in front than behind.

Example footprint:

```text
            FRONT

          1.0 m
       ┌─────────┐
       │ caution │
   ┌───┴─────────┴───┐
   │      ROBOT      │
   └─────────────────┘
          0.5 m

            REAR
```

This allows conservative forward navigation while avoiding unnecessary stopping from objects farther behind.

---

# 29. Human Crossing Scenario

Example:

Robot travelling:

```text
Kitchen → Table 3
```

A simulated pedestrian crosses its path.

Expected behavior:

```text
Person enters caution region
        ↓
Robot slows
        ↓
Person enters stop region
        ↓
Robot stops
        ↓
Person clears
        ↓
Robot resumes path
```

No replanning should occur for a very short crossing.

---

# 30. Persistent Blockage Scenario

Example:

A person or chair remains in the path.

```text
Obstacle detected
      ↓
Robot stops
      ↓
Wait T seconds
```

Example:

```text
T = 2–5 seconds
```

If still blocked:

```text
temporary obstacle
      ↓
added to planning grid
      ↓
A* executed again
      ↓
alternate route
```

---

# 31. Replanning

Replanning shall be triggered when:

1. planned route is persistently blocked,
2. robot deviates significantly from its path,
3. destination changes,
4. new permanent obstacle appears,
5. robot fails to progress.

---

# 32. Progress Monitoring

System shall continuously calculate:

```text
distance_to_goal
```

and:

```text
distance_progress
```

If:

```text
robot commanded to move
```

but its position changes by less than threshold for a defined period:

```text
robot_stuck = true
```

Then:

```text
stop
→ inspect obstacle map
→ replan
```

---

# 33. Local Avoidance — Phase 1

Phase 1 shall NOT attempt sophisticated steering between walking people.

Behaviour:

```text
detect
→ slow
→ stop
→ wait
→ resume
→ replan if necessary
```

This is deliberately conservative.

---

# 34. Local Avoidance — Phase 2

Optional later enhancement:

```text
Pure Pursuit command
+
local obstacle field
        ↓
velocity modification
```

Potential algorithms:

* Vector Field Histogram,
* Dynamic Window-style velocity search,
* gap-following,
* trajectory rollout,
* velocity obstacles.

This shall not be required for initial product acceptance.

---

# 35. Mission Manager

Create a lightweight finite-state machine.

Example:

```text
IDLE
 ↓
GO_TO_KITCHEN
 ↓
WAIT_FOR_LOADING
 ↓
GO_TO_TABLE
 ↓
ARRIVED
 ↓
WAIT_FOR_COLLECTION
 ↓
RETURN_HOME
 ↓
IDLE
```

---

# 36. Delivery Mission API

Example internal command:

```text
deliver(TABLE_3)
```

Expected sequence:

```text
Kitchen
↓
Table 3
↓
Home
```

Alternatively:

```text
navigateTo("TABLE_3")
```

---

# 37. Goal Completion Criteria

Destination reached when:

```text
position_error < 0.10–0.20 m
```

and optionally:

```text
heading_error < 10°
```

Robot shall then:

```text
v = 0
ω = 0
```

and transition to:

```text
ARRIVED
```

---

# 38. Restaurant World Requirements

Minimum test environment:

**approximately 8 m × 8 m or larger**

with:

* kitchen counter,
* five dining tables,
* chairs,
* narrow corridor,
* open region,
* wall boundaries,
* loading point,
* home point.

---

# 39. Dynamic Pedestrians

Use Webots moving human/obstacle actors if convenient.

If pedestrian animation becomes unnecessarily complicated, use moving cylindrical proxies initially.

From the navigation algorithm's perspective:

```text
moving cylinder
```

and:

```text
walking human
```

are equivalent LiDAR obstacles.

This allows navigation engineering to proceed independently of graphical realism.

---

# 40. Required Test Scenarios

## Test 1 — Empty Restaurant

```text
Kitchen → Table 1
```

Expected:

* route generated,
* path followed,
* destination reached.

---

## Test 2 — Multiple Destinations

```text
Kitchen → Table 1
Kitchen → Table 3
Kitchen → Table 5
```

All shall succeed.

---

## Test 3 — Person Crossing

Pedestrian crosses directly ahead.

Expected:

```text
slow
→ stop if necessary
→ continue
```

No collision.

---

## Test 4 — Stationary Person

Person stands directly on route.

Expected:

```text
stop
→ timeout
→ replan
→ alternate path
```

---

## Test 5 — Moving Crowd

Two or three pedestrians move around robot.

Expected:

```text
reduce speed
→ stop whenever clearance becomes unsafe
→ continue when safe
```

Robot is NOT required to aggressively weave through pedestrians.

---

# 41. Test 6 — Chair Moved Into Route

An unmapped chair is placed into corridor.

Expected:

```text
detect
→ stop
→ update temporary obstacle map
→ A* replan
→ bypass chair
```

---

# 42. Test 7 — Blocked Corridor

Entire corridor becomes unavailable.

Expected:

```text
detect blockage
→ alternate route
```

If no alternate route exists:

```text
NO_PATH
```

and robot remains safely stopped.

---

# 43. Test 8 — Localization Disturbance

Introduce moderate odometry error.

Expected:

LiDAR-based localization shall prevent the robot position estimate from continuously diverging.

---

# 44. Test 9 — Destination Change

While travelling:

```text
TABLE_2
```

issue:

```text
TABLE_4
```

Expected:

```text
cancel existing path
→ generate new A*
→ follow new route
```

---

# 45. Test 10 — Emergency Stop

Force safety condition.

Expected:

Motor command:

```text
left_velocity = 0
right_velocity = 0
```

within the next control cycle.

---

# 46. Software Modules

Recommended project structure:

```text
restaurant_robot/
│
├── simulator/
│   ├── webots_interface
│   └── restaurant_world
│
├── sensors/
│   ├── lidar
│   ├── encoders
│   └── imu
│
├── estimation/
│   ├── odometry
│   └── localization
│
├── mapping/
│   └── slam
│
├── planning/
│   ├── occupancy_grid
│   ├── astar
│   ├── inflation
│   └── path_smoothing
│
├── control/
│   ├── pure_pursuit
│   └── differential_drive
│
├── obstacle/
│   ├── dynamic_obstacle_detector
│   └── local_obstacle_map
│
├── safety/
│   └── safety_supervisor
│
├── mission/
│   └── delivery_manager
│
├── visualization/
│
└── tests/
```

---

# 47. Programming Language

Preferred implementation:

**C++**

Reason:

* deterministic execution,
* suitable for later embedded/robot deployment,
* good integration with standalone SLAM libraries,
* minimal runtime overhead.

Python may be used for:

* plotting,
* evaluation,
* logging,
* experiment analysis.

The main navigation controller should preferably remain C++.

---

# 48. Main Control Loop

Conceptually:

```cpp
while (robot.step(timeStep) != -1) {

    readSensors();

    updateOdometry();

    updateLocalization();

    updateDynamicObstacles();

    if (newGoal)
        globalPath = astar(map, pose, goal);

    if (pathBlockedForTooLong())
        globalPath = astar(updatedMap, pose, goal);

    VelocityCommand cmd =
        purePursuit(globalPath, pose);

    cmd =
        safetySupervisor(cmd, lidarData);

    sendWheelVelocities(cmd);
}
```

This should remain understandable to a normal robotics engineer without requiring knowledge of ROS internals.

---

# 49. Update Rates

Suggested initial frequencies:

| Function          | Frequency |
| ----------------- | --------: |
| Webots physics    |  32–64 Hz |
| Wheel control     |  20–50 Hz |
| LiDAR processing  |   5–10 Hz |
| Localization      |   5–20 Hz |
| Pure Pursuit      |     20 Hz |
| Safety supervisor |  20–50 Hz |
| Global A*         | On demand |
| Dynamic map       |   5–10 Hz |
| Mission manager   |   5–10 Hz |

The safety layer must execute faster than global planning.

---

# 50. Logging

Every simulation run shall record:

```text
timestamp
robot pose
estimated pose
goal
linear velocity
angular velocity
minimum obstacle distance
planner state
safety state
replanning events
distance to destination
collision count
```

---

# 51. Visualization

Webots shall visually display the environment and robot.

Additionally, a lightweight debug visualization should show:

* occupancy map,
* robot pose,
* A* path,
* Pure Pursuit target,
* LiDAR obstacle points,
* dynamic obstacles,
* safety region,
* destination.

This can be implemented using:

* Webots Display device,
* Supervisor drawing,
* OpenCV,
* lightweight custom GUI.

No RViz is required.

---

# 52. Performance Metrics

Each test run shall measure:

### Navigation success rate

```text
successful missions / total missions
```

Target:

**≥95% in controlled restaurant simulation**

---

### Collision rate

Target:

**0 collisions in standard test scenarios**

---

### Goal accuracy

Target:

**≤0.20 m**

---

### Replanning success

Robot shall successfully find alternate paths whenever a valid alternate route exists.

---

### Human crossing response

Robot shall stop before violating configured minimum clearance.

---

# 53. Safety Architecture

Safety Supervisor must have final authority over motion.

Architecture:

```text
Planner
   ↓
Pure Pursuit
   ↓
Velocity Command
   ↓
SAFETY SUPERVISOR
   ↓
Motor Controller
```

NOT:

```text
Safety logic
   ↓
Planner
   ↓
Controller
```

The safety module must be able to override any higher-level command immediately.

---

# 54. Safety Priority

Command priority:

```text
Emergency Stop
        >
Collision Prevention
        >
Dynamic Obstacle Avoidance
        >
Path Tracking
        >
Mission Command
```

---

# 55. Hardware Abstraction Requirement

The navigation algorithms shall never directly call Webots motor or sensor functions.

Instead:

```text
INavigationHardware
```

shall provide methods such as:

```cpp
LaserScan getLaserScan();

EncoderData getEncoders();

ImuData getImu();

void setVelocity(
    double linear,
    double angular
);
```

Simulation implementation:

```text
WebotsHardware
```

Future real implementation:

```text
RestaurantRobotHardware
```

This design decision is essential.

---

# 56. Simulation-to-Real Migration

Phase 1:

```text
Navigation Software
        ↓
WebotsHardware
        ↓
Webots Robot
```

Future:

```text
Navigation Software
        ↓
RealRobotHardware
        ↓
Motor Driver
        ↓
Hoverboard Motors
```

The following modules should remain unchanged:

```text
A*
Pure Pursuit
Mission Manager
Dynamic Obstacle Logic
Safety Supervisor
Replanning Logic
Map Handling
```

Only the hardware and possibly localization interfaces should change.

---

# 57. Phase Development Plan

## Phase 1 — Robot Movement

Implement:

* TurtleBot3 Burger,
* direct Webots C++ Controller,
* encoder reading,
* LiDAR reading,
* differential drive.

Acceptance:

Robot moves to commanded:

```text
v, ω
```

---

## Phase 2 — Odometry

Implement:

```text
encoder → x,y,θ
```

Acceptance:

Estimated trajectory approximately follows simulated ground truth.

---

## Phase 3 — Mapping

Integrate standalone SLAM.

Acceptance:

Restaurant occupancy map generated.

---

## Phase 4 — Localization

Load saved map and estimate pose.

Acceptance:

Robot can continuously estimate its location.

---

## Phase 5 — A*

Implement occupancy-grid path planning.

Acceptance:

Path found from kitchen to every table.

---

## Phase 6 — Pure Pursuit

Robot follows A* path.

Acceptance:

Robot reaches static goals.

---

## Phase 7 — Safety

Implement:

```text
LiDAR slowdown
stop zone
emergency override
```

Acceptance:

No collision with stationary obstacles.

---

## Phase 8 — Dynamic Obstacles

Introduce pedestrians.

Acceptance:

Robot:

```text
slows
stops
waits
continues
```

---

## Phase 9 — Replanning

Persistent obstacles added to temporary planning map.

Acceptance:

Robot finds alternate route.

---

## Phase 10 — Restaurant Mission

Implement:

```text
Kitchen
→ Table
→ Home
```

Acceptance:

Complete autonomous delivery cycle.

---

# 58. MVP Definition

The MVP is considered complete when the following scenario succeeds:

1. Restaurant map is loaded.
2. Robot starts at HOME.
3. User requests TABLE_3.
4. Robot localizes itself.
5. A* generates route.
6. Pure Pursuit follows route.
7. A pedestrian crosses.
8. Robot slows/stops.
9. Pedestrian clears.
10. Robot continues.
11. Another obstacle blocks route permanently.
12. Robot replans.
13. Robot reaches TABLE_3.
14. Robot waits.
15. Robot returns HOME.
16. No collisions occur.

---

# 59. Success Criteria

The project succeeds if we demonstrate:

> **A completely standalone autonomous mobile robot navigating a restaurant environment using LiDAR, odometry and IMU in Webots, with mapping/localization, A* planning, Pure Pursuit tracking, dynamic-obstacle response, safety stopping and automatic replanning, without ROS or Nav2.**

---

# 60. Final Frozen MVP Stack

The recommended stack is:

**Webots**

↓

**TurtleBot3 Burger**

↓

**Direct Webots C++ Controller API**

↓

**LiDAR + Wheel Encoders + IMU**

↓

**Standalone SLAM / Localization**

↓

**Occupancy Grid**

↓

**A***

↓

**Path Simplification**

↓

**Pure Pursuit**

↓

**LiDAR Dynamic-Obstacle Layer**

↓

**Slow / Stop Safety Supervisor**

↓

**Persistent-Obstacle Replanning**

↓

**Differential-Drive Kinematics**

↓

**Webots Wheel Motors**

with:

**Kitchen → Table → Home mission state machine**

as the application layer.

This is the proposed baseline architecture for the first restaurant-delivery robot simulation.
