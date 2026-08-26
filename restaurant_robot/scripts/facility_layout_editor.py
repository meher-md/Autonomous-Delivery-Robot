#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import json
import math
import os
import pathlib
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

try:
    from generate_webots_world_from_layout import default_world_path, generate_world_file
except ModuleNotFoundError:
    from restaurant_robot.scripts.generate_webots_world_from_layout import default_world_path, generate_world_file

FREE = 0
OCCUPIED = 100
UNKNOWN = 255


class FacilityLayoutEditor:
    def __init__(self, root: tk.Tk, output_path: pathlib.Path):
        self.root = root
        self.output_path = output_path
        self.width_m = tk.DoubleVar(value=9.0)
        self.height_m = tk.DoubleVar(value=9.0)
        self.resolution_m = tk.DoubleVar(value=0.05)
        self.wall_thickness_m = tk.DoubleVar(value=0.12)
        self.origin_corner = tk.StringVar(value="bottom-left")
        self.tool = tk.StringVar(value="go")
        self.status = tk.StringVar(value="Drag a zone, or choose a point tool and click the map.")

        self.zones: list[dict] = []
        self.points: dict[str, dict] = {}
        self.undo_stack: list[tuple[list[dict], dict[str, dict]]] = []
        self.drag_start: tuple[float, float] | None = None
        self.drag_last: tuple[float, float] | None = None
        self.drag_mode: str | None = None
        self.move_undo_saved = False
        self.preview_rect: int | None = None
        self.selected: tuple[str, int | str] | None = None
        self.selected_label = tk.StringVar(value="None")
        self.edit_type = tk.StringVar(value="")
        self.edit_name = tk.StringVar(value="")
        self.edit_min_x = tk.StringVar(value="")
        self.edit_min_y = tk.StringVar(value="")
        self.edit_max_x = tk.StringVar(value="")
        self.edit_max_y = tk.StringVar(value="")
        self.edit_point_x = tk.StringVar(value="")
        self.edit_point_y = tk.StringVar(value="")
        self.edit_point_theta = tk.StringVar(value="")

        root.title("Facility Layout Editor")
        root.geometry("1060x780")

        self.main = ttk.Frame(root, padding=10)
        self.main.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        self.main.columnconfigure(1, weight=1)
        self.main.rowconfigure(0, weight=1)

        self._build_panel()
        self._build_canvas()
        if self.output_path.exists():
            self.load_layout_path(self.output_path, show_error=False)
        else:
            self.redraw()

    def _build_panel(self):
        panel = ttk.Frame(self.main, padding=(0, 0, 10, 0))
        panel.grid(row=0, column=0, sticky="ns")

        dimensions = ttk.LabelFrame(panel, text="Scale", padding=8)
        dimensions.grid(row=0, column=0, sticky="ew")
        ttk.Label(dimensions, text="Width m").grid(row=0, column=0, sticky="w")
        ttk.Entry(dimensions, textvariable=self.width_m, width=8).grid(row=0, column=1, sticky="w")
        ttk.Label(dimensions, text="Height m").grid(row=1, column=0, sticky="w")
        ttk.Entry(dimensions, textvariable=self.height_m, width=8).grid(row=1, column=1, sticky="w")
        ttk.Label(dimensions, text="Resolution m").grid(row=2, column=0, sticky="w")
        ttk.Entry(dimensions, textvariable=self.resolution_m, width=8).grid(row=2, column=1, sticky="w")
        ttk.Label(dimensions, text="Wall thick m").grid(row=3, column=0, sticky="w")
        ttk.Entry(dimensions, textvariable=self.wall_thickness_m, width=8).grid(row=3, column=1, sticky="w")
        ttk.Label(dimensions, text="Corner").grid(row=4, column=0, sticky="w")
        ttk.Combobox(
            dimensions,
            textvariable=self.origin_corner,
            values=["bottom-left", "top-left"],
            width=11,
            state="readonly",
        ).grid(row=4, column=1, sticky="w")
        ttk.Button(dimensions, text="Apply", command=self.apply_scale).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        tools = ttk.LabelFrame(panel, text="Draw", padding=8)
        tools.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        for row, (value, label) in enumerate(
            [
                ("select", "Select/edit"),
                ("go", "Go zone"),
                ("wall", "Wall"),
                ("no_go", "No-go zone"),
                ("table_zone", "Table zone"),
                ("kitchen_zone", "Kitchen zone"),
                ("charging_zone", "Charging zone"),
                ("table", "Table point"),
                ("kitchen", "Kitchen point"),
                ("home", "Home point"),
                ("charging", "Charging point"),
            ]
        ):
            ttk.Radiobutton(tools, text=label, value=value, variable=self.tool).grid(row=row, column=0, sticky="w")

        actions = ttk.Frame(panel)
        actions.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="Undo", command=self.undo).grid(row=0, column=0, sticky="ew")
        ttk.Button(actions, text="Clear", command=self.clear).grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ttk.Button(actions, text="Open", command=self.open_layout).grid(row=1, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(actions, text="Save", command=self.save_layout).grid(row=1, column=1, sticky="ew", padx=(6, 0), pady=(6, 0))

        selected = ttk.LabelFrame(panel, text="Selected", padding=8)
        selected.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(selected, textvariable=self.selected_label).grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(selected, text="Type").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Combobox(
            selected,
            textvariable=self.edit_type,
            values=["go", "wall", "no_go", "table_zone", "kitchen_zone", "charging_zone"],
            width=13,
        ).grid(row=1, column=1, columnspan=3, sticky="ew", pady=(6, 0))
        ttk.Label(selected, text="Name").grid(row=2, column=0, sticky="w")
        ttk.Entry(selected, textvariable=self.edit_name, width=15).grid(row=2, column=1, columnspan=3, sticky="ew")
        ttk.Label(selected, text="Min X").grid(row=3, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(selected, textvariable=self.edit_min_x, width=7).grid(row=3, column=1, sticky="ew", pady=(6, 0))
        ttk.Label(selected, text="Max X").grid(row=3, column=2, sticky="w", padx=(6, 0), pady=(6, 0))
        ttk.Entry(selected, textvariable=self.edit_max_x, width=7).grid(row=3, column=3, sticky="ew", pady=(6, 0))
        ttk.Label(selected, text="Min Y").grid(row=4, column=0, sticky="w")
        ttk.Entry(selected, textvariable=self.edit_min_y, width=7).grid(row=4, column=1, sticky="ew")
        ttk.Label(selected, text="Max Y").grid(row=4, column=2, sticky="w", padx=(6, 0))
        ttk.Entry(selected, textvariable=self.edit_max_y, width=7).grid(row=4, column=3, sticky="ew")
        ttk.Label(selected, text="X").grid(row=5, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(selected, textvariable=self.edit_point_x, width=7).grid(row=5, column=1, sticky="ew", pady=(6, 0))
        ttk.Label(selected, text="Y").grid(row=5, column=2, sticky="w", padx=(6, 0), pady=(6, 0))
        ttk.Entry(selected, textvariable=self.edit_point_y, width=7).grid(row=5, column=3, sticky="ew", pady=(6, 0))
        ttk.Label(selected, text="Theta").grid(row=6, column=0, sticky="w")
        ttk.Entry(selected, textvariable=self.edit_point_theta, width=7).grid(row=6, column=1, sticky="ew")
        ttk.Button(selected, text="Apply", command=self.apply_selected_edits).grid(row=7, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Button(selected, text="Delete", command=self.delete_selected).grid(row=7, column=2, columnspan=2, sticky="ew", padx=(6, 0), pady=(8, 0))
        ttk.Button(selected, text="Clear selection", command=self.clear_selection).grid(row=8, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        selected.columnconfigure(1, weight=1)
        selected.columnconfigure(3, weight=1)

        self.summary = tk.Text(panel, width=31, height=18, wrap="word")
        self.summary.grid(row=4, column=0, sticky="nsew", pady=(10, 0))
        panel.rowconfigure(4, weight=1)
        self.summary.configure(state="disabled")

    def _build_canvas(self):
        frame = ttk.Frame(self.main)
        frame.grid(row=0, column=1, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(frame, bg="#f0f2f0", highlightthickness=1, highlightbackground="#808080")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        ttk.Label(frame, textvariable=self.status).grid(row=1, column=0, sticky="ew", pady=(6, 0))
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Motion>", self.on_motion)
        self.canvas.bind("<Configure>", lambda _event: self.redraw())
        self.root.bind("<Delete>", self.on_delete_key)
        self.root.bind("<Escape>", self.on_escape_key)

    def apply_scale(self):
        try:
            if (
                self.width_m.get() <= 0.5
                or self.height_m.get() <= 0.5
                or self.resolution_m.get() <= 0.0
                or self.wall_thickness_m.get() <= 0.0
            ):
                raise ValueError
        except tk.TclError:
            messagebox.showerror("Invalid scale", "Width, height, and resolution must be numeric.")
            return
        except ValueError:
            messagebox.showerror("Invalid scale", "Use positive dimensions and resolution.")
            return
        self.redraw()

    def canvas_bounds(self) -> tuple[float, float, float, float, float]:
        margin = 24.0
        canvas_w = max(self.canvas.winfo_width(), 100)
        canvas_h = max(self.canvas.winfo_height(), 100)
        scale = min((canvas_w - 2 * margin) / self.width_m.get(), (canvas_h - 2 * margin) / self.height_m.get())
        map_w = self.width_m.get() * scale
        map_h = self.height_m.get() * scale
        left = (canvas_w - map_w) / 2.0
        top = (canvas_h - map_h) / 2.0
        return left, top, map_w, map_h, scale

    def canvas_to_world(self, event: tk.Event) -> tuple[float, float]:
        left, top, map_w, map_h, scale = self.canvas_bounds()
        x_px = min(max(event.x, left), left + map_w)
        y_px = min(max(event.y, top), top + map_h)
        x = (x_px - left) / scale
        y = self.height_m.get() - (y_px - top) / scale
        return x, y

    def world_to_canvas(self, x: float, y: float) -> tuple[float, float]:
        left, top, _map_w, _map_h, scale = self.canvas_bounds()
        return left + x * scale, top + (self.height_m.get() - y) * scale

    def display_coord(self, x: float, y: float) -> tuple[float, float]:
        if self.origin_corner.get() == "top-left":
            return x, self.height_m.get() - y
        return x, y

    def wall_thickness(self) -> float:
        try:
            return max(0.03, self.wall_thickness_m.get())
        except tk.TclError:
            return 0.12

    def remember_undo(self):
        self.undo_stack.append((copy.deepcopy(self.zones), copy.deepcopy(self.points)))

    def keyboard_event_in_editor_field(self, event: tk.Event) -> bool:
        widget_class = event.widget.winfo_class()
        return "Entry" in widget_class or "Combobox" in widget_class

    def on_delete_key(self, event: tk.Event):
        if self.keyboard_event_in_editor_field(event):
            return None
        self.delete_selected()
        return "break"

    def on_escape_key(self, event: tk.Event):
        if self.keyboard_event_in_editor_field(event):
            return None
        self.clear_selection()
        return "break"

    def clear_selection(self):
        self.selected = None
        self.populate_selection_fields()
        self.redraw()

    def selected_description(self) -> str:
        if self.selected is None:
            return "None"
        kind, key = self.selected
        if kind == "zone" and isinstance(key, int) and 0 <= key < len(self.zones):
            zone = self.zones[key]
            return f"Zone {key + 1}: {zone.get('name', zone['type'])}"
        if kind == "point" and isinstance(key, str) and key in self.points:
            return f"Point: {key}"
        return "None"

    def populate_selection_fields(self):
        self.selected_label.set(self.selected_description())
        self.edit_type.set("")
        self.edit_name.set("")
        self.edit_min_x.set("")
        self.edit_min_y.set("")
        self.edit_max_x.set("")
        self.edit_max_y.set("")
        self.edit_point_x.set("")
        self.edit_point_y.set("")
        self.edit_point_theta.set("")
        if self.selected is None:
            return
        kind, key = self.selected
        if kind == "zone" and isinstance(key, int) and 0 <= key < len(self.zones):
            zone = self.zones[key]
            self.edit_type.set(str(zone.get("type", "")))
            self.edit_name.set(str(zone.get("name", "")))
            self.edit_min_x.set(f"{float(zone['min_x']):.3f}")
            self.edit_min_y.set(f"{float(zone['min_y']):.3f}")
            self.edit_max_x.set(f"{float(zone['max_x']):.3f}")
            self.edit_max_y.set(f"{float(zone['max_y']):.3f}")
        elif kind == "point" and isinstance(key, str) and key in self.points:
            pose = self.points[key]
            self.edit_name.set(key)
            self.edit_point_x.set(f"{float(pose['x']):.3f}")
            self.edit_point_y.set(f"{float(pose['y']):.3f}")
            self.edit_point_theta.set(f"{float(pose.get('theta', 0.0)):.3f}")

    def find_selection(self, x: float, y: float) -> tuple[str, int | str] | None:
        _left, _top, _map_w, _map_h, scale = self.canvas_bounds()
        hit_radius_m = max(0.12, 10.0 / scale)
        for name, pose in sorted(self.points.items(), reverse=True):
            if math.hypot(float(pose["x"]) - x, float(pose["y"]) - y) <= hit_radius_m:
                return "point", name
        probe = {"x": x, "y": y}
        for index in range(len(self.zones) - 1, -1, -1):
            zone = self.zones[index]
            if self.zone_contains_point(zone, probe) or self.distance_to_zone(zone, probe) <= hit_radius_m:
                return "zone", index
        return None

    def move_selected(self, dx: float, dy: float):
        if self.selected is None:
            return
        width_m = self.width_m.get()
        height_m = self.height_m.get()
        kind, key = self.selected
        if kind == "zone" and isinstance(key, int) and 0 <= key < len(self.zones):
            zone = self.zones[key]
            zone_width = zone["max_x"] - zone["min_x"]
            zone_height = zone["max_y"] - zone["min_y"]
            new_min_x = min(max(zone["min_x"] + dx, 0.0), max(0.0, width_m - zone_width))
            new_min_y = min(max(zone["min_y"] + dy, 0.0), max(0.0, height_m - zone_height))
            zone["min_x"] = round(new_min_x, 3)
            zone["min_y"] = round(new_min_y, 3)
            zone["max_x"] = round(new_min_x + zone_width, 3)
            zone["max_y"] = round(new_min_y + zone_height, 3)
        elif kind == "point" and isinstance(key, str) and key in self.points:
            pose = self.points[key]
            pose["x"] = round(min(max(float(pose["x"]) + dx, 0.0), width_m), 3)
            pose["y"] = round(min(max(float(pose["y"]) + dy, 0.0), height_m), 3)

    def parse_float_field(self, var: tk.StringVar, label: str) -> float | None:
        try:
            return float(var.get())
        except ValueError:
            messagebox.showerror("Invalid edit", f"{label} must be numeric.")
            return None

    def apply_selected_edits(self):
        if self.selected is None:
            self.status.set("Nothing selected.")
            return
        kind, key = self.selected
        if kind == "zone" and isinstance(key, int) and 0 <= key < len(self.zones):
            zone_type = self.edit_type.get().strip()
            if zone_type not in {"go", "wall", "no_go", "table_zone", "kitchen_zone", "charging_zone"}:
                messagebox.showerror("Invalid edit", "Choose a valid zone type.")
                return
            min_x = self.parse_float_field(self.edit_min_x, "Min X")
            min_y = self.parse_float_field(self.edit_min_y, "Min Y")
            max_x = self.parse_float_field(self.edit_max_x, "Max X")
            max_y = self.parse_float_field(self.edit_max_y, "Max Y")
            if None in {min_x, min_y, max_x, max_y}:
                return
            assert min_x is not None and min_y is not None and max_x is not None and max_y is not None
            min_x, max_x = sorted((min_x, max_x))
            min_y, max_y = sorted((min_y, max_y))
            min_x = min(max(min_x, 0.0), self.width_m.get())
            max_x = min(max(max_x, 0.0), self.width_m.get())
            min_y = min(max(min_y, 0.0), self.height_m.get())
            max_y = min(max(max_y, 0.0), self.height_m.get())
            if max_x - min_x < 0.01 or max_y - min_y < 0.01:
                messagebox.showerror("Invalid edit", "Zone width and height must be at least 0.01 m.")
                return
            name = self.edit_name.get().strip()
            if zone_type == "table_zone" and not name:
                name = f"TABLE_{self.next_table_zone_number()}"
            self.remember_undo()
            zone = self.zones[key]
            zone["type"] = zone_type
            zone["min_x"] = round(min_x, 3)
            zone["min_y"] = round(min_y, 3)
            zone["max_x"] = round(max_x, 3)
            zone["max_y"] = round(max_y, 3)
            if name:
                zone["name"] = name
            else:
                zone.pop("name", None)
            if zone_type == "wall":
                zone["thickness"] = round(self.wall_thickness(), 3)
            else:
                zone.pop("thickness", None)
            self.status.set(f"Updated {self.selected_description()}.")
        elif kind == "point" and isinstance(key, str) and key in self.points:
            name = self.edit_name.get().strip()
            if not name:
                messagebox.showerror("Invalid edit", "Point name is required.")
                return
            if name != key and name in self.points:
                messagebox.showerror("Invalid edit", f"{name} already exists.")
                return
            x = self.parse_float_field(self.edit_point_x, "X")
            y = self.parse_float_field(self.edit_point_y, "Y")
            theta = self.parse_float_field(self.edit_point_theta, "Theta")
            if None in {x, y, theta}:
                return
            assert x is not None and y is not None and theta is not None
            self.remember_undo()
            pose = self.points.pop(key)
            pose["x"] = round(min(max(x, 0.0), self.width_m.get()), 3)
            pose["y"] = round(min(max(y, 0.0), self.height_m.get()), 3)
            pose["theta"] = round(theta, 3)
            self.points[name] = pose
            self.selected = ("point", name)
            self.status.set(f"Updated Point: {name}.")
        else:
            self.selected = None
            self.status.set("Selection no longer exists.")
        self.populate_selection_fields()
        self.redraw()

    def delete_selected(self):
        if self.selected is None:
            self.status.set("Nothing selected.")
            return
        kind, key = self.selected
        self.remember_undo()
        if kind == "zone" and isinstance(key, int) and 0 <= key < len(self.zones):
            removed = self.zones.pop(key)
            self.status.set(f"Deleted {removed.get('name', removed['type'])}.")
        elif kind == "point" and isinstance(key, str) and key in self.points:
            self.points.pop(key)
            self.status.set(f"Deleted {key}.")
        self.selected = None
        self.populate_selection_fields()
        self.redraw()

    def table_number(self, name: str) -> int | None:
        if not name.startswith("TABLE_"):
            return None
        suffix = name.split("_", 1)[1]
        return int(suffix) if suffix.isdigit() else None

    def next_table_point_number(self) -> int:
        used = {number for name in self.points for number in [self.table_number(name)] if number is not None}
        number = 1
        while number in used:
            number += 1
        return number

    def next_table_zone_number(self) -> int:
        used = {
            number
            for zone in self.zones
            for number in [self.table_number(str(zone.get("name") or ""))]
            if zone.get("type") == "table_zone" and number is not None
        }
        number = 1
        while number in used:
            number += 1
        return number

    def zone_center(self, zone: dict) -> tuple[float, float]:
        return (zone["min_x"] + zone["max_x"]) / 2.0, (zone["min_y"] + zone["max_y"]) / 2.0

    def zone_contains_point(self, zone: dict, pose: dict) -> bool:
        return zone["min_x"] <= pose["x"] <= zone["max_x"] and zone["min_y"] <= pose["y"] <= zone["max_y"]

    def distance_to_zone(self, zone: dict, pose: dict) -> float:
        dx = max(zone["min_x"] - pose["x"], 0.0, pose["x"] - zone["max_x"])
        dy = max(zone["min_y"] - pose["y"], 0.0, pose["y"] - zone["max_y"])
        return math.hypot(dx, dy)

    def is_blocked_point(self, pose: dict, ignored_zone: dict | None = None, clearance_m: float = 0.0) -> bool:
        for zone in self.zones:
            if zone is ignored_zone or zone["type"] not in {"wall", "no_go", "table_zone"}:
                continue
            if self.distance_to_zone(zone, pose) <= clearance_m:
                return True
        return False

    def delivery_point_for_table_zone(self, zone: dict) -> dict:
        return self.service_point_near_zone(zone, ignored_zone=zone)

    def service_point_near_zone(self, zone: dict, ignored_zone: dict | None = None) -> dict:
        cx, cy = self.zone_center(zone)
        offset = max(self.resolution_m.get(), 0.05)
        margin = offset
        candidates = [
            (cx, zone["min_y"] - offset),
            (zone["min_x"] - offset, cy),
            (zone["max_x"] + offset, cy),
            (cx, zone["max_y"] + offset),
        ]
        for x, y in candidates:
            pose = {
                "x": round(min(max(x, margin), self.width_m.get() - margin), 3),
                "y": round(min(max(y, margin), self.height_m.get() - margin), 3),
                "theta": 0.0,
            }
            if not self.zone_contains_point(zone, pose) and not self.is_blocked_point(pose, ignored_zone=ignored_zone):
                return pose
        return {"x": round(cx, 3), "y": round(cy, 3), "theta": 0.0}

    def effective_points(self) -> dict[str, dict]:
        points = {name: dict(pose) for name, pose in self.points.items()}

        if "HOME" not in points and "CHARGING" in points:
            points["HOME"] = dict(points["CHARGING"])
        if "CHARGING" not in points and "HOME" in points:
            points["CHARGING"] = dict(points["HOME"])

        for zone in self.zones:
            if zone["type"] == "kitchen_zone" and "KITCHEN" not in points:
                points["KITCHEN"] = self.service_point_near_zone(zone)
            elif zone["type"] == "charging_zone" and "CHARGING" not in points:
                x, y = self.zone_center(zone)
                points["CHARGING"] = {"x": round(x, 3), "y": round(y, 3), "theta": 0.0}
            elif zone["type"] == "table_zone":
                name = str(zone.get("name") or "")
                if name.startswith("TABLE_") and name not in points:
                    points[name] = self.delivery_point_for_table_zone(zone)

        return points

    def on_motion(self, event: tk.Event):
        x, y = self.canvas_to_world(event)
        dx, dy = self.display_coord(x, y)
        self.status.set(f"{self.origin_corner.get()} x={dx:.2f} m y={dy:.2f} m")

    def on_press(self, event: tk.Event):
        x, y = self.canvas_to_world(event)
        if self.tool.get() == "select":
            self.selected = self.find_selection(x, y)
            self.populate_selection_fields()
            self.drag_start = (x, y)
            self.drag_last = (x, y)
            self.drag_mode = "move" if self.selected is not None else None
            self.move_undo_saved = False
            self.redraw()
            return
        if self.tool.get() in {"table", "kitchen", "home", "charging"}:
            self.add_point(self.tool.get(), x, y)
            return
        self.drag_start = (x, y)
        self.drag_last = None
        self.drag_mode = "draw"

    def on_drag(self, event: tk.Event):
        if not self.drag_start:
            return
        if self.drag_mode == "move" and self.drag_last is not None and self.selected is not None:
            x, y = self.canvas_to_world(event)
            dx = x - self.drag_last[0]
            dy = y - self.drag_last[1]
            if not self.move_undo_saved and math.hypot(x - self.drag_start[0], y - self.drag_start[1]) >= 0.01:
                self.remember_undo()
                self.move_undo_saved = True
            self.move_selected(dx, dy)
            self.drag_last = (x, y)
            self.populate_selection_fields()
            self.redraw()
            return
        if self.drag_mode != "draw":
            return
        x0, y0 = self.drag_start
        x1, y1 = self.canvas_to_world(event)
        cx0, cy0 = self.world_to_canvas(x0, y0)
        cx1, cy1 = self.world_to_canvas(x1, y1)
        if self.preview_rect is not None:
            self.canvas.delete(self.preview_rect)
        self.preview_rect = self.canvas.create_rectangle(cx0, cy0, cx1, cy1, outline="#222222", dash=(4, 3), width=2)

    def on_release(self, event: tk.Event):
        if not self.drag_start:
            return
        if self.drag_mode == "move":
            self.drag_start = None
            self.drag_last = None
            self.drag_mode = None
            self.move_undo_saved = False
            return
        if self.drag_mode != "draw":
            self.drag_start = None
            self.drag_last = None
            return
        x0, y0 = self.drag_start
        x1, y1 = self.canvas_to_world(event)
        self.drag_start = None
        self.drag_last = None
        self.drag_mode = None
        if self.preview_rect is not None:
            self.canvas.delete(self.preview_rect)
            self.preview_rect = None
        if self.tool.get() == "wall":
            zone = self.wall_zone_from_drag(x0, y0, x1, y1)
            if zone is None:
                return
        elif abs(x1 - x0) < 0.05 or abs(y1 - y0) < 0.05:
            return
        else:
            zone_type = self.tool.get()
            name = None
            if zone_type == "table_zone":
                number = simpledialog.askinteger("Table zone", "Table number", initialvalue=self.next_table_zone_number(), minvalue=1)
                if number is None:
                    return
                name = f"TABLE_{number}"
            zone = {
                "type": zone_type,
                "min_x": round(min(x0, x1), 3),
                "min_y": round(min(y0, y1), 3),
                "max_x": round(max(x0, x1), 3),
                "max_y": round(max(y0, y1), 3),
            }
            if name:
                zone["name"] = name
        self.remember_undo()
        self.zones.append(zone)
        self.selected = ("zone", len(self.zones) - 1)
        self.populate_selection_fields()
        self.redraw()

    def wall_zone_from_drag(self, x0: float, y0: float, x1: float, y1: float) -> dict | None:
        if math.hypot(x1 - x0, y1 - y0) < 0.08:
            return None
        thickness = self.wall_thickness()
        half = thickness / 2.0
        if abs(x1 - x0) >= abs(y1 - y0):
            y_mid = (y0 + y1) / 2.0
            min_x, max_x = min(x0, x1), max(x0, x1)
            min_y, max_y = y_mid - half, y_mid + half
        else:
            x_mid = (x0 + x1) / 2.0
            min_x, max_x = x_mid - half, x_mid + half
            min_y, max_y = min(y0, y1), max(y0, y1)
        return {
            "type": "wall",
            "min_x": round(max(0.0, min_x), 3),
            "min_y": round(max(0.0, min_y), 3),
            "max_x": round(min(self.width_m.get(), max_x), 3),
            "max_y": round(min(self.height_m.get(), max_y), 3),
            "thickness": round(thickness, 3),
        }

    def add_point(self, tool: str, x: float, y: float):
        if tool == "table":
            number = simpledialog.askinteger("Table", "Table number", initialvalue=self.next_table_point_number(), minvalue=1)
            if number is None:
                return
            name = f"TABLE_{number}"
        elif tool == "kitchen":
            name = "KITCHEN"
        elif tool == "charging":
            name = "CHARGING"
        else:
            name = "HOME"
        self.remember_undo()
        self.points[name] = {"x": round(x, 3), "y": round(y, 3), "theta": 0.0}
        if name == "HOME" and "CHARGING" not in self.points:
            self.points["CHARGING"] = dict(self.points[name])
        self.selected = ("point", name)
        self.populate_selection_fields()
        self.redraw()

    def undo(self):
        if not self.undo_stack:
            self.status.set("Nothing to undo.")
            return
        self.zones, self.points = self.undo_stack.pop()
        self.selected = None
        self.populate_selection_fields()
        self.redraw()

    def clear(self):
        if messagebox.askyesno("Clear layout", "Remove all zones and points?"):
            self.remember_undo()
            self.zones.clear()
            self.points.clear()
            self.selected = None
            self.populate_selection_fields()
            self.redraw()

    def redraw(self):
        self.canvas.delete("all")
        left, top, map_w, map_h, scale = self.canvas_bounds()
        self.canvas.create_rectangle(left, top, left + map_w, top + map_h, fill="#d5d8d0", outline="#202020", width=2)

        for meter in range(math.floor(self.width_m.get()) + 1):
            x, _ = self.world_to_canvas(float(meter), 0)
            self.canvas.create_line(x, top, x, top + map_h, fill="#b7bcb2")
            self.canvas.create_text(x + 3, top + map_h - 12, text=str(meter), anchor="w", fill="#555555")
        for meter in range(math.floor(self.height_m.get()) + 1):
            _, y = self.world_to_canvas(0, float(meter))
            self.canvas.create_line(left, y, left + map_w, y, fill="#b7bcb2")
            self.canvas.create_text(left + 4, y - 4, text=str(meter), anchor="w", fill="#555555")

        colors = {
            "go": ("#c7e6be", "#3b7d37"),
            "wall": ("#4f5458", "#202020"),
            "no_go": ("#d9a39a", "#8f2b1f"),
            "table_zone": ("#b99772", "#67452b"),
            "kitchen_zone": ("#f1c178", "#a56500"),
            "charging_zone": ("#a8dce5", "#1a6c7b"),
        }
        labels = {"go": "GO", "wall": "WALL", "no_go": "NO-GO", "table_zone": "TABLE", "kitchen_zone": "KITCHEN", "charging_zone": "CHARGE"}
        for index, zone in enumerate(self.zones):
            fill, outline = colors.get(zone["type"], ("#dddddd", "#555555"))
            x0, y0 = self.world_to_canvas(zone["min_x"], zone["max_y"])
            x1, y1 = self.world_to_canvas(zone["max_x"], zone["min_y"])
            self.canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline=outline, width=2)
            label_color = "#ffffff" if zone["type"] == "wall" else "#202020"
            label = zone.get("name", labels.get(zone["type"], zone["type"]))
            self.canvas.create_text((x0 + x1) / 2, (y0 + y1) / 2, text=label, fill=label_color)
            if self.selected == ("zone", index):
                self.canvas.create_rectangle(x0, y0, x1, y1, outline="#0d47a1", width=3, dash=(6, 3))
                for hx, hy in [(x0, y0), (x0, y1), (x1, y0), (x1, y1)]:
                    self.canvas.create_rectangle(hx - 4, hy - 4, hx + 4, hy + 4, fill="#0d47a1", outline="#ffffff")

        for name, pose in sorted(self.points.items()):
            x, y = self.world_to_canvas(pose["x"], pose["y"])
            color = "#1e5aa8"
            if name == "KITCHEN":
                color = "#b86700"
            elif name == "HOME":
                color = "#2b7a39"
            elif name == "CHARGING":
                color = "#0c7582"
            self.canvas.create_oval(x - 7, y - 7, x + 7, y + 7, fill=color, outline="#111111")
            if self.selected == ("point", name):
                self.canvas.create_oval(x - 12, y - 12, x + 12, y + 12, outline="#0d47a1", width=3)
            self.canvas.create_text(x + 10, y - 10, text=name, anchor="w", fill="#111111", font=("TkDefaultFont", 9, "bold"))

        self.update_summary()

    def update_summary(self):
        effective_points = self.effective_points()
        tables = sorted(name for name in effective_points if name.startswith("TABLE_"))
        wall_count = sum(1 for zone in self.zones if zone["type"] == "wall")
        table_zone_count = sum(1 for zone in self.zones if zone["type"] == "table_zone")
        kitchen_state = "yes" if "KITCHEN" in self.points else "auto from zone" if "KITCHEN" in effective_points else "missing"
        home_state = "yes" if "HOME" in self.points else "auto from charging" if "HOME" in effective_points else "missing"
        charging_state = "yes" if "CHARGING" in self.points else "auto from home/zone" if "CHARGING" in effective_points else "missing"
        lines = [
            f"Size: {self.width_m.get():.2f} x {self.height_m.get():.2f} m",
            f"Resolution: {self.resolution_m.get():.3f} m/cell",
            f"Wall thickness: {self.wall_thickness():.2f} m",
            f"Zones: {len(self.zones)}",
            f"Walls: {wall_count}",
            f"Table zones: {table_zone_count}",
            f"Tables: {', '.join(tables) if tables else 'none'}",
            f"Kitchen: {kitchen_state}",
            f"Home: {home_state}",
            f"Charging: {charging_state}",
            "",
            f"Output: {self.output_path}",
        ]
        self.summary.configure(state="normal")
        self.summary.delete("1.0", tk.END)
        self.summary.insert("1.0", "\n".join(lines))
        self.summary.configure(state="disabled")

    def validate_before_save(self) -> bool:
        points = self.effective_points()
        tables = [name for name in points if name.startswith("TABLE_")]
        missing = [name for name in ["HOME", "KITCHEN", "CHARGING"] if name not in points]
        if missing or not tables:
            missing_text = ", ".join(missing + ([] if tables else ["TABLE_N"]))
            messagebox.showerror("Missing delivery labels", f"Add these before saving: {missing_text}")
            return False
        try:
            width_cells = round(self.width_m.get() / self.resolution_m.get())
            height_cells = round(self.height_m.get() / self.resolution_m.get())
        except tk.TclError:
            messagebox.showerror("Invalid scale", "Width, height, and resolution must be numeric.")
            return False
        if width_cells <= 0 or height_cells <= 0:
            messagebox.showerror("Invalid scale", "Map cell dimensions must be positive.")
            return False
        if width_cells * height_cells > 1_200_000:
            messagebox.showerror("Map too large", "Use a larger resolution or smaller floor area.")
            return False
        for name, pose in points.items():
            for zone in self.zones:
                if zone["type"] not in {"wall", "no_go", "table_zone"}:
                    continue
                inside_x = zone["min_x"] <= pose["x"] <= zone["max_x"]
                inside_y = zone["min_y"] <= pose["y"] <= zone["max_y"]
                if inside_x and inside_y:
                    messagebox.showerror("Blocked point", f"{name} is inside a {zone['type']} area.")
                    return False
        return True

    def save_layout(self):
        if not self.validate_before_save():
            return
        chosen = filedialog.asksaveasfilename(
            title="Save facility map",
            initialfile=self.output_path.name,
            initialdir=str(self.output_path.parent),
            defaultextension=".json",
            filetypes=[("Map JSON", "*.json"), ("All files", "*.*")],
        )
        if not chosen:
            return
        self.output_path = pathlib.Path(chosen)
        effective = self.effective_points()
        if effective != self.points:
            self.remember_undo()
        self.points = effective
        data = self.build_map_json()
        world_path = default_world_path()
        data["layout"]["map_json"] = str(self.output_path)
        data["layout"]["webots_world"] = str(world_path)
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.output_path.with_suffix(self.output_path.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
        os.replace(tmp_path, self.output_path)
        try:
            generated_world = generate_world_file(data, world_path)
        except OSError as exc:
            messagebox.showwarning("World generation failed", str(exc))
            self.status.set(f"Saved map only: {self.output_path}")
        else:
            self.status.set(f"Saved map and world: {generated_world}")
        self.redraw()
        self.update_summary()

    def open_layout(self):
        chosen = filedialog.askopenfilename(
            title="Open facility map",
            initialdir=str(self.output_path.parent),
            filetypes=[("Map JSON", "*.json"), ("All files", "*.*")],
        )
        if not chosen:
            return
        self.load_layout_path(pathlib.Path(chosen), show_error=True)

    def load_layout_path(self, path: pathlib.Path, show_error: bool = True):
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            if show_error:
                messagebox.showerror("Open failed", str(exc))
            else:
                self.redraw()
            return
        layout = data.get("layout", {})
        self.width_m.set(float(layout.get("width_m", data.get("width", 180) * data.get("resolution", 0.05))))
        self.height_m.set(float(layout.get("height_m", data.get("height", 180) * data.get("resolution", 0.05))))
        self.resolution_m.set(float(data.get("resolution", layout.get("resolution_m", 0.05))))
        self.wall_thickness_m.set(float(layout.get("wall_thickness_m", 0.12)))
        self.origin_corner.set(layout.get("origin_corner", "bottom-left"))
        self.zones = list(layout.get("zones", []))
        self.points = {
            name: {"x": float(pose["x"]), "y": float(pose["y"]), "theta": float(pose.get("theta", 0.0))}
            for name, pose in data.get("destinations", {}).items()
        }
        self.undo_stack.clear()
        self.selected = None
        self.populate_selection_fields()
        self.output_path = path
        self.status.set(f"Loaded layout: {self.output_path}")
        self.redraw()

    def build_map_json(self) -> dict:
        width_cells = int(round(self.width_m.get() / self.resolution_m.get()))
        height_cells = int(round(self.height_m.get() / self.resolution_m.get()))
        cells = [UNKNOWN] * (width_cells * height_cells)

        def set_cell(x_idx: int, y_idx: int, value: int):
            if 0 <= x_idx < width_cells and 0 <= y_idx < height_cells:
                cells[y_idx * width_cells + x_idx] = value

        def fill_rect(zone: dict, value: int):
            min_x = max(0, int(math.floor(zone["min_x"] / self.resolution_m.get())))
            max_x = min(width_cells - 1, int(math.ceil(zone["max_x"] / self.resolution_m.get())))
            min_y = max(0, int(math.floor(zone["min_y"] / self.resolution_m.get())))
            max_y = min(height_cells - 1, int(math.ceil(zone["max_y"] / self.resolution_m.get())))
            for y_idx in range(min_y, max_y + 1):
                for x_idx in range(min_x, max_x + 1):
                    set_cell(x_idx, y_idx, value)

        go_zones = [zone for zone in self.zones if zone["type"] == "go"]
        if go_zones:
            for zone in go_zones:
                fill_rect(zone, FREE)
        else:
            for y_idx in range(height_cells):
                for x_idx in range(width_cells):
                    set_cell(x_idx, y_idx, FREE)

        for zone in self.zones:
            if zone["type"] in {"kitchen_zone", "charging_zone"}:
                fill_rect(zone, FREE)
        point_radius_cells = max(1, int(round(0.20 / self.resolution_m.get())))
        points = self.effective_points()
        for pose in points.values():
            center_x = int(round(pose["x"] / self.resolution_m.get()))
            center_y = int(round(pose["y"] / self.resolution_m.get()))
            for dy in range(-point_radius_cells, point_radius_cells + 1):
                for dx in range(-point_radius_cells, point_radius_cells + 1):
                    if dx * dx + dy * dy <= point_radius_cells * point_radius_cells:
                        set_cell(center_x + dx, center_y + dy, FREE)

        for zone in self.zones:
            if zone["type"] in {"wall", "no_go", "table_zone"}:
                fill_rect(zone, OCCUPIED)

        for x_idx in range(width_cells):
            set_cell(x_idx, 0, OCCUPIED)
            set_cell(x_idx, height_cells - 1, OCCUPIED)
        for y_idx in range(height_cells):
            set_cell(0, y_idx, OCCUPIED)
            set_cell(width_cells - 1, y_idx, OCCUPIED)

        return {
            "width": width_cells,
            "height": height_cells,
            "resolution": self.resolution_m.get(),
            "origin_x": 0.0,
            "origin_y": 0.0,
            "cells": cells,
            "destinations": {name: points[name] for name in sorted(points)},
            "layout": {
                "width_m": self.width_m.get(),
                "height_m": self.height_m.get(),
                "wall_thickness_m": self.wall_thickness_m.get(),
                "origin_corner": self.origin_corner.get(),
                "zones": self.zones,
            },
        }


def default_output_path() -> pathlib.Path:
    root = pathlib.Path(__file__).resolve().parents[2]
    return root / "build" / "restaurant_robot" / "facility_layout_map.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=default_output_path())
    args = parser.parse_args()

    root = tk.Tk()
    FacilityLayoutEditor(root, args.output.resolve())
    root.mainloop()


if __name__ == "__main__":
    main()
