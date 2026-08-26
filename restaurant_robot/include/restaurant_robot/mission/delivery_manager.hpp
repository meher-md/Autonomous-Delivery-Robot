#pragma once

#include <map>
#include <optional>
#include <string>

#include "restaurant_robot/common/types.hpp"

namespace restaurant_robot {

enum class MissionState {
    Idle,
    GoToKitchen,
    WaitForLoading,
    GoToTable,
    Arrived,
    WaitForCollection,
    ReturnKitchen,
    GoToNamedDestination,
    Complete,
    NoPath,
};

struct MissionOutput {
    std::optional<Pose2D> active_goal;
    bool new_goal{false};
    bool mission_complete{false};
};

class DeliveryManager {
public:
    explicit DeliveryManager(std::map<std::string, Pose2D> destinations);

    bool deliver(const std::string& table_name);
    bool deliverDirect(const std::string& table_name);
    bool goToDestination(const std::string& destination_name);
    void cancel();
    MissionOutput update(const Pose2D& pose, bool planner_has_path, double dt_s);

    MissionState state() const { return state_; }
    std::string activeDestinationName() const { return active_destination_; }

private:
    bool reached(const Pose2D& pose, const Pose2D& goal) const;
    std::optional<Pose2D> destination(const std::string& name) const;
    void setGoal(const std::string& name, MissionOutput& output);

    std::map<std::string, Pose2D> destinations_;
    MissionState state_{MissionState::Idle};
    std::string requested_table_;
    std::string direct_destination_;
    std::string active_destination_;
    double wait_timer_s_{0.0};
    double wait_duration_s_{1.0};
    double position_tolerance_m_{0.22};
};

std::string toString(MissionState state);

}  // namespace restaurant_robot
