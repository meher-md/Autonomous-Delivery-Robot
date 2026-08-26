#!/usr/bin/env python3
import os
import time

import rclpy
from geometry_msgs.msg import PoseWithCovarianceStamped


got_amcl_pose = False


def env_float(name, default):
    return float(os.environ.get(name, default))


def env_int(name, default):
    return int(os.environ.get(name, default))


def main():
    rclpy.init()
    node = rclpy.create_node('andino_initial_pose_publisher')
    publisher = node.create_publisher(PoseWithCovarianceStamped, '/initialpose', 10)

    def on_amcl_pose(_msg):
        global got_amcl_pose
        got_amcl_pose = True

    node.create_subscription(PoseWithCovarianceStamped, '/amcl_pose', on_amcl_pose, 10)

    delay = env_float('INITIAL_POSE_DELAY', '8.0')
    attempts = env_int('INITIAL_POSE_ATTEMPTS', '30')
    period = env_float('INITIAL_POSE_PERIOD', '1.0')

    end_time = time.monotonic() + delay
    while time.monotonic() < end_time and rclpy.ok():
        rclpy.spin_once(node, timeout_sec=0.2)

    msg = PoseWithCovarianceStamped()
    msg.header.frame_id = 'map'
    msg.pose.pose.position.x = env_float('INITIAL_X', '0.0')
    msg.pose.pose.position.y = env_float('INITIAL_Y', '0.0')
    msg.pose.pose.position.z = 0.0
    msg.pose.pose.orientation.z = env_float('INITIAL_Z', '0.0')
    msg.pose.pose.orientation.w = env_float('INITIAL_W', '1.0')
    msg.pose.covariance[0] = 0.25
    msg.pose.covariance[7] = 0.25
    msg.pose.covariance[35] = 0.06853891945200942

    node.get_logger().info(
        f'Publishing initial pose to /initialpose for {attempts} attempts'
    )
    for _ in range(attempts):
        if not rclpy.ok() or got_amcl_pose:
            break
        publisher.publish(msg)
        rclpy.spin_once(node, timeout_sec=0.1)
        time.sleep(period)

    if got_amcl_pose:
        node.get_logger().info('AMCL pose received; stopping initial pose publisher')

    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
