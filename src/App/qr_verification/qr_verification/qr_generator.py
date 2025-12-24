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
        self.qr_dir = os.path.expanduser(os.path.join('~/ws', 'generated_qr'))
        os.makedirs(self.qr_dir, exist_ok=True)
        
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
            qr = qrcode.QRCode(version=1, box_size=10, border=4)
            qr.add_data(json.dumps(payload))
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            # save to file
            filename = f"qr_{order_id}.png"
            filepath = os.path.join(self.qr_dir, filename)
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
            
            self.get_logger().info(f"Generated QR for order {order_id} (saved {filepath})")
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
