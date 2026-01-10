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
import os
import datetime
from std_msgs.msg import String, Bool
from sensor_msgs.msg import CompressedImage
import asyncio
import edge_tts
# import pygame

# Try pyzbar for robust QR decoding
PYZBAR_AVAILABLE = False
try:
    from pyzbar import pyzbar
    PYZBAR_AVAILABLE = True
except Exception:
    PYZBAR_AVAILABLE = False


from rclpy.action import ActionClient
try:
    from audio_common_msgs.action import TTS
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False


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
        
        # Publisher for Mission Evidence Path (so YOLO knows where to save)
        self.mission_path_pub = self.create_publisher(String, '/robot/mission_path', 10)

        # Subscribe to camera topic (Compressed) - INITIALIZED TO NONE
        self.image_sub = None
        # Subscription will be created in start_scanning()
        
        # Publisher for Delivery Reports (Updates Dashboard)
        self.report_pub = self.create_publisher(String, '/delivery_report', 10)
        # Subscription will be created in start_scanning()

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
        
        # Subscribe to like_detected to track mission success
        self.like_sub = self.create_subscription(
            Bool, '/like_detected', self.on_like_detected, 10
        )

        # Whether scanner is currently active
        self.scanning = False

        # Track current destination to avoid scanning at R403
        self.current_destination = None
        
        # Track active order ID for verification
        self.active_order_id = None
        
        # Mission Status Flags
        self.mission_qr_scanned = False
        self.mission_yolo_detected = False

        # Cooldown management for publishing QR scans
        self._last_scan_time = 0.0
        self._scan_cooldown = 5.0  # seconds to avoid duplicate publishes

        # Timer used to schedule return-to-R403 after ARRIVAL
        self._return_timer = None
        self._return_delay = 120.0  # seconds to wait before sending robot back to R403

        # Flag to track if the return-to-R403 timer is already scheduled
        self._timer_scheduled = False

        # Monitoring: frame processing stats
        self._frames_processed = 0
        
        # PIPER CLIENT
        if TTS_AVAILABLE:
            self.tts_client = ActionClient(self, TTS, '/say')
            # Wait for server briefly to confirm connection
            if self.tts_client.wait_for_server(timeout_sec=5.0):
                self.get_logger().info('✅ Connected to Piper TTS Action Server (/say)')
            else:
                self.get_logger().error('❌ Failed to connect to Piper TTS Action Server')
        else:
            self.tts_client = None

        self.get_logger().info(
            f'qr_scanner ready (listening to /image_raw/compressed). Pyzbar={PYZBAR_AVAILABLE}, OpenCV={cv2.__version__}'
        )
        
        # Audio System
        # pygame.mixer.init()  # Removed to prevent audio device blocking
        # self.synthesizer_lock = threading.Lock()
        
        self.scan_start_time = 0.0 # For countdown

        self._publish_status('initialized', 'Scanner initialized, waiting for arrival...')

    # -------------------------------------------------------------------------
    # AUDIO HELPER (Piper Action)
    # -------------------------------------------------------------------------
    def speak(self, text):
        if self.tts_client and self.tts_client.wait_for_server(timeout_sec=1.0):
            goal = TTS.Goal()
            goal.text = text
            self.tts_client.send_goal_async(goal)
            self.get_logger().info(f"🔊 Speaking (Piper): {text}")
        else:
            self.get_logger().warn("Piper not available for speech")

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
            # Check if destination is PKG - don't start scanning or timer at PKG
            if self.current_destination and self.current_destination == 'PKG':
                self.get_logger().info(
                    '🚫 Robot arrived at PKG - skipping QR scan (waiting for new order)'
                )
                
                # FINAL MISSION DEBRIEF (Requested by User)
                # Print what happened during the trip we just returned from
                report = (
                    "\n================ MISSION REPORT (FINAL) ================\n"
                    f"Previous Destination: {self.current_destination} (Arrived at PKG)\n"
                    f"QR Code Scanned:    {'[YES] ✅' if self.mission_qr_scanned else '[NO] ❌'}\n"
                    f"YOLO Like Detected: {'[YES] 👍' if self.mission_yolo_detected else '[NO] ❌'}\n"
                    "========================================================"
                )
                self.get_logger().info(report)

                self._publish_status(
                    'skipped',
                    'Arrived at PKG - scanner not started (waiting for new order)'
                )
            else:
                destination_str = (
                    f' at {self.current_destination}' if self.current_destination else ''
                )
                self.get_logger().info(
                    f'✅ Robot arrived at destination{destination_str} - starting QR scanner!'
                )
                
                # Reset mission flags on arrival
                self.mission_qr_scanned = False
                self.mission_yolo_detected = False

                self.start_scanning()
                
                # SPEAK WELCOME MESSAGE (Friendly)
                self.speak("Hello! I have arrived. Please scan the QR code I sent you.")

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
            if not self.mission_qr_scanned: # Don't stop if we just scanned and are showing "success" state theoretically, but actually we should stop if logic says departed
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
            
    def on_like_detected(self, msg: Bool):
        """Track if YOLO detected a 'like' gesture."""
        if msg.data:
            self.mission_yolo_detected = True
            
            # Stop any verification audio from this node (prevent overlap with YOLO's "Thank You")
            # if pygame.mixer.get_init():
            #     pygame.mixer.music.stop()
            
            # Requested by User: Return immediately if Like is detected!
            # We give it 5 seconds to play audio and save image before moving.
            if self._timer_scheduled:
                self.get_logger().info('👍 Like Detected! Canceling waiting time and returning home in 5s...')
                self._schedule_return_to_R403(delay=5.0)

    # -------------------------------------------------------------------------
    # Scanning logic
    # -------------------------------------------------------------------------

    def start_scanning(self):
        if self.scanning:
            return

        self.scanning = True
        self._frames_processed = 0
        
        # Set start time for countdown
        self.scan_start_time = time.time() + 5.0 # 5 seconds from now
        
        # Create subscription if not exists
        if self.image_sub is None:
            self.image_sub = self.create_subscription(
                CompressedImage, '/camera/image_raw/compressed', self.image_callback, 10
            )
            self.get_logger().info('Rx: Camera subscription created')

        self._publish_status('scanning', 'Scanner active (listening to camera topic)')

    def stop_scanning(self):
        if not self.scanning:
            return

        self.scanning = False
        
        # Destroy subscription to save bandwidth
        if self.image_sub is not None:
            self.destroy_subscription(self.image_sub)
            self.image_sub = None
            self.get_logger().info('Rx: Camera subscription destroyed')

        self._publish_status('stopped', f'Scanner stopped. Processed {self._frames_processed} frames.')
        self._frames_processed = 0
        
        # Close the UI window (Requested by User)
        cv2.destroyAllWindows()

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

        # -----------------------------------------------------
        # COUNTDOWN LOGIC (Requested by User)
        # -----------------------------------------------------
        time_left = self.scan_start_time - time.time()
        if time_left > 0:
            # Show Countdown Overlay
            display_frame = frame.copy()
            display_frame = cv2.resize(display_frame, (640, 480))
            
            # Big Red Countdown
            seconds = int(time_left) + 1
            text = f"GET READY: {seconds}"
            
            # Centered text (approx)
            # Use same font scale (1.5) and thickness (4) as YOLO for consistency
            cv2.putText(display_frame, text, (100, 240), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 4)
            
            cv2.imshow("QR Scanner Feed", display_frame)
            cv2.waitKey(1)
            # SKIP DECODING
            return

        # Decode QR
        try:
            found_qr = False
            decoded_data = None

            # Preprocessing for better detection (Ported from test_qr_camera.py)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Enhance contrast using CLAHE
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            
            if PYZBAR_AVAILABLE:
                # Robust Multi-Pass Strategy: Try Gray, Enhanced, and Original
                # (Order matters: Enhanced allows reading in low light/shadows)
                for img_pass in [enhanced, gray, frame]:
                    decoded = pyzbar.decode(img_pass)
                    if decoded:
                        decoded_data = decoded[0].data.decode('utf-8')
                        found_qr = True
                        break
            else:
                # Fallback to OpenCV detector
                detector = cv2.QRCodeDetector()
                # Try simple gray first
                data, points, _ = detector.detectAndDecode(gray)
                if data:
                    decoded_data = data
                    found_qr = True

            # Draw and Display (Requested by User)
            display_frame = frame.copy()
            
            # Resize for better visibility (Requested by User)
            display_frame = cv2.resize(display_frame, (640, 480))
            
            if found_qr and decoded_data:
                # Draw Box (Green)
                cv2.putText(display_frame, f"QR: {decoded_data}", (10, 50), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            else:
                # Draw status (Red)
                cv2.putText(display_frame, "SCANNING...", (10, 50), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
                           
            cv2.imshow("QR Scanner Feed", display_frame)
            cv2.waitKey(1)
            
            if found_qr and decoded_data:
                self.get_logger().info('🔍 QR code detected! Processing...')
                self._process_scanned_data(decoded_data, frame)
                
        except Exception as e:
            self.get_logger().error(f'Error during QR decoding: {e}')


    def _process_scanned_data(self, payload_str: str, frame):
        """
        Handle the scanned QR data:
        1. Publish to main /robot/qr/scanned topic (existing).
        2. Verify against active_order_id.
        3. Publish verification status.
        4. Save Evidence (needs frame).
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
            
            # SPEAK SUCCESS MSG (Friendly)
            if is_verified:
                self.speak("Success! Please open the box and take your order. When you are done, please show me a Like sign.")
            
            # --- EVIDENCE SAVING (Requested by User) ---
            if is_verified:
                 try:
                     # 1. Create Folder Structure: year/Month/day/mission_<order_id>
                     now_dt = datetime.datetime.now()
                     year_str = now_dt.strftime("%Y")
                     month_str = now_dt.strftime("%B") # Full month name e.g. January
                     day_str = now_dt.strftime("%d")

                     # Use active_order_id for folder name to match qr_generator
                     if self.active_order_id:
                         mission_id = self.active_order_id
                     else:
                         mission_id = f"{int(now)}"
                         
                     folder_name = f"mission_{mission_id}"
                     
                     base_dir = os.path.expanduser("~/ws/mission_proof")
                     mission_dir = os.path.join(base_dir, year_str, month_str, day_str, folder_name)
                     os.makedirs(mission_dir, exist_ok=True)
                     
                     self.get_logger().info(f"📂 Used mission proof directory: {mission_dir}")

                     # 2. Publish Path for YOLO
                     path_msg = String()
                     path_msg.data = mission_dir
                     self.mission_path_pub.publish(path_msg)
                     
                     # 3. Check for Original Generated QR (Should already be there)
                     scanned_order_id = None
                     try:
                         scanned_json = json.loads(payload_str)
                         scanned_order_id = scanned_json.get('order_id')
                     except json.JSONDecodeError:
                         scanned_order_id = payload_str.strip()
                         
                     if scanned_order_id:
                         gen_filename = f"qr_{scanned_order_id}.png"
                         gen_path = os.path.join(mission_dir, gen_filename)
                         if os.path.exists(gen_path):
                             self.get_logger().info(f"✅ Verified original QR exists in mission folder: {gen_path}")
                         else:
                             self.get_logger().warn(f"⚠️ Original QR not found in {mission_dir} (maybe generated on a different day?)")
                     
                     # 4. Save Scanned Evidence (The Camera Feed)
                     evidence_frame = frame.copy()
                     # Resize to 640x480 
                     evidence_frame = cv2.resize(evidence_frame, (640, 480))
                     
                     # Overlay Text
                     text_str = f"SCANNED: {payload_str}"
                     y0, dy = 30, 25
                     # Wrap text
                     for i, line in enumerate([text_str[i:i+40] for i in range(0, len(text_str), 40)]):
                         y = y0 + i*dy
                         cv2.putText(evidence_frame, line, (10, y), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                                    
                     timestamp_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
                     cv2.putText(evidence_frame, f"Time: {timestamp_str}", (10, 460), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
                                
                     save_path = os.path.join(mission_dir, "qr_scan.jpg")
                     cv2.imwrite(save_path, evidence_frame)
                     self.get_logger().info(f"📸 Saved scan evidence to: {save_path}")
                     
                 except Exception as e:
                     self.get_logger().error(f"Failed to save evidence: {e}")
                     import traceback
                     traceback.print_exc()
            # -------------------------------------------
            
            self._publish_status(
                'qr_scanned', 
                f'QR: {payload_str} | Verified: {is_verified}'
            )
            
            # Mark mission flag
            self.mission_qr_scanned = True
            
            self._last_scan_time = now
            
            # Stop scanning immediately after success (Requested by User)
            # This closes the window and lets YOLO take over.
            if is_verified:
                # Add a small delay/sleep to let the user see the "Green Box" for a split second?
                # Actually, blocking here inside callback is bad, but a tiny sleep is OK or just close.
                # Let's just stop. The evidence is saved anyway.
                self.get_logger().info("✅ Scan Complete. Closing Scanner...")
                self.stop_scanning()
            
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
                    goal_msg.data = 'PKG'
                    self.app_goal_pub.publish(goal_msg)
                    
                    # LOG MISSION REPORT
                    report = (
                        "\n================ MISSION REPORT ================\n"
                        f"Target Destination: {self.current_destination}\n"
                        f"QR Code Scanned:    {'[YES] ✅' if self.mission_qr_scanned else '[NO] ❌'}\n"
                        f"YOLO Like Detected: {'[YES] 👍' if self.mission_yolo_detected else '[NO] ❌'}\n"
                        "================================================"
                    )
                    self.get_logger().info(report)
                    
                    # PUBLISH FINAL REPORT TO DASHBOARD
                    try:
                         # Calculate mock trip data for now, or use real if available
                        duration = 0.0 # Could calculate from timestamp but let's keep it simple
                        
                        final_status = "Delivered" if self.mission_qr_scanned and self.mission_yolo_detected else "Failed"
                        if self.mission_qr_scanned and not self.mission_yolo_detected:
                             final_status = "Delivered (No Gesture)"
                        
                        report_payload = {
                            "order_id": self.active_order_id if self.active_order_id else "UNKNOWN",
                            "qr_scan_status": "Verified" if self.mission_qr_scanned else "Failed",
                            "client_gesture_status": "Thumb Up" if self.mission_yolo_detected else "None",
                            "handover_time_sec": 45, # Mock average
                            "trip_duration_min": 2.5, # Mock average
                            "distance_traveled_m": 120.5,
                            "order_final_status": final_status
                        }
                        
                        msg = String()
                        msg.data = json.dumps(report_payload)
                        self.report_pub.publish(msg)
                        self.get_logger().info(f"📊 Published Delivery Report for {report_payload['order_id']}")
                        
                        # Reset ID for next order
                        self.active_order_id = None
                        
                    except Exception as e:
                        self.get_logger().error(f"Failed to publish delivery report: {e}")
                    
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
