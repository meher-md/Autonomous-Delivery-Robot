#!/usr/bin/env bash
set -eo pipefail

cd "$(dirname "$0")"
source /opt/ros/humble/setup.bash

if [ ! -f install/setup.bash ]; then
  colcon build --symlink-install \
    --packages-select andino_description andino_slam andino_gz deliverybot_bringup
fi

source install/setup.bash

pkg_share="$(ros2 pkg prefix andino_gz)/share/andino_gz"
export GZ_SIM_RESOURCE_PATH="$pkg_share/models:$pkg_share/worlds:${GZ_SIM_RESOURCE_PATH:-}"
export IGN_GAZEBO_RESOURCE_PATH="$pkg_share/models:$pkg_share/worlds:${IGN_GAZEBO_RESOURCE_PATH:-}"

ros2 launch andino_gz andino_gz.launch.py \
  nav2:=True \
  world_name:=office.sdf \
  map:=office \
  autostart:=True
