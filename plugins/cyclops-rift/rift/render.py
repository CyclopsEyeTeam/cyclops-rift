#!/usr/bin/env python3
"""Draw Rift from a scene. The clock may breathe and drift. It may not invent work."""

import math
from pathlib import Path

from evidence import RED_S, SEVER_S, SPARK_S, length_at

THEMES = {
    "rift": {
        "edge": (186, 244, 255),
        "edge_dim": (64, 128, 146),
        "violet": (168, 120, 214),
        "core": (8, 10, 14),
        "filament": (96, 206, 214),
        "star": (42, 72, 86),
        "nebula": (78, 52, 118),
        "spark": (226, 252, 255),
        "red": (214, 58, 68),
        "thread": (132, 104, 176),
        "secondary": (140, 210, 220),
        "strand": (90, 190, 255),
        "cloth": (36, 48, 64),
        "screen": (120, 230, 190),
    },
    "void": {
        "edge": (62, 78, 84),
        "edge_dim": (22, 28, 32),
        "violet": (42, 36, 58),
        "core": (0, 0, 0),
        "filament": (32, 48, 54),
        "star": (16, 20, 24),
        "nebula": (18, 14, 26),
        "spark": (120, 128, 132),
        "red": (148, 42, 48),
        "thread": (36, 32, 44),
        "secondary": (48, 64, 70),
        "strand": (40, 70, 90),
        "cloth": (18, 22, 28),
        "screen": (48, 72, 64),
    },
    "signal": {
        "edge": (244, 255, 255),
        "edge_dim": (0, 206, 220),
        "violet": (196, 80, 255),
        "core": (0, 0, 0),
        "filament": (0, 255, 255),
        "star": (0, 132, 156),
        "nebula": (104, 0, 168),
        "spark": (255, 255, 255),
        "red": (255, 36, 56),
        "thread": (176, 0, 255),
        "secondary": (0, 255, 255),
        "strand": (80, 220, 255),
        "cloth": (20, 28, 40),
        "screen": (180, 255, 220),
    },
}

STATE_LABEL = {
    "working": "rift · working",
    "tool": "rift · tool",
    "waiting": "rift · waiting",
    "compacting": "rift · compacting",
    "interrupted": "rift · cut",
}


def state_label(state):
    """Her name stays up. The word after it is only there while something is happening."""
    return STATE_LABEL.get(state or "", "rift")

TEXT_MARKS = {
    "spark": ("✶", "*"),
    "keeper": ("◎", "O"),
    "prism": ("⟐", "<>"),
    "rift": ("◉", "o"),
}

# Four picture rows. A Grok status line keeps five, and the fifth is the label.
ROWS = 4


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _breath(theme, now, hold=False):
    """Breath of the hood and the ring.

    A live surface holds each step. The exported mark does not: it is one
    instant, and other presences copy that instant as she drew it.
    """
    if hold:
        now = math.floor(float(now) / 0.8) * 0.8
    wave = 0.5 + 0.5 * math.sin(now / 3.6)
    if hold:
        wave = round(wave * 8) / 8
    return _lerp(theme["edge_dim"], theme["edge"], wave)


def _blank(width):
    return [[(" ", None) for _ in range(width)] for _ in range(ROWS)]


def _put(grid, row, col, char, color):
    if row < 0 or col < 0 or row >= len(grid) or col >= len(grid[0]):
        return
    if char == " ":
        return
    grid[row][col] = (char, color)


def _anchor(width):
    """Narrow rows keep the face in the exported mark. Wide rows sit her at the left."""
    if width <= 32:
        return max(1, width // 2 - 5)
    return 2


def _lane_row(lane):
    if lane == 0:
        return 3
    if lane == 1:
        return 1
    if lane == 2:
        return 0
    return 2


def _paint_sky(grid, now, theme):
    """Drift only. Homes are evenly spaced, and each star moves by one cell."""
    width = len(grid[0])
    count = 4 if width < 56 else 5
    gap = max(4, width // (count + 1))
    for index in range(count):
        drift = int(now / 14.0 + index * 1.3) % 3 - 1
        col = min(width - 2, max(1, gap * (index + 1) + drift))
        _put(grid, 0, col, "+" if index % 2 else "·", theme["star"])


def _paint_filament(grid, filament, now, origin, limit, color, violet):
    count = length_at(filament, now)
    if count <= 0:
        return
    full = max(1, int(filament.get("length") or 1))
    room = max(1, limit - origin)
    cells = max(1, round(room * min(1.0, count / full)))
    row = _lane_row(filament.get("lane"))
    severed = bool(filament.get("severed")) and filament.get("gone") is not None
    gap = 1 if severed else 0
    for index in range(cells):
        if index < gap:
            continue
        tip = index == cells - 1
        _put(grid, row, origin + index, "∴" if tip else "╌", violet if tip else color)


def _paint_figure(grid, scene, ax, theme, red, now, hold=False, top=1):
    """Hoodie, smirk, eyes that brighten only on a real turn. top is the hood row."""
    level = scene.get("open", 1)
    awake = bool(scene.get("nebula") or scene.get("turn"))
    violet = theme["violet"]
    if level <= 0:
        face = "(-◡-)"
        eye_at = ()
        eye = violet
    elif scene.get("waiting") and not scene.get("compacting"):
        face = "(◦◡◦)"
        eye_at = (1, 3)
        eye = theme["edge_dim"]
    else:
        face = "(◉◡◉)"
        eye_at = (1, 3)
        if red:
            eye = theme["red"]
        elif awake:
            eye = theme["edge"]
        else:
            eye = theme["edge_dim"]
    for index, glyph in enumerate(face):
        tone = eye if index in eye_at else violet
        _put(grid, top + 1, ax + index, glyph, tone)
    breath = _breath(theme, now, hold=hold)
    for index, glyph in enumerate("╭─╮"):
        tone = breath if index == 1 else theme["edge_dim"]
        _put(grid, top, ax + 1 + index, glyph, tone)
    # A short step toward the breath. The chest stays violet.
    chest = _lerp(violet, breath, 0.35)
    for index, glyph in enumerate("╰─┬─╯"):
        if glyph == "┬":
            tone = chest
        elif glyph in "╰╯":
            tone = violet
        else:
            tone = theme["cloth"]
        _put(grid, top + 2, ax + index, glyph, tone)


def _place_pane(origin, width, level):
    """A slit at rest, a screen while a turn has the aperture open. None when shut."""
    tail = width - origin - 1
    if level <= 0 or tail < 3:
        return None, 0
    pane_w = 3 if level == 1 else (10 if level >= 3 else 8)
    if pane_w > tail:
        pane_w = 3 if tail >= 3 else 0
    if pane_w == 0:
        return None, 0
    gap = min(16, max(0, tail - pane_w))
    box = origin + gap
    if box + pane_w > width:
        return None, 0
    return box, pane_w


def _drawable(box, pane_w):
    """Inner glass, skipping the padding cells of a wide pane."""
    right = box + pane_w - 1
    inner = list(range(box + 1, right))
    if len(inner) > 2:
        return inner[1:-1]
    return inner


def _paint_glass(grid, cells, scene, now, theme, sketch):
    """Waiting, compacting, evidence, then an authored sketch. The frame stays outside."""
    if not cells:
        return
    if sketch:
        for index, char in enumerate(sketch[:len(cells)]):
            if char == " ":
                continue
            _put(grid, 2, cells[index], char, theme["edge"])
        return
    if scene.get("compacting"):
        _put(grid, 2, cells[len(cells) // 2], "│", theme["violet"])
        return
    if scene.get("waiting"):
        return
    if not (scene.get("nebula") or scene.get("turn")):
        return
    center = cells[len(cells) // 2]
    if scene.get("turn"):
        _put(grid, 2, center, "░", theme["nebula"])
    lanes = set()
    for filament in scene.get("filaments") or []:
        if filament.get("kind") != "tool" or length_at(filament, now) <= 0:
            continue
        lane = filament.get("lane")
        if lane in (0, 1, 2):
            lanes.add(lane)
    slots = {0: cells[0], 1: center, 2: cells[-1]}
    tools = int(scene.get("tools") or 0)
    for lane in (0, 1, 2):
        if lane not in lanes:
            continue
        if tools > 3 and slots[lane] == cells[-1]:
            continue
        _put(grid, 2, slots[lane], "▓", theme["filament"])
    if tools > 3:
        _put(grid, 2, cells[-1], str(min(tools, 9)), theme["secondary"])


def _paint_pane(grid, box, pane_w, scene, now, theme, frame, sketch):
    if box is None or pane_w < 3 or box + pane_w > len(grid[0]):
        return
    right = box + pane_w - 1
    awake = bool(scene.get("nebula") or scene.get("turn"))
    # Square while it is only a slit. Round once the screen is actually open.
    nw, ne, sw, se = ("╭", "╮", "╰", "╯") if awake or pane_w > 3 else ("┌", "┐", "└", "┘")
    _put(grid, 1, box, nw, frame)
    _put(grid, 1, right, ne, frame)
    _put(grid, 3, box, sw, frame)
    _put(grid, 3, right, se, frame)
    for col in range(box + 1, right):
        _put(grid, 1, col, "─", frame)
        _put(grid, 3, col, "─", frame)
    _put(grid, 2, box, "│", frame)
    _put(grid, 2, right, "│", frame)
    _paint_glass(grid, _drawable(box, pane_w), scene, now, theme, sketch)


def _clear_star(grid, row, col):
    if row < 0 or col < 0 or row >= len(grid) or col >= len(grid[0]):
        return
    if grid[row][col][0] in {"+", "·"}:
        grid[row][col] = (" ", None)


def _paint_thread(grid, start, stop, theme):
    """Stars only. A filament already on this row stays."""
    for col in range(max(0, start), max(0, stop)):
        if grid[0][col][0] not in {" ", "+", "·"}:
            continue
        _clear_star(grid, 0, col)
        _put(grid, 0, col, "·", theme["thread"])


def _paint_mini(grid, col, branches, theme, top=0):
    frame = theme["edge_dim"]
    mark = theme["secondary"]
    for row in range(top, top + 3):
        _clear_star(grid, row, col)
        _clear_star(grid, row, col + 1)
    _put(grid, top, col, "╭", frame)
    _put(grid, top, col + 1, "╮", frame)
    if branches == 1:
        _put(grid, top + 1, col, "◦", mark)
    else:
        _put(grid, top + 1, col, str(min(int(branches), 9)), mark)
    _put(grid, top + 1, col + 1, "│", frame)
    _put(grid, top + 2, col, "╰", frame)
    _put(grid, top + 2, col + 1, "╯", frame)


def _paint_company(grid, scene, ax, box, pane_w, theme):
    """One second aperture when it fits. Otherwise one moon and whatever thread fits."""
    branches = int(scene.get("branches") or 0)
    if branches <= 0:
        return
    width = len(grid[0])
    hood = ax + 1
    if box is not None and pane_w and width - (box + pane_w) >= 3:
        _paint_thread(grid, hood, box, theme)
        _paint_mini(grid, box + pane_w, branches, theme)
        return
    end = (box - 1) if box is not None else width - 1
    end = max(0, min(width - 1, end))
    if end > hood:
        _paint_thread(grid, hood, end, theme)
    _clear_star(grid, 0, end)
    _put(grid, 0, end, "◦", theme["secondary"])


def _paint_ground(grid, start, stop, theme):
    width = len(grid[0])
    for col in range(max(0, start), min(stop, width)):
        if grid[3][col][0] == " ":
            _put(grid, 3, col, "─", theme["edge_dim"])


def paint(scene, now, theme_name="rift", width=48, peers=None, threads=None, caption="", mark="", sketch="", hold=False):
    """Return row strings of cells (char, color). Peers are their own marks."""
    theme = THEMES.get(theme_name, THEMES["rift"])
    width = max(24, width)
    grid = _blank(width)
    ax = _anchor(width)
    edge = _breath(theme, now, hold=hold)
    red = scene.get("red_at") is not None and 0 <= now - scene["red_at"] < RED_S
    tip = theme["red"] if red else theme["violet"]

    _paint_sky(grid, now, theme)

    origin = ax + 6
    level = scene.get("open", 1)
    box, pane_w = _place_pane(origin, width, level)
    # Stop one cell short of the glass so a tip does not sit on the frame.
    limit = (box - 1) if box else min(width - 1, origin + 16)
    filaments = scene.get("filaments") or []
    for filament in filaments:
        _paint_filament(grid, filament, now, origin, limit, theme["filament"], tip)
    # The desk meets the frame, unless a beam is already on that row.
    # Then it stops short, so a tip is not followed by one stray dash.
    on_desk = any(
        _lane_row(item.get("lane")) == 3 and length_at(item, now) > 0 for item in filaments
    )
    _paint_ground(grid, origin, limit if on_desk or not box else box, theme)
    _paint_pane(grid, box, pane_w, scene, now, theme, theme["red"] if red else edge, sketch or "")
    _paint_company(grid, scene, ax, box, pane_w, theme)
    _paint_figure(grid, scene, ax, theme, red, now, hold=hold)

    if any(0 <= now - moment < SPARK_S for moment in scene.get("sparks") or []):
        _put(grid, 1, ax + 2, "✦", theme["spark"])

    rows = [list(row) for row in grid]
    footer = _footer(
        peers or [], threads or [], caption, mark, theme, width, scene.get("state") or "",
    )
    return rows, footer, theme


def _footer(peers, threads, caption, mark, theme, width, state=""):
    cells = []
    label = state_label(state)
    for char in label:
        cells.append((char, theme["edge"]))
    if label and (peers or caption or mark):
        cells.append((" ", None))
        cells.append(("·", theme["star"]))
        cells.append((" ", None))
    order = ["prism", "spark", "keeper"]
    by_name = {}
    for peer in peers:
        by_name.setdefault(peer["presence"], peer)
    shown = [name for name in order if name in by_name]
    linked = {(item["from"], item["to"]) for item in threads}
    for index, name in enumerate(shown):
        if index and any(
            (left, name) in linked or (name, left) in linked
            for left in shown[:index]
        ):
            cells.append(("—", theme["thread"]))
        else:
            if index:
                cells.append((" ", None))
        glyph = TEXT_MARKS[name][0] if load_sheet(name) else name
        cells.append((glyph, theme["filament"]))
    text = (caption or "").replace("\n", " ").strip()
    badge = (mark or "").replace("\n", " ").strip()
    if badge:
        if cells:
            cells.append((" ", None))
        cells.append((badge[:2], theme["violet"]))
    if text:
        if cells:
            cells.append((" ", None))
            cells.append(("·", theme["star"]))
            cells.append((" ", None))
        for char in text[:48]:
            cells.append((char, theme["edge_dim"]))
    if len(cells) > width:
        cells = cells[:width]
    while len(cells) < width:
        cells.append((" ", None))
    return cells


def ansi_rows(rows, footer):
    lines = [_ansi_line(row) for row in rows]
    if any(cell[0] != " " for cell in footer):
        lines.append(_ansi_line(footer))
    return lines


def _ansi_line(cells):
    parts = []
    current = None
    for char, color in cells:
        if color != current:
            if color is None:
                parts.append("\033[0m")
            else:
                parts.append(f"\033[38;2;{color[0]};{color[1]};{color[2]}m")
            current = color
        parts.append(char)
    if current is not None:
        parts.append("\033[0m")
    return "".join(parts).rstrip()


def plain(rows, footer):
    lines = ["".join(cell[0] for cell in row).rstrip() for row in rows]
    if any(cell[0] != " " for cell in footer):
        lines.append("".join(cell[0] for cell in footer).rstrip())
    return lines


def colors_used(rows, footer):
    found = []
    for row in list(rows) + [footer]:
        for _char, color in row:
            if color is not None:
                found.append(color)
    return found


def warm(color):
    red, green, blue = color
    return red > 140 and red > green + 40 and red > blue + 20


def _grid(width, height):
    return [[(" ", None) for _ in range(width)] for _ in range(height)]


def _seat_row(width, height):
    """Hood row, when the pane can hold her under the slit. None on a short pane."""
    if width < 18 or height < 18:
        return None
    return height - 6


def _paint_desk(grid, ax, row, theme):
    """The short stretch she sits at. Not a floor."""
    width = len(grid[0])
    for col in range(ax, ax + 5):
        if 0 <= row < len(grid) and 0 <= col < width and grid[row][col][0] in {" ", "·", "+"}:
            _put(grid, row, col, "─", theme["edge_dim"])


def paint_side(scene, now, theme_name="rift", width=36, height=40):
    """The aperture, and her under it when the pane is tall enough."""
    theme = THEMES.get(theme_name, THEMES["rift"])
    width = max(1, int(width))
    height = max(1, int(height))
    grid = _grid(width, height)
    red = scene.get("red_at") is not None and 0 <= now - scene["red_at"] < RED_S
    # The long bars stay one colour. A breath along the whole spine reads as a flicker.
    ring = theme["red"] if red else theme["edge"]
    violet = theme["violet"]
    tip = theme["red"] if red else theme["violet"]
    cx = width // 2
    level = scene.get("open", 1)
    hood = _seat_row(width, height)
    # The slit stays above her. A short pane keeps the slit alone.
    floor = (hood - 2) if hood is not None else (height - 2)
    cy = min(max(floor, 0), max(0, floor // 2))
    half_h = min(cy, max(0, floor - cy), max(2, floor // 3))
    half_h = max(0, half_h)
    reach = {0: 0, 1: 1, 2: 2, 3: 3}.get(level, 1)
    awake = bool(scene.get("nebula") or scene.get("turn"))

    _side_sky(grid, now, theme)

    if level > 0:
        for dy in range(-half_h, half_h + 1):
            y = cy + dy
            taper = abs(dy) >= half_h - 1
            inner = max(0, reach - (1 if taper else 0))
            if abs(dy) == half_h:
                _put(grid, y, cx - 1, "╲" if dy < 0 else "╱", violet)
                _put(grid, y, cx + 1, "╱" if dy < 0 else "╲", violet)
                _put(grid, y, cx, "│", ring)
                continue
            left = cx - inner
            right = cx + inner
            outer = inner + 1
            _put(grid, y, cx - outer, "│", violet)
            _put(grid, y, cx + outer, "│", violet)
            _put(grid, y, left, "│", ring)
            if right != left:
                _put(grid, y, right, "│", ring)
            if dy == 0:
                if red:
                    tone = theme["red"]
                elif scene.get("waiting") and not scene.get("compacting"):
                    tone = theme["edge_dim"]
                elif awake:
                    tone = theme["edge"]
                else:
                    tone = _breath(theme, now, hold=True)
                _put(grid, y, cx, "◉", tone)
            elif scene.get("compacting") and dy == 1:
                _put(grid, y, cx, "│", theme["violet"])
            elif (
                scene.get("nebula")
                and not scene.get("compacting")
                and not scene.get("waiting")
                and abs(dy) < half_h - 1
            ):
                _put(grid, y, cx, "░", theme["nebula"])
    else:
        _put(grid, cy, cx, "·", theme["edge_dim"])

    if level > 0:
        _glass_drift(grid, now, cx, cy, half_h, theme)
    for filament in scene.get("filaments") or []:
        if filament.get("kind") == "tool":
            continue
        _side_filament(grid, filament, now, cx, cy, reach, theme["filament"], tip)
    _side_tools(grid, scene, now, cx, cy, reach, theme)
    if scene.get("branches"):
        branches = int(scene["branches"])
        gap = cx + reach + 3
        seat = min(width - 2, cx + reach + 8)
        if seat + 1 < width:
            for col in range(gap, seat):
                if grid[cy][col][0] == " ":
                    _put(grid, cy, col, "·", theme["thread"])
            _paint_mini(grid, seat, branches, theme, top=cy - 1)
        else:
            seat = min(width - 1, cx + reach + 8)
            for col in range(gap, min(seat, width)):
                if grid[cy][col][0] == " ":
                    _put(grid, cy, col, "·", theme["thread"])
            _put(grid, cy, seat, "◦", theme["secondary"])
    if any(0 <= now - moment < SPARK_S for moment in scene.get("sparks") or []):
        if hood is not None:
            _put(grid, hood, cx, "✦", theme["spark"])
        else:
            _put(grid, cy - 1, cx, "✦", theme["spark"])

    if hood is not None:
        _paint_figure(grid, scene, cx - 2, theme, red, now, hold=True, top=hood)
        _paint_desk(grid, cx - 2, hood + 3, theme)

    label = state_label(scene.get("state"))
    if label:
        start = max(0, (width - len(label)) // 2)
        for index, char in enumerate(label):
            _put(grid, height - 1, start + index, char, theme["edge_dim"])
    return grid


def _side_sky(grid, now, theme):
    """Evenly spaced sky. Each mark moves by one cell, including near the slit."""
    width = len(grid[0])
    height = len(grid)
    if width < 3 or height < 3:
        return
    count = 4 if height < 28 else 6
    gap_y = max(3, height // (count + 1))
    gap_x = max(3, width // (count + 1))
    for index in range(count):
        drift = int(now / 14.0 + index * 1.3) % 3 - 1
        col = min(width - 2, max(1, gap_x * (index + 1) + drift))
        row = min(height - 2, max(0, gap_y * (index + 1)))
        _put(grid, row, col, "+" if index % 2 else "·", theme["star"])


def _glass_drift(grid, now, cx, cy, half_h, theme):
    """Dim sky through the open column. Evidence already drawn there stays."""
    if half_h < 2 or not grid or not grid[0]:
        return
    height = len(grid)
    track = [
        row for row in range(cy - half_h + 1, cy + half_h)
        if row != cy and 0 <= row < height
    ]
    if len(track) < 3:
        return
    step = int(now / 7.0) % len(track)
    span = len(track) // 3
    for index in range(3):
        row = track[(step + index * span) % len(track)]
        if grid[row][cx][0] != " ":
            continue
        _put(grid, row, cx, "+" if index == 1 else "·", theme["star"])


def _side_tools(grid, scene, now, cx, cy, reach, theme):
    """One fixed brush per live lane. The clock does not add cells."""
    live = set()
    for filament in scene.get("filaments") or []:
        if filament.get("kind") != "tool" or length_at(filament, now) <= 0:
            continue
        lane = filament.get("lane")
        if lane in (0, 1, 2):
            live.add(lane)
    tools = int(scene.get("tools") or 0)
    if not live and tools <= 3:
        return
    outer = reach + 1
    slots = {
        0: (cy, cx + outer + 1),
        1: (cy, cx - outer - 1),
        2: (cy - 1, cx + outer + 1),
    }
    right = slots[2]
    for lane, (row, col) in slots.items():
        if lane not in live:
            continue
        if tools > 3 and (row, col) == right:
            continue
        _put(grid, row, col, "▓", theme["filament"])
    if tools > 3:
        _put(grid, right[0], right[1], str(min(tools, 9)), theme["secondary"])


def _side_filament(grid, filament, now, cx, cy, reach, color, violet):
    count = length_at(filament, now)
    if count <= 0:
        return
    full = max(1, int(filament.get("length") or 1))
    frac = min(1.0, count / full)
    width = len(grid[0])
    lane = filament.get("lane")
    if lane == 0:
        row, sign, start = cy, 1, cx + reach + 2
        room = width - 2 - start
    elif lane == 1:
        row, sign, start = min(len(grid) - 2, cy + 2), -1, cx - reach - 2
        room = start - 1
    elif lane == 2:
        row, sign, start = max(1, cy - 2), 1, cx + reach + 2
        room = width - 2 - start
    else:
        row, sign, start = max(1, cy - 1), -1, cx - reach - 2
        room = start - 1
    room = max(1, min(room, 16))
    cells = max(1, round(room * frac))
    gap = 1 if filament.get("severed") and filament.get("gone") is not None else 0
    for index in range(cells):
        if index < gap:
            continue
        col = start + sign * index
        if not (0 <= row < len(grid) and 0 <= col < width):
            continue
        if grid[row][col][0] not in {" ", "·", "+"}:
            continue
        tip = index == cells - 1
        glyph = "∴" if tip else ("╌" if index % 2 == 0 else ":")
        _put(grid, row, col, glyph, violet if tip else color)


MARK_DIR = Path(__file__).resolve().parent.parent / "link-mark"


def load_sheet(presence):
    path = MARK_DIR / f"{presence}.json"
    try:
        import json
        sheet = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(sheet, dict) or sheet.get("presence") != presence or "idle" not in sheet.get("frames", {}):
        return None
    return sheet


def mark_sheet():
    """Rift's own sheet, from this renderer, for another presence to vendor later."""
    from evidence import apply, fresh
    scene = fresh()
    shots = {"idle": (fresh(), 0.0)}
    apply(scene, "turn.start", 1)
    shots["working"] = (json_scene(scene), 1.5)
    apply(scene, "tool.start", 2)
    shots["tool"] = (json_scene(scene), 2.6)
    apply(scene, "approval.request", 3)
    shots["waiting"] = (json_scene(scene), 3.0)
    apply(scene, "approval.resolved", 3.1)
    apply(scene, "compact.start", 3.2)
    shots["compacting"] = (json_scene(scene), 3.2)
    apply(scene, "compact.end", 3.3)
    apply(scene, "tool.end", 4)
    apply(scene, "turn.end", 5)
    shots["stopped"] = (json_scene(scene), 6.0)
    scene = fresh()
    apply(scene, "turn.start", 1)
    apply(scene, "tool.start", 2)
    apply(scene, "interrupt", 3)
    shots["interrupted"] = (json_scene(scene), 3.1)
    scene = fresh()
    apply(scene, "session.end", 1)
    shots["ended"] = (json_scene(scene), 2.0)
    frames = {}
    ascii_frames = {}
    for name, (shot, moment) in (
        ("idle", shots["idle"]),
        ("working", shots["working"]),
        ("tool", shots["tool"]),
        ("waiting", shots["waiting"]),
        ("compacting", shots["compacting"]),
        ("stopped", shots["stopped"]),
        ("interrupted", shots["interrupted"]),
        ("ended", shots["ended"]),
    ):
        rows, _footer, _theme = paint(shot, moment, "rift", 21)
        cropped = [row[5:16] for row in rows]
        while len(cropped) < 5:
            cropped.append([(" ", None) for _ in range(11)])
        frames[name] = [
            [[char, list(color) if color else None, None] for char, color in row]
            for row in cropped
        ]
        ascii_frames[name] = ["".join(char if 32 <= ord(char) < 127 else "." for char, _color in row) for row in cropped]
    return {
        "v": 1,
        "presence": "rift",
        "cols": 11,
        "rows": 5,
        "note": "Rift at the desk, rendered by her own terminal renderer (rift/render.py). A host draws it at her seat; it never redraws Rift itself.",
        "states_map": {"listening": "idle", "thinking": "working"},
        "frames": frames,
        "ascii": ascii_frames,
    }


def json_scene(scene):
    import copy
    return copy.deepcopy(scene)


def peer_mark(presence, state, ascii_only=False):
    """A peer's own exported mark. A missing sheet is the name, never an invented picture."""
    sheet = load_sheet(presence)
    if sheet is None:
        return presence
    if ascii_only:
        frames = sheet.get("ascii") or {}
        mapped = (sheet.get("states_map") or {}).get(state, state)
        return "\n".join(frames.get(mapped) or frames.get("idle") or [presence])
    glyph, ascii_glyph = TEXT_MARKS.get(presence, (presence, presence))
    return ascii_glyph if ascii_only else glyph
