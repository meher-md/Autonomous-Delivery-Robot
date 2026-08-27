#include "restaurant_robot/mapping/restaurant_map_factory.hpp"

#include <cmath>
#include <vector>

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

}  // namespace

RestaurantMap createPrototypeRestaurantMap(double resolution_m) {
    OccupancyGrid grid(
        static_cast<int>(std::round(18.0 / resolution_m)),
        static_cast<int>(std::round(18.0 / resolution_m)),
        resolution_m,
        Point2D{0.0, 0.0},
        kFree);

    fillRect(grid, 0.0, 0.0, 18.0, 0.10, kOccupied);
    fillRect(grid, 0.0, 17.90, 18.0, 18.0, kOccupied);
    fillRect(grid, 0.0, 0.0, 0.10, 18.0, kOccupied);
    fillRect(grid, 17.90, 0.0, 18.0, 18.0, kOccupied);

    // Eight table-and-chair clusters. Each footprint matches the static layout JSON.
    const std::vector<Point2D> table_centers = {
        {2.5, 4.0}, {2.5, 8.0}, {2.5, 12.0}, {8.0, 4.0},
        {15.5, 4.0}, {15.5, 8.0}, {15.5, 12.0}, {12.0, 4.0},
    };
    for (const Point2D& center : table_centers) {
        fillRect(grid, center.x - 1.1, center.y - 0.9, center.x + 1.1, center.y + 0.9, kOccupied);
    }

    // Back and service counters define the kitchen while leaving an approach aisle.
    fillRect(grid, 0.9, 16.0, 5.0, 17.0, kOccupied);
    fillRect(grid, 0.9, 14.1, 5.0, 14.8, kOccupied);

    RestaurantMap map;
    map.grid = grid;
    map.destinations = {
        {"HOME", Pose2D{8.0, 1.2, kPi / 2.0}},
        {"CHARGING", Pose2D{16.3, 16.2, kPi}},
        {"KITCHEN", Pose2D{6.2, 15.5, kPi}},
        {"TABLE_1", Pose2D{4.15, 4.0, kPi}},
        {"TABLE_2", Pose2D{4.15, 8.0, kPi}},
        {"TABLE_3", Pose2D{4.15, 12.0, kPi}},
        {"TABLE_4", Pose2D{8.0, 2.45, kPi / 2.0}},
        {"TABLE_5", Pose2D{13.85, 4.0, 0.0}},
        {"TABLE_6", Pose2D{13.85, 8.0, 0.0}},
        {"TABLE_7", Pose2D{13.85, 12.0, 0.0}},
        {"TABLE_8", Pose2D{12.0, 2.45, kPi / 2.0}},
    };
    return map;
}

}  // namespace restaurant_robot
