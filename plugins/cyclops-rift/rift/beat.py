#!/usr/bin/env python3
"""Heartbeat for one linked session. It republishes the scene already on disk.

It does not read a project, a prompt, or a tool. If the host process is gone
it stops and leaves the record to go stale. Inactivity is not an end.
"""

import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

import link
from evidence import load_scene


def _alive(pid):
    if pid <= 1:
        return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def main(argv):
    if len(argv) != 5:
        return 0
    key, instance, room, pid_text, data = argv
    try:
        pid = int(pid_text)
    except ValueError:
        return 0
    writer = link.Writer(instance, room)
    started = time.time()
    while True:
        if not _alive(pid):
            return 0
        if not link.enabled():
            if writer.last and not writer.last["ended"]:
                writer.end(now=time.time())
            writer.seal()
            return 0
        scene = load_scene(data, key)
        now = time.time()
        if scene.get("ended"):
            writer.end(now=now)
            deadline = now + link.END_GRACE_SECONDS
            while time.time() < deadline:
                if not _alive(pid):
                    return 0
                time.sleep(1)
            writer.cleanup(now=time.time())
            return 0
        if writer.last is None:
            writer.publish(
                scene["state"], tools=scene["tools"], branches=scene["branches"],
                reaching=scene["reaching"], now=now, ended=False,
            )
        else:
            writer.heartbeat(now=now)
            if writer.refused:
                return 0
        if time.time() - started > 7 * 24 * 3600:
            return 0
        time.sleep(1)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception:
        sys.exit(0)
