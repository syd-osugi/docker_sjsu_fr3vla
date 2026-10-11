#!/usr/bin/env python3
import math

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState


class FrankaStateSubscriber(Node):
    def __init__(self):
        super().__init__('franka_state_subscriber')

        # Published by joint_state_publisher (merges /franka/joint_states
        # with the gripper's joint states). Change if you use a namespace.
        topic_name = '/joint_states'

        self.last_print = 0.0
        self.subscription = self.create_subscription(
            JointState,
            topic_name,
            self.listener_callback,
            10
        )
        self.get_logger().info(f"[+] Active. Listening for Franka telemetry on: {topic_name}")

    def listener_callback(self, msg):
        # Print at most twice per second so the terminal stays readable
        now = self.get_clock().now().nanoseconds / 1e9
        if now - self.last_print < 0.5:
            return
        self.last_print = now

        # Only the 7 arm joints (skips gripper finger joints)
        arm = [i for i, n in enumerate(msg.name) if n.startswith('fr3_joint')]
        if not arm:
            return

        print("\n================ FRANKA LIVE ARM TELEMETRY ================")
        print(" Joint Name  | Position (Rad) | Position (Deg) | Speed  | Torque (Nm)")
        print("-" * 69)

        for i in arm:
            # Fall back to 0.0 if a vector isn't fully populated
            pos_rad = msg.position[i] if i < len(msg.position) else 0.0
            vel = msg.velocity[i] if i < len(msg.velocity) else 0.0
            eff = msg.effort[i] if i < len(msg.effort) else 0.0

            print(f"  {msg.name[i]:10} | {pos_rad:14.4f} | {math.degrees(pos_rad):13.2f}° | {vel:6.2f} | {eff:11.2f}")
        print("===========================================================")


def main(args=None):
    rclpy.init(args=args)
    node = FrankaStateSubscriber()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        print("\n[-] Franka subscriber disconnected cleanly.")
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()