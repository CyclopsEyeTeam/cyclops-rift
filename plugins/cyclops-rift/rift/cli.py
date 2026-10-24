#!/usr/bin/env python3
"""rift link on | off | status, rift theme, rift preview."""

import copy
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

import link
from evidence import apply, fresh
from render import ansi_rows, paint


def _status():
    state = "on" if link.enabled() else "off"
    print(f"Cyclops Link: {state}")
    print(f"Theme: {link.load_theme()}")
    print("Rift publishes presence rift on host grok.")
    print("Spark, Keeper and Prism speak Link V1, which does not list that pair, so they do not draw her yet.")
    print("She draws them, in their own marks, when they are in this folder and Link is on.")
    if not link.enabled():
        print("Off: she does not create the Link directory, and she does not read the others.")
    return 0


def _preview():
    scene = fresh()
    moment = time.time()
    frames = [("rest", copy.deepcopy(scene), moment)]
    apply(scene, "turn.start", moment + 1)
    frames.append(("turn", copy.deepcopy(scene), moment + 1.5))
    apply(scene, "tool.start", moment + 2)
    frames.append(("tool", copy.deepcopy(scene), moment + 2.6))
    apply(scene, "branch.start", moment + 3)
    frames.append(("branch", copy.deepcopy(scene), moment + 3.2))
    apply(scene, "tool.end", moment + 4)
    frames.append(("return", copy.deepcopy(scene), moment + 4.1))
    apply(scene, "branch.end", moment + 4.4)
    apply(scene, "interrupt", moment + 5)
    frames.append(("interrupt", copy.deepcopy(scene), moment + 5.1))
    theme = link.load_theme()
    for label, shot, when in frames:
        # copy so later events don't rewrite earlier frames
        print(f"\033[2m{label}\033[0m")
        rows, footer, _theme = paint(shot, when, theme, 56)
        for line in ansi_rows(rows, footer):
            print(line)
        print()
    print("Preview uses scripted events. A live session moves only when Grok emits the same events.")
    return 0


def main(argv):
    word = argv[0] if argv else "status"
    if word == "link":
        action = argv[1] if len(argv) > 1 else "status"
        if action == "on":
            path = link.set_enabled(True)
            print(f"Rift Link on. Switch: {path}")
            print("She shares coarse state only: no prompts, paths, names, or tool arguments.")
            return 0
        if action == "off":
            path = link.set_enabled(False)
            print(f"Rift Link off. Switch: {path}")
            return 0
        if action == "status":
            return _status()
    if word == "theme" and len(argv) > 1:
        link.set_theme(argv[1])
        print(f"Theme: {argv[1]}")
        return 0
    if word == "preview":
        return _preview()
    if word == "status":
        return _status()
    print("usage: rift link [on|off|status] | rift theme rift|void|signal | rift preview")
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except ValueError as exc:
        print(str(exc))
        sys.exit(2)
