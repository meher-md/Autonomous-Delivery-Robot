#pragma once

#include <string>

#include "restaurant_robot/common/types.hpp"

namespace restaurant_robot {

enum class SafetyState {
    Normal,
    Caution,
    Stop,
    EmergencyStop,
};

struct SafetyConfig {
    double front_caution_distance{1.0};
    double front_stop_distance{0.32};
    double rear_caution_distance{0.5};
    double rear_stop_distance{0.20};
    double caution_max_velocity{0.22};
    double front_angle_limit_rad{kPi / 2.0};
    double front_stop_angle_limit_rad{kPi / 3.0};
};

struct SafetyResult {
    VelocityCommand command;
    SafetyState state{SafetyState::Normal};
    double minimum_obstacle_distance{0.0};
};

class SafetySupervisor {
public:
    explicit SafetySupervisor(SafetyConfig config = {});

    void setEmergencyStop(bool enabled);
    SafetyResult apply(const VelocityCommand& requested, const LaserScan& scan) const;

private:
    SafetyConfig config_;
    bool emergency_stop_{false};
};

std::string toString(SafetyState state);

}  // namespace restaurant_robot
