#!/usr/bin/env bash
# ملاحظة: ما نستخدمش -u علشان setup.bash بتاعة ROS بتتوقع متغيرات مش معرفة أحيانًا
set -eo pipefail

echo "[env] Sourcing ROS…"
source /opt/ros/humble/setup.bash
# لو اتبنيت الـ workspace قبل كده:
if [ -f ~/ws/install/setup.bash ]; then
  source ~/ws/install/setup.bash
fi

echo "[kill] تأمين البورتات 9090/8080"
sudo fuser -k 9090/tcp || true
sudo fuser -k 8080/tcp || true
sleep 0.5

# ===== (اختياري) شغّل SLAM/Nav2 هنا لو جاهز عندك =====
# أمثلة، فعل واحد فقط وعدّل المسارات حسبك:
# ros2 launch slam_toolbox online_async_launch.py use_sim_time:=false &
# ros2 launch nav2_bringup navigation_launch.py map:=/home/mo/maps/office.yaml use_sim_time:=false &
# =======================================================

echo "[bridge] rosbridge على 9090"
ros2 launch rosbridge_server rosbridge_websocket_launch.xml port:=9090 address:=0.0.0.0 > /tmp/rosbridge.log 2>&1 &

echo "[video] web_video_server على 8080"
ros2 run web_video_server web_video_server --port 8080 > /tmp/web_video_server.log 2>&1 &

echo "[qr] خدمة QR"
ros2 run delivery_qr qr_generator_node > /tmp/qr.log 2>&1 &

echo "[order] نود الأوردر"
ros2 launch delivery_order delivery_order.launch.py > /tmp/order.log 2>&1 &

# انتظر شوية لحد ما يقوموا
sleep 2

echo "---- CHECKS ----"
echo "[ports]"
sudo ss -ltnp | awk '/:9090|:8080/ {print}'
echo "[WS test via nginx -> rosbridge]"
python3 - <<'PY'
import asyncio, websockets
async def main():
    ws = await websockets.connect('ws://10.42.0.1/rosbridge/')
    print("WS OK /rosbridge/")
    await ws.close()
asyncio.run(main())
PY
echo "[HTTP health]"
curl -sS http://10.42.0.1/ | cat
echo
echo "[camera HEAD]"
curl -sSI http://10.42.0.1/camera | sed -n '1,10p'
echo "[nav2]"
ros2 action list | grep navigate_to_pose || echo "تحذير: navigate_to_pose مش ظاهر (شغّل SLAM/Nav2)"
echo "[camera topic]"
ros2 topic list | grep -E 'image_raw|Image' || echo "تحذير: مفيش /image_raw (شغّل درايفر الكاميرا)"
echo "== stack up. Logs: /tmp/{rosbridge,web_video_server,qr,order}.log =="
