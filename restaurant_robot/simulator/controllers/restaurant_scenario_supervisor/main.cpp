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
    const double* position{nullptr};
};

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

void setTranslation(webots::Node* node, double x, double y, double z) {
    if (!node) {
        return;
    }
    double value[3] = {x, y, z};
    node->getField("translation")->setSFVec3f(value);
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

void updateScenario(const std::string& scenario, double time, const std::vector<Proxy>& proxies) {
    if (scenario == "person_crossing") {
        const double phase = std::clamp((time - 8.0) / 8.0, 0.0, 1.0);
        setTranslation(proxies[0].node, 3.4, 1.1 + phase * 2.5, 0.45);
        setTranslation(proxies[1].node, -20.0, -20.0, 0.45);
        setTranslation(proxies[2].node, -21.0, -20.0, 0.45);
    } else if (scenario == "stationary_blockage") {
        setTranslation(proxies[0].node, 1.50, 2.95, 0.45);
        setTranslation(proxies[1].node, -20.0, -20.0, 0.45);
        setTranslation(proxies[2].node, -21.0, -20.0, 0.45);
    } else if (scenario == "moving_crowd") {
        setTranslation(proxies[0].node, 2.8 + std::sin(time * 0.45), 2.2, 0.45);
        setTranslation(proxies[1].node, 4.2, 1.2 + 1.2 * std::sin(time * 0.35), 0.45);
        setTranslation(proxies[2].node, 5.8 + 0.7 * std::sin(time * 0.55), 3.5, 0.45);
    } else if (scenario == "destination_change") {
        setTranslation(proxies[0].node, -20.0, -20.0, 0.45);
        setTranslation(proxies[1].node, -21.0, -20.0, 0.45);
        setTranslation(proxies[2].node, -22.0, -20.0, 0.45);
    } else if (scenario == "emergency_stop") {
        setTranslation(proxies[0].node, -20.0, -20.0, 0.45);
        setTranslation(proxies[1].node, -21.0, -20.0, 0.45);
        setTranslation(proxies[2].node, -22.0, -20.0, 0.45);
    } else if (scenario == "chair_moved") {
        if (time < 6.0) {
            setTranslation(proxies[0].node, -20.0, -20.0, 0.45);
        } else {
            setTranslation(proxies[0].node, 1.50, 2.95, 0.45);
        }
        setTranslation(proxies[1].node, -21.0, -20.0, 0.45);
        setTranslation(proxies[2].node, -22.0, -20.0, 0.45);
    } else if (scenario == "blocked_corridor") {
        setTranslation(proxies[0].node, 1.35, 2.90, 0.45);
        setTranslation(proxies[1].node, 1.55, 3.10, 0.45);
        setTranslation(proxies[2].node, 1.75, 3.30, 0.45);
    } else if (scenario == "localization_disturbance") {
        setTranslation(proxies[0].node, -20.0, -20.0, 0.45);
        setTranslation(proxies[1].node, -21.0, -20.0, 0.45);
        setTranslation(proxies[2].node, -22.0, -20.0, 0.45);
    } else {
        setTranslation(proxies[0].node, -20.0, -20.0, 0.45);
        setTranslation(proxies[1].node, -21.0, -20.0, 0.45);
        setTranslation(proxies[2].node, -22.0, -20.0, 0.45);
    }
}

}  // namespace

int main() {
    webots::Supervisor supervisor;
    const int time_step_ms = static_cast<int>(supervisor.getBasicTimeStep());
    const std::string scenario = getenvOr("SCENARIO", "person_crossing");
    const double max_time_s = getenvDoubleOr("MAX_TIME", 45.0);

    webots::Node* robot = supervisor.getFromDef("DELIVERY_ROBOT");
    webots::Field* robot_custom_data = robot ? robot->getField("customData") : nullptr;
    if (robot) {
        robot->enableContactPointsTracking(time_step_ms, true);
    }
    std::vector<Proxy> proxies = {
        {supervisor.getFromDef("DYNAMIC_OBSTACLE_1"), nullptr},
        {supervisor.getFromDef("DYNAMIC_OBSTACLE_2"), nullptr},
        {supervisor.getFromDef("DYNAMIC_OBSTACLE_3"), nullptr},
    };

    std::ofstream metrics("scenario_metrics.csv");
    metrics << "timestamp,scenario,robot_x,robot_y,min_dynamic_clearance,collision_count,clearance_collision_count,contact_collision_count,contact_point_count\n";

    CollisionCounts collisions;
    double previous_clearance_collision_time = -10.0;
    double previous_contact_collision_time = -10.0;
    while (supervisor.step(time_step_ms) != -1) {
        const double time = supervisor.getTime();
        updateScenario(scenario, time, proxies);
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

        if (time >= max_time_s) {
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
