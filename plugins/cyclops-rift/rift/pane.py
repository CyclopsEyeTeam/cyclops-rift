#!/usr/bin/env python3
"""Draw Rift in her own tmux pane. She reads the scene the hooks already wrote."""

import fcntl
import os
from pathlib import Path
import re
import struct
import sys
import termios
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

import link
from evidence import fresh, load_scene, state_dir
from render import paint_side

KEY = re.compile(r"^[0-9a-f]{16}$")


def _size():
    packed = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, b"\0" * 8)
    rows, cols = struct.unpack("hh", packed[:4])
    return max(20, cols), max(12, rows)


def _scene(data):
    try:
        key = (Path(data) / "current-session").read_text(encoding="utf-8").strip()
    except OSError:
        return fresh()
    if not KEY.fullmatch(key):
        return fresh()
    return load_scene(data, key)


def frame(grid):
    """Place each row with a cursor address. A newline at the bottom row scrolls the pane."""
    parts = ["\033[?7l"]
    for y, row in enumerate(grid, start=1):
        parts.append(f"\033[{y};1H\033[2K")
        current = None
        for char, color in row:
            if color != current:
                if color is None:
                    parts.append("\033[0m")
                else:
                    parts.append(f"\033[38;2;{color[0]};{color[1]};{color[2]}m")
                current = color
            parts.append(char)
        if current is not None:
            parts.append("\033[0m")
    parts.append("\033[?7h")
    return "".join(parts)


def _emit(grid):
    sys.stdout.write(frame(grid))
    sys.stdout.flush()


def main():
    data = state_dir()
    theme = link.load_theme()
    if not sys.stdout.isatty():
        grid = paint_side(_scene(data), time.time(), theme, 36, 24)
        _emit(grid)
        return 0
    sys.stdout.write("\033[?1049h\033[?25l\033[2J")
    sys.stdout.flush()
    try:
        while True:
            cols, rows = _size()
            _emit(paint_side(_scene(data), time.time(), theme, cols, rows))
            time.sleep(0.12)
    except KeyboardInterrupt:
        return 0
    finally:
        sys.stdout.write("\033[?25h\033[?1049l")
        sys.stdout.flush()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.stdout.write("\033[?25h\033[?1049l")
        sys.exit(0)
