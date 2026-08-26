#include <cmath>
#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <limits>
#include <memory>
#include <optional>
#include <string>

#include "restaurant_robot/control/differential_drive.hpp"
#include "restaurant_robot/estimation/localization.hpp"
#include "restaurant_robot/control/pure_pursuit.hpp"
#include "restaurant_robot/estimation/odometry.hpp"
#include "restaurant_robot/hardware/navigation_hardware.hpp"
#include "restaurant_robot/logging/run_logger.hpp"
#include "restaurant_robot/mapping/map_io.hpp"
#include "restaurant_robot/mapping/occupancy_ray_mapper.hpp"
#include "restaurant_robot/mapping/restaurant_map_factory.hpp"
#include "restaurant_robot/mapping/slam_backend.hpp"
#include "restaurant_robot/mission/delivery_manager.hpp"
#include "restaurant_robot/navigation/navigator.hpp"
#include "restaurant_robot/planning/astar.hpp"
#include "restaurant_robot/planning/inflation.hpp"
#include "restaurant_robot/planning/path_smoothing.hpp"
#include "restaurant_robot/safety/safety_supervisor.hpp"

// This controller is intentionally isolated from the core navigation library.
// Build it inside Webots with WEBOTS_CONTROLLER defined after adding the Webots
// include/library paths for the local simulator installation.
#ifdef WEBOTS_CONTROLLER
#include <webots/Device.hpp>
#include <webots/Display.hpp>
#include <webots/Gyro.hpp>
#include <webots/InertialUnit.hpp>
#include <webots/Lidar.hpp>
#include <webots/Motor.hpp>
#include <webots/PositionSensor.hpp>
#include <webots/Robot.hpp>

using namespace restaurant_robot;

namespace {

double getenvDoubleOr(const char* name, double fallback) {
    const char* value = std::getenv(name);
    return value ? std::atof(value) : fallback;
}

std::string getenvOr(const char* name, const std::string& fallback) {
    const char* value = std::getenv(name);
    return value ? std::string(value) : fallback;
}

bool getenvBoolOr(const char* name, bool fallback) {
    const char* value = std::getenv(name);
    if (!value) {
        return fallback;
    }
    const std::string text(value);
    return text == "1" || text == "true" || text == "TRUE" || text == "on";
}

bool isKnownTable(const RestaurantMap& restaurant, const std::string& destination) {
    return destination.rfind("TABLE_", 0) == 0 && restaurant.destinations.find(destination) != restaurant.destinations.end();
}

class WebotsHardware final : public INavigationHardware {
public:
    WebotsHardware(webots::Robot& robot, int time_step_ms)
        : robot_(robot), time_step_ms_(time_step_ms) {
        lidar_ = robot_.getLidar("LDS-01");
        if (hasDevice("inertial unit")) {
            imu_ = robot_.getInertialUnit("inertial unit");
        }
        if (hasDevice("imu gyro")) {
            gyro_ = robot_.getGyro("imu gyro");
        }
        left_motor_ = robot_.getMotor("left wheel motor");
        right_motor_ = robot_.getMotor("right wheel motor");
        left_encoder_ = robot_.getPositionSensor("left wheel sensor");
        right_encoder_ = robot_.getPositionSensor("right wheel sensor");
        if (hasDevice("debug display")) {
            display_ = robot_.getDisplay("debug display");
        }

        if (lidar_) {
            lidar_->enable(time_step_ms_);
        }
        if (imu_) {
            imu_->enable(time_step_ms_);
        }
        if (gyro_) {
            gyro_->enable(time_step_ms_);
        }
        if (left_encoder_) {
            left_encoder_->enable(time_step_ms_);
        }
        if (right_encoder_) {
            right_encoder_->enable(time_step_ms_);
        }
        if (left_motor_ && right_motor_) {
            left_motor_->setPosition(INFINITY);
            right_motor_->setPosition(INFINITY);
            left_motor_->setVelocity(0.0);
            right_motor_->setVelocity(0.0);
        }
    }

    webots::Display* display() const {
        return display_;
    }

    LaserScan getLaserScan() override {
        LaserScan scan;
        if (!lidar_) {
            return scan;
        }
        const int count = lidar_->getHorizontalResolution();
        const float* ranges = lidar_->getRangeImage();
        scan.ranges.assign(ranges, ranges + count);
        scan.angle_min = -lidar_->getFov() / 2.0;
        scan.angle_increment = count > 1 ? lidar_->getFov() / static_cast<double>(count - 1) : 0.0;
        scan.max_range = lidar_->getMaxRange();
        scan.timestamp = robot_.getTime();
        return scan;
    }

    EncoderData getEncoders() override {
        return EncoderData{
            left_encoder_ ? left_encoder_->getValue() : 0.0,
            right_encoder_ ? right_encoder_->getValue() : 0.0,
            robot_.getTime(),
        };
    }

    ImuData getImu() override {
        ImuData data;
        if (imu_) {
            const double* rpy = imu_->getRollPitchYaw();
            data.yaw = rpy[2];
        }
        if (gyro_) {
            const double* values = gyro_->getValues();
            data.angular_velocity_z = values[2];
            data.yaw_rate = values[2];
        }
        data.timestamp = robot_.getTime();
        return data;
    }

    void setVelocity(double linear, double angular) override {
        const auto wheel = kinematics_.toWheelAngularVelocities(VelocityCommand{linear, angular});
        if (left_motor_ && right_motor_) {
            left_motor_->setVelocity(std::clamp(wheel.left, -max_wheel_speed_rad_s_, max_wheel_speed_rad_s_));
            right_motor_->setVelocity(std::clamp(wheel.right, -max_wheel_speed_rad_s_, max_wheel_speed_rad_s_));
        }
    }

private:
    bool hasDevice(const std::string& name) {
        for (int i = 0; i < robot_.getNumberOfDevices(); ++i) {
            webots::Device* device = robot_.getDeviceByIndex(i);
            if (device && device->getName() == name) {
                return true;
            }
        }
        return false;
    }

    webots::Robot& robot_;
    int time_step_ms_{32};
    DifferentialDriveKinematics kinematics_{0.033, 0.16};
    double max_wheel_speed_rad_s_{6.67};
    webots::Lidar* lidar_{nullptr};
    webots::InertialUnit* imu_{nullptr};
    webots::Gyro* gyro_{nullptr};
    webots::Motor* left_motor_{nullptr};
    webots::Motor* right_motor_{nullptr};
    webots::PositionSensor* left_encoder_{nullptr};
    webots::PositionSensor* right_encoder_{nullptr};
    webots::Display* display_{nullptr};
};

class DebugDisplayRenderer {
public:
    DebugDisplayRenderer(webots::Display* display, RestaurantMap map)
        : display_(display), map_(std::move(map)) {}

    void draw(const Pose2D& pose, const LaserScan& scan, const Navigator& navigator, const NavigatorStepResult& nav) {
        if (!display_) {
            return;
        }

        const int w = display_->getWidth();
        const int h = display_->getHeight();
        display_->setAlpha(1.0);
        display_->setColor(0xF3F3F3);
        display_->fillRectangle(0, 0, w, h);
        drawMap();
        drawLidarHits(pose, scan);
        drawDynamicHits(pose, scan);
        drawPath(navigator.activePath());
        drawPurePursuitTarget(nav.pure_pursuit_target);
        drawGoal(nav.active_goal);
        drawSafetyZones(pose);
        drawRobot(pose, nav.safety_state);

        display_->setColor(0x202020);
        display_->setFont("Arial", 12, true);
        display_->drawText(nav.active_goal + " " + toString(nav.safety_state), 8, 16);
    }

    bool saveImage(const std::string& path) {
        if (!display_ || path.empty()) {
            return false;
        }
        const std::filesystem::path output_path(path);
        if (output_path.has_parent_path()) {
            std::filesystem::create_directories(output_path.parent_path());
        }
        webots::ImageRef* image = display_->imageCopy(0, 0, display_->getWidth(), display_->getHeight());
        if (!image) {
            return false;
        }
        display_->imageSave(image, path);
        display_->imageDelete(image);
        return true;
    }

private:
    int sx(double x) const {
        return static_cast<int>((x - map_.grid.origin().x) * scale_);
    }

    int sy(double y) const {
        const double map_height_m = map_.grid.height() * map_.grid.resolution();
        return static_cast<int>((map_.grid.origin().y + map_height_m - y) * scale_);
    }

    void drawMap() {
        const double cell_scale = std::max(1.0, map_.grid.resolution() * scale_);
        for (int y = 0; y < map_.grid.height(); ++y) {
            for (int x = 0; x < map_.grid.width(); ++x) {
                const auto value = map_.grid.get(x, y);
                if (value == kOccupied) {
                    display_->setColor(0x2F3437);
                } else if (value == kUnknown) {
                    display_->setColor(0xAEB5BA);
                } else {
                    continue;
                }
                const auto point = map_.grid.gridToWorld(x, y);
                display_->fillRectangle(
                    sx(point.x - map_.grid.resolution() / 2.0),
                    sy(point.y + map_.grid.resolution() / 2.0),
                    static_cast<int>(cell_scale),
                    static_cast<int>(cell_scale));
            }
        }
    }

    void drawPath(const Path& path) {
        if (path.points.size() < 2) {
            return;
        }
        display_->setColor(0x1C6DD0);
        for (std::size_t i = 0; i + 1 < path.points.size(); ++i) {
            display_->drawLine(sx(path.points[i].x), sy(path.points[i].y), sx(path.points[i + 1].x), sy(path.points[i + 1].y));
        }
    }

    void drawGoal(const std::string& name) {
        const auto it = map_.destinations.find(name);
        if (it == map_.destinations.end()) {
            return;
        }
        display_->setColor(0x3B8C3A);
        display_->fillOval(sx(it->second.x), sy(it->second.y), 5, 5);
    }

    void drawPurePursuitTarget(const std::optional<Point2D>& target) {
        if (!target) {
            return;
        }
        display_->setColor(0x7B1FA2);
        display_->fillOval(sx(target->x), sy(target->y), 7, 7);
        display_->drawLine(sx(target->x - 0.10), sy(target->y), sx(target->x + 0.10), sy(target->y));
        display_->drawLine(sx(target->x), sy(target->y - 0.10), sx(target->x), sy(target->y + 0.10));
    }

    void drawLidarHits(const Pose2D& pose, const LaserScan& scan) {
        if (scan.ranges.empty() || scan.max_range <= 0.0) {
            return;
        }
        display_->setColor(0xE0B000);
        for (std::size_t i = 0; i < scan.ranges.size(); i += 4) {
            const double range = scan.ranges[i];
            if (range <= 0.02 || range >= scan.max_range - 0.05) {
                continue;
            }
            const Point2D hit = scanHitPoint(pose, scan, i);
            display_->fillOval(sx(hit.x), sy(hit.y), 2, 2);
        }
    }

    void drawDynamicHits(const Pose2D& pose, const LaserScan& scan) {
        if (scan.ranges.empty() || scan.max_range <= 0.0) {
            return;
        }
        display_->setColor(0xD32F2F);
        for (std::size_t i = 0; i < scan.ranges.size(); i += 2) {
            const double range = scan.ranges[i];
            if (range <= 0.02 || range >= scan.max_range - 0.05) {
                continue;
            }
            const Point2D hit = scanHitPoint(pose, scan, i);
            const auto cell = map_.grid.worldToGrid(hit);
            if (cell && map_.grid.get(cell->x, cell->y) == kFree) {
                display_->fillOval(sx(hit.x), sy(hit.y), 4, 4);
            }
        }
    }

    Point2D scanHitPoint(const Pose2D& pose, const LaserScan& scan, std::size_t index) const {
        const double range = scan.ranges[index];
        const double angle = normalizeAngle(pose.theta + scan.angle_min + static_cast<double>(index) * scan.angle_increment);
        return Point2D{
            pose.x + range * std::cos(angle),
            pose.y + range * std::sin(angle),
        };
    }

    void drawRobot(const Pose2D& pose, SafetyState state) {
        display_->setColor(state == SafetyState::EmergencyStop ? 0xC62828 : 0x111111);
        display_->fillOval(sx(pose.x), sy(pose.y), 5, 5);
        const double hx = pose.x + 0.35 * std::cos(pose.theta);
        const double hy = pose.y + 0.35 * std::sin(pose.theta);
        display_->drawLine(sx(pose.x), sy(pose.y), sx(hx), sy(hy));
    }

    void drawSafetyZones(const Pose2D& pose) {
        display_->setAlpha(0.25);
        display_->setColor(0xF0A000);
        const double front_x = pose.x + 0.5 * std::cos(pose.theta);
        const double front_y = pose.y + 0.5 * std::sin(pose.theta);
        display_->fillOval(sx(front_x), sy(front_y), static_cast<int>(1.0 * scale_), static_cast<int>(0.45 * scale_));
        display_->setColor(0xB00020);
        const double stop_x = pose.x + 0.23 * std::cos(pose.theta);
        const double stop_y = pose.y + 0.23 * std::sin(pose.theta);
        display_->fillOval(sx(stop_x), sy(stop_y), static_cast<int>(0.45 * scale_), static_cast<int>(0.22 * scale_));
        display_->setAlpha(1.0);
    }

    webots::Display* display_{nullptr};
    RestaurantMap map_;
    double scale_{512.0 / 9.0};
};

}  // namespace

int main() {
    webots::Robot robot;
    const int time_step_ms = static_cast<int>(robot.getBasicTimeStep());
    WebotsHardware hardware(robot, time_step_ms);

    const auto restaurant = createPrototypeRestaurantMap(0.05);
    DebugDisplayRenderer debug_renderer(hardware.display(), restaurant);
    WheelImuOdometry odometry(0.033, 0.16);
    ScanMapLocalizationConfig localization_config;
    localization_config.search_xy_radius_m = 0.35;
    localization_config.search_xy_step_m = 0.10;
    localization_config.search_theta_radius_rad = 15.0 * kPi / 180.0;
    localization_config.search_theta_step_rad = 5.0 * kPi / 180.0;
    localization_config.correction_gain = 0.45;
    localization_config.minimum_score_improvement = 0.30;
    localization_config.max_translation_correction_m = 0.02;
    localization_config.max_rotation_correction_rad = 2.0 * kPi / 180.0;
    localization_config.max_scan_points = 72;
    ScanMapLocalizer localizer(restaurant.grid, localization_config);
    Navigator navigator(restaurant);
    auto slam_backend = createSlamBackend(getenvOr("SLAM_BACKEND", "known_pose"));
    RunLogger logger("restaurant_run.csv");
    const double max_time_s = getenvDoubleOr("MAX_TIME", 0.0);
    const std::string operating_mode = getenvOr("OPERATING_MODE", "NAVIGATION");
    const bool mapping_mode = operating_mode == "MAPPING";
    const bool scan_localization_enabled = !mapping_mode && getenvBoolOr("ENABLE_SCAN_LOCALIZATION", false);
    const std::string map_output_prefix = getenvOr("MAP_OUTPUT_PREFIX", "webots_restaurant_map");
    const std::string debug_export_path = getenvOr("DEBUG_EXPORT_PATH", "");
    const double debug_export_interval_s = getenvDoubleOr("DEBUG_EXPORT_INTERVAL", 0.0);
    std::string requested_destination = getenvOr("GOAL_TABLE", "TABLE_3");
    std::string last_command;
    bool odometry_initialized = false;
    bool mission_complete = false;
    int draw_counter = 0;
    int final_replanning_events = 0;
    Pose2D last_estimated_pose = restaurant.destinations.at("HOME");
    Pose2D localization_offset;
    double next_localization_update_s = 0.0;
    bool scan_localization_active = false;
    double next_debug_export_s = debug_export_interval_s > 0.0 ? debug_export_interval_s : std::numeric_limits<double>::infinity();
    bool debug_image_drawn = false;
    bool debug_image_saved = false;
    constexpr double localization_update_period_s = 0.25;

    if (!isKnownTable(restaurant, requested_destination)) {
        requested_destination = "TABLE_3";
    }
    navigator.deliver(requested_destination);

    while (robot.step(time_step_ms) != -1) {
        if (max_time_s > 0.0 && robot.getTime() >= max_time_s) {
            hardware.setVelocity(0.0, 0.0);
            break;
        }

        const auto scan = hardware.getLaserScan();
        const auto encoders = hardware.getEncoders();
        const auto imu = hardware.getImu();
        if (!odometry_initialized) {
            odometry.reset(restaurant.destinations.at("HOME"), encoders);
            odometry_initialized = true;
        }
        Pose2D odometry_pose = odometry.update(encoders, imu);
        Pose2D estimated_pose{
            odometry_pose.x + localization_offset.x,
            odometry_pose.y + localization_offset.y,
            normalizeAngle(odometry_pose.theta + localization_offset.theta),
        };
        if (scan_localization_enabled && scan_localization_active && !scan.ranges.empty() &&
            robot.getTime() >= next_localization_update_s) {
            estimated_pose = localizer.update(estimated_pose, scan);
            localization_offset = Pose2D{
                estimated_pose.x - odometry_pose.x,
                estimated_pose.y - odometry_pose.y,
                normalizeAngle(estimated_pose.theta - odometry_pose.theta),
            };
            next_localization_update_s = robot.getTime() + localization_update_period_s;
        }
        last_estimated_pose = estimated_pose;

        const std::string command = robot.getCustomData();
        if (command != last_command) {
            last_command = command;
            if (command == "ESTOP") {
                navigator.setEmergencyStop(true);
            } else if (command == "CLEAR_ESTOP") {
                navigator.setEmergencyStop(false);
            } else if (isKnownTable(restaurant, command) && command != requested_destination) {
                requested_destination = command;
                navigator.deliver(requested_destination);
                navigator.setEmergencyStop(false);
            } else if (command == "DISTURB_POSE") {
                const Pose2D pose_belief_before_disturbance = estimated_pose;
                const Pose2D disturbed{
                    odometry_pose.x,
                    odometry_pose.y - 0.25,
                    normalizeAngle(odometry_pose.theta + 0.18),
                };
                odometry.reset(disturbed, encoders);
                odometry_pose = disturbed;
                estimated_pose = pose_belief_before_disturbance;
                localization_offset = Pose2D{
                    estimated_pose.x - odometry_pose.x,
                    estimated_pose.y - odometry_pose.y,
                    normalizeAngle(estimated_pose.theta - odometry_pose.theta),
                };
                scan_localization_active = true;
                next_localization_update_s = robot.getTime() + 10.0;
            }
        }

        const auto nav = navigator.update(estimated_pose, scan, time_step_ms / 1000.0);
        final_replanning_events = nav.replanning_events;
        if (mapping_mode && !scan.ranges.empty()) {
            slam_backend->update(scan, encoders, imu, estimated_pose);
        }
        hardware.setVelocity(nav.command.linear, nav.command.angular);
        if (++draw_counter % 5 == 0) {
            debug_renderer.draw(estimated_pose, scan, navigator, nav);
            debug_image_drawn = true;
            if (!debug_export_path.empty() && debug_export_interval_s > 0.0 && robot.getTime() >= next_debug_export_s) {
                debug_image_saved = debug_renderer.saveImage(debug_export_path);
                next_debug_export_s = robot.getTime() + debug_export_interval_s;
            }
        }
        logger.write(RunLogRecord{
            robot.getTime(),
            odometry_pose,
            estimated_pose,
            nav.active_goal,
            requested_destination,
            nav.command.linear,
            nav.command.angular,
            nav.minimum_obstacle_distance,
            toString(nav.planner_state),
            nav.safety_state,
            nav.replanning_events,
            nav.distance_to_goal,
            0,
        });

        if (!mapping_mode && nav.mission_complete) {
            mission_complete = true;
            hardware.setVelocity(0.0, 0.0);
            break;
        }
    }

    if (!debug_export_path.empty()) {
        if (!debug_image_drawn) {
            LaserScan empty_scan;
            NavigatorStepResult empty_nav;
            empty_nav.active_goal = navigator.activeGoalName();
            debug_renderer.draw(last_estimated_pose, empty_scan, navigator, empty_nav);
        }
        debug_image_saved = debug_renderer.saveImage(debug_export_path) || debug_image_saved;
        std::cout << "debug_snapshot=" << debug_export_path << "\n";
        std::cout << "debug_snapshot_saved=" << (debug_image_saved ? "true" : "false") << "\n";
    }

    const double final_home_error = distance(last_estimated_pose, restaurant.destinations.at("HOME"));
    std::cout << "mission_success=" << (mission_complete ? "true" : "false") << "\n";
    std::cout << "requested_destination=" << requested_destination << "\n";
    std::cout << "final_home_error_m=" << final_home_error << "\n";
    std::cout << "final_pose_x=" << last_estimated_pose.x << "\n";
    std::cout << "final_pose_y=" << last_estimated_pose.y << "\n";
    std::cout << "final_pose_theta=" << last_estimated_pose.theta << "\n";
    std::cout << "replanning_events=" << final_replanning_events << "\n";
    std::cout << "elapsed_time_s=" << robot.getTime() << "\n";

    if (mapping_mode) {
        const std::string json_path = map_output_prefix + ".json";
        const std::string pgm_path = map_output_prefix + ".pgm";
        const bool map_ok = slam_backend->saveMap(map_output_prefix);
        std::cout << "mapping_mode=true\n";
        std::cout << "slam_backend=" << slam_backend->name() << "\n";
        std::cout << "map_json=" << json_path << "\n";
        std::cout << "map_pgm=" << pgm_path << "\n";
        std::cout << "map_saved=" << (map_ok ? "true" : "false") << "\n";
    }

    return 0;
}
#else
int main() {
    std::cerr << "restaurant_delivery_controller requires Webots and WEBOTS_CONTROLLER.\n";
    return 1;
}
#endif
