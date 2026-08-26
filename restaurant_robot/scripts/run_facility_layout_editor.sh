#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUTPUT_PATH="${FACILITY_MAP_JSON:-${ROOT_DIR}/build/restaurant_robot/facility_layout_map.json}"

mkdir -p "$(dirname "${OUTPUT_PATH}")"
python3 "${ROOT_DIR}/restaurant_robot/scripts/facility_layout_editor.py" --output "${OUTPUT_PATH}"
