#pragma once

#include "restaurant_robot/common/types.hpp"
#include "restaurant_robot/planning/occupancy_grid.hpp"

namespace restaurant_robot {

struct RayMappingConfig {
    double map_width_m{18.0};
    double map_height_m{18.0};
    double resolution_m{0.05};
    Point2D origin{0.0, 0.0};
    double occupied_endpoint_margin_m{0.05};
};

class OccupancyRayMapper {
public:
    explicit OccupancyRayMapper(RayMappingConfig config = {});

    void integrateScan(const Pose2D& pose, const LaserScan& scan);
    const OccupancyGrid& grid() const { return grid_; }
    OccupancyGrid& grid() { return grid_; }

private:
    void traceFreeCells(const Point2D& from, const Point2D& to);

    RayMappingConfig config_;
    OccupancyGrid grid_;
};

}  // namespace restaurant_robot
