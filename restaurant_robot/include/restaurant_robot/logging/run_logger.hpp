#pragma once

#include <fstream>
#include <string>

#include "restaurant_robot/common/types.hpp"
#include "restaurant_robot/safety/safety_supervisor.hpp"

namespace restaurant_robot {

struct RunLogRecord {
    double timestamp{0.0};
    Pose2D robot_pose;
    Pose2D estimated_pose;
    std::string goal;
    std::string requested_destination;
    double linear_velocity{0.0};
    double angular_velocity{0.0};
    double minimum_obstacle_distance{0.0};
    std::string planner_state;
    SafetyState safety_state{SafetyState::Normal};
    int replanning_events{0};
    double distance_to_destination{0.0};
    int collision_count{0};
};

class RunLogger {
public:
    explicit RunLogger(const std::string& path);
    bool isOpen() const;
    void write(const RunLogRecord& record);

private:
    std::ofstream out_;
};

}  // namespace restaurant_robot
