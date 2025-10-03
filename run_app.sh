#!/usr/bin/env bash
set -e
[ -f /opt/ros/humble/setup.bash ] && source /opt/ros/humble/setup.bash || true
[ -f "$HOME/ws/install/setup.bash" ] && source "$HOME/ws/install/setup.bash" || true

PKG=deliverybot_bringup
ROSBRIDGE_PORT=${ROSBRIDGE_PORT:-9090}
WEB_VIDEO_PORT=${WEB_VIDEO_PORT:-8080}
START_SLAM=${START_SLAM:-false}
START_MAP_HTTP=${START_MAP_HTTP:-false}
MAP_HTTP_PORT=${MAP_HTTP_PORT:-8070}

echo "==> launching ${PKG}/app.launch.py (rosbridge:${ROSBRIDGE_PORT}, web_video:${WEB_VIDEO_PORT}, slam:${START_SLAM}, map_http:${START_MAP_HTTP})"

set +e
ros2 launch "${PKG}" app.launch.py \
  rosbridge_port:=${ROSBRIDGE_PORT} \
  web_video_port:=${WEB_VIDEO_PORT} \
  start_slam:=${START_SLAM} \
  start_map_http:=${START_MAP_HTTP} \
  map_http_port:=${MAP_HTTP_PORT}
rc=$?
set -e

if [ $rc -ne 0 ]; then
  echo "!! launch failed; starting minimal stack directly..."
  pgrep -f rosbridge_websocket >/dev/null || \
    (nohup ros2 run rosbridge_server rosbridge_websocket --port ${ROSBRIDGE_PORT} \
      > ~/.ros/rosbridge.log 2>&1 &)
  pgrep -f web_video_server >/dev/null || \
    (nohup ros2 run web_video_server web_video_server --port ${WEB_VIDEO_PORT} \
      > ~/.ros/web_video.log 2>&1 &)
  if [ "${START_SLAM}" = "true" ]; then
    pgrep -f async_slam_toolbox_node >/dev/null || \
      (nohup ros2 launch slam_toolbox online_async_launch.py \
        > ~/.ros/slam_toolbox.log 2>&1 &)
  fi
  if [ "${START_MAP_HTTP}" = "true" ]; then
    if ros2 pkg executables map_http_bridge >/dev/null 2>&1; then
      pgrep -f map_http_bridge >/dev/null || \
        (nohup ros2 run map_http_bridge map_http_bridge --port ${MAP_HTTP_PORT} \
          > ~/.ros/map_http_bridge.log 2>&1 &)
    else
      echo "!! map_http_bridge package not found; skipping map HTTP bridge"
    fi
  fi
  echo "Started minimal stack."
  wait
fi
