#pragma once

#include <string>

#include "restaurant_robot/planning/occupancy_grid.hpp"
#include "restaurant_robot/mapping/restaurant_map_factory.hpp"

namespace restaurant_robot {

bool saveOccupancyGridJson(const OccupancyGrid& grid, const std::string& path);
bool loadOccupancyGridJson(const std::string& path, OccupancyGrid& grid);
bool saveRestaurantMapJson(const RestaurantMap& map, const std::string& path);
bool loadRestaurantMapJson(const std::string& path, RestaurantMap& map);

}  // namespace restaurant_robot
