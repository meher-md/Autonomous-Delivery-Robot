#!/usr/bin/env bash
set -euo pipefail

MAX_TIME_SECONDS="${1:-0}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORLD_PATH="${ROOT_DIR}/restaurant_robot/simulator/worlds/restaurant_delivery.wbt"
OUTPUT_PREFIX="${MAP_OUTPUT_PREFIX:-${ROOT_DIR}/build/restaurant_robot/manual_restaurant_map}"
CONTROL_FILE="${CONTROL_FILE:-${ROOT_DIR}/build/restaurant_robot/control_command.txt}"
MAP_INPUT="${MAP_INPUT_JSON:-}"

if pgrep -f "webots-bin.*restaurant_delivery.wbt" >/dev/null; then
  echo "A restaurant Webots world is already running. Close it before starting manual mapping."
  exit 1
fi

cmake -S "${ROOT_DIR}" -B "${ROOT_DIR}/build"
cmake --build "${ROOT_DIR}/build" --target restaurant_delivery_controller restaurant_scenario_supervisor

echo "Manual mapping controls:"
echo "  W/A/S/D or arrow keys: drive"
echo "  Space: stop"
echo "  M: save current map checkpoint"
echo "  Q: quit controller"
echo "Map output prefix: ${OUTPUT_PREFIX}"

OPERATING_MODE=MANUAL_MAPPING CONTROL_FILE="${CONTROL_FILE}" MAP_OUTPUT_PREFIX="${OUTPUT_PREFIX}" MAP_INPUT_JSON="${MAP_INPUT}" MAX_TIME="${MAX_TIME_SECONDS}" SCENARIO=none \
  webots --mode=realtime --stdout --stderr "${WORLD_PATH}"
