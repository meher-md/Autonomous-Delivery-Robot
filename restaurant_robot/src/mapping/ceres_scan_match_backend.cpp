#include "restaurant_robot/mapping/slam_backend.hpp"

#ifdef RESTAURANT_ROBOT_HAS_CERES

#include <ceres/ceres.h>

#include <algorithm>
#include <cmath>
#include <limits>
#include <optional>
#include <vector>

#include "restaurant_robot/mapping/map_io.hpp"

namespace restaurant_robot {
namespace {

struct BeamAssociation {
    double local_x{0.0};
    double local_y{0.0};
    Point2D target;
};

struct EndpointAssociationCost {
    EndpointAssociationCost(double local_x_in, double local_y_in, Point2D target_in, double weight_in)
        : local_x(local_x_in),
          local_y(local_y_in),
          target(target_in),
          weight(weight_in) {}

    template <typename T>
    bool operator()(const T* const pose, T* residuals) const {
        const T c = ceres::cos(pose[2]);
        const T s = ceres::sin(pose[2]);
        const T world_x = pose[0] + c * T(local_x) - s * T(local_y);
        const T world_y = pose[1] + s * T(local_x) + c * T(local_y);
        residuals[0] = T(weight) * (world_x - T(target.x));
        residuals[1] = T(weight) * (world_y - T(target.y));
        return true;
    }

    double local_x;
    double local_y;
    Point2D target;
    double weight;
};

struct PosePriorCost {
    PosePriorCost(Pose2D hint_in, double translation_weight_in, double rotation_weight_in)
        : hint(hint_in),
          translation_weight(translation_weight_in),
          rotation_weight(rotation_weight_in) {}

    template <typename T>
    bool operator()(const T* const pose, T* residuals) const {
        residuals[0] = T(translation_weight) * (pose[0] - T(hint.x));
        residuals[1] = T(translation_weight) * (pose[1] - T(hint.y));
        residuals[2] = T(rotation_weight) * ceres::sin(pose[2] - T(hint.theta));
        return true;
    }

    Pose2D hint;
    double translation_weight;
    double rotation_weight;
};

int countOccupiedCells(const OccupancyGrid& grid) {
    int occupied_count = 0;
    for (const auto cell : grid.cells()) {
        if (cell == kOccupied) {
            ++occupied_count;
        }
    }
    return occupied_count;
}

std::optional<Point2D> nearestOccupiedCell(
    const OccupancyGrid& grid,
    const Point2D& point,
    double radius_m) {
    const auto center = grid.worldToGrid(point);
    if (!center) {
        return std::nullopt;
    }

    const int radius_cells = std::max(1, static_cast<int>(std::ceil(radius_m / grid.resolution())));
    const double max_dist_sq = radius_m * radius_m;
    double best_dist_sq = std::numeric_limits<double>::infinity();
    std::optional<Point2D> best;

    for (int y = center->y - radius_cells; y <= center->y + radius_cells; ++y) {
        for (int x = center->x - radius_cells; x <= center->x + radius_cells; ++x) {
            if (!grid.inBounds(x, y) || grid.get(x, y) != kOccupied) {
                continue;
            }
            const Point2D candidate = grid.gridToWorld(x, y);
            const double dx = candidate.x - point.x;
            const double dy = candidate.y - point.y;
            const double dist_sq = dx * dx + dy * dy;
            if (dist_sq < best_dist_sq && dist_sq <= max_dist_sq) {
                best_dist_sq = dist_sq;
                best = candidate;
            }
        }
    }

    return best;
}

std::vector<BeamAssociation> collectAssociations(
    const OccupancyGrid& grid,
    const LaserScan& scan,
    const Pose2D& pose_hint,
    const CeresScanMatchConfig& config) {
    std::vector<BeamAssociation> associations;
    if (scan.ranges.empty() || scan.max_range <= 0.0 || config.max_beams <= 0) {
        return associations;
    }

    const int stride = std::max(1, static_cast<int>(scan.ranges.size()) / config.max_beams);
    for (std::size_t i = 0; i < scan.ranges.size() && associations.size() < static_cast<std::size_t>(config.max_beams);
         i += static_cast<std::size_t>(stride)) {
        const double range = scan.ranges[i];
        if (range <= 0.02 || range >= scan.max_range - config.ray_mapping.occupied_endpoint_margin_m) {
            continue;
        }

        const double local_angle = scan.angle_min + static_cast<double>(i) * scan.angle_increment;
        const double local_x = range * std::cos(local_angle);
        const double local_y = range * std::sin(local_angle);
        const double world_angle = normalizeAngle(pose_hint.theta + local_angle);
        const Point2D hinted_endpoint{
            pose_hint.x + range * std::cos(world_angle),
            pose_hint.y + range * std::sin(world_angle),
        };
        const auto target = nearestOccupiedCell(grid, hinted_endpoint, config.association_radius_m);
        if (target) {
            associations.push_back(BeamAssociation{local_x, local_y, *target});
        }
    }
    return associations;
}

Pose2D clampPoseCorrection(const Pose2D& hint, const Pose2D& optimized, const CeresScanMatchConfig& config) {
    Pose2D clamped = optimized;
    const double dx = optimized.x - hint.x;
    const double dy = optimized.y - hint.y;
    const double translation = std::hypot(dx, dy);
    if (translation > config.max_translation_correction_m && translation > 1e-9) {
        const double scale = config.max_translation_correction_m / translation;
        clamped.x = hint.x + dx * scale;
        clamped.y = hint.y + dy * scale;
    }

    const double dtheta = normalizeAngle(optimized.theta - hint.theta);
    const double limited_dtheta = std::clamp(
        dtheta,
        -config.max_rotation_correction_rad,
        config.max_rotation_correction_rad);
    clamped.theta = normalizeAngle(hint.theta + limited_dtheta);
    return clamped;
}

}  // namespace

CeresScanMatchSlamBackend::CeresScanMatchSlamBackend(CeresScanMatchConfig config)
    : config_(config),
      mapper_(config.ray_mapping) {}

Pose2D CeresScanMatchSlamBackend::update(
    const LaserScan& scan,
    const EncoderData&,
    const ImuData&,
    const Pose2D& pose_hint) {
    Pose2D pose = pose_hint;

    if (countOccupiedCells(mapper_.grid()) >= config_.min_associations) {
        const auto associations = collectAssociations(mapper_.grid(), scan, pose_hint, config_);
        if (associations.size() >= static_cast<std::size_t>(config_.min_associations)) {
            double pose_params[3] = {pose_hint.x, pose_hint.y, pose_hint.theta};
            ceres::Problem problem;

            for (const auto& association : associations) {
                auto* cost = new ceres::AutoDiffCostFunction<EndpointAssociationCost, 2, 3>(
                    new EndpointAssociationCost(
                        association.local_x,
                        association.local_y,
                        association.target,
                        config_.endpoint_weight));
                problem.AddResidualBlock(cost, new ceres::HuberLoss(0.20), pose_params);
            }

            auto* prior = new ceres::AutoDiffCostFunction<PosePriorCost, 3, 3>(
                new PosePriorCost(
                    pose_hint,
                    config_.translation_prior_weight,
                    config_.rotation_prior_weight));
            problem.AddResidualBlock(prior, nullptr, pose_params);

            ceres::Solver::Options options;
            options.max_num_iterations = config_.max_solver_iterations;
            options.minimizer_progress_to_stdout = false;
            options.num_threads = 1;
            options.linear_solver_type = ceres::DENSE_QR;

            ceres::Solver::Summary summary;
            ceres::Solve(options, &problem, &summary);
            if (summary.IsSolutionUsable()) {
                pose = clampPoseCorrection(
                    pose_hint,
                    Pose2D{pose_params[0], pose_params[1], normalizeAngle(pose_params[2])},
                    config_);
            }
        }
    }

    mapper_.integrateScan(pose, scan);
    return pose;
}

const OccupancyGrid& CeresScanMatchSlamBackend::currentMap() const {
    return mapper_.grid();
}

bool CeresScanMatchSlamBackend::saveMap(const std::string& output_prefix) const {
    return saveOccupancyGridJson(mapper_.grid(), output_prefix + ".json") &&
           mapper_.grid().savePgm(output_prefix + ".pgm");
}

std::string CeresScanMatchSlamBackend::name() const {
    return "ceres_scan_match_ray_mapper";
}

}  // namespace restaurant_robot

#endif
