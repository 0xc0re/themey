# Vendored: `org.themey.dock`

This directory is a **fork of third-party GPL-2.0-or-later QML**, not themey's
own work. Unlike `runtime/pager/` and `runtime/deskbutton/` (themey-authored,
MIT), it is vendored, and it keeps its own licence: see `COPYING` (the full GNU
General Public License, version 2), the per-file headers where upstream
carried them (`SPDX-License-Identifier: GPL-2.0-or-later` — two upstream
files, `layoutmetrics.js` and `LauncherDrop.qml`, ship bare and were not
modified), and `License: GPL-2.0+` in the generated `metadata.json`. Both
files are installed with the package.

## Provenance

* **Upstream:** *Icons-Only Task Manager 2* — a macOS-style dock for Plasma 6
  (zoom on hover, parabolic rise, pinned launchers).
* **Repository:** <https://github.com/GridyushkoF/MacOS-Like-dock-for-KDE-Plasma>
* **Store page:** <https://store.kde.org/p/2352806/>
* **Vendored from:** commit `8230092` (v1.3, 2026-08-18).
* **Author:** GridyushkoF.

Upstream is itself a pure-QML fork of **KDE's Icons-Only Task Manager**
(`plasma-desktop/applets/taskmanager`, Eike Hein and the KDE Plasma
contributors) — which is why several files carry KDE copyright headers of their
own. The stock applet's QML is compiled into a `.so` via qrc and cannot be
imported, so the parts themey needs are ported by hand from the
`Plasma/6.6` branch (paths and line numbers are cited in the code).

## What was vendored

The 11 `contents/ui/*.qml`, the 2 `contents/ui/code/*.js`,
`contents/config/config.qml` and `contents/config/main.xml`. Upstream's
`metadata.json` is NOT vendored — themey generates it (`plasmoids.metadata`),
which is what renames the applet to `org.themey.dock`. Neither is upstream's
`.plasmoid` zip or its README.

## themey's changes

Every file below carries an added `SPDX-FileCopyrightText: 2026 themey
contributors` line; no existing header was removed.

* **`contents/ui/code/TaskTools.js`** (new) — `taskPrefix` /
  `taskPrefixHovered` ported verbatim from plasma-desktop `Plasma/6.6`
  `applets/taskmanager/qml/code/TaskTools.js:221-246`. The bottom edge asks
  for `["south-<p>", "<p>"]`; themey's Plasma Style ships no `south-` set, so
  the unprefixed set is the bottom-panel one — the assumption
  `generate/plasmastyle._TASKS_FOCUS_EDGES` is built on.
* **`contents/ui/Task.qml`**
  * A `KSvg.FrameSvgItem { imagePath: "widgets/tasks" }` plate, so the dock
    paints the *theme's* task art (which themey synthesizes from the E16
    iconbox buttons) instead of the fork's `Kirigami.Theme` rectangles. It is
    a **sibling below `iconContainer`**, not a child: inside that item's
    `layer.enabled` FBO it would be rasterised once at the container's rest
    scale and stay soft, and pinned to the static cell it would read as a hole
    the icon lifts out of. It follows `iconContainer`'s centre offsets and
    size, so it is crisp 1:1 at rest and lifts and grows with the icon.
  * `basePrefix` precedence via `states`, upstream `Task.qml:640-673`:
    launcher `""` → `attention` → `minimized` → `focus` → `normal`.
  * New properties `hasTaskArt`, `hoverEffect`, `hoveredByList`,
    `metricFrame`, and `highlighted = hovered || hoveredByList`.
  * The icon is inset by `metricFrame.fixedMargins` (upstream
    `Task.qml:533-540`) and fills the inset cell when there is art
    (`iconFit` 1.0), keeping the fork's 0.88 padding when there is none.
  * `Kirigami.Icon.active: highlighted`.
  * The running dot is hidden for the ACTIVE task when art is present — the
    focus plate already carries themey's accent bar.
  * The per-task `PlasmaCore.ToolTipArea` is re-enabled (the fork had it
    inert at `active: false`), driven by the item's own hover state and off
    while dragging or on a group parent. It also calls
    `showToolTip()`/`hideToolTip()` explicitly, because the zoom sensor
    above it consumes the hover events its own `containsMouse` would need.
    The fork's comment blames `ToolTipArea`'s internal hover handling for
    jitter during the zoom; that is unverified against this arrangement and
    **wants a look on a live desktop**. The fallback is a short settle timer
    on `hovered` before showing.
  * `console.log` tracing removed.
* **`contents/ui/TaskList.qml`**
  * An invisible `KSvg.FrameSvgItem` on the `normal` prefix (upstream
    `main.qml:356-363`) passed to every delegate as `metricFrame`.
  * `baseIconSize` budgets the hover PEAK into the cell for art and no-art
    alike: `floor((panelThickness - 2 * rise) / zoomFactor)`, floored at
    the small icon size. Task centres the icon, scales it by up to
    `zoomFactor` and lifts it by the parabolic rise, so the top edge clears
    the panel only while `size * zoom + 2 * rise <= panelThickness` — and a
    DOCKED panel's window is exactly its thickness. The fork's
    `- smallSpacing * 4` rest margin and its 10 % anti-clip shrink only ever
    approximated the zoom and never budgeted the rise, which clipped every
    hover on a 60 px docked panel (2026-09-05). The rise itself is also
    clamped to the headroom the zoomed cell leaves (`riseHeadroom`), so no
    configuration can push an icon past the panel edge; on a floating panel
    the margin is slack on top of the budget. Defaults follow: rise 6 px
    (upstream 18 assumed that margin) and anti-clip off (still honoured
    when turned on).
  * **Delegate geometry publishing restored** (upstream `main.qml:120-132,
    248-316`): `requestPublishDelegateGeometry` per task on a 500 ms settle
    timer, restarted on size / position / location / count changes and on the
    containment's `screenGeometryChanged`. Upstream reads the rect from the
    private C++ backend's `globalRect()`, which the fork dropped along with
    the plugin; `task.mapToGlobal(0, 0)` is the pure-QML equivalent. Without
    it KWin's Squash and Magic Lamp minimize effects animate from nowhere.
    The delegate handed over is the STATIC cell, never the zoomed icon — on
    Wayland KWin reads the item's own geometry and ignores the rect.
  * The global hover sensor is `acceptedButtons: Qt.NoButton`: it sits above
    every delegate at `z: 1000`, and accepting buttons there meant declining
    each press, release and click back down by hand.
* **`contents/ui/main.qml`**
  * A `KSvg.Svg` art probe on `widgets/tasks` — `hasTaskArt = isValid() &&
    hasElement("center")`, re-evaluated `onRepaintNeeded` (a plain binding on
    `hasElement()` runs once), mirroring `runtime/pager/contents/ui/main.qml`.
  * `hoverEffect` from `Plasmoid.configuration.taskHoverEffect`.
  * `Plasmoid.backgroundHints` deliberately left at its default so the panel
    keeps painting `widgets/panel-background.svg`.
  * `console.log` tracing removed; the two component-creation failures became
    `console.warn`.
* **`contents/config/main.xml`** — added the `taskHoverEffect` Bool (default
  true), upstream `main.xml:137-140`. This is the key `themey apply` writes
  from the Plasma Style's `X-Themey-TasksHover` stamp. It is deliberately NOT
  exposed in `config.qml`'s UI — it is themey's own per-theme spec, like the
  iconbox's, not a user-facing setting.
* **`contents/ui/code/launcherfromdrop.js`** — its one `console.log` became
  `console.warn`; SPDX header added (it had none).

Nothing else was renamed: no `icontasks2` string exists anywhere in upstream's
sources, so the applet id lives only in the generated `metadata.json`.
