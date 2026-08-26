#!/usr/bin/env bash
set -euo pipefail

MAX_TIME_SECONDS="${1:-10}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORLD_PATH="${ROOT_DIR}/restaurant_robot/simulator/worlds/restaurant_delivery.wbt"
OUTPUT_PREFIX="${ROOT_DIR}/build/restaurant_robot/webots_generated_map"
WEBOTS_TIMEOUT_SECONDS="$((MAX_TIME_SECONDS + 8))"

cmake -S "${ROOT_DIR}" -B "${ROOT_DIR}/build"
cmake --build "${ROOT_DIR}/build" --target restaurant_delivery_controller restaurant_scenario_supervisor

set +e
OPERATING_MODE=MAPPING MAP_OUTPUT_PREFIX="${OUTPUT_PREFIX}" MAX_TIME="${MAX_TIME_SECONDS}" SCENARIO=none \
  timeout "${WEBOTS_TIMEOUT_SECONDS}s" webots --batch --no-rendering --mode=fast --stdout --stderr "${WORLD_PATH}"
WEBOTS_STATUS="$?"
set -e

if [[ "${WEBOTS_STATUS}" != "0" && "${WEBOTS_STATUS}" != "124" ]]; then
  exit "${WEBOTS_STATUS}"
fi

JSON_PATH="${OUTPUT_PREFIX}.json"
PGM_PATH="${OUTPUT_PREFIX}.pgm"

test -s "${JSON_PATH}"
test -s "${PGM_PATH}"

echo "map_json=${JSON_PATH}"
echo "map_pgm=${PGM_PATH}"
ls -lh "${JSON_PATH}" "${PGM_PATH}"
