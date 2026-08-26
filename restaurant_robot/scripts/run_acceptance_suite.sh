#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ROBOT_LOG="${ROOT_DIR}/restaurant_robot/simulator/controllers/restaurant_delivery_controller/restaurant_run.csv"
SCENARIO_LOG="${ROOT_DIR}/restaurant_robot/simulator/controllers/restaurant_scenario_supervisor/scenario_metrics.csv"
SUMMARY="${ROOT_DIR}/restaurant_robot/acceptance_summary.txt"

pass() {
  echo "PASS: $*" | tee -a "${SUMMARY}"
}

fail() {
  echo "FAIL: $*" | tee -a "${SUMMARY}"
  exit 1
}

require_log_contains() {
  local file="$1"
  local pattern="$2"
  local label="$3"
  if rg -q "${pattern}" "${file}"; then
    pass "${label}"
  else
    fail "${label}"
  fi
}

run_webots_and_check_zero_collisions() {
  local scenario="$1"
  local seconds="$2"
  bash "${ROOT_DIR}/restaurant_robot/scripts/run_webots_scenario.sh" "${scenario}" "${seconds}" >/tmp/restaurant_${scenario}.log 2>&1
  require_log_contains "/tmp/restaurant_${scenario}.log" "collision_count=0" "${scenario}: zero collisions"
}

run_debug_export_check() {
  local image="/tmp/restaurant_debug_snapshot.png"
  rm -f "${image}"
  DEBUG_EXPORT_PATH="${image}" bash "${ROOT_DIR}/restaurant_robot/scripts/run_webots_scenario.sh" person_crossing 4 >/tmp/restaurant_debug_export.log 2>&1
  require_log_contains /tmp/restaurant_debug_export.log "debug_snapshot_saved=true" "debug export: snapshot save reported"
  if [[ -s "${image}" ]]; then
    pass "debug export: PNG snapshot generated"
  else
    fail "debug export: PNG snapshot generated"
  fi
}

run_headless_and_check_success() {
  local table="$1"
  "${ROOT_DIR}/build/restaurant_robot/run_headless_scenario" "${table}" 3000 | tee "/tmp/headless_${table}.log" | tee -a "${SUMMARY}"
  require_log_contains "/tmp/headless_${table}.log" "mission_success=true" "headless ${table} mission success"
  require_log_contains "/tmp/headless_${table}.log" "collision_count=0" "headless ${table} zero collisions"
}

: > "${SUMMARY}"

cmake -S "${ROOT_DIR}" -B "${ROOT_DIR}/build" | tee -a "${SUMMARY}"
cmake --build "${ROOT_DIR}/build" | tee -a "${SUMMARY}"
ctest --test-dir "${ROOT_DIR}/build" --output-on-failure | tee -a "${SUMMARY}"
pass "core tests and Webots smoke test"

"${ROOT_DIR}/build/restaurant_robot/run_headless_scenario" TABLE_3 2400 | tee /tmp/headless_table3.log | tee -a "${SUMMARY}"
require_log_contains /tmp/headless_table3.log "mission_success=true" "headless TABLE_3 mission success"
require_log_contains /tmp/headless_table3.log "collision_count=0" "headless TABLE_3 zero collisions"
run_headless_and_check_success TABLE_1
run_headless_and_check_success TABLE_5

"${ROOT_DIR}/build/restaurant_robot/generate_map_artifacts" "${ROOT_DIR}/build/restaurant_robot/generated_restaurant_map" | tee /tmp/generated_map.log | tee -a "${SUMMARY}"
require_log_contains /tmp/generated_map.log "map_json=.*generated_restaurant_map.json" "mapping: JSON artifact generated"
require_log_contains /tmp/generated_map.log "map_pgm=.*generated_restaurant_map.pgm" "mapping: PGM artifact generated"
require_log_contains /tmp/generated_map.log "slam_backend=known_pose_ray_mapper" "mapping: known-pose backend used"
require_log_contains /tmp/generated_map.log "occupied_cells=[1-9][0-9]*" "mapping: occupied cells generated"

bash "${ROOT_DIR}/restaurant_robot/scripts/run_webots_mapping.sh" 8 >/tmp/webots_mapping.log 2>&1
require_log_contains /tmp/webots_mapping.log "map_json=.*webots_generated_map.json" "webots mapping: JSON artifact generated"
require_log_contains /tmp/webots_mapping.log "map_pgm=.*webots_generated_map.pgm" "webots mapping: PGM artifact generated"
require_log_contains /tmp/webots_mapping.log "slam_backend=known_pose_ray_mapper" "webots mapping: known-pose backend used"

run_webots_and_check_zero_collisions person_crossing 12
require_log_contains "${ROBOT_LOG}" "CAUTION" "person_crossing: robot entered caution state"
run_debug_export_check

run_webots_and_check_zero_collisions stationary_blockage 18
require_log_contains "${ROBOT_LOG}" "STOP" "stationary_blockage: robot stopped"
require_log_contains "${ROBOT_LOG}" ",1," "stationary_blockage: replan event recorded"

run_webots_and_check_zero_collisions chair_moved 18
require_log_contains "${ROBOT_LOG}" "STOP" "chair_moved: robot stopped"
require_log_contains "${ROBOT_LOG}" ",1," "chair_moved: replan event recorded"

run_webots_and_check_zero_collisions blocked_corridor 18
require_log_contains "${ROBOT_LOG}" "STOP" "blocked_corridor: robot stopped"
require_log_contains "${ROBOT_LOG}" ",1," "blocked_corridor: replan event recorded"

run_webots_and_check_zero_collisions moving_crowd 12
pass "moving_crowd: completed scenario run"

run_webots_and_check_zero_collisions destination_change 8
require_log_contains "${ROBOT_LOG}" "TABLE_2" "destination_change: initial destination TABLE_2 observed"
require_log_contains "${ROBOT_LOG}" "TABLE_4" "destination_change: updated destination TABLE_4 observed"

run_webots_and_check_zero_collisions emergency_stop 7
require_log_contains "${ROBOT_LOG}" "EMERGENCY_STOP" "emergency_stop: emergency safety state observed"
require_log_contains "${ROBOT_LOG}" "4\\.032,.*KITCHEN,TABLE_3,0,0,.*EMERGENCY_STOP" "emergency_stop: zero command next cycle"

run_webots_and_check_zero_collisions localization_disturbance 9
ROBOT_LAST="$(tail -n 1 "${ROBOT_LOG}")"
SCENARIO_LAST="$(tail -n 1 "${SCENARIO_LOG}")"
if awk -F, -v robot_row="${ROBOT_LAST}" -v scenario_row="${SCENARIO_LAST}" '
  BEGIN {
    split(robot_row, r, ",");
    split(scenario_row, s, ",");
    odom_dx = r[2] - s[3];
    odom_dy = r[3] - s[4];
    est_dx = r[5] - s[3];
    est_dy = r[6] - s[4];
    odom_error = sqrt(odom_dx * odom_dx + odom_dy * odom_dy);
    est_error = sqrt(est_dx * est_dx + est_dy * est_dy);
    exit(est_error < odom_error ? 0 : 1);
  }'; then
  pass "localization_disturbance: estimated pose closer than disturbed odometry"
else
  fail "localization_disturbance: estimated pose closer than disturbed odometry"
fi

pass "acceptance suite completed"
echo "summary=${SUMMARY}"
