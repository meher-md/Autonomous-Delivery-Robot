# How To Run Webots GUI Simulations

Run all commands from the repository root. First clone or pull the repo, then enter your local checkout:

```bash
cd Autonomous-Delivery-Robot
```

Only keep one Webots world open at a time. The launcher scripts stop if another `.wbt` is already running.

## Build Once

```bash
cmake -S . -B build
cmake --build build --target restaurant_delivery_controller restaurant_scenario_supervisor
```

The run scripts also build automatically, so this step is optional.

## Facility Layout World With Control GUI

This is the main restaurant simulation from the facility layout editor. It uses:

- `restaurant_robot/config/facility_layout_map.json`
- `restaurant_robot/simulator/worlds/facility_layout_generated.wbt`
- Tkinter robot control GUI

```bash
bash restaurant_robot/scripts/run_generated_facility_world.sh
```

Use this for normal testing: select destination, press `Go`, tune planner parameters, save map, use E-stop, and drive manually.

## Facility Layout World Without Regenerating

Use this when the tracked generated world already exists and you do not want the script to rewrite it before launch.

```bash
MAP_INPUT_JSON=restaurant_robot/config/facility_layout_map.json \
WEBOTS_WORLD=restaurant_robot/simulator/worlds/facility_layout_generated.wbt \
bash restaurant_robot/scripts/run_webots_gui_control.sh
```

## Default Prototype World With Control GUI

This opens the older default Webots restaurant world.

```bash
bash restaurant_robot/scripts/run_webots_gui_control.sh
```

## Manual Mapping GUI

This opens Webots in manual mapping mode. Drive with keyboard and press `M` in the Webots window to save a map checkpoint.

```bash
bash restaurant_robot/scripts/run_webots_manual_mapping.sh
```

Controls:

```text
W/A/S/D or arrow keys: drive
Space: stop
M: save map
Q: quit controller
```

Default saved map:

```text
build/restaurant_robot/manual_restaurant_map.json
build/restaurant_robot/manual_restaurant_map.pgm
```

## Run GUI Using A Saved Map

After saving a manual map, run the GUI against that map:

```bash
MAP_INPUT_JSON=build/restaurant_robot/manual_restaurant_map.json \
bash restaurant_robot/scripts/run_webots_gui_control.sh
```

## GUI With Scenario Obstacles

The GUI launcher accepts `SCENARIO=...`. These use the scenario supervisor while still showing the Webots GUI and Tkinter control GUI.

```bash
SCENARIO=person_crossing bash restaurant_robot/scripts/run_webots_gui_control.sh
```

```bash
SCENARIO=stationary_blockage bash restaurant_robot/scripts/run_webots_gui_control.sh
```

```bash
SCENARIO=moving_crowd bash restaurant_robot/scripts/run_webots_gui_control.sh
```

```bash
SCENARIO=chair_moved bash restaurant_robot/scripts/run_webots_gui_control.sh
```

```bash
SCENARIO=blocked_corridor bash restaurant_robot/scripts/run_webots_gui_control.sh
```

For generated facility world plus a scenario:

```bash
SCENARIO=moving_crowd \
MAP_INPUT_JSON=restaurant_robot/config/facility_layout_map.json \
WEBOTS_WORLD=restaurant_robot/simulator/worlds/facility_layout_generated.wbt \
bash restaurant_robot/scripts/run_webots_gui_control.sh
```

## Batch Scenario Runs

These run Webots without the interactive GUI. Use them for quick checks.

```bash
bash restaurant_robot/scripts/run_webots_scenario.sh person_crossing 45
bash restaurant_robot/scripts/run_webots_scenario.sh stationary_blockage 18
bash restaurant_robot/scripts/run_webots_scenario.sh moving_crowd 45
bash restaurant_robot/scripts/run_webots_scenario.sh destination_change 45
bash restaurant_robot/scripts/run_webots_scenario.sh emergency_stop 8
bash restaurant_robot/scripts/run_webots_scenario.sh chair_moved 18
bash restaurant_robot/scripts/run_webots_scenario.sh blocked_corridor 18
bash restaurant_robot/scripts/run_webots_scenario.sh localization_disturbance 9
```

## Webots Mapping Batch Run

This runs Webots mapping without the GUI and writes a map artifact.

```bash
bash restaurant_robot/scripts/run_webots_mapping.sh 10
```

Output:

```text
build/restaurant_robot/webots_generated_map.json
build/restaurant_robot/webots_generated_map.pgm
```

## Facility Layout Editor

Use this to edit tables, walls, no-go zones, kitchen, charging, home, and table points.

```bash
bash restaurant_robot/scripts/run_facility_layout_editor.sh
```

Default tracked output:

```text
restaurant_robot/config/facility_layout_map.json
restaurant_robot/simulator/worlds/facility_layout_generated.wbt
```

After saving, run:

```bash
bash restaurant_robot/scripts/run_generated_facility_world.sh
```

## Common Problems

If Webots does not start because another world is open:

```bash
ps -eo pid,cmd | rg -i 'webots|restaurant_delivery_controller|restaurant_control_gui'
```

Close the old Webots window before running another launcher.

If the generated facility world cannot find its map, verify these tracked files exist:

```bash
ls restaurant_robot/config/facility_layout_map.json
ls restaurant_robot/simulator/worlds/facility_layout_generated.wbt
```

The generated world should contain this portable map path:

```text
../../../config/facility_layout_map.json
```
