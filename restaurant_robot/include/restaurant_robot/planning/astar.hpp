#pragma once

#include <string>

#include "restaurant_robot/planning/occupancy_grid.hpp"

namespace restaurant_robot {

enum class PlannerStatus {
    Success,
    StartOutsideMap,
    GoalOutsideMap,
    StartOccupied,
    GoalOccupied,
    NoPath,
};

struct AStarResult {
    PlannerStatus status{PlannerStatus::NoPath};
    Path path;
    int expanded_nodes{0};
};

class AStarPlanner {
public:
    AStarResult plan(const OccupancyGrid& grid, const Pose2D& start, const Pose2D& goal) const;
};

std::string toString(PlannerStatus status);

}  // namespace restaurant_robot
