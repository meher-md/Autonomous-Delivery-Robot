#pragma once

#include "restaurant_robot/common/types.hpp"
#include "restaurant_robot/planning/occupancy_grid.hpp"

namespace restaurant_robot {

class ILocalizer {
public:
    virtual ~ILocalizer() = default;
    virtual Pose2D update(const Pose2D& predicted_pose, const LaserScan& scan) = 0;
};

struct ScanMapLocalizationConfig {
    double search_xy_radius_m{0.25};
    double search_xy_step_m{0.05};
    double search_theta_radius_rad{10.0 * kPi / 180.0};
    double search_theta_step_rad{2.5 * kPi / 180.0};
    double correction_gain{0.65};
    double minimum_score_improvement{0.05};
    double max_translation_correction_m{0.08};
    double max_rotation_correction_rad{5.0 * kPi / 180.0};
    int max_scan_points{120};
};

class ScanMapLocalizer : public ILocalizer {
public:
    ScanMapLocalizer(OccupancyGrid map, ScanMapLocalizationConfig config = {});

    Pose2D update(const Pose2D& predicted_pose, const LaserScan& scan) override;

private:
    double scorePose(const Pose2D& pose, const LaserScan& scan) const;
    double occupiedProximityScore(int x, int y) const;

    OccupancyGrid map_;
    ScanMapLocalizationConfig config_;
};

}  // namespace restaurant_robot
