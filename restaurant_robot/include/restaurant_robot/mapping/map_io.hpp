#pragma once

#include <string>

#include "restaurant_robot/planning/occupancy_grid.hpp"

namespace restaurant_robot {

bool saveOccupancyGridJson(const OccupancyGrid& grid, const std::string& path);
bool loadOccupancyGridJson(const std::string& path, OccupancyGrid& grid);

}  // namespace restaurant_robot
