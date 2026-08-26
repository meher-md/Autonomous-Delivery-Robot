#include <iostream>
#include <string>

#include "restaurant_robot/mapping/restaurant_map_factory.hpp"
#include "restaurant_robot/simulation/scenario_runner.hpp"

using namespace restaurant_robot;

int main(int argc, char** argv) {
    std::string table = "TABLE_3";
    if (argc > 1) {
        table = argv[1];
    }
    int max_steps = 1800;
    if (argc > 2) {
        max_steps = std::stoi(argv[2]);
    }

    const auto map = createPrototypeRestaurantMap(0.10);
    ScenarioRunner runner(map);

    ScenarioConfig scenario;
    scenario.initial_pose = map.destinations.at("HOME");
    scenario.expected_final_pose = map.destinations.at("KITCHEN");
    scenario.table_goal = table;
    scenario.max_steps = max_steps;

    const auto metrics = runner.run(
        scenario,
        [](const Pose2D&, double time_s, int) {
            return makeUniformScan(6.0, time_s);
        });

    std::cout << "scenario_goal=" << table << "\n";
    std::cout << "mission_success=" << (metrics.mission_success ? "true" : "false") << "\n";
    std::cout << "collision_count=" << metrics.collision_count << "\n";
    std::cout << "replanning_events=" << metrics.replanning_events << "\n";
    std::cout << "minimum_obstacle_distance_m=" << metrics.minimum_obstacle_distance << "\n";
    std::cout << "final_goal_error_m=" << metrics.final_goal_error << "\n";
    std::cout << "final_pose_x=" << metrics.final_pose.x << "\n";
    std::cout << "final_pose_y=" << metrics.final_pose.y << "\n";
    std::cout << "final_pose_theta=" << metrics.final_pose.theta << "\n";
    std::cout << "elapsed_time_s=" << metrics.elapsed_time_s << "\n";
    std::cout << "steps=" << metrics.steps << "\n";

    return metrics.mission_success && metrics.collision_count == 0 ? 0 : 1;
}
