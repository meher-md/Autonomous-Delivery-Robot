# Standalone SLAM Selection Notes

Phase 1 keeps SLAM behind a module boundary and ships map loading/planning first. The PRD says SLAM should not be written from scratch, and that constraint is correct: scan matching and loop closure are easy to get half-working but hard to trust.

Current implementation status:

- `ISlamBackend` defines the integration boundary in `include/restaurant_robot/mapping/slam_backend.hpp`.
- `KnownPoseRaySlamBackend` implements that boundary using known/estimated pose plus LiDAR ray insertion.
- `CeresScanMatchSlamBackend` is built when `find_package(Ceres)` succeeds. It associates LiDAR hit endpoints against the current occupancy map, uses Ceres to refine `x`, `y`, and yaw around the odometry/localization hint, clamps large corrections, then inserts the scan.
- `generate_map_artifacts` and Webots `OPERATING_MODE=MAPPING` accept `SLAM_BACKEND=known_pose` or `SLAM_BACKEND=ceres_scan_match`. The known-pose backend remains the default acceptance path.
- The Ceres backend is scan-to-current-map matching. It is not graph SLAM and does not perform loop closure. It is a stronger external-library mapping step while a full standalone SLAM dependency is selected.

Initial candidates to evaluate:

- Google Cartographer library mode, if its standalone build can be kept isolated from ROS.
- Karto/OpenKarto-style 2D graph SLAM, if dependency and maintenance state are acceptable.
- TinySLAM or BreezySLAM for an early mapping experiment, if C++ integration and license checks pass.

Required integration boundary:

```cpp
class ISlamBackend {
public:
    virtual Pose2D update(
        const LaserScan& scan,
        const EncoderData& encoders,
        const ImuData& imu,
        const Pose2D& pose_hint) = 0;
    virtual const OccupancyGrid& currentMap() const = 0;
    virtual bool saveMap(const std::string& output_prefix) const = 0;
    virtual std::string name() const = 0;
};
```

Expected replacement path:

1. Add an external backend class implementing `ISlamBackend`.
2. Keep `Navigator`, `AStarPlanner`, `PurePursuitController`, `SafetySupervisor`, and `DeliveryManager` unchanged.
3. Select the backend in Webots mapping mode using configuration, for example `SLAM_BACKEND=cartographer` or `SLAM_BACKEND=karto`.
4. Preserve the same map artifact contract: `<prefix>.json` and `<prefix>.pgm`.

Normal restaurant operation should load a saved occupancy grid and localize against it. Continuous map rebuilding is intentionally not part of the first operating mode.
