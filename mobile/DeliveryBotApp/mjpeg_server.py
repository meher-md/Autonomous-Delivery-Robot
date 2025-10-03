#!/usr/bin/env python3
import io, threading, time
from flask import Flask, Response
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from PIL import Image as PILImage
import numpy as np

app = Flask(__name__)
latest_jpeg_lock = threading.Lock()
latest_jpeg = None

class ImgSub(Node):
    def __init__(self):
        super().__init__('mjpeg_bridge')
        self.create_subscription(Image, '/image_raw', self.cb, 10)

    def cb(self, msg: Image):
        if msg.encoding in ('rgb8','bgr8'):
            arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width, -1)
            if msg.encoding == 'bgr8':
                arr = arr[:, :, ::-1]
        elif msg.encoding in ('mono8',):
            arr = np.frombuffer(msg.data, dtype=np.uint8).reshape(msg.height, msg.width)
        else:
            return
        im = PILImage.fromarray(arr)
        buf = io.BytesIO()
        im.save(buf, format='JPEG', quality=80)
        buf.seek(0)
        global latest_jpeg
        with latest_jpeg_lock:
            latest_jpeg = buf.read()

def gen():
    global latest_jpeg
    while True:
        frame = None
        with latest_jpeg_lock:
            frame = latest_jpeg
        if frame is None:
            time.sleep(0.05); continue
        yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
        time.sleep(0.03)

@app.route('/stream.mjpg')
def stream():
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

def main():
    rclpy.init()
    node = ImgSub()
    t = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    t.start()
    app.run(host='0.0.0.0', port=8080, threaded=True)

if __name__ == '__main__':
    main()
