#pragma once

#include <functional>
#include <string>

#include "restaurant_robot/navigation/navigator.hpp"

namespace restaurant_robot {

struct ScenarioMetrics {
    bool mission_success{false};
    int steps{0};
    int collision_count{0};
    int replanning_events{0};
    double minimum_obstacle_distance{0.0};
    double final_goal_error{0.0};
    double elapsed_time_s{0.0};
    Pose2D final_pose;
};

using ScanProvider = std::function<LaserScan(const Pose2D& pose, double time_s, int step)>;

struct ScenarioConfig {
    double dt_s{0.1};
    int max_steps{1500};
    double collision_distance_m{0.18};
    Pose2D initial_pose{0.0, 0.0, 0.0};
    Pose2D expected_final_pose{0.0, 0.0, 0.0};
    std::string table_goal{"TABLE_3"};
};

class ScenarioRunner {
public:
    ScenarioRunner(RestaurantMap map, NavigatorConfig navigator_config = {});

    ScenarioMetrics run(const ScenarioConfig& scenario, const ScanProvider& scan_provider);

private:
    RestaurantMap map_;
    NavigatorConfig navigator_config_;
};

LaserScan makeUniformScan(double range_m, double timestamp_s, int samples = 181, double max_range_m = 6.0);

}  // namespace restaurant_robot
