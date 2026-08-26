#include "restaurant_robot/planning/inflation.hpp"

#include <cmath>

namespace restaurant_robot {

OccupancyGrid inflateObstacles(const OccupancyGrid& input, double inflation_radius_m) {
    OccupancyGrid inflated = input;
    const int radius_cells = static_cast<int>(std::ceil(inflation_radius_m / input.resolution()));

    for (int y = 0; y < input.height(); ++y) {
        for (int x = 0; x < input.width(); ++x) {
            if (input.get(x, y) != kOccupied) {
                continue;
            }

            for (int dy = -radius_cells; dy <= radius_cells; ++dy) {
                for (int dx = -radius_cells; dx <= radius_cells; ++dx) {
                    const double d = std::hypot(dx * input.resolution(), dy * input.resolution());
                    if (d <= inflation_radius_m) {
                        inflated.set(x + dx, y + dy, kOccupied);
                    }
                }
            }
        }
    }

    return inflated;
}

}  // namespace restaurant_robot
