#include "restaurant_robot/planning/astar.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <optional>
#include <queue>
#include <unordered_map>

namespace restaurant_robot {
namespace {

struct QueueNode {
    int x;
    int y;
    double f;
};

struct QueueCompare {
    bool operator()(const QueueNode& a, const QueueNode& b) const {
        return a.f > b.f;
    }
};

double octileHeuristic(int x0, int y0, int x1, int y1) {
    const double dx = std::abs(x0 - x1);
    const double dy = std::abs(y0 - y1);
    const double f = std::sqrt(2.0) - 1.0;
    return dx < dy ? f * dx + dy : f * dy + dx;
}

std::optional<GridIndex> nearestTraversableCell(const OccupancyGrid& grid, GridIndex seed, double max_radius_m) {
    if (grid.isTraversable(seed.x, seed.y)) {
        return seed;
    }

    const int max_radius_cells = std::max(1, static_cast<int>(std::ceil(max_radius_m / grid.resolution())));
    for (int radius = 1; radius <= max_radius_cells; ++radius) {
        std::optional<GridIndex> best;
        double best_dist_sq = std::numeric_limits<double>::infinity();
        for (int y = seed.y - radius; y <= seed.y + radius; ++y) {
            for (int x = seed.x - radius; x <= seed.x + radius; ++x) {
                if (std::max(std::abs(x - seed.x), std::abs(y - seed.y)) != radius) {
                    continue;
                }
                if (!grid.isTraversable(x, y)) {
                    continue;
                }
                const double dx = static_cast<double>(x - seed.x);
                const double dy = static_cast<double>(y - seed.y);
                const double dist_sq = dx * dx + dy * dy;
                if (dist_sq < best_dist_sq) {
                    best_dist_sq = dist_sq;
                    best = GridIndex{x, y};
                }
            }
        }
        if (best) {
            return best;
        }
    }
    return std::nullopt;
}

}  // namespace

AStarResult AStarPlanner::plan(const OccupancyGrid& grid, const Pose2D& start, const Pose2D& goal) const {
    auto start_cell = grid.worldToGrid(Point2D{start.x, start.y});
    if (!start_cell) {
        return {PlannerStatus::StartOutsideMap, {}, 0};
    }
    auto goal_cell = grid.worldToGrid(Point2D{goal.x, goal.y});
    if (!goal_cell) {
        return {PlannerStatus::GoalOutsideMap, {}, 0};
    }
    auto traversable_start = nearestTraversableCell(grid, *start_cell, 0.75);
    if (!traversable_start) {
        return {PlannerStatus::StartOccupied, {}, 0};
    }
    auto traversable_goal = nearestTraversableCell(grid, *goal_cell, 0.75);
    if (!traversable_goal) {
        return {PlannerStatus::GoalOccupied, {}, 0};
    }
    start_cell = traversable_start;
    goal_cell = traversable_goal;

    const int total = grid.width() * grid.height();
    std::vector<double> g_score(total, std::numeric_limits<double>::infinity());
    std::vector<int> parent(total, -1);
    std::vector<bool> closed(total, false);
    std::priority_queue<QueueNode, std::vector<QueueNode>, QueueCompare> open;

    const int start_idx = grid.index(start_cell->x, start_cell->y);
    const int goal_idx = grid.index(goal_cell->x, goal_cell->y);
    g_score[start_idx] = 0.0;
    open.push(QueueNode{
        start_cell->x,
        start_cell->y,
        octileHeuristic(start_cell->x, start_cell->y, goal_cell->x, goal_cell->y),
    });

    const int moves[8][2] = {
        {1, 0}, {-1, 0}, {0, 1}, {0, -1},
        {1, 1}, {1, -1}, {-1, 1}, {-1, -1},
    };

    int expanded = 0;
    while (!open.empty()) {
        const QueueNode current = open.top();
        open.pop();

        const int current_idx = grid.index(current.x, current.y);
        if (closed[current_idx]) {
            continue;
        }
        closed[current_idx] = true;
        ++expanded;

        if (current_idx == goal_idx) {
            std::vector<Point2D> reversed;
            int cursor = goal_idx;
            while (cursor != -1) {
                const int x = cursor % grid.width();
                const int y = cursor / grid.width();
                reversed.push_back(grid.gridToWorld(x, y));
                cursor = parent[cursor];
            }
            std::reverse(reversed.begin(), reversed.end());
            return {PlannerStatus::Success, Path{reversed}, expanded};
        }

        for (const auto& move : moves) {
            const int nx = current.x + move[0];
            const int ny = current.y + move[1];
            if (!grid.isTraversable(nx, ny)) {
                continue;
            }

            // Prevent cutting diagonally through table or wall corners.
            if (move[0] != 0 && move[1] != 0) {
                if (!grid.isTraversable(current.x + move[0], current.y) ||
                    !grid.isTraversable(current.x, current.y + move[1])) {
                    continue;
                }
            }

            const int neighbor_idx = grid.index(nx, ny);
            if (closed[neighbor_idx]) {
                continue;
            }

            const double step_cost = move[0] != 0 && move[1] != 0 ? std::sqrt(2.0) : 1.0;
            const double tentative = g_score[current_idx] + step_cost;
            if (tentative < g_score[neighbor_idx]) {
                parent[neighbor_idx] = current_idx;
                g_score[neighbor_idx] = tentative;
                const double h = octileHeuristic(nx, ny, goal_cell->x, goal_cell->y);
                open.push(QueueNode{nx, ny, tentative + h});
            }
        }
    }

    return {PlannerStatus::NoPath, {}, expanded};
}

std::string toString(PlannerStatus status) {
    switch (status) {
        case PlannerStatus::Success:
            return "SUCCESS";
        case PlannerStatus::StartOutsideMap:
            return "START_OUTSIDE_MAP";
        case PlannerStatus::GoalOutsideMap:
            return "GOAL_OUTSIDE_MAP";
        case PlannerStatus::StartOccupied:
            return "START_OCCUPIED";
        case PlannerStatus::GoalOccupied:
            return "GOAL_OCCUPIED";
        case PlannerStatus::NoPath:
            return "NO_PATH";
    }
    return "UNKNOWN";
}

}  // namespace restaurant_robot
