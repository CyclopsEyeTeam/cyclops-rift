#!/usr/bin/env python3
"""Rift's evidence, picture, and Cyclops Link checks."""

import json
import math
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "rift"))

import caption
import link
from evidence import MAPPING, apply, fresh, length_at, narrow, session_key
from render import colors_used, load_sheet, mark_sheet, paint, paint_side, plain, warm
import bar
import pane
import launch
from session import Presence
import mcp_server
import statusline

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SALT_HEX = "6c696e6b2d76312d666978747572652d73616c742d6e6f742d612d7365637265"


def _env(root, link_on):
    env = os.environ.copy()
    env["HOME"] = str(root / "home")
    env["XDG_CONFIG_HOME"] = str(root / "config")
    env["XDG_STATE_HOME"] = str(root / "xdg")
    env["RIFT_STATE_DIR"] = str(root / "state")
    env["CYCLOPS_LINK_DIR"] = str(root / "link")
    env["RIFT_NO_BEAT"] = "1"
    env["RIFT_LINK"] = "1" if link_on else "0"
    env["CYCLOPS_LINK"] = "1"
    env.pop("RIFT_THEME", None)
    Path(env["HOME"]).mkdir(parents=True, exist_ok=True)
    return env


def _match(record, expect):
    return all(record.get(key) == value for key, value in expect.items())


class EvidenceTests(unittest.TestCase):
    def test_mapping_covers_every_event(self):
        named = {row[0] for row in MAPPING}
        for event in (
            "session.start", "turn.start", "tool.start", "tool.end", "tool.fail",
            "branch.start", "branch.end", "approval.request", "approval.resolved",
            "compact.start", "compact.end", "turn.end", "interrupt", "turn.fail",
            "idle.notice", "session.end",
        ):
            self.assertIn(event, named)

    def test_idle_clock_does_not_grow_a_filament(self):
        scene = fresh()
        before = json.dumps(scene)
        apply(scene, "nope", 50)
        self.assertEqual(json.dumps(scene), before)
        early = plain(*paint(scene, 10, "rift", 48)[:2])
        later = plain(*paint(scene, 80, "rift", 48)[:2])
        self.assertIn("◉", early[2])
        self.assertIn("◉", later[2])
        self.assertNotIn("∴", "\n".join(early))
        self.assertNotIn("✦", "\n".join(early))
        self.assertNotEqual(early[0], later[0])

    def test_turn_tool_branch_interrupt(self):
        scene = fresh()
        apply(scene, "turn.start", 10)
        self.assertEqual(scene["open"], 2)
        self.assertTrue(scene["nebula"])
        self.assertEqual(len(scene["filaments"]), 1)
        apply(scene, "tool.start", 11)
        self.assertEqual(scene["state"], "tool")
        self.assertEqual(scene["tools"], 1)
        drawn = plain(*paint(scene, 12, "rift", 48)[:2])
        self.assertIn("∴", "\n".join(drawn))
        apply(scene, "branch.start", 12)
        branched = plain(*paint(scene, 12.2, "rift", 56)[:2])
        self.assertIn("◦", "\n".join(branched))
        apply(scene, "tool.end", 13)
        self.assertEqual(scene["tools"], 0)
        self.assertTrue(scene["sparks"])
        spark = plain(*paint(scene, 13.1, "rift", 48)[:2])
        self.assertIn("✦", "\n".join(spark))
        self.assertEqual(length_at(scene["filaments"][1], 13.1) > 0, True)
        self.assertEqual(length_at(scene["filaments"][1], 14), 0)
        apply(scene, "tool.start", 15)
        apply(scene, "interrupt", 16)
        self.assertEqual(scene["state"], "interrupted")
        self.assertEqual(scene["tools"], 0)
        self.assertEqual(scene["open"], 1)
        self.assertFalse(scene["nebula"])
        self.assertGreater(length_at(scene["filaments"][-1], 16.1), 0)
        self.assertEqual(length_at(scene["filaments"][-1], 17), 0)
        red = colors_used(*paint(scene, 16.1, "rift", 48)[:2])
        self.assertTrue(any(warm(color) for color in red))
        calm = colors_used(*paint(scene, 20, "rift", 48)[:2])
        self.assertFalse(any(warm(color) for color in calm))

    def test_waiting_leaves_the_glass_empty(self):
        scene = fresh()
        apply(scene, "turn.start", 0)
        apply(scene, "approval.request", 1)
        rows, _, _ = paint(scene, 2, "rift", 56)
        row = "".join(cell[0] for cell in rows[2])
        self.assertIn("(◦◡◦)", row)
        self.assertNotIn("░", row)

    def test_compacting_is_one_stroke(self):
        scene = fresh()
        apply(scene, "turn.start", 0)
        apply(scene, "compact.start", 1)
        rows, _, theme = paint(scene, 2, "rift", 56)
        row = "".join(cell[0] for cell in rows[2])
        self.assertNotIn("░", row)
        self.assertIn("◉", row)
        bars = [cell for cell in rows[2] if cell[0] == "│" and cell[1] == theme["violet"]]
        self.assertEqual(len(bars), 1)

    def test_branch_aperture_counts_without_a_second_moon(self):
        scene = fresh()
        apply(scene, "turn.start", 0)
        apply(scene, "branch.start", 1)
        rows, _, _ = paint(scene, 2, "rift", 56)
        picture = "\n".join("".join(cell[0] for cell in row) for row in rows)
        self.assertIn("◦", picture)
        self.assertIn("·", "".join(cell[0] for cell in rows[0]))
        apply(scene, "branch.start", 2)
        rows, _, _ = paint(scene, 3, "rift", 56)
        picture = "\n".join("".join(cell[0] for cell in row) for row in rows)
        self.assertIn("2", picture)
        self.assertNotIn("◦", picture)

    def test_hood_breathes_between_trough_and_peak(self):
        peak = 3.6 * math.pi / 2
        trough = 3.6 * 3 * math.pi / 2
        high = paint(fresh(), peak, "rift", 48)[0][1][4]
        low = paint(fresh(), trough, "rift", 48)[0][1][4]
        self.assertEqual(high[0], "─")
        self.assertEqual(low[0], "─")
        self.assertNotEqual(high[1], low[1])

    def test_cut_reddens_eyes_and_leaves_the_smirk(self):
        scene = fresh()
        apply(scene, "turn.start", 10)
        apply(scene, "tool.start", 11)
        apply(scene, "interrupt", 16)
        rows, _, _ = paint(scene, 16.1, "rift", 48)
        self.assertTrue(any(warm(color) for color in colors_used(rows, [])))
        self.assertEqual(rows[2][4], ("◡", (168, 120, 214)))

    def test_four_tools_paint_a_digit(self):
        scene = fresh()
        apply(scene, "turn.start", 0)
        for moment in range(4):
            apply(scene, "tool.start", moment + 1)
        self.assertEqual(scene["tools"], 4)
        row = "".join(cell[0] for cell in paint(scene, 6, "rift", 56)[0][2])
        self.assertIn("4", row)

    def test_themes_stay_cool_until_a_cut(self):
        scene = fresh()
        apply(scene, "turn.start", 1)
        apply(scene, "tool.start", 2)
        for name in ("rift", "void", "signal"):
            colors = colors_used(*paint(scene, 3, name, 48)[:2])
            self.assertFalse(any(warm(color) for color in colors), name)

    def test_waiting_only_from_an_ask(self):
        scene = fresh()
        apply(scene, "turn.start", 0)
        apply(scene, "tool.start", 1)
        self.assertNotEqual(scene["state"], "waiting")
        apply(scene, "approval.request", 300)
        self.assertEqual(scene["state"], "waiting")
        apply(scene, "approval.resolved", 301)
        self.assertEqual(scene["state"], "tool")

    def test_narrow_drops_tool_input(self):
        payload = {
            "hook_event_name": "PreToolUse",
            "sessionId": "019a1c2e-7d3b-7f21-8a90-3b4c5d6e7f80",
            "cwd": "/home/alex/clients/acme-merger",
            "toolName": "mcp__vault__read_secret",
            "toolInput": {"command": "rm -rf /home/alex/.ssh", "password": "hunter2"},
            "peer_reach": "not-a-presence",
        }
        item = narrow(payload)
        self.assertEqual(item["event"], "tool.start")
        self.assertIsNone(item["peer_reach"])
        self.assertNotIn("toolInput", item)
        self.assertNotIn("hunter2", json.dumps({key: item[key] for key in ("event", "peer_reach")}))
        self.assertIsNone(narrow({"hook_event_name": "Notification", "notification_type": "task_complete", "sessionId": "a"}))

    def test_status_line_does_not_invent_a_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = _env(Path(tmp), False)
            old = os.environ.copy()
            os.environ.update(env)
            try:
                lines = statusline.render_payload({
                    "session_id": "live-session",
                    "prompt_id": "running",
                    "trigger": "refresh_interval",
                    "workspace": {"current_dir": "/tmp/does-not-matter"},
                }, now=100)
            finally:
                os.environ.clear()
                os.environ.update(old)
        text = "\n".join(lines)
        self.assertNotIn("∴", text)
        self.assertNotIn("◦", text)
        self.assertNotIn("✦", text)


class LinkTests(unittest.TestCase):
    def test_switch_is_per_presence(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = _env(Path(tmp), False)
            env["CYCLOPS_LINK"] = "1"
            env["RIFT_LINK"] = "0"
            self.assertFalse(link.enabled(env))
            env["RIFT_LINK"] = "1"
            self.assertTrue(link.enabled(env))

    def test_derivation_fixtures(self):
        data = json.loads((FIXTURES / "derivation.json").read_text(encoding="utf-8"))
        salt = bytes.fromhex(data["salt_hex"])
        for case in data["room"]:
            self.assertEqual(link.room_for(salt, case["project_identity"]), case["expect"], case["project_identity"])
        for case in data["instance"]:
            identity = case["host"].encode("ascii") + b"\n" + case["session_id"].encode("utf-8")
            self.assertEqual(link.derive(salt, "instance", identity), case["expect"])

    def test_record_fixtures(self):
        data = json.loads((FIXTURES / "records.json").read_text(encoding="utf-8"))
        for case in data["cases"]:
            if case.get("needs") == "other-uid":
                continue
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / case["filename"]
                kind = case["fs"]["type"]
                mode = int(case["fs"]["mode"], 8)
                if kind == "dir":
                    path.mkdir(mode=mode)
                elif kind == "symlink":
                    target = Path(tmp) / "target.json"
                    target.write_bytes(_case_bytes(case))
                    path.symlink_to(target)
                else:
                    path.write_bytes(_case_bytes(case))
                    os.chmod(path, mode)
                got = link.read_record(path)
                if case["expect"] == "valid":
                    self.assertIsNotNone(got, case["name"])
                else:
                    self.assertIsNone(got, case["name"])

    def test_ignored_names_are_not_peers(self):
        data = json.loads((FIXTURES / "records.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            os.chmod(root, 0o700)
            for name in data["ignored_names"]:
                (root / name).write_text("{}", encoding="utf-8")
            env = _env(root / "work", True)
            env["CYCLOPS_LINK_DIR"] = str(root)
            reader = link.Reader(env)
            self.assertEqual(reader.poll(now=0), [])

    def test_view_fixtures(self):
        data = json.loads((FIXTURES / "views.json").read_text(encoding="utf-8"))
        for case in data["scenarios"]:
            records = [
                item["record"] for item in case["files"]
                if link.valid(item["filename"], item["record"])
            ]
            got = link.compose(case["self"], records, case["now"], case["policy"])
            self.assertEqual(got, case["expect"], case["name"])

    def test_bearings(self):
        data = json.loads((FIXTURES / "views.json").read_text(encoding="utf-8"))
        for key, expect in data["bearings"].items():
            viewer, peer = key.split("->")
            self.assertEqual(link.bearing(viewer, peer), expect, key)

    def test_lifecycle_fixtures(self):
        data = json.loads((FIXTURES / "lifecycle.json").read_text(encoding="utf-8"))
        for case in data["scenarios"]:
            with self.subTest(case=case["name"]):
                self._lifecycle(case)

    def _lifecycle(self, case):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = _env(root, case["link"] == "on")
            link_dir = Path(env["CYCLOPS_LINK_DIR"])
            setup = case.get("setup", {}).get("LINK_DIR")
            if isinstance(setup, dict) and setup.get("mode") == "0777":
                link_dir.mkdir(parents=True)
                os.chmod(link_dir, 0o777)
            presence = Presence(
                "sess", "/tmp/rift-room", environ=env, data=root / "state",
                instance="ab" * 8, room="cd" * 8,
            )
            events = case["events"]
            marks = [item.get("by_t", 0) for item in case.get("expect", [])]
            marks += [item.get("at_t", 0) for item in case.get("expect", [])]
            marks += [item.get("after_t", 0) for item in case.get("expect", [])]
            end = max([0.0] + [event["t"] for event in events] + marks)
            index = 0
            cursor = 0.0
            sealed_failure = False
            while cursor <= end + 1e-9:
                while index < len(events) and events[index]["t"] <= cursor + 1e-9:
                    event = events[index]
                    if event["event"] == "link.off":
                        env["RIFT_LINK"] = "0"
                        presence.turn_link_off(event["t"])
                    else:
                        presence.event(event["event"], event["t"], peer_reach=event.get("peer_reach"))
                    if case["name"] == "write-failure-is-silent" and presence.history and not sealed_failure:
                        os.chmod(link_dir, 0o500)
                        sealed_failure = True
                    index += 1
                if link.enabled(env):
                    presence.heartbeat(cursor)
                cursor += 0.5
            for item in case.get("expect", []):
                if "file" in item:
                    presence.writer.cleanup(now=item["after_t"] + 1)
                    own = link_dir / f"rift-{presence.instance}.json"
                    self.assertFalse(own.exists(), case["name"])
                    continue
                if "by_t" in item:
                    found = [row for row in presence.history if row["updated_at"] <= item["by_t"] and _match(row, item["record"])]
                    self.assertTrue(found, (case["name"], item))
                if "at_t" in item:
                    prior = [row for row in presence.history if row["updated_at"] <= item["at_t"]]
                    self.assertTrue(prior, case["name"])
                    self.assertTrue(_match(prior[-1], item["record"]), (case["name"], prior[-1], item["record"]))
            if case["name"] == "off-by-default":
                self.assertFalse(link_dir.exists())
            if case["name"] == "link-turned-off":
                self.assertFalse(any(row["updated_at"] > 10.5 for row in presence.history))
            if case["name"] == "unsafe-directory":
                self.assertEqual(stat.S_IMODE(link_dir.stat().st_mode), 0o777)
                self.assertEqual(list(link_dir.iterdir()), [])
            if case["name"] == "write-failure-is-silent":
                self.assertLessEqual(presence.writer.attempts, 4)
                os.chmod(link_dir, 0o700)

    def test_rift_record_is_not_a_v1_peer(self):
        record = {
            "v": 1, "presence": "rift", "host": "grok", "instance": "ab" * 8, "room": "cd" * 8,
            "state": "idle", "tools": 0, "branches": 0, "reaching": [], "updated_at": 1, "ended": False,
        }
        self.assertFalse(link.valid(f"rift-{'ab' * 8}.json", record))

    def test_privacy_fixture_and_hook(self):
        data = json.loads((FIXTURES / "privacy.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = _env(root, True)
            salt_path = Path(env["CYCLOPS_LINK_DIR"])
            salt_path.mkdir(parents=True)
            os.chmod(salt_path, 0o700)
            (salt_path / ".salt").write_text(data["salt_hex"] + "\n", encoding="ascii")
            os.chmod(salt_path / ".salt", 0o600)
            salt = bytes.fromhex(data["salt_hex"])
            facts = data["host_facts"]
            presence = Presence(
                facts["session_id"], facts["cwd"], environ=env, data=root / "state",
                instance=link.instance_for(salt, facts["session_id"]),
                room=link.room_for(salt, facts["cwd"]),
            )
            for event in data["semantic_events"]:
                presence.event(event["event"], 10, peer_reach=event.get("peer_reach"))
            record = presence.history[-1]
            self.assertEqual(record["presence"], "rift")
            self.assertEqual(record["host"], "grok")
            self.assertEqual(record["state"], "tool")
            self.assertEqual(record["tools"], 1)
            self.assertEqual(record["reaching"], ["spark"])
            blob = json.dumps(record)
            rows, footer, _theme = paint(presence.scene, 11, "rift", 48)
            shown = "\n".join(plain(rows, footer))
            for secret in data["forbidden_substrings"]:
                self.assertNotIn(secret, blob)
                self.assertNotIn(secret, shown)
            hook_env = dict(env)
            hook_root = root / "hook"
            hook_env["RIFT_STATE_DIR"] = str(hook_root / "state")
            hook_env["CYCLOPS_LINK_DIR"] = str(hook_root / "link")
            hook = ROOT / "rift" / "hook.py"
            payload = {
                "hook_event_name": "PreToolUse",
                "sessionId": facts["session_id"],
                "cwd": facts["cwd"],
                "toolName": facts["tool_name"],
                "toolInput": {"command": facts["command"], "arguments": facts["arguments"]},
                "toolResponse": facts["tool_result"],
            }
            proc = subprocess.run(
                [sys.executable, str(hook)], input=json.dumps(payload), text=True,
                capture_output=True, env=hook_env, timeout=10,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, "")
            dumped = ""
            for folder in (root / "state", Path(env["CYCLOPS_LINK_DIR"]), hook_root):
                if not folder.exists():
                    continue
                for path in folder.rglob("*"):
                    if path.is_file():
                        dumped += path.read_text(encoding="utf-8", errors="replace")
            for secret in data["forbidden_substrings"]:
                self.assertNotIn(secret, dumped, secret)
            key = session_key(facts["session_id"])
            scene = json.loads((hook_root / "state" / "sessions" / f"{key}.json").read_text(encoding="utf-8"))
            self.assertEqual(scene["tools"], 1)
            self.assertNotIn("cwd", scene)

    def test_caption_stays_out_of_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = _env(root, True)
            old = os.environ.copy()
            os.environ.update(env)
            try:
                presence = Presence("sess", "/tmp/rift-room", environ=env, data=root / "state", instance="ab" * 8, room="cd" * 8)
                presence.event("turn.start", 1)
                caption.remember_session(root / "state", presence.key)
                caption.write(root / "state", presence.key, text="hello rift", mark="*", sketch="+=")
                record = json.dumps(presence.history[-1])
                self.assertNotIn("hello", record)
                self.assertNotIn("+=", record)
                lines = statusline.render_payload({"session_id": "sess"}, now=2)
            finally:
                os.environ.clear()
                os.environ.update(old)
        shown = "\n".join(lines)
        self.assertIn("hello rift", shown)
        self.assertIn("+", shown)
        self.assertIn("=", shown)

    def test_sheets_are_their_own(self):
        for name in ("spark", "keeper", "prism"):
            sheet = load_sheet(name)
            self.assertIsNotNone(sheet, name)
            self.assertIn("idle", sheet["frames"])
            self.assertEqual(sheet["presence"], name)

    def test_rift_sheet_matches_the_renderer(self):
        sheet = load_sheet("rift")
        made = mark_sheet()
        self.assertEqual(sheet["frames"], made["frames"])
        self.assertEqual(sheet["ascii"], made["ascii"])


class McpTests(unittest.TestCase):
    def test_caption_requires_a_session_and_a_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = _env(root, False)
            old = os.environ.copy()
            os.environ.update(env)
            try:
                refused = mcp_server._call("rift_caption", {"text": "guess"})
                self.assertTrue(refused.get("isError"))
                refused = mcp_server._call("rift_sketch", {"sketch": "+="})
                self.assertTrue(refused.get("isError"))
                caption.remember_session(root / "state", "ab" * 8)
                mcp_server._call("rift_caption", {"text": "kept on purpose"})
                stored = caption.read(root / "state", "ab" * 8)
                self.assertEqual(stored["text"], "kept on purpose")
                mcp_server._call("rift_clear", {})
                self.assertEqual(caption.read(root / "state", "ab" * 8)["text"], "")
                mcp_server._call("rift_sketch", {"sketch": "a  b"})
                self.assertEqual(caption.read(root / "state", "ab" * 8)["sketch"], "a  b")
                mcp_server._call("rift_sketch", {"sketch": "+=✦123456789"})
                self.assertEqual(caption.read(root / "state", "ab" * 8)["sketch"], "+=123456")
                bare = root / "state" / "authored" / ("cd" * 8 + ".json")
                bare.write_text('{"v":1,"text":"old","mark":""}', encoding="utf-8")
                self.assertEqual(caption.read(root / "state", "cd" * 8)["sketch"], "")
                mcp_server._call("rift_clear", {})
                self.assertEqual(caption.read(root / "state", "ab" * 8)["sketch"], "")
            finally:
                os.environ.clear()
                os.environ.update(old)


class SideTests(unittest.TestCase):
    def test_idle_aperture_does_not_reach(self):
        rows = paint_side(fresh(), 10, "rift", 36, 24)
        text = "\n".join("".join(cell[0] for cell in row) for row in rows)
        self.assertEqual(len(rows), 24)
        self.assertEqual(len(rows[0]), 36)
        self.assertIn("◉", text)
        self.assertNotIn("∴", text)
        self.assertNotIn("✦", text)
        self.assertFalse(any(warm(color) for color in colors_used(rows, [])))

    def test_turn_reaches_and_a_cut_is_red(self):
        scene = fresh()
        apply(scene, "turn.start", 10)
        text = "\n".join("".join(cell[0] for cell in row) for row in paint_side(scene, 12, "rift", 36, 24))
        self.assertIn("∴", text)
        self.assertFalse(any(warm(color) for color in colors_used(paint_side(scene, 12, "rift", 36, 24), [])))
        apply(scene, "interrupt", 13)
        colors = colors_used(paint_side(scene, 13.1, "rift", 36, 24), [])
        self.assertTrue(any(warm(color) for color in colors))

    def test_small_terminal_is_refused(self):
        with self.assertRaises(ValueError):
            launch.require_size("side", 80, 20)
        self.assertEqual(launch.split_args("side"), ["-h", "-l", "36"])
        self.assertEqual(launch.split_args("top")[:3], ["-b", "-v", "-l"])

    def test_private_side_pane_is_thirty_six_columns(self):
        if shutil.which("tmux") is None:
            self.skipTest("tmux is not installed")
        with tempfile.TemporaryDirectory() as tmp:
            sock = Path(tmp) / "rift.sock"
            config = Path(tmp) / "empty.conf"
            config.write_text("", encoding="utf-8")
            try:
                launch.open_private(
                    sock, "side", ["sleep", "20"], ["sleep", "20"],
                    120, 40, config=str(config),
                )
                width = subprocess.check_output(
                    ["tmux", "-S", str(sock), "-f", str(config), "display-message", "-p", "-t", "rift:0.1", "#{pane_width}"],
                    text=True,
                ).strip()
                marker = subprocess.check_output(
                    ["tmux", "-S", str(sock), "-f", str(config), "display-message", "-p", "-t", "rift:0.1", "#{@cyclops_rift}"],
                    text=True,
                ).strip()
                window = subprocess.check_output(
                    ["tmux", "-S", str(sock), "-f", str(config), "display-message", "-p", "-t", "rift", "#{window_name}"],
                    text=True,
                ).strip()
                left = subprocess.check_output(
                    ["tmux", "-S", str(sock), "-f", str(config), "show-options", "-t", "rift", "-v", "status-left"],
                    text=True,
                )
            finally:
                subprocess.run(["tmux", "-S", str(sock), "kill-server"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.assertEqual(width, "36")
        self.assertEqual(marker, "1")
        self.assertEqual(window, "grok")
        self.assertIn("rift", left)
        self.assertNotIn("python", left)

    def test_pane_frame_does_not_scroll(self):
        grid = paint_side(fresh(), 10, "rift", 36, 12)
        text = pane.frame(grid)
        self.assertNotIn("\n", text)
        self.assertIn("\033[1;1H", text)
        self.assertIn("\033[12;1H", text)

    def test_bar_token_is_state_only(self):
        self.assertEqual(bar.token(fresh(), 10), "◉")
        scene = fresh()
        apply(scene, "turn.start", 10)
        self.assertEqual(bar.token(scene, 12), "◉ working")
        apply(scene, "interrupt", 13)
        self.assertEqual(bar.token(scene, 13.1), "╱ cut")
        self.assertNotIn("/", bar.token(fresh(), 1))


def _case_bytes(case):
    if "raw_hex" in case:
        return bytes.fromhex(case["raw_hex"])
    if "raw" in case:
        return case["raw"].encode("utf-8")
    return json.dumps(case["record"]).encode("utf-8")


if __name__ == "__main__":
    unittest.main()
