import rclpy
from rclpy.node import Node
from delivery_qr.srv import GenerateQr

import qrcode
import base64
from io import BytesIO

class QrGenerator(Node):
    def __init__(self):
        super().__init__('qr_generator')
        self.srv = self.create_service(GenerateQr, 'generate_qr', self.generate_qr_callback)
        self.get_logger().info("✅ QR Generator Service Ready: /generate_qr")

    def generate_qr_callback(self, request, response):
        try:
            payload = f"OrderID:{request.order_id}|Phone:{request.phone}|Address:{request.address}"
            img = qrcode.make(payload)
            buf = BytesIO()
            img.save(buf, format="PNG")
            response.qr_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
            self.get_logger().info(f"Generated QR for order {request.order_id}")
        except Exception as e:
            self.get_logger().error(f"QR generation failed: {e}")
            response.qr_base64 = ""
        return response

def main(args=None):
    rclpy.init(args=args)
    node = QrGenerator()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
