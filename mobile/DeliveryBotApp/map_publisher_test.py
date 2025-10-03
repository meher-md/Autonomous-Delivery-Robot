#!/usr/bin/env python3
import math, time
import numpy as np
import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import Pose, Point, Quaternion
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy

class StaticMapPublisher(Node):
    def __init__(self):
        super().__init__('static_map_publisher')
        qos = QoSProfile(depth=1,
                         reliability=ReliabilityPolicy.RELIABLE,
                         durability=DurabilityPolicy.TRANSIENT_LOCAL,
                         history=HistoryPolicy.KEEP_LAST)
        self.pub = self.create_publisher(OccupancyGrid, '/map', qos)
        self.timer = self.create_timer(1.0, self.publish_map)  # 1 Hz
        # خريطة صغيرة 200x200 بخط أسود وعوائق
        self.resolution = 0.05  # 5cm/pixel
        self.w = 200; self.h = 200
        grid = np.full((self.h, self.w), -1, dtype=np.int8)  # unknown
        grid[:, :] = 0  # خليها فاضية
        grid[50:55, 20:180] = 100  # جدار أفقي
        for i in range(40,160,10):  # عوائق نقطية
            grid[120, i] = 100
        self.grid = grid

    def publish_map(self):
        msg = OccupancyGrid()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'map'
        msg.info.resolution = self.resolution
        msg.info.width = self.w
        msg.info.height = self.h
        msg.info.origin = Pose(position=Point(x=0.0, y=0.0, z=0.0),
                               orientation=Quaternion(x=0.0, y=0.0, z=0.0, w=1.0))
        msg.data = [int(v) for v in self.grid.flatten()]
        self.pub.publish(msg)
        self.get_logger().info(f'Published test map {self.w}x{self.h} (res={self.resolution})')

def main():
    rclpy.init()
    node = StaticMapPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
