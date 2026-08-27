#include <algorithm>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

#ifdef WEBOTS_CONTROLLER
#include <webots/Node.hpp>
#include <webots/Field.hpp>
#include <webots/Supervisor.hpp>

namespace {

struct Proxy {
    webots::Node* node{nullptr};
    webots::Node* boundary{nullptr};
    const double* position{nullptr};
    webots::Field* rotation{nullptr};
    webots::Field* left_arm{nullptr};
    webots::Field* right_arm{nullptr};
    webots::Field* left_leg{nullptr};
    webots::Field* right_leg{nullptr};
    webots::Field* left_knee{nullptr};
    webots::Field* right_knee{nullptr};
};

struct Point2 {
    double x{0.0};
    double y{0.0};
};

struct RoutePose {
    double x{0.0};
    double y{0.0};
    double yaw{0.0};
};

using Route = std::vector<Point2>;

struct CollisionCounts {
    int clearance{0};
    int contact{0};
};

std::string getenvOr(const char* name, const std::string& fallback) {
    const char* value = std::getenv(name);
    return value ? std::string(value) : fallback;
}

double getenvDoubleOr(const char* name, double fallback) {
    const char* value = std::getenv(name);
    return value ? std::atof(value) : fallback;
}

int getenvIntOr(const char* name, int fallback) {
    const char* value = std::getenv(name);
    return value ? std::atoi(value) : fallback;
}

void setTranslation(webots::Node* node, double x, double y, double z) {
    if (!node) {
        return;
    }
    double value[3] = {x, y, z};
    node->getField("translation")->setSFVec3f(value);
}

void setProxyTranslation(const Proxy& proxy, double x, double y, double z) {
    setTranslation(proxy.node, x, y, z);
    setTranslation(proxy.boundary, x, y, 0.03);
}

void setRotation(webots::Field* field, double x, double y, double z, double angle) {
    if (!field) {
        return;
    }
    const double value[4] = {x, y, z, angle};
    field->setSFRotation(value);
}

void setJointAngle(webots::Field* field, double angle) {
    if (field) {
        field->setSFFloat(angle);
    }
}

void setWalkingPose(const Proxy& proxy, double walking_distance, bool walking) {
    const double phase = walking ? walking_distance * 10.0 : 0.0;
    const double swing = std::sin(phase);
    const double left_knee = walking ? 0.48 * std::max(0.0, -swing) : 0.0;
    const double right_knee = walking ? 0.48 * std::max(0.0, swing) : 0.0;
    setJointAngle(proxy.left_arm, -0.55 * swing);
    setJointAngle(proxy.right_arm, 0.55 * swing);
    setJointAngle(proxy.left_leg, 0.62 * swing);
    setJointAngle(proxy.right_leg, -0.62 * swing);
    setJointAngle(proxy.left_knee, left_knee);
    setJointAngle(proxy.right_knee, right_knee);
}

void setProxyPose(const Proxy& proxy, double x, double y, double yaw, double walking_distance, bool walking = true) {
    const double bounce = walking ? 0.018 * std::abs(std::sin(walking_distance * 10.0)) : 0.0;
    setProxyTranslation(proxy, x, y, 1.27 + bounce);
    setRotation(proxy.rotation, 0.0, 0.0, 1.0, yaw);
    setWalkingPose(proxy, walking_distance, walking);
}

double routeLength(const Route& route) {
    double length = 0.0;
    for (std::size_t i = 0; i < route.size(); ++i) {
        const Point2& from = route[i];
        const Point2& to = route[(i + 1) % route.size()];
        length += std::hypot(to.x - from.x, to.y - from.y);
    }
    return length;
}

RoutePose sampleRoute(const Route& route, double distance) {
    const double length = routeLength(route);
    if (route.size() < 2 || length <= 0.0) {
        return {};
    }
    double remaining = std::fmod(distance, length);
    if (remaining < 0.0) {
        remaining += length;
    }
    for (std::size_t i = 0; i < route.size(); ++i) {
        const Point2& from = route[i];
        const Point2& to = route[(i + 1) % route.size()];
        const double segment = std::hypot(to.x - from.x, to.y - from.y);
        if (remaining <= segment || i + 1 == route.size()) {
            const double ratio = segment > 0.0 ? remaining / segment : 0.0;
            return {
                from.x + ratio * (to.x - from.x),
                from.y + ratio * (to.y - from.y),
                std::atan2(to.y - from.y, to.x - from.x),
            };
        }
        remaining -= segment;
    }
    return {};
}

const std::vector<Route>& crowdRoutes(bool generated_facility) {
    static const std::vector<Route> prototype_routes = {
        {{5.45, 1.0}, {17.2, 1.0}, {17.2, 17.2}, {5.45, 17.2}},
        {{1.0, 1.0}, {17.0, 1.0}, {17.0, 2.2}, {1.0, 2.2}},
        {{4.7, 2.4}, {5.3, 2.4}, {5.3, 13.5}, {4.7, 13.5}},
        {{9.8, 5.5}, {10.3, 5.5}, {10.3, 16.8}, {9.8, 16.8}},
    };
    static const std::vector<Route> generated_routes = {
        {{5.45, 1.0}, {17.2, 1.0}, {17.2, 17.2}, {5.45, 17.2}},
        {{1.0, 1.0}, {17.0, 1.0}, {17.0, 2.2}, {1.0, 2.2}},
        {{4.7, 2.4}, {5.3, 2.4}, {5.3, 13.5}, {4.7, 13.5}},
        {{9.8, 5.5}, {10.3, 5.5}, {10.3, 16.8}, {9.8, 16.8}},
    };
    return generated_facility ? generated_routes : prototype_routes;
}

void hideProxy(const Proxy& proxy, std::size_t index) {
    setProxyPose(proxy, -20.0 - static_cast<double>(index), -20.0, 0.0, 0.0, false);
}

double distance2d(const double* a, const double* b) {
    if (!a || !b) {
        return 1000.0;
    }
    return std::hypot(a[0] - b[0], a[1] - b[1]);
}

int nonFloorContactPointCount(webots::Node* robot) {
    if (!robot) {
        return 0;
    }

    int count = 0;
    int total = 0;
    const webots::ContactPoint* contacts = robot->getContactPoints(true, &total);
    for (int i = 0; i < total; ++i) {
        if (contacts[i].point[2] < 0.04) {
            continue;
        }
        ++count;
    }
    return count;
}

void updateScenario(
    const std::string& scenario,
    double time,
    const std::vector<Proxy>& proxies,
    int human_count,
    bool generated_facility) {
    for (std::size_t i = 3; i < proxies.size(); ++i) {
        hideProxy(proxies[i], i);
    }
    if (scenario == "person_crossing") {
        const double phase = std::clamp((time - 8.0) / 8.0, 0.0, 1.0);
        setProxyPose(proxies[0], 5.0, 1.1 + phase * 2.0, 1.5708, phase * 2.0);
        hideProxy(proxies[1], 1);
        hideProxy(proxies[2], 2);
    } else if (scenario == "stationary_blockage") {
        setProxyPose(proxies[0], 1.50, 2.40, 0.0, 0.0, false);
        hideProxy(proxies[1], 1);
        hideProxy(proxies[2], 2);
    } else if (scenario == "moving_crowd") {
        const std::vector<Route>& routes = crowdRoutes(generated_facility);
        for (std::size_t i = 0; i < proxies.size(); ++i) {
            if (static_cast<int>(i) >= human_count) {
                hideProxy(proxies[i], i);
                continue;
            }
            const Route& route = routes[i % routes.size()];
            const double speed = 0.48 + 0.04 * static_cast<double>(i % 3);
            const double offset = routeLength(route) * std::fmod(static_cast<double>(i) * 0.381966, 1.0);
            const double distance = offset + speed * time;
            const RoutePose pose = sampleRoute(route, distance);
            setProxyPose(proxies[i], pose.x, pose.y, pose.yaw, distance);
        }
    } else if (scenario == "destination_change") {
        hideProxy(proxies[0], 0);
        hideProxy(proxies[1], 1);
        hideProxy(proxies[2], 2);
    } else if (scenario == "emergency_stop") {
        hideProxy(proxies[0], 0);
        hideProxy(proxies[1], 1);
        hideProxy(proxies[2], 2);
    } else if (scenario == "chair_moved") {
        if (time < 6.0) {
            hideProxy(proxies[0], 0);
        } else {
            setProxyPose(proxies[0], 1.50, 2.40, 0.0, 0.0, false);
        }
        hideProxy(proxies[1], 1);
        hideProxy(proxies[2], 2);
    } else if (scenario == "blocked_corridor") {
        setProxyPose(proxies[0], 4.65, 2.25, 0.0, 0.0, false);
        setProxyPose(proxies[1], 5.00, 2.25, 0.0, 0.0, false);
        setProxyPose(proxies[2], 5.35, 2.25, 0.0, 0.0, false);
    } else if (scenario == "localization_disturbance") {
        hideProxy(proxies[0], 0);
        hideProxy(proxies[1], 1);
        hideProxy(proxies[2], 2);
    } else {
        hideProxy(proxies[0], 0);
        hideProxy(proxies[1], 1);
        hideProxy(proxies[2], 2);
    }
}

}  // namespace

int main() {
    webots::Supervisor supervisor;
    const int time_step_ms = static_cast<int>(supervisor.getBasicTimeStep());
    const std::string scenario = getenvOr("SCENARIO", "person_crossing");
    const double max_time_s = getenvDoubleOr("MAX_TIME", 45.0);
    constexpr int kMaximumHumanCount = 12;
    const int human_count = std::clamp(getenvIntOr("HUMAN_COUNT", 3), 1, kMaximumHumanCount);
    const std::string scene_export_path = getenvOr("WORLD_SCREENSHOT_PATH", "");
    const double scene_export_time_s = getenvDoubleOr("WORLD_SCREENSHOT_TIME", 0.5);

    webots::Node* robot = supervisor.getFromDef("DELIVERY_ROBOT");
    webots::Field* robot_custom_data = robot ? robot->getField("customData") : nullptr;
    if (robot) {
        robot->enableContactPointsTracking(time_step_ms, true);
    }
    std::vector<Proxy> proxies;
    for (int i = 1; i <= kMaximumHumanCount; ++i) {
        const std::string def = "DYNAMIC_OBSTACLE_" + std::to_string(i);
        webots::Node* node = supervisor.getFromDef(def);
        if (!node) {
            continue;
        }
        Proxy proxy;
        proxy.node = node;
        proxy.boundary = supervisor.getFromDef(def + "_KEEP_OUT");
        proxy.rotation = node->getField("rotation");
        proxy.left_arm = node->getField("leftArmAngle");
        proxy.right_arm = node->getField("rightArmAngle");
        proxy.left_leg = node->getField("leftLegAngle");
        proxy.right_leg = node->getField("rightLegAngle");
        proxy.left_knee = node->getField("leftLowerLegAngle");
        proxy.right_knee = node->getField("rightLowerLegAngle");
        proxies.push_back(proxy);
    }
    if (proxies.size() < 3) {
        std::cerr << "The world must provide at least three DYNAMIC_OBSTACLE nodes.\n";
        return 1;
    }
    const bool generated_facility = supervisor.getFromDef("WALL_NORTH") != nullptr;
    std::cout << "human_count=" << human_count << "\n";

    std::ofstream metrics("scenario_metrics.csv");
    metrics << "timestamp,scenario,robot_x,robot_y,min_dynamic_clearance,collision_count,clearance_collision_count,contact_collision_count,contact_point_count\n";

    CollisionCounts collisions;
    double previous_clearance_collision_time = -10.0;
    double previous_contact_collision_time = -10.0;
    bool scene_exported = false;
    while (supervisor.step(time_step_ms) != -1) {
        const double time = supervisor.getTime();
        updateScenario(scenario, time, proxies, human_count, generated_facility);
        if (!scene_exported && !scene_export_path.empty() && time >= scene_export_time_s) {
            supervisor.exportImage(scene_export_path, 95);
            scene_exported = true;
            std::cout << "world_screenshot=" << scene_export_path << "\n";
        }
        if (scenario == "destination_change" && robot_custom_data) {
            robot_custom_data->setSFString(time < 6.0 ? "TABLE_2" : "TABLE_4");
        } else if (scenario == "emergency_stop" && robot_custom_data) {
            robot_custom_data->setSFString(time < 4.0 ? "TABLE_3" : "ESTOP");
        } else if (scenario == "localization_disturbance" && robot_custom_data) {
            robot_custom_data->setSFString(time < 4.0 ? "TABLE_3" : "DISTURB_POSE");
        }

        const double* robot_position = robot ? robot->getPosition() : nullptr;
        double min_clearance = 1000.0;
        for (auto& proxy : proxies) {
            proxy.position = proxy.node ? proxy.node->getPosition() : nullptr;
            min_clearance = std::min(min_clearance, distance2d(robot_position, proxy.position));
        }

        if (min_clearance < 0.22 && time - previous_clearance_collision_time > 0.5) {
            ++collisions.clearance;
            previous_clearance_collision_time = time;
        }
        const int contact_point_count = nonFloorContactPointCount(robot);
        if (contact_point_count > 0 && time - previous_contact_collision_time > 0.5) {
            ++collisions.contact;
            previous_contact_collision_time = time;
        }
        const int collision_count = std::max(collisions.clearance, collisions.contact);

        metrics << time << ","
                << scenario << ","
                << (robot_position ? robot_position[0] : 0.0) << ","
                << (robot_position ? robot_position[1] : 0.0) << ","
                << min_clearance << ","
                << collision_count << ","
                << collisions.clearance << ","
                << collisions.contact << ","
                << contact_point_count << "\n";

        if (max_time_s > 0.0 && time >= max_time_s) {
            break;
        }
    }

    const int final_collision_count = std::max(collisions.clearance, collisions.contact);
    std::cout << "contact_collision_count=" << collisions.contact << "\n";
    std::cout << "clearance_collision_count=" << collisions.clearance << "\n";
    std::cout << "scenario=" << scenario << "\n";
    std::cout << "collision_count=" << final_collision_count << "\n";
    return final_collision_count == 0 ? 0 : 2;
}
#else
int main() {
    std::cerr << "restaurant_scenario_supervisor requires Webots and WEBOTS_CONTROLLER.\n";
    return 1;
}
#endif
