#!/usr/bin/env python3
import json
import time
import threading
import traceback

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

# Try picamera (older Raspberry Pi API) - not used in this simplified version
PICAMERA_AVAILABLE = False
try:
    import picamera
    import picamera.array
    PICAMERA_AVAILABLE = True
except Exception:
    PICAMERA_AVAILABLE = False

# Try OpenCV as primary camera / decoder (laptop or Raspberry Pi camera via /dev/video0)
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

        # Publisher for scanned QR codes
        self.scan_pub = self.create_publisher(String, '/robot/qr/scanned', 10)

        # Publisher to request app-style named-goal navigation (e.g. "Lobby")
        self.app_goal_pub = self.create_publisher(String, '/app/goal_name', 10)

        # Publisher for scanner status (for monitoring)
        self.status_pub = self.create_publisher(String, '/robot/qr/scanner_status', 10)

        # Subscribe to app_goal_gateway status (publishes "succeeded" when robot arrives)
        self.status_sub = self.create_subscription(
            String, '/app/goal_status', self.on_status, 10
        )

        # Subscribe to goal_name to track current destination (to skip scanning at Lobby)
        self.goal_name_sub = self.create_subscription(
            String, '/app/goal_name', self.on_goal_name, 10
        )

        # Subscribe to order creation topics to reset timer state when a new order is placed
        self.order_create_sub = self.create_subscription(
            String, '/order/create', self.on_order_created, 10
        )
        self.order_json_sub = self.create_subscription(
            String, '/order/json', self.on_order_created, 10
        )

        # Whether scanner loop is currently active
        self.scanning = False

        # Track current destination to avoid scanning at Lobby
        self.current_destination = None

        # Background scanning thread
        self.scan_thread = None

        # Cooldown management for publishing QR scans
        self._last_scan_time = 0.0
        self._scan_cooldown = 5.0  # seconds to avoid duplicate publishes

        # Timer used to schedule return-to-lobby after ARRIVAL
        self._return_timer = None
        self._return_delay = 30.0  # seconds to wait before sending robot back to Lobby

        # Flag to track if the return-to-lobby timer is already scheduled
        self._timer_scheduled = False

        # Monitoring: frame processing stats
        self._frames_processed = 0

        # Whether camera is currently open
        self._camera_opened = False

        self.get_logger().info(
            f'qr_scanner ready (using OpenCV camera, opencv={OPENCV_AVAILABLE}, pyzbar={PYZBAR_AVAILABLE})'
        )
        self._publish_status('initialized', 'Scanner initialized and ready')

    # -------------------------------------------------------------------------
    # Callbacks for external topics
    # -------------------------------------------------------------------------

    def on_goal_name(self, msg: String):
        """Track the current destination name (e.g. Lab, Lobby, Cafeteria)."""
        try:
            goal_name = msg.data.strip()
            if goal_name:
                self.current_destination = goal_name
                self.get_logger().debug(f'Tracking destination: {goal_name}')
        except Exception as e:
            self.get_logger().debug(f'Error tracking goal name: {e}')

    def on_status(self, msg: String):
        """
        Handle status messages from app_goal_gateway (/app/goal_status).

        - When robot ARRIVES (status contains "arrived" or "succeeded"):
          * If destination != Lobby:
              - Start QR scanner.
              - Schedule return to Lobby after self._return_delay seconds
                (even if QR scan fails or no QR is detected).
          * If destination == Lobby:
              - Do not start scanner and do not schedule return.

        - When robot is no longer arrived and scanner is active:
          * Stop scanner.
        """
        try:
            # Try to parse as JSON first: {"arrived": true, ...}
            st = json.loads(msg.data)
            arrived = bool(st.get('arrived', False))
            self.get_logger().debug(
                f'Received status (JSON): {msg.data}, arrived={arrived}'
            )
        except Exception:
            # Fallback: check if message contains "succeeded" or "arrived"
            payload = (msg.data or "").lower()
            arrived = 'arrived' in payload or 'succeeded' in payload
            self.get_logger().info(
                f'Received status message: "{msg.data}" -> arrived={arrived}'
            )

        if arrived and not self.scanning:
            # Check if destination is Lobby - don't start scanning or timer at Lobby
            if self.current_destination and self.current_destination.lower() == 'lobby':
                self.get_logger().info(
                    '🚫 Robot arrived at Lobby - skipping QR scan (waiting for new order)'
                )
                self._publish_status(
                    'skipped',
                    'Arrived at Lobby - scanner not started (waiting for new order)'
                )
            else:
                destination_str = (
                    f' at {self.current_destination}' if self.current_destination else ''
                )
                self.get_logger().info(
                    f'✅ Robot arrived at destination{destination_str} - starting QR scanner!'
                )

                # Start QR scanner on arrival
                self.start_scanning()

                # Schedule return to Lobby after a fixed delay,
                # regardless of whether QR scanning succeeds or not
                if not self._timer_scheduled:
                    try:
                        self._schedule_return_to_lobby(self._return_delay)
                    except Exception as e:
                        self.get_logger().error(
                            f'Failed scheduling return to Lobby: {e}'
                        )

        elif not arrived and self.scanning:
            # Robot left destination - stop scanner
            self.get_logger().info('Robot left destination - stopping QR scanner')
            self.stop_scanning()

        elif arrived and self.scanning:
            # Already scanning at destination
            self.get_logger().debug('Robot still at destination, scanner already running')

        else:
            # No arrival and not scanning
            self.get_logger().debug(
                f'Robot not at destination (status: "{msg.data}"), scanner not running'
            )

    def on_order_created(self, msg: String):
        """
        Reset timer state when a new order is placed,
        allowing a new return-to-lobby timer to be scheduled after the next arrival.
        """
        try:
            # Parse order message to verify it's a valid order
            order_data = json.loads(msg.data) if msg.data else {}
            if order_data or 'order_id' in str(msg.data):
                # Allow a new timer to be scheduled for the next arrival
                self._timer_scheduled = False

                # Cancel any existing timer since a new order was placed
                if self._return_timer is not None:
                    try:
                        self._return_timer.cancel()
                    except Exception:
                        pass
                    self._return_timer = None

                self.get_logger().info(
                    'New order detected - timer state reset, '
                    'timer can be scheduled again after arrival'
                )
        except Exception as e:
            self.get_logger().debug(f'Error parsing order message: {e}')

    # -------------------------------------------------------------------------
    # Scanning control
    # -------------------------------------------------------------------------

    def start_scanning(self):
        """
        Start QR scanning using OpenCV VideoCapture on device 0.

        This assumes:
        - On laptop: internal webcam is /dev/video0
        - On Raspberry Pi: Pi camera or USB camera is exposed as /dev/video0
        """
        if not OPENCV_AVAILABLE:
            error_msg = 'OpenCV not available. Install opencv-python for camera support.'
            self.get_logger().error(error_msg)
            self._publish_status('error', error_msg)
            return

        if self.scan_thread and self.scan_thread.is_alive():
            self.get_logger().debug('Scan thread already running')
            return

        self.scanning = True
        self._frames_processed = 0

        self.scan_thread = threading.Thread(
            target=self._scan_with_opencv,
            daemon=True
        )
        self.get_logger().info(
            '🚀 Starting QR scanner using OpenCV VideoCapture (camera device 0)'
        )
        self._publish_status('starting', 'Starting camera and QR scanner...')
        self.scan_thread.start()

    def stop_scanning(self):
        """Stop the scanning thread and reset camera state."""
        self.scanning = False
        self._camera_opened = False

        if self.scan_thread:
            self.scan_thread.join(timeout=2.0)
            self.scan_thread = None

        self.get_logger().info('⏹️  Stopped QR scanning')
        self._publish_status(
            'stopped',
            f'Scanner stopped. Processed {self._frames_processed} frames.'
        )
        self._frames_processed = 0

    # -------------------------------------------------------------------------
    # Camera backend: OpenCV
    # -------------------------------------------------------------------------

    def _scan_with_picamera(self):
        """
        Unused in this simplified version. Included only for completeness.
        """
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
            self.get_logger().error(
                f'picamera scanning loop failed: {e}\n{traceback.format_exc()}'
            )
            self.scanning = False

    def _scan_with_opencv(self):
        """
        Main scanning loop using OpenCV VideoCapture on device 0.
        """
        cap = None
        try:
            self.get_logger().info('📷 Attempting to open camera with OpenCV (device 0)...')
            cap = cv2.VideoCapture(0)

            # Configure basic capture properties
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

            # Small warm-up delay
            time.sleep(0.5)

            if not cap.isOpened():
                error_msg = (
                    '❌ OpenCV VideoCapture could not open camera device (0). '
                    'Check if camera is connected and not in use by another application.'
                )
                self.get_logger().error(error_msg)
                self._publish_status('error', error_msg)
                self.scanning = False
                return

            # Get camera properties for logging
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)

            self._camera_opened = True
            self.get_logger().info(
                f'✅ Camera opened successfully! Resolution: {width}x{height}, FPS: {fps}'
            )
            self._publish_status(
                'scanning',
                f'Camera active. Scanning for QR codes at {width}x{height}...'
            )

            # Initialize QR decoder
            qr_detector = None
            if USE_CV2_QR:
                qr_detector = cv2.QRCodeDetector()
                self.get_logger().info('Using cv2.QRCodeDetector for QR decoding')
            elif PYZBAR_AVAILABLE:
                self.get_logger().info('Using pyzbar for QR decoding')

            frame_count = 0
            last_status_update = time.time()

            while self.scanning and cap.isOpened():
                ret, frame = cap.read()
                if not ret or frame is None:
                    self.get_logger().warn('⚠️  Failed to read frame from camera')
                    time.sleep(0.1)
                    continue

                frame_count += 1
                self._frames_processed += 1

                # Periodic status update (every 5 seconds)
                if time.time() - last_status_update >= 5.0:
                    self.get_logger().info(
                        f'📹 Camera active: processed {self._frames_processed} frames '
                        f'({frame_count} in current session)'
                    )
                    self._publish_status(
                        'scanning',
                        f'Active: {self._frames_processed} frames processed, scanning for QR codes...'
                    )
                    last_status_update = time.time()

                # Decode QR using pyzbar if available
                if PYZBAR_AVAILABLE:
                    decoded = pyzbar.decode(frame)
                    if decoded:
                        for obj in decoded:
                            try:
                                raw = obj.data.decode('utf-8')
                                self.get_logger().info('🔍 QR code detected! Processing...')
                                self._publish_scan(raw)
                            except Exception as e:
                                self.get_logger().error(
                                    f'Failed handling pyzbar decoded QR: {e}'
                                )
                # Otherwise use cv2.QRCodeDetector
                elif USE_CV2_QR:
                    try:
                        data, points, _ = qr_detector.detectAndDecode(frame)
                        if data:
                            self.get_logger().info('🔍 QR code detected! Processing...')
                            self._publish_scan(data)
                    except Exception as e:
                        self.get_logger().error(f'cv2 QR decode failed: {e}')
                else:
                    # No decoder available
                    error_msg = 'No QR decoder available (pyzbar or cv2.QRCodeDetector).'
                    self.get_logger().error(error_msg)
                    self._publish_status('error', error_msg)
                    break

                time.sleep(0.1)

        except Exception as e:
            error_msg = f'OpenCV scanning loop failed: {e}'
            self.get_logger().error(f'{error_msg}\n{traceback.format_exc()}')
            self._publish_status('error', error_msg)
        finally:
            try:
                if cap is not None and cap.isOpened():
                    cap.release()
                    self.get_logger().info('📷 Camera released')
            except Exception:
                pass
            self._camera_opened = False
            self.scanning = False

    # -------------------------------------------------------------------------
    # QR publish + status + return-to-lobby scheduling
    # -------------------------------------------------------------------------

    def _process_frame(self, image):
        """
        Process a single BGR image (numpy array) and try to decode QR codes.
        This is provided for completeness but not used in this simplified flow.
        """
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
        """
        Publish a QR scan result to /robot/qr/scanned with cooldown.
        NOTE:
        - The return-to-Lobby timer is NOT triggered here anymore.
        - Timer is now scheduled on arrival in on_status(), regardless of scan success.
        """
        now = time.time()
        if now - self._last_scan_time < self._scan_cooldown:
            self.get_logger().debug('Scan cooldown active, ignoring duplicate scan')
            return

        try:
            out = String()
            out.data = json.dumps({
                'raw': payload_str,
                'timestamp': now
            })
            self.scan_pub.publish(out)
            self.get_logger().info(
                f'✅ QR code scanned successfully! Data: {payload_str[:50]}...'
            )
            self._publish_status(
                'qr_scanned',
                f'QR code scanned: {payload_str[:30]}...'
            )
            self._last_scan_time = now
        except Exception as e:
            self.get_logger().error(f'Publishing scan failed: {e}')

    def _publish_status(self, status: str, message: str):
        """
        Publish scanner status to /robot/qr/scanner_status for monitoring.
        """
        try:
            status_msg = String()
            status_data = {
                'status': status,
                'message': message,
                'scanning': self.scanning,
                'camera_opened': self._camera_opened,
                'frames_processed': self._frames_processed,
                'timestamp': time.time()
            }
            status_msg.data = json.dumps(status_data)
            self.status_pub.publish(status_msg)
        except Exception as e:
            self.get_logger().debug(f'Failed to publish status: {e}')

    def _schedule_return_to_lobby(self, delay: float = 30.0):
        """
        Schedule publishing the named goal "Lobby" to /app/goal_name after `delay` seconds.

        - Timer is non-resettable until a new order is placed.
        - If a timer already exists, it will be cancelled and replaced.
        """
        try:
            # Cancel existing timer if active
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
                    self.get_logger().info(
                        f'Published return-to-Lobby request to {self.app_goal_pub.topic_name}'
                    )
                    # Reset flag after timer fires
                    self._timer_scheduled = False
                except Exception as e:
                    self.get_logger().error(f'Failed to publish return-to-Lobby: {e}')
                    self._timer_scheduled = False

            t = threading.Timer(delay, _do_return)
            t.daemon = True
            t.start()
            self._return_timer = t
            self._timer_scheduled = True

            self.get_logger().info(
                f'Scheduled return to Lobby in {delay} seconds '
                '(timer is non-resettable until a new order is placed)'
            )
        except Exception as e:
            self.get_logger().error(f'Error scheduling return to Lobby: {e}')
            self._timer_scheduled = False


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
