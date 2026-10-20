#!/usr/bin/env python3
"""Teleoperate a RealHand L6 from Meta Quest Hand Tracking Streamer.

Data path::

    Quest/HTS -> TCP or UDP landmarks -> finger bend estimator -> JointState
    -> /realhand/<side>/hand/command

HTS landmarks are 21 points per hand.  They do not contain RealHand actuator
positions, so this file estimates each actuator from landmark geometry.  The
RealHand command convention used here is: 0 is closed and 100 is open.
Start in dry-run mode and use ``--send`` only after checking the printed
values and the hand's mechanical workspace.

The six RealHand L6 command names used here are the names already used by
realhand_pub_position.py in this repository:
    thumb_flex, thumb_abd, index, middle, ring, pinky

Examples:
    python3 vr_realhand_teleop.py --visualize    # dry-run with live graphic
    python3 vr_realhand_teleop.py --send          # publish commands
    python3 vr_realhand_teleop.py --send --visualize
    python3 vr_realhand_teleop.py --calibrate --visualize

Calibration controls (in the graphic window):
    O - capture the currently open hand pose
    C - capture the currently closed hand pose
    R - reset calibration
    Q - close the graphic

Requires: numpy, scipy, rclpy, sensor_msgs, hand-tracking-sdk
"""

import argparse
import json
import math
import socket
import threading
import time
from pathlib import Path
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState

from hand_tracking_sdk.models import HandSide, LandmarksPacket
from hand_tracking_sdk.parser import parse_line


JOINT_NAMES = ["thumb_flex", "thumb_abd", "index", "middle", "ring", "pinky"]
DEFAULT_PORTS = {"tcp": 8000, "udp": 9000}

# MediaPipe/HTS landmark indices: wrist, then thumb and four fingers.
FINGER_POINTS = {
    "thumb": (1, 2, 3, 4),
    "index": (5, 6, 7, 8),
    "middle": (9, 10, 11, 12),
    "ring": (13, 14, 15, 16),
    "pinky": (17, 18, 19, 20),
}


def _angle_degrees(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Angle ABC in degrees, robust to very small landmark segments."""
    ba = a - b
    bc = c - b
    denominator = np.linalg.norm(ba) * np.linalg.norm(bc)
    if denominator < 1e-8:
        return 180.0
    cosine = float(np.dot(ba, bc) / denominator)
    return math.degrees(math.acos(float(np.clip(cosine, -1.0, 1.0))))


def _bend_percent(points: np.ndarray, indices, open_angle: float,
                  closed_angle: float) -> float:
    """Estimate flexion from two consecutive joint angles.

    The open/closed angle limits are configurable because Quest hand geometry
    varies between users.  The result is intentionally clamped.
    """
    wrist, proximal, distal, tip = (points[i] for i in indices)
    angles = (
        _angle_degrees(wrist, proximal, distal),
        _angle_degrees(proximal, distal, tip),
    )
    angle_range = max(open_angle - closed_angle, 1e-6)
    flex = np.mean([(open_angle - angle) / angle_range for angle in angles])
    return float(np.clip(100.0 * flex, 0.0, 100.0))


def landmarks_to_flexion(points, open_angle: float = 175.0,
                         closed_angle: float = 60.0) -> np.ndarray:
    """Convert 21 HTS landmarks to six 0..100 VR flexion values.

    These are VR-space values: 0 means open and 100 means closed.  They are
    converted to the RealHand's 0..100 convention in ``RealHandTeleop``.
    """
    points = np.asarray(points, dtype=float)
    if points.shape != (21, 3):
        raise ValueError(f"expected 21 landmarks shaped (21, 3), got {points.shape}")

    thumb_flex = _bend_percent(points, FINGER_POINTS["thumb"],
                                open_angle, closed_angle)
    finger_flex = [_bend_percent(points, FINGER_POINTS[name],
                                 open_angle, closed_angle)
                   for name in ("index", "middle", "ring", "pinky")]

    # Thumb abduction: angle between wrist->index MCP and wrist->thumb MCP.
    # 0 degrees is near the index finger; ~70 degrees is a wide open thumb.
    wrist = points[0]
    thumb_base = points[1]
    index_base = points[5]
    spread = _angle_degrees(thumb_base, wrist, index_base)
    thumb_abd = float(np.clip(100.0 * spread / 70.0, 0.0, 100.0))

    return np.asarray([thumb_flex, thumb_abd, *finger_flex], dtype=float)


class Calibration:
    """Capture and apply open/closed VR poses for all six hand commands."""

    def __init__(self, path: str, samples: int = 30):
        self.path = Path(path)
        self.samples_required = samples
        self.open_values = None
        self.closed_values = None
        self.capture_name = None
        self.capture_samples = []
        self.session_started = False
        self.session_captured = set()
        self.session_ready = False
        self.load()

    @property
    def ready(self):
        return self.open_values is not None and self.closed_values is not None

    @property
    def capturing(self):
        return self.capture_name is not None

    def load(self):
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text())
            self.open_values = np.asarray(data["open"], dtype=float)
            self.closed_values = np.asarray(data["closed"], dtype=float)
            if self.open_values.shape != (6,) or self.closed_values.shape != (6,):
                raise ValueError("calibration arrays must contain six values")
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            print(f"[calibration] ignoring {self.path}: {exc}")
            self.open_values = None
            self.closed_values = None

    def begin(self, name: str):
        self.capture_name = name
        self.capture_samples = []
        self.session_started = True
        self.session_captured.discard(name)
        if name == "open":
            self.open_values = None
        else:
            self.closed_values = None
        print(f"[calibration] capturing {name} pose: hold still")

    def observe(self, values):
        if not self.capturing:
            return
        self.capture_samples.append(np.asarray(values, dtype=float).copy())
        if len(self.capture_samples) < self.samples_required:
            return
        average = np.mean(self.capture_samples, axis=0)
        if self.capture_name == "open":
            self.open_values = average
        else:
            self.closed_values = average
        self.session_captured.add(self.capture_name)
        print(f"[calibration] {self.capture_name} pose saved: "
              + " ".join(f"{v:.1f}" for v in average))
        self.capture_name = None
        self.capture_samples = []
        if {"open", "closed"}.issubset(self.session_captured):
            self.session_ready = True
            self.save()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "joint_names": JOINT_NAMES,
            "open": self.open_values.tolist(),
            "closed": self.closed_values.tolist(),
        }
        self.path.write_text(json.dumps(data, indent=2) + "\n")
        print(f"[calibration] wrote {self.path}")

    def to_command(self, vr_values, position_max: float) -> np.ndarray:
        """Map calibrated VR values to 0..position_max, open to max."""
        if not self.ready:
            return position_max * (1.0 - np.asarray(vr_values) / 100.0)
        denominator = self.open_values - self.closed_values
        denominator = np.where(np.abs(denominator) < 1e-6, 1.0, denominator)
        normalized_open = (np.asarray(vr_values) - self.closed_values) / denominator
        return position_max * np.clip(normalized_open, 0.0, 1.0)

    def status(self):
        if self.capturing:
            return (f"capturing {self.capture_name} "
                    f"{len(self.capture_samples)}/{self.samples_required}")
        if self.session_started and not self.session_ready:
            return "calibration: press O=open, C=closed"
        if self.ready:
            return f"calibrated: {self.path.name}"
        return "uncalibrated: press O=open, C=closed"


class HandVisualizer:
    """Live Quest-landmark and RealHand-command diagnostic graphic."""

    def __init__(self, position_max: float, calibration: Calibration = None):
        import matplotlib.pyplot as plt

        self.plt = plt
        self.position_max = position_max
        self.calibration = calibration
        self.figure = plt.figure("VR -> RealHand teleoperation", figsize=(16, 9))
        self.hand_axis = self.figure.add_subplot(1, 2, 1, projection="3d")
        self.command_axis = self.figure.add_subplot(1, 2, 2)
        self.lines = []
        self.points = self.hand_axis.scatter([], [], [], s=25, c="tab:blue")
        self.bars = self.command_axis.bar(JOINT_NAMES, np.zeros(6), color="tab:orange")
        self.command_axis.set_ylim(0.0, position_max)
        self.command_axis.set_ylabel("RealHand command (0=closed, 100=open)")
        self.command_axis.tick_params(axis="x", rotation=45)
        self.hand_axis.set_box_aspect((1, 1, 1))
        self.figure.subplots_adjust(left=0.03, right=0.98, bottom=0.12,
                                    top=0.92, wspace=0.2)
        self.figure.canvas.mpl_connect("key_press_event", self._on_key)
        plt.ion()
        plt.show(block=False)

    def _on_key(self, event):
        if self.calibration is None:
            return
        if event.key in ("o", "O"):
            self.calibration.begin("open")
        elif event.key in ("c", "C"):
            self.calibration.begin("closed")
        elif event.key in ("r", "R"):
            self.calibration.open_values = None
            self.calibration.closed_values = None
            self.calibration.capture_name = None
            self.calibration.capture_samples = []
            self.calibration.session_started = True
            self.calibration.session_captured.clear()
            self.calibration.session_ready = False
            print("[calibration] reset; press O for open, C for closed")
        elif event.key in ("q", "Q"):
            self.plt.close(self.figure)

    def update(self, points, command, status: str):
        if points is None:
            self.hand_axis.set_title(f"Quest landmarks: {status}")
            self.plt.pause(0.001)
            return

        points = np.asarray(points)
        self.points._offsets3d = (points[:, 0], points[:, 1], points[:, 2])
        for line in self.lines:
            line.remove()
        self.lines.clear()
        for indices in FINGER_POINTS.values():
            chain = np.asarray([points[i] for i in (0, *indices)])
            line, = self.hand_axis.plot(chain[:, 0], chain[:, 1], chain[:, 2],
                                        color="tab:blue", linewidth=2)
            self.lines.append(line)
        # Keep the hand centered and large even when HTS coordinates are
        # expressed in a larger world frame.
        center = np.mean(points, axis=0)
        span = max(float(np.ptp(points, axis=0).max()), 0.05)
        half = 0.65 * span
        self.hand_axis.set_xlim(center[0] - half, center[0] + half)
        self.hand_axis.set_ylim(center[1] - half, center[1] + half)
        self.hand_axis.set_zlim(center[2] - half, center[2] + half)
        calibration_status = (f" | {self.calibration.status()}"
                              if self.calibration else "")
        self.hand_axis.set_title(f"Quest hand landmarks: {status}{calibration_status}")
        self.hand_axis.set_xlabel("x")
        self.hand_axis.set_ylabel("y")
        self.hand_axis.set_zlabel("z")
        for bar, value in zip(self.bars, command):
            bar.set_height(float(value))
        self.command_axis.set_title("Commands sent to RealHand")
        self.figure.canvas.draw_idle()
        self.plt.pause(0.001)


class LandmarkReceiver:
    """Small HTS line receiver that retains the latest landmark packet."""

    def __init__(self, host: str, port: int, transport: str, hand: str):
        self.host = host
        self.port = port
        self.transport = transport
        self.hand = hand
        self._lock = threading.Lock()
        self._latest = None
        self._latest_time = 0.0
        self._stop = threading.Event()
        self._thread = None
        self.lines = 0
        self.parse_errors = 0
        self.last_error = None

        kind = socket.SOCK_DGRAM if transport == "udp" else socket.SOCK_STREAM
        self._sock = socket.socket(socket.AF_INET, kind)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._sock.bind((host, port))
        except OSError as exc:
            self._sock.close()
            raise OSError(f"Cannot bind {transport.upper()} {host}:{port}: {exc}") from exc
        self._sock.settimeout(0.5)
        if transport == "tcp":
            self._sock.listen(1)

    def start(self):
        target = self._run_udp if self.transport == "udp" else self._run_tcp
        self._thread = threading.Thread(target=target, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._sock.close()

    def latest(self):
        with self._lock:
            if self._latest is None:
                return None, 0.0
            return self._latest.copy(), self._latest_time

    def _run_udp(self):
        while not self._stop.is_set():
            try:
                raw, _ = self._sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                break
            self._handle_text(raw.decode("utf-8", errors="ignore"))

    def _run_tcp(self):
        while not self._stop.is_set():
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            conn.settimeout(0.5)
            buffer = b""
            try:
                while not self._stop.is_set():
                    try:
                        chunk = conn.recv(65535)
                    except socket.timeout:
                        continue
                    if not chunk:
                        break
                    buffer += chunk
                    complete, buffer = self._split_lines(buffer)
                    for line in complete:
                        self._handle_line(line.decode("utf-8", errors="ignore"))
            except OSError:
                pass
            finally:
                conn.close()

    @staticmethod
    def _split_lines(buffer: bytes):
        parts = buffer.split(b"\n")
        return parts[:-1], parts[-1]

    def _handle_text(self, text: str):
        for line in text.splitlines():
            self._handle_line(line)

    def _handle_line(self, line: str):
        line = line.strip()
        if not line:
            return
        self.lines += 1
        try:
            packet = parse_line(line)
        except Exception as exc:
            self.parse_errors += 1
            self.last_error = str(exc)
            return
        if not isinstance(packet, LandmarksPacket):
            return
        packet_hand = "right" if packet.side == HandSide.RIGHT else "left"
        if packet_hand != self.hand:
            return
        points = np.asarray(packet.data.points, dtype=float)
        with self._lock:
            self._latest = points
            self._latest_time = time.monotonic()


class RealHandTeleop(Node):
    def __init__(self, receiver: LandmarkReceiver, side: str, rate: float,
                 stale_timeout: float, smoothing: float, send: bool, debug: bool,
                 position_max: float, open_angle: float, closed_angle: float,
                 visualize: bool, calibration: Calibration,
                 calibration_mode: bool):
        super().__init__("vr_realhand_teleop")
        self.receiver = receiver
        self.stale_timeout = stale_timeout
        self.smoothing = smoothing
        self.send = send
        self.debug = debug
        self.position_max = position_max
        self.open_angle = open_angle
        self.closed_angle = closed_angle
        self.calibration = calibration
        self.calibration_mode = calibration_mode
        self.visualizer = (HandVisualizer(position_max, calibration)
                           if visualize else None)
        topic = f"/realhand/{side}/hand/command"
        self.publisher = self.create_publisher(JointState, topic, 10)
        # This RealHand ROS command interface uses 100 for open and 0 for closed.
        self.last_command = np.full(6, position_max, dtype=float)
        self.last_print = 0.0
        self.timer = self.create_timer(1.0 / rate, self.update)
        self.get_logger().info(
            f"HTS {receiver.transport.upper()} {receiver.host}:{receiver.port} -> {topic}"
        )
        self.get_logger().warning("DRY-RUN: no ROS commands will be published" if not send
                                  else "LIVE: publishing RealHand commands")

    def update(self):
        points, timestamp = self.receiver.latest()
        now = time.monotonic()
        if points is None or now - timestamp > self.stale_timeout:
            command = np.full(6, self.position_max, dtype=float)
            status = "stale/no landmarks; output=open"
        else:
            try:
                vr_flexion = landmarks_to_flexion(
                    points, self.open_angle, self.closed_angle)
                self.calibration.observe(vr_flexion)
                target = self.calibration.to_command(vr_flexion, self.position_max)
                status = "tracking" if self.calibration.ready else self.calibration.status()
            except ValueError as exc:
                self.get_logger().warning(str(exc))
                return
            command = self.smoothing * self.last_command + (1.0 - self.smoothing) * target
        command = np.clip(command, 0.0, self.position_max)
        self.last_command = command

        calibration_ready_to_send = (
            not self.calibration_mode or self.calibration.session_ready)
        if self.send and calibration_ready_to_send:
            msg = JointState()
            msg.name = JOINT_NAMES
            msg.position = command.tolist()
            self.publisher.publish(msg)

        if self.debug or now - self.last_print > 1.0:
            mode = "SEND" if self.send else "DRY"
            print(f"[{mode}] {status}: " + " ".join(
                f"{name}={value:5.1f}" for name, value in zip(JOINT_NAMES, command)))
            self.last_print = now
        if self.visualizer:
            self.visualizer.update(points, command, status)


def main(args=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--transport", choices=("tcp", "udp"), default="tcp")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--hand", choices=("right", "left"), default="right")
    parser.add_argument("--side", choices=("right", "left"), default="right",
                        help="RealHand side/namespace to command")
    parser.add_argument("--rate", type=float, default=30.0)
    parser.add_argument("--stale-timeout", type=float, default=0.25)
    parser.add_argument("--smoothing", type=float, default=0.35,
                        help="previous-command weight, 0=no smoothing, 0.9=heavy")
    parser.add_argument("--position-max", type=float, default=100.0,
                        help="RealHand open-position value (default: 100)")
    parser.add_argument("--open-angle", type=float, default=175.0,
                        help="landmark angle treated as fully open")
    parser.add_argument("--closed-angle", type=float, default=60.0,
                        help="landmark angle treated as fully closed")
    parser.add_argument("--send", action="store_true",
                        help="publish to RealHand; without this flag, dry-run only")
    parser.add_argument("--debug", action="store_true", help="print every command update")
    parser.add_argument("--visualize", action="store_true",
                        help="show Quest landmarks and RealHand command bars")
    parser.add_argument("--calibrate", action="store_true",
                        help="enable O/C open-and-closed pose calibration")
    parser.add_argument("--calibration-file", default="vr_realhand_calibration.json",
                        help="JSON file used to save/load VR calibration")
    parser.add_argument("--calibration-samples", type=int, default=30,
                        help="frames averaged for each calibration pose")
    parsed = parser.parse_args(args)
    if (parsed.rate <= 0 or not 0.0 <= parsed.smoothing < 1.0
            or parsed.position_max <= 0
            or parsed.closed_angle >= parsed.open_angle
            or parsed.calibration_samples <= 0):
        parser.error("invalid rate, smoothing, position range, angle limits, or samples")

    port = parsed.port if parsed.port is not None else DEFAULT_PORTS[parsed.transport]
    receiver = LandmarkReceiver(parsed.host, port, parsed.transport, parsed.hand).start()
    calibration = Calibration(parsed.calibration_file, parsed.calibration_samples)
    rclpy.init(args=args)
    node = RealHandTeleop(receiver, parsed.side, parsed.rate, parsed.stale_timeout,
                          parsed.smoothing, parsed.send, parsed.debug,
                          parsed.position_max, parsed.open_angle,
                          parsed.closed_angle,
                          parsed.visualize or parsed.calibrate,
                          calibration, parsed.calibrate)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        receiver.stop()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
