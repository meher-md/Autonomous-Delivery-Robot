#pragma once

#include "restaurant_robot/common/types.hpp"

namespace restaurant_robot {

class INavigationHardware {
public:
    virtual ~INavigationHardware() = default;

    virtual LaserScan getLaserScan() = 0;
    virtual EncoderData getEncoders() = 0;
    virtual ImuData getImu() = 0;
    virtual void setVelocity(double linear, double angular) = 0;
};

}  // namespace restaurant_robot
