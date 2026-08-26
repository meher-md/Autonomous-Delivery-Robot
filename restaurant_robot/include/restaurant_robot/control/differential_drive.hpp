#pragma once

#include "restaurant_robot/common/types.hpp"

namespace restaurant_robot {

class DifferentialDriveKinematics {
public:
    DifferentialDriveKinematics(double wheel_radius_m, double wheel_separation_m);

    WheelVelocities toWheelAngularVelocities(const VelocityCommand& command) const;
    VelocityCommand fromWheelAngularVelocities(double left_wheel_rad_s, double right_wheel_rad_s) const;

    double wheelRadius() const { return wheel_radius_m_; }
    double wheelSeparation() const { return wheel_separation_m_; }

private:
    double wheel_radius_m_{0.033};
    double wheel_separation_m_{0.16};
};

}  // namespace restaurant_robot
