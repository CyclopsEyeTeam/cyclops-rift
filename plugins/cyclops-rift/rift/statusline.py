#!/usr/bin/env python3
"""Project the scene already recorded. This process does not invent events."""

import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

import caption
import link
from evidence import load_scene, session_key, state_dir
from render import ansi_rows, paint


def _folder_tag(folder):
    if not folder:
        return ""
    return hashlib.sha256(os.fsencode(folder)).hexdigest()[:16]


def _read_cache(path):
    try:
        if path.is_symlink() or path.stat().st_size > 65536:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def _write_cache(path, value):
    try:
        path.write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8")
        os.chmod(path, 0o600)
    except OSError:
        pass


def _view(session_id, folder, now, data):
    if not link.enabled() or not session_id:
        return [], []
    cache_path = Path(data) / "peer-cache.json"
    tag = _folder_tag(folder)
    cached = _read_cache(cache_path)
    if cached and cached.get("tag") == tag and now - float(cached.get("at", 0)) < 1.0:
        if now - float(cached.get("beat", 0)) >= link.HEARTBEAT_SECONDS and cached.get("instance"):
            link.refresh_own(cached["instance"], now)
            cached["beat"] = now
            _write_cache(cache_path, cached)
        return cached.get("peers") or [], cached.get("threads") or []
    directory = link.prepare_dir(link.link_dir(), create=False)
    salt = link.load_salt(directory, create=False) if directory else None
    if directory is None or salt is None:
        return [], []
    own = {
        "presence": link.PRESENCE,
        "instance": link.instance_for(salt, session_id),
        "room": link.room_for(salt, folder) if folder else "",
        "reaching": [],
        "ended": False,
    }
    scene = load_scene(data, session_key(session_id))
    own["reaching"] = [item for item in scene.get("reaching") or [] if item in link.PEERS]
    own["ended"] = bool(scene.get("ended"))
    records = link.Reader().poll(now=time.monotonic())
    view = link.compose(own, records, now, policy="room")
    _write_cache(cache_path, {
        "at": now, "beat": now, "tag": tag, "room": own["room"], "instance": own["instance"],
        "peers": view["peers"], "threads": view["threads"],
    })
    link.refresh_own(own["instance"], now)
    return view["peers"], view["threads"]


def render_payload(payload, now=None):
    now = time.time() if now is None else now
    session_id = ""
    folder = ""
    if isinstance(payload, dict):
        session_id = payload.get("session_id") or ""
        workspace = payload.get("workspace") if isinstance(payload.get("workspace"), dict) else {}
        folder = workspace.get("current_dir") or payload.get("cwd") or ""
        if not isinstance(folder, str):
            folder = ""
    data = state_dir()
    if session_id:
        scene = load_scene(data, session_key(session_id))
        authored = caption.read(data, session_key(session_id))
        peers, threads = _view(session_id, folder if link.enabled() else "", now, data)
    else:
        from evidence import fresh
        scene = fresh()
        authored = {"text": "", "mark": "", "sketch": ""}
        peers, threads = [], []
    width = 48
    try:
        width = max(24, min(96, int(os.environ.get("COLUMNS", "48"))))
    except ValueError:
        width = 48
    rows, footer, _theme = paint(
        scene, now, link.load_theme(), width, peers, threads,
        authored["text"], authored["mark"], authored.get("sketch") or "",
    )
    return ansi_rows(rows, footer)


def main():
    raw = sys.stdin.read()
    payload = {}
    if raw.strip():
        try:
            payload = json.loads(raw)
        except ValueError:
            payload = {}
    for line in render_payload(payload):
        sys.stdout.write(line + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
