#pragma once

#include "restaurant_robot/common/types.hpp"

namespace restaurant_robot {

class WheelImuOdometry {
public:
    WheelImuOdometry(double wheel_radius_m, double wheel_separation_m, double imu_yaw_weight = 0.15);

    void reset(const Pose2D& pose, const EncoderData& encoders);
    Pose2D update(const EncoderData& encoders, const ImuData& imu);
    Pose2D pose() const { return pose_; }

private:
    double wheel_radius_m_{0.033};
    double wheel_separation_m_{0.16};
    double imu_yaw_weight_{0.15};
    bool initialized_{false};
    EncoderData previous_{};
    Pose2D pose_{};
};

}  // namespace restaurant_robot
