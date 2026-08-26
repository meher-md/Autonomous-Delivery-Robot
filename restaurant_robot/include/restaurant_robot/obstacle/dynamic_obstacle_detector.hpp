#pragma once

#include <vector>

#include "restaurant_robot/common/types.hpp"
#include "restaurant_robot/planning/occupancy_grid.hpp"

namespace restaurant_robot {

class DynamicObstacleDetector {
public:
    std::vector<Point2D> detectFreeSpaceObstacles(
        const OccupancyGrid& static_grid,
        const Pose2D& robot_pose,
        const LaserScan& scan) const;
};

}  // namespace restaurant_robot
