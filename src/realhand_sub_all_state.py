#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import String
import json
import os

class UltimateHandSubscriber(Node):
    def __init__(self):
        super().__init__('ultimate_hand_subscriber')
        
        # ROS 2 Namespace routing mapping. 
        # 'side:=right' parameter during launch moves all topics under this root path.
        ns = '/realhand/right/hand'
        
        # Telemetry Data Buffers (Initialized to placeholder strings until packets arrive)
        self.joints = {}
        self.forces = "No data"
        self.temps = "No data"
        self.faults = "No data"
        self.currents = "No data"
        self.speeds_json = "No data"
        self.control_status = "No data"

        # ----------------------------------------------------------------------
        # ROS 2 TOPIC SUBSCRIPTION PIPELINES
        # ----------------------------------------------------------------------
        # 1. Core Kinematic Data (Positions, Speeds, and Motor Effort metrics)
        self.create_subscription(JointState, f'{ns}/state', self.joint_callback, 10)
        
        # 2. Tactile Touch Data (Raw pressure grid values from the fingertip matrices)
        self.create_subscription(String, f'{ns}/force_sensor', self.force_callback, 10)
        
        # 3. Core Thermal Data (Live temperature tracking on the internal motor chips)
        self.create_subscription(String, f'{ns}/temperature', self.temp_callback, 10)
        
        # 4. Safety Fault Status (Binary flag indicators showing system errors or safety locks)
        self.create_subscription(String, f'{ns}/fault', self.fault_callback, 10)
        
        # 5. Raw Amperage Tracking (Electrical power draw on each independent motor channel)
        self.create_subscription(String, f'{ns}/current', self.current_callback, 10)
        
        # 6. Global Operational Velocity (Current baseline limits configured for the backend)
        self.create_subscription(String, f'{ns}/speed', self.speed_json_callback, 10)
        
        # 7. Driver Transaction Logging (Handshake responses from control requests)
        self.create_subscription(String, f'{ns}/control_status', self.status_callback, 10)

        # Refresh Timer: Executes the terminal UI redrawing block 10 times per second (10 Hz)
        self.create_timer(0.1, self.render_dashboard)
        self.get_logger().info(f"[+] Multi-channel raw metric listener active on {ns}/*")

    def joint_callback(self, msg):
        """Processes JointState frames. Converts normalized float positions to raw hardware ticks."""
        for i in range(len(msg.name)):
            # position value arrives normalized on a 0.0 to 100.0% scale
            pos_percent = msg.position[i] if i < len(msg.position) else 0.0
            
            # HARDWARE TICK CONVERSION:
            # The RealHand L6 internal 12-bit quadrature encoders map a full finger flex 
            # across a range of 0 to 2000 digital ticks (0 = Flat Open, 2000 = Closed Fist).
            raw_ticks = int((pos_percent / 100.0) * 2000)
            
            self.joints[msg.name[i]] = {
                'pct': pos_percent,
                'raw': raw_ticks,
                'vel': msg.velocity[i] if i < len(msg.velocity) else 0.0,
                'eff': msg.effort[i] if i < len(msg.effort) else 0.0
            }

    # JSON Data Extraction Hooks (Pipes the raw string packets straight into our buffers)
    def force_callback(self, msg): self.forces = msg.data
    def temp_callback(self, msg): self.temps = msg.data
    def fault_callback(self, msg): self.faults = msg.data
    def current_callback(self, msg): self.currents = msg.data
    def speed_json_callback(self, msg): self.speeds_json = msg.data
    def status_callback(self, msg): self.control_status = msg.data

    def render_dashboard(self):
        """Clears the console screen and renders a formatted real-time instrument dashboard."""
        os.system('clear')
        print("=========================================================================")
        print("                REALHAND L6 ULTIMATE LIVE STATE DASHBOARD                ")
        print("=========================================================================")
        
        #-----------------------------------------------------------------------
        # CORE JOINT STATE METRICS
        #-----------------------------------------------------------------------
        # Pos (%): 0.00% (Fully Straight/Open) to 100.00% (Fully Curled/Closed)
        # Ticks:   0 Ticks (Optical Home position) to 2000 Ticks (Max Mechanical Limit)
        # Speed:   Normalized relative tracking velocity scale (0 to 100)
        # Curr:    Motor feedback current/torque effort signature (0 to 100)
        #-----------------------------------------------------------------------
        print("\n CORE JOINT STATE (Percent / Raw Ticks / Velocity / Effort)")
        print("-" * 73)
        if not self.joints:
            print("  Waiting for JointState stream packets...")
        for name, data in self.joints.items():
            print(f"  Finger: {name:12} | Pos: {data['pct']:6.2f}% ({data['raw']:4d} Ticks) | Speed: {data['vel']:5.1f} | Curr: {data['eff']:5.1f}")

        #-----------------------------------------------------------------------
        # TACTILE FORCE SENSING HEATMAP METRIC
        #-----------------------------------------------------------------------
        # Range: An array of 8-bit resolution integer matrices per finger.
        #        0 represents completely untouched air.
        #        255 represents high-pressure surface collision/solid contact object.
        #-----------------------------------------------------------------------
        print("\n TACTILE FORCE SENSING HEATMAP METRIC")
        print("-" * 73)
        print(f"  Raw Matrix Data (0 to 255): {self.forces}")

        #-----------------------------------------------------------------------
        # THERMAL METRICS
        #-----------------------------------------------------------------------
        # Range: Real-time board temp array in degrees Celsius (°C).
        #        Normal idling operational room temps run between 25°C to 45°C.
        #        Safety cutoff sensors automatically disable the hand above 75°C.
        #-----------------------------------------------------------------------
        print("\n CORE THERMAL TELEMETRY (Celsius)")
        print("-" * 73)
        print(f"  Temperatures: {self.temps}")

        #-----------------------------------------------------------------------
        # ELECTRICAL CURRENT DRAW METRICS
        #-----------------------------------------------------------------------
        # Range: Real-time active power draw per motor channel in Milliamperes (mA).
        #        Idling draw runs between 50 mA - 150 mA.
        #        Stalling against heavy solid objects can spike values up to 1500 mA.
        #-----------------------------------------------------------------------
        print("\n ELECTRICAL CURRENT DRAW ANALYSIS")
        print("-" * 73)
        print(f"  Currents (mA): {self.currents}")

        #-----------------------------------------------------------------------
        # HARDWARE FAULT MASK METRIC
        #-----------------------------------------------------------------------
        # Range: Binary status bitfield output array (e.g., [0, 0, 0, 0, 0, 0]).
        #        0 = Completely Healthy.
        #        1 = Hardware Fault Active (e.g., CAN bus timeout, Overcurrent, Overheating).
        #-----------------------------------------------------------------------
        print("\n SYSTEM HEALTH & HARDWARE FAULT SAFETY MATRIX")
        print("-" * 73)
        print(f"  Active Fault Status Flags (0=OK, 1=Error): {self.faults}")
        print("=========================================================================")

def main(args=None):
    rclpy.init(args=args)
    node = UltimateHandSubscriber()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
