#pragma once

#include <vector>

#include "restaurant_robot/common/types.hpp"
#include "restaurant_robot/planning/occupancy_grid.hpp"

namespace restaurant_robot {

class LocalObstacleMap {
public:
    LocalObstacleMap(double size_m, double resolution_m, double obstacle_timeout_s);

    void updateFromScan(const Pose2D& robot_pose, const LaserScan& scan);
    void updateFromScan(const Pose2D& robot_pose, const LaserScan& scan, const OccupancyGrid& static_grid);
    void decay(double now_s);
    OccupancyGrid overlayOnto(const OccupancyGrid& static_grid) const;
    bool obstacleNearPath(const Path& path, double radius_m) const;
    int activeObstacleCount() const;

private:
    struct TimedObstacle {
        Point2D point;
        double last_seen_s{0.0};
    };

    void updateFromScan(const Pose2D& robot_pose, const LaserScan& scan, const OccupancyGrid* static_grid);

    double size_m_{6.0};
    double resolution_m_{0.05};
    double obstacle_timeout_s_{2.0};
    std::vector<TimedObstacle> obstacles_;
};

}  // namespace restaurant_robot
