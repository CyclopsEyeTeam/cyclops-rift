#!/usr/bin/env python3
"""One tmux status token from the scene. No paths, names, or prompts."""

from pathlib import Path
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

from evidence import RED_S, fresh, load_scene, state_dir

KEY = re.compile(r"^[0-9a-f]{16}$")
WORDS = {
    "working": "◉ working",
    "tool": "∴ tool",
    "waiting": "◉ waiting",
    "compacting": "◉ compacting",
    "interrupted": "╱ cut",
}


def token(scene, now):
    red = scene.get("red_at") is not None and 0 <= now - scene["red_at"] < RED_S
    state = scene.get("state") or "idle"
    if red and state in {"interrupted", "stopped"}:
        return "╱ cut"
    return WORDS.get(state, "◉")


def scene():
    try:
        key = (Path(state_dir()) / "current-session").read_text(encoding="utf-8").strip()
    except OSError:
        return fresh()
    if not KEY.fullmatch(key):
        return fresh()
    return load_scene(state_dir(), key)


def main():
    sys.stdout.write(token(scene(), time.time()))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.stdout.write("◉")
        sys.exit(0)
