import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import time
import datetime

class TestClient(Node):
    def __init__(self):
        super().__init__('test_chatbot_client')
        self.req_pub = self.create_publisher(String, '/app/chat/request', 10)
        self.yolo_pub = self.create_publisher(String, '/yolo/detections_str', 10)
        
        self.resp_sub = self.create_subscription(String, '/app/chat/response', self.on_response, 10)
        
        self.received_response = None

    def on_response(self, msg):
        self.get_logger().info(f"RECEIVED RESPONSE: {msg.data}")
        self.received_response = msg.data

    def send_query(self, text, timeout=20):
        self.received_response = None
        self.get_logger().info(f"--- SENDING: {text} ---")
        msg = String()
        msg.data = text
        self.req_pub.publish(msg)
        
        start = time.time()
        while time.time() - start < timeout:
            rclpy.spin_once(self, timeout_sec=0.1)
            if self.received_response:
                return self.received_response
        return None

    def simulate_vision(self, item):
        self.get_logger().info(f"Simulating Vision: {item}")
        msg = String()
        msg.data = item
        self.yolo_pub.publish(msg)

def main():
    rclpy.init()
    node = TestClient()
    
    # Allow connections
    time.sleep(2)
    
    # 1. Hello
    res = node.send_query("Hello")
    if res:
        print(f"TEST 1 (Hello) PASSED: {res}")
    else:
        print("TEST 1 (Hello) FAILED: Timeout")

    # 2. Time
    res = node.send_query("What is today?")
    if res and "2026" in res:
        print(f"TEST 2 (Time) PASSED: {res}")
    else:
        print(f"TEST 2 (Time) FAILED/UNCERTAIN: {res}")

    # 3. History
    res = node.send_query("Compare last 4 trips")
    if res and len(res) > 50:
         print(f"TEST 3 (History) PASSED: Length {len(res)}")
    else:
         print(f"TEST 3 (History) FAILED: Too short or empty -> {res}")

    # 4. Vision
    node.simulate_vision("A big red chair")
    time.sleep(1)
    res = node.send_query("What do you see?")
    if res and ("chair" in res.lower() or "seat" in res.lower()):
        print(f"TEST 4 (Vision) PASSED: {res}")
    else:
        print(f"TEST 4 (Vision) FAILED: {res}")
        
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
