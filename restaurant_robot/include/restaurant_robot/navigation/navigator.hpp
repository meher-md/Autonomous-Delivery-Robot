#pragma once

#include <optional>
#include <string>

#include "restaurant_robot/control/pure_pursuit.hpp"
#include "restaurant_robot/logging/run_logger.hpp"
#include "restaurant_robot/mapping/restaurant_map_factory.hpp"
#include "restaurant_robot/mission/delivery_manager.hpp"
#include "restaurant_robot/obstacle/local_obstacle_map.hpp"
#include "restaurant_robot/planning/astar.hpp"
#include "restaurant_robot/planning/inflation.hpp"
#include "restaurant_robot/safety/safety_supervisor.hpp"

namespace restaurant_robot {

enum class NavigatorPlannerState {
    Idle,
    PathReady,
    Replanning,
    NoPath,
};

struct NavigatorConfig {
    double obstacle_inflation_radius_m{0.40};
    double persistent_blockage_timeout_s{3.0};
    double path_obstacle_radius_m{0.35};
    double stuck_timeout_s{3.0};
    double stuck_motion_threshold_m{0.05};
};

struct NavigatorStepResult {
    VelocityCommand command;
    SafetyState safety_state{SafetyState::Normal};
    NavigatorPlannerState planner_state{NavigatorPlannerState::Idle};
    bool replanned{false};
    bool mission_complete{false};
    bool no_path{false};
    int replanning_events{0};
    double distance_to_goal{0.0};
    double minimum_obstacle_distance{0.0};
    std::optional<Point2D> pure_pursuit_target;
    std::string active_goal;
};

class Navigator {
public:
    Navigator(RestaurantMap restaurant_map, NavigatorConfig config = {});

    bool deliver(const std::string& table_name);
    void setEmergencyStop(bool enabled);
    NavigatorStepResult update(const Pose2D& pose, const LaserScan& scan, double dt_s);

    const Path& activePath() const { return active_path_; }
    NavigatorPlannerState plannerState() const { return planner_state_; }
    int replanningEvents() const { return replanning_events_; }
    std::string activeGoalName() const { return mission_.activeDestinationName(); }

private:
    bool planTo(const Pose2D& pose, const Pose2D& goal, bool use_dynamic_obstacles);
    bool shouldReplan(const Pose2D& pose, const VelocityCommand& requested, SafetyState safety_state, double dt_s);
    double currentDistanceToGoal(const Pose2D& pose) const;

    RestaurantMap restaurant_map_;
    NavigatorConfig config_;
    OccupancyGrid inflated_static_grid_;
    AStarPlanner planner_;
    PurePursuitController tracker_;
    SafetySupervisor safety_;
    LocalObstacleMap local_obstacles_;
    DeliveryManager mission_;
    Path active_path_;
    std::optional<Pose2D> active_goal_pose_;
    NavigatorPlannerState planner_state_{NavigatorPlannerState::Idle};
    int replanning_events_{0};
    double blocked_timer_s_{0.0};
    double stuck_timer_s_{0.0};
    Pose2D last_progress_pose_{};
};

std::string toString(NavigatorPlannerState state);

}  // namespace restaurant_robot
