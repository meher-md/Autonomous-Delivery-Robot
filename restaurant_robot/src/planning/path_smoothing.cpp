#include "restaurant_robot/planning/path_smoothing.hpp"

#include <algorithm>
#include <cmath>
#include <vector>

namespace restaurant_robot {
namespace {

bool samePoint(const Point2D& a, const Point2D& b) {
    return distance(a, b) < 1e-6;
}

void appendDistinct(std::vector<Point2D>& points, const Point2D& point) {
    if (points.empty() || !samePoint(points.back(), point)) {
        points.push_back(point);
    }
}

Point2D interpolate(const Point2D& a, const Point2D& b, double t) {
    return Point2D{
        a.x + (b.x - a.x) * t,
        a.y + (b.y - a.y) * t,
    };
}

Point2D quadraticBezier(const Point2D& a, const Point2D& control, const Point2D& b, double t) {
    return interpolate(interpolate(a, control, t), interpolate(control, b, t), t);
}

bool validChain(const OccupancyGrid& grid, const Point2D& start, const std::vector<Point2D>& points) {
    Point2D previous = start;
    for (const auto& point : points) {
        if (!hasLineOfSight(grid, previous, point)) {
            return false;
        }
        previous = point;
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
        if (!grid.isTraversable(x0, y0)) {
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

Path smoothPathCorners(const OccupancyGrid& grid, const Path& path, double corner_distance_m) {
    if (path.points.size() <= 2 || corner_distance_m <= 1e-6) {
        return path;
    }

    Path smoothed;
    smoothed.points.push_back(path.points.front());

    for (std::size_t i = 1; i + 1 < path.points.size(); ++i) {
        const Point2D& previous = path.points[i - 1];
        const Point2D& corner = path.points[i];
        const Point2D& next = path.points[i + 1];
        const double incoming_length = distance(previous, corner);
        const double outgoing_length = distance(corner, next);
        if (incoming_length <= 1e-9 || outgoing_length <= 1e-9) {
            appendDistinct(smoothed.points, corner);
            continue;
        }
        const double trim = std::min({corner_distance_m, incoming_length * 0.45, outgoing_length * 0.45});

        if (trim < grid.resolution()) {
            appendDistinct(smoothed.points, corner);
            continue;
        }

        const Point2D entry{
            corner.x - (corner.x - previous.x) / incoming_length * trim,
            corner.y - (corner.y - previous.y) / incoming_length * trim,
        };
        const Point2D exit{
            corner.x + (next.x - corner.x) / outgoing_length * trim,
            corner.y + (next.y - corner.y) / outgoing_length * trim,
        };
        std::vector<Point2D> candidates;
        candidates.reserve(10);
        candidates.push_back(entry);
        for (int sample = 1; sample <= 8; ++sample) {
            candidates.push_back(quadraticBezier(entry, corner, exit, static_cast<double>(sample) / 9.0));
        }
        candidates.push_back(exit);
        std::vector<Point2D> validation_points = candidates;
        if (i + 2 == path.points.size()) {
            validation_points.push_back(path.points.back());
        }

        if (validChain(grid, smoothed.points.back(), validation_points)) {
            for (const auto& point : candidates) {
                appendDistinct(smoothed.points, point);
            }
        } else {
            appendDistinct(smoothed.points, corner);
        }
    }

    appendDistinct(smoothed.points, path.points.back());
    return smoothed;
}

}  // namespace restaurant_robot
