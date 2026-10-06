#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import sys

class FrankaPositionPublisher(Node):
    def __init__(self, target_positions):
        super().__init__('franka_position_publisher')
        
        # Target topic for position controller tracking hooks
        topic_name = '/joint_commands'
        self.publisher_ = self.create_publisher(JointState, topic_name, 10)
        
        # Give discovery a brief moment, then command target positions
        self.get_logger().info(f"Connecting to command pipeline: {topic_name}...")
        self.timer = self.create_timer(1.0, lambda: self.send_command(target_positions))

    def send_command(self, positions):
        msg = JointState()
        # Explicitly map the 7 joint identifier tags for the Franka system architecture
        msg.name = [
            'fr3_joint1', 'fr3_joint2', 'fr3_joint3', 
            'fr3_joint4', 'fr3_joint5', 'fr3_joint6', 'fr3_joint7'
        ]
        msg.position = positions

        self.publisher_.publish(msg)
        self.get_logger().info(f"[+] SUCCESS: Sent arm trajectory target: {positions}")
        
        # Shutdown node execution safely after sending the command frame
        raise SystemExit

def main(args=None):
    rclpy.init(args=args)
    
    # Baseline fallback target coordinates (Home configuration in Radians)
    target_joints = [0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785]
    
    if len(sys.argv) > 1:
        try:
            # Expects a comma-separated string of 7 radian elements: e.g., 0.0,-0.5,0.0,-2.0,0.0,1.5,0.7
            target_joints = [float(x) for x in sys.argv[1].split(',')]
            if len(target_joints) != 7:
                raise ValueError
        except ValueError:
            print("[-] ERROR: Provide exactly 7 radian values separated by commas.")
            return

    node = FrankaPositionPublisher(target_joints)
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
