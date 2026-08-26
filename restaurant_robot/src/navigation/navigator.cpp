#include "restaurant_robot/navigation/navigator.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <optional>
#include <utility>

#include "restaurant_robot/planning/path_smoothing.hpp"

namespace restaurant_robot {
namespace {

std::optional<Point2D> nearestTraversablePoint(const OccupancyGrid& grid, const Pose2D& pose, double max_radius_m) {
    const auto seed = grid.worldToGrid(Point2D{pose.x, pose.y});
    if (!seed) {
        return std::nullopt;
    }
    if (grid.isTraversable(seed->x, seed->y)) {
        return Point2D{pose.x, pose.y};
    }

    const int max_radius_cells = std::max(1, static_cast<int>(std::ceil(max_radius_m / grid.resolution())));
    std::optional<Point2D> best;
    double best_dist_sq = std::numeric_limits<double>::infinity();
    for (int radius = 1; radius <= max_radius_cells; ++radius) {
        for (int y = seed->y - radius; y <= seed->y + radius; ++y) {
            for (int x = seed->x - radius; x <= seed->x + radius; ++x) {
                if (std::max(std::abs(x - seed->x), std::abs(y - seed->y)) != radius || !grid.isTraversable(x, y)) {
                    continue;
                }
                const Point2D candidate = grid.gridToWorld(x, y);
                const double dx = candidate.x - pose.x;
                const double dy = candidate.y - pose.y;
                const double dist_sq = dx * dx + dy * dy;
                if (dist_sq < best_dist_sq) {
                    best_dist_sq = dist_sq;
                    best = candidate;
                }
            }
        }
        if (best) {
            return best;
        }
    }
    return std::nullopt;
}

}  // namespace

Navigator::Navigator(RestaurantMap restaurant_map, NavigatorConfig config)
    : restaurant_map_(std::move(restaurant_map)),
      config_(config),
      footprint_static_grid_(inflateObstacles(restaurant_map_.grid, config_.robot_footprint_radius_m)),
      local_obstacles_(6.0, restaurant_map_.grid.resolution(), 2.0),
      mission_(restaurant_map_.destinations) {}

bool Navigator::deliver(const std::string& table_name) {
    active_path_ = {};
    active_goal_pose_.reset();
    planner_state_ = NavigatorPlannerState::Idle;
    blocked_timer_s_ = 0.0;
    stuck_timer_s_ = 0.0;
    replanning_events_ = 0;
    return mission_.deliver(table_name);
}

bool Navigator::goToDestination(const std::string& destination_name) {
    active_path_ = {};
    active_goal_pose_.reset();
    planner_state_ = NavigatorPlannerState::Idle;
    blocked_timer_s_ = 0.0;
    stuck_timer_s_ = 0.0;
    replanning_events_ = 0;
    return mission_.goToDestination(destination_name);
}

void Navigator::setEmergencyStop(bool enabled) {
    safety_.setEmergencyStop(enabled);
}

NavigatorStepResult Navigator::update(const Pose2D& pose, const LaserScan& scan, double dt_s) {
    local_obstacles_.updateFromScan(pose, scan, restaurant_map_.grid);

    NavigatorStepResult result;
    result.replanning_events = replanning_events_;
    result.active_goal = mission_.activeDestinationName();

    const bool planner_has_path = planner_state_ != NavigatorPlannerState::NoPath;
    const auto mission_output = mission_.update(pose, planner_has_path, dt_s);
    if (mission_output.mission_complete) {
        active_path_ = {};
        active_goal_pose_.reset();
        planner_state_ = NavigatorPlannerState::Idle;
        result.mission_complete = true;
        return result;
    }

    if (mission_output.new_goal && mission_output.active_goal) {
        active_goal_pose_ = *mission_output.active_goal;
        const bool planned = planTo(pose, *active_goal_pose_, false);
        if (!planned) {
            result.no_path = true;
            result.planner_state = planner_state_;
            return result;
        }
    }

    const VelocityCommand requested = tracker_.computeCommand(active_path_, pose);
    const SafetyResult safe = safety_.apply(requested, scan);

    if (active_goal_pose_ && shouldReplan(pose, requested, safe.state, dt_s)) {
        ++replanning_events_;
        planner_state_ = NavigatorPlannerState::Replanning;
        result.replanned = true;
        const bool planned = planTo(pose, *active_goal_pose_, true);
        if (!planned) {
            result.no_path = true;
            result.command = {};
            result.planner_state = planner_state_;
            result.safety_state = safe.state;
            result.minimum_obstacle_distance = safe.minimum_obstacle_distance;
            result.replanning_events = replanning_events_;
            result.distance_to_goal = currentDistanceToGoal(pose);
            return result;
        }
    }

    const SafetyResult final_safe = safety_.apply(tracker_.computeCommand(active_path_, pose), scan);
    result.command = applyStaticFootprintGuard(pose, final_safe.command, dt_s);
    result.safety_state = final_safe.state;
    result.minimum_obstacle_distance = final_safe.minimum_obstacle_distance;
    result.planner_state = planner_state_;
    result.replanning_events = replanning_events_;
    result.distance_to_goal = currentDistanceToGoal(pose);
    result.pure_pursuit_target = tracker_.selectLookaheadTarget(active_path_, pose);
    result.active_goal = mission_.activeDestinationName();
    return result;
}

bool Navigator::planTo(const Pose2D& pose, const Pose2D& goal, bool use_dynamic_obstacles) {
    OccupancyGrid planning_grid = footprint_static_grid_;
    if (use_dynamic_obstacles) {
        planning_grid = inflateObstacles(
            local_obstacles_.overlayOnto(restaurant_map_.grid),
            config_.robot_footprint_radius_m);
    }

    const auto plan = planner_.plan(planning_grid, pose, goal);
    if (plan.status != PlannerStatus::Success) {
        active_path_ = {};
        planner_state_ = NavigatorPlannerState::NoPath;
        return false;
    }

    active_path_ = simplifyPathLineOfSight(planning_grid, plan.path);
    if (!active_path_.points.empty()) {
        active_path_.points.back() = Point2D{goal.x, goal.y};
    }
    planner_state_ = NavigatorPlannerState::PathReady;
    blocked_timer_s_ = 0.0;
    stuck_timer_s_ = 0.0;
    last_progress_pose_ = pose;
    return true;
}

bool Navigator::shouldReplan(
    const Pose2D& pose,
    const VelocityCommand& requested,
    SafetyState safety_state,
    double dt_s) {
    if (active_path_.points.empty()) {
        return false;
    }
    if (safety_state == SafetyState::EmergencyStop) {
        blocked_timer_s_ = 0.0;
        stuck_timer_s_ = 0.0;
        last_progress_pose_ = pose;
        return false;
    }

    const bool blocked_path = local_obstacles_.obstacleNearPath(active_path_, config_.path_obstacle_radius_m);
    const bool stopped_by_safety = safety_state == SafetyState::Stop;
    const bool forward_motion_requested = requested.linear > 0.05;
    if (stopped_by_safety && (blocked_path || forward_motion_requested)) {
        blocked_timer_s_ += dt_s;
    } else {
        blocked_timer_s_ = 0.0;
    }

    if (forward_motion_requested) {
        if (distance(pose, last_progress_pose_) < config_.stuck_motion_threshold_m) {
            stuck_timer_s_ += dt_s;
        } else {
            stuck_timer_s_ = 0.0;
            last_progress_pose_ = pose;
        }
    } else {
        stuck_timer_s_ = 0.0;
        last_progress_pose_ = pose;
    }

    return blocked_timer_s_ >= config_.persistent_blockage_timeout_s || stuck_timer_s_ >= config_.stuck_timeout_s;
}

VelocityCommand Navigator::applyStaticFootprintGuard(const Pose2D& pose, const VelocityCommand& command, double dt_s) const {
    const auto current_cell = footprint_static_grid_.worldToGrid(Point2D{pose.x, pose.y});
    if (!current_cell) {
        return {};
    }
    if (!footprint_static_grid_.isTraversable(current_cell->x, current_cell->y)) {
        const auto escape = nearestTraversablePoint(footprint_static_grid_, pose, 0.90);
        if (!escape) {
            return {};
        }
        const double heading_error = normalizeAngle(std::atan2(escape->y - pose.y, escape->x - pose.x) - pose.theta);
        const double angular = std::clamp(1.6 * heading_error, -0.55, 0.55);
        if (std::abs(heading_error) > 0.35) {
            return VelocityCommand{0.0, angular};
        }
        return VelocityCommand{0.08, angular};
    }

    if (std::abs(command.linear) <= 1e-6) {
        return command;
    }

    const double simulation_dt_s = dt_s > 1e-6 ? dt_s : 0.05;
    const double sample_dt_s = std::clamp(simulation_dt_s, 0.02, 0.05);
    const double horizon_s = std::max(0.20, simulation_dt_s);
    const int samples = std::max(1, static_cast<int>(std::ceil(horizon_s / sample_dt_s)));
    Pose2D projected = pose;
    for (int i = 0; i < samples; ++i) {
        projected.x += command.linear * std::cos(projected.theta) * sample_dt_s;
        projected.y += command.linear * std::sin(projected.theta) * sample_dt_s;
        projected.theta = normalizeAngle(projected.theta + command.angular * sample_dt_s);

        const auto cell = footprint_static_grid_.worldToGrid(Point2D{projected.x, projected.y});
        if (!cell || !footprint_static_grid_.isTraversable(cell->x, cell->y)) {
            return VelocityCommand{0.0, command.angular};
        }
    }

    return command;
}

double Navigator::currentDistanceToGoal(const Pose2D& pose) const {
    if (!active_goal_pose_) {
        return 0.0;
    }
    return distance(pose, *active_goal_pose_);
}

std::string toString(NavigatorPlannerState state) {
    switch (state) {
        case NavigatorPlannerState::Idle:
            return "IDLE";
        case NavigatorPlannerState::PathReady:
            return "PATH_READY";
        case NavigatorPlannerState::Replanning:
            return "REPLANNING";
        case NavigatorPlannerState::NoPath:
            return "NO_PATH";
    }
    return "UNKNOWN";
}

}  // namespace restaurant_robot
