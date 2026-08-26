#pragma once

#include <memory>
#include <vector>
#include <string>

#include "restaurant_robot/common/types.hpp"
#include "restaurant_robot/mapping/occupancy_ray_mapper.hpp"

namespace restaurant_robot {

class ISlamBackend {
public:
    virtual ~ISlamBackend() = default;

    virtual Pose2D update(
        const LaserScan& scan,
        const EncoderData& encoders,
        const ImuData& imu,
        const Pose2D& pose_hint) = 0;
    virtual const OccupancyGrid& currentMap() const = 0;
    virtual bool saveMap(const std::string& output_prefix) const = 0;
    virtual std::string name() const = 0;
};

struct SlamBackendInfo {
    std::string name;
    bool available{false};
    std::string description;
    std::string install_hint;
};

std::vector<SlamBackendInfo> availableSlamBackends();
std::unique_ptr<ISlamBackend> createSlamBackend(const std::string& requested_backend);

class KnownPoseRaySlamBackend final : public ISlamBackend {
public:
    explicit KnownPoseRaySlamBackend(RayMappingConfig config = {});

    Pose2D update(
        const LaserScan& scan,
        const EncoderData& encoders,
        const ImuData& imu,
        const Pose2D& pose_hint) override;
    const OccupancyGrid& currentMap() const override;
    bool saveMap(const std::string& output_prefix) const override;
    std::string name() const override;

private:
    OccupancyRayMapper mapper_;
};

#ifdef RESTAURANT_ROBOT_HAS_CERES
struct CeresScanMatchConfig {
    RayMappingConfig ray_mapping{};
    int max_beams{60};
    int min_associations{8};
    int max_solver_iterations{20};
    double association_radius_m{0.45};
    double max_translation_correction_m{0.35};
    double max_rotation_correction_rad{15.0 * kPi / 180.0};
    double endpoint_weight{1.0};
    double translation_prior_weight{4.0};
    double rotation_prior_weight{2.0};
};

class CeresScanMatchSlamBackend final : public ISlamBackend {
public:
    explicit CeresScanMatchSlamBackend(CeresScanMatchConfig config = {});

    Pose2D update(
        const LaserScan& scan,
        const EncoderData& encoders,
        const ImuData& imu,
        const Pose2D& pose_hint) override;
    const OccupancyGrid& currentMap() const override;
    bool saveMap(const std::string& output_prefix) const override;
    std::string name() const override;

private:
    CeresScanMatchConfig config_;
    OccupancyRayMapper mapper_;
};
#endif

}  // namespace restaurant_robot
