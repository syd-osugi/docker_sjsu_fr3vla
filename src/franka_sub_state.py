#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import math

class FrankaStateSubscriber(Node):
    def __init__(self):
        super().__init__('franka_state_subscriber')
        
        # Standard topic published by the franka_robot_state_broadcaster
        # Update namespace if you launch the robot with custom namespaces (e.g. /fr3/joint_states)
        topic_name = '/joint_states'
        
        self.subscription = self.create_subscription(
            JointState,
            topic_name,
            self.listener_callback,
            10
        )
        self.get_logger().info(f"[+] Active. Listening for Franka telemetry on: {topic_name}")

    def listener_callback(self, msg):
        # Filter to ensure we are only tracking the 7 primary arm joints
        if not msg.name or 'joint_1' not in msg.name[0]:
            return
            
        print("\n================ FRANKA LIVE ARM TELEMETRY ================")
        print(" Joint Name  | Position (Rad) | Position (Deg) | Speed  | Torque (Nm)")
        print("-" * 69)
        
        for i in range(len(msg.name)):
            # Fallbacks to 0.0 if vectors aren't fully populated during a frame drop
            pos_rad = msg.position[i] if i < len(msg.position) else 0.0
            pos_deg = math.degrees(pos_rad)
            vel = msg.velocity[i] if i < len(msg.velocity) else 0.0
            eff = msg.effort[i] if i < len(msg.effort) else 0.0
            
            print(f"  {msg.name[i]:10} | {pos_rad:14.4f} | {pos_deg:14.2f}° | {vel:6.2f} | {eff:11.2f}")
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
