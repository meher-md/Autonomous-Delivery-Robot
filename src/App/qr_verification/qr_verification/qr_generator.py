#!/usr/bin/env python3
import os
import json
import time
import uuid
import base64
from io import BytesIO
from datetime import datetime

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

import qrcode

class QrGenerator(Node):
    def __init__(self):
        super().__init__('qr_generator')
        self.sub = self.create_subscription(String, '/app/qr/generate', self.on_generate, 10)
        self.pub = self.create_publisher(String, '/app/qr/image', 10)
        # Subscribe to goal_name to track location changes
        self.goal_name_sub = self.create_subscription(String, '/app/goal_name', self.on_goal_name, 10)
        # Track robot location to ensure QR is only generated when moving from R403
        # Assume robot starts at R403 (stock location)
        self.previous_location = 'R403'
        self.current_location = 'R403'
        self.has_moved_from_R403 = False  # Flag to track if robot has moved from R403
        
        # Order history file in main project folder
        self.project_root = os.path.expanduser('~/ws')
        self.order_history_file = os.path.join(self.project_root, 'order_history.txt')
        
        self.get_logger().info(f'qr_generator ready (order history: {self.order_history_file})')

    def on_goal_name(self, msg: String):
        """Track robot location changes to detect movement from R403."""
        try:
            goal_name = msg.data.strip()
            if not goal_name:
                return
            
            # Update location tracking
            self.previous_location = self.current_location
            self.current_location = goal_name
            
            # Check if robot has moved from R403 to another location
            if self.previous_location and self.previous_location == 'R403' and self.current_location != 'R403':
                self.has_moved_from_R403 = True
                self.get_logger().info(f'Robot moved from R403 to {self.current_location} - QR generation now allowed')
            elif self.current_location == 'R403':
                # Reset flag when robot returns to R403
                self.has_moved_from_R403 = False
                self.get_logger().info('Robot returned to R403 - QR generation disabled until next departure')
        except Exception as e:
            self.get_logger().error(f'Error tracking goal name: {e}')

    def on_generate(self, msg: String):
        """Generate QR code only if robot has moved from R403 to another location."""
        try:
            req = json.loads(msg.data) if msg.data else {}
            address = req.get('address', 'Unknown')
            
            # Check if robot has moved from R403
            if not self.has_moved_from_R403:
                error_msg = 'QR code can only be generated after robot moves from R403 to another location. Please send robot to a destination first.'
                self.get_logger().warn(error_msg)
                # Publish error response
                error_resp = {
                    'error': error_msg,
                    'address': address
                }
                msg_out = String()
                msg_out.data = json.dumps(error_resp)
                self.pub.publish(msg_out)
                return
            
            # create a unique payload for this order
            order_id = str(uuid.uuid4())[:8]
            timestamp = int(time.time())
            payload = {
                'order_id': order_id,
                'address': address,
                'timestamp': timestamp
            }
            
            # generate QR image
            # Custom Color: Dark Blue (R=0, G=74, B=173) to match App Theme
            qr = qrcode.QRCode(version=1, box_size=12, border=4, error_correction=qrcode.constants.ERROR_CORRECT_H)
            qr.add_data(json.dumps(payload))
            qr.make(fit=True)
            
            # Create QR with Blue color and White background
            img = qr.make_image(fill_color="#004AAD", back_color="white").convert('RGBA')

            # Embed Logo
            try:
                logo_path = os.path.expanduser('~/ws/src/App/order_logger/dashboard/robot_logo_dashboard.png')
                if os.path.exists(logo_path):
                    from PIL import Image, ImageDraw
                    logo = Image.open(logo_path).convert("RGBA")
                    
                    # Calculate logo size (25% of QR width)
                    qr_width, qr_height = img.size
                    logo_size = int(qr_width * 0.25)
                    logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
                    
                    # Calculate position to center the logo
                    pos = ((qr_width - logo_size) // 2, (qr_height - logo_size) // 2)
                    
                    # Create a white background box for the logo (to make it distinct like the example)
                    # Size includes a small padding
                    padding = 10
                    bg_size = (logo_size + padding, logo_size + padding)
                    bg_pos = (pos[0] - padding // 2, pos[1] - padding // 2)
                    
                    # Draw White Rectangle (Background)
                    draw = ImageDraw.Draw(img)
                    draw.rectangle(
                        [bg_pos, (bg_pos[0] + bg_size[0], bg_pos[1] + bg_size[1])],
                        fill="white"
                    )
                    
                    # Paste logo on top of the white background
                    img.paste(logo, pos, logo)
                    
                    # Convert back to RGB
                    img = img.convert("RGB")
                    self.get_logger().info("Logo embedded in QR code with white background")
            except Exception as e:
                self.get_logger().error(f"Failed to embed logo: {e}")
            
            # Create Mission Folder Structure: year/Month/day/mission_<order_id>
            now = datetime.fromtimestamp(timestamp)
            year_str = now.strftime("%Y")
            month_str = now.strftime("%B")
            day_str = now.strftime("%d")
            mission_folder = f"mission_{order_id}"
            
            base_dir = os.path.expanduser("~/ws/mission_proof")
            mission_dir = os.path.join(base_dir, year_str, month_str, day_str, mission_folder)
            os.makedirs(mission_dir, exist_ok=True)
            
            # save to file directly in mission folder
            filename = f"qr_{order_id}.png"
            filepath = os.path.join(mission_dir, filename)
            img.save(filepath)
            
            # prepare base64 PNG
            bio = BytesIO()
            img.save(bio, format='PNG')
            b64_png = base64.b64encode(bio.getvalue()).decode('utf-8')
            
            resp = {
                'qr_b64_png': b64_png,
                'payload': payload,
                'filename': filename
            }
            msg_out = String()
            msg_out.data = json.dumps(resp)
            self.pub.publish(msg_out)
            
            # Log to order history file
            self._log_to_order_history(order_id, address, timestamp, filename, filepath)
            
            self.get_logger().info(f"Generated QR for order {order_id} (saved to {filepath})")
        except Exception as e:
            self.get_logger().error(f"QR generation failed: {e}")

    def _log_to_order_history(self, order_id: str, address: str, timestamp: int, filename: str, filepath: str):
        """Append order and QR code information to order history file."""
        try:
            dt = datetime.fromtimestamp(timestamp)
            timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            
            # Format entry
            entry = f"""
{'='*80}
Order ID: {order_id}
Address: {address}
Timestamp: {timestamp_str} ({timestamp})
QR Code File: {filename}
QR Code Path: {filepath}
{'='*80}
"""
            
            # Append to history file
            with open(self.order_history_file, 'a', encoding='utf-8') as f:
                f.write(entry)
            
            self.get_logger().info(f'Order {order_id} logged to history file')
        except Exception as e:
            self.get_logger().error(f'Failed to log order to history: {e}')

def main(args=None):
    rclpy.init(args=args)
    node = QrGenerator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
