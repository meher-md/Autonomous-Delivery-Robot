#include "restaurant_robot/mapping/restaurant_map_factory.hpp"

#include <cmath>

namespace restaurant_robot {
namespace {

void fillRect(OccupancyGrid& grid, double min_x, double min_y, double max_x, double max_y, std::uint8_t value) {
    const auto a = grid.worldToGrid(Point2D{min_x, min_y});
    const auto b = grid.worldToGrid(Point2D{max_x, max_y});
    if (!a || !b) {
        return;
    }
    for (int y = std::min(a->y, b->y); y <= std::max(a->y, b->y); ++y) {
        for (int x = std::min(a->x, b->x); x <= std::max(a->x, b->x); ++x) {
            grid.set(x, y, value);
        }
    }
}

void fillCircle(OccupancyGrid& grid, double cx, double cy, double radius, std::uint8_t value) {
    const int radius_cells = static_cast<int>(std::ceil(radius / grid.resolution()));
    const auto center = grid.worldToGrid(Point2D{cx, cy});
    if (!center) {
        return;
    }
    for (int dy = -radius_cells; dy <= radius_cells; ++dy) {
        for (int dx = -radius_cells; dx <= radius_cells; ++dx) {
            if (std::hypot(dx * grid.resolution(), dy * grid.resolution()) <= radius) {
                grid.set(center->x + dx, center->y + dy, value);
            }
        }
    }
}

}  // namespace

RestaurantMap createPrototypeRestaurantMap(double resolution_m) {
    OccupancyGrid grid(
        static_cast<int>(std::round(9.0 / resolution_m)),
        static_cast<int>(std::round(9.0 / resolution_m)),
        resolution_m,
        Point2D{-0.5, -0.5},
        kFree);

    fillRect(grid, -0.5, -0.5, 8.5, -0.35, kOccupied);
    fillRect(grid, -0.5, 8.35, 8.5, 8.5, kOccupied);
    fillRect(grid, -0.5, -0.5, -0.35, 8.5, kOccupied);
    fillRect(grid, 8.35, -0.5, 8.5, 8.5, kOccupied);

    // Kitchen counter and serving/loading station.
    fillRect(grid, 0.0, 6.4, 2.4, 8.0, kOccupied);
    fillRect(grid, 2.0, 7.2, 3.0, 8.0, kOccupied);

    // Five compact dining tables with chair clusters.
    fillCircle(grid, 2.0, 2.0, 0.32, kOccupied);
    fillCircle(grid, 4.3, 2.1, 0.32, kOccupied);
    fillCircle(grid, 6.4, 2.0, 0.32, kOccupied);
    fillCircle(grid, 3.1, 5.0, 0.32, kOccupied);
    fillCircle(grid, 6.2, 5.2, 0.32, kOccupied);

    fillRect(grid, 1.55, 1.48, 2.45, 1.62, kOccupied);
    fillRect(grid, 3.85, 1.58, 4.75, 1.72, kOccupied);
    fillRect(grid, 5.95, 1.48, 6.85, 1.62, kOccupied);
    fillRect(grid, 2.65, 4.48, 3.55, 4.62, kOccupied);
    fillRect(grid, 5.75, 4.68, 6.65, 4.82, kOccupied);

    // A narrow divider creates a corridor while leaving alternate routing around it.
    fillRect(grid, 4.9, 3.35, 5.25, 6.5, kOccupied);
    fillRect(grid, 5.25, 6.15, 6.7, 6.5, kOccupied);

    RestaurantMap map;
    map.grid = grid;
    map.destinations = {
        {"HOME", Pose2D{0.8, 0.8, 0.0}},
        {"KITCHEN", Pose2D{2.4, 5.75, kPi / 2.0}},
        {"TABLE_1", Pose2D{2.0, 2.85, -kPi / 2.0}},
        {"TABLE_2", Pose2D{4.3, 2.95, -kPi / 2.0}},
        {"TABLE_3", Pose2D{6.4, 3.15, -kPi / 2.0}},
        {"TABLE_4", Pose2D{3.1, 5.85, -kPi / 2.0}},
        {"TABLE_5", Pose2D{7.25, 5.45, kPi}},
    };
    return map;
}

}  // namespace restaurant_robot
