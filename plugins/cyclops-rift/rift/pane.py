#!/usr/bin/env python3
"""Draw Rift in her own tmux pane. She reads the scene the hooks already wrote."""

import fcntl
import os
from pathlib import Path
import re
import signal
import struct
import subprocess
import sys
import termios
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

import launch
import link
from evidence import fresh, load_scene, state_dir
from render import paint_side

KEY = re.compile(r"^[0-9a-f]{16}$")
_WINCH = False
_FITTED = None


def _size():
    """The pane's real size. A larger grid than this scrolls, and that scrolls as flicker."""
    try:
        packed = fcntl.ioctl(sys.stdout.fileno(), termios.TIOCGWINSZ, b"\0" * 8)
        rows, cols = struct.unpack("hh", packed[:4])
    except OSError:
        return 36, 24
    return max(1, cols), max(1, rows)


def _mode():
    if len(sys.argv) > 1 and sys.argv[1] in {"side", "top"}:
        return sys.argv[1]
    return "side"


def _mark_winch(_signum, _frame):
    global _WINCH
    _WINCH = True


def _refit(mode):
    """Keep her pane in proportion when the window changes. One try per size."""
    global _FITTED
    # TMUX_PANE is this process. The active pane may be Grok's, and a bare
    # resize-pane would shrink her instead.
    pane = os.environ.get("TMUX_PANE")
    if not os.environ.get("TMUX") or not pane:
        return
    try:
        text = subprocess.check_output(
            ["tmux", "display-message", "-t", pane, "-p",
             "#{window_width} #{window_height} #{pane_width} #{pane_height}"],
            text=True, stderr=subprocess.DEVNULL,
        ).split()
        window_w, window_h, pane_w, pane_h = (int(part) for part in text[:4])
    except (OSError, subprocess.CalledProcessError, ValueError, IndexError):
        return
    key = (mode, window_w, window_h)
    if key == _FITTED:
        return
    _FITTED = key
    flag, want = launch.fit_target(mode, window_w, window_h)
    current = pane_w if flag == "-x" else pane_h
    if want == current:
        return
    subprocess.run(
        ["tmux", "resize-pane", "-t", pane, flag, str(want)],
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _scene(data):
    try:
        key = (Path(data) / "current-session").read_text(encoding="utf-8").strip()
    except OSError:
        return fresh()
    if not KEY.fullmatch(key):
        return fresh()
    return load_scene(data, key)


def frame(grid):
    """One synchronized paint. Cells are overwritten in place, never erased first."""
    parts = ["\033[?2026h"]
    for y, row in enumerate(grid, start=1):
        parts.append(f"\033[{y};1H")
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
    parts.append("\033[1;1H\033[?2026l")
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
    mode = _mode()
    global _WINCH
    _WINCH = True
    signal.signal(signal.SIGWINCH, _mark_winch)
    sys.stdout.write("\033[?1049h\033[?25l\033[?7l\033[2J")
    sys.stdout.flush()
    last = None
    last_size = None
    try:
        while True:
            if _WINCH:
                _WINCH = False
                _refit(mode)
            cols, rows = _size()
            text = frame(paint_side(_scene(data), time.time(), theme, cols, rows))
            if text != last or (cols, rows) != last_size:
                if last_size is not None and (cols, rows) != last_size:
                    sys.stdout.write("\033[2J")
                sys.stdout.write(text)
                sys.stdout.flush()
                last = text
                last_size = (cols, rows)
            time.sleep(0.1)
    except KeyboardInterrupt:
        return 0
    finally:
        sys.stdout.write("\033[?7h\033[?25h\033[?1049l")
        sys.stdout.flush()


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.stdout.write("\033[?7h\033[?25h\033[?1049l")
        sys.exit(0)
