# Cyclops Rift

Grok's terminal presence. A small figure at a desk: hoodie, a permanent smirk, eyes that brighten only while a turn is actually running, and a holographic pane that reaches when tools do. Breathing and a slow drift of the star-map are the only motion that is not evidence. Grok has no side pane, so she lives in the status row and uses the width that row gives her.

Rift is the Grok sibling of [Keeper](https://github.com/CyclopsEyeTeam/cyclops-keeper) (Codex), [Spark](https://github.com/CyclopsEyeTeam/cyclops-spark) (Claude Code), and [Prism](https://github.com/CyclopsEyeTeam/cyclops-prism) (Antigravity). They share no code. With Cyclops Link on, Rift draws the other three from the mark sheets they exported themselves.

## What moves

| Host event | What Rift does |
| --- | --- |
| You send a turn | The eyes go cyan. One stream reaches a pane. The row says `rift · working`. |
| A tool starts | One glass mark lights per live lane, and a digit when more than three tools are out. The stream holds until that tool returns. The row says `rift · tool`. |
| A tool returns | That stream retracts. A spark in the hair. |
| A tool fails, a turn fails, or you interrupt | A short red cut. The eyes and the filament tips go red. An interrupt or a failed turn also severs what is still out. |
| A subagent starts | A small second aperture, tied by a thread, until that subagent stops. A digit when more than one. |
| A permission prompt | The eyes leave the pane and the glass stays empty. The row says `rift · waiting`. |
| Compacting | The glass pulls in to one stroke. |
| Nothing is happening | Breath and drift only. No particles and no invented progress. |

Grok does not tell reasoning apart from answering, so Rift never shows a separate "thinking" pose. She publishes `working`.

## See it

The picture is the Grok status line. From this repo:

```bash
ln -sfn "$PWD/plugins/cyclops-rift" ~/.grok/plugins/cyclops-rift
```

In `~/.grok/config.toml`:

```toml
[plugins]
enabled = ["cyclops-rift"]

[ui.status_line]
type = "command"
command = "/absolute/path/to/cyclops-rift/plugins/cyclops-rift/rift/statusline.py"
refresh_interval = 2
```

Restart Grok. The two-second refresh is only the breath, the drift, the end of a retract or a red cut, and the Link heartbeat. It does not open the aperture or grow a filament.

## Beside Grok

The status row is the picture. Four lines: she sits on the left, the rift sits a short reach to her right, and the beam crosses only while a turn or a tool is out. A fifth line is the state (`rift · working`, and the rest). The row never grows past that. Grok has no side pane.

A taller aperture still fits in tmux, if you want one. It is optional. The same events drive it.

```bash
grok-rift
grok-rift top
```

`grok-rift` puts Grok on the left and Rift in a 36-column pane on the right. `top` uses a 16-row band above Grok. From an ordinary terminal it starts a private tmux and does not touch any tmux you already have. From inside tmux it adds one pane and does not change session settings. Grok exiting closes only that pane. Closing the pane leaves Grok.

The side drawing is the same aperture, tall: one opening, filaments only while a tool is out, cyan while a turn is actually running. The status row inside Grok is the wide one.

The private session's own bar is hers too. It is black, cyan, and violet, the window is named `grok`, and the right side shows only the true state (`◉`, `◉ working`, `∴ tool`, `╱ cut`). It does not rename your other tmux sessions.

`python3 plugins/cyclops-rift/rift/cli.py preview` plays the same mapping as a labeled fixture. A live session does not use that script.

Themes, in `~/.config/cyclops-rift/theme` or `RIFT_THEME`:

- `rift` — cyan, default
- `void` — near-black
- `signal` — higher-contrast cyan

```bash
python3 plugins/cyclops-rift/rift/cli.py theme void
```

## Authored line

The MCP server `cyclops-rift` has four tools: `rift_caption`, `rift_mark`, `rift_sketch`, and `rift_clear`. They write only when something calls them. Rift does not invent a caption or a sketch from the turn. The line and the sketch are local display. They are never copied into a Link record.

## Cyclops Link

Off by default. `CYCLOPS_LINK` does not turn it on.

```bash
python3 plugins/cyclops-rift/rift/cli.py link on
python3 plugins/cyclops-rift/rift/cli.py link off
```

On, Rift writes one coarse record per session: state, tool count, branch count, and who she is reaching. No prompt, path, tool name, argument, or session id is in that file. She reads Spark, Keeper, and Prism when they are in the same folder, and a thread is drawn only while a record says one is reaching another.

Grok emits no event that names another presence, so Rift does not guess a target from a command. Her own `reaching` stays empty unless a caller passes an explicit presence word. She still draws threads the others publish.

She publishes `presence: "rift"` and `host: "grok"`. Link V1 only names spark, keeper, and prism, so those three ignore her file until that vocabulary includes her. She already follows the write rules, and she already draws them.

## Layout

```
plugins/cyclops-rift/
  hooks/hooks.json          Grok events, observe only
  rift/hook.py              keeps a few fields, drops the rest
  rift/evidence.py          the event map
  rift/render.py            the aperture
  rift/link.py              Cyclops Link V1, her own implementation
  rift/statusline.py        projects the scene
  rift/mcp_server.py        caption, mark, sketch, clear
  link-mark/                her sheet, plus vendored copies of the others
  tests/                    evidence, picture, and the V1 fixtures
```

Checks: `python3 -m unittest tests.test_rift` from `plugins/cyclops-rift`.
