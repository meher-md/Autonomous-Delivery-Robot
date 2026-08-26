#include "restaurant_robot/safety/safety_supervisor.hpp"

#include <algorithm>
#include <cmath>
#include <limits>

namespace restaurant_robot {

SafetySupervisor::SafetySupervisor(SafetyConfig config) : config_(config) {}

void SafetySupervisor::configure(SafetyConfig config) {
    config_ = config;
}

void SafetySupervisor::setEmergencyStop(bool enabled) {
    emergency_stop_ = enabled;
}

SafetyResult SafetySupervisor::apply(const VelocityCommand& requested, const LaserScan& scan) const {
    if (emergency_stop_) {
        return {VelocityCommand{}, SafetyState::EmergencyStop, 0.0};
    }

    double front_min = std::numeric_limits<double>::infinity();
    double front_stop_min = std::numeric_limits<double>::infinity();
    double rear_min = std::numeric_limits<double>::infinity();
    double angle = scan.angle_min;
    for (double range : scan.ranges) {
        if (range > 0.02 && range < scan.max_range) {
            const double normalized = normalizeAngle(angle);
            if (std::abs(normalized) <= config_.front_angle_limit_rad) {
                front_min = std::min(front_min, range);
                if (std::abs(normalized) <= config_.front_stop_angle_limit_rad) {
                    front_stop_min = std::min(front_stop_min, range);
                }
            } else {
                rear_min = std::min(rear_min, range);
            }
        }
        angle += scan.angle_increment;
    }

    const double min_distance = std::min(front_min, rear_min);
    if (front_stop_min <= config_.front_stop_distance || rear_min <= config_.rear_stop_distance) {
        return {VelocityCommand{}, SafetyState::Stop, min_distance};
    }

    VelocityCommand command = requested;
    if (front_min <= config_.front_caution_distance || rear_min <= config_.rear_caution_distance) {
        command.linear = std::clamp(command.linear, -config_.caution_max_velocity, config_.caution_max_velocity);
        return {command, SafetyState::Caution, min_distance};
    }

    return {command, SafetyState::Normal, std::isfinite(min_distance) ? min_distance : scan.max_range};
}

std::string toString(SafetyState state) {
    switch (state) {
        case SafetyState::Normal:
            return "NORMAL";
        case SafetyState::Caution:
            return "CAUTION";
        case SafetyState::Stop:
            return "STOP";
        case SafetyState::EmergencyStop:
            return "EMERGENCY_STOP";
    }
    return "UNKNOWN";
}

}  // namespace restaurant_robot
