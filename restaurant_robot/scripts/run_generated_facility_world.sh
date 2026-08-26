#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FACILITY_MAP_JSON="${FACILITY_MAP_JSON:-${ROOT_DIR}/build/restaurant_robot/facility_layout_map.json}"
FACILITY_WORLD="${FACILITY_WORLD:-${ROOT_DIR}/restaurant_robot/simulator/worlds/facility_layout_generated.wbt}"

if [[ ! -f "${FACILITY_MAP_JSON}" ]]; then
  echo "Facility map does not exist: ${FACILITY_MAP_JSON}"
  echo "Create it with: bash restaurant_robot/scripts/run_facility_layout_editor.sh"
  exit 1
fi

python3 "${ROOT_DIR}/restaurant_robot/scripts/generate_webots_world_from_layout.py" "${FACILITY_MAP_JSON}" "${FACILITY_WORLD}" >/dev/null

MAP_INPUT_JSON="${FACILITY_MAP_JSON}" WEBOTS_WORLD="${FACILITY_WORLD}" \
  bash "${ROOT_DIR}/restaurant_robot/scripts/run_webots_gui_control.sh"
