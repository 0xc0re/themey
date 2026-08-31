# Contributing to themey

## Setup

```sh
uv sync
```

That is the whole bootstrap. `uv` manages the Python toolchain, the virtualenv,
and the lockfile; there is nothing to activate.

Run the CLI out of the checkout with `uv run themey ...`.

## Verify

Three commands, all of which must pass before you open a PR:

```sh
uv run pytest
uv run ruff check .
uv run pyright src
```

`pyright` is configured in `basic` mode and is gated on `src/` only — `tests/`
is not type-clean and is not expected to be.

## Do NOT run `ruff format`

**This codebase is linted but not formatted.** `ruff format` has never been
applied to it, and running it would rewrite 121 of the 126 Python files. That
is the single most likely way to produce an accidental thousand-line diff here.

`ruff check` (lint, with the `E,W,F,I,B,C4,UP,RUF` rule set from
`pyproject.toml`) is the gate. `ruff format` is not. Do not enable
format-on-save for this repo, and if your editor does it anyway, check
`git diff --stat` before you commit.

## Rendering is guarded by perceptual hashes — do not regenerate to go green

`tests/test_svg_rc_invariant.py` enforces the one invariant the SVG backend
cannot violate: the strip thicknesses baked into `decoration.svg` and the
`Border*` / `TitleHeight` values in the Aurorae `rc` file both come from
`decoration_svg.strip_thicknesses()`, so they can never drift apart.

`tests/snapshots/visual/` holds committed perceptual hashes (`.phash`, plus the
reference PNG) for both backends: `test_visual_snapshot.py` rasterizes
`decoration.svg` with `rsvg-convert`; `test_qmldeco_visual.py` (files suffixed
`-qml`) cannot do that, because the QML backend's only faithful renderer is
KWin, so it screenshots the real nested-KWin harness instead. Both compare by
Hamming distance against a threshold of 8 bits out of 64 — that tolerance
absorbs librsvg and font-version drift, so a failure means the pixels genuinely
moved.

**A phash diff is a finding, not a chore.** Regenerate only when you intended
the visual change *and* have looked at the new render and confirmed it is
right:

```sh
uv run pytest tests/test_visual_snapshot.py --update-visual-hashes
uv run pytest tests/test_qmldeco_visual.py --update-visual-hashes
```

Never run either to turn a red test green.

## `themey render` is the truth

```sh
uv run themey render Aliens --plugin qml
```

`themey render` screenshots the theme inside a real nested headless KWin. That
is ground truth for how a decoration actually looks.

`scripts/render_review.py` is a fast approximation that draws the SVG itself.
It is useful for a quick look, but it knows nothing about the QML backend (the
default), and it can and does disagree with KWin. Do not settle a visual
question with it.

## Tests that skip without external tools

Every one of these is a `skipif` on `shutil.which(...)` — nothing fails merely
because a tool is missing, so a clean run on a bare machine can still be hiding
coverage. Check the skip list (`pytest -rs`) before trusting a green run.

| Tool | What skips without it |
|------|----------------------|
| `xcursorgen` | The cursor tests in `test_generate_cursors.py`, `test_cursors_binary.py`, `test_pipeline_cursors.py`, and `test_pipeline_lookandfeel.py`. Separately, `test_cli.py` and `test_pipeline_aliens_canary.py` do *not* skip — they drop their cursor assertions and keep running, so the rest of the pipeline is still checked. |
| `rsvg-convert` | Both tests in `test_visual_snapshot.py` — i.e. the entire SVG-backend phash guard. |
| `kwin_wayland`, `dbus-run-session`, `spectacle`, `kdialog` | All four are required together (`render.REQUIRED_TOOLS`). Missing any of them skips `test_render.py`'s end-to-end headless render **and all of `test_qmldeco_visual.py`** — i.e. the entire phash guard on the default backend. The `kwinrc`/`kwinrulesrc` writers are unit-tested unconditionally. |
| `qmllint` | `test_qmldeco_package.py::test_runtime_passes_qmllint`, which is the only check that the four verbatim QML/JS runtime files actually parse. |

On Debian/Ubuntu: `xcursorgen` is in `x11-apps`, `rsvg-convert` in
`librsvg2-bin`, `qmllint` in `qt6-declarative-dev-tools`.

## Before you change anything

Read `CLAUDE.md`. It carries the architecture, the pipeline stages, and the
load-bearing conventions — the naming contract that ties every installed
artifact to one slug, the resolver lockstep between `resolver.py` and
`resolver.js`, the Aurorae element-ID contract, and the handful of "do not
simplify this" notes (the hand-rolled XBM parser, `RawConfigParser` with
`optionxform = str`, `NEAREST` for pixel art) that exist because the obvious
alternative silently produces wrong output.

Every module also opens with a docstring naming the contract it satisfies.
Those are worth reading before editing the module, not after.
