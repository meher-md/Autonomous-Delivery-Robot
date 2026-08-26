#include "restaurant_robot/planning/path_smoothing.hpp"

#include <cmath>

namespace restaurant_robot {
namespace {

bool hasClearance(const OccupancyGrid& grid, int cx, int cy) {
    for (int y = cy - 1; y <= cy + 1; ++y) {
        for (int x = cx - 1; x <= cx + 1; ++x) {
            if (!grid.isTraversable(x, y)) {
                return false;
            }
        }
    }
    return true;
}

}  // namespace

bool hasLineOfSight(const OccupancyGrid& grid, const Point2D& from, const Point2D& to) {
    const auto a = grid.worldToGrid(from);
    const auto b = grid.worldToGrid(to);
    if (!a || !b) {
        return false;
    }

    int x0 = a->x;
    int y0 = a->y;
    const int x1 = b->x;
    const int y1 = b->y;

    const int dx = std::abs(x1 - x0);
    const int dy = std::abs(y1 - y0);
    const int sx = x0 < x1 ? 1 : -1;
    const int sy = y0 < y1 ? 1 : -1;
    int err = dx - dy;

    while (true) {
        if (!hasClearance(grid, x0, y0)) {
            return false;
        }
        if (x0 == x1 && y0 == y1) {
            return true;
        }
        const int e2 = 2 * err;
        if (e2 > -dy) {
            err -= dy;
            x0 += sx;
        }
        if (e2 < dx) {
            err += dx;
            y0 += sy;
        }
    }
}

Path simplifyPathLineOfSight(const OccupancyGrid& grid, const Path& path) {
    if (path.points.size() <= 2) {
        return path;
    }

    Path simplified;
    simplified.points.push_back(path.points.front());

    std::size_t anchor = 0;
    while (anchor < path.points.size() - 1) {
        std::size_t furthest = anchor + 1;
        for (std::size_t candidate = path.points.size() - 1; candidate > anchor; --candidate) {
            if (hasLineOfSight(grid, path.points[anchor], path.points[candidate])) {
                furthest = candidate;
                break;
            }
        }
        simplified.points.push_back(path.points[furthest]);
        anchor = furthest;
    }

    return simplified;
}

}  // namespace restaurant_robot
