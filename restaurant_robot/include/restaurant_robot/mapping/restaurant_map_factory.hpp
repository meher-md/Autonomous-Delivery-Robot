#pragma once

#include <map>

#include "restaurant_robot/planning/occupancy_grid.hpp"

namespace restaurant_robot {

struct RestaurantMap {
    OccupancyGrid grid;
    std::map<std::string, Pose2D> destinations;
};

RestaurantMap createPrototypeRestaurantMap(double resolution_m = 0.10);

}  // namespace restaurant_robot
