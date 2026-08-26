#include "restaurant_robot/mapping/slam_backend.hpp"

#include <iostream>

#include "restaurant_robot/mapping/map_io.hpp"

namespace restaurant_robot {

KnownPoseRaySlamBackend::KnownPoseRaySlamBackend(RayMappingConfig config)
    : mapper_(config) {}

Pose2D KnownPoseRaySlamBackend::update(
    const LaserScan& scan,
    const EncoderData&,
    const ImuData&,
    const Pose2D& pose_hint) {
    mapper_.integrateScan(pose_hint, scan);
    return pose_hint;
}

const OccupancyGrid& KnownPoseRaySlamBackend::currentMap() const {
    return mapper_.grid();
}

bool KnownPoseRaySlamBackend::saveMap(const std::string& output_prefix) const {
    return saveOccupancyGridJson(mapper_.grid(), output_prefix + ".json") &&
           mapper_.grid().savePgm(output_prefix + ".pgm");
}

std::string KnownPoseRaySlamBackend::name() const {
    return "known_pose_ray_mapper";
}

std::vector<SlamBackendInfo> availableSlamBackends() {
    std::vector<SlamBackendInfo> backends = {
        SlamBackendInfo{
            "known_pose",
            true,
            "Known/estimated-pose LiDAR ray mapper used as the deterministic baseline.",
            "",
        },
#ifdef RESTAURANT_ROBOT_HAS_CERES
        SlamBackendInfo{
            "ceres_scan_match",
            true,
            "Ceres-backed scan-to-current-map matching plus occupancy ray insertion.",
            "",
        },
#else
        SlamBackendInfo{
            "ceres_scan_match",
            false,
            "Ceres-backed scan-to-current-map matching plus occupancy ray insertion.",
            "Install libceres-dev and configure with RESTAURANT_ROBOT_ENABLE_CERES_SCAN_MATCHING=ON.",
        },
#endif
#ifdef RESTAURANT_ROBOT_HAS_MRPT_GRAPHSLAM
        SlamBackendInfo{
            "mrpt_graphslam",
            true,
            "MRPT graph-SLAM backend.",
            "",
        },
#else
        SlamBackendInfo{
            "mrpt_graphslam",
            false,
            "MRPT graph-SLAM backend candidate for full standalone loop-closure SLAM.",
            "Install libmrpt-graphslam-dev libmrpt-slam-dev libmrpt-maps-dev libmrpt-obs-dev libmrpt-poses-dev.",
        },
#endif
    };
    return backends;
}

std::unique_ptr<ISlamBackend> createSlamBackend(const std::string& requested_backend) {
#ifdef RESTAURANT_ROBOT_HAS_CERES
    if (requested_backend == "ceres" || requested_backend == "ceres_scan_match" ||
        requested_backend == "ceres_scan_match_ray_mapper") {
        return std::make_unique<CeresScanMatchSlamBackend>();
    }
#endif

    if (requested_backend == "mrpt_graphslam") {
#ifdef RESTAURANT_ROBOT_HAS_MRPT_GRAPHSLAM
        return createMrptGraphSlamBackend();
#else
        std::cerr << "SLAM_BACKEND=mrpt_graphslam unavailable: install MRPT graph-SLAM development packages.\n";
#endif
    } else if (requested_backend != "known_pose" && requested_backend != "known_pose_ray_mapper") {
        std::cerr << "SLAM_BACKEND=" << requested_backend << " unavailable, using known_pose\n";
    }
    return std::make_unique<KnownPoseRaySlamBackend>();
}

}  // namespace restaurant_robot
