#!/usr/bin/env python3
"""Evidence in, a rift scene out.

Nothing in this module is a clock that pretends to work. Breathing and the
slow drift are drawn later, from the wall clock alone. Every other change is
one of the events in MAPPING.
"""

import hashlib
import json
import os
from pathlib import Path
import tempfile

OPEN_REST = 1
OPEN_MAX = 3
SPARK_S = 0.45
RED_S = 0.70
SEVER_S = 0.55
EXTEND_S = 0.40
RETRACT_S = 0.45

# event, evidence kept, what the picture is allowed to do
MAPPING = (
    ("session.start", "a session file at rest", "aperture at a slit, no filament"),
    ("turn.start", "open +1, nebula on, one turn filament", "aperture opens one step, one filament reaches"),
    ("tool.start", "one filament born on a lane", "filament extends and holds"),
    ("tool.end", "that filament marked gone, one spark time", "filament retracts, spark at the aperture"),
    ("tool.fail", "tool.end plus a red time", "retract, short red cut"),
    ("branch.start", "branches +1", "a secondary rift, linked while the count is above zero"),
    ("branch.end", "branches -1", "that secondary rift leaves"),
    ("approval.request", "waiting", "no new motion; link state waiting"),
    ("approval.resolved", "waiting cleared", "returns to the state the counts still support"),
    ("compact.start", "compacting", "no new motion"),
    ("compact.end", "compacting cleared", "no new motion"),
    ("turn.end", "live filaments severed, open -1, nebula off", "filaments sever, aperture closes one step"),
    ("interrupt", "turn.end plus a red time", "sever, close one step, short red cut"),
    ("turn.fail", "turn.end plus a red time", "sever, close one step, short red cut"),
    ("idle.notice", "state idle when nothing is in flight", "no motion"),
    ("session.end", "ended, open 0", "aperture shuts"),
    ("peer.reach", "a presence word on a tool that is in flight", "a link thread, and only while that call lasts"),
)


def fresh():
    return {
        "v": 1,
        "open": OPEN_REST,
        "nebula": False,
        "turn": False,
        "state": "idle",
        "tools": 0,
        "branches": 0,
        "reaching": [],
        "reach_stack": [],
        "filaments": [],
        "sparks": [],
        "red_at": None,
        "waiting": False,
        "compacting": False,
        "ended": False,
    }


def _clamp_open(scene):
    if scene["ended"]:
        scene["open"] = 0
    else:
        scene["open"] = max(OPEN_REST, min(OPEN_MAX, scene["open"]))


def _settle(scene):
    if scene["ended"]:
        scene["state"] = "ended"
        return
    if scene["compacting"]:
        scene["state"] = "compacting"
        return
    if scene["waiting"]:
        scene["state"] = "waiting"
        return
    if scene["tools"] > 0:
        scene["state"] = "tool"
        return
    if scene["turn"]:
        scene["state"] = "working"
        return
    if scene["state"] == "interrupted":
        return
    if scene["state"] not in {"stopped", "idle", "interrupted"}:
        scene["state"] = "idle"


def _prune(scene, now):
    kept = []
    for filament in scene["filaments"]:
        gone = filament.get("gone")
        if gone is None:
            kept.append(filament)
            continue
        limit = SEVER_S if filament.get("severed") else RETRACT_S
        if now - gone < limit + 0.05:
            kept.append(filament)
    scene["filaments"] = kept
    scene["sparks"] = [moment for moment in scene["sparks"] if now - moment < 2.0]


def _sever(scene, now):
    for filament in scene["filaments"]:
        if filament.get("gone") is None:
            filament["gone"] = now
            filament["severed"] = True
    scene["tools"] = 0
    scene["reaching"] = []
    scene["reach_stack"] = []
    scene["turn"] = False
    scene["nebula"] = False
    scene["waiting"] = False


def _pop_tool(scene, now, spark):
    if scene["tools"] > 0:
        scene["tools"] -= 1
    for filament in scene["filaments"]:
        if filament.get("kind") == "tool" and filament.get("gone") is None:
            filament["gone"] = now
            filament["severed"] = False
            break
    if scene["reach_stack"]:
        scene["reach_stack"].pop()
    scene["reaching"] = _reaching(scene["reach_stack"])
    if spark:
        scene["sparks"].append(now)


def _reaching(stack):
    found = []
    for item in stack:
        if item and item not in found:
            found.append(item)
    return found


def apply(scene, event, now, peer_reach=None):
    """Fold one finite event into the scene. Unknown events change nothing."""
    _prune(scene, now)
    if event == "session.start":
        if scene["ended"]:
            return scene
        _settle(scene)
        return scene
    if event == "turn.start":
        scene["ended"] = False
        scene["turn"] = True
        scene["nebula"] = True
        scene["waiting"] = False
        scene["state"] = "working"
        if scene["open"] < OPEN_MAX:
            scene["open"] += 1
        scene["filaments"].append({
            "kind": "turn", "lane": "turn", "born": now, "gone": None,
            "severed": False, "length": 3,
        })
        _settle(scene)
        return scene
    if event == "tool.start":
        scene["tools"] = min(256, scene["tools"] + 1)
        lane = (scene["tools"] - 1) % 3
        scene["filaments"].append({
            "kind": "tool", "lane": lane, "born": now, "gone": None,
            "severed": False, "length": 4 + lane,
        })
        word = peer_reach if peer_reach in {"spark", "keeper", "prism"} else None
        scene["reach_stack"].append(word)
        scene["reaching"] = _reaching(scene["reach_stack"])
        _settle(scene)
        return scene
    if event in {"tool.end", "tool.fail"}:
        _pop_tool(scene, now, spark=True)
        if event == "tool.fail":
            scene["red_at"] = now
        _settle(scene)
        return scene
    if event == "branch.start":
        scene["branches"] = min(32, scene["branches"] + 1)
        return scene
    if event == "branch.end":
        scene["branches"] = max(0, scene["branches"] - 1)
        return scene
    if event == "approval.request":
        scene["waiting"] = True
        _settle(scene)
        return scene
    if event == "approval.resolved":
        scene["waiting"] = False
        _settle(scene)
        return scene
    if event == "compact.start":
        scene["compacting"] = True
        _settle(scene)
        return scene
    if event == "compact.end":
        scene["compacting"] = False
        _settle(scene)
        return scene
    if event == "turn.end":
        _sever(scene, now)
        scene["open"] = max(OPEN_REST, scene["open"] - 1)
        scene["state"] = "stopped"
        return scene
    if event == "interrupt":
        _sever(scene, now)
        scene["open"] = max(OPEN_REST, scene["open"] - 1)
        scene["red_at"] = now
        scene["state"] = "interrupted"
        return scene
    if event == "turn.fail":
        _sever(scene, now)
        scene["open"] = max(OPEN_REST, scene["open"] - 1)
        scene["red_at"] = now
        scene["state"] = "stopped"
        return scene
    if event == "idle.notice":
        if not scene["turn"] and scene["tools"] == 0 and not scene["waiting"] and not scene["compacting"]:
            if scene["state"] != "interrupted":
                scene["state"] = "idle"
        return scene
    if event == "session.end":
        _sever(scene, now)
        scene["ended"] = True
        scene["open"] = 0
        scene["state"] = "ended"
        scene["compacting"] = False
        return scene
    return scene


def session_key(session_id):
    return hashlib.sha256(b"cyclops-rift/session/" + session_id.encode("utf-8", "surrogateescape")).hexdigest()[:16]


def state_dir(environ=None):
    env = os.environ if environ is None else environ
    override = env.get("RIFT_STATE_DIR")
    if override:
        return Path(override)
    state_home = env.get("XDG_STATE_HOME")
    if state_home and os.path.isabs(state_home):
        root = Path(state_home)
    else:
        root = Path(env.get("HOME", "/nonexistent")) / ".local" / "state"
    return root / "cyclops-rift"


def _private(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    return path


def scene_path(directory, key):
    return _private(Path(directory) / "sessions") / f"{key}.json"


def load_scene(directory, key):
    path = scene_path(directory, key)
    try:
        if path.is_symlink() or path.stat().st_size > 65536:
            return fresh()
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fresh()
    if not isinstance(value, dict) or value.get("v") != 1:
        return fresh()
    scene = fresh()
    scene.update({item: value[item] for item in scene if item in value})
    scene["v"] = 1
    return scene


def save_scene(directory, key, scene):
    root = _private(Path(directory))
    os.chmod(root, 0o700)
    directory = _private(root / "sessions")
    payload = json.dumps(scene, separators=(",", ":"), allow_nan=False).encode("utf-8")
    fd, name = tempfile.mkstemp(prefix=key + "-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(name, 0o600)
        os.replace(name, directory / f"{key}.json")
    finally:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass


def length_at(filament, now):
    """How much of a filament is drawn. Zero means it is not on screen."""
    born = filament["born"]
    gone = filament.get("gone")
    full = filament["length"]
    if filament.get("severed"):
        if gone is None or now - gone > SEVER_S or now < gone:
            return 0
        return full
    if gone is None:
        grown = 0.0 if now <= born else min(1.0, (now - born) / EXTEND_S)
        return max(0, round(full * grown))
    if now < gone:
        return 0
    grown = min(1.0, max(0.0, (gone - born) / EXTEND_S))
    shrink = min(1.0, (now - gone) / RETRACT_S)
    return max(0, round(full * grown * (1.0 - shrink)))


GROK_EVENTS = {
    "SessionStart": "session.start",
    "session_start": "session.start",
    "UserPromptSubmit": "turn.start",
    "user_prompt_submit": "turn.start",
    "PreToolUse": "tool.start",
    "pre_tool_use": "tool.start",
    "PostToolUse": "tool.end",
    "post_tool_use": "tool.end",
    "PostToolUseFailure": "tool.fail",
    "post_tool_use_failure": "tool.fail",
    "Stop": "turn.end",
    "stop": "turn.end",
    "StopCancelled": "interrupt",
    "stop_cancelled": "interrupt",
    "StopFailure": "turn.fail",
    "stop_failure": "turn.fail",
    "SubagentStart": "branch.start",
    "subagent_start": "branch.start",
    "SubagentStop": "branch.end",
    "subagent_stop": "branch.end",
    "PreCompact": "compact.start",
    "pre_compact": "compact.start",
    "PostCompact": "compact.end",
    "post_compact": "compact.end",
    "SessionEnd": "session.end",
    "session_end": "session.end",
}

NOTIFICATIONS = {
    "permission_prompt": "approval.request",
    "idle_prompt": "idle.notice",
}


def narrow(payload):
    """The only fields a Grok hook may keep. Tool input is not among them."""
    if not isinstance(payload, dict):
        return None
    name = payload.get("hook_event_name") or payload.get("hookEventName") or ""
    event = GROK_EVENTS.get(name)
    if name in {"Notification", "notification"}:
        kind = payload.get("notification_type") or payload.get("notificationType") or ""
        event = NOTIFICATIONS.get(kind)
    if event is None:
        return None
    reach = payload.get("peer_reach")
    if reach not in {"spark", "keeper", "prism"}:
        reach = None
    session = payload.get("session_id") or payload.get("sessionId") or ""
    folder = payload.get("cwd") if isinstance(payload.get("cwd"), str) else ""
    return {"event": event, "peer_reach": reach, "session_id": session, "cwd": folder}
