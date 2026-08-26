#include "restaurant_robot/mapping/occupancy_ray_mapper.hpp"

#include <algorithm>
#include <cmath>

namespace restaurant_robot {

OccupancyRayMapper::OccupancyRayMapper(RayMappingConfig config)
    : config_(config),
      grid_(
          static_cast<int>(std::round(config.map_width_m / config.resolution_m)),
          static_cast<int>(std::round(config.map_height_m / config.resolution_m)),
          config.resolution_m,
          config.origin,
          kUnknown) {}

void OccupancyRayMapper::integrateScan(const Pose2D& pose, const LaserScan& scan) {
    const Point2D origin{pose.x, pose.y};
    for (std::size_t i = 0; i < scan.ranges.size(); ++i) {
        const double range = scan.ranges[i];
        if (range <= 0.02) {
            continue;
        }

        const double clamped_range = std::min(range, scan.max_range);
        const double beam_angle = normalizeAngle(pose.theta + scan.angle_min + static_cast<double>(i) * scan.angle_increment);
        const bool hit = range < scan.max_range - config_.occupied_endpoint_margin_m;
        const double free_range = hit ? std::max(0.0, range - grid_.resolution()) : clamped_range;
        const Point2D free_end{
            pose.x + free_range * std::cos(beam_angle),
            pose.y + free_range * std::sin(beam_angle),
        };
        traceFreeCells(origin, free_end);

        if (hit) {
            const Point2D endpoint{
                pose.x + range * std::cos(beam_angle),
                pose.y + range * std::sin(beam_angle),
            };
            const auto cell = grid_.worldToGrid(endpoint);
            if (cell) {
                grid_.set(cell->x, cell->y, kOccupied);
            }
        }
    }
}

void OccupancyRayMapper::traceFreeCells(const Point2D& from, const Point2D& to) {
    const auto a = grid_.worldToGrid(from);
    const auto b = grid_.worldToGrid(to);
    if (!a || !b) {
        return;
    }

    int x0 = a->x;
    int y0 = a->y;
    const int x1 = b->x;
    const int y1 = b->y;
    const int dx = std::abs(x1 - x0);
    const int dy = std::abs(y1 - y0);
    const int sx = x0 < x1 ? 1 : -1;
    const int sy = y0 < y1 ? 1 : -1;
    int err = dx - dy;

    while (true) {
        if (grid_.get(x0, y0) != kOccupied) {
            grid_.set(x0, y0, kFree);
        }
        if (x0 == x1 && y0 == y1) {
            break;
        }
        const int e2 = 2 * err;
        if (e2 > -dy) {
            err -= dy;
            x0 += sx;
        }
        if (e2 < dx) {
            err += dx;
            y0 += sy;
        }
        if (!grid_.inBounds(x0, y0)) {
            break;
        }
    }
}

}  // namespace restaurant_robot
