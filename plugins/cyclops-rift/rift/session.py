#!/usr/bin/env python3
"""Apply one finite event, then publish the coarse Link record if Link is on."""

import os
from pathlib import Path

import link
from evidence import apply, fresh, load_scene, save_scene, session_key, state_dir


class Presence:
    def __init__(self, session_id, folder, environ=None, data=None, instance=None, room=None):
        self.environ = os.environ if environ is None else environ
        self.data = Path(data) if data else state_dir(self.environ)
        self.session_id = session_id or ""
        self.key = session_key(self.session_id) if self.session_id else "0" * 16
        self.folder = folder or ""
        self.instance = instance or ""
        self.room = room or ""
        self.writer = None
        self.history = []
        self.scene = load_scene(self.data, self.key) if self.session_id else fresh()

    def _writer(self, now):
        if self.writer is not None:
            return self.writer
        if not link.enabled(self.environ):
            return None
        directory = link.prepare_dir(link.link_dir(self.environ), create=True)
        salt = link.load_salt(directory, create=True) if directory else None
        if directory is None or salt is None:
            self.writer = link.Writer("", "", self.environ)
            self.writer.refused = True
            return self.writer
        instance = self.instance or link.instance_for(salt, self.session_id or "rift-session")
        room = self.room or (link.room_for(salt, self.folder) if self.folder else "0" * 16)
        self.instance = instance
        self.room = room
        self.writer = link.Writer(instance, room, self.environ)
        self.writer.directory = directory
        return self.writer

    def event(self, name, now, peer_reach=None):
        apply(self.scene, name, now, peer_reach=peer_reach)
        if self.session_id:
            save_scene(self.data, self.key, self.scene)
        self._publish(now)
        return self.scene

    def _publish(self, now):
        if not link.enabled(self.environ):
            if self.writer and self.writer.last and not self.writer.last["ended"] and not self.writer.closed:
                self.writer.end(now=now)
                self.history.append(dict(self.writer.last))
                self.writer.seal()
            return
        writer = self._writer(now)
        if writer is None or writer.closed or writer.refused:
            return
        writer.publish(
            self.scene["state"],
            tools=self.scene["tools"],
            branches=self.scene["branches"],
            reaching=self.scene["reaching"],
            now=now,
            ended=self.scene["ended"],
        )
        if writer.last:
            self.history.append(dict(writer.last))

    def heartbeat(self, now):
        if not link.enabled(self.environ):
            return False
        writer = self._writer(now)
        if writer is None:
            return False
        ok = writer.heartbeat(now=now)
        if ok and writer.last:
            self.history.append(dict(writer.last))
        return ok

    def turn_link_off(self, now):
        if self.writer and self.writer.last and not self.writer.last["ended"] and not self.writer.closed:
            self.writer.end(now=now)
            if self.writer.last:
                self.history.append(dict(self.writer.last))
        if self.writer:
            self.writer.seal()
