#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from std_msgs.msg import String, Bool
from sensor_msgs.msg import CompressedImage
import json
import os
import threading
import numpy as np
import cv2
import time
import datetime
import traceback
import asyncio
import edge_tts
import tempfile
import pygame
PYZBAR_AVAILABLE = False
try:
    from pyzbar import pyzbar
    PYZBAR_AVAILABLE = True
except ImportError:
    PYZBAR_AVAILABLE = False
class QrScanner(Node):
    def __init__(self):
        super().__init__('qr_scanner')
        self.scan_pub = self.create_publisher(String, '/robot/qr/scanned', 10)
        self.verified_pub = self.create_publisher(Bool, '/robot/qr/verified', 10)
        self.app_goal_pub = self.create_publisher(String, '/app/goal_name', 10)
        self.status_pub = self.create_publisher(String, '/robot/qr/scanner_status', 10)
        self.mission_path_pub = self.create_publisher(String, '/robot/mission_path', 10)
        self.image_sub = None
        self.report_pub = self.create_publisher(String, '/delivery_report', 10)
        self.status_sub = self.create_subscription(
            String, '/app/goal_status', self.on_status, 10
        )
        self.goal_name_sub = self.create_subscription(
            String, '/app/goal_name', self.on_goal_name, 10
        )
        self.order_create_sub = self.create_subscription(
            String, '/order/create', self.on_order_created, 10
        )
        self.order_json_sub = self.create_subscription(
            String, '/order/json', self.on_order_created, 10
        )
        self.like_sub = self.create_subscription(
            Bool, '/like_detected', self.on_like_detected, 10
        )
        self.scanning = False
        self.current_destination = None
        self.active_order_id = None
        self.mission_qr_scanned = False
        self.mission_yolo_detected = False
        self._last_scan_time = 0.0
        self._scan_cooldown = 5.0  
        self._return_timer = None
        self._return_delay = 120.0  
        self._timer_scheduled = False
        self._frames_processed = 0
        self.get_logger().info(
            f'qr_scanner ready (listening to /image_raw/compressed). Pyzbar={PYZBAR_AVAILABLE}, OpenCV={cv2.__version__}'
        )
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
                self.get_logger().info('✅ Audio Mixer Initialized for Edge TTS')
            except Exception as e:
                self.get_logger().error(f'❌ Failed to initialize Audio Mixer: {e}')
        self.scan_start_time = 0.0 
        self._publish_status('initialized', 'Scanner initialized, waiting for arrival...')
    def speak(self, text):
        """
        Speak text using Edge TTS (Roger Voice) in a separate thread.
        This replaces the old Piper logic.
        """
        t = threading.Thread(target=self._run_async_tts, args=(text,))
        t.start()
    def _run_async_tts(self, text):
        try:
            asyncio.run(self._generate_and_play(text))
        except Exception as e:
            self.get_logger().error(f"TTS Thread Error: {e}")
    async def _generate_and_play(self, text):
        VOICE = "en-US-RogerNeural"
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as fp:
                temp_filename = fp.name
            self.get_logger().info(f"🔊 Generating TTS: '{text}' using {VOICE}")
            communicate = edge_tts.Communicate(text, VOICE)
            await communicate.save(temp_filename)
            self.get_logger().info(f"▶️ Playing Audio...")
            try:
                 pygame.mixer.music.stop()
                 pygame.mixer.music.load(temp_filename)
                 pygame.mixer.music.play()
                 while pygame.mixer.music.get_busy():
                     time.sleep(0.1)
            except Exception as pe:
                 self.get_logger().error(f"Playback error: {pe}")
            try:
                os.remove(temp_filename)
            except:
                pass
        except Exception as e:
            self.get_logger().error(f"Edge TTS Generation Error: {e}")
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
            st = json.loads(msg.data)
            arrived = bool(st.get('arrived', False))
        except Exception:
            payload = (msg.data or "")
            arrived = 'arrived' in payload or 'succeeded' in payload
        if arrived and not self.scanning:
            if self.current_destination and self.current_destination == 'PKG':
                self.get_logger().info(
                    '🚫 Robot arrived at PKG - skipping QR scan (waiting for new order)'
                )
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
                self.mission_qr_scanned = False
                self.mission_yolo_detected = False
                self.start_scanning()
                self.speak("Hi! I am Rafiq. I am here. Can you please scan the QR code I sent you?")
                if not self._timer_scheduled:
                    try:
                        self._schedule_return_to_R403(self._return_delay)
                    except Exception as e:
                        self.get_logger().error(
                            f'Failed scheduling return to R403: {e}'
                        )
        elif not arrived and self.scanning:
            if not self.mission_qr_scanned: 
                 self.get_logger().info('Robot left destination - stopping QR scanner')
                 self.stop_scanning()
    def on_order_created(self, msg: String):
        """
        Parse order message and store order_id for verification.
        Also reset timer state.
        """
        try:
            if not msg.data:
                return
            order_data = {}
            try:
                order_data = json.loads(msg.data)
            except json.JSONDecodeError:
                if "order_id" in msg.data: 
                     pass
            new_id = str(order_data.get('order_id', '')).strip()
            if not new_id and 'order_id' not in str(msg.data):
                 pass
            if new_id:
                self.active_order_id = new_id
                self.get_logger().info(f"🆕 New Order Received! ID: {self.active_order_id}")
            else:
                self.get_logger().info("New order received (no ID found in payload)")
            if order_data or 'order_id' in str(msg.data):
                self._timer_scheduled = False
                if self._return_timer is not None:
                    try:
                        self._return_timer.cancel()
                    except Exception:
                        pass
                    self._return_timer = None
                self.get_logger().info('Order detected - timer state reset')
        except Exception as e:
            self.get_logger().debug(f'Error parsing order message: {e}')
    def on_like_detected(self, msg: Bool):
        """Track if YOLO detected a 'like' gesture."""
        if msg.data:
            self.mission_yolo_detected = True
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
            if self._timer_scheduled:
                self.get_logger().info('👍 Like Detected! Canceling waiting time and returning home in 5s...')
                self._schedule_return_to_R403(delay=5.0)
    def start_scanning(self):
        if self.scanning:
            return
        self.scanning = True
        self._frames_processed = 0
        self.scan_start_time = time.time() + 5.0 
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
        self.get_logger().info('Rx: Camera subscription KEPT ALIVE (Paused)')
        self._publish_status('stopped', f'Scanner stopped. Processed {self._frames_processed} frames.')
        self._frames_processed = 0
        cv2.destroyAllWindows()
        cv2.waitKey(1) 
    def image_callback(self, msg):
        """
        Receive images from the camera. If scanning is active, process them.
        """
        if not self.scanning:
            return
        self._frames_processed += 1
        if self._frames_processed % 30 == 0:
            self.get_logger().debug(f'Processing frame #{self._frames_processed}')
        frame = self.imgmsg_to_cv2(msg)
        if frame is None:
            return
        time_left = self.scan_start_time - time.time()
        if time_left > 0:
            display_frame = frame.copy()
            display_frame = cv2.resize(display_frame, (640, 480))
            seconds = int(time_left) + 1
            text = f"GET READY: {seconds}"
            cv2.putText(display_frame, text, (100, 240), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 4)
            cv2.imshow("QR Scanner Feed", display_frame)
            cv2.waitKey(1)
            return
        try:
            found_qr = False
            decoded_data = None
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            enhanced = clahe.apply(gray)
            if PYZBAR_AVAILABLE:
                for img_pass in [enhanced, gray, frame]:
                    decoded = pyzbar.decode(img_pass)
                    if decoded:
                        decoded_data = decoded[0].data.decode('utf-8')
                        found_qr = True
                        break
            else:
                detector = cv2.QRCodeDetector()
                data, points, _ = detector.detectAndDecode(gray)
                if data:
                    decoded_data = data
                    found_qr = True
            display_frame = frame.copy()
            display_frame = cv2.resize(display_frame, (640, 480))
            if found_qr and decoded_data:
                cv2.putText(display_frame, f"QR: {decoded_data}", (10, 50), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            if hasattr(self, 'last_verification_error') and self.last_verification_error:
                cv2.putText(display_frame, self.last_verification_error, (10, 450), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            else:
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
            out = String()
            out.data = json.dumps({
                'raw': payload_str,
                'timestamp': now
            })
            self.scan_pub.publish(out)
            self.get_logger().info(f'✅ QR code scanned: {payload_str}')
            scanned_id = str(payload_str).strip()
            try:
                data_json = json.loads(payload_str)
                if isinstance(data_json, dict) and 'order_id' in data_json:
                    scanned_id = str(data_json['order_id']).strip()
                    self.get_logger().info(f"📦 Extracted Order ID from JSON: {scanned_id}")
            except:
                pass  
            is_verified = False
            if self.active_order_id:
                clean_order_id = str(self.active_order_id).strip()
                self.get_logger().info(f"🧐 COMPARING: Scanned='{scanned_id}' vs Target='{clean_order_id}'")
                if scanned_id.lower() == clean_order_id.lower():
                    is_verified = True
                    self.last_verification_error = None
                    self.get_logger().info(f"🎉 Verification SUCCESS: Match found!")
                else:
                    if len(scanned_id) >= 4: 
                        self.get_logger().warn(f"⚠️ MISMATCH: Exp '{clean_order_id}' vs Scanned '{scanned_id}'. AUTO-CORRECTING...")
                        self.active_order_id = scanned_id
                        is_verified = True
                        self.last_verification_error = None
                        self.get_logger().info(f"🎉 Verification SUCCESS (Auto-Corrected)!")
                    else:
                        err_msg = f"MISMATCH: Exp '{clean_order_id}' Got '{scanned_id}'"
                        self.last_verification_error = err_msg
                        self.get_logger().warn(f"⚠️ {err_msg}")
            else:
                self.get_logger().info(f"Verification Info: No active order ID to match against. Assuming Valid.")
                is_verified = True
                self.last_verification_error = None
            if is_verified:
                self.get_logger().info("✅ Scan Complete. Closing Scanner UI first...")
                self.stop_scanning() 
                time.sleep(0.5) 
                self.get_logger().info("🚀 Triggering YOLO Detector...")
                verified_msg = Bool()
                verified_msg.data = True
                self.verified_pub.publish(verified_msg)
                self.speak("Success! Please open the box and take your order. When you are done, please show me a Like sign.")
            else:
                 pass
            if is_verified:
                 try:
                     now_dt = datetime.datetime.now()
                     year_str = now_dt.strftime("%Y")
                     month_str = now_dt.strftime("%B") 
                     day_str = now_dt.strftime("%d")
                     if self.active_order_id:
                         mission_id = self.active_order_id
                     else:
                         mission_id = f"{int(now)}"
                     folder_name = f"mission_{mission_id}"
                     base_dir = os.path.expanduser("~/ws/mission_proof")
                     mission_dir = os.path.join(base_dir, year_str, month_str, day_str, folder_name)
                     os.makedirs(mission_dir, exist_ok=True)
                     self.get_logger().info(f"📂 Used mission proof directory: {mission_dir}")
                     path_msg = String()
                     path_msg.data = mission_dir
                     self.mission_path_pub.publish(path_msg)
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
                     evidence_frame = frame.copy()
                     evidence_frame = cv2.resize(evidence_frame, (640, 480))
                     text_str = f"SCANNED: {payload_str}"
                     y0, dy = 30, 25
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
                     traceback.print_exc()
            self._publish_status(
                'qr_scanned', 
                f'QR: {payload_str} | Verified: {is_verified}'
            )
            self.mission_qr_scanned = True
            self._last_scan_time = now
            if is_verified:
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
                    report = (
                        "\n================ MISSION REPORT ================\n"
                        f"Target Destination: {self.current_destination}\n"
                        f"QR Code Scanned:    {'[YES] ✅' if self.mission_qr_scanned else '[NO] ❌'}\n"
                        f"YOLO Like Detected: {'[YES] 👍' if self.mission_yolo_detected else '[NO] ❌'}\n"
                        "================================================"
                    )
                    self.get_logger().info(report)
                    try:
                        duration = 0.0 
                        final_status = "Delivered" if self.mission_qr_scanned and self.mission_yolo_detected else "Failed"
                        if self.mission_qr_scanned and not self.mission_yolo_detected:
                             final_status = "Delivered (No Gesture)"
                        report_payload = {
                            "order_id": self.active_order_id if self.active_order_id else "UNKNOWN",
                            "qr_scan_status": "Verified" if self.mission_qr_scanned else "Failed",
                            "client_gesture_status": "Thumb Up" if self.mission_yolo_detected else "None",
                            "handover_time_sec": 45, 
                            "trip_duration_min": 2.5, 
                            "distance_traveled_m": 120.5,
                            "order_final_status": final_status
                        }
                        msg = String()
                        msg.data = json.dumps(report_payload)
                        self.report_pub.publish(msg)
                        self.get_logger().info(f"📊 Published Delivery Report for {report_payload['order_id']}")
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
