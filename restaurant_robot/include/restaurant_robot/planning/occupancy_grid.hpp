#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

#include "restaurant_robot/common/types.hpp"

namespace restaurant_robot {

enum OccupancyValue : std::uint8_t {
    kFree = 0,
    kOccupied = 100,
    kUnknown = 255,
};

struct GridIndex {
    int x{0};
    int y{0};
};

class OccupancyGrid {
public:
    OccupancyGrid() = default;
    OccupancyGrid(int width, int height, double resolution, Point2D origin, std::uint8_t initial = kUnknown);

    int width() const { return width_; }
    int height() const { return height_; }
    double resolution() const { return resolution_; }
    Point2D origin() const { return origin_; }
    const std::vector<std::uint8_t>& cells() const { return cells_; }
    std::vector<std::uint8_t>& cells() { return cells_; }

    bool inBounds(int x, int y) const;
    int index(int x, int y) const;
    std::uint8_t get(int x, int y) const;
    void set(int x, int y, std::uint8_t value);
    bool isTraversable(int x, int y) const;

    std::optional<GridIndex> worldToGrid(const Point2D& point) const;
    Point2D gridToWorld(int x, int y) const;

    bool savePgm(const std::string& path) const;

private:
    int width_{0};
    int height_{0};
    double resolution_{0.05};
    Point2D origin_{};
    std::vector<std::uint8_t> cells_;
};

}  // namespace restaurant_robot
