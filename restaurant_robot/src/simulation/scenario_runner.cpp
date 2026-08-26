#include "restaurant_robot/simulation/scenario_runner.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <utility>

namespace restaurant_robot {

ScenarioRunner::ScenarioRunner(RestaurantMap map, NavigatorConfig navigator_config)
    : map_(std::move(map)), navigator_config_(navigator_config) {}

ScenarioMetrics ScenarioRunner::run(const ScenarioConfig& scenario, const ScanProvider& scan_provider) {
    Navigator navigator(map_, navigator_config_);
    ScenarioMetrics metrics;
    Pose2D pose = scenario.initial_pose;
    metrics.minimum_obstacle_distance = std::numeric_limits<double>::infinity();

    if (!navigator.deliver(scenario.table_goal)) {
        metrics.final_goal_error = distance(pose, scenario.expected_final_pose);
        return metrics;
    }

    for (int step = 0; step < scenario.max_steps; ++step) {
        const double time_s = step * scenario.dt_s;
        const LaserScan scan = scan_provider(pose, time_s, step);
        const auto result = navigator.update(pose, scan, scenario.dt_s);

        metrics.steps = step + 1;
        metrics.elapsed_time_s = (step + 1) * scenario.dt_s;
        metrics.replanning_events = result.replanning_events;

        if (result.mission_complete) {
            metrics.mission_success = true;
            break;
        }

        metrics.minimum_obstacle_distance = std::min(metrics.minimum_obstacle_distance, result.minimum_obstacle_distance);

        if (result.minimum_obstacle_distance <= scenario.collision_distance_m) {
            ++metrics.collision_count;
        }

        pose.x += result.command.linear * std::cos(pose.theta) * scenario.dt_s;
        pose.y += result.command.linear * std::sin(pose.theta) * scenario.dt_s;
        pose.theta = normalizeAngle(pose.theta + result.command.angular * scenario.dt_s);
    }

    metrics.final_goal_error = distance(pose, scenario.expected_final_pose);
    metrics.final_pose = pose;
    if (!std::isfinite(metrics.minimum_obstacle_distance)) {
        metrics.minimum_obstacle_distance = 0.0;
    }
    return metrics;
}

LaserScan makeUniformScan(double range_m, double timestamp_s, int samples, double max_range_m) {
    LaserScan scan;
    scan.angle_min = -kPi;
    scan.angle_increment = samples > 1 ? 2.0 * kPi / static_cast<double>(samples - 1) : 0.0;
    scan.max_range = max_range_m;
    scan.timestamp = timestamp_s;
    scan.ranges.assign(samples, range_m);
    return scan;
}

}  // namespace restaurant_robot
