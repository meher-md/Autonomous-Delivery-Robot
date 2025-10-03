import json
import time
import math
from typing import Optional

import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
from rclpy.duration import Duration

from std_msgs.msg import String, Bool
from geometry_msgs.msg import PoseStamped, Quaternion
from nav2_msgs.action import NavigateToPose
from sensor_msgs.msg import Image

from cv_bridge import CvBridge
import cv2
from pyzbar import pyzbar
import yaml

def yaw_to_quat(yaw: float) -> Quaternion:
    # Z-only yaw
    q = Quaternion()
    half = yaw * 0.5
    q.z = math.sin(half)
    q.w = math.cos(half)
    return q

class DeliveryOrderNode(Node):
    def __init__(self):
        super().__init__('delivery_order_node')

        # Params
        self.declare_parameter('waypoints_yaml', '')
        self.declare_parameter('image_topic', '/image_raw')
        self.declare_parameter('qr_timeout_sec', 20.0)

        self.image_topic = self.get_parameter('image_topic').get_parameter_value().string_value
        self.qr_timeout = self.get_parameter('qr_timeout_sec').get_parameter_value().double_value
        waypoints_yaml = self.get_parameter('waypoints_yaml').get_parameter_value().string_value

        # Load waypoints
        self.waypoints = {}
        if waypoints_yaml:
            try:
                from ament_index_python.packages import get_package_share_directory
                if waypoints_yaml.startswith('package://'):
                    # package://delivery_order/config/waypoints.yaml
                    pkg, rel = waypoints_yaml[len('package://'):].split('/', 1)
                    base = get_package_share_directory(pkg)
                    path = f'{base}/{rel}'
                else:
                    path = waypoints_yaml
                with open(path, 'r') as f:
                    data = yaml.safe_load(f) or {}
                    self.waypoints = data.get('waypoints', {})
                self.get_logger().info(f'Loaded waypoints: {list(self.waypoints.keys())}')
            except Exception as e:
                self.get_logger().warn(f'Failed to load waypoints: {e}')

        # Publishers
        self.pub_status = self.create_publisher(String, '/order/status', 10)
        self.pub_verified = self.create_publisher(Bool, '/order/verified', 10)

        # Subscriber for orders (JSON via app through rosbridge)
        self.sub_order = self.create_subscription(
            String, '/order/json', self.on_order, 10
        )

        # Nav2 action client
        self.nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        # Image subscriber on-demand
        self.bridge = CvBridge()
        self.image_sub = None
        self.latest_frame = None

        self.get_logger().info('delivery_order_node is up. Waiting for /order/json ...')

    # ---------- Order handler ----------
    def on_order(self, msg: String):
        try:
            order = json.loads(msg.data)
        except Exception as e:
            self._status(f'invalid order json: {e}')
            return

        order_id = str(order.get('order_id', ''))
        phone    = str(order.get('phone', ''))
        address  = str(order.get('address', ''))
        waypoint = str(order.get('waypoint', ''))  # optional alias

        if not order_id or not address:
            self._status('order missing order_id/address'); return

        self._status(f'Received order {order_id} -> "{address or waypoint}"')

        # Resolve pose from waypoint or inline coordinates
        pose = self._resolve_pose(address, waypoint, order)
        if pose is None:
            self._status('failed to resolve destination pose'); return

        # Navigate
        if not self._navigate_to_pose(pose):
            self._status('navigation failed'); return

        self._status('Arrived. Starting QR scan ...')

        # Expected QR payload (same format as delivery_qr.qr_generator_node)
        expected = f'order:{order_id};phone:{phone};address:{address}'

        ok = self._scan_qr_until(expected, timeout_sec=self.qr_timeout)
        self.pub_verified.publish(Bool(data=ok))
        if ok:
            self._status('QR verified ✅')
        else:
            self._status('QR verification failed ❌')

    # ---------- Helpers ----------
    def _resolve_pose(self, address: str, waypoint: str, order: dict) -> Optional[PoseStamped]:
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.get_clock().now().to_msg()

        # 1) waypoint name
        key = waypoint or address
        if key and key in self.waypoints:
            wp = self.waypoints[key]
            x = float(wp.get('x', 0.0)); y = float(wp.get('y', 0.0)); th = float(wp.get('theta', 0.0))
            pose.pose.position.x = x
            pose.pose.position.y = y
            pose.pose.orientation = yaw_to_quat(th)
            return pose

        # 2) direct fields x,y,theta in order JSON
        if all(k in order for k in ('x','y','theta')):
            x = float(order['x']); y = float(order['y']); th = float(order['theta'])
            pose.pose.position.x = x
            pose.pose.position.y = y
            pose.pose.orientation = yaw_to_quat(th)
            return pose

        # Not found
        self.get_logger().warn(f'No waypoint match for "{key}", and no x/y/theta in order.')
        return None

    def _navigate_to_pose(self, pose: PoseStamped) -> bool:
        if not self.nav_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error('Nav2 action server not available')
            return False

        goal = NavigateToPose.Goal()
        goal.pose = pose

        self._status('Sending goal to Nav2 ...')
        send_future = self.nav_client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, send_future)
        goal_handle = send_future.result()
        if not goal_handle or not goal_handle.accepted:
            self.get_logger().error('Goal rejected')
            return False

        self._status('Goal accepted. Waiting for result ...')
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        result = result_future.result()
        if not result:
            self.get_logger().error('No result from Nav2')
            return False

        status = getattr(result, 'status', 0)
        success = (status == 4)  # SUCCEEDED
        self.get_logger().info(f'Nav2 result status={status} success={success}')
        return success

    def _scan_qr_until(self, expected_text: str, timeout_sec: float) -> bool:
        # Subscribe
        if self.image_sub is None:
            qos = QoSProfile(
                depth=1,
                reliability=QoSReliabilityPolicy.BEST_EFFORT,
                history=QoSHistoryPolicy.KEEP_LAST
            )
            self.image_sub = self.create_subscription(Image, self.image_topic, self._on_image, qos)
            # اعطِ بعض الوقت لتدفّق الفريمات
            rclpy.spin_once(self, timeout_sec=0.1)

        end_time = self.get_clock().now() + Duration(seconds=timeout_sec)
        while self.get_clock().now() < end_time:
            rclpy.spin_once(self, timeout_sec=0.05)
            frame = self.latest_frame
            if frame is None:
                continue
            # Decode QR
            barcodes = pyzbar.decode(frame)
            for b in barcodes:
                txt = b.data.decode('utf-8', errors='ignore')
                if txt == expected_text:
                    return True
        return False

    def _on_image(self, msg: Image):
        try:
            cvimg = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            gray = cv2.cvtColor(cvimg, cv2.COLOR_BGR2GRAY)
            self.latest_frame = gray
        except Exception as e:
            self.get_logger().warn(f'cv_bridge error: {e}')

    def _status(self, text: str):
        self.get_logger().info(text)
        self.pub_status.publish(String(data=text))

def main():
    rclpy.init()
    node = DeliveryOrderNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()
