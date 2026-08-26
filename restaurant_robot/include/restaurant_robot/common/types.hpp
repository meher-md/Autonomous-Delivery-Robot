#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace restaurant_robot {

constexpr double kPi = 3.14159265358979323846;

struct Point2D {
    double x{0.0};
    double y{0.0};
};

struct Pose2D {
    double x{0.0};
    double y{0.0};
    double theta{0.0};
};

struct LaserScan {
    std::vector<double> ranges;
    double angle_min{-kPi};
    double angle_increment{0.0};
    double max_range{0.0};
    double timestamp{0.0};
};

struct EncoderData {
    double left_wheel_angle{0.0};
    double right_wheel_angle{0.0};
    double timestamp{0.0};
};

struct ImuData {
    double yaw{0.0};
    double yaw_rate{0.0};
    double angular_velocity_z{0.0};
    double timestamp{0.0};
};

struct VelocityCommand {
    double linear{0.0};
    double angular{0.0};
};

struct WheelVelocities {
    double left{0.0};
    double right{0.0};
};

struct Path {
    std::vector<Point2D> points;
};

struct Destination {
    std::string name;
    Pose2D pose;
};

double normalizeAngle(double angle);
double distance(const Point2D& a, const Point2D& b);
double distance(const Pose2D& a, const Pose2D& b);

}  // namespace restaurant_robot
