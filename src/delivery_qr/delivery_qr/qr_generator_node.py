import base64
import io
import rclpy
from rclpy.node import Node
from delivery_qr_interfaces.srv import GenerateQr
import qrcode
from PIL import Image

class QrGenerator(Node):
    def __init__(self):
        super().__init__('qr_generator')
        self.srv = self.create_service(GenerateQr, 'generate_qr', self.handle_generate_qr)
        self.get_logger().info('QR Generator service ready on /generate_qr')

    def handle_generate_qr(self, request, response):
        try:
            payload = f"order:{request.order_id};phone:{request.phone};address:{request.address}"
            img = qrcode.make(payload)
            if not isinstance(img, Image.Image):
                img = img.get_image()
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            response.success = True
            response.message = 'QR generated'
            response.qr_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
        except Exception as e:
            response.success = False
            response.message = f'QR generation failed: {e}'
            response.qr_base64 = ''
        return response

def main(args=None):
    rclpy.init(args=args)
    node = QrGenerator()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
