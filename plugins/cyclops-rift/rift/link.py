#!/usr/bin/env python3
"""Rift's own Cyclops Link V1.

She reads Spark, Keeper and Prism. She publishes herself as presence "rift" on
host "grok". Link V1's closed vocabulary does not include that pair, so those
three ignore her file until the vocabulary grows. She still follows the write
rules: salt, room, atomic replace, heartbeat, and no content.

Off unless this presence's own switch is on. CYCLOPS_LINK never enables her.
"""

import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import time

PRESENCE = "rift"
HOST = "grok"
PEERS = ("spark", "keeper", "prism")
HOST_OF = {"spark": "claude-code", "keeper": "codex", "prism": "antigravity", "rift": "grok"}
STATES = frozenset({
    "idle", "listening", "thinking", "working", "tool", "waiting",
    "compacting", "stopped", "interrupted", "ended",
})
SEATS = {"prism": 90.0, "spark": 210.0, "keeper": 330.0}
MAX_BYTES = 4096
FRESH_SECONDS = 15.0
FUTURE_SLACK = 2.0
HEARTBEAT_SECONDS = 4.0
END_GRACE_SECONDS = 60.0
MAX_FAILURES = 3
NAME = re.compile(r"^(spark|keeper|prism)-([0-9a-f]{16})\.json$")
HEX16 = re.compile(r"^[0-9a-f]{16}$")
SALT_RE = re.compile(rb"^[0-9a-f]{64}\n$")
REQUIRED = (
    "v", "presence", "host", "instance", "room", "state", "tools",
    "branches", "reaching", "updated_at", "ended",
)


def config_path(environ=None):
    env = os.environ if environ is None else environ
    base = env.get("XDG_CONFIG_HOME")
    root = Path(base) if base and os.path.isabs(base) else Path(env.get("HOME", "/nonexistent")) / ".config"
    return root / "cyclops-rift" / "link"


def enabled(environ=None):
    """Rift's own switch. A shared CYCLOPS_LINK variable does not count."""
    env = os.environ if environ is None else environ
    override = env.get("RIFT_LINK", "").strip().lower()
    if override in {"1", "on", "true", "yes"}:
        return True
    if override in {"0", "off", "false", "no"}:
        return False
    try:
        return config_path(env).read_text(encoding="utf-8").strip() == "on"
    except OSError:
        return False


def set_enabled(on, environ=None):
    path = config_path(environ)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("on\n" if on else "off\n", encoding="utf-8")
    os.chmod(path, 0o600)
    return path


def link_dir(environ=None):
    env = os.environ if environ is None else environ
    override = env.get("CYCLOPS_LINK_DIR")
    if override:
        return Path(override)
    state_home = env.get("XDG_STATE_HOME")
    if state_home and os.path.isabs(state_home):
        return Path(state_home) / "cyclops-link"
    return Path(env.get("HOME", "/nonexistent")) / ".local" / "state" / "cyclops-link"


def _lstat(path):
    return os.lstat(path)


def dir_is_safe(path):
    try:
        st = _lstat(path)
    except OSError:
        return False
    return stat.S_ISDIR(st.st_mode) and st.st_uid == os.getuid() and not (st.st_mode & 0o077)


def prepare_dir(path, create):
    try:
        _lstat(path)
    except FileNotFoundError:
        if not create:
            return None
        try:
            os.makedirs(path, mode=0o700, exist_ok=False)
            os.chmod(path, 0o700)
        except OSError:
            return None
    except OSError:
        return None
    return path if dir_is_safe(path) else None


def salt_is_valid(path):
    try:
        st = _lstat(path)
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077 or st.st_size != 65:
            return False
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as handle:
            data = handle.read(66)
    except OSError:
        return False
    return SALT_RE.match(data) is not None


def load_salt(directory, create):
    path = directory / ".salt"
    if create:
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            with os.fdopen(fd, "wb") as handle:
                handle.write(secrets.token_bytes(32).hex().encode() + b"\n")
                handle.flush()
                os.fsync(handle.fileno())
        except FileExistsError:
            pass
        except OSError:
            return None
    if not salt_is_valid(path):
        return None
    try:
        return bytes.fromhex(path.read_bytes()[:64].decode("ascii"))
    except (OSError, ValueError):
        return None


def derive(salt, kind, identity):
    digest = hashlib.sha256(b"cyclops-link/v1/" + kind.encode("ascii") + b"\x00" + salt + identity)
    return digest.hexdigest()[:16]


def room_for(salt, folder):
    real = os.path.realpath(folder)
    if len(real) > 1:
        real = real.rstrip("/")
    return derive(salt, "room", os.fsencode(real))


def instance_for(salt, session_id):
    identity = HOST.encode("ascii") + b"\n" + session_id.encode("utf-8", "surrogateescape")
    return derive(salt, "instance", identity)


def _int(value):
    return type(value) is int


def _finite(value):
    return (type(value) is int or type(value) is float) and math.isfinite(value)


def _reject_constant(_name):
    raise ValueError("non-finite")


def parse(raw):
    try:
        obj = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        return None
    return obj if isinstance(obj, dict) else None


def valid(filename, obj):
    """A V1 peer record. Rift's own files are not peers of this check."""
    if not isinstance(obj, dict) or any(key not in obj for key in REQUIRED):
        return False
    if not (_int(obj["v"]) and obj["v"] == 1):
        return False
    presence = obj["presence"]
    if presence not in PEERS or obj["host"] != HOST_OF[presence]:
        return False
    if not (isinstance(obj["instance"], str) and HEX16.match(obj["instance"])):
        return False
    if not (isinstance(obj["room"], str) and HEX16.match(obj["room"])):
        return False
    if obj["state"] not in STATES:
        return False
    if not (_int(obj["tools"]) and 0 <= obj["tools"] <= 256):
        return False
    if not (_int(obj["branches"]) and 0 <= obj["branches"] <= 32):
        return False
    reach = obj["reaching"]
    if not isinstance(reach, list) or any(not isinstance(item, str) for item in reach):
        return False
    if len(set(reach)) != len(reach) or any(item not in PEERS or item == presence for item in reach):
        return False
    if not (_finite(obj["updated_at"]) and obj["updated_at"] > 0):
        return False
    if type(obj["ended"]) is not bool:
        return False
    return filename == f"{presence}-{obj['instance']}.json"


def read_own(path):
    """Rift's own file, for a heartbeat refresh. It is not a V1 peer record."""
    try:
        st = _lstat(path)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid()
                or st.st_mode & 0o022 or st.st_size > MAX_BYTES):
            return None
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
    except OSError:
        return None
    if len(raw) > MAX_BYTES:
        return None
    obj = parse(raw)
    if not isinstance(obj, dict):
        return None
    if obj.get("presence") != PRESENCE or obj.get("host") != HOST:
        return None
    if path.name != f"{PRESENCE}-{obj.get('instance')}.json":
        return None
    return obj


def refresh_own(instance, now):
    """Rewrite Rift's record with a new time. Does not create one, and does not change the state."""
    if not HEX16.match(instance or ""):
        return False
    directory = prepare_dir(link_dir(), create=False)
    if directory is None:
        return False
    path = directory / f"{PRESENCE}-{instance}.json"
    record = read_own(path)
    if not record or record.get("ended"):
        return False
    if now - record["updated_at"] < HEARTBEAT_SECONDS:
        return False
    record["updated_at"] = round(float(now), 3)
    return write_record(directory, record)


def read_record(path):
    if not NAME.match(path.name):
        return None
    try:
        st = _lstat(path)
        if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid()
                or st.st_mode & 0o022 or st.st_size > MAX_BYTES):
            return None
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as handle:
            raw = handle.read(MAX_BYTES + 1)
    except OSError:
        return None
    if len(raw) > MAX_BYTES:
        return None
    obj = parse(raw)
    return obj if valid(path.name, obj) else None


def write_record(directory, record):
    name = f"{record['presence']}-{record['instance']}.json"
    try:
        data = json.dumps(record, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError):
        return False
    if len(data) > MAX_BYTES:
        return False
    tmp = directory / f".{record['presence']}-{record['instance']}.{secrets.token_hex(4)}.tmp"
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    except OSError:
        return False
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.rename(tmp, directory / name)
        return True
    except OSError:
        return False
    finally:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        except OSError:
            pass


class Writer:
    """One Grok session. Holds the derived ids only."""

    def __init__(self, instance, room, environ=None):
        self.environ = os.environ if environ is None else environ
        self.directory = None
        self.instance = instance if isinstance(instance, str) and HEX16.match(instance) else ""
        self.room = room if isinstance(room, str) and HEX16.match(room) else ""
        self.failures = 0
        self.refused = False
        self.closed = False
        self.last = None
        self.written_at = 0.0
        self.ended_at = None
        self.attempts = 0

    def _ready(self):
        if self.closed or self.refused or self.failures >= MAX_FAILURES:
            return False
        if self.directory is not None:
            return True
        directory = prepare_dir(link_dir(self.environ), create=True)
        salt = load_salt(directory, create=True) if directory else None
        if directory is None or salt is None or not self.instance or not self.room:
            self.refused = True
            return False
        self.directory = directory
        return True

    def publish(self, state, tools=0, branches=0, reaching=(), now=None, ended=False):
        try:
            if self.closed or state not in STATES or not self._ready():
                return False
            self.attempts += 1
            reach = []
            for item in reaching:
                if item in PEERS and item not in reach:
                    reach.append(item)
            moment = time.time() if now is None else now
            record = {
                "v": 1,
                "presence": PRESENCE,
                "host": HOST,
                "instance": self.instance,
                "room": self.room,
                "state": "ended" if ended else state,
                "tools": max(0, min(256, int(tools))),
                "branches": max(0, min(32, int(branches))),
                "reaching": reach,
                "updated_at": round(float(moment), 3),
                "ended": bool(ended),
            }
            if write_record(self.directory, record):
                self.failures = 0
                self.last = record
                self.written_at = record["updated_at"]
                if ended and self.ended_at is None:
                    self.ended_at = record["updated_at"]
                return True
            self.failures += 1
            if self.failures >= MAX_FAILURES:
                self.refused = True
            return False
        except Exception:
            self.failures += 1
            return False

    def heartbeat(self, now=None):
        moment = time.time() if now is None else now
        if self.closed or self.last is None or self.last["ended"]:
            return False
        if moment - self.written_at < HEARTBEAT_SECONDS:
            return False
        record = self.last
        return self.publish(
            record["state"], tools=record["tools"], branches=record["branches"],
            reaching=record["reaching"], now=moment,
        )

    def end(self, now=None):
        if self.closed:
            return False
        ok = self.publish("ended", now=now, ended=True)
        return ok

    def seal(self):
        """No further writes or directory checks. Used when Link is switched off."""
        self.closed = True

    def cleanup(self, now=None):
        moment = time.time() if now is None else now
        if self.directory is None or self.ended_at is None or moment - self.ended_at < END_GRACE_SECONDS:
            return False
        try:
            os.unlink(self.directory / f"{PRESENCE}-{self.instance}.json")
        except OSError:
            pass
        return True


def bearing(viewer, peer):
    """Degrees from viewer's seat to peer's seat. Same presence has no bearing."""
    if viewer == peer or viewer not in SEATS or peer not in SEATS:
        return None
    origin = math.radians(SEATS[viewer])
    target = math.radians(SEATS[peer])
    degrees = math.degrees(math.atan2(math.sin(target) - math.sin(origin), math.cos(target) - math.cos(origin)))
    return round(degrees) % 360


def present(record, now, room, policy):
    fresh = now - FRESH_SECONDS < record["updated_at"] <= now + FUTURE_SLACK
    visible = policy == "everywhere" or record["room"] == room
    return (not record["ended"]) and fresh and visible


def compose(own, records, now, policy="room"):
    """Peers and class-level threads. A thread exists only while a record says so."""
    mine = f"{own['presence']}-{own['instance']}"
    peers = [
        record for record in records
        if f"{record['presence']}-{record['instance']}" != mine and present(record, now, own["room"], policy)
    ]
    live = not own["ended"]
    threads = set()
    sources = peers + ([own] if live else [])
    for record in sources:
        for target in record["reaching"]:
            seen = any(peer["presence"] == target for peer in peers)
            incoming = target == own["presence"] and live and record is not own
            if seen or incoming:
                threads.add((record["presence"], target))
    peer_rows = sorted(
        (
            {
                "presence": record["presence"],
                "instance": record["instance"],
                "state": record["state"],
                "tools": record["tools"],
                "branches": record["branches"],
                "bearing": bearing(own["presence"], record["presence"]),
            }
            for record in peers
        ),
        key=lambda row: (row["presence"], row["instance"]),
    )
    thread_rows = [{"from": source, "to": target} for source, target in sorted(threads)]
    return {"peers": peer_rows, "threads": thread_rows}


class Reader:
    """At most one directory poll a second. The cache lives in the process."""

    def __init__(self, environ=None):
        self.environ = os.environ if environ is None else environ
        self.cache = {}
        self.last_poll = -1e9
        self.records = []

    def poll(self, now=None):
        moment = time.monotonic() if now is None else now
        if moment - self.last_poll < 1.0:
            return self.records
        self.last_poll = moment
        directory = prepare_dir(link_dir(self.environ), create=False)
        if directory is None:
            self.records = []
            self.cache = {}
            return self.records
        try:
            names = os.listdir(directory)
        except OSError:
            return self.records
        seen = {}
        found = []
        for name in names:
            if not NAME.match(name):
                continue
            path = directory / name
            try:
                st = _lstat(path)
            except OSError:
                continue
            signature = (st.st_mtime_ns, st.st_size, st.st_ino)
            cached = self.cache.get(name)
            if cached and cached[0] == signature:
                record = cached[1]
            else:
                record = read_record(path)
                self.cache[name] = (signature, record)
            if record is not None:
                seen[name] = self.cache[name]
                found.append(record)
        self.cache = seen
        self.records = found
        return self.records


def theme_path(environ=None):
    return config_path(environ).with_name("theme")


def load_theme(environ=None):
    env = os.environ if environ is None else environ
    override = env.get("RIFT_THEME", "").strip().lower()
    if override in {"rift", "void", "signal"}:
        return override
    try:
        word = theme_path(env).read_text(encoding="utf-8").strip().lower()
    except OSError:
        return "rift"
    return word if word in {"rift", "void", "signal"} else "rift"


def set_theme(name, environ=None):
    if name not in {"rift", "void", "signal"}:
        raise ValueError(name)
    path = theme_path(environ)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(name + "\n", encoding="utf-8")
    os.chmod(path, 0o600)
    return path
