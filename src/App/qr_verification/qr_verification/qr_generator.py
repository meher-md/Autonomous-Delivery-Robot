import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import os
import json
import time
import uuid
import base64
from io import BytesIO
from datetime import datetime
import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers import CircleModuleDrawer
from qrcode.image.styles.colormasks import SquareGradiantColorMask
from PIL import Image, ImageDraw

class QrGenerator(Node):
    def __init__(self):
        super().__init__('qr_generator')
        self.sub = self.create_subscription(String, '/app/qr/generate', self.on_generate, 10)
        self.pub = self.create_publisher(String, '/app/qr/image', 10)
        self.goal_name_sub = self.create_subscription(String, '/app/goal_name', self.on_goal_name, 10)
        self.previous_location = 'R403'
        self.current_location = 'R403'
        self.has_moved_from_R403 = False  
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.dashboard_dir = os.path.abspath(os.path.join(current_dir, '../../order_logger/dashboard'))
        self.order_history_file = os.path.join(self.dashboard_dir, 'order_history.txt')
        self.get_logger().info(f'qr_generator ready (order history: {self.order_history_file})')
    def on_goal_name(self, msg: String):
        """Track robot location changes to detect movement from R403."""
        try:
            goal_name = msg.data.strip()
            if not goal_name:
                return
            self.previous_location = self.current_location
            self.current_location = goal_name
            if self.previous_location and self.previous_location == 'R403' and self.current_location != 'R403':
                self.has_moved_from_R403 = True
                self.get_logger().info(f'Robot moved from R403 to {self.current_location} - QR generation now allowed')
            elif self.current_location == 'R403':
                self.has_moved_from_R403 = False
                self.get_logger().info('Robot returned to R403 - QR generation disabled until next departure')
        except Exception as e:
            self.get_logger().error(f'Error tracking goal name: {e}')
    def on_generate(self, msg: String):
        """Generate QR code only if robot has moved from R403 to another location."""
        try:
            req = json.loads(msg.data) if msg.data else {}
            address = req.get('address', 'Unknown')
            if not self.has_moved_from_R403:
                error_msg = 'QR code can only be generated after robot moves from R403 to another location. Please send robot to a destination first.'
                self.get_logger().warn(error_msg)
                error_resp = {
                    'error': error_msg,
                    'address': address
                }
                msg_out = String()
                msg_out.data = json.dumps(error_resp)
                self.pub.publish(msg_out)
                return
            order_id = str(uuid.uuid4())[:8]
            timestamp = int(time.time())
            payload = {
                'order_id': order_id,
                'address': address,
                'timestamp': timestamp
            }
            qr = qrcode.QRCode(version=None, box_size=12, border=6, error_correction=qrcode.constants.ERROR_CORRECT_H)
            #qr arg >> version = None >> auto detect version depending on data size
            #qr arg >> box_size = 12 >> size of each module in pixels
            #qr arg >> border = 6 >> border size in modules
            #qr arg >> error_correction = qrcode.constants.ERROR_CORRECT_H >> error correction level
            qr.add_data(json.dumps(payload))
            qr.make(fit=True)
            img = qr.make_image(image_factory=StyledPilImage,
                                module_drawer=CircleModuleDrawer(),
                                color_mask=SquareGradiantColorMask(
                                    back_color=(255, 255, 255),
                                    center_color=(0, 120, 215),
                                    edge_color=(50, 50, 50)
                                )).convert('RGBA')
            """try:
                logo_path = os.path.join(self.dashboard_dir, 'robot_logo_dashboard.png')
                if os.path.exists(logo_path):
                    logo = Image.open(logo_path).convert("RGBA")
                    qr_width, qr_height = img.size
                    logo_size = int(qr_width * 0.25)
                    logo = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
                    pos = ((qr_width - logo_size) // 2, (qr_height - logo_size) // 2)
                    padding = 10
                    bg_size = (logo_size + padding, logo_size + padding)
                    bg_pos = (pos[0] - padding // 2, pos[1] - padding // 2)
                    draw = ImageDraw.Draw(img)
                    draw.rectangle(
                        [bg_pos, (bg_pos[0] + bg_size[0], bg_pos[1] + bg_size[1])],
                        fill="white"
                    )
                    img.paste(logo, pos, logo)
                    img = img.convert("RGB")
                    self.get_logger().info("Logo embedded in QR code with white background")
            except Exception as e:
                self.get_logger().error(f"Failed to embed logo: {e}")"""
            
            # Create Mission Folder Structure
            try:
                now_dt = datetime.now()
                year_str = now_dt.strftime("%Y")
                month_str = now_dt.strftime("%B") 
                day_str = now_dt.strftime("%d")
                folder_name = f"mission_{order_id}"
                
                base_dir = os.path.expanduser("~/ws/mission_proof")
                mission_dir = os.path.join(base_dir, year_str, month_str, day_str, folder_name)
                os.makedirs(mission_dir, exist_ok=True)
                self.get_logger().info(f"📂 Created mission directory: {mission_dir}")
                
                filename = f"qr_{order_id}.png"
                filepath = os.path.join(mission_dir, filename)
                
                # Save the image directly to the mission folder
                img.save(filepath)
                
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
                self._log_to_order_history(order_id, address, timestamp, filename, filepath)
                self.get_logger().info(f"Generated QR for order {order_id} (saved to {filepath})")
            except Exception as e:
                self.get_logger().error(f"Failed to create mission folder or save QR: {e}")
                # Fallback to tmp if critical failure, to ensure app still gets a QR? 
                # For now, we assume this must succeed for the flow to work.
        except Exception as e:
            self.get_logger().error(f"QR generation failed: {e}")
    def _log_to_order_history(self, order_id: str, address: str, timestamp: int, filename: str, filepath: str):
        """Append order and QR code information to order history file."""
        try:
            dt = datetime.fromtimestamp(timestamp)
            timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            entry = f"""
{'='*80}
Order ID: {order_id}
Address: {address}
Timestamp: {timestamp_str} ({timestamp})
QR Code File: {filename}
QR Code Path: {filepath}
{'='*80}
"""
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
