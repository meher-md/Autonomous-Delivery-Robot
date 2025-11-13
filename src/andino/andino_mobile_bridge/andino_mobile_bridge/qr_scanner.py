#!/usr/bin/env python3
import json
import time
import threading
import traceback

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

# Try picamera (older RPi API)
PICAMERA_AVAILABLE = False
try:
    import picamera
    import picamera.array
    PICAMERA_AVAILABLE = True
except Exception:
    PICAMERA_AVAILABLE = False

# Try OpenCV as fallback camera / decoder
OPENCV_AVAILABLE = False
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except Exception:
    OPENCV_AVAILABLE = False

# Try pyzbar for robust QR decoding
PYZBAR_AVAILABLE = False
try:
    from pyzbar import pyzbar
    PYZBAR_AVAILABLE = True
except Exception:
    PYZBAR_AVAILABLE = False

# Use cv2.QRCodeDetector if pyzbar not available but OpenCV is
USE_CV2_QR = OPENCV_AVAILABLE and not PYZBAR_AVAILABLE

class QrScanner(Node):
    def __init__(self):
        super().__init__('qr_scanner')
        self.scan_pub = self.create_publisher(String, '/robot/qr/scanned', 10)
        # Publisher to request app-style named-goal navigation (e.g. "Lobby")
        self.app_goal_pub = self.create_publisher(String, '/app/goal_name', 10)
        self.status_sub = self.create_subscription(String, '/robot/status', self.on_status, 10)
        self.scanning = False
        self.scan_thread = None
        self._last_scan_time = 0.0
        self._scan_cooldown = 5.0  # seconds to avoid duplicate publishes
        # Timer used to schedule return-to-lobby after a successful scan
        self._return_timer = None
        self._return_delay = 30.0  # seconds to wait before sending robot back to Lobby

        self.get_logger().info(f'qr_scanner ready (picamera={PICAMERA_AVAILABLE} opencv={OPENCV_AVAILABLE} pyzbar={PYZBAR_AVAILABLE})')

    def on_status(self, msg: String):
        try:
            st = json.loads(msg.data)
            arrived = bool(st.get('arrived', False))
        except Exception:
            payload = (msg.data or "").lower()
            arrived = 'arrived' in payload or 'succeeded' in payload

        if arrived and not self.scanning:
            self.start_scanning()
        elif not arrived and self.scanning:
            self.stop_scanning()

    def start_scanning(self):
        # Decide backend
        if not (PICAMERA_AVAILABLE or OPENCV_AVAILABLE):
            self.get_logger().error('No camera backend available (picamera or opencv). Install picamera or opencv/python bindings.')
            return

        if self.scan_thread and self.scan_thread.is_alive():
            self.get_logger().debug('Scan thread already running')
            return

        self.scanning = True
        if PICAMERA_AVAILABLE:
            self.scan_thread = threading.Thread(target=self._scan_with_picamera, daemon=True)
            self.get_logger().info('Starting scanner using picamera')
        else:
            self.scan_thread = threading.Thread(target=self._scan_with_opencv, daemon=True)
            self.get_logger().info('Starting scanner using OpenCV VideoCapture')
        self.scan_thread.start()

    def stop_scanning(self):
        self.scanning = False
        if self.scan_thread:
            self.scan_thread.join(timeout=2.0)
            self.scan_thread = None
        self.get_logger().info('Stopped QR scanning')

    def _scan_with_picamera(self):
        try:
            with picamera.PiCamera() as camera:
                camera.resolution = (640, 480)
                with picamera.array.PiRGBArray(camera) as stream:
                    while self.scanning:
                        camera.capture(stream, format='bgr', use_video_port=True)
                        image = stream.array
                        self._process_frame(image)
                        stream.truncate(0)
                        time.sleep(0.1)
        except Exception as e:
            self.get_logger().error(f'picamera scanning loop failed: {e}\n{traceback.format_exc()}')
            self.scanning = False

    def _scan_with_opencv(self):
        cap = None
        try:
            cap = cv2.VideoCapture(0)
            # try common options to improve capture on RasPi
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            # wait for camera warmup
            time.sleep(0.5)
            if not cap.isOpened():
                self.get_logger().error('OpenCV VideoCapture could not open camera device (0).')
                self.scanning = False
                return

            # if using cv2 QR detector, create instance
            qr_detector = None
            if USE_CV2_QR:
                qr_detector = cv2.QRCodeDetector()

            while self.scanning and cap.isOpened():
                ret, frame = cap.read()
                if not ret or frame is None:
                    time.sleep(0.1)
                    continue

                # frame is BGR numpy array
                if PYZBAR_AVAILABLE:
                    # pyzbar expects RGB or BGR works too; decode directly
                    decoded = pyzbar.decode(frame)
                    if decoded:
                        for obj in decoded:
                            try:
                                raw = obj.data.decode('utf-8')
                                self._publish_scan(raw)
                            except Exception as e:
                                self.get_logger().error(f'Failed handling pyzbar decoded QR: {e}')
                elif USE_CV2_QR:
                    try:
                        data, points, _ = qr_detector.detectAndDecode(frame)
                        if data:
                            self._publish_scan(data)
                    except Exception as e:
                        self.get_logger().error(f'cv2 QR decode failed: {e}')
                else:
                    # neither decoder available
                    self.get_logger().error('No QR decoder available (pyzbar or cv2.QRCodeDetector).')
                    break

                time.sleep(0.1)
        except Exception as e:
            self.get_logger().error(f'OpenCV scanning loop failed: {e}\n{traceback.format_exc()}')
        finally:
            try:
                if cap is not None and cap.isOpened():
                    cap.release()
            except Exception:
                pass
            self.scanning = False

    def _process_frame(self, image):
        # image: numpy BGR array
        try:
            if PYZBAR_AVAILABLE:
                decoded = pyzbar.decode(image)
                for obj in decoded:
                    try:
                        raw = obj.data.decode('utf-8')
                        self._publish_scan(raw)
                    except Exception as e:
                        self.get_logger().error(f'Failed to handle decoded QR: {e}')
            elif USE_CV2_QR:
                detector = cv2.QRCodeDetector()
                data, points, _ = detector.detectAndDecode(image)
                if data:
                    self._publish_scan(data)
            else:
                self.get_logger().error('No decoder available to process frames')
        except Exception as e:
            self.get_logger().error(f'Frame processing failed: {e}')

    def _publish_scan(self, payload_str: str):
        now = time.time()
        if now - self._last_scan_time < self._scan_cooldown:
            return
        try:
            out = String()
            out.data = json.dumps({
                'raw': payload_str,
                'timestamp': now
            })
            self.scan_pub.publish(out)
            self.get_logger().info(f'Scanned QR data: {payload_str}')
            self._last_scan_time = now
            # After a successful scan, schedule (or reset) a 30s timer to send robot to Lobby
            try:
                self._schedule_return_to_lobby(self._return_delay)
            except Exception as e:
                self.get_logger().error(f'Failed scheduling return to Lobby: {e}')
        except Exception as e:
            self.get_logger().error(f'Publishing scan failed: {e}')

    def _schedule_return_to_lobby(self, delay: float = 30.0):
        """Schedule publishing the named goal 'Lobby' to /app/goal_name after `delay` seconds.
        If a timer is already pending, cancel it and reset the timer so the robot waits `delay`
        seconds after the most recent successful scan.
        """
        # Cancel existing timer if active
        try:
            if self._return_timer is not None:
                try:
                    self._return_timer.cancel()
                except Exception:
                    pass
                self._return_timer = None

            def _do_return():
                try:
                    goal_msg = String()
                    goal_msg.data = 'Lobby'
                    self.app_goal_pub.publish(goal_msg)
                    self.get_logger().info(f'Published return-to-Lobby request to {self.app_goal_pub.topic_name}')
                except Exception as e:
                    self.get_logger().error(f'Failed to publish return-to-Lobby: {e}')

            t = threading.Timer(delay, _do_return)
            t.daemon = True
            t.start()
            self._return_timer = t
            self.get_logger().info(f'Scheduled return to Lobby in {delay} seconds')
        except Exception as e:
            self.get_logger().error(f'Error scheduling return to Lobby: {e}')

def main(args=None):
    rclpy.init(args=args)
    node = QrScanner()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.stop_scanning()
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
