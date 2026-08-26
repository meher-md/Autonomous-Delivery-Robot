#include "restaurant_robot/obstacle/local_obstacle_map.hpp"

#include <algorithm>
#include <cmath>
#include <utility>

namespace restaurant_robot {
namespace {

double pointToSegmentDistance(const Point2D& point, const Point2D& a, const Point2D& b) {
    const double vx = b.x - a.x;
    const double vy = b.y - a.y;
    const double wx = point.x - a.x;
    const double wy = point.y - a.y;
    const double length2 = vx * vx + vy * vy;
    if (length2 <= 1e-9) {
        return distance(point, a);
    }
    const double t = std::max(0.0, std::min(1.0, (wx * vx + wy * vy) / length2));
    const Point2D projection{a.x + t * vx, a.y + t * vy};
    return distance(point, projection);
}

bool nearStaticObstacle(const OccupancyGrid& static_grid, const Point2D& point, double radius_m) {
    const auto center = static_grid.worldToGrid(point);
    if (!center) {
        return true;
    }
    const int radius_cells = std::max(1, static_cast<int>(std::ceil(radius_m / static_grid.resolution())));
    for (int y = center->y - radius_cells; y <= center->y + radius_cells; ++y) {
        for (int x = center->x - radius_cells; x <= center->x + radius_cells; ++x) {
            if (!static_grid.inBounds(x, y)) {
                return true;
            }
            if (static_grid.get(x, y) == kOccupied &&
                distance(point, static_grid.gridToWorld(x, y)) <= radius_m) {
                return true;
            }
        }
    }
    return false;
}

}  // namespace

LocalObstacleMap::LocalObstacleMap(double size_m, double resolution_m, double obstacle_timeout_s)
    : size_m_(size_m), resolution_m_(resolution_m), obstacle_timeout_s_(obstacle_timeout_s) {}

void LocalObstacleMap::updateFromScan(const Pose2D& robot_pose, const LaserScan& scan) {
    updateFromScan(robot_pose, scan, nullptr);
}

void LocalObstacleMap::updateFromScan(const Pose2D& robot_pose, const LaserScan& scan, const OccupancyGrid& static_grid) {
    updateFromScan(robot_pose, scan, &static_grid);
}

void LocalObstacleMap::updateFromScan(const Pose2D& robot_pose, const LaserScan& scan, const OccupancyGrid* static_grid) {
    double angle = scan.angle_min;
    for (double range : scan.ranges) {
        if (range > 0.02 && range < scan.max_range) {
            const double world_angle = normalizeAngle(robot_pose.theta + angle);
            Point2D point{
                robot_pose.x + range * std::cos(world_angle),
                robot_pose.y + range * std::sin(world_angle),
            };
            if (static_grid) {
                const auto cell = static_grid->worldToGrid(point);
                if (!cell || static_grid->get(cell->x, cell->y) != kFree ||
                    nearStaticObstacle(*static_grid, point, 0.18)) {
                    angle += scan.angle_increment;
                    continue;
                }
            }

            bool updated = false;
            for (auto& obstacle : obstacles_) {
                if (distance(obstacle.point, point) <= resolution_m_ * 2.0) {
                    obstacle.point = point;
                    obstacle.last_seen_s = scan.timestamp;
                    updated = true;
                    break;
                }
            }
            if (!updated) {
                obstacles_.push_back(TimedObstacle{point, scan.timestamp});
            }
        }
        angle += scan.angle_increment;
    }

    decay(scan.timestamp);
}

void LocalObstacleMap::decay(double now_s) {
    std::vector<TimedObstacle> kept;
    kept.reserve(obstacles_.size());
    for (const auto& obstacle : obstacles_) {
        if (now_s - obstacle.last_seen_s <= obstacle_timeout_s_) {
            kept.push_back(obstacle);
        }
    }
    obstacles_ = std::move(kept);
}

OccupancyGrid LocalObstacleMap::overlayOnto(const OccupancyGrid& static_grid) const {
    OccupancyGrid combined = static_grid;
    const double radius = size_m_ / 2.0;
    const Point2D origin = static_grid.origin();
    const Point2D max_point{
        origin.x + static_grid.width() * static_grid.resolution(),
        origin.y + static_grid.height() * static_grid.resolution(),
    };

    for (const auto& obstacle : obstacles_) {
        if (obstacle.point.x < origin.x - radius || obstacle.point.y < origin.y - radius ||
            obstacle.point.x > max_point.x + radius || obstacle.point.y > max_point.y + radius) {
            continue;
        }
        auto cell = combined.worldToGrid(obstacle.point);
        if (cell) {
            combined.set(cell->x, cell->y, kOccupied);
        }
    }
    return combined;
}

bool LocalObstacleMap::obstacleNearPath(const Path& path, double radius_m) const {
    if (path.points.empty()) {
        return false;
    }

    for (const auto& obstacle : obstacles_) {
        for (std::size_t i = 0; i + 1 < path.points.size(); ++i) {
            if (pointToSegmentDistance(obstacle.point, path.points[i], path.points[i + 1]) <= radius_m) {
                return true;
            }
        }
        if (path.points.size() == 1 && distance(obstacle.point, path.points.front()) <= radius_m) {
            return true;
        }
    }
    return false;
}

int LocalObstacleMap::activeObstacleCount() const {
    return static_cast<int>(obstacles_.size());
}

}  // namespace restaurant_robot
