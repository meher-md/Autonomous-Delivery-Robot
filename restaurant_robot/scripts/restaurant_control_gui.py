#!/usr/bin/env python3
import argparse
import json
import os
import pathlib
import tkinter as tk
from tkinter import ttk


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

        root.title("Restaurant Robot Control")
        root.resizable(False, False)

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
        ttk.Button(actions, text="Clear", command=self.clear_estop).grid(row=0, column=2, padx=3, pady=3)
        ttk.Button(actions, text="Quit Robot", command=self.quit_robot).grid(row=0, column=3, padx=3, pady=3)

        self.status = tk.StringVar(value=f"Control file: {self.control_file}")
        ttk.Label(frame, textvariable=self.status, width=62).grid(row=4, column=0, columnspan=4, sticky="w", pady=(8, 0))

        self.write_command()

    def write_command(self, **updates):
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
        }
        data.update(updates)
        self.control_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self.control_file.with_suffix(self.control_file.suffix + ".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            for key, value in data.items():
                handle.write(f"{key}={value}\n")
        os.replace(tmp_path, self.control_file)
        self.status.set(f"Sent seq {self.seq}: mode={data['mode']} linear={data['linear']} angular={data['angular']}")

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
        self.write_command(save_map=1)

    def estop(self):
        self.write_command(estop=1, linear=0.0, angular=0.0)

    def clear_estop(self):
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
