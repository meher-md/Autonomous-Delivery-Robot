#include "restaurant_robot/mission/delivery_manager.hpp"

#include <cmath>
#include <utility>

namespace restaurant_robot {

DeliveryManager::DeliveryManager(std::map<std::string, Pose2D> destinations)
    : destinations_(std::move(destinations)) {}

bool DeliveryManager::deliver(const std::string& table_name) {
    if (!destination(table_name) || !destination("KITCHEN")) {
        return false;
    }
    requested_table_ = table_name;
    direct_destination_.clear();
    state_ = MissionState::GoToKitchen;
    active_destination_.clear();
    wait_timer_s_ = 0.0;
    return true;
}

bool DeliveryManager::goToDestination(const std::string& destination_name) {
    if (!destination(destination_name)) {
        return false;
    }
    requested_table_.clear();
    direct_destination_ = destination_name;
    state_ = MissionState::GoToNamedDestination;
    active_destination_.clear();
    wait_timer_s_ = 0.0;
    return true;
}

MissionOutput DeliveryManager::update(const Pose2D& pose, bool planner_has_path, double dt_s) {
    MissionOutput output;

    if ((state_ == MissionState::GoToKitchen || state_ == MissionState::GoToTable ||
         state_ == MissionState::ReturnKitchen || state_ == MissionState::GoToNamedDestination) &&
        !planner_has_path && !active_destination_.empty()) {
        state_ = MissionState::NoPath;
        return output;
    }

    switch (state_) {
        case MissionState::Idle:
        case MissionState::Complete:
        case MissionState::NoPath:
            return output;
        case MissionState::GoToKitchen:
            if (active_destination_ != "KITCHEN") {
                setGoal("KITCHEN", output);
            } else if (reached(pose, *destination("KITCHEN"))) {
                state_ = MissionState::WaitForLoading;
                wait_timer_s_ = 0.0;
            }
            break;
        case MissionState::WaitForLoading:
            wait_timer_s_ += dt_s;
            if (wait_timer_s_ >= wait_duration_s_) {
                state_ = MissionState::GoToTable;
                active_destination_.clear();
                setGoal(requested_table_, output);
            }
            break;
        case MissionState::GoToTable:
            if (active_destination_ != requested_table_) {
                setGoal(requested_table_, output);
            } else if (reached(pose, *destination(requested_table_))) {
                state_ = MissionState::Arrived;
            }
            break;
        case MissionState::Arrived:
            state_ = MissionState::WaitForCollection;
            wait_timer_s_ = dt_s;
            if (wait_timer_s_ >= wait_duration_s_) {
                state_ = MissionState::ReturnKitchen;
                active_destination_.clear();
                setGoal("KITCHEN", output);
            }
            break;
        case MissionState::WaitForCollection:
            wait_timer_s_ += dt_s;
            if (wait_timer_s_ >= wait_duration_s_) {
                state_ = MissionState::ReturnKitchen;
                active_destination_.clear();
                setGoal("KITCHEN", output);
            }
            break;
        case MissionState::ReturnKitchen:
            if (active_destination_ != "KITCHEN") {
                setGoal("KITCHEN", output);
            } else if (reached(pose, *destination("KITCHEN"))) {
                state_ = MissionState::Complete;
                output.mission_complete = true;
            }
            break;
        case MissionState::GoToNamedDestination:
            if (active_destination_ != direct_destination_) {
                setGoal(direct_destination_, output);
            } else if (reached(pose, *destination(direct_destination_))) {
                state_ = MissionState::Complete;
                output.mission_complete = true;
            }
            break;
    }

    return output;
}

bool DeliveryManager::reached(const Pose2D& pose, const Pose2D& goal) const {
    return distance(pose, goal) <= position_tolerance_m_;
}

std::optional<Pose2D> DeliveryManager::destination(const std::string& name) const {
    const auto it = destinations_.find(name);
    if (it == destinations_.end()) {
        return std::nullopt;
    }
    return it->second;
}

void DeliveryManager::setGoal(const std::string& name, MissionOutput& output) {
    auto pose = destination(name);
    if (!pose) {
        state_ = MissionState::NoPath;
        return;
    }
    active_destination_ = name;
    output.active_goal = *pose;
    output.new_goal = true;
}

std::string toString(MissionState state) {
    switch (state) {
        case MissionState::Idle:
            return "IDLE";
        case MissionState::GoToKitchen:
            return "GO_TO_KITCHEN";
        case MissionState::WaitForLoading:
            return "WAIT_FOR_LOADING";
        case MissionState::GoToTable:
            return "GO_TO_TABLE";
        case MissionState::Arrived:
            return "ARRIVED";
        case MissionState::WaitForCollection:
            return "WAIT_FOR_COLLECTION";
        case MissionState::ReturnKitchen:
            return "RETURN_KITCHEN";
        case MissionState::GoToNamedDestination:
            return "GO_TO_NAMED_DESTINATION";
        case MissionState::Complete:
            return "COMPLETE";
        case MissionState::NoPath:
            return "NO_PATH";
    }
    return "UNKNOWN";
}

}  // namespace restaurant_robot
