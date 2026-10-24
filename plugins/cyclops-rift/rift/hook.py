#!/usr/bin/env python3
"""Grok hook. Reads one event, keeps a handful of fields, writes the scene.

Stdout stays empty. A decision is never returned. Tool arguments are never stored.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

import caption
import link
from evidence import narrow, session_key, state_dir
from session import Presence


def _comm(pid):
    try:
        return Path(f"/proc/{pid}/comm").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def host_pid():
    pid = os.getppid()
    seen = set()
    while pid > 1 and pid not in seen:
        seen.add(pid)
        if "grok" in _comm(pid):
            return pid
        try:
            text = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
            pid = int(text[text.rindex(")") + 2:].split()[1])
        except (OSError, ValueError, IndexError):
            break
    return os.getppid()


def _beat(key, instance, room, data):
    if os.environ.get("RIFT_NO_BEAT"):
        return
    pid_path = Path(data) / "beats" / f"{key}.pid"
    try:
        old = int(pid_path.read_text(encoding="utf-8").strip())
        os.kill(old, 0)
        return
    except (OSError, ValueError):
        pass
    pid_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    script = Path(__file__).resolve().parent / "beat.py"
    proc = subprocess.Popen(
        [sys.executable, str(script), key, instance, room, str(host_pid()), str(data)],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    pid_path.write_text(str(proc.pid) + "\n", encoding="utf-8")
    os.chmod(pid_path, 0o600)


def main():
    raw = sys.stdin.read()
    if not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except ValueError:
        return 0
    item = narrow(payload)
    del payload
    if not item or not item["session_id"]:
        return 0
    data = state_dir()
    caption.remember_session(data, session_key(item["session_id"]))
    folder = item["cwd"] if link.enabled() else ""
    presence = Presence(item["session_id"], folder, data=data)
    presence.event(item["event"], time.time(), peer_reach=item["peer_reach"])
    if link.enabled() and presence.instance and presence.room and not presence.scene.get("ended"):
        _beat(presence.key, presence.instance, presence.room, data)
    if presence.scene.get("ended") and presence.writer:
        presence.writer.cleanup(now=time.time())
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
