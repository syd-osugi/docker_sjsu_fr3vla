#!/usr/bin/env python3
"""Franka ROS 2 client: move the arm, read joint states, grasp with the gripper.

Prerequisite: franka_bringup (franka_hardware) must be running and connected
to the robot. This node does NOT talk to the robot directly.

Usage:
  python3 franka_ros_client.py --arm 0,0,0,0,0,0,0.1 --delta   # small relative move
  python3 franka_ros_client.py --arm 0.0,-0.785,0.0,-2.356,0.0,1.571,0.785
  python3 franka_ros_client.py --grasp --width 0.005
  python3 franka_ros_client.py --echo          # just print joint states
"""
import argparse
import sys

import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from builtin_interfaces.msg import Duration
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint

JOINT_NAMES = [f"fr3_joint{i}" for i in range(1, 8)]
MAX_STEP_RAD = 0.3  # safety: refuse bigger jumps unless --allow-large


class FrankaClient(Node):
    def __init__(self, args):
        super().__init__("franka_client")
        self.args = args
        self.last_state = None

        # Subscribe: joint states published by joint_state_broadcaster
        self.create_subscription(JointState, args.state_topic, self.on_state, 10)

        # Publish: trajectory command for the arm controller
        self.traj_pub = self.create_publisher(JointTrajectory, args.traj_topic, 10)

        self.sent = False
        self.timer = self.create_timer(0.5, self.tick)

    def on_state(self, msg: JointState):
        self.last_state = msg
        if self.args.echo:
            pairs = ", ".join(f"{n}={p:.3f}" for n, p in zip(msg.name, msg.position))
            self.get_logger().info(pairs)

    def tick(self):
        if self.sent or self.args.echo or self.args.arm is None:
            return
        # Wait until the controller is actually listening
        if self.traj_pub.get_subscription_count() == 0:
            self.get_logger().warn(
                f"No subscriber on {self.args.traj_topic} yet. Is the controller "
                "active? (ros2 control list_controllers)"
            )
            return
        # Need the current pose for relative moves and the step-size safety check
        if self.last_state is None:
            self.get_logger().warn(f"Waiting for joint states on {self.args.state_topic}...")
            return
        cur = dict(zip(self.last_state.name, self.last_state.position))
        missing = [n for n in JOINT_NAMES if n not in cur]
        if missing:
            self.get_logger().error(f"Joint states missing {missing}; not moving.")
            self.sent = True
            return
        current = [cur[n] for n in JOINT_NAMES]

        if self.args.delta:
            target = [c + d for c, d in zip(current, self.args.arm)]
        else:
            target = self.args.arm

        biggest = max(abs(t - c) for t, c in zip(target, current))
        if biggest > MAX_STEP_RAD and not self.args.allow_large:
            self.get_logger().error(
                f"Refusing move: largest joint change is {biggest:.2f} rad "
                f"(limit {MAX_STEP_RAD} rad). Current: "
                f"{[round(c, 3) for c in current]}. Use smaller steps, or pass "
                "--allow-large if you are sure."
            )
            self.sent = True
            return

        traj = JointTrajectory()
        traj.joint_names = JOINT_NAMES
        point = JointTrajectoryPoint()
        point.positions = target
        point.time_from_start = Duration(sec=self.args.duration)
        traj.points = [point]
        self.traj_pub.publish(traj)
        self.sent = True
        self.get_logger().info(
            f"Sent arm target (max change {biggest:.3f} rad over "
            f"{self.args.duration}s): {[round(t, 3) for t in target]}"
        )

    def grasp(self):
        from franka_msgs.action import Grasp

        client = ActionClient(self, Grasp, self.args.grasp_action)
        if not client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error(
                f"Action server {self.args.grasp_action} not found. Run "
                "'ros2 action list' and start franka_gripper if needed."
            )
            return False
        goal = Grasp.Goal()
        goal.width = self.args.width
        goal.speed = self.args.speed
        goal.force = self.args.force
        goal.epsilon.inner = 0.005
        goal.epsilon.outer = 0.005
        future = client.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future)
        handle = future.result()
        if not handle.accepted:
            self.get_logger().error("Grasp goal rejected")
            return False
        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        ok = result_future.result().result.success
        self.get_logger().info(f"Grasp success: {ok}")
        return ok


def parse_arm(text):
    vals = [float(x) for x in text.split(",")]
    if len(vals) != 7:
        raise argparse.ArgumentTypeError("need exactly 7 comma-separated radians")
    return vals


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--arm", type=parse_arm, help="7 joint targets in radians")
    p.add_argument("--duration", type=int, default=10, help="seconds to reach target")
    p.add_argument("--delta", action="store_true", help="treat --arm values as offsets from the current pose")
    p.add_argument("--allow-large", action="store_true", help="allow joint moves larger than the safety limit")
    p.add_argument("--echo", action="store_true", help="print joint states")
    p.add_argument("--grasp", action="store_true")
    p.add_argument("--width", type=float, default=0.005)
    p.add_argument("--speed", type=float, default=0.1)
    p.add_argument("--force", type=float, default=60.0)
    # Verify these against 'ros2 topic list' / 'ros2 action list' on your system
    p.add_argument("--traj-topic", default="/fr3_arm_controller/joint_trajectory")
    p.add_argument("--state-topic", default="/joint_states")
    p.add_argument("--grasp-action", default="/franka_gripper/grasp")
    args, ros_args = p.parse_known_args()

    rclpy.init(args=ros_args)
    node = FrankaClient(args)
    try:
        if args.grasp:
            node.grasp()
        else:
            rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())