#include "restaurant_robot/control/pure_pursuit.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <vector>

namespace restaurant_robot {

PurePursuitController::PurePursuitController(PurePursuitConfig config) : config_(config) {}

VelocityCommand PurePursuitController::computeCommand(const Path& path, const Pose2D& pose) const {
    const auto maybe_target = selectLookaheadTarget(path, pose);
    if (!maybe_target) {
        return {};
    }
    const Point2D target = *maybe_target;
    const Point2D robot{pose.x, pose.y};
    const Point2D goal = path.points.back();
    const double distance_to_goal = distance(robot, goal);

    const double dx = target.x - pose.x;
    const double dy = target.y - pose.y;
    const double cos_t = std::cos(pose.theta);
    const double sin_t = std::sin(pose.theta);
    const double target_x_robot = cos_t * dx + sin_t * dy;
    const double target_y_robot = -sin_t * dx + cos_t * dy;
    const double heading_error = normalizeAngle(std::atan2(dy, dx) - pose.theta);

    if (target_x_robot < 0.0) {
        const double angular = std::clamp(heading_error, -config_.max_angular_velocity, config_.max_angular_velocity);
        return VelocityCommand{0.0, angular};
    }

    const double ld2 = std::max(0.001, target_x_robot * target_x_robot + target_y_robot * target_y_robot);
    const double curvature = 2.0 * target_y_robot / ld2;

    double linear = config_.max_linear_velocity;
    if (distance_to_goal < config_.goal_slowdown_distance) {
        linear *= std::max(0.25, distance_to_goal / config_.goal_slowdown_distance);
    }
    double angular = curvature * linear;
    angular = std::clamp(angular, -config_.max_angular_velocity, config_.max_angular_velocity);
    return VelocityCommand{linear, angular};
}

std::optional<Point2D> PurePursuitController::selectLookaheadTarget(const Path& path, const Pose2D& pose) const {
    if (path.points.empty()) {
        return std::nullopt;
    }

    const Point2D robot{pose.x, pose.y};
    const Point2D goal = path.points.back();
    const double distance_to_goal = distance(robot, goal);
    if (distance_to_goal < config_.goal_tolerance) {
        return std::nullopt;
    }
    if (path.points.size() == 1) {
        return goal;
    }

    std::vector<double> cumulative(path.points.size(), 0.0);
    for (std::size_t i = 1; i < path.points.size(); ++i) {
        cumulative[i] = cumulative[i - 1] + distance(path.points[i - 1], path.points[i]);
    }

    double nearest_path_s = 0.0;
    double nearest_distance_sq = std::numeric_limits<double>::infinity();
    for (std::size_t i = 0; i + 1 < path.points.size(); ++i) {
        const Point2D& a = path.points[i];
        const Point2D& b = path.points[i + 1];
        const double vx = b.x - a.x;
        const double vy = b.y - a.y;
        const double length_sq = vx * vx + vy * vy;
        if (length_sq <= 1e-9) {
            continue;
        }
        const double t = std::clamp(((robot.x - a.x) * vx + (robot.y - a.y) * vy) / length_sq, 0.0, 1.0);
        const Point2D projection{a.x + t * vx, a.y + t * vy};
        const double dx = robot.x - projection.x;
        const double dy = robot.y - projection.y;
        const double dist_sq = dx * dx + dy * dy;
        if (dist_sq < nearest_distance_sq) {
            nearest_distance_sq = dist_sq;
            nearest_path_s = cumulative[i] + std::sqrt(length_sq) * t;
        }
    }

    const double target_path_s = std::min(cumulative.back(), nearest_path_s + config_.lookahead_distance);
    for (std::size_t i = 0; i + 1 < path.points.size(); ++i) {
        if (target_path_s > cumulative[i + 1]) {
            continue;
        }
        const double segment_length = std::max(1e-9, cumulative[i + 1] - cumulative[i]);
        const double t = std::clamp((target_path_s - cumulative[i]) / segment_length, 0.0, 1.0);
        return Point2D{
            path.points[i].x + (path.points[i + 1].x - path.points[i].x) * t,
            path.points[i].y + (path.points[i + 1].y - path.points[i].y) * t,
        };
    }

    return goal;
}

}  // namespace restaurant_robot
