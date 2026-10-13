#!/usr/bin/env python3
"""Repeat operator-selected keys through the official teleop_twist_keyboard PTY.

No ROS subscriptions, mapping logic, route selection or feedback control.
Write a fresh command atomically to .runtime/teleop_command.json after startup:
  {"id": "move-001", "key": "i", "duration": 3.0}
Allowed keys: i (forward), , (backward), j/l (turn), k (stop).
Each held key is repeated at 10 Hz by default, then k is sent. A new command
interrupts the current hold. Commands already present at startup are ignored.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import errno
import json
import math
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import time


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_command(path: Path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, UnicodeError, json.JSONDecodeError):
        # Atomic replacements are recommended; incomplete writes are retried.
        return None


def command_id(command):
    identifier = command.get("id") if command else None
    if isinstance(identifier, bool) or not isinstance(identifier, (str, int)):
        return None
    return str(identifier) if str(identifier) else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--speed", type=float, default=0.22)
    parser.add_argument("--turn", type=float, default=0.4)
    parser.add_argument("--repeat-hz", type=float, default=10.0)
    args = parser.parse_args()
    for name, value in [("speed", args.speed), ("turn", args.turn), ("repeat-hz", args.repeat_hz)]:
        if not math.isfinite(value) or value <= 0:
            parser.error(f"--{name} must be a finite positive number")
    project = args.project.expanduser().resolve()
    runtime = project / ".runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    command_path = runtime / "teleop_command.json"
    state_path = runtime / "teleop_bridge_state.json"
    transcript_path = runtime / "teleop_command_transcript.jsonl"
    log_path = runtime / "teleop_keyboard.log"
    period = 1.0 / args.repeat_hz
    seen = set()
    existing_id = command_id(read_command(command_path))
    if existing_id is not None:
        seen.add(existing_id)
    active = None
    stopping = False

    def stop_requested(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, stop_requested)
    signal.signal(signal.SIGTERM, stop_requested)

    def write_state(value):
        temporary = state_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        temporary.replace(state_path)

    def record(event):
        event = {"timestamp_utc": utc_now(), **event}
        with transcript_path.open("a", encoding="utf-8") as transcript:
            transcript.write(json.dumps(event) + "\n")
            transcript.flush()

    master, slave = pty.openpty()
    process = None
    keyboard_log = log_path.open("ab", buffering=0)

    def send_key(key):
        os.write(master, key.encode("ascii"))

    def finish_active(status, reason):
        nonlocal active
        if active is None:
            return
        send_key("k")
        state = {"id": active["id"], "key": active["key"], "status": status,
                 "requested_duration_seconds": active["duration"],
                 "elapsed_wall_seconds": max(0.0, time.monotonic() - active["started_monotonic"]),
                 "key_repetitions": active["repetitions"], "reason": reason,
                 "finished_at_utc": utc_now()}
        write_state(state)
        record({"event": "command_finished", **state})
        active = None

    try:
        command = ["ros2", "run", "teleop_twist_keyboard", "teleop_twist_keyboard",
                   "--ros-args", "-p", f"speed:={args.speed:g}", "-p", f"turn:={args.turn:g}"]
        process = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave,
                                   close_fds=True, start_new_session=True)
        os.close(slave)
        slave = -1
        os.set_blocking(master, False)
        ready = {"id": None, "status": "ready", "child_pid": process.pid,
                 "speed": args.speed, "turn": args.turn, "repeat_hz": args.repeat_hz,
                 "ignored_startup_command_id": existing_id,
                 "started_at_utc": utc_now()}
        write_state(ready)
        record({"event": "bridge_started", "command": command, **ready})
        print(f"Keyboard bridge ready; official teleop child PID {process.pid}.", flush=True)
        print(f"Submit fresh operator commands to {command_path}.", flush=True)

        while not stopping:
            if process.poll() is not None:
                raise RuntimeError(f"Official keyboard teleop exited with status {process.returncode}")
            now = time.monotonic()
            pending = read_command(command_path)
            identifier = command_id(pending)
            if identifier is not None and identifier not in seen:
                seen.add(identifier)
                finish_active("interrupted", "operator submitted a new command")
                key = pending.get("key")
                duration = pending.get("duration", 0.0)
                valid_duration = (not isinstance(duration, bool)
                                  and isinstance(duration, (int, float))
                                  and math.isfinite(duration) and 0 <= duration <= 30)
                if key not in ("i", "j", "l", ",", "k") or not valid_duration:
                    send_key("k")
                    rejection = {"id": identifier, "status": "rejected",
                                 "reason": "Require key i/j/l/,/k and finite duration 0..30 seconds"}
                    write_state(rejection)
                    record({"event": "command_rejected", **rejection})
                elif key == "k" or duration == 0:
                    send_key("k")
                    stopped = {"id": identifier, "key": key, "status": "done",
                               "elapsed_wall_seconds": 0.0, "finished_at_utc": utc_now()}
                    write_state(stopped)
                    record({"event": "operator_stop", **stopped})
                else:
                    active = {"id": identifier, "key": key, "duration": float(duration),
                              "started_monotonic": now, "deadline": now + float(duration),
                              "next_repeat": now, "repetitions": 0}
                    state = {"id": identifier, "key": key, "status": "running",
                             "requested_duration_seconds": float(duration),
                             "started_at_utc": utc_now()}
                    write_state(state)
                    record({"event": "operator_command", **state})
            now = time.monotonic()
            if active is not None:
                if now >= active["deadline"]:
                    finish_active("done", "operator-selected hold duration completed")
                elif now >= active["next_repeat"]:
                    send_key(active["key"])
                    active["repetitions"] += 1
                    # Avoid a burst of accumulated keys after a scheduler stall.
                    active["next_repeat"] = now + period
            timeout = 0.025
            if active is not None:
                timeout = min(timeout, max(0.0, active["deadline"] - time.monotonic()),
                              max(0.0, active["next_repeat"] - time.monotonic()))
            readable, _, _ = select.select([master], [], [], timeout)
            if readable:
                try:
                    data = os.read(master, 65536)
                    if data:
                        keyboard_log.write(data)
                except OSError as error:
                    if error.errno not in (errno.EIO, errno.EAGAIN):
                        raise
        finish_active("interrupted", "keyboard bridge stopped by operator")
        send_key("k")
        return 0
    except Exception as error:
        write_state({"id": active["id"] if active else None,
                     "status": "error", "reason": str(error), "finished_at_utc": utc_now()})
        record({"event": "bridge_error", "reason": str(error)})
        print(str(error), file=sys.stderr)
        return 1
    finally:
        if process is not None and process.poll() is None:
            try:
                send_key("k")
                # Give official teleop time to consume the final stop key.
                time.sleep(0.1)
                os.killpg(process.pid, signal.SIGINT)
                process.wait(timeout=4)
            except (ProcessLookupError, subprocess.TimeoutExpired, OSError):
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait(timeout=2)
        record({"event": "bridge_stopped", "child_returncode": process.poll() if process else None})
        keyboard_log.close()
        if slave >= 0:
            os.close(slave)
        os.close(master)


if __name__ == "__main__":
    raise SystemExit(main())
