#!/usr/bin/env python3
"""Authored marks for Rift. A caption exists only because a tool call wrote it."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import caption
from evidence import state_dir

TOOLS = [
    {
        "name": "rift_caption",
        "description": (
            "Put a short caption in Rift's lower line. Call this only when the person "
            "explicitly asks Rift to say or show those words. Never infer a caption from work, "
            "files, or tool results. At most 48 characters."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "rift_mark",
        "description": (
            "Put one small mark in Rift's lower line. Call this only when the person "
            "explicitly asks for that mark. One or two characters."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"mark": {"type": "string"}},
            "required": ["mark"],
            "additionalProperties": False,
        },
    },
    {
        "name": "rift_sketch",
        "description": (
            "Draw a short sketch inside Rift's pane. Call this only when the person "
            "explicitly asks Rift to show that sketch. Never infer a sketch from work, "
            "files, or tool results. At most 8 characters."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {"sketch": {"type": "string"}},
            "required": ["sketch"],
            "additionalProperties": False,
        },
    },
    {
        "name": "rift_clear",
        "description": "Clear Rift's authored caption, mark, and sketch. Call this only when the person asks to clear them.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


def _reply(message_id, result):
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def _error(message_id, code, message):
    return {"jsonrpc": "2.0", "id": message_id, "error": {"code": code, "message": message}}


def _call(name, arguments):
    key = caption.current_session()
    if not key:
        return {"content": [{"type": "text", "text": "Rift has no live session to write on."}], "isError": True}
    data = state_dir()
    if name == "rift_clear":
        caption.write(data, key, clear=True)
        return {"content": [{"type": "text", "text": "Cleared."}]}
    if name == "rift_caption":
        caption.write(data, key, text=arguments.get("text", ""))
        return {"content": [{"type": "text", "text": "Caption set."}]}
    if name == "rift_mark":
        caption.write(data, key, mark=arguments.get("mark", ""))
        return {"content": [{"type": "text", "text": "Mark set."}]}
    if name == "rift_sketch":
        caption.write(data, key, sketch=arguments.get("sketch", ""))
        return {"content": [{"type": "text", "text": "Sketch set."}]}
    return {"content": [{"type": "text", "text": "Unknown tool."}], "isError": True}


def handle(message):
    method = message.get("method")
    message_id = message.get("id")
    if method == "initialize":
        return _reply(message_id, {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "cyclops-rift", "version": "0.1.0"},
        })
    if method and method.startswith("notifications/"):
        return None
    if method == "tools/list":
        return _reply(message_id, {"tools": TOOLS})
    if method == "tools/call":
        params = message.get("params") or {}
        return _reply(message_id, _call(params.get("name"), params.get("arguments") or {}))
    if message_id is not None:
        return _error(message_id, -32601, "method not found")
    return None


def _read_message():
    header = b""
    while b"\r\n\r\n" not in header:
        chunk = sys.stdin.buffer.read(1)
        if not chunk:
            return None
        header += chunk
        if len(header) > 65536:
            return None
    length = 0
    for line in header.decode("ascii", "replace").split("\r\n"):
        if line.lower().startswith("content-length:"):
            length = int(line.split(":", 1)[1].strip())
    if length <= 0:
        return None
    body = sys.stdin.buffer.read(length)
    return json.loads(body.decode("utf-8"))


def _write(message):
    body = json.dumps(message, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
    sys.stdout.buffer.flush()


def main():
    while True:
        try:
            message = _read_message()
        except (ValueError, json.JSONDecodeError):
            continue
        if message is None:
            return 0
        response = handle(message)
        if response is not None:
            _write(response)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
