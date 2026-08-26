#include "restaurant_robot/estimation/odometry.hpp"

#include <cmath>

namespace restaurant_robot {

WheelImuOdometry::WheelImuOdometry(double wheel_radius_m, double wheel_separation_m, double imu_yaw_weight)
    : wheel_radius_m_(wheel_radius_m),
      wheel_separation_m_(wheel_separation_m),
      imu_yaw_weight_(imu_yaw_weight) {}

void WheelImuOdometry::reset(const Pose2D& pose, const EncoderData& encoders) {
    pose_ = pose;
    previous_ = encoders;
    initialized_ = true;
}

Pose2D WheelImuOdometry::update(const EncoderData& encoders, const ImuData& imu) {
    if (!initialized_) {
        reset(Pose2D{}, encoders);
        return pose_;
    }

    const double d_left = (encoders.left_wheel_angle - previous_.left_wheel_angle) * wheel_radius_m_;
    const double d_right = (encoders.right_wheel_angle - previous_.right_wheel_angle) * wheel_radius_m_;
    previous_ = encoders;

    const double distance_center = (d_right + d_left) / 2.0;
    const double dtheta_enc = (d_right - d_left) / wheel_separation_m_;
    const double theta_mid = pose_.theta + dtheta_enc / 2.0;
    pose_.x += distance_center * std::cos(theta_mid);
    pose_.y += distance_center * std::sin(theta_mid);

    const double fused_yaw = normalizeAngle((1.0 - imu_yaw_weight_) * normalizeAngle(pose_.theta + dtheta_enc) +
                                           imu_yaw_weight_ * imu.yaw);
    pose_.theta = fused_yaw;
    return pose_;
}

}  // namespace restaurant_robot
