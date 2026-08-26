#include "restaurant_robot/mapping/map_io.hpp"

#include <cctype>
#include <fstream>
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

}  // namespace

bool saveOccupancyGridJson(const OccupancyGrid& grid, const std::string& path) {
    std::ofstream out(path);
    if (!out) {
        return false;
    }

    out << "{\n";
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
    out << "\n  ]\n";
    out << "}\n";
    return true;
}

bool loadOccupancyGridJson(const std::string& path, OccupancyGrid& grid) {
    std::string text;
    if (!readFile(path, text)) {
        return false;
    }

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

}  // namespace restaurant_robot
