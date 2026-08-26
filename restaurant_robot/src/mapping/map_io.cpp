#include "restaurant_robot/mapping/map_io.hpp"

#include <cctype>
#include <fstream>
#include <iomanip>
#include <map>
#include <optional>
#include <sstream>
#include <string>
#include <utility>

namespace restaurant_robot {
namespace {

bool readFile(const std::string& path, std::string& data) {
    std::ifstream in(path);
    if (!in) {
        return false;
    }
    std::ostringstream buffer;
    buffer << in.rdbuf();
    data = buffer.str();
    return true;
}

bool extractNumber(const std::string& text, const std::string& key, double& value) {
    const std::string quoted = "\"" + key + "\"";
    const std::size_t key_pos = text.find(quoted);
    if (key_pos == std::string::npos) {
        return false;
    }
    const std::size_t colon = text.find(':', key_pos + quoted.size());
    if (colon == std::string::npos) {
        return false;
    }
    std::size_t begin = colon + 1;
    while (begin < text.size() && std::isspace(static_cast<unsigned char>(text[begin]))) {
        ++begin;
    }
    std::size_t end = begin;
    while (end < text.size() &&
           (std::isdigit(static_cast<unsigned char>(text[end])) || text[end] == '.' || text[end] == '-' ||
            text[end] == '+')) {
        ++end;
    }
    if (begin == end) {
        return false;
    }
    value = std::stod(text.substr(begin, end - begin));
    return true;
}

std::optional<std::string> extractObject(const std::string& text, const std::string& key) {
    const std::string quoted = "\"" + key + "\"";
    const std::size_t key_pos = text.find(quoted);
    if (key_pos == std::string::npos) {
        return std::nullopt;
    }
    const std::size_t colon = text.find(':', key_pos + quoted.size());
    const std::size_t open = text.find('{', colon);
    if (colon == std::string::npos || open == std::string::npos) {
        return std::nullopt;
    }

    int depth = 0;
    bool in_string = false;
    bool escaped = false;
    for (std::size_t i = open; i < text.size(); ++i) {
        const char ch = text[i];
        if (in_string) {
            if (escaped) {
                escaped = false;
            } else if (ch == '\\') {
                escaped = true;
            } else if (ch == '"') {
                in_string = false;
            }
            continue;
        }
        if (ch == '"') {
            in_string = true;
        } else if (ch == '{') {
            ++depth;
        } else if (ch == '}') {
            --depth;
            if (depth == 0) {
                return text.substr(open + 1, i - open - 1);
            }
        }
    }
    return std::nullopt;
}

bool extractCells(const std::string& text, std::vector<std::uint8_t>& cells) {
    const std::string key = "\"cells\"";
    const std::size_t key_pos = text.find(key);
    if (key_pos == std::string::npos) {
        return false;
    }
    const std::size_t open = text.find('[', key_pos + key.size());
    const std::size_t close = text.find(']', open);
    if (open == std::string::npos || close == std::string::npos || close <= open) {
        return false;
    }

    cells.clear();
    std::size_t cursor = open + 1;
    while (cursor < close) {
        while (cursor < close &&
               (std::isspace(static_cast<unsigned char>(text[cursor])) || text[cursor] == ',')) {
            ++cursor;
        }
        if (cursor >= close) {
            break;
        }

        std::size_t end = cursor;
        while (end < close && std::isdigit(static_cast<unsigned char>(text[end]))) {
            ++end;
        }
        if (end == cursor) {
            return false;
        }
        const int value = std::stoi(text.substr(cursor, end - cursor));
        if (value < 0 || value > 255) {
            return false;
        }
        cells.push_back(static_cast<std::uint8_t>(value));
        cursor = end;
    }
    return true;
}

bool parseOccupancyGridJson(const std::string& text, OccupancyGrid& grid) {
    double width = 0.0;
    double height = 0.0;
    double resolution = 0.0;
    double origin_x = 0.0;
    double origin_y = 0.0;
    std::vector<std::uint8_t> cells;
    if (!extractNumber(text, "width", width) || !extractNumber(text, "height", height) ||
        !extractNumber(text, "resolution", resolution) || !extractNumber(text, "origin_x", origin_x) ||
        !extractNumber(text, "origin_y", origin_y) || !extractCells(text, cells)) {
        return false;
    }

    const int w = static_cast<int>(width);
    const int h = static_cast<int>(height);
    if (w <= 0 || h <= 0 || resolution <= 0.0 || static_cast<int>(cells.size()) != w * h) {
        return false;
    }

    grid = OccupancyGrid(w, h, resolution, Point2D{origin_x, origin_y}, kUnknown);
    grid.cells() = std::move(cells);
    return true;
}

bool parseDestinations(const std::string& text, std::map<std::string, Pose2D>& destinations) {
    const auto object = extractObject(text, "destinations");
    if (!object) {
        destinations.clear();
        return true;
    }

    destinations.clear();
    std::size_t cursor = 0;
    while (cursor < object->size()) {
        const std::size_t label_open = object->find('"', cursor);
        if (label_open == std::string::npos) {
            break;
        }
        const std::size_t label_close = object->find('"', label_open + 1);
        if (label_close == std::string::npos) {
            return false;
        }
        const std::string label = object->substr(label_open + 1, label_close - label_open - 1);
        const std::size_t colon = object->find(':', label_close);
        const std::size_t value_open = object->find('{', colon);
        if (colon == std::string::npos || value_open == std::string::npos) {
            return false;
        }

        int depth = 0;
        std::size_t value_close = std::string::npos;
        for (std::size_t i = value_open; i < object->size(); ++i) {
            if ((*object)[i] == '{') {
                ++depth;
            } else if ((*object)[i] == '}') {
                --depth;
                if (depth == 0) {
                    value_close = i;
                    break;
                }
            }
        }
        if (value_close == std::string::npos) {
            return false;
        }

        const std::string pose_text = object->substr(value_open + 1, value_close - value_open - 1);
        double x = 0.0;
        double y = 0.0;
        double theta = 0.0;
        if (!extractNumber(pose_text, "x", x) || !extractNumber(pose_text, "y", y)) {
            return false;
        }
        extractNumber(pose_text, "theta", theta);
        destinations[label] = Pose2D{x, y, theta};
        cursor = value_close + 1;
    }

    return true;
}

std::string escapeJsonString(const std::string& text) {
    std::string out;
    for (const char ch : text) {
        if (ch == '"' || ch == '\\') {
            out.push_back('\\');
        }
        out.push_back(ch);
    }
    return out;
}

void writeOccupancyGridJsonFields(std::ostream& out, const OccupancyGrid& grid) {
    out << "  \"width\": " << grid.width() << ",\n";
    out << "  \"height\": " << grid.height() << ",\n";
    out << "  \"resolution\": " << grid.resolution() << ",\n";
    out << "  \"origin_x\": " << grid.origin().x << ",\n";
    out << "  \"origin_y\": " << grid.origin().y << ",\n";
    out << "  \"cells\": [";
    for (std::size_t i = 0; i < grid.cells().size(); ++i) {
        if (i != 0) {
            out << ",";
        }
        if (i % 40 == 0) {
            out << "\n    ";
        }
        out << static_cast<int>(grid.cells().at(i));
    }
    out << "\n  ]";
}

}  // namespace

bool saveOccupancyGridJson(const OccupancyGrid& grid, const std::string& path) {
    std::ofstream out(path);
    if (!out) {
        return false;
    }

    out << "{\n";
    writeOccupancyGridJsonFields(out, grid);
    out << "\n";
    out << "}\n";
    return true;
}

bool loadOccupancyGridJson(const std::string& path, OccupancyGrid& grid) {
    std::string text;
    if (!readFile(path, text)) {
        return false;
    }

    return parseOccupancyGridJson(text, grid);
}

bool saveRestaurantMapJson(const RestaurantMap& map, const std::string& path) {
    std::ofstream out(path);
    if (!out) {
        return false;
    }

    out << std::setprecision(10);
    out << "{\n";
    writeOccupancyGridJsonFields(out, map.grid);
    out << ",\n";
    out << "  \"destinations\": {";
    bool first = true;
    for (const auto& [name, pose] : map.destinations) {
        if (!first) {
            out << ",";
        }
        out << "\n    \"" << escapeJsonString(name) << "\": {"
            << "\"x\": " << pose.x << ", "
            << "\"y\": " << pose.y << ", "
            << "\"theta\": " << pose.theta << "}";
        first = false;
    }
    out << "\n  }\n";
    out << "}\n";
    return true;
}

bool loadRestaurantMapJson(const std::string& path, RestaurantMap& map) {
    std::string text;
    if (!readFile(path, text)) {
        return false;
    }

    OccupancyGrid grid;
    std::map<std::string, Pose2D> destinations;
    if (!parseOccupancyGridJson(text, grid) || !parseDestinations(text, destinations)) {
        return false;
    }

    map.grid = std::move(grid);
    map.destinations = std::move(destinations);
    return true;
}

}  // namespace restaurant_robot
