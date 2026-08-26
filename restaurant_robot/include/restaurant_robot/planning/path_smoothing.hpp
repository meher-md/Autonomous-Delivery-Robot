#pragma once

#include "restaurant_robot/planning/occupancy_grid.hpp"

namespace restaurant_robot {

Path simplifyPathLineOfSight(const OccupancyGrid& grid, const Path& path);
Path smoothPathCorners(const OccupancyGrid& grid, const Path& path, double corner_distance_m);
bool hasLineOfSight(const OccupancyGrid& grid, const Point2D& from, const Point2D& to);

}  // namespace restaurant_robot
