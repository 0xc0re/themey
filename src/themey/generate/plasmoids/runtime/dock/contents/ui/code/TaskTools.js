/*
    SPDX-FileCopyrightText: 2012-2016 Eike Hein <hein@kde.org>
    SPDX-FileCopyrightText: 2020 Nate Graham <nate@kde.org>
    SPDX-FileCopyrightText: 2026 themey contributors

    SPDX-License-Identifier: GPL-2.0-or-later
*/

/*
    The FrameSvg prefix chain KDE's own task manager uses, ported verbatim
    from plasma-desktop Plasma/6.6
    applets/taskmanager/qml/code/TaskTools.js:221-246 (the stock applet's
    QML is compiled into a .so, so it cannot simply be imported).

    Both functions return a LIST of prefixes; KSvg.FrameSvgItem takes the
    first one the SVG actually has, so each entry is a fallback for the one
    before it.

    The bottom edge asks for ["south-<p>", "<p>"] — themey's Plasma Style
    generator ships no `south-` set, which makes the UNPREFIXED set the
    bottom-panel one, exactly as generate/plasmastyle's _TASKS_FOCUS_EDGES
    assumes. `north-`/`west-`/`east-` are shipped for the focus states.
*/

.pragma library

.import org.kde.plasma.core as PlasmaCore

function taskPrefix(prefix, location) {
    let effectivePrefix;

    switch (location) {
    case PlasmaCore.Types.LeftEdge:
        effectivePrefix = "west-" + prefix;
        break;
    case PlasmaCore.Types.TopEdge:
        effectivePrefix = "north-" + prefix;
        break;
    case PlasmaCore.Types.RightEdge:
        effectivePrefix = "east-" + prefix;
        break;
    default:
        effectivePrefix = "south-" + prefix;
    }
    return [effectivePrefix, prefix];
}

function taskPrefixHovered(prefix, location) {
    return [
        ...taskPrefix((prefix || "launcher") + "-hover", location),
        ...prefix ? taskPrefix("hover", location) : [],
        ...taskPrefix(prefix, location),
    ];
}
