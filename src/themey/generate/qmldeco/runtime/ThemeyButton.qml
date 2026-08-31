// themey QML runtime v1 — a DecorationButton positioned by an E16 part.
// DecorationButton (org.kde.kwin.decoration) is an Item + MouseArea that
// fires decoration.request*() per buttonType — placeable ANYWHERE in the
// frame, which is what lets side-border button stacks work. main.qml's
// installed title item extends KWin's titleBar rect to cover every button
// part's rect, so the cursor is an arrow wherever buttons live.
import QtQuick
import org.kde.kwin.decoration

DecorationButton {
    id: btn
    property string kind: ""
    anchors.fill: parent
    // Gate on the client's capability so an unsupported request (e.g.
    // shade on a Wayland-native window, where KWin offers no shading)
    // degrades to a window drag instead of a dead click. `!== false`
    // keeps the button live when the bridge omits the property (KCM
    // preview hands us partial clients).
    enabled: {
        var c = decoration ? decoration.client : null;
        if (!c)
            return true;
        switch (btn.kind) {
        case "close":
            return c.closeable !== false;
        case "minimize":
            return c.minimizeable !== false;
        case "maximizeRestore":
            return c.maximizeable !== false;
        case "shade":
            return c.shadeable !== false;
        }
        return true;
    }
    // Static English tooltip labels (localization out of scope) shown via
    // the v1 plugin's decoration.requestShowToolTip — present on the
    // decoration context property but never called by the stock QML.
    readonly property string label: {
        switch (btn.kind) {
        case "close":
            return "Close";
        case "minimize":
            return "Minimize";
        case "maximizeRestore":
            return "Maximize";
        case "shade":
            return "Shade";
        case "onAllDesktops":
            return "On all desktops";
        case "keepAbove":
            return "Keep above others";
        case "keepBelow":
            return "Keep below others";
        case "menu":
            return "Menu";
        }
        return "";
    }

    Timer {
        id: tooltipTimer
        interval: 700
        onTriggered: {
            if (btn.label !== "" && decoration
                    && typeof decoration.requestShowToolTip === "function")
                decoration.requestShowToolTip(btn.label);
        }
    }
    function hideToolTip() {
        tooltipTimer.stop();
        if (decoration && typeof decoration.requestHideToolTip === "function")
            decoration.requestHideToolTip();
    }
    onHoveredChanged: {
        if (btn.hovered)
            tooltipTimer.restart();
        else
            btn.hideToolTip();
    }
    onPressedChanged: {
        if (btn.pressed)
            btn.hideToolTip();
    }

    buttonType: {
        switch (btn.kind) {
        case "close":
            return DecorationOptions.DecorationButtonClose;
        case "minimize":
            return DecorationOptions.DecorationButtonMinimize;
        case "maximizeRestore":
            return DecorationOptions.DecorationButtonMaximizeRestore;
        case "shade":
            return DecorationOptions.DecorationButtonShade;
        case "onAllDesktops":
            return DecorationOptions.DecorationButtonOnAllDesktops;
        case "keepAbove":
            return DecorationOptions.DecorationButtonKeepAbove;
        case "keepBelow":
            return DecorationOptions.DecorationButtonKeepBelow;
        case "menu":
            return DecorationOptions.DecorationButtonMenu;
        }
        return DecorationOptions.DecorationButtonNone;
    }
}
