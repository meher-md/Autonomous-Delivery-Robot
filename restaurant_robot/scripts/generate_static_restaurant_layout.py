#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import pathlib

from generate_webots_world_from_layout import default_map_path, default_world_path, generate_world_file


FREE = 0
OCCUPIED = 100
WIDTH_M = 18.0
HEIGHT_M = 18.0
RESOLUTION_M = 0.05
WALL_THICKNESS_M = 0.12


def table_zone(name: str, x: float, y: float) -> dict:
    # The 2.2 x 1.8 m footprint contains a 1.2 x 0.8 m table and four chairs.
    return {
        "type": "table_zone",
        "min_x": x - 1.1,
        "min_y": y - 0.9,
        "max_x": x + 1.1,
        "max_y": y + 0.9,
        "name": name,
    }


def static_layout() -> tuple[list[dict], dict[str, dict]]:
    table_centers = [
        ("TABLE_1", 2.5, 4.0),
        ("TABLE_2", 2.5, 8.0),
        ("TABLE_3", 2.5, 12.0),
        ("TABLE_4", 8.0, 4.0),
        ("TABLE_5", 15.5, 4.0),
        ("TABLE_6", 15.5, 8.0),
        ("TABLE_7", 15.5, 12.0),
        ("TABLE_8", 12.0, 4.0),
    ]
    zones = [table_zone(name, x, y) for name, x, y in table_centers]
    zones.extend([
        {
            "type": "kitchen_zone",
            "min_x": 0.6,
            "min_y": 13.6,
            "max_x": 5.4,
            "max_y": 17.4,
            "name": "KITCHEN",
        },
        {
            "type": "wall",
            "min_x": 0.9,
            "min_y": 16.0,
            "max_x": 5.0,
            "max_y": 17.0,
            "name": "KITCHEN_COUNTER_BACK",
        },
        {
            "type": "wall",
            "min_x": 0.9,
            "min_y": 14.1,
            "max_x": 5.0,
            "max_y": 14.8,
            "name": "KITCHEN_COUNTER_SERVICE",
        },
        {
            "type": "charging_zone",
            "min_x": 15.4,
            "min_y": 15.2,
            "max_x": 17.2,
            "max_y": 17.2,
            "name": "CHARGING",
        },
    ])

    destinations: dict[str, dict] = {
        "HOME": {"x": 8.0, "y": 1.2, "theta": math.pi / 2.0},
        "CHARGING": {"x": 16.3, "y": 16.2, "theta": math.pi},
        "KITCHEN": {"x": 6.2, "y": 15.5, "theta": math.pi},
    }
    destinations.update({
        "TABLE_1": {"x": 4.15, "y": 4.0, "theta": math.pi},
        "TABLE_2": {"x": 4.15, "y": 8.0, "theta": math.pi},
        "TABLE_3": {"x": 4.15, "y": 12.0, "theta": math.pi},
        "TABLE_4": {"x": 8.0, "y": 2.45, "theta": math.pi / 2.0},
        "TABLE_5": {"x": 13.85, "y": 4.0, "theta": 0.0},
        "TABLE_6": {"x": 13.85, "y": 8.0, "theta": 0.0},
        "TABLE_7": {"x": 13.85, "y": 12.0, "theta": 0.0},
        "TABLE_8": {"x": 12.0, "y": 2.45, "theta": math.pi / 2.0},
    })
    return zones, destinations


def build_map() -> dict:
    zones, destinations = static_layout()
    width = int(round(WIDTH_M / RESOLUTION_M))
    height = int(round(HEIGHT_M / RESOLUTION_M))
    cells = [FREE] * (width * height)

    def set_cell(x: int, y: int, value: int) -> None:
        if 0 <= x < width and 0 <= y < height:
            cells[y * width + x] = value

    def fill_rect(zone: dict, value: int) -> None:
        min_x = max(0, int(math.floor(float(zone["min_x"]) / RESOLUTION_M)))
        max_x = min(width - 1, int(math.ceil(float(zone["max_x"]) / RESOLUTION_M)))
        min_y = max(0, int(math.floor(float(zone["min_y"]) / RESOLUTION_M)))
        max_y = min(height - 1, int(math.ceil(float(zone["max_y"]) / RESOLUTION_M)))
        for y in range(min_y, max_y + 1):
            row = y * width
            for x in range(min_x, max_x + 1):
                cells[row + x] = value

    for zone in zones:
        if zone["type"] in {"wall", "no_go", "table_zone"}:
            fill_rect(zone, OCCUPIED)

    for x in range(width):
        set_cell(x, 0, OCCUPIED)
        set_cell(x, height - 1, OCCUPIED)
    for y in range(height):
        set_cell(0, y, OCCUPIED)
        set_cell(width - 1, y, OCCUPIED)

    return {
        "width": width,
        "height": height,
        "resolution": RESOLUTION_M,
        "origin_x": 0.0,
        "origin_y": 0.0,
        "cells": cells,
        "destinations": destinations,
        "layout": {
            "width_m": WIDTH_M,
            "height_m": HEIGHT_M,
            "wall_thickness_m": WALL_THICKNESS_M,
            "origin_corner": "bottom-left",
            "zones": zones,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the tracked 18 x 18 m static restaurant layout.")
    parser.add_argument("--map", type=pathlib.Path, default=default_map_path())
    parser.add_argument("--world", type=pathlib.Path, default=default_world_path())
    parser.add_argument("--prototype-world", type=pathlib.Path)
    args = parser.parse_args()

    data = build_map()
    data["layout"]["map_json"] = str(args.map)
    data["layout"]["webots_world"] = str(args.world)
    args.map.parent.mkdir(parents=True, exist_ok=True)
    with args.map.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, separators=(",", ":"))
        handle.write("\n")
    generate_world_file(data, args.world.resolve())
    if args.prototype_world:
        generate_world_file(data, args.prototype_world.resolve())
    print(f"map={args.map.resolve()}")
    print(f"world={args.world.resolve()}")
    if args.prototype_world:
        print(f"prototype_world={args.prototype_world.resolve()}")


if __name__ == "__main__":
    main()
