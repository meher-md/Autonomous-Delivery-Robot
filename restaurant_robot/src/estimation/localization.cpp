#include "restaurant_robot/estimation/localization.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <utility>

namespace restaurant_robot {

ScanMapLocalizer::ScanMapLocalizer(OccupancyGrid map, ScanMapLocalizationConfig config)
    : map_(std::move(map)), config_(config) {}

Pose2D ScanMapLocalizer::update(const Pose2D& predicted_pose, const LaserScan& scan) {
    Pose2D best = predicted_pose;
    const double predicted_score = scorePose(predicted_pose, scan);
    double best_score = -std::numeric_limits<double>::infinity();

    for (double dy = -config_.search_xy_radius_m; dy <= config_.search_xy_radius_m + 1e-9;
         dy += config_.search_xy_step_m) {
        for (double dx = -config_.search_xy_radius_m; dx <= config_.search_xy_radius_m + 1e-9;
             dx += config_.search_xy_step_m) {
            for (double dt = -config_.search_theta_radius_rad; dt <= config_.search_theta_radius_rad + 1e-9;
                 dt += config_.search_theta_step_rad) {
                const Pose2D candidate{
                    predicted_pose.x + dx,
                    predicted_pose.y + dy,
                    normalizeAngle(predicted_pose.theta + dt),
                };
                const double score = scorePose(candidate, scan);
                if (score > best_score) {
                    best_score = score;
                    best = candidate;
                }
            }
        }
    }

    if (best_score < predicted_score + config_.minimum_score_improvement) {
        return predicted_pose;
    }

    const double gain = std::clamp(config_.correction_gain, 0.0, 1.0);
    double dx = gain * (best.x - predicted_pose.x);
    double dy = gain * (best.y - predicted_pose.y);
    const double translation = std::hypot(dx, dy);
    if (translation > config_.max_translation_correction_m && translation > 1e-9) {
        const double scale = config_.max_translation_correction_m / translation;
        dx *= scale;
        dy *= scale;
    }
    const double dtheta = std::clamp(
        gain * normalizeAngle(best.theta - predicted_pose.theta),
        -config_.max_rotation_correction_rad,
        config_.max_rotation_correction_rad);
    return Pose2D{
        predicted_pose.x + dx,
        predicted_pose.y + dy,
        normalizeAngle(predicted_pose.theta + dtheta),
    };
}

double ScanMapLocalizer::scorePose(const Pose2D& pose, const LaserScan& scan) const {
    if (scan.ranges.empty()) {
        return -std::numeric_limits<double>::infinity();
    }

    double score = 0.0;
    int used = 0;
    const int max_points = std::max(1, config_.max_scan_points);
    const std::size_t stride = std::max<std::size_t>(1, scan.ranges.size() / static_cast<std::size_t>(max_points));
    for (std::size_t i = 0; i < scan.ranges.size(); i += stride) {
        const double angle = scan.angle_min + static_cast<double>(i) * scan.angle_increment;
        const double range = scan.ranges[i];
        if (range > 0.05 && range < scan.max_range) {
            const double world_angle = normalizeAngle(pose.theta + angle);
            const Point2D endpoint{
                pose.x + range * std::cos(world_angle),
                pose.y + range * std::sin(world_angle),
            };
            const auto cell = map_.worldToGrid(endpoint);
            if (cell) {
                score += occupiedProximityScore(cell->x, cell->y);
            } else {
                score -= 2.0;
            }
            ++used;
        }
    }

    if (used == 0) {
        return -std::numeric_limits<double>::infinity();
    }
    return score / static_cast<double>(used);
}

double ScanMapLocalizer::occupiedProximityScore(int x, int y) const {
    double best = -1.0;
    for (int dy = -2; dy <= 2; ++dy) {
        for (int dx = -2; dx <= 2; ++dx) {
            const int nx = x + dx;
            const int ny = y + dy;
            if (!map_.inBounds(nx, ny)) {
                continue;
            }
            if (map_.get(nx, ny) == kOccupied) {
                const double d = std::hypot(dx, dy);
                best = std::max(best, 3.0 - d);
            } else if (map_.get(nx, ny) == kFree) {
                best = std::max(best, -0.25);
            }
        }
    }
    return best;
}

}  // namespace restaurant_robot
