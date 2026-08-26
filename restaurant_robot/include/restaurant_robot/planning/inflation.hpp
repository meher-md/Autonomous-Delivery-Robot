#pragma once

#include "restaurant_robot/planning/occupancy_grid.hpp"

namespace restaurant_robot {

OccupancyGrid inflateObstacles(const OccupancyGrid& input, double inflation_radius_m);

}  // namespace restaurant_robot
