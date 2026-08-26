#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORLD_PATH="${ROOT_DIR}/restaurant_robot/simulator/worlds/restaurant_delivery.wbt"
CONTROL_FILE="${CONTROL_FILE:-${ROOT_DIR}/build/restaurant_robot/control_command.txt}"
OUTPUT_PREFIX="${MAP_OUTPUT_PREFIX:-${ROOT_DIR}/build/restaurant_robot/manual_restaurant_map}"
MAX_TIME_SECONDS="${MAX_TIME:-0}"
MAP_INPUT="${MAP_INPUT_JSON:-}"

if pgrep -f "webots-bin.*restaurant_delivery.wbt" >/dev/null; then
  echo "A restaurant Webots world is already running. Close it before starting GUI control."
  exit 1
fi

cmake -S "${ROOT_DIR}" -B "${ROOT_DIR}/build"
cmake --build "${ROOT_DIR}/build" --target restaurant_delivery_controller restaurant_scenario_supervisor

mkdir -p "$(dirname "${CONTROL_FILE}")"

python3 "${ROOT_DIR}/restaurant_robot/scripts/restaurant_control_gui.py" --control-file "${CONTROL_FILE}" &
GUI_PID="$!"

cleanup() {
  if kill -0 "${GUI_PID}" >/dev/null 2>&1; then
    kill "${GUI_PID}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

OPERATING_MODE=NAVIGATION CONTROL_FILE="${CONTROL_FILE}" MAP_OUTPUT_PREFIX="${OUTPUT_PREFIX}" MAP_INPUT_JSON="${MAP_INPUT}" MAX_TIME="${MAX_TIME_SECONDS}" SCENARIO=none \
  webots --mode=realtime --stdout --stderr "${WORLD_PATH}"
