#pragma once

#include <optional>

#include "restaurant_robot/common/types.hpp"

namespace restaurant_robot {

struct PurePursuitConfig {
    double lookahead_distance{0.22};
    double final_lookahead_distance{0.12};
    double final_approach_distance{0.55};
    double max_linear_velocity{0.28};
    double max_angular_velocity{0.7};
    double angular_gain{1.8};
    double rotate_in_place_heading_error{0.45};
    double heading_slowdown_error{0.20};
    double goal_slowdown_distance{0.75};
    double goal_tolerance{0.18};
};

class PurePursuitController {
public:
    explicit PurePursuitController(PurePursuitConfig config = {});

    VelocityCommand computeCommand(const Path& path, const Pose2D& pose) const;
    std::optional<Point2D> selectLookaheadTarget(const Path& path, const Pose2D& pose) const;

private:
    PurePursuitConfig config_;
};

}  // namespace restaurant_robot
