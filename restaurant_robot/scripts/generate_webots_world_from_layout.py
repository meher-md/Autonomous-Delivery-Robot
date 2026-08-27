#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
from typing import Any

ROBOT_CLEARANCE_RADIUS_M = 0.32
FRONT_STOP_DISTANCE_M = 0.32
FRONT_CAUTION_DISTANCE_M = 1.0
MAX_SCENARIO_HUMANS = 12


def repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2]


def default_world_path() -> pathlib.Path:
    return repo_root() / "restaurant_robot" / "simulator" / "worlds" / "facility_layout_generated.wbt"


def default_map_path() -> pathlib.Path:
    return repo_root() / "restaurant_robot" / "config" / "facility_layout_map.json"


def controller_dir() -> pathlib.Path:
    return repo_root() / "restaurant_robot" / "simulator" / "controllers" / "restaurant_delivery_controller"


def controller_relative_map_path(path: pathlib.Path) -> str:
    resolved = path.resolve()
    try:
        return os.path.relpath(resolved, controller_dir())
    except ValueError:
        return str(resolved)


def portable_map_argument(map_json: str) -> str:
    path = pathlib.Path(map_json)
    if not path.is_absolute():
        path = repo_root() / path
    return controller_relative_map_path(path)


def fmt(value: float) -> str:
    return f"{value:.6g}"


def sanitize_def(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_]", "_", name.upper())
    if not cleaned or cleaned[0].isdigit():
        cleaned = "NODE_" + cleaned
    return cleaned


def zone_center(zone: dict[str, Any]) -> tuple[float, float]:
    return (float(zone["min_x"]) + float(zone["max_x"])) / 2.0, (float(zone["min_y"]) + float(zone["max_y"])) / 2.0


def zone_size(zone: dict[str, Any]) -> tuple[float, float]:
    return max(0.01, float(zone["max_x"]) - float(zone["min_x"])), max(0.01, float(zone["max_y"]) - float(zone["min_y"]))


def distance_to_zone(zone: dict[str, Any], pose: dict[str, Any]) -> float:
    x = float(pose["x"])
    y = float(pose["y"])
    dx = max(float(zone["min_x"]) - x, 0.0, x - float(zone["max_x"]))
    dy = max(float(zone["min_y"]) - y, 0.0, y - float(zone["max_y"]))
    return (dx * dx + dy * dy) ** 0.5


def nearest_table_destination_label(zone: dict[str, Any], destinations: dict[str, Any]) -> str | None:
    best_label: str | None = None
    best_distance = 1.25
    for label, pose in destinations.items():
        if not str(label).startswith("TABLE_"):
            continue
        distance = distance_to_zone(zone, pose)
        if distance < best_distance:
            best_label = str(label)
            best_distance = distance
    return best_label


def solid_box(def_name: str, name: str, x: float, y: float, sx: float, sy: float, sz: float, color: str) -> str:
    return f"""DEF {sanitize_def(def_name)} Solid {{
  name "{name}"
  translation {fmt(x)} {fmt(y)} {fmt(sz / 2.0)}
  children [
    Shape {{
      appearance PBRAppearance {{ baseColor {color} roughness 0.82 }}
      geometry Box {{ size {fmt(sx)} {fmt(sy)} {fmt(sz)} }}
    }}
  ]
  boundingObject Box {{ size {fmt(sx)} {fmt(sy)} {fmt(sz)} }}
}}"""


def visual_box(def_name: str, name: str, x: float, y: float, sx: float, sy: float, z: float, color: str, transparency: float) -> str:
    return f"""DEF {sanitize_def(def_name)} Solid {{
  name "{name}"
  translation {fmt(x)} {fmt(y)} {fmt(z)}
  children [
    Shape {{
      appearance PBRAppearance {{
        baseColor {color}
        transparency {fmt(transparency)}
        roughness 0.5
      }}
      geometry Box {{ size {fmt(sx)} {fmt(sy)} 0.018 }}
      castShadows FALSE
    }}
  ]
}}"""


def visual_rect_outline(def_name: str, name: str, x: float, y: float, sx: float, sy: float, z: float, color: str) -> str:
    thickness = 0.035
    return "\n\n".join([
        visual_box(f"{def_name}_N", f"{name} north edge", x, y + sy / 2.0, sx, thickness, z, color, 0.12),
        visual_box(f"{def_name}_S", f"{name} south edge", x, y - sy / 2.0, sx, thickness, z, color, 0.12),
        visual_box(f"{def_name}_E", f"{name} east edge", x + sx / 2.0, y, thickness, sy, z, color, 0.12),
        visual_box(f"{def_name}_W", f"{name} west edge", x - sx / 2.0, y, thickness, sy, z, color, 0.12),
    ])


def visual_disk(def_name: str, name: str, x: float, y: float, z: float, radius: float, color: str, transparency: float) -> str:
    return f"""DEF {sanitize_def(def_name)} Solid {{
  name "{name}"
  translation {fmt(x)} {fmt(y)} {fmt(z)}
  children [
    Shape {{
      appearance PBRAppearance {{
        baseColor {color}
        transparency {fmt(transparency)}
        roughness 0.5
      }}
      geometry Cylinder {{ radius {fmt(radius)} height 0.018 subdivision 64 }}
      castShadows FALSE
    }}
  ]
}}"""


def robot_boundary_visuals() -> str:
    return f"""    Transform {{
      translation 0 0 0.026
      children [
        Shape {{
          appearance PBRAppearance {{
            baseColor 0.10 0.25 1.00
            transparency 0.70
            roughness 0.5
          }}
          geometry Cylinder {{ radius {fmt(ROBOT_CLEARANCE_RADIUS_M)} height 0.012 subdivision 64 }}
        }}
      ]
    }}
    Transform {{
      translation {fmt(FRONT_STOP_DISTANCE_M / 2.0)} 0 0.036
      scale {fmt(FRONT_STOP_DISTANCE_M / 2.0)} 0.22 1
      children [
        Shape {{
          appearance PBRAppearance {{
            baseColor 1.00 0.00 0.00
            transparency 0.62
            roughness 0.5
          }}
          geometry Cylinder {{ radius 1 height 0.012 subdivision 64 }}
        }}
      ]
    }}
    Transform {{
      translation {fmt(FRONT_CAUTION_DISTANCE_M / 2.0)} 0 0.046
      scale {fmt(FRONT_CAUTION_DISTANCE_M / 2.0)} 0.50 1
      children [
        Shape {{
          appearance PBRAppearance {{
            baseColor 1.00 0.70 0.00
            transparency 0.78
            roughness 0.5
          }}
          geometry Cylinder {{ radius 1 height 0.012 subdivision 64 }}
        }}
      ]
    }}"""


def floor_marker(name: str, x: float, y: float, sx: float, sy: float, color: str) -> str:
    return f"""Solid {{
  name "{name}"
  translation {fmt(x)} {fmt(y)} 0.006
  children [
    Shape {{
      appearance PBRAppearance {{ baseColor {color} roughness 0.6 }}
      geometry Box {{ size {fmt(sx)} {fmt(sy)} 0.012 }}
      castShadows FALSE
    }}
  ]
}}"""


def table_solid(zone: dict[str, Any], table_index: int, label_override: str | None = None) -> str:
    x, y = zone_center(zone)
    sx, sy = zone_size(zone)
    # Use most of the reserved footprint so full-size people look proportional
    # without changing the navigation coordinates represented by the layout.
    table_x = min(max(sx * 0.55, 0.70), 1.20)
    table_y = min(max(sy * 0.45, 0.65), 0.80)
    label = label_override or str(zone.get("name") or f"TABLE_ZONE_{table_index}")
    tray = "DEF GENERATED_TABLE_TOP VarnishedPine {\n        textureTransform TextureTransform { scale 6 6 }\n      }" if table_index == 1 else "USE GENERATED_TABLE_TOP"
    return f"""DEF {sanitize_def(label + "_PROP")} Solid {{
  name "{label} table"
  translation {fmt(x)} {fmt(y)} 0.01
  children [
    Table {{
      translation 0 0 0
      name "{label}"
      size {fmt(table_x)} {fmt(table_y)} 0.75
      feetSize 0 0
      trayAppearance {tray}
      legAppearance MattePaint {{
        baseColor 0.12 0.12 0.12
      }}
    }}
  ]
  boundingObject Box {{ size {fmt(sx)} {fmt(sy)} 0.75 }}
}}

Chair {{
  translation {fmt(x - table_x / 2.0 - 0.38)} {fmt(y)} 0
  rotation 0 0 1 0
  name "{label} chair west"
}}

Chair {{
  translation {fmt(x + table_x / 2.0 + 0.38)} {fmt(y)} 0
  rotation 0 0 1 3.14159
  name "{label} chair east"
}}

Chair {{
  translation {fmt(x)} {fmt(y - table_y / 2.0 - 0.38)} 0
  rotation 0 0 1 1.5708
  name "{label} chair south"
}}

Chair {{
  translation {fmt(x)} {fmt(y + table_y / 2.0 + 0.38)} 0
  rotation 0 0 1 -1.5708
  name "{label} chair north"
}}"""


def scenario_humans() -> list[str]:
    palettes = [
        ("0.12 0.34 0.80", "0.10 0.10 0.13"),
        ("0.12 0.58 0.42", "0.16 0.16 0.18"),
        ("0.72 0.22 0.18", "0.15 0.15 0.18"),
        ("0.62 0.45 0.08", "0.12 0.16 0.24"),
        ("0.45 0.20 0.65", "0.20 0.16 0.12"),
        ("0.05 0.52 0.62", "0.13 0.13 0.16"),
    ]
    nodes: list[str] = []
    for index in range(1, MAX_SCENARIO_HUMANS + 1):
        shirt, pants = palettes[(index - 1) % len(palettes)]
        nodes.extend([
            "",
            f'''DEF DYNAMIC_OBSTACLE_{index} Pedestrian {{
  name "pedestrian customer {index}"
  translation {-20 - index} -20 1.27
  controller "<none>"
  controllerArgs [
    "--supervisor-controlled"
  ]
  enableBoundingObject TRUE
  shirtColor {shirt}
  pantsColor {pants}
}}''',
        ])
    return nodes


SEGMENTS_BY_DIGIT = {
    "0": "abcedf",
    "1": "bc",
    "2": "abged",
    "3": "abgcd",
    "4": "fgbc",
    "5": "afgcd",
    "6": "afgecd",
    "7": "abc",
    "8": "abcdefg",
    "9": "abfgcd",
}

SEGMENT_BOXES = {
    "a": (0.0, 0.095, 0.12, 0.025),
    "b": (0.065, 0.045, 0.025, 0.10),
    "c": (0.065, -0.065, 0.025, 0.10),
    "d": (0.0, -0.115, 0.12, 0.025),
    "e": (-0.065, -0.065, 0.025, 0.10),
    "f": (-0.065, 0.045, 0.025, 0.10),
    "g": (0.0, -0.01, 0.12, 0.025),
}


def digit_shapes(label: str) -> str:
    suffix = label.split("_", 1)[1] if "_" in label else label
    digits = [char for char in suffix if char.isdigit()]
    if not digits:
        return ""
    spacing = 0.18
    start = -spacing * (len(digits) - 1) / 2.0
    pieces: list[str] = []
    for digit_index, digit in enumerate(digits):
        digit_x = start + digit_index * spacing
        for segment in SEGMENTS_BY_DIGIT.get(digit, ""):
            sx, sy, bx, by = SEGMENT_BOXES[segment]
            pieces.append(
                f"""    Transform {{
      translation {fmt(digit_x + sx)} {fmt(sy)} 0.014
      children [
        Shape {{
          appearance PBRAppearance {{ baseColor 0.02 0.02 0.02 roughness 0.5 }}
          geometry Box {{ size {fmt(bx)} {fmt(by)} 0.012 }}
        }}
      ]
    }}"""
            )
    return "\n".join(pieces)


def service_marker(label: str, pose: dict[str, Any]) -> str:
    x = float(pose["x"])
    y = float(pose["y"])
    color = "0.10 0.20 0.70"
    radius = 0.22
    if label == "HOME":
        color = "0.12 0.48 0.18"
        radius = 0.18
    elif label == "KITCHEN":
        color = "0.80 0.42 0.05"
        radius = 0.18
    elif label == "CHARGING":
        color = "0.05 0.48 0.55"
        radius = 0.18

    digits = digit_shapes(label) if label.startswith("TABLE_") else ""
    digit_block = f"\n{digits}" if digits else ""
    return f"""Solid {{
  name "{label} service marker"
  translation {fmt(x)} {fmt(y)} 0.025
  children [
    Shape {{
      appearance PBRAppearance {{ baseColor {color} roughness 0.45 }}
      geometry Cylinder {{ radius {fmt(radius)} height 0.012 }}
    }}{digit_block}
  ]
}}"""


def robot_node(home: dict[str, Any], map_json: str | None) -> str:
    theta = float(home.get("theta", 0.0))
    controller_args = ""
    if map_json:
        escaped = portable_map_argument(map_json).replace("\\", "\\\\").replace('"', '\\"')
        controller_args = f"""  controllerArgs [
    "--map-input-json"
    "{escaped}"
  ]
"""
    return f"""DEF DELIVERY_ROBOT TurtleBot3Burger {{
  name "delivery robot"
  supervisor TRUE
  translation {fmt(float(home["x"]))} {fmt(float(home["y"]))} 0.0
  rotation 0 0 1 {fmt(theta)}
  controller "restaurant_delivery_controller"
{controller_args.rstrip()}
  extensionSlot [
    Lidar {{
      translation -0.03 0 0.19
      name "LDS-01"
      fieldOfView 6.283185307
      horizontalResolution 360
      numberOfLayers 1
      near 0.08
      minRange 0.12
      maxRange 3.5
      noise 0.005
    }}
    InertialUnit {{
      name "inertial unit"
    }}
    Gyro {{
      name "imu gyro"
    }}
    Display {{
      name "debug display"
      width 512
      height 512
    }}
{robot_boundary_visuals()}
  ]
}}"""


def generated_world_text(data: dict[str, Any]) -> str:
    layout = data.get("layout", {})
    width = float(layout.get("width_m", float(data["width"]) * float(data["resolution"])))
    height = float(layout.get("height_m", float(data["height"]) * float(data["resolution"])))
    wall_thickness = float(layout.get("wall_thickness_m", 0.12))
    destinations = data.get("destinations", {})
    home = destinations.get("HOME", {"x": wall_thickness + 0.5, "y": wall_thickness + 0.5, "theta": 0.0})
    zones = data.get("layout", {}).get("zones", [])
    map_json = layout.get("map_json")

    body: list[str] = [
        "#VRML_SIM R2025a utf8",
        "",
        'EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/objects/backgrounds/protos/TexturedBackground.proto"',
        'EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/objects/backgrounds/protos/TexturedBackgroundLight.proto"',
        'EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/objects/floors/protos/Floor.proto"',
        'EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/appearances/protos/Parquetry.proto"',
        'EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/appearances/protos/MattePaint.proto"',
        'EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/appearances/protos/VarnishedPine.proto"',
        'EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/objects/lights/protos/CeilingLight.proto"',
        'EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/objects/tables/protos/Table.proto"',
        'EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/objects/chairs/protos/Chair.proto"',
        'EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/humans/pedestrian/protos/Pedestrian.proto"',
        'EXTERNPROTO "https://raw.githubusercontent.com/cyberbotics/webots/R2025a/projects/robots/robotis/turtlebot/protos/TurtleBot3Burger.proto"',
        "",
        "WorldInfo {",
        "  basicTimeStep 32",
        "}",
        "",
        "Viewpoint {",
        "  orientation 0 1 0 1.5708",
        f"  position {fmt(width / 2.0)} {fmt(height / 2.0)} {fmt(max(width, height) * 1.35)}",
        "}",
        "",
        "TexturedBackground {",
        "}",
        "",
        "TexturedBackgroundLight {",
        "}",
        "",
        "Floor {",
        f"  translation {fmt(width / 2.0)} {fmt(height / 2.0)} 0",
        f"  size {fmt(width)} {fmt(height)}",
        "  appearance Parquetry {",
        '    type "light strip"',
        "    textureTransform TextureTransform {",
        "      scale 0.5 0.5",
        "    }",
        "  }",
        "}",
        "",
        "CeilingLight {",
        f"  translation {fmt(width * 0.25)} {fmt(height * 0.25)} 2.8",
        '  name "facility ceiling light 1"',
        "  bulbColor 1 0.86 0.62",
        "  pointLightColor 1 0.86 0.62",
        "  pointLightIntensity 2.5",
        "}",
        "",
        "CeilingLight {",
        f"  translation {fmt(width * 0.75)} {fmt(height * 0.25)} 2.8",
        '  name "facility ceiling light 2"',
        "  bulbColor 1 0.86 0.62",
        "  pointLightColor 1 0.86 0.62",
        "  pointLightIntensity 2.5",
        "}",
        "",
        "CeilingLight {",
        f"  translation {fmt(width * 0.25)} {fmt(height * 0.75)} 2.8",
        '  name "facility ceiling light 3"',
        "  bulbColor 1 0.86 0.62",
        "  pointLightColor 1 0.86 0.62",
        "  pointLightIntensity 2.5",
        "}",
        "",
        "CeilingLight {",
        f"  translation {fmt(width * 0.75)} {fmt(height * 0.75)} 2.8",
        '  name "facility ceiling light 4"',
        "  bulbColor 1 0.86 0.62",
        "  pointLightColor 1 0.86 0.62",
        "  pointLightIntensity 2.5",
        "}",
        "",
        robot_node(home, str(map_json) if map_json else None),
        "",
        'Robot {\n  name "scenario supervisor"\n  supervisor TRUE\n  controller "restaurant_scenario_supervisor"\n}',
        "",
        solid_box("WALL_NORTH", "wall north", width / 2.0, height + wall_thickness / 2.0, width + 2 * wall_thickness, wall_thickness, 1.2, "0.72 0.72 0.68"),
        "",
        solid_box("WALL_SOUTH", "wall south", width / 2.0, -wall_thickness / 2.0, width + 2 * wall_thickness, wall_thickness, 1.2, "0.72 0.72 0.68"),
        "",
        solid_box("WALL_EAST", "wall east", width + wall_thickness / 2.0, height / 2.0, wall_thickness, height, 1.2, "0.72 0.72 0.68"),
        "",
        solid_box("WALL_WEST", "wall west", -wall_thickness / 2.0, height / 2.0, wall_thickness, height, 1.2, "0.72 0.72 0.68"),
    ]

    table_count = 0
    for index, zone in enumerate(zones, start=1):
        x, y = zone_center(zone)
        sx, sy = zone_size(zone)
        zone_type = zone.get("type", "")
        if zone_type == "wall":
            zone_name = str(zone.get("name") or f"layout wall {index}")
            is_counter = zone_name.startswith("KITCHEN_COUNTER")
            height_m = 0.90 if is_counter else 1.2
            color = "0.42 0.30 0.18" if is_counter else "0.48 0.50 0.50"
            body.extend(["", solid_box(f"WALL_{index}", zone_name, x, y, sx, sy, height_m, color)])
            body.extend(["", visual_box(f"ALGO_RAW_WALL_{index}", f"algorithm raw wall {index}", x, y, sx, sy, 0.022, "0.05 0.05 0.05", 0.45)])
        elif zone_type == "no_go":
            body.extend(["", solid_box(f"NO_GO_{index}", f"no go zone {index}", x, y, sx, sy, 0.18, "0.75 0.22 0.18")])
            body.extend(["", visual_box(f"ALGO_RAW_NO_GO_{index}", f"algorithm raw no-go {index}", x, y, sx, sy, 0.022, "0.75 0.05 0.05", 0.42)])
        elif zone_type == "table_zone":
            table_count += 1
            label = nearest_table_destination_label(zone, destinations) or str(zone.get("name") or f"table zone {index}")
            body.extend(["", table_solid(zone, table_count, label)])
            body.extend(["", visual_box(f"ALGO_RAW_{label}", f"algorithm raw footprint {label}", x, y, sx, sy, 0.022, "0.70 0.34 0.05", 0.70)])
            body.extend(["", visual_rect_outline(f"ALGO_BOUNDARY_{label}", f"algorithm table boundary {label}", x, y, sx, sy, 0.04, "1.00 0.20 0.00")])
        elif zone_type == "kitchen_zone":
            body.extend(["", floor_marker(f"kitchen zone {index}", x, y, sx, sy, "0.86 0.53 0.14")])
        elif zone_type == "charging_zone":
            body.extend(["", floor_marker(f"charging zone {index}", x, y, sx, sy, "0.16 0.62 0.68")])

    for label, pose in sorted(destinations.items()):
        body.extend(["", service_marker(label, pose)])

    body.extend(scenario_humans())
    body.append("")
    return "\n".join(body)


def generate_world_file(data: dict[str, Any], output_path: pathlib.Path) -> pathlib.Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generated_world_text(data), encoding="utf-8")
    return output_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("layout_json", type=pathlib.Path, nargs="?", default=default_map_path())
    parser.add_argument("world_path", type=pathlib.Path, nargs="?", default=default_world_path())
    args = parser.parse_args()

    with args.layout_json.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    data.setdefault("layout", {})["map_json"] = str(args.layout_json.resolve())
    output = generate_world_file(data, args.world_path.resolve())
    print(output)


if __name__ == "__main__":
    main()
