#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
from PIL import Image
import numpy as np, os

class MapToPNG(Node):
    def __init__(self):
        super().__init__('map_to_png')
        self.sub = self.create_subscription(OccupancyGrid, '/map', self.cb, 10)
        self.out_dir = os.path.expanduser('~/maps')
        os.makedirs(self.out_dir, exist_ok=True)

    def cb(self, msg: OccupancyGrid):
        w, h = msg.info.width, msg.info.height
        data = np.array(msg.data, dtype=np.int16).reshape(h, w)  # -1,0..100
        # خرائط رمادي: -1 (unknown)=128, 0 (حر)=255, 100 (مشغول)=0
        img = np.full((h, w), 128, dtype=np.uint8)
        known = data >= 0
        img[known] = 255 - (data[known] * 255 // 100)
        im = Image.fromarray(img, mode='L').transpose(Image.FLIP_TOP_BOTTOM)
        im.save(os.path.join(self.out_dir, 'map.png'))
        # ملف مؤشر للتطبيق (اختياري)
        open(os.path.join(self.out_dir, 'map.ts'), 'w').write(str(self.get_clock().now().nanoseconds))
        self.get_logger().debug('map.png updated')

def main():
    rclpy.init()
    n = MapToPNG()
    rclpy.spin(n)
    n.destroy_node()
    rclpy.shutdown()
if __name__ == '__main__': main()
