#!/usr/bin/env python3
import argparse
import json
import os
import pathlib
import tkinter as tk
from tkinter import ttk


TUNING_GROUPS = {
    "Planner": [
        ("tune_planner_clearance_radius_m", "No-go distance m", 0.25, 0.70, 0.01, 0.40),
        ("tune_path_obstacle_radius_m", "Dynamic path radius m", 0.15, 0.80, 0.01, 0.35),
        ("tune_persistent_blockage_timeout_s", "Blocked replan s", 0.3, 8.0, 0.1, 0.8),
        ("tune_stuck_timeout_s", "Stuck replan s", 0.5, 8.0, 0.1, 3.0),
        ("tune_stuck_motion_threshold_m", "Stuck movement m", 0.01, 0.20, 0.01, 0.05),
    ],
    "Tracking": [
        ("tune_lookahead_distance_m", "Lookahead m", 0.10, 0.80, 0.01, 0.22),
        ("tune_final_lookahead_distance_m", "Final lookahead m", 0.05, 0.40, 0.01, 0.12),
        ("tune_final_approach_distance_m", "Final approach m", 0.20, 1.50, 0.01, 0.55),
        ("tune_max_linear_velocity_mps", "Max linear m/s", 0.05, 0.60, 0.01, 0.28),
        ("tune_max_angular_velocity_rps", "Max angular rad/s", 0.20, 1.80, 0.01, 0.70),
        ("tune_angular_gain", "Angular gain", 0.50, 4.00, 0.05, 1.80),
        ("tune_rotate_in_place_heading_error_rad", "Turn-in-place rad", 0.10, 1.20, 0.01, 0.45),
        ("tune_heading_slowdown_error_rad", "Heading slowdown rad", 0.05, 0.90, 0.01, 0.20),
        ("tune_goal_slowdown_distance_m", "Goal slowdown m", 0.20, 2.00, 0.01, 0.75),
        ("tune_goal_tolerance_m", "Goal tolerance m", 0.05, 0.50, 0.01, 0.18),
    ],
    "Safety": [
        ("tune_front_caution_distance_m", "Front caution m", 0.30, 2.50, 0.01, 1.00),
        ("tune_front_stop_distance_m", "Front stop m", 0.10, 0.80, 0.01, 0.32),
        ("tune_rear_caution_distance_m", "Rear caution m", 0.20, 1.50, 0.01, 0.50),
        ("tune_rear_stop_distance_m", "Rear stop m", 0.08, 0.70, 0.01, 0.20),
        ("tune_caution_max_velocity_mps", "Caution speed m/s", 0.05, 0.40, 0.01, 0.22),
        ("tune_front_angle_limit_rad", "Front angle rad", 0.50, 3.14, 0.01, 1.57),
        ("tune_front_stop_angle_limit_rad", "Stop angle rad", 0.30, 2.20, 0.01, 1.05),
    ],
}


class RestaurantControlGui:
    def __init__(self, root: tk.Tk, control_file: pathlib.Path, destination_values: list[str]):
        self.root = root
        self.control_file = control_file
        self.seq = 0
        self.mode = tk.StringVar(value="auto")
        self.destination_values = destination_values
        self.goal = tk.StringVar(value="TABLE_3" if "TABLE_3" in destination_values else destination_values[0])
        self.linear = 0.0
        self.angular = 0.0
        self.tuning_vars: dict[str, tk.DoubleVar] = {}
        self.tuning_labels: dict[str, tk.StringVar] = {}

        root.title("Restaurant Robot Control")
        root.resizable(True, True)

        frame = ttk.Frame(root, padding=12)
        frame.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frame, text="Mode").grid(row=0, column=0, sticky="w")
        mode_frame = ttk.Frame(frame)
        mode_frame.grid(row=0, column=1, columnspan=3, sticky="ew", pady=3)
        ttk.Radiobutton(mode_frame, text="Auto", value="auto", variable=self.mode, command=self.send_mode).grid(row=0, column=0, padx=2)
        ttk.Radiobutton(mode_frame, text="Manual", value="manual", variable=self.mode, command=self.send_mode).grid(row=0, column=1, padx=2)

        ttk.Label(frame, text="Destination").grid(row=1, column=0, sticky="w")
        destination_menu = ttk.Combobox(frame, textvariable=self.goal, values=self.destination_values, width=12, state="readonly")
        destination_menu.grid(row=1, column=1, sticky="w", pady=3)
        ttk.Button(frame, text="Go", command=self.send_goal).grid(row=1, column=2, padx=3)

        drive = ttk.LabelFrame(frame, text="Manual Drive", padding=8)
        drive.grid(row=2, column=0, columnspan=4, pady=8)
        ttk.Button(drive, text="Forward", command=lambda: self.send_drive(0.18, 0.0)).grid(row=0, column=1, padx=3, pady=3)
        ttk.Button(drive, text="Left", command=lambda: self.send_drive(0.0, 0.9)).grid(row=1, column=0, padx=3, pady=3)
        ttk.Button(drive, text="Stop", command=lambda: self.send_drive(0.0, 0.0)).grid(row=1, column=1, padx=3, pady=3)
        ttk.Button(drive, text="Right", command=lambda: self.send_drive(0.0, -0.9)).grid(row=1, column=2, padx=3, pady=3)
        ttk.Button(drive, text="Reverse", command=lambda: self.send_drive(-0.10, 0.0)).grid(row=2, column=1, padx=3, pady=3)

        actions = ttk.Frame(frame)
        actions.grid(row=3, column=0, columnspan=4, sticky="ew")
        ttk.Button(actions, text="Save Map", command=self.save_map).grid(row=0, column=0, padx=3, pady=3)
        ttk.Button(actions, text="E-Stop", command=self.estop).grid(row=0, column=1, padx=3, pady=3)
        ttk.Button(actions, text="Release E-Stop", command=self.release_estop).grid(row=0, column=2, padx=3, pady=3)
        ttk.Button(actions, text="Quit Robot", command=self.quit_robot).grid(row=0, column=3, padx=3, pady=3)

        tuning = ttk.LabelFrame(frame, text="Tuning", padding=8)
        tuning.grid(row=4, column=0, columnspan=4, sticky="ew", pady=8)
        notebook = ttk.Notebook(tuning)
        notebook.grid(row=0, column=0, columnspan=3, sticky="ew")
        for tab_name, params in TUNING_GROUPS.items():
            tab = ttk.Frame(notebook, padding=6)
            notebook.add(tab, text=tab_name)
            for row, (key, label, start, end, step, default) in enumerate(params):
                var = tk.DoubleVar(value=default)
                value_text = tk.StringVar(value=f"{default:.2f}")
                self.tuning_vars[key] = var
                self.tuning_labels[key] = value_text
                ttk.Label(tab, text=label, width=22).grid(row=row, column=0, sticky="w", padx=3, pady=2)
                scale = ttk.Scale(
                    tab,
                    from_=start,
                    to=end,
                    variable=var,
                    command=lambda _value, name=key: self.update_tuning_label(name),
                )
                scale.grid(row=row, column=1, sticky="ew", padx=3, pady=2)
                ttk.Label(tab, textvariable=value_text, width=6).grid(row=row, column=2, sticky="e", padx=3, pady=2)
                tab.columnconfigure(1, weight=1)
        ttk.Button(tuning, text="Apply Tuning", command=self.apply_tuning).grid(row=1, column=0, padx=3, pady=(8, 0), sticky="w")
        ttk.Button(tuning, text="Reset Tuning", command=self.reset_tuning).grid(row=1, column=1, padx=3, pady=(8, 0), sticky="w")

        self.status = tk.StringVar(value=f"Control file: {self.control_file}")
        ttk.Label(frame, textvariable=self.status, width=80).grid(row=5, column=0, columnspan=4, sticky="w", pady=(8, 0))

        self.write_command()

    def write_command(self, include_tuning: bool = False, **updates):
        self.seq += 1
        data = {
            "seq": self.seq,
            "mode": self.mode.get(),
            "goal": self.goal.get(),
            "linear": self.linear,
            "angular": self.angular,
            "save_map": 0,
            "quit": 0,
            "estop": 0,
            "clear_estop": 0,
            "tune_only": 0,
        }
        if include_tuning:
            data.update({key: round(var.get(), 4) for key, var in self.tuning_vars.items()})
        data.update(updates)
        self.control_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.control_file.with_suffix(self.control_file.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            for key, value in data.items():
                handle.write(f"{key}={value}\n")
        os.replace(tmp_path, self.control_file)
        self.status.set(f"Sent seq {self.seq}: mode={data['mode']} goal={data['goal']} linear={data['linear']} angular={data['angular']}")

    def update_tuning_label(self, key: str):
        self.tuning_labels[key].set(f"{self.tuning_vars[key].get():.2f}")

    def apply_tuning(self):
        self.write_command(include_tuning=True, tune_only=1, goal="", linear=0.0, angular=0.0)

    def reset_tuning(self):
        for params in TUNING_GROUPS.values():
            for key, _label, _start, _end, _step, default in params:
                self.tuning_vars[key].set(default)
                self.update_tuning_label(key)
        self.apply_tuning()

    def send_mode(self):
        self.write_command()

    def send_goal(self):
        self.mode.set("auto")
        self.linear = 0.0
        self.angular = 0.0
        self.write_command()

    def send_drive(self, linear: float, angular: float):
        self.mode.set("manual")
        self.linear = linear
        self.angular = angular
        self.write_command()

    def save_map(self):
        self.write_command(save_map=1, mode="", goal="", linear=0.0, angular=0.0)

    def estop(self):
        self.write_command(estop=1, linear=0.0, angular=0.0)

    def release_estop(self):
        self.write_command(clear_estop=1)

    def quit_robot(self):
        self.write_command(quit=1, linear=0.0, angular=0.0)


def default_control_file() -> pathlib.Path:
    root = pathlib.Path(__file__).resolve().parents[2]
    return root / "build" / "restaurant_robot" / "control_command.txt"


def load_destination_values(map_input_json: pathlib.Path | None) -> list[str]:
    def table_sort_key(value: str) -> tuple[int, int | str]:
        suffix = value.split("_", 1)[1]
        return (0, int(suffix)) if suffix.isdigit() else (1, suffix)

    destinations = ["HOME", "KITCHEN", "CHARGING"]
    if map_input_json and map_input_json.exists():
        try:
            with map_input_json.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            names = list(data.get("destinations", {}).keys())
            tables = sorted([name for name in names if name.startswith("TABLE_")], key=table_sort_key)
            fixed = [name for name in destinations if name in names]
            if tables or fixed:
                return tables + fixed
        except (OSError, json.JSONDecodeError, ValueError):
            pass
    return [f"TABLE_{i}" for i in range(1, 6)] + destinations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-file", type=pathlib.Path, default=default_control_file())
    parser.add_argument("--map-input-json", type=pathlib.Path, default=os.environ.get("MAP_INPUT_JSON") or None)
    args = parser.parse_args()

    root = tk.Tk()
    RestaurantControlGui(root, args.control_file.resolve(), load_destination_values(args.map_input_json))
    root.mainloop()


if __name__ == "__main__":
    main()
