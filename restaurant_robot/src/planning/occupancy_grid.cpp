#include "restaurant_robot/planning/occupancy_grid.hpp"

#include <cmath>
#include <fstream>

namespace restaurant_robot {

double normalizeAngle(double angle) {
    while (angle > kPi) {
        angle -= 2.0 * kPi;
    }
    while (angle < -kPi) {
        angle += 2.0 * kPi;
    }
    return angle;
}

double distance(const Point2D& a, const Point2D& b) {
    return std::hypot(a.x - b.x, a.y - b.y);
}

double distance(const Pose2D& a, const Pose2D& b) {
    return std::hypot(a.x - b.x, a.y - b.y);
}

OccupancyGrid::OccupancyGrid(int width, int height, double resolution, Point2D origin, std::uint8_t initial)
    : width_(width), height_(height), resolution_(resolution), origin_(origin), cells_(width * height, initial) {}

bool OccupancyGrid::inBounds(int x, int y) const {
    return x >= 0 && y >= 0 && x < width_ && y < height_;
}

int OccupancyGrid::index(int x, int y) const {
    return y * width_ + x;
}

std::uint8_t OccupancyGrid::get(int x, int y) const {
    if (!inBounds(x, y)) {
        return kOccupied;
    }
    return cells_.at(index(x, y));
}

void OccupancyGrid::set(int x, int y, std::uint8_t value) {
    if (inBounds(x, y)) {
        cells_.at(index(x, y)) = value;
    }
}

bool OccupancyGrid::isTraversable(int x, int y) const {
    return inBounds(x, y) && get(x, y) == kFree;
}

std::optional<GridIndex> OccupancyGrid::worldToGrid(const Point2D& point) const {
    const int gx = static_cast<int>(std::floor((point.x - origin_.x) / resolution_));
    const int gy = static_cast<int>(std::floor((point.y - origin_.y) / resolution_));
    if (!inBounds(gx, gy)) {
        return std::nullopt;
    }
    return GridIndex{gx, gy};
}

Point2D OccupancyGrid::gridToWorld(int x, int y) const {
    return Point2D{
        origin_.x + (static_cast<double>(x) + 0.5) * resolution_,
        origin_.y + (static_cast<double>(y) + 0.5) * resolution_,
    };
}

bool OccupancyGrid::savePgm(const std::string& path) const {
    std::ofstream out(path, std::ios::binary);
    if (!out) {
        return false;
    }

    out << "P5\n" << width_ << " " << height_ << "\n255\n";
    for (int y = height_ - 1; y >= 0; --y) {
        for (int x = 0; x < width_; ++x) {
            const auto value = get(x, y);
            unsigned char pixel = 127;
            if (value == kFree) {
                pixel = 255;
            } else if (value == kOccupied) {
                pixel = 0;
            }
            out.write(reinterpret_cast<const char*>(&pixel), 1);
        }
    }
    return true;
}

}  // namespace restaurant_robot
