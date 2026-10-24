#!/usr/bin/env python3
"""Open Grok with Rift beside her.

From an ordinary terminal this starts a private tmux server. Inside tmux it
adds one pane and leaves every existing setting alone. Grok exiting closes
only that pane. Closing the pane leaves Grok.
"""

import os
from pathlib import Path
import shlex
import shutil
import stat
import subprocess
import sys

# Preferred picture. She shrinks below this on a narrow row and grows a little
# on a wide one, always leaving Grok a pane she can work in.
SIDE_PREF = 36
SIDE_FLOOR = 20
SIDE_CAP = 48
TOP_PREF = 16
TOP_FLOOR = 12
TOP_CAP = 24
MIN_SIDE = (56, 14)
MIN_TOP = (40, 18)

ROOT = Path(__file__).resolve().parent
PANE = ROOT / "pane.py"


def require_size(mode, columns, rows):
    need_x, need_y = MIN_SIDE if mode == "side" else MIN_TOP
    if columns < need_x or rows < need_y:
        raise ValueError(
            f"Rift {mode} needs a terminal of {need_x}x{need_y}. This one is {columns}x{rows}."
        )


def side_cols(columns):
    """Her pane, in columns. 36 once Grok can keep a long row."""
    room = max(0, int(columns) - 1)
    if room >= SIDE_PREF + 60:
        extra = min(SIDE_CAP - SIDE_PREF, (room - SIDE_PREF - 60) // 5)
        return SIDE_PREF + extra
    leave = min(48, max(24, room - SIDE_FLOOR))
    return max(SIDE_FLOOR, min(SIDE_PREF, room - leave))


def top_rows(rows):
    """Her band, in rows. 16 once Grok still has a stack of lines under it."""
    room = max(0, int(rows))
    if room >= TOP_PREF + 10:
        extra = min(TOP_CAP - TOP_PREF, (room - TOP_PREF - 10) // 4)
        return TOP_PREF + extra
    leave = min(10, max(6, room - TOP_FLOOR))
    return max(TOP_FLOOR, min(TOP_PREF, room - leave))


def split_args(mode, columns, rows):
    if mode == "top":
        return ["-b", "-v", "-l", str(top_rows(rows))]
    return ["-h", "-l", str(side_cols(columns))]


def fit_target(mode, columns, rows):
    """tmux resize flag and the size her pane should be for this window."""
    if mode == "top":
        return "-y", top_rows(rows)
    return "-x", side_cols(columns)


def _tmux(sock, config, *args, check=True):
    command = ["tmux", "-S", str(sock)]
    if config:
        command.extend(["-f", config])
    command.extend(args)
    result = subprocess.run(command, text=True, capture_output=True)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "tmux failed").strip()
        raise RuntimeError(detail)
    return result


def open_private(sock, mode, host_argv, pane_argv, columns, rows, config=None, session="rift"):
    """Detached private server. The caller attaches. Does not touch other tmux servers."""
    require_size(mode, columns, rows)
    sock = Path(sock)
    sock.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    host = shlex.join(list(host_argv))
    pane = shlex.join(list(pane_argv))
    _tmux(
        sock, config, "new-session", "-d", "-s", session,
        "-x", str(columns), "-y", str(rows), host,
    )
    try:
        created = _tmux(
            sock, config, "split-window", "-d", "-t", f"{session}:0.0",
            *split_args(mode, columns, rows), "-P", "-F", "#{pane_id}", pane,
        )
        rift = created.stdout.strip().splitlines()[-1]
        _tmux(sock, config, "set-option", "-p", "-t", rift, "@cyclops_rift", "1")
        _tmux(sock, config, "set-option", "-p", "-t", rift, "remain-on-exit", "off")
        dress(sock, config, session)
        _tmux(sock, config, "select-pane", "-t", f"{session}:0.0")
    except Exception:
        _tmux(sock, config, "kill-server", check=False)
        raise
    return rift


def dress(sock, config, session):
    """Session-only chrome. Never a global tmux option."""
    bar = shlex.quote(str(ROOT / "bar.py"))
    right = f"#({sys.executable} {bar})"
    options = {
        "status": "on",
        "status-interval": "1",
        "status-style": "bg=#0c0e12,fg=#67d0dc",
        "status-left-length": "20",
        "status-right-length": "24",
        "status-left": "#[fg=#a878d8,bg=#0c0e12] ▏#[fg=#e8fbff,bg=#0c0e12] ◉ #[fg=#8fdff0,bg=#0c0e12]rift ",
        "status-right": f"#[fg=#8fdff0,bg=#0c0e12]{right} ",
        "window-status-format": "",
        "window-status-current-format": "#[fg=#0c0e12,bg=#67d0dc] grok #[fg=#a878d8,bg=#0c0e12]▏",
        "automatic-rename": "off",
        "pane-border-style": "fg=#3c3158",
        "pane-active-border-style": "fg=#8fdff0",
        "status-justify": "left",
    }
    for key, value in options.items():
        _tmux(sock, config, "set-option", "-t", session, key, value)
    _tmux(sock, config, "rename-window", "-t", session, "grok")


def _owned_server(socket_path):
    path = Path(socket_path)
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        raise ValueError("refusing a symlinked tmux socket")
    if info.st_uid != os.getuid():
        raise ValueError("refusing a tmux socket owned by someone else")
    if info.st_mode & 0o077:
        raise ValueError("refusing a tmux socket other people can open")


def split_into_current(mode, pane_argv):
    """One new pane in the tmux the user is already in. No global options."""
    if not os.environ.get("TMUX"):
        raise ValueError("not inside tmux")
    socket_path = subprocess.check_output(
        ["tmux", "display-message", "-p", "#{socket_path}"], text=True
    ).strip()
    _owned_server(socket_path)
    size = subprocess.check_output(
        ["tmux", "display-message", "-p", "#{window_width} #{window_height}"], text=True
    ).split()
    require_size(mode, int(size[0]), int(size[1]))
    source = os.environ.get("TMUX_PANE") or subprocess.check_output(
        ["tmux", "display-message", "-p", "#{pane_id}"], text=True
    ).strip()
    result = subprocess.run(
        ["tmux", "split-window", "-d", "-t", source, *split_args(mode, int(size[0]), int(size[1])), "-P", "-F", "#{pane_id}", shlex.join(pane_argv)],
        text=True, capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or "could not split").strip())
    rift = result.stdout.strip().splitlines()[-1]
    subprocess.run(["tmux", "set-option", "-p", "-t", rift, "@cyclops_rift", "1"], check=False)
    subprocess.run(["tmux", "set-option", "-p", "-t", rift, "remain-on-exit", "off"], check=False)
    subprocess.run(["tmux", "select-pane", "-t", source], check=False)
    return rift


def close_owned(pane_id):
    if not pane_id:
        return
    listed = subprocess.run(
        ["tmux", "list-panes", "-F", "#{pane_id} #{@cyclops_rift}"],
        text=True, capture_output=True,
    )
    if listed.returncode != 0:
        return
    for line in listed.stdout.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == pane_id and parts[1] == "1":
            subprocess.run(["tmux", "kill-pane", "-t", pane_id], check=False)
            return


def run_host(grok_argv):
    """Inside the private session: run Grok, then close only the pane we marked."""
    deadline = 5.0
    import time
    rift = ""
    started = time.monotonic()
    while time.monotonic() - started < deadline and not rift:
        listed = subprocess.run(
            ["tmux", "list-panes", "-F", "#{pane_id} #{@cyclops_rift}"],
            text=True, capture_output=True,
        )
        for line in listed.stdout.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1] == "1":
                rift = parts[0]
                break
        else:
            time.sleep(0.05)
    code = subprocess.call(list(grok_argv))
    close_owned(rift)
    return code


def _grok_bin():
    found = shutil.which("grok")
    if found:
        return found
    home = Path.home() / ".local" / "bin" / "grok"
    if home.is_file():
        return str(home)
    raise ValueError("grok is not on PATH")


def _mode(argv):
    if argv and argv[0] in {"side", "top"}:
        return argv[0], argv[1:]
    return "side", argv


def main(argv):
    if argv and argv[0] == "--host":
        return run_host(argv[1:])
    mode, rest = _mode(argv)
    if rest[:1] == ["--"]:
        rest = rest[1:]
    try:
        grok = _grok_bin()
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    pane_argv = [sys.executable, str(PANE), mode]
    if os.environ.get("TMUX"):
        try:
            rift = split_into_current(mode, pane_argv)
        except (ValueError, RuntimeError) as exc:
            print(exc, file=sys.stderr)
            return 2
        code = subprocess.call([grok, *rest])
        close_owned(rift)
        return code
    size = shutil.get_terminal_size(fallback=(80, 24))
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/cyclops-rift-{os.getuid()}")
    sock = runtime / f"cyclops-rift-{os.getpid()}.sock"
    host_argv = [sys.executable, str(ROOT / "launch.py"), "--host", grok, *rest]
    try:
        open_private(sock, mode, host_argv, pane_argv, size.columns, size.lines)
    except (ValueError, RuntimeError) as exc:
        print(exc, file=sys.stderr)
        return 2
    code = subprocess.call(["tmux", "-S", str(sock), "attach", "-t", "rift"])
    still = subprocess.run(
        ["tmux", "-S", str(sock), "has-session", "-t", "rift"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if still.returncode == 0:
        print(f"Detached. Grok is still running. Reattach: tmux -S {sock} attach -t rift")
    else:
        try:
            sock.unlink()
        except OSError:
            pass
    return code


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        sys.exit(130)
