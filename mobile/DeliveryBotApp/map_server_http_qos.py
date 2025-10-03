#!/usr/bin/env python3
import io, threading
from flask import Flask, send_file
import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid
import numpy as np
from PIL import Image
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy, HistoryPolicy

app = Flask(__name__)
lock = threading.Lock()
png_bytes = None

class MapSub(Node):
    def __init__(self):
        super().__init__('map_http_bridge')
        qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST
        )
        self.create_subscription(OccupancyGrid, '/map', self.cb, qos)

    def cb(self, msg: OccupancyGrid):
        data = np.array(msg.data, dtype=np.int16).reshape(msg.info.height, msg.info.width)
        img = np.zeros((msg.info.height, msg.info.width), dtype=np.uint8)
        img[:] = 205
        occ = data >= 65
        free = data == 0
        img[occ] = 0
        img[free] = 255
        img = np.flipud(img)
        from io import BytesIO
        buf = BytesIO()
        Image.fromarray(img, mode='L').save(buf, format='PNG')
        buf.seek(0)
        global png_bytes
        with lock:
            png_bytes = buf.read()

@app.route('/map.png')
def map_png():
    global png_bytes
    with lock:
        if png_bytes is None:
            return ("Map not ready", 503)
        return send_file(io.BytesIO(png_bytes), mimetype='image/png')

def main():
    rclpy.init()
    node = MapSub()
    import threading as th
    t = th.Thread(target=rclpy.spin, args=(node,), daemon=True)
    t.start()
    app.run(host='0.0.0.0', port=8070, threaded=True)

if __name__ == '__main__':
    main()
