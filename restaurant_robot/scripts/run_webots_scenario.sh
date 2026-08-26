#!/usr/bin/env bash
set -euo pipefail

SCENARIO_NAME="${1:-person_crossing}"
MAX_TIME_SECONDS="${2:-45}"
WEBOTS_TIMEOUT_SECONDS="$((MAX_TIME_SECONDS + 8))"
INITIAL_GOAL_TABLE="${GOAL_TABLE:-TABLE_3}"
SCAN_LOCALIZATION="${ENABLE_SCAN_LOCALIZATION:-0}"
if [[ "${SCENARIO_NAME}" == "destination_change" && -z "${GOAL_TABLE:-}" ]]; then
  INITIAL_GOAL_TABLE="TABLE_2"
fi
if [[ "${SCENARIO_NAME}" == "localization_disturbance" && -z "${ENABLE_SCAN_LOCALIZATION:-}" ]]; then
  SCAN_LOCALIZATION="1"
fi
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORLD_PATH="${ROOT_DIR}/restaurant_robot/simulator/worlds/restaurant_delivery.wbt"
ROBOT_LOG="${ROOT_DIR}/restaurant_robot/simulator/controllers/restaurant_delivery_controller/restaurant_run.csv"
SCENARIO_LOG="${ROOT_DIR}/restaurant_robot/simulator/controllers/restaurant_scenario_supervisor/scenario_metrics.csv"

cmake -S "${ROOT_DIR}" -B "${ROOT_DIR}/build"
cmake --build "${ROOT_DIR}/build" --target restaurant_delivery_controller restaurant_scenario_supervisor

rm -f "${ROBOT_LOG}" "${SCENARIO_LOG}"

set +e
SCENARIO="${SCENARIO_NAME}" MAX_TIME="${MAX_TIME_SECONDS}" GOAL_TABLE="${INITIAL_GOAL_TABLE}" ENABLE_SCAN_LOCALIZATION="${SCAN_LOCALIZATION}" \
  timeout "${WEBOTS_TIMEOUT_SECONDS}s" webots --batch --no-rendering --mode=fast --stdout --stderr "${WORLD_PATH}"
WEBOTS_STATUS="$?"
set -e

if [[ "${WEBOTS_STATUS}" != "0" && "${WEBOTS_STATUS}" != "124" ]]; then
  exit "${WEBOTS_STATUS}"
fi

echo "robot_log=${ROBOT_LOG}"
tail -n 5 "${ROBOT_LOG}" || true

echo "scenario_log=${SCENARIO_LOG}"
tail -n 5 "${SCENARIO_LOG}" || true
