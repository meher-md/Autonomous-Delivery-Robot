#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib
import re
from typing import Any

ROBOT_CLEARANCE_RADIUS_M = 0.40
FRONT_STOP_DISTANCE_M = 0.32
FRONT_CAUTION_DISTANCE_M = 1.0


def repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parents[2]


def default_world_path() -> pathlib.Path:
    return repo_root() / "restaurant_robot" / "simulator" / "worlds" / "facility_layout_generated.wbt"


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
    }}
  ]
}}"""


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
    }}
  ]
}}"""


def table_solid(zone: dict[str, Any], table_index: int) -> str:
    x, y = zone_center(zone)
    sx, sy = zone_size(zone)
    table_x = min(max(sx * 0.82, 0.45), 1.4)
    table_y = min(max(sy * 0.82, 0.45), 1.4)
    label = str(zone.get("name") or f"TABLE_ZONE_{table_index}")
    tray = "DEF GENERATED_TABLE_TOP VarnishedPine {\n        textureTransform TextureTransform { scale 6 6 }\n      }" if table_index == 1 else "USE GENERATED_TABLE_TOP"
    return f"""DEF {sanitize_def(label + "_PROP")} Solid {{
  name "{label} table"
  translation {fmt(x)} {fmt(y)} 0.01
  children [
    Table {{
      translation 0 0 0
      name "{label}"
      size {fmt(table_x)} {fmt(table_y)} 0.72
      feetSize 0 0
      trayAppearance {tray}
      legAppearance MattePaint {{
        baseColor 0.12 0.12 0.12
      }}
    }}
  ]
  boundingObject Box {{ size {fmt(sx)} {fmt(sy)} 0.72 }}
}}"""


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
        escaped = map_json.replace("\\", "\\\\").replace('"', '\\"')
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
        f"  translation {fmt(width * 0.35)} {fmt(height * 0.35)} 2.5",
        '  name "facility ceiling light 1"',
        "  bulbColor 1 0.86 0.62",
        "  pointLightColor 1 0.86 0.62",
        "  pointLightIntensity 2.5",
        "}",
        "",
        "CeilingLight {",
        f"  translation {fmt(width * 0.72)} {fmt(height * 0.70)} 2.5",
        '  name "facility ceiling light 2"',
        "  bulbColor 1 0.86 0.62",
        "  pointLightColor 1 0.86 0.62",
        "  pointLightIntensity 2.5",
        "}",
        "",
        robot_node(home, str(map_json) if map_json else None),
        "",
        'Robot {\n  name "scenario supervisor"\n  supervisor TRUE\n  controller "restaurant_scenario_supervisor"\n}',
        "",
        solid_box("WALL_NORTH", "wall north", width / 2.0, height + wall_thickness / 2.0, width + 2 * wall_thickness, wall_thickness, 0.5, "0.72 0.72 0.68"),
        "",
        solid_box("WALL_SOUTH", "wall south", width / 2.0, -wall_thickness / 2.0, width + 2 * wall_thickness, wall_thickness, 0.5, "0.72 0.72 0.68"),
        "",
        solid_box("WALL_EAST", "wall east", width + wall_thickness / 2.0, height / 2.0, wall_thickness, height, 0.5, "0.72 0.72 0.68"),
        "",
        solid_box("WALL_WEST", "wall west", -wall_thickness / 2.0, height / 2.0, wall_thickness, height, 0.5, "0.72 0.72 0.68"),
    ]

    table_count = 0
    for index, zone in enumerate(zones, start=1):
        x, y = zone_center(zone)
        sx, sy = zone_size(zone)
        zone_type = zone.get("type", "")
        if zone_type == "wall":
            body.extend(["", solid_box(f"WALL_{index}", f"layout wall {index}", x, y, sx, sy, 0.5, "0.48 0.50 0.50")])
            body.extend(["", visual_box(f"ALGO_RAW_WALL_{index}", f"algorithm raw wall {index}", x, y, sx, sy, 0.022, "0.05 0.05 0.05", 0.45)])
        elif zone_type == "no_go":
            body.extend(["", solid_box(f"NO_GO_{index}", f"no go zone {index}", x, y, sx, sy, 0.18, "0.75 0.22 0.18")])
            body.extend(["", visual_box(f"ALGO_RAW_NO_GO_{index}", f"algorithm raw no-go {index}", x, y, sx, sy, 0.022, "0.75 0.05 0.05", 0.42)])
        elif zone_type == "table_zone":
            table_count += 1
            body.extend(["", table_solid(zone, table_count)])
            label = str(zone.get("name") or f"table zone {index}")
            body.extend(["", visual_box(f"ALGO_RAW_{label}", f"algorithm raw footprint {label}", x, y, sx, sy, 0.022, "0.28 0.10 0.00", 0.38)])
        elif zone_type == "kitchen_zone":
            body.extend(["", floor_marker(f"kitchen zone {index}", x, y, sx, sy, "0.86 0.53 0.14")])
        elif zone_type == "charging_zone":
            body.extend(["", floor_marker(f"charging zone {index}", x, y, sx, sy, "0.16 0.62 0.68")])

    for label, pose in sorted(destinations.items()):
        body.extend(["", service_marker(label, pose)])

    body.extend(
        [
            "",
            'DEF DYNAMIC_OBSTACLE_1 Pedestrian {\n  name "pedestrian customer 1"\n  translation -20 -20 1.27\n  shirtColor 0.12 0.34 0.80\n  pantsColor 0.10 0.10 0.13\n}',
            "",
            'DEF DYNAMIC_OBSTACLE_2 Pedestrian {\n  name "pedestrian customer 2"\n  translation -21 -20 1.27\n  shirtColor 0.12 0.58 0.42\n  pantsColor 0.16 0.16 0.18\n}',
            "",
            'DEF DYNAMIC_OBSTACLE_3 Pedestrian {\n  name "pedestrian customer 3"\n  translation -22 -20 1.27\n  shirtColor 0.72 0.22 0.18\n  pantsColor 0.15 0.15 0.18\n}',
            "",
        ]
    )
    return "\n".join(body)


def generate_world_file(data: dict[str, Any], output_path: pathlib.Path) -> pathlib.Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(generated_world_text(data), encoding="utf-8")
    return output_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("layout_json", type=pathlib.Path)
    parser.add_argument("world_path", type=pathlib.Path, nargs="?", default=default_world_path())
    args = parser.parse_args()

    with args.layout_json.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    data.setdefault("layout", {}).setdefault("map_json", str(args.layout_json.resolve()))
    output = generate_world_file(data, args.world_path.resolve())
    print(output)


if __name__ == "__main__":
    main()
