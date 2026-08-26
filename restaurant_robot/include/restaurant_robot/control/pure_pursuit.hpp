#pragma once

#include <optional>

#include "restaurant_robot/common/types.hpp"

namespace restaurant_robot {

struct PurePursuitConfig {
    double lookahead_distance{0.32};
    double max_linear_velocity{0.35};
    double max_angular_velocity{0.8};
    double goal_slowdown_distance{0.6};
    double goal_tolerance{0.15};
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
