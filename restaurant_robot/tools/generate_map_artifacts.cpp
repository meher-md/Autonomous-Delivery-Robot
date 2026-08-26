#include <cmath>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>

#include "restaurant_robot/mapping/map_io.hpp"
#include "restaurant_robot/mapping/restaurant_map_factory.hpp"
#include "restaurant_robot/mapping/slam_backend.hpp"

using namespace restaurant_robot;

namespace {

LaserScan raycastScan(const OccupancyGrid& grid, const Pose2D& pose, int samples = 360, double max_range = 4.0) {
    LaserScan scan;
    scan.angle_min = -kPi;
    scan.angle_increment = samples > 1 ? 2.0 * kPi / static_cast<double>(samples - 1) : 0.0;
    scan.max_range = max_range;
    scan.ranges.reserve(samples);

    for (int i = 0; i < samples; ++i) {
        const double angle = normalizeAngle(pose.theta + scan.angle_min + i * scan.angle_increment);
        double range = max_range;
        for (double r = 0.05; r <= max_range; r += grid.resolution() / 2.0) {
            const Point2D point{pose.x + r * std::cos(angle), pose.y + r * std::sin(angle)};
            const auto cell = grid.worldToGrid(point);
            if (!cell || grid.get(cell->x, cell->y) == kOccupied) {
                range = r;
                break;
            }
        }
        scan.ranges.push_back(range);
    }
    return scan;
}

std::string getenvOr(const char* name, const std::string& fallback) {
    const char* value = std::getenv(name);
    return value ? std::string(value) : fallback;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc > 1 && std::string(argv[1]) == "--list-backends") {
        for (const auto& backend : availableSlamBackends()) {
            std::cout << backend.name
                      << " available=" << (backend.available ? "true" : "false")
                      << " description=\"" << backend.description << "\"";
            if (!backend.install_hint.empty()) {
                std::cout << " install_hint=\"" << backend.install_hint << "\"";
            }
            std::cout << "\n";
        }
        return 0;
    }

    std::string output_prefix = "restaurant_map";
    if (argc > 1) {
        output_prefix = argv[1];
    }
    std::string backend_name = getenvOr("SLAM_BACKEND", "known_pose");
    if (argc > 2) {
        backend_name = argv[2];
    }

    const auto reference = createPrototypeRestaurantMap(0.05);
    auto slam_backend = createSlamBackend(backend_name);
    const std::vector<Pose2D> exploration_poses = {
        {0.8, 0.8, 0.0},
        {2.8, 1.0, 0.2},
        {5.8, 1.0, 0.0},
        {7.0, 3.0, 1.2},
        {6.8, 6.2, 2.7},
        {3.2, 6.4, -2.8},
        {2.2, 3.8, -0.4},
        {4.4, 4.0, 1.4},
    };

    for (const auto& pose : exploration_poses) {
        slam_backend->update(raycastScan(reference.grid, pose), EncoderData{}, ImuData{}, pose);
    }

    const std::string json_path = output_prefix + ".json";
    const std::string pgm_path = output_prefix + ".pgm";
    if (!slam_backend->saveMap(output_prefix)) {
        std::cerr << "failed to save map artifacts for " << output_prefix << "\n";
        return 1;
    }

    int free_count = 0;
    int occupied_count = 0;
    int unknown_count = 0;
    for (const auto cell : slam_backend->currentMap().cells()) {
        if (cell == kFree) {
            ++free_count;
        } else if (cell == kOccupied) {
            ++occupied_count;
        } else {
            ++unknown_count;
        }
    }

    std::cout << "map_json=" << json_path << "\n";
    std::cout << "map_pgm=" << pgm_path << "\n";
    std::cout << "slam_backend=" << slam_backend->name() << "\n";
    std::cout << "free_cells=" << free_count << "\n";
    std::cout << "occupied_cells=" << occupied_count << "\n";
    std::cout << "unknown_cells=" << unknown_count << "\n";
    return free_count > 0 && occupied_count > 0 ? 0 : 2;
}
