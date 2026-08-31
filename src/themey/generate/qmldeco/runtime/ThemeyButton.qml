// themey QML runtime v1 — a DecorationButton positioned by an E16 part.
// DecorationButton (org.kde.kwin.decoration) is an Item + MouseArea that
// fires decoration.request*() per buttonType — placeable ANYWHERE in the
// frame, which is what lets side-border button stacks work. The known
// cosmetic limit: the cursor shows a resize shape over side-border buttons
// (kdecoration exposes a single titleBar QRect); clicks still win.
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
