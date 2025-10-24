#!/usr/bin/env python3
import os
import json
import time
import uuid
import base64
from io import BytesIO

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

import qrcode

class QrGenerator(Node):
    def __init__(self):
        super().__init__('qr_generator')
        self.sub = self.create_subscription(String, '/app/qr/generate', self.on_generate, 10)
        self.pub = self.create_publisher(String, '/app/qr/image', 10)
        self.qr_dir = os.path.expanduser(os.path.join('~/ws', 'generated_qr'))
        os.makedirs(self.qr_dir, exist_ok=True)
        self.get_logger().info('qr_generator ready')

    def on_generate(self, msg: String):
        try:
            req = json.loads(msg.data) if msg.data else {}
            address = req.get('address', 'Unknown')
            # create a unique payload for this order
            order_id = str(uuid.uuid4())[:8]
            payload = {
                'order_id': order_id,
                'address': address,
                'timestamp': int(time.time())
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
            self.get_logger().info(f"Generated QR for order {order_id} (saved {filepath})")
        except Exception as e:
            self.get_logger().error(f"QR generation failed: {e}")

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
