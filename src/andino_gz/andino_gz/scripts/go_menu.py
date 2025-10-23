#!/usr/bin/env python3
import os
import yaml
import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from geometry_msgs.msg import PoseStamped, Quaternion
from nav2_msgs.action import NavigateToPose
from math import sin, cos

DEFAULT_YAML_PATH = os.path.expanduser('~/ws/src/andino_gz/config/named_poses.yaml')


def yaw_to_quat(yaw: float) -> Quaternion:
    q = Quaternion()
    q.x = 0.0
    q.y = 0.0
    q.z = sin(yaw / 2.0)
    q.w = cos(yaw / 2.0)
    return q


def load_named_poses(yaml_path: str):
    """Return dict{name: {'position':{x,y,z}, 'orientation':{x,y,z,w}}}."""
    if not os.path.exists(yaml_path):
        return {}
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f) or {}

    items = data.get('waypoints', data) if isinstance(data, dict) else {}
    poses = {}
    for name, pose in items.items():
        if not isinstance(pose, dict):
            continue
        p = pose.get('position', {}) or {}
        o = pose.get('orientation', None)
        pos = {
            'x': float(p.get('x', 0.0)),
            'y': float(p.get('y', 0.0)),
            'z': float(p.get('z', 0.0)),
        }
        if o is None and 'yaw' in pose:
            q = yaw_to_quat(float(pose['yaw']))
            ori = {'x': q.x, 'y': q.y, 'z': q.z, 'w': q.w}
        elif o is None:
            q = yaw_to_quat(0.0)
            ori = {'x': q.x, 'y': q.y, 'z': q.z, 'w': q.w}
        else:
            ori = {
                'x': float(o.get('x', 0.0)),
                'y': float(o.get('y', 0.0)),
                'z': float(o.get('z', 0.0)),
                'w': float(o.get('w', 1.0)),
            }
        poses[str(name)] = {'position': pos, 'orientation': ori}
    return poses


class GoMenu(Node):
    def __init__(self):
        super().__init__('go_menu')

        # Parameters
        self.declare_parameter('yaml_path', DEFAULT_YAML_PATH)
        self.declare_parameter('frame_id', 'map')
        self.declare_parameter('timeout_sec', 0.0)  # 0 = no overall timeout

        self.yaml_path = self.get_parameter('yaml_path').get_parameter_value().string_value
        self.frame_id = self.get_parameter('frame_id').get_parameter_value().string_value
        self.timeout = self.get_parameter('timeout_sec').get_parameter_value().double_value

        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')

        self.get_logger().info('Interactive menu started.')
        self.menu_loop()

    # ---------- main loop ----------
    def menu_loop(self):
        try:
            while rclpy.ok():
                poses = load_named_poses(self.yaml_path)
                if not poses:
                    print(f'\nNo waypoints found in {self.yaml_path}')
                    print('Add some labels first, then press [r] to reload, or [q] to quit.')
                    choice = input('Enter choice: ').strip().lower()
                    if choice == 'q':
                        break
                    else:
                        continue

                names = sorted(poses.keys())
                print('\n=== Select Destination ===')
                for i, n in enumerate(names, start=1):
                    p = poses[n]['position']
                    print(f'{i}) {n}  (x={p["x"]:.2f}, y={p["y"]:.2f})')
                print('r) Reload from YAML')
                print('q) Quit')

                choice = input('Enter number: ').strip().lower()
                if choice == 'q':
                    break
                if choice == 'r':
                    continue

                if not choice.isdigit():
                    print('Invalid input.')
                    continue
                idx = int(choice)
                if idx < 1 or idx > len(names):
                    print('Out of range.')
                    continue

                name = names[idx - 1]
                self.navigate_to(poses[name], name)

        except (KeyboardInterrupt, EOFError):
            pass

    # ---------- navigation ----------
    def navigate_to(self, item: dict, name: str):
        if not self.client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error('navigate_to_pose action server not available.')
            return

        p = item['position']
        o = item['orientation']

        goal = NavigateToPose.Goal()
        goal.pose = PoseStamped()
        goal.pose.header.frame_id = self.frame_id
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = p['x']
        goal.pose.pose.position.y = p['y']
        goal.pose.pose.position.z = p.get('z', 0.0)
        goal.pose.pose.orientation = Quaternion(x=o['x'], y=o['y'], z=o['z'], w=o['w'])

        self.get_logger().info(f'Navigating to "{name}" ...')
        send_future = self.client.send_goal_async(goal, feedback_callback=self.on_feedback)
        rclpy.spin_until_future_complete(self, send_future)
        handle = send_future.result()
        if not handle or not handle.accepted:
            self.get_logger().error('Goal rejected.')
            return

        result_future = handle.get_result_async()
        # Wait until done
        rclpy.spin_until_future_complete(self, result_future)
        if result_future.result() and result_future.result().status == 4:
            self.get_logger().info(f'Goal "{name}" reached.')
        else:
            status = None if not result_future.result() else result_future.result().status
            self.get_logger().warn(f'Goal "{name}" finished with status={status}.')

    def on_feedback(self, fb_msg):
        fb = fb_msg.feedback
        try:
            print(f'  remaining: {fb.distance_remaining:.2f} m')
        except Exception:
            pass


def main():
    rclpy.init()
    node = GoMenu()
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
