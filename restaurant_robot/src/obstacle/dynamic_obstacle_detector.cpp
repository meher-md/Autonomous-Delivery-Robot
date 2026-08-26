#include "restaurant_robot/obstacle/dynamic_obstacle_detector.hpp"

#include <cmath>

namespace restaurant_robot {

std::vector<Point2D> DynamicObstacleDetector::detectFreeSpaceObstacles(
    const OccupancyGrid& static_grid,
    const Pose2D& robot_pose,
    const LaserScan& scan) const {
    std::vector<Point2D> obstacles;
    double angle = scan.angle_min;
    for (double range : scan.ranges) {
        if (range > 0.02 && range < scan.max_range) {
            const double world_angle = normalizeAngle(robot_pose.theta + angle);
            const Point2D point{
                robot_pose.x + range * std::cos(world_angle),
                robot_pose.y + range * std::sin(world_angle),
            };
            const auto cell = static_grid.worldToGrid(point);
            if (cell && static_grid.get(cell->x, cell->y) == kFree) {
                obstacles.push_back(point);
            }
        }
        angle += scan.angle_increment;
    }
    return obstacles;
}

}  // namespace restaurant_robot
