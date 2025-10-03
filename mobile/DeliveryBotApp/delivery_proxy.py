#!/usr/bin/env python3
from flask import Flask, Response, send_file, stream_with_context
import requests

app = Flask(__name__)

ROSBRIDGE_URL = "ws://127.0.0.1:9090"
CAMERA_URL    = "http://127.0.0.1:8080/stream.mjpg"
MAP_URL       = "http://127.0.0.1:8070/map.png"

@app.route("/camera")
def camera():
    r = requests.get(CAMERA_URL, stream=True)
    return Response(stream_with_context(r.iter_content(chunk_size=1024)),
                    content_type=r.headers["Content-Type"])

@app.route("/map")
def map_png():
    r = requests.get(MAP_URL, stream=True)
    return Response(r.content, content_type="image/png")

@app.route("/ws")
def rosbridge_info():
    return f"Use WebSocket at {ROSBRIDGE_URL}"

@app.route("/")
def index():
    return """
    <h3>DeliveryBot Proxy</h3>
    <ul>
      <li><a href="/camera">Camera Stream</a></li>
      <li><a href="/map">Map PNG</a></li>
      <li>Rosbridge WebSocket: /ws</li>
    </ul>
    """

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
