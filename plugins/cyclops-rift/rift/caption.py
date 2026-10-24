#!/usr/bin/env python3
"""Authored captions. Written only when something asks, never inferred."""

import json
import os
from pathlib import Path
import tempfile

from evidence import state_dir


def _path(directory, key):
    root = Path(directory) / "authored"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(root, 0o700)
    return root / f"{key}.json"


def _blank():
    return {"text": "", "mark": "", "sketch": ""}


def _sketch(value):
    """Keep spaces. Drop anything outside printable ASCII. Cap at 8."""
    if not isinstance(value, str):
        return ""
    return "".join(char for char in value if 32 <= ord(char) <= 126)[:8]


def read(directory, key):
    path = _path(directory, key)
    try:
        if path.is_symlink() or path.stat().st_size > 4096:
            return _blank()
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _blank()
    if not isinstance(value, dict):
        return _blank()
    text = value.get("text") if isinstance(value.get("text"), str) else ""
    mark = value.get("mark") if isinstance(value.get("mark"), str) else ""
    return {"text": text[:48], "mark": mark[:2], "sketch": _sketch(value.get("sketch"))}


def write(directory, key, text=None, mark=None, sketch=None, clear=False):
    current = _blank() if clear else read(directory, key)
    if text is not None:
        current["text"] = " ".join(str(text).split())[:48]
    if mark is not None:
        current["mark"] = " ".join(str(mark).split())[:2]
    if sketch is not None:
        current["sketch"] = _sketch(sketch)
    if clear:
        current = _blank()
    path = _path(directory, key)
    payload = json.dumps(
        {"v": 1, "text": current["text"], "mark": current["mark"], "sketch": current["sketch"]},
        separators=(",", ":"),
    )
    fd, name = tempfile.mkstemp(prefix=key + "-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
    return current


def remember_session(directory, key):
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / "current-session"
    fd, name = tempfile.mkstemp(prefix="current-", suffix=".tmp", dir=root)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(key + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def current_session(directory=None, environ=None):
    root = Path(directory) if directory else state_dir(environ)
    try:
        key = (root / "current-session").read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if len(key) == 16 and all(char in "0123456789abcdef" for char in key):
        return key
    return ""
