#include <cmath>
#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <limits>
#include <memory>
#include <optional>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

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
#include <webots/Keyboard.hpp>
#include <webots/Lidar.hpp>
#include <webots/Motor.hpp>
#include <webots/PositionSensor.hpp>
#include <webots/Robot.hpp>
#include <webots/Supervisor.hpp>

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

std::string argValueOr(int argc, char** argv, const std::string& name, const std::string& fallback) {
    for (int i = 1; i < argc; ++i) {
        const std::string arg(argv[i]);
        const std::string prefix = name + "=";
        if (arg == name && i + 1 < argc) {
            return argv[i + 1];
        }
        if (arg.rfind(prefix, 0) == 0) {
            return arg.substr(prefix.size());
        }
    }
    return fallback;
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

bool isKnownDestination(const RestaurantMap& restaurant, const std::string& destination) {
    return restaurant.destinations.find(destination) != restaurant.destinations.end();
}

bool commandDestination(Navigator& navigator, const RestaurantMap& restaurant, const std::string& destination) {
    if (isKnownTable(restaurant, destination)) {
        return navigator.deliver(destination);
    }
    if (isKnownDestination(restaurant, destination)) {
        return navigator.goToDestination(destination);
    }
    return false;
}

std::optional<std::string> firstKnownTable(const RestaurantMap& restaurant) {
    const auto preferred = restaurant.destinations.find("TABLE_3");
    if (preferred != restaurant.destinations.end()) {
        return preferred->first;
    }
    for (const auto& [name, pose] : restaurant.destinations) {
        (void)pose;
        if (name.rfind("TABLE_", 0) == 0) {
            return name;
        }
    }
    return std::nullopt;
}

std::optional<std::string> tableFromKey(int key) {
    const int plain_key = key & webots::Keyboard::KEY;
    if (plain_key >= '1' && plain_key <= '9') {
        return "TABLE_" + std::to_string(plain_key - '0');
    }
    return std::nullopt;
}

bool saveManualRestaurantMap(const RestaurantMap& restaurant,
                             const OccupancyGrid& mapped_grid,
                             const std::string& output_prefix) {
    RestaurantMap snapshot = restaurant;
    snapshot.grid = mapped_grid;
    return saveRestaurantMapJson(snapshot, output_prefix + ".json") && mapped_grid.savePgm(output_prefix + ".pgm");
}

struct ManualDriveInput {
    VelocityCommand command;
    bool has_drive_command{false};
    bool save_map{false};
    bool quit{false};
};

struct GuiCommand {
    int seq{-1};
    std::string mode;
    std::optional<std::string> goal;
    VelocityCommand manual_command;
    NavigatorConfig tuning_config;
    bool has_manual_command{false};
    bool has_tuning_config{false};
    bool save_map{false};
    bool quit{false};
    bool estop{false};
    bool clear_estop{false};
    bool tune_only{false};
};

std::string trim(std::string text) {
    const auto begin = text.find_first_not_of(" \t\r\n");
    if (begin == std::string::npos) {
        return "";
    }
    const auto end = text.find_last_not_of(" \t\r\n");
    return text.substr(begin, end - begin + 1);
}

bool boolValue(const std::string& value) {
    return value == "1" || value == "true" || value == "TRUE" || value == "on" || value == "yes";
}

bool assignDoubleValue(
    const std::unordered_map<std::string, std::string>& values,
    const std::string& key,
    double& target,
    bool& assigned) {
    const auto value = values.find(key);
    if (value == values.end()) {
        return true;
    }
    try {
        target = std::stod(value->second);
        assigned = true;
        return true;
    } catch (const std::exception&) {
        return false;
    }
}

std::optional<GuiCommand> readGuiCommand(const std::string& path) {
    if (path.empty()) {
        return std::nullopt;
    }
    std::ifstream in(path);
    if (!in) {
        return std::nullopt;
    }

    std::unordered_map<std::string, std::string> values;
    std::string line;
    while (std::getline(in, line)) {
        const auto split = line.find('=');
        if (split == std::string::npos) {
            continue;
        }
        values[trim(line.substr(0, split))] = trim(line.substr(split + 1));
    }

    GuiCommand command;
    const auto seq = values.find("seq");
    if (seq == values.end()) {
        return std::nullopt;
    }
    try {
        command.seq = std::stoi(seq->second);
        if (const auto mode = values.find("mode"); mode != values.end()) {
            command.mode = mode->second;
        }
        if (const auto goal = values.find("goal"); goal != values.end() && !goal->second.empty()) {
            command.goal = goal->second;
        }
        if (const auto linear = values.find("linear"); linear != values.end()) {
            command.manual_command.linear = std::stod(linear->second);
            command.has_manual_command = true;
        }
        if (const auto angular = values.find("angular"); angular != values.end()) {
            command.manual_command.angular = std::stod(angular->second);
            command.has_manual_command = true;
        }
    } catch (const std::exception&) {
        return std::nullopt;
    }

    if (const auto save = values.find("save_map"); save != values.end()) {
        command.save_map = boolValue(save->second);
    }
    if (const auto quit = values.find("quit"); quit != values.end()) {
        command.quit = boolValue(quit->second);
    }
    if (const auto estop = values.find("estop"); estop != values.end()) {
        command.estop = boolValue(estop->second);
    }
    if (const auto clear = values.find("clear_estop"); clear != values.end()) {
        command.clear_estop = boolValue(clear->second);
    }
    if (const auto tune = values.find("tune_only"); tune != values.end()) {
        command.tune_only = boolValue(tune->second);
    }
    if (!assignDoubleValue(values, "tune_planner_clearance_radius_m", command.tuning_config.planner_clearance_radius_m, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_path_obstacle_radius_m", command.tuning_config.path_obstacle_radius_m, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_persistent_blockage_timeout_s", command.tuning_config.persistent_blockage_timeout_s, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_stuck_timeout_s", command.tuning_config.stuck_timeout_s, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_stuck_motion_threshold_m", command.tuning_config.stuck_motion_threshold_m, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_lookahead_distance_m", command.tuning_config.pure_pursuit.lookahead_distance, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_final_lookahead_distance_m", command.tuning_config.pure_pursuit.final_lookahead_distance, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_final_approach_distance_m", command.tuning_config.pure_pursuit.final_approach_distance, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_max_linear_velocity_mps", command.tuning_config.pure_pursuit.max_linear_velocity, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_max_angular_velocity_rps", command.tuning_config.pure_pursuit.max_angular_velocity, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_angular_gain", command.tuning_config.pure_pursuit.angular_gain, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_rotate_in_place_heading_error_rad", command.tuning_config.pure_pursuit.rotate_in_place_heading_error, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_heading_slowdown_error_rad", command.tuning_config.pure_pursuit.heading_slowdown_error, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_goal_slowdown_distance_m", command.tuning_config.pure_pursuit.goal_slowdown_distance, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_goal_tolerance_m", command.tuning_config.pure_pursuit.goal_tolerance, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_front_caution_distance_m", command.tuning_config.safety.front_caution_distance, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_front_stop_distance_m", command.tuning_config.safety.front_stop_distance, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_rear_caution_distance_m", command.tuning_config.safety.rear_caution_distance, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_rear_stop_distance_m", command.tuning_config.safety.rear_stop_distance, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_caution_max_velocity_mps", command.tuning_config.safety.caution_max_velocity, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_front_angle_limit_rad", command.tuning_config.safety.front_angle_limit_rad, command.has_tuning_config) ||
        !assignDoubleValue(values, "tune_front_stop_angle_limit_rad", command.tuning_config.safety.front_stop_angle_limit_rad, command.has_tuning_config)) {
        return std::nullopt;
    }
    return command;
}

ManualDriveInput manualDriveInput(webots::Keyboard* keyboard) {
    ManualDriveInput input;
    if (!keyboard) {
        return input;
    }

    bool forward = false;
    bool reverse = false;
    bool left = false;
    bool right = false;
    bool stop = false;
    for (int key = keyboard->getKey(); key != -1; key = keyboard->getKey()) {
        const int plain_key = key & webots::Keyboard::KEY;
        switch (plain_key) {
            case webots::Keyboard::UP:
            case 'W':
            case 'w':
                forward = true;
                break;
            case webots::Keyboard::DOWN:
            case 'S':
            case 's':
                reverse = true;
                break;
            case webots::Keyboard::LEFT:
            case 'A':
            case 'a':
                left = true;
                break;
            case webots::Keyboard::RIGHT:
            case 'D':
            case 'd':
                right = true;
                break;
            case ' ':
                stop = true;
                input.has_drive_command = true;
                break;
            case 'Q':
            case 'q':
                input.quit = true;
                break;
            case 'M':
            case 'm':
                input.save_map = true;
                break;
            default:
                break;
        }
    }

    if (!stop) {
        input.command.linear = forward == reverse ? 0.0 : (forward ? 0.18 : -0.10);
        input.command.angular = left == right ? 0.0 : (left ? 0.9 : -0.9);
        input.has_drive_command = forward || reverse || left || right;
    }
    return input;
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
        : display_(display), map_(std::move(map)) {
        if (display_) {
            const double map_width_m = map_.grid.width() * map_.grid.resolution();
            const double map_height_m = map_.grid.height() * map_.grid.resolution();
            if (map_width_m > 0.0 && map_height_m > 0.0) {
                scale_ = std::min(
                    static_cast<double>(display_->getWidth()) / map_width_m,
                    static_cast<double>(display_->getHeight()) / map_height_m);
            }
        }
    }

    void setGrid(const OccupancyGrid& grid) {
        map_.grid = grid;
    }

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
    double scale_{1.0};
};

class PlannedPathWorldOverlay {
public:
    explicit PlannedPathWorldOverlay(webots::Supervisor* supervisor) : supervisor_(supervisor) {}

    void update(const Path& path) {
        if (!supervisor_) {
            return;
        }
        ensureNodes();
        if (!ready_) {
            return;
        }
        const std::size_t segment_count = path.points.size() < 2
                                              ? 0
                                              : std::min<std::size_t>(path.points.size() - 1, kMaxSegments);
        for (std::size_t i = 0; i < kMaxSegments; ++i) {
            if (i < segment_count) {
                showSegment(i, path.points[i], path.points[i + 1]);
            } else {
                hideSegment(i);
            }
        }
        const std::size_t joint_count = std::min<std::size_t>(path.points.size(), kMaxJoints);
        for (std::size_t i = 0; i < kMaxJoints; ++i) {
            if (i < joint_count) {
                showJoint(i, path.points[i]);
            } else {
                hideJoint(i);
            }
        }
    }

    void hide() {
        if (!supervisor_) {
            return;
        }
        ensureNodes();
        for (std::size_t i = 0; ready_ && i < kMaxSegments; ++i) {
            hideSegment(i);
        }
        for (std::size_t i = 0; ready_ && i < kMaxJoints; ++i) {
            hideJoint(i);
        }
    }

private:
    static constexpr std::size_t kMaxSegments = 96;
    static constexpr std::size_t kMaxJoints = kMaxSegments + 1;

    void ensureNodes() {
        if (initialized_) {
            return;
        }
        initialized_ = true;
        webots::Node* root = supervisor_->getRoot();
        webots::Field* children = root ? root->getField("children") : nullptr;
        if (!children) {
            return;
        }

        for (std::size_t i = 0; i < kMaxSegments; ++i) {
            const std::string def_name = "PLANNED_PATH_SEGMENT_" + std::to_string(i);
            std::ostringstream node;
            node << "DEF " << def_name << " Transform { "
                 << "translation -20 -20 0.045 "
                 << "scale 0.001 0.045 0.006 "
                 << "children [ Shape { "
                 << "appearance PBRAppearance { baseColor 0.05 0.25 1 roughness 0.45 transparency 0.18 } "
                 << "geometry Box { size 1 1 1 } "
                 << "} ] }";
            children->importMFNodeFromString(-1, node.str());
            segments_.push_back(supervisor_->getFromDef(def_name));
        }
        for (std::size_t i = 0; i < kMaxJoints; ++i) {
            const std::string def_name = "PLANNED_PATH_JOINT_" + std::to_string(i);
            std::ostringstream node;
            node << "DEF " << def_name << " Transform { "
                 << "translation -20 -20 0.048 "
                 << "children [ Shape { "
                 << "appearance PBRAppearance { baseColor 0.05 0.25 1 roughness 0.45 transparency 0.18 } "
                 << "geometry Cylinder { radius 0.035 height 0.007 subdivision 16 } "
                 << "} ] }";
            children->importMFNodeFromString(-1, node.str());
            joints_.push_back(supervisor_->getFromDef(def_name));
        }
        ready_ = std::all_of(segments_.begin(), segments_.end(), [](const webots::Node* node) {
            return node != nullptr;
        }) && std::all_of(joints_.begin(), joints_.end(), [](const webots::Node* node) {
            return node != nullptr;
        });
    }

    void showSegment(std::size_t index, const Point2D& a, const Point2D& b) {
        webots::Node* node = segments_.at(index);
        const double dx = b.x - a.x;
        const double dy = b.y - a.y;
        const double length = std::hypot(dx, dy);
        if (!node || length < 0.02) {
            hideSegment(index);
            return;
        }
        const double translation[3] = {(a.x + b.x) / 2.0, (a.y + b.y) / 2.0, 0.045};
        const double rotation[4] = {0.0, 0.0, 1.0, std::atan2(dy, dx)};
        const double scale[3] = {length, 0.045, 0.006};
        node->getField("translation")->setSFVec3f(translation);
        node->getField("rotation")->setSFRotation(rotation);
        node->getField("scale")->setSFVec3f(scale);
    }

    void hideSegment(std::size_t index) {
        webots::Node* node = segments_.at(index);
        if (!node) {
            return;
        }
        const double translation[3] = {-20.0, -20.0, 0.045};
        const double scale[3] = {0.001, 0.045, 0.006};
        node->getField("translation")->setSFVec3f(translation);
        node->getField("scale")->setSFVec3f(scale);
    }

    void showJoint(std::size_t index, const Point2D& point) {
        webots::Node* node = joints_.at(index);
        if (!node) {
            return;
        }
        const double translation[3] = {point.x, point.y, 0.048};
        node->getField("translation")->setSFVec3f(translation);
    }

    void hideJoint(std::size_t index) {
        webots::Node* node = joints_.at(index);
        if (!node) {
            return;
        }
        const double translation[3] = {-20.0, -20.0, 0.048};
        node->getField("translation")->setSFVec3f(translation);
    }

    webots::Supervisor* supervisor_{nullptr};
    bool initialized_{false};
    bool ready_{false};
    std::vector<webots::Node*> segments_;
    std::vector<webots::Node*> joints_;
};

}  // namespace

int main(int argc, char** argv) {
    webots::Supervisor robot;
    const int time_step_ms = static_cast<int>(robot.getBasicTimeStep());
    webots::Keyboard* keyboard = robot.getKeyboard();
    if (keyboard) {
        keyboard->enable(time_step_ms);
    }
    WebotsHardware hardware(robot, time_step_ms);

    auto restaurant = createPrototypeRestaurantMap(0.05);
    const std::string map_input_json = argValueOr(argc, argv, "--map-input-json", getenvOr("MAP_INPUT_JSON", ""));
    bool loaded_map_from_json = false;
    bool loaded_destinations_from_json = false;
    if (!map_input_json.empty()) {
        RestaurantMap loaded_map;
        loaded_map_from_json = loadRestaurantMapJson(map_input_json, loaded_map);
        if (loaded_map_from_json) {
            restaurant.grid = std::move(loaded_map.grid);
            if (!loaded_map.destinations.empty()) {
                restaurant.destinations = std::move(loaded_map.destinations);
                loaded_destinations_from_json = true;
            }
        }
        std::cout << "map_input_json=" << map_input_json << "\n";
        std::cout << "map_loaded=" << (loaded_map_from_json ? "true" : "false") << "\n";
        std::cout << "destinations_loaded=" << (loaded_destinations_from_json ? "true" : "false") << "\n";
    }
    if (restaurant.destinations.find("HOME") == restaurant.destinations.end() ||
        restaurant.destinations.find("KITCHEN") == restaurant.destinations.end() ||
        !firstKnownTable(restaurant)) {
        std::cerr << "restaurant map must contain HOME, KITCHEN, and at least one TABLE_N destination.\n";
        return 2;
    }
    DebugDisplayRenderer debug_renderer(hardware.display(), restaurant);
    PlannedPathWorldOverlay path_overlay(&robot);
    OccupancyRayMapper manual_mapper;
    if (loaded_map_from_json) {
        manual_mapper.grid() = restaurant.grid;
    }
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
    NavigatorConfig navigation_config;
    Navigator navigator(restaurant, navigation_config);
    SafetySupervisor manual_safety(navigation_config.safety);
    auto slam_backend = createSlamBackend(getenvOr("SLAM_BACKEND", "known_pose"));
    RunLogger logger("restaurant_run.csv");
    const double max_time_s = getenvDoubleOr("MAX_TIME", 0.0);
    const std::string operating_mode = getenvOr("OPERATING_MODE", "NAVIGATION");
    const bool batch_mapping_mode = operating_mode == "MAPPING";
    bool manual_mapping_mode = operating_mode == "MANUAL_MAPPING" || operating_mode == "TELEOP_MAPPING";
    bool mapping_mode = batch_mapping_mode || manual_mapping_mode;
    const bool scan_localization_enabled = !mapping_mode && getenvBoolOr("ENABLE_SCAN_LOCALIZATION", false);
    const std::string map_output_prefix = getenvOr("MAP_OUTPUT_PREFIX", "webots_restaurant_map");
    const std::string control_file_path = getenvOr("CONTROL_FILE", "");
    const bool gui_control_mode = !control_file_path.empty();
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
    bool manual_map_saved = false;
    int last_gui_command_seq = -1;
    VelocityCommand gui_manual_command;
    bool gui_has_manual_command = false;
    constexpr double localization_update_period_s = 0.25;

    if (!control_file_path.empty()) {
        std::cout << "control_file=" << control_file_path << "\n";
    }

    if (!isKnownTable(restaurant, requested_destination)) {
        requested_destination = firstKnownTable(restaurant).value();
    }
    commandDestination(navigator, restaurant, requested_destination);

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
        if (!mapping_mode && scan_localization_enabled && scan_localization_active && !scan.ranges.empty() &&
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

        bool gui_save_map = false;
        bool gui_quit = false;
        if (const auto gui = readGuiCommand(control_file_path); gui && gui->seq != last_gui_command_seq) {
            last_gui_command_seq = gui->seq;
            if (gui->has_tuning_config) {
                navigation_config = gui->tuning_config;
                navigator.configure(navigation_config, estimated_pose);
                manual_safety.configure(navigation_config.safety);
                std::cout << "navigation_tuning planner_clearance=" << navigation_config.planner_clearance_radius_m
                          << " lookahead=" << navigation_config.pure_pursuit.lookahead_distance
                          << " front_stop=" << navigation_config.safety.front_stop_distance << "\n";
            }
            if (gui->tune_only) {
                std::cout << "gui_tuning_applied\n";
            } else if (gui->estop) {
                navigator.setEmergencyStop(true);
                manual_safety.setEmergencyStop(true);
                std::cout << "gui_estop=latched\n";
            } else if (gui->clear_estop) {
                navigator.setEmergencyStop(false);
                manual_safety.setEmergencyStop(false);
                std::cout << "gui_estop=released\n";
            } else {
                if (gui->mode == "manual" || gui->mode == "MANUAL") {
                    manual_mapping_mode = true;
                    mapping_mode = true;
                    std::cout << "control_mode=manual\n";
                } else if (gui->mode == "auto" || gui->mode == "AUTO") {
                    manual_mapping_mode = false;
                    mapping_mode = batch_mapping_mode;
                    if (!commandDestination(navigator, restaurant, requested_destination)) {
                        std::cout << "control_mode=auto command_rejected=" << requested_destination << "\n";
                    }
                    std::cout << "control_mode=auto\n";
                }
                if (gui->has_manual_command) {
                    gui_manual_command = gui->manual_command;
                    gui_has_manual_command = true;
                }
                if (gui->goal && isKnownDestination(restaurant, *gui->goal)) {
                    if (commandDestination(navigator, restaurant, *gui->goal)) {
                        requested_destination = *gui->goal;
                        std::cout << "gui_destination=" << requested_destination << "\n";
                    } else {
                        std::cout << "gui_destination_rejected=" << *gui->goal << "\n";
                    }
                }
            }
            gui_save_map = gui->save_map;
            gui_quit = gui->quit;
        }

        if (manual_mapping_mode) {
            if (!scan.ranges.empty()) {
                manual_mapper.integrateScan(estimated_pose, scan);
                debug_renderer.setGrid(manual_mapper.grid());
            }
            auto manual_input = manualDriveInput(keyboard);
            if (!manual_input.has_drive_command && gui_has_manual_command) {
                manual_input.command = gui_manual_command;
            }
            if (manual_input.save_map || gui_save_map) {
                const bool map_ok = saveManualRestaurantMap(restaurant, manual_mapper.grid(), map_output_prefix);
                manual_map_saved = manual_map_saved || map_ok;
                std::cout << "map_checkpoint_saved=" << (map_ok ? "true" : "false") << "\n";
                std::cout << "map_json=" << map_output_prefix << ".json\n";
                std::cout << "map_pgm=" << map_output_prefix << ".pgm\n";
            }
            const SafetyResult safe = manual_safety.apply(manual_input.command, scan);
            hardware.setVelocity(safe.command.linear, safe.command.angular);

            NavigatorStepResult manual_nav;
            manual_nav.command = safe.command;
            manual_nav.safety_state = safe.state;
            manual_nav.minimum_obstacle_distance = safe.minimum_obstacle_distance;
            manual_nav.active_goal = "MANUAL_MAP";
            if (++draw_counter % 5 == 0) {
                debug_renderer.draw(estimated_pose, scan, navigator, manual_nav);
                debug_image_drawn = true;
                if (!debug_export_path.empty() && debug_export_interval_s > 0.0 && robot.getTime() >= next_debug_export_s) {
                    debug_image_saved = debug_renderer.saveImage(debug_export_path);
                    next_debug_export_s = robot.getTime() + debug_export_interval_s;
                }
            }
            path_overlay.hide();
            logger.write(RunLogRecord{
                robot.getTime(),
                odometry_pose,
                estimated_pose,
                manual_nav.active_goal,
                requested_destination,
                safe.command.linear,
                safe.command.angular,
                safe.minimum_obstacle_distance,
                toString(manual_nav.planner_state),
                safe.state,
                0,
                0.0,
                0,
            });
            if (manual_input.quit || gui_quit) {
                hardware.setVelocity(0.0, 0.0);
                break;
            }
            continue;
        }

        if (gui_save_map) {
            const bool map_ok = saveManualRestaurantMap(restaurant, manual_mapper.grid(), map_output_prefix);
            manual_map_saved = manual_map_saved || map_ok;
            std::cout << "map_checkpoint_saved=" << (map_ok ? "true" : "false") << "\n";
            std::cout << "map_json=" << map_output_prefix << ".json\n";
            std::cout << "map_pgm=" << map_output_prefix << ".pgm\n";
        }
        if (gui_quit) {
            hardware.setVelocity(0.0, 0.0);
            break;
        }

        if (keyboard) {
            for (int key = keyboard->getKey(); key != -1; key = keyboard->getKey()) {
                const auto keyboard_destination = tableFromKey(key);
                if (keyboard_destination && isKnownTable(restaurant, *keyboard_destination) &&
                    *keyboard_destination != requested_destination) {
                    if (commandDestination(navigator, restaurant, *keyboard_destination)) {
                        requested_destination = *keyboard_destination;
                        robot.setCustomData(requested_destination);
                        std::cout << "keyboard_destination=" << requested_destination << "\n";
                    } else {
                        std::cout << "keyboard_destination_rejected=" << *keyboard_destination << "\n";
                    }
                }
            }
        }

        const std::string command = robot.getCustomData();
        if (command != last_command) {
            last_command = command;
            if (command == "ESTOP") {
                navigator.setEmergencyStop(true);
            } else if (command == "CLEAR_ESTOP") {
                navigator.setEmergencyStop(false);
            } else if (isKnownDestination(restaurant, command) && command != requested_destination) {
                if (commandDestination(navigator, restaurant, command)) {
                    requested_destination = command;
                } else {
                    std::cout << "custom_destination_rejected=" << command << "\n";
                }
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
        path_overlay.update(navigator.activePath());
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
            if (!gui_control_mode) {
                break;
            }
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
    const double final_kitchen_error = distance(last_estimated_pose, restaurant.destinations.at("KITCHEN"));
    std::cout << "mission_success=" << (mission_complete ? "true" : "false") << "\n";
    std::cout << "requested_destination=" << requested_destination << "\n";
    std::cout << "final_home_error_m=" << final_home_error << "\n";
    std::cout << "final_kitchen_error_m=" << final_kitchen_error << "\n";
    std::cout << "final_pose_x=" << last_estimated_pose.x << "\n";
    std::cout << "final_pose_y=" << last_estimated_pose.y << "\n";
    std::cout << "final_pose_theta=" << last_estimated_pose.theta << "\n";
    std::cout << "replanning_events=" << final_replanning_events << "\n";
    std::cout << "elapsed_time_s=" << robot.getTime() << "\n";

    if (mapping_mode && !manual_mapping_mode) {
        const std::string json_path = map_output_prefix + ".json";
        const std::string pgm_path = map_output_prefix + ".pgm";
        const bool map_ok = slam_backend->saveMap(map_output_prefix);
        std::cout << "mapping_mode=true\n";
        std::cout << "slam_backend=" << slam_backend->name() << "\n";
        std::cout << "map_json=" << json_path << "\n";
        std::cout << "map_pgm=" << pgm_path << "\n";
        std::cout << "map_saved=" << (map_ok ? "true" : "false") << "\n";
    } else if (manual_mapping_mode) {
        std::cout << "manual_mapping_mode=true\n";
        std::cout << "slam_backend=" << slam_backend->name() << "\n";
        std::cout << "map_json=" << map_output_prefix << ".json\n";
        std::cout << "map_pgm=" << map_output_prefix << ".pgm\n";
        std::cout << "map_saved=" << (manual_map_saved ? "true" : "false") << "\n";
    }

    return 0;
}
#else
int main() {
    std::cerr << "restaurant_delivery_controller requires Webots and WEBOTS_CONTROLLER.\n";
    return 1;
}
#endif
