#include "restaurant_robot/control/differential_drive.hpp"

namespace restaurant_robot {

DifferentialDriveKinematics::DifferentialDriveKinematics(double wheel_radius_m, double wheel_separation_m)
    : wheel_radius_m_(wheel_radius_m), wheel_separation_m_(wheel_separation_m) {}

WheelVelocities DifferentialDriveKinematics::toWheelAngularVelocities(const VelocityCommand& command) const {
    const double left_linear = command.linear - command.angular * wheel_separation_m_ / 2.0;
    const double right_linear = command.linear + command.angular * wheel_separation_m_ / 2.0;
    return WheelVelocities{left_linear / wheel_radius_m_, right_linear / wheel_radius_m_};
}

VelocityCommand DifferentialDriveKinematics::fromWheelAngularVelocities(
    double left_wheel_rad_s,
    double right_wheel_rad_s) const {
    const double left_linear = left_wheel_rad_s * wheel_radius_m_;
    const double right_linear = right_wheel_rad_s * wheel_radius_m_;
    return VelocityCommand{
        (right_linear + left_linear) / 2.0,
        (right_linear - left_linear) / wheel_separation_m_,
    };
}

}  // namespace restaurant_robot
