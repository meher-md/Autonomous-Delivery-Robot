#!/usr/bin/env python3
import json
import time
import threading
import traceback
import sys
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Bool
from sensor_msgs.msg import CompressedImage
import cv2
import numpy as np

# Try pyzbar for robust QR decoding
PYZBAR_AVAILABLE = False
try:
    from pyzbar import pyzbar
    PYZBAR_AVAILABLE = True
except Exception:
    PYZBAR_AVAILABLE = False


class QrScanner(Node):
    def __init__(self):
        super().__init__('qr_scanner')

        # Publisher for scanned QR codes
        self.scan_pub = self.create_publisher(String, '/robot/qr/scanned', 10)

        # Publisher for verification status (triggers Like Detector)
        self.verified_pub = self.create_publisher(Bool, '/robot/qr/verified', 10)

        # Publisher to request app-style named-goal navigation (e.g. "R403")
        self.app_goal_pub = self.create_publisher(String, '/app/goal_name', 10)

        # Publisher for scanner status (for monitoring)
        self.status_pub = self.create_publisher(String, '/robot/qr/scanner_status', 10)

        # Subscribe to camera topic (Compressed)
        self.image_sub = self.create_subscription(
            CompressedImage, '/camera/image_raw/compressed', self.image_callback, 10
        )

        # Subscribe to app_goal_gateway status (publishes "succeeded" when robot arrives)
        self.status_sub = self.create_subscription(
            String, '/app/goal_status', self.on_status, 10
        )

        # Subscribe to goal_name to track current destination (to skip scanning at R403)
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

        # Whether scanner is currently active
        self.scanning = False

        # Track current destination to avoid scanning at R403
        self.current_destination = None
        
        # Track active order ID for verification
        self.active_order_id = None

        # Cooldown management for publishing QR scans
        self._last_scan_time = 0.0
        self._scan_cooldown = 5.0  # seconds to avoid duplicate publishes

        # Timer used to schedule return-to-R403 after ARRIVAL
        self._return_timer = None
        self._return_delay = 30.0  # seconds to wait before sending robot back to R403

        # Flag to track if the return-to-R403 timer is already scheduled
        self._timer_scheduled = False

        # Monitoring: frame processing stats
        self._frames_processed = 0

        self.get_logger().info(
            f'qr_scanner ready (listening to /image_raw/compressed). Pyzbar={PYZBAR_AVAILABLE}, OpenCV={cv2.__version__}'
        )
        self._publish_status('initialized', 'Scanner initialized, waiting for arrival...')

    # -------------------------------------------------------------------------
    # Helper: Manual Image Conversion (NumPy 2.x compatible)
    # -------------------------------------------------------------------------
    def imgmsg_to_cv2(self, img_msg):
        """
        Manually convert a sensor_msgs/CompressedImage to an OpenCV image.
        """
        try:
            np_arr = np.frombuffer(img_msg.data, np.uint8)
            im = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            return im
        except Exception as e:
            self.get_logger().error(f"Failed to convert compressed image: {e}")
            return None

    # -------------------------------------------------------------------------
    # Callbacks for external topics
    # -------------------------------------------------------------------------

    def on_goal_name(self, msg: String):
        """Track the current destination name (e.g. Lab, R403, Cafeteria)."""
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
        """
        try:
            # Try to parse as JSON first: {"arrived": true, ...}
            st = json.loads(msg.data)
            arrived = bool(st.get('arrived', False))
        except Exception:
            # Fallback: check if message contains "succeeded" or "arrived"
            payload = (msg.data or "")
            arrived = 'arrived' in payload or 'succeeded' in payload

        if arrived and not self.scanning:
            # Check if destination is R403 - don't start scanning or timer at R403
            if self.current_destination and self.current_destination == 'R403':
                self.get_logger().info(
                    '🚫 Robot arrived at R403 - skipping QR scan (waiting for new order)'
                )
                self._publish_status(
                    'skipped',
                    'Arrived at R403 - scanner not started (waiting for new order)'
                )
            else:
                destination_str = (
                    f' at {self.current_destination}' if self.current_destination else ''
                )
                self.get_logger().info(
                    f'✅ Robot arrived at destination{destination_str} - starting QR scanner!'
                )

                self.start_scanning()

                # Schedule return to R403 after a fixed delay
                if not self._timer_scheduled:
                    try:
                        self._schedule_return_to_R403(self._return_delay)
                    except Exception as e:
                        self.get_logger().error(
                            f'Failed scheduling return to R403: {e}'
                        )

        elif not arrived and self.scanning:
            # Robot left destination - stop scanner
            self.get_logger().info('Robot left destination - stopping QR scanner')
            self.stop_scanning()

    def on_order_created(self, msg: String):
        """
        Parse order message and store order_id for verification.
        Also reset timer state.
        """
        try:
            # Parse order message
            if not msg.data:
                return
                
            order_data = {}
            try:
                order_data = json.loads(msg.data)
            except json.JSONDecodeError:
                # If simple string, maybe it's just the ID?
                if "order_id" in msg.data: 
                     # naive parse if not json
                     pass
            
            # Extract ID
            new_id = str(order_data.get('order_id', '')).strip()
            
            # If no ID in json, check if the message itself is the ID or contains it
            if not new_id and 'order_id' not in str(msg.data):
                 # Assume the whole message might be an ID if it's short? 
                 # Or just leave it empty if we can't find it.
                 pass
            
            if new_id:
                self.active_order_id = new_id
                self.get_logger().info(f"🆕 New Order Received! ID: {self.active_order_id}")
            else:
                # If we can't find an ID, we might just track that an order exists
                # For now let's hope for an ID
                self.get_logger().info("New order received (no ID found in payload)")

            # Timer logic
            if order_data or 'order_id' in str(msg.data):
                self._timer_scheduled = False
                if self._return_timer is not None:
                    try:
                        self._return_timer.cancel()
                    except Exception:
                        pass
                    self._return_timer = None
                self.get_logger().info('Order detected - timer state reset')
                
            # Allow immediately publishing verification if scanner active? No, wait for scan.
                
        except Exception as e:
            self.get_logger().debug(f'Error parsing order message: {e}')

    # -------------------------------------------------------------------------
    # Scanning logic
    # -------------------------------------------------------------------------

    def start_scanning(self):
        self.scanning = True
        self._frames_processed = 0
        self._publish_status('scanning', 'Scanner active (listening to camera topic)')

    def stop_scanning(self):
        self.scanning = False
        self._publish_status('stopped', f'Scanner stopped. Processed {self._frames_processed} frames.')
        self._frames_processed = 0

    def image_callback(self, msg):
        """
        Receive images from the camera. If scanning is active, process them.
        """
        if not self.scanning:
            return

        self._frames_processed += 1
        
        # Periodic logging
        if self._frames_processed % 30 == 0:
            self.get_logger().debug(f'Processing frame #{self._frames_processed}')

        # Convert to OpenCV image
        frame = self.imgmsg_to_cv2(msg)
        if frame is None:
            return

        # Decode QR
        try:
            found_qr = False
            decoded_data = None

            if PYZBAR_AVAILABLE:
                decoded = pyzbar.decode(frame)
                if decoded:
                    # Just take the first one
                    decoded_data = decoded[0].data.decode('utf-8')
                    found_qr = True
            else:
                # Fallback to OpenCV detector
                detector = cv2.QRCodeDetector()
                data, points, _ = detector.detectAndDecode(frame)
                if data:
                    decoded_data = data
                    found_qr = True

            if found_qr and decoded_data:
                self.get_logger().info('🔍 QR code detected! Processing...')
                self._process_scanned_data(decoded_data)
                
        except Exception as e:
            self.get_logger().error(f'Error during QR decoding: {e}')


    def _process_scanned_data(self, payload_str: str):
        """
        Handle the scanned QR data:
        1. Publish to main /robot/qr/scanned topic (existing).
        2. Verify against active_order_id.
        3. Publish verification status.
        """
        now = time.time()
        if now - self._last_scan_time < self._scan_cooldown:
            return

        try:
            # 1. Publish Scan
            out = String()
            out.data = json.dumps({
                'raw': payload_str,
                'timestamp': now
            })
            self.scan_pub.publish(out)
            self.get_logger().info(f'✅ QR code scanned: {payload_str}')
            
            # 2. Verification Logic
            is_verified = False
            # If we expected an ID, check it
            if self.active_order_id:
                if str(payload_str).strip() == str(self.active_order_id).strip():
                    is_verified = True
                    self.get_logger().info(f"🎉 Verification SUCCESS: QR '{payload_str}' matches Order '{self.active_order_id}'")
                else:
                    self.get_logger().warn(f"⚠️ Verification FAILED: QR '{payload_str}' != Order '{self.active_order_id}'")
            else:
                # If no active order ID known, assume any QR is valid? 
                # Or invalid? For this use case, let's allow it so user doesn't get stuck if they forgot to send order json.
                self.get_logger().info(f"Verification Info: No active order ID to match against. Assuming Valid.")
                is_verified = True

            # 3. Publish Verification Status (Triggers Like Detector)
            verified_msg = Bool()
            verified_msg.data = is_verified
            self.verified_pub.publish(verified_msg)
            
            self._publish_status(
                'qr_scanned', 
                f'QR: {payload_str} | Verified: {is_verified}'
            )
            
            self._last_scan_time = now
            
        except Exception as e:
            self.get_logger().error(f'Publishing scan/verification failed: {e}')

    def _publish_status(self, status: str, message: str):
        try:
            status_msg = String()
            status_data = {
                'status': status,
                'message': message,
                'scanning': self.scanning,
                'frames_processed': self._frames_processed,
                'timestamp': time.time()
            }
            status_msg.data = json.dumps(status_data)
            self.status_pub.publish(status_msg)
        except Exception as e:
            pass

    def _schedule_return_to_R403(self, delay: float = 30.0):
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
                    goal_msg.data = 'R403'
                    self.app_goal_pub.publish(goal_msg)
                    self.get_logger().info(f'Published return-to-R403 request')
                    self._timer_scheduled = False
                except Exception as e:
                    self.get_logger().error(f'Failed to publish return-to-R403: {e}')
                    self._timer_scheduled = False

            t = threading.Timer(delay, _do_return)
            t.daemon = True
            t.start()
            self._return_timer = t
            self._timer_scheduled = True

            self.get_logger().info(f'Scheduled return to R403 in {delay} seconds')
        except Exception as e:
            self.get_logger().error(f'Error scheduling return to R403: {e}')
            self._timer_scheduled = False


def main(args=None):
    rclpy.init(args=args)
    node = QrScanner()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
