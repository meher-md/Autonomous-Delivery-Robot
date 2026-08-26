#include <cassert>
#include <cmath>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>

#include "restaurant_robot/control/differential_drive.hpp"
#include "restaurant_robot/control/pure_pursuit.hpp"
#include "restaurant_robot/estimation/localization.hpp"
#include "restaurant_robot/estimation/odometry.hpp"
#include "restaurant_robot/logging/run_logger.hpp"
#include "restaurant_robot/mapping/map_io.hpp"
#include "restaurant_robot/mapping/occupancy_ray_mapper.hpp"
#include "restaurant_robot/mapping/restaurant_map_factory.hpp"
#include "restaurant_robot/mapping/slam_backend.hpp"
#include "restaurant_robot/mission/delivery_manager.hpp"
#include "restaurant_robot/navigation/navigator.hpp"
#include "restaurant_robot/obstacle/dynamic_obstacle_detector.hpp"
#include "restaurant_robot/obstacle/local_obstacle_map.hpp"
#include "restaurant_robot/planning/astar.hpp"
#include "restaurant_robot/planning/inflation.hpp"
#include "restaurant_robot/planning/path_smoothing.hpp"
#include "restaurant_robot/safety/safety_supervisor.hpp"
#include "restaurant_robot/simulation/scenario_runner.hpp"

using namespace restaurant_robot;

namespace {

void require(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

LaserScan makeScan(double range, int samples = 181) {
    LaserScan scan;
    scan.angle_min = -kPi;
    scan.angle_increment = 2.0 * kPi / static_cast<double>(samples - 1);
    scan.max_range = 6.0;
    scan.timestamp = 1.0;
    scan.ranges.assign(samples, range);
    return scan;
}

RestaurantMap createStraightTestMap() {
    RestaurantMap map;
    map.grid = OccupancyGrid(60, 30, 0.10, Point2D{0.0, -1.5}, kFree);
    map.destinations = {
        {"HOME", Pose2D{0.5, 0.0, 0.0}},
        {"KITCHEN", Pose2D{2.0, 0.0, 0.0}},
        {"TABLE_2", Pose2D{3.8, 0.8, 0.0}},
        {"TABLE_3", Pose2D{4.5, 0.0, 0.0}},
        {"TABLE_4", Pose2D{5.0, -0.8, 0.0}},
    };
    return map;
}

RestaurantMap createNarrowCorridorTestMap() {
    RestaurantMap map;
    map.grid = OccupancyGrid(70, 11, 0.10, Point2D{0.0, -0.55}, kFree);
    for (int x = 0; x < map.grid.width(); ++x) {
        map.grid.set(x, 0, kOccupied);
        map.grid.set(x, map.grid.height() - 1, kOccupied);
    }
    for (int y = 0; y < map.grid.height(); ++y) {
        map.grid.set(0, y, kOccupied);
        map.grid.set(map.grid.width() - 1, y, kOccupied);
    }
    map.destinations = {
        {"HOME", Pose2D{0.5, 0.0, 0.0}},
        {"KITCHEN", Pose2D{1.5, 0.0, 0.0}},
        {"TABLE_3", Pose2D{5.5, 0.0, 0.0}},
    };
    return map;
}

RestaurantMap createStaticKeepoutGuardTestMap() {
    RestaurantMap map;
    map.grid = OccupancyGrid(45, 30, 0.10, Point2D{0.0, -1.5}, kFree);
    for (int x = 6; x <= 12; ++x) {
        for (int y = 13; y <= 16; ++y) {
            map.grid.set(x, y, kOccupied);
        }
    }
    map.destinations = {
        {"HOME", Pose2D{0.2, 0.0, 0.0}},
        {"KITCHEN", Pose2D{2.5, 0.0, 0.0}},
        {"TABLE_1", Pose2D{3.7, 0.0, 0.0}},
    };
    return map;
}

OccupancyGrid createLocalizationTestMap() {
    OccupancyGrid grid(70, 60, 0.10, Point2D{0.0, 0.0}, kFree);
    for (int x = 0; x < grid.width(); ++x) {
        grid.set(x, 0, kOccupied);
        grid.set(x, grid.height() - 1, kOccupied);
    }
    for (int y = 0; y < grid.height(); ++y) {
        grid.set(0, y, kOccupied);
        grid.set(grid.width() - 1, y, kOccupied);
    }
    for (int y = 8; y < 45; ++y) {
        grid.set(43, y, kOccupied);
    }
    for (int x = 12; x < 25; ++x) {
        grid.set(x, 38, kOccupied);
    }
    return grid;
}

LaserScan raycastScan(const OccupancyGrid& grid, const Pose2D& pose, int samples = 73, double max_range = 6.0) {
    LaserScan scan;
    scan.angle_min = -kPi;
    scan.angle_increment = samples > 1 ? 2.0 * kPi / static_cast<double>(samples - 1) : 0.0;
    scan.max_range = max_range;
    scan.timestamp = 1.0;
    scan.ranges.reserve(samples);

    for (int i = 0; i < samples; ++i) {
        const double angle = normalizeAngle(pose.theta + scan.angle_min + i * scan.angle_increment);
        double range = max_range;
        for (double r = 0.05; r <= max_range; r += 0.025) {
            const Point2D point{pose.x + r * std::cos(angle), pose.y + r * std::sin(angle)};
            const auto cell = grid.worldToGrid(point);
            if (!cell || grid.get(cell->x, cell->y) == kOccupied) {
                range = r;
                break;
            }
        }
        scan.ranges.push_back(range);
    }
    return scan;
}

std::string readTextFile(const std::string& path) {
    std::ifstream in(path);
    std::ostringstream buffer;
    buffer << in.rdbuf();
    return buffer.str();
}

void testRestaurantRoutes() {
    const auto restaurant = createPrototypeRestaurantMap(0.10);
    const auto inflated = inflateObstacles(restaurant.grid, 0.40);
    const AStarPlanner planner;

    for (const std::string table : {"TABLE_1", "TABLE_3", "TABLE_5"}) {
        const auto result = planner.plan(inflated, restaurant.destinations.at("KITCHEN"), restaurant.destinations.at(table));
        require(result.status == PlannerStatus::Success, "A* failed for " + table + ": " + toString(result.status));
        const auto simplified = simplifyPathLineOfSight(inflated, result.path);
        require(!simplified.points.empty(), "simplified path empty for " + table);
        require(simplified.points.size() < result.path.points.size(), "path simplification did not reduce waypoints for " + table);
    }
}

void testPlannerSnapsInflatedStartCell() {
    OccupancyGrid grid(20, 20, 0.10, Point2D{0.0, 0.0}, kFree);
    grid.set(5, 5, kOccupied);

    const AStarPlanner planner;
    const auto result = planner.plan(grid, Pose2D{0.55, 0.55, 0.0}, Pose2D{1.5, 1.5, 0.0});
    require(result.status == PlannerStatus::Success, "A* should snap a near-obstacle start pose to free space");
    require(!result.path.points.empty(), "snapped-start path should not be empty");
}

void testPlannerRejectsOccupiedGoalCell() {
    OccupancyGrid grid(20, 20, 0.10, Point2D{0.0, 0.0}, kFree);
    grid.set(15, 15, kOccupied);

    const AStarPlanner planner;
    const auto result = planner.plan(grid, Pose2D{0.5, 0.5, 0.0}, Pose2D{1.55, 1.55, 0.0});
    require(result.status == PlannerStatus::GoalOccupied, "A* should reject occupied destination instead of moving it");
    require(result.path.points.empty(), "occupied-goal plan should not return a path");
}

void testPathCornerSmoothingUsesLookaheadScale() {
    OccupancyGrid grid(40, 40, 0.05, Point2D{-0.5, -0.5}, kFree);
    Path path;
    path.points = {Point2D{0.0, 0.0}, Point2D{1.0, 0.0}, Point2D{1.0, 1.0}};

    const auto smoothed = smoothPathCorners(grid, path, 0.20);
    require(smoothed.points.size() > path.points.size(), "corner smoothing should add intermediate route points");
    require(distance(smoothed.points.front(), path.points.front()) < 1e-9, "smoothed path should keep the original start");
    require(distance(smoothed.points.back(), path.points.back()) < 1e-9, "smoothed path should keep the original goal");
    require(distance(smoothed.points.at(1), Point2D{0.8, 0.0}) < 1e-6,
            "corner smoothing should trim the corner by the requested lookahead scale");
}

void testPathCornerSmoothingRejectsDisconnectedFinalCorner() {
    OccupancyGrid grid(40, 40, 0.05, Point2D{-0.5, -0.5}, kFree);
    const auto blocked = grid.worldToGrid(Point2D{1.0, 0.6});
    require(blocked.has_value(), "test obstacle should be inside grid");
    grid.set(blocked->x, blocked->y, kOccupied);

    Path path;
    path.points = {Point2D{0.0, 0.0}, Point2D{1.0, 0.0}, Point2D{1.0, 1.0}};

    const auto smoothed = smoothPathCorners(grid, path, 0.20);
    require(smoothed.points.size() == path.points.size(),
            "final corner smoothing should be rejected when the smoothed exit cannot connect to the goal");
    require(distance(smoothed.points.at(1), path.points.at(1)) < 1e-9,
            "rejected final smoothing should keep the original corner instead of adding a backward kink");
}

void testMapPersistence() {
    const auto restaurant = createPrototypeRestaurantMap(0.10);
    const std::string json_path = "restaurant_map_test.json";
    const std::string pgm_path = "restaurant_map_test.pgm";

    require(saveOccupancyGridJson(restaurant.grid, json_path), "map JSON save should succeed");
    require(restaurant.grid.savePgm(pgm_path), "map PGM save should succeed");

    OccupancyGrid loaded;
    require(loadOccupancyGridJson(json_path, loaded), "map JSON load should succeed");
    require(loaded.width() == restaurant.grid.width(), "loaded map width mismatch");
    require(loaded.height() == restaurant.grid.height(), "loaded map height mismatch");
    require(std::abs(loaded.resolution() - restaurant.grid.resolution()) < 1e-9, "loaded map resolution mismatch");
    require(loaded.cells() == restaurant.grid.cells(), "loaded map cells mismatch");

    const std::string semantic_json_path = "restaurant_semantic_map_test.json";
    require(saveRestaurantMapJson(restaurant, semantic_json_path), "semantic map JSON save should succeed");

    RestaurantMap semantic_loaded;
    require(loadRestaurantMapJson(semantic_json_path, semantic_loaded), "semantic map JSON load should succeed");
    require(semantic_loaded.grid.width() == restaurant.grid.width(), "semantic loaded map width mismatch");
    require(semantic_loaded.grid.cells() == restaurant.grid.cells(), "semantic loaded map cells mismatch");
    require(semantic_loaded.destinations.size() == restaurant.destinations.size(), "semantic destinations count mismatch");
    require(std::abs(semantic_loaded.destinations.at("TABLE_3").x - restaurant.destinations.at("TABLE_3").x) < 1e-9,
            "semantic TABLE_3 x mismatch");
    require(std::abs(semantic_loaded.destinations.at("KITCHEN").theta - restaurant.destinations.at("KITCHEN").theta) < 1e-9,
            "semantic KITCHEN theta mismatch");
}

void testOccupancyRayMapper() {
    OccupancyRayMapper mapper(RayMappingConfig{
        4.0,
        4.0,
        0.10,
        Point2D{-2.0, -2.0},
        0.05,
    });

    LaserScan scan;
    scan.angle_min = 0.0;
    scan.angle_increment = kPi / 2.0;
    scan.max_range = 3.0;
    scan.ranges = {1.0, 3.0, 3.0};

    mapper.integrateScan(Pose2D{0.0, 0.0, 0.0}, scan);
    const auto occupied = mapper.grid().worldToGrid(Point2D{1.0, 0.0});
    const auto free = mapper.grid().worldToGrid(Point2D{0.5, 0.0});
    require(occupied && mapper.grid().get(occupied->x, occupied->y) == kOccupied,
            "ray mapper should mark hit endpoint occupied");
    require(free && mapper.grid().get(free->x, free->y) == kFree,
            "ray mapper should mark traversed cells free");
}

void testKnownPoseSlamBackend() {
    KnownPoseRaySlamBackend backend(RayMappingConfig{
        4.0,
        4.0,
        0.10,
        Point2D{-2.0, -2.0},
        0.05,
    });

    LaserScan scan;
    scan.angle_min = 0.0;
    scan.angle_increment = kPi / 2.0;
    scan.max_range = 3.0;
    scan.ranges = {1.0, 3.0, 3.0};

    const Pose2D hint{0.0, 0.0, 0.0};
    const auto pose = backend.update(scan, EncoderData{}, ImuData{}, hint);
    require(distance(pose, hint) < 1e-9, "known-pose backend should return pose hint");
    require(backend.name() == "known_pose_ray_mapper", "known-pose backend name should be stable");

    int occupied_count = 0;
    int free_count = 0;
    for (const auto cell : backend.currentMap().cells()) {
        if (cell == kOccupied) {
            ++occupied_count;
        } else if (cell == kFree) {
            ++free_count;
        }
    }
    require(occupied_count > 0, "known-pose backend should create occupied cells");
    require(free_count > 0, "known-pose backend should create free cells");
    require(backend.saveMap("known_pose_backend_test_map"), "known-pose backend should save map artifacts");
}

void testSlamBackendSelectionReportsGraphCandidate() {
    const auto backends = availableSlamBackends();
    bool found_known_pose = false;
    bool found_mrpt_graphslam = false;
    for (const auto& backend : backends) {
        if (backend.name == "known_pose") {
            found_known_pose = backend.available;
        }
        if (backend.name == "mrpt_graphslam") {
            found_mrpt_graphslam = true;
            require(!backend.description.empty(), "MRPT graph-SLAM candidate should describe its role");
            if (!backend.available) {
                require(!backend.install_hint.empty(), "unavailable MRPT graph-SLAM backend should expose install hint");
            }
        }
    }
    require(found_known_pose, "known-pose SLAM backend should be available");
    require(found_mrpt_graphslam, "MRPT graph-SLAM candidate should be listed");

    const auto fallback = createSlamBackend("mrpt_graphslam");
    require(fallback->name() == "known_pose_ray_mapper" || fallback->name() == "mrpt_graphslam",
            "MRPT graph-SLAM selection should either instantiate or fall back explicitly");
}

#ifdef RESTAURANT_ROBOT_HAS_CERES
void testCeresScanMatchSlamBackend() {
    CeresScanMatchConfig config;
    config.ray_mapping.map_width_m = 7.0;
    config.ray_mapping.map_height_m = 6.0;
    config.ray_mapping.resolution_m = 0.10;
    config.ray_mapping.origin = Point2D{0.0, 0.0};
    config.max_beams = 60;
    config.min_associations = 8;
    config.association_radius_m = 0.55;
    config.translation_prior_weight = 1.0;
    config.rotation_prior_weight = 0.6;

    CeresScanMatchSlamBackend backend(config);
    const auto reference_map = createLocalizationTestMap();
    const Pose2D true_pose{1.7, 2.2, 0.12};
    const Pose2D disturbed_pose{1.92, 2.03, 0.22};
    const auto scan = raycastScan(reference_map, true_pose, 121, 6.0);

    backend.update(scan, EncoderData{}, ImuData{}, true_pose);
    const auto corrected = backend.update(scan, EncoderData{}, ImuData{}, disturbed_pose);

    require(backend.name() == "ceres_scan_match_ray_mapper", "Ceres backend name should be stable");
    require(distance(corrected, true_pose) < distance(disturbed_pose, true_pose),
            "Ceres scan matching should reduce position disturbance");
    require(std::abs(normalizeAngle(corrected.theta - true_pose.theta)) <
                std::abs(normalizeAngle(disturbed_pose.theta - true_pose.theta)),
            "Ceres scan matching should reduce heading disturbance");
}
#endif

void testDifferentialDriveAndOdometry() {
    DifferentialDriveKinematics kinematics(0.033, 0.16);
    const auto wheels = kinematics.toWheelAngularVelocities(VelocityCommand{0.20, 0.0});
    require(std::abs(wheels.left - wheels.right) < 1e-9, "straight command should give equal wheel velocities");

    WheelImuOdometry odom(0.033, 0.16, 0.0);
    odom.reset(Pose2D{}, EncoderData{0.0, 0.0, 0.0});
    const auto pose = odom.update(EncoderData{3.0, 3.0, 1.0}, ImuData{0.0, 0.0, 0.0, 1.0});
    require(pose.x > 0.09 && std::abs(pose.y) < 1e-6, "odometry should move forward with equal wheel angles");

    WheelImuOdometry wrapped_odom(0.033, 0.16, 0.15);
    wrapped_odom.reset(Pose2D{0.0, 0.0, 3.10}, EncoderData{0.0, 0.0, 0.0});
    const double wheel_delta = 0.02 * 0.16 / 0.033 / 2.0;
    const auto wrapped_pose = wrapped_odom.update(
        EncoderData{-wheel_delta, wheel_delta, 1.0},
        ImuData{-3.12, 0.0, 0.0, 1.0});
    require(std::abs(normalizeAngle(wrapped_pose.theta - 3.1265)) < 0.05,
            "odometry should fuse IMU yaw across +/-pi without a heading jump");
}

void testScanMapLocalizationCorrectsDisturbance() {
    const auto map = createLocalizationTestMap();
    const Pose2D true_pose{1.7, 2.2, 0.12};
    const Pose2D disturbed_pose{1.92, 2.03, 0.22};
    const auto scan = raycastScan(map, true_pose);

    ScanMapLocalizationConfig config;
    config.search_xy_radius_m = 0.30;
    config.search_xy_step_m = 0.05;
    config.search_theta_radius_rad = 12.0 * kPi / 180.0;
    config.search_theta_step_rad = 2.0 * kPi / 180.0;
    config.correction_gain = 1.0;

    ScanMapLocalizer localizer(map, config);
    const auto corrected = localizer.update(disturbed_pose, scan);

    require(distance(corrected, true_pose) < distance(disturbed_pose, true_pose),
            "scan-map localization should reduce position disturbance");
    require(std::abs(normalizeAngle(corrected.theta - true_pose.theta)) <
                std::abs(normalizeAngle(disturbed_pose.theta - true_pose.theta)),
            "scan-map localization should reduce heading disturbance");
}

void testPurePursuit() {
    Path path;
    path.points = {Point2D{0.0, 0.0}, Point2D{1.0, 0.0}, Point2D{2.0, 0.0}};
    PurePursuitController controller;
    const auto target = controller.selectLookaheadTarget(path, Pose2D{0.0, 0.0, 0.0});
    require(target && target->x > 0.15 && target->x < 0.30 && std::abs(target->y) < 1e-9,
            "pure pursuit should expose an interpolated forward lookahead target for visualization");
    const auto command = controller.computeCommand(path, Pose2D{0.0, 0.0, 0.0});
    require(command.linear > 0.0, "pure pursuit should command forward motion");
    require(std::abs(command.angular) < 1e-6, "straight path should not command rotation");

    Path return_path;
    return_path.points = {Point2D{2.0, 0.0}, Point2D{0.5, 0.0}};
    const auto turn_command = controller.computeCommand(return_path, Pose2D{2.0, 0.0, 0.0});
    require(turn_command.linear == 0.0, "target behind robot should rotate before driving");
    require(std::abs(turn_command.angular) > 0.1, "target behind robot should command turn-in-place");

    Path left_path;
    left_path.points = {Point2D{0.0, 0.0}, Point2D{0.0, 1.0}};
    const auto left_turn = controller.computeCommand(left_path, Pose2D{0.0, 0.0, 0.0});
    require(left_turn.linear > 0.0 && left_turn.angular > 0.0,
            "side target should crawl while turning anticlockwise instead of spinning in place");

    Path right_path;
    right_path.points = {Point2D{0.0, 0.0}, Point2D{0.0, -1.0}};
    const auto right_turn = controller.computeCommand(right_path, Pose2D{0.0, 0.0, 0.0});
    require(right_turn.linear > 0.0 && right_turn.angular < 0.0,
            "side target should crawl while turning clockwise instead of spinning in place");

    Path near_goal_path;
    near_goal_path.points = {Point2D{0.0, 0.0}, Point2D{0.4, 0.0}};
    const auto near_goal_command = controller.computeCommand(near_goal_path, Pose2D{0.0, 0.0, 0.0});
    require(near_goal_command.linear > 0.0 && near_goal_command.linear < command.linear,
            "final approach should slow down instead of overshooting around the goal");
}

void testSafetySupervisor() {
    SafetySupervisor supervisor;

    auto caution = makeScan(6.0);
    caution.ranges.at(caution.ranges.size() / 2) = 0.75;
    const auto caution_result = supervisor.apply(VelocityCommand{0.40, 0.0}, caution);
    require(caution_result.state == SafetyState::Caution, "0.75 m front obstacle should trigger caution");
    require(caution_result.command.linear <= 0.22, "caution speed should be capped");

    auto stop = makeScan(6.0);
    stop.ranges.at(stop.ranges.size() / 2) = 0.30;
    const auto stop_result = supervisor.apply(VelocityCommand{0.40, 0.2}, stop);
    require(stop_result.state == SafetyState::Stop, "0.30 m front obstacle should stop robot");
    require(stop_result.command.linear == 0.0 && stop_result.command.angular == 0.0, "stop state should zero command");

    supervisor.setEmergencyStop(true);
    const auto estop = supervisor.apply(VelocityCommand{0.40, 0.2}, makeScan(6.0));
    require(estop.state == SafetyState::EmergencyStop, "emergency stop should override scan state");
}

void testDynamicObstacleLayer() {
    const auto restaurant = createPrototypeRestaurantMap(0.10);
    DynamicObstacleDetector detector;
    LaserScan scan = makeScan(6.0, 9);
    scan.angle_min = -kPi / 2.0;
    scan.angle_increment = kPi / 8.0;
    scan.ranges.at(4) = 0.8;

    const auto obstacles = detector.detectFreeSpaceObstacles(restaurant.grid, Pose2D{0.8, 0.8, 0.0}, scan);
    require(!obstacles.empty(), "LiDAR return in mapped free space should be treated as dynamic obstacle");

    LocalObstacleMap local(6.0, 0.10, 2.0);
    local.updateFromScan(Pose2D{0.8, 0.8, 0.0}, scan);
    require(local.activeObstacleCount() >= 1, "local obstacle map should store scan obstacle");
    local.decay(5.0);
    require(local.activeObstacleCount() == 0, "local obstacle map should decay stale obstacles");
}

void testMissionManager() {
    const auto restaurant = createPrototypeRestaurantMap(0.10);
    DeliveryManager manager(restaurant.destinations);
    require(manager.deliver("TABLE_3"), "delivery command should accept TABLE_3");

    auto out = manager.update(restaurant.destinations.at("HOME"), true, 0.1);
    require(out.new_goal && manager.activeDestinationName() == "KITCHEN", "mission should first go to kitchen");

    manager.update(restaurant.destinations.at("KITCHEN"), true, 0.1);
    out = manager.update(restaurant.destinations.at("KITCHEN"), true, 1.0);
    require(out.new_goal && manager.activeDestinationName() == "TABLE_3", "mission should continue to requested table");

    manager.update(restaurant.destinations.at("TABLE_3"), true, 0.1);
    out = manager.update(restaurant.destinations.at("TABLE_3"), true, 1.0);
    require(out.new_goal && manager.activeDestinationName() == "KITCHEN", "mission should return kitchen after collection wait");

    out = manager.update(restaurant.destinations.at("KITCHEN"), true, 0.1);
    require(out.mission_complete && manager.state() == MissionState::Complete, "mission should complete at KITCHEN");

    require(manager.goToDestination("HOME"), "manager should accept explicit HOME command");
    out = manager.update(restaurant.destinations.at("KITCHEN"), true, 0.1);
    require(out.new_goal && manager.activeDestinationName() == "HOME", "explicit HOME command should go directly home");
    out = manager.update(restaurant.destinations.at("HOME"), true, 0.1);
    require(out.mission_complete && manager.state() == MissionState::Complete, "explicit HOME command should complete at HOME");
}

void testNavigatorReplansPersistentBlockage() {
    NavigatorConfig config;
    config.persistent_blockage_timeout_s = 0.20;
    config.stuck_timeout_s = 10.0;

    Navigator navigator(createStraightTestMap(), config);
    require(navigator.deliver("TABLE_3"), "navigator should accept TABLE_3 delivery");

    const Pose2D pose{0.5, 0.0, 0.0};
    auto clear_scan = makeScan(6.0);
    auto result = navigator.update(pose, clear_scan, 0.1);
    require(result.planner_state == NavigatorPlannerState::PathReady, "navigator should plan initial route");
    require(!navigator.activePath().points.empty(), "navigator path should not be empty");

    auto blocked_scan = makeScan(6.0);
    blocked_scan.ranges.at(blocked_scan.ranges.size() / 2) = 0.28;
    blocked_scan.timestamp = 1.1;
    result = navigator.update(pose, blocked_scan, 0.1);
    require(result.safety_state == SafetyState::Stop, "front blockage should stop before replanning timeout");

    blocked_scan.timestamp = 1.2;
    result = navigator.update(pose, blocked_scan, 0.15);
    require(result.replanned, "persistent blockage should trigger replanning");
    require(result.replanning_events == 1, "replanning event count should increment");
    require(result.planner_state == NavigatorPlannerState::PathReady, "alternate route should be found in open map");
}

void testNavigatorReplansDynamicObstacleOnPathBeforeStop() {
    NavigatorConfig config;
    config.persistent_blockage_timeout_s = 0.10;
    config.stuck_timeout_s = 10.0;

    Navigator navigator(createStraightTestMap(), config);
    require(navigator.deliver("TABLE_3"), "navigator should accept TABLE_3 delivery for dynamic replan test");

    const Pose2D pose{0.5, 0.0, 0.0};
    auto result = navigator.update(pose, makeScan(6.0), 0.1);
    require(result.planner_state == NavigatorPlannerState::PathReady, "dynamic replan test should have initial route");

    auto path_obstacle_scan = makeScan(6.0);
    path_obstacle_scan.ranges.at(path_obstacle_scan.ranges.size() / 2) = 1.2;
    path_obstacle_scan.timestamp = 2.0;
    result = navigator.update(pose, path_obstacle_scan, 0.15);

    require(result.safety_state != SafetyState::Stop, "path obstacle at caution distance should not require hard stop first");
    require(result.replanned, "dynamic obstacle on active path should trigger replanning before hard stop");
}

void testNavigatorReplansExactBoundaryCorridorBlockage() {
    NavigatorConfig config;
    config.persistent_blockage_timeout_s = 0.10;
    config.stuck_timeout_s = 10.0;

    Navigator navigator(createNarrowCorridorTestMap(), config);
    require(navigator.deliver("TABLE_3"), "navigator should accept corridor mission");

    const Pose2D pose{0.5, 0.0, 0.0};
    auto result = navigator.update(pose, makeScan(6.0), 0.1);
    require(result.planner_state == NavigatorPlannerState::PathReady, "corridor test should have initial route");

    auto blocked_scan = makeScan(6.0);
    blocked_scan.ranges.at(blocked_scan.ranges.size() / 2) = 0.28;
    blocked_scan.timestamp = 2.0;
    result = navigator.update(pose, blocked_scan, 0.15);

    require(result.replanned, "persistent blockage should still trigger replanning");
    require(!result.no_path, "exact-boundary corridor should not become NO_PATH from one occupied scan cell");
    require(result.planner_state == NavigatorPlannerState::PathReady, "exact-boundary corridor should keep a route");
}

void testNavigatorDestinationChange() {
    Navigator navigator(createStraightTestMap());
    require(navigator.deliver("TABLE_2"), "first delivery command should be accepted");
    const Pose2D pose{0.5, 0.0, 0.0};
    auto result = navigator.update(pose, makeScan(6.0), 0.1);
    require(result.active_goal == "KITCHEN", "fresh delivery should start by going to KITCHEN");

    require(navigator.deliver("TABLE_4"), "destination change command should reroute active mission");
    result = navigator.update(pose, makeScan(6.0), 0.1);
    require(result.active_goal == "TABLE_4", "active destination change should go directly to the new table");
    require(result.planner_state == NavigatorPlannerState::PathReady, "destination change should create a new path");

    result = navigator.update(Pose2D{5.0, -0.8, 0.0}, makeScan(6.0), 0.1);
    result = navigator.update(Pose2D{5.0, -0.8, 0.0}, makeScan(6.0), 1.0);
    require(result.active_goal == "KITCHEN", "direct table reroute should still return to KITCHEN after service");
}

void testNavigatorEmergencyStopOverride() {
    Navigator navigator(createStraightTestMap());
    require(navigator.deliver("TABLE_3"), "emergency-stop test mission should be accepted");

    const Pose2D pose{0.5, 0.0, 0.0};
    auto result = navigator.update(pose, makeScan(6.0), 0.1);
    require(result.command.linear > 0.0, "navigator should command motion before emergency stop");

    navigator.setEmergencyStop(true);
    result = navigator.update(pose, makeScan(6.0), 0.1);
    require(result.safety_state == SafetyState::EmergencyStop, "emergency stop should be final safety state");
    require(result.command.linear == 0.0 && result.command.angular == 0.0,
            "emergency stop should zero command in the next cycle");
    require(!navigator.deliver("TABLE_1"), "mission command should be rejected while emergency stop is latched");
    require(!navigator.goToDestination("HOME"), "direct destination should be rejected while emergency stop is latched");

    navigator.setEmergencyStop(false);
    result = navigator.update(pose, makeScan(6.0), 0.1);
    require(result.safety_state != SafetyState::EmergencyStop, "clear emergency stop should restore normal safety processing");
    require(result.planner_state == NavigatorPlannerState::Idle, "released emergency stop should leave navigator idle");
    require(result.command.linear == 0.0 && result.command.angular == 0.0,
            "released emergency stop should not resume old mission");

    require(navigator.deliver("TABLE_3"), "new mission after emergency-stop release should be accepted");
    result = navigator.update(pose, makeScan(6.0), 0.1);
    require(result.command.linear > 0.0, "new mission after release should command motion");
}

void testNavigatorStopsBeforeStaticKeepout() {
    NavigatorConfig config;

    Navigator navigator(createStaticKeepoutGuardTestMap(), config);
    require(navigator.goToDestination("KITCHEN"), "static keepout guard test should accept KITCHEN destination");

    const Pose2D pose{0.45, 0.0, 0.0};
    const auto result = navigator.update(pose, makeScan(6.0), 0.1);
    require(result.planner_state == NavigatorPlannerState::PathReady, "static keepout guard test should find a route around obstacle");
    require(!navigator.activePath().points.empty(), "static keepout guard route should not be empty");
    require(result.command.linear == 0.0, "navigator should stop before commanded motion enters inflated static keepout");
}

void testNavigatorPlansWithUpdatedStaticMap() {
    NavigatorConfig config;
    config.planner_clearance_radius_m = 0.05;

    const auto map = createStraightTestMap();
    Navigator navigator(map, config);
    const Pose2D pose{0.5, 0.0, 0.0};
    require(navigator.goToDestination("TABLE_3"), "updated-map test should accept TABLE_3 destination");

    auto result = navigator.update(pose, makeScan(6.0), 0.1);
    require(result.planner_state == NavigatorPlannerState::PathReady, "updated-map test should have an initial path");
    const auto initial_path = navigator.activePath();
    require(!initial_path.points.empty(), "updated-map initial path should not be empty");

    OccupancyGrid learned_grid = map.grid;
    for (int x = 24; x <= 27; ++x) {
        for (int y = 10; y < learned_grid.height(); ++y) {
            learned_grid.set(x, y, kOccupied);
        }
    }
    navigator.updateStaticMap(learned_grid);
    require(navigator.goToDestination("TABLE_3"), "updated-map test should accept TABLE_3 after map update");

    result = navigator.update(pose, makeScan(6.0), 0.1);
    require(result.planner_state == NavigatorPlannerState::PathReady, "navigator should plan after learned map update");
    const auto updated_path = navigator.activePath();
    require(!updated_path.points.empty(), "updated-map route should not be empty");

    double min_y = std::numeric_limits<double>::infinity();
    for (const auto& point : updated_path.points) {
        min_y = std::min(min_y, point.y);
    }
    require(min_y < -0.45, "updated-map route should go around the learned obstacle through the lower gap");
}

void testNavigatorCompletesHeadlessDelivery() {
    Navigator navigator(createStraightTestMap());
    require(navigator.deliver("TABLE_3"), "headless delivery should accept TABLE_3");

    Pose2D pose{0.5, 0.0, 0.0};
    constexpr double dt = 0.1;
    bool complete = false;
    for (int step = 0; step < 1200; ++step) {
        auto scan = makeScan(6.0);
        scan.timestamp = step * dt;
        const auto result = navigator.update(pose, scan, dt);
        if (result.mission_complete) {
            complete = true;
            break;
        }

        pose.x += result.command.linear * std::cos(pose.theta) * dt;
        pose.y += result.command.linear * std::sin(pose.theta) * dt;
        pose.theta = normalizeAngle(pose.theta + result.command.angular * dt);
    }

    require(complete, "headless navigator should complete Kitchen -> Table -> Home");
    require(distance(pose, Pose2D{2.0, 0.0, 0.0}) < 0.25, "headless delivery should finish near KITCHEN");
}

void testScenarioRunnerMetrics() {
    const auto map = createStraightTestMap();
    ScenarioRunner runner(map);

    ScenarioConfig scenario;
    scenario.initial_pose = map.destinations.at("HOME");
    scenario.expected_final_pose = map.destinations.at("KITCHEN");
    scenario.table_goal = "TABLE_3";
    scenario.max_steps = 1200;

    const auto metrics = runner.run(
        scenario,
        [](const Pose2D&, double time_s, int) {
            return makeUniformScan(6.0, time_s);
        });

    require(metrics.mission_success, "scenario runner should complete clear delivery mission");
    require(metrics.collision_count == 0, "clear delivery mission should have zero collisions");
    require(metrics.final_goal_error < 0.25, "scenario final accuracy should be within target tolerance");
    require(metrics.steps > 0, "scenario metrics should record steps");
}

void testRunLogger() {
    const std::string path = "run_logger_test.csv";
    {
        RunLogger logger(path);
        require(logger.isOpen(), "run logger should open CSV file");
        logger.write(RunLogRecord{
            1.25,
            Pose2D{0.1, 0.2, 0.3},
            Pose2D{0.1, 0.2, 0.3},
            "TABLE_3",
            "TABLE_3",
            0.2,
            0.1,
            0.75,
            "PATH_READY",
            SafetyState::Caution,
            2,
            1.5,
            0,
        });
    }

    const auto text = readTextFile(path);
    require(text.find("timestamp,robot_x,robot_y") != std::string::npos, "run logger should write header");
    require(text.find("TABLE_3") != std::string::npos, "run logger should write goal name");
    require(text.find("CAUTION") != std::string::npos, "run logger should write safety state");
}

}  // namespace

int main() {
    testRestaurantRoutes();
    testPlannerSnapsInflatedStartCell();
    testPlannerRejectsOccupiedGoalCell();
    testPathCornerSmoothingUsesLookaheadScale();
    testPathCornerSmoothingRejectsDisconnectedFinalCorner();
    testMapPersistence();
    testOccupancyRayMapper();
    testKnownPoseSlamBackend();
#ifdef RESTAURANT_ROBOT_HAS_CERES
    testCeresScanMatchSlamBackend();
#endif
    testDifferentialDriveAndOdometry();
    testScanMapLocalizationCorrectsDisturbance();
    testPurePursuit();
    testSafetySupervisor();
    testDynamicObstacleLayer();
    testMissionManager();
    testNavigatorReplansPersistentBlockage();
    testNavigatorReplansDynamicObstacleOnPathBeforeStop();
    testNavigatorReplansExactBoundaryCorridorBlockage();
    testNavigatorDestinationChange();
    testNavigatorEmergencyStopOverride();
    testNavigatorStopsBeforeStaticKeepout();
    testNavigatorPlansWithUpdatedStaticMap();
    testNavigatorCompletesHeadlessDelivery();
    testScenarioRunnerMetrics();
    testRunLogger();

    std::cout << "restaurant_robot navigation core tests passed\n";
    return 0;
}
