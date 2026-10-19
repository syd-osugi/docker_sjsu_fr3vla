#!/usr/bin/env python3
"""
vr_pose_listener.py - listener for the Quest Hand Tracking Streamer.

Receives the text stream from the headset app, parses the wrist packets with
hand_tracking_sdk and prints position + orientation.

Transports (must match the headset app's protocol setting):
  tcp  - this script is the TCP *server* (default port 8000). Use this with
         USB:  adb reverse tcp:8000 tcp:8000   and app IP 127.0.0.1, port 8000.
  udp  - this script binds a UDP port (default 9000). Use this over Wi-Fi with
         the app pointed at this computer's LAN IP (see `hostname -I`).

Examples:
  python vr_pose_listener.py                            # tcp, port 8000, right hand
  python vr_pose_listener.py --transport udp            # udp, port 9000
  python vr_pose_listener.py --hand both --frame robot
  python vr_pose_listener.py --debug                    # also show raw lines + parse errors

Or import and use:
  from vr_pose_listener import VRPoseListener
  listener = VRPoseListener(transport="tcp", port=8000, frame="robot").start()
  pose = listener.latest("right")   # dict(pos, quat, rot, t) or None

Frames:
  vr    - raw Unity left-handed frame, as sent by the headset.
  robot - converted to the robot FLU frame (x forward, y left, z up)

Requires: numpy, scipy, hand-tracking-sdk
"""
import argparse
import socket
import threading
import time

import numpy as np
from scipy.spatial.transform import Rotation

from hand_tracking_sdk.models import HandSide, WristPacket
from hand_tracking_sdk.parser import parse_line

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORTS = {"udp": 9000, "tcp": 8000}

# LeVR coordinate transform: Unity left-hand -> FLU robot base frame
C_VR_TO_ROBOT = np.array([
    [0.0, 0.0, 1.0],
    [-1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
])


def to_robot_frame(pos, rot):
    """Convert a VR-frame (position, rotation matrix) to the robot FLU frame."""
    return C_VR_TO_ROBOT @ pos, C_VR_TO_ROBOT @ rot @ C_VR_TO_ROBOT.T


class VRPoseListener:
    """Background listener. Latest wrist pose per hand is in .latest()."""

    def __init__(self, host=DEFAULT_HOST, port=None, transport="tcp",
                 frame="vr", debug=False):
        if transport not in DEFAULT_PORTS:
            raise ValueError("transport must be 'tcp' or 'udp'")
        self.transport = transport
        self.frame = frame
        self.debug = debug
        self.host = host
        self.port = port if port is not None else DEFAULT_PORTS[transport]

        self._lock = threading.Lock()
        self._latest = {}            # "right"/"left" -> dict(pos, quat, rot, t)
        self._stop = threading.Event()
        self._thread = None
        self._debug_left = 5         # raw lines to echo in debug mode

        # Diagnostics
        self.connected = False       # tcp: a headset is connected
        self.lines = 0               # lines received
        self.wrist_packets = 0       # wrist packets parsed
        self.parse_errors = 0
        self.last_error = None

        if transport == "udp":
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        else:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if transport == "tcp":
            # Lets the server restart right away. Not set for UDP: it would let
            # two receivers silently share a port and split the packets.
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self._sock.bind((self.host, self.port))
        except OSError as exc:
            self._sock.close()
            raise OSError(
                f"Cannot bind {transport.upper()} {self.host}:{self.port} ({exc}). "
                "Is another receiver (visualizer, SDK example, ROS node) using it?"
            ) from exc
        self._sock.settimeout(0.5)
        if transport == "tcp":
            self._sock.listen(1)

    # ------------------------------------------------------------------ control
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

    def latest(self, hand="right"):
        """Return dict(pos[3], quat[x,y,z,w], rot[3x3], t) or None if nothing received."""
        with self._lock:
            return self._latest.get(hand)

    # ---------------------------------------------------------------- receiving
    def _run_udp(self):
        while not self._stop.is_set():
            try:
                raw, _ = self._sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            for line in raw.decode("utf-8", errors="ignore").splitlines():
                self._handle_line(line)

    def _run_tcp(self):
        while not self._stop.is_set():
            try:
                conn, addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self.connected = True
            if self.debug:
                print(f"[tcp] headset connected from {addr}")
            conn.settimeout(0.5)
            buf = b""
            try:
                while not self._stop.is_set():
                    try:
                        chunk = conn.recv(4096)
                    except socket.timeout:
                        continue
                    if not chunk:           # headset closed the connection
                        break
                    buf += chunk
                    # A TCP stream can split a line across reads: keep the tail.
                    *complete, buf = buf.split(b"\n")
                    for raw_line in complete:
                        self._handle_line(raw_line.decode("utf-8", errors="ignore"))
            except OSError:
                pass
            finally:
                conn.close()
                self.connected = False
                if self.debug:
                    print("[tcp] headset disconnected, waiting for reconnect")

    def _handle_line(self, line):
        line = line.strip()
        if not line:
            return
        self.lines += 1
        if self.debug and self._debug_left > 0:
            self._debug_left -= 1
            print(f"[raw] {line[:120]}")
        try:
            pkt = parse_line(line)
        except Exception as exc:
            self.parse_errors += 1
            self.last_error = f"{exc} | line: {line[:80]!r}"
            return
        if not isinstance(pkt, WristPacket):
            return
        self.wrist_packets += 1
        w = pkt.data
        pos = np.array([w.x, w.y, w.z])
        rot = Rotation.from_quat([w.qx, w.qy, w.qz, w.qw]).as_matrix()
        if self.frame == "robot":
            pos, rot = to_robot_frame(pos, rot)
        quat = Rotation.from_matrix(rot).as_quat()   # x, y, z, w
        hand = "right" if pkt.side == HandSide.RIGHT else "left"
        with self._lock:
            self._latest[hand] = {"pos": pos, "quat": quat, "rot": rot,
                                  "t": time.monotonic()}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--transport", choices=["tcp", "udp"], default="tcp")
    ap.add_argument("--hand", choices=["right", "left", "both"], default="right")
    ap.add_argument("--frame", choices=["vr", "robot"], default="vr")
    ap.add_argument("--host", default=DEFAULT_HOST, help="address to listen on")
    ap.add_argument("--port", type=int, default=None,
                    help="default: 8000 for tcp, 9000 for udp")
    ap.add_argument("--rate", type=float, default=10.0, help="print rate in Hz")
    ap.add_argument("--debug", action="store_true",
                    help="echo first raw lines, connection events and parse errors")
    args = ap.parse_args()

    hands = ["right", "left"] if args.hand == "both" else [args.hand]
    listener = VRPoseListener(host=args.host, port=args.port,
                              transport=args.transport, frame=args.frame,
                              debug=args.debug).start()
    print(f"Listening on {args.transport.upper()} {listener.host}:{listener.port} "
          f"({args.frame} frame). Ctrl+C to quit.")
    try:
        while True:
            time.sleep(1.0 / args.rate)
            for h in hands:
                s = listener.latest(h)
                if s is None:
                    if args.transport == "tcp":
                        state = "headset connected" if listener.connected else "waiting for headset"
                    else:
                        state = "waiting for packets"
                    extra = ""
                    if listener.parse_errors:
                        extra = (f" | {listener.parse_errors} parse errors, last: "
                                 f"{listener.last_error}")
                    print(f"{h:>5}: no data ({state}; {listener.lines} lines){extra}")
                    continue
                p, q = s["pos"], s["quat"]
                rpy = Rotation.from_quat(q).as_euler("xyz", degrees=True)
                print(f"{h:>5}: pos [{p[0]:+.3f} {p[1]:+.3f} {p[2]:+.3f}] m | "
                      f"quat xyzw [{q[0]:+.3f} {q[1]:+.3f} {q[2]:+.3f} {q[3]:+.3f}] | "
                      f"rpy [{rpy[0]:+.1f} {rpy[1]:+.1f} {rpy[2]:+.1f}] deg | "
                      f"age {1000 * (time.monotonic() - s['t']):.0f} ms")
    except KeyboardInterrupt:
        pass
    finally:
        listener.stop()


if __name__ == "__main__":
    main()