#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
import sys

class HandPositionPublisher(Node):
    def __init__(self, target_positions):
        super().__init__('hand_position_publisher')
        
        # Adjust namespace to match your launcher setup ('left' or 'right')
        topic_name = '/realhand/right/hand/command'
        self.publisher_ = self.create_publisher(JointState, topic_name, 10)
        
        # Wait briefly for discovery to ensure the message isn't dropped
        self.get_logger().info(f"Connecting to topic pipeline: {topic_name}...")
        self.timer = self.create_timer(1.0, lambda: self.send_command(target_positions))

    def send_command(self, positions):
        msg = JointState()
        # Define the exact 6 joint identifiers mapping to the L6 model architecture
        msg.name = ['thumb_flex', 'thumb_abd', 'index', 'middle', 'ring', 'pinky']
        msg.position = positions

        self.publisher_.publish(msg)
        self.get_logger().info(f"[+] SUCCESS: Sent target positions: {positions}")
        
        # Shutdown cleanly after publishing the position shift execution frame
        raise SystemExit

def main(args=None):
    rclpy.init(args=args)
    
    # Default to half-closed (50.0) across all fingers if no values are provided via terminal CLI
    target_pos = [0.0, 50.0, 50.0, 90.0, 90.0, 90.0]
    
    if len(sys.argv) > 1:
        try:
            # Expects a comma-separated string like: 0,100,50,50,0,100
            target_pos = [float(x) for x in sys.argv[1].split(',')]
            if len(target_pos) != 6:
                raise ValueError
        except ValueError:
            print("[-] ERROR: Provide exactly 6 floating-point values separated by commas (0 to 100).")
            return

    node = HandPositionPublisher(target_pos)
    try:
        rclpy.spin(node)
    except SystemExit:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
