#include "restaurant_robot/logging/run_logger.hpp"

namespace restaurant_robot {

RunLogger::RunLogger(const std::string& path) : out_(path) {
    if (out_) {
        out_ << "timestamp,robot_x,robot_y,robot_theta,estimated_x,estimated_y,estimated_theta,goal,requested_destination,"
                "linear_velocity,angular_velocity,minimum_obstacle_distance,planner_state,safety_state,"
                "replanning_events,distance_to_destination,collision_count\n";
    }
}

bool RunLogger::isOpen() const {
    return out_.is_open();
}

void RunLogger::write(const RunLogRecord& record) {
    if (!out_) {
        return;
    }
    out_ << record.timestamp << ","
         << record.robot_pose.x << ","
         << record.robot_pose.y << ","
         << record.robot_pose.theta << ","
         << record.estimated_pose.x << ","
         << record.estimated_pose.y << ","
         << record.estimated_pose.theta << ","
         << record.goal << ","
         << record.requested_destination << ","
         << record.linear_velocity << ","
         << record.angular_velocity << ","
         << record.minimum_obstacle_distance << ","
         << record.planner_state << ","
         << toString(record.safety_state) << ","
         << record.replanning_events << ","
         << record.distance_to_destination << ","
         << record.collision_count << "\n";
}

}  // namespace restaurant_robot
