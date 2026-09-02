/*
    themey deskbutton — one end of E16's desktop dragbar.

    E16 (desktops.c:95-346) synthesizes its top bar from three buttons:
    DESKTOP_RAISEBUTTON at the start ("desk next"), the DRAGBUTTON strip
    stretched across, DESKTOP_LOWERBUTTON at the end ("desk prev"). This
    applet is one of the two end buttons; `direction` (next|prev) picks
    which. Theme-agnostic on purpose: the glyph comes from the ACTIVE
    Plasma Style's widgets/themey-dragbar.svg (element
    <direction>-<horiz|vert>-<normal|hover|pressed>, written by themey's
    plasmastyle generator), with widgets/arrows as the fallback when the
    style ships no such element, so one panel configuration survives
    re-converts of any theme.

    Desktop switching goes through KWin's D-Bus VirtualDesktopManager
    (the `current` property is readwrite; VirtualDesktopInfo has no switch
    method in QML) via the Plasma5Support executable DataSource — the only
    in-stack D-Bus shim available to applet QML on Plasma 6.6. E16's
    desk next/prev WRAP around the desktop list, so does this.
*/
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.kde.ksvg as KSvg
import org.kde.taskmanager as TaskManager

PlasmoidItem {
    id: root

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation

    readonly property bool vertical: Plasmoid.formFactor === PlasmaCore.Types.Vertical
    readonly property string direction: Plasmoid.configuration.direction === "prev" ? "prev" : "next"
    readonly property string orient: vertical ? "vert" : "horiz"
    readonly property string baseElement: direction + "-" + orient
    // Re-evaluated on every repaint (theme swap): a plain binding on
    // hasElement() would only run once.
    property bool hasArt: false

    function refreshArt() {
        hasArt = dragbarSvg.isValid() && dragbarSvg.hasElement(baseElement + "-normal");
    }
    onBaseElementChanged: refreshArt()
    Component.onCompleted: refreshArt()

    Plasmoid.title: direction === "next" ? i18n("Next desktop") : i18n("Previous desktop")
    toolTipMainText: direction === "next" ? i18n("Next desktop") : i18n("Previous desktop")
    toolTipSubText: i18n("E16 dragbar button — switches virtual desktops (wraps around)")

    TaskManager.VirtualDesktopInfo { id: desktopInfo }

    P5Support.DataSource {
        id: shell
        engine: "executable"
        connectedSources: []
        onNewData: (sourceName, data) => { disconnectSource(sourceName); }
    }

    function step() {
        var ids = desktopInfo.desktopIds;
        var n = ids.length;
        if (n === 0) {
            return;
        }
        var i = ids.indexOf(desktopInfo.currentDesktop);
        if (i < 0) {
            i = 0;
        }
        var target = ids[(i + (direction === "next" ? 1 : n - 1)) % n];
        shell.connectSource(
            "qdbus6 org.kde.KWin /VirtualDesktopManager "
            + "org.freedesktop.DBus.Properties.Set "
            + "org.kde.KWin.VirtualDesktopManager current '"
            + String(target).replace(/'/g, "") + "'");
    }

    KSvg.Svg {
        id: dragbarSvg
        imagePath: "widgets/themey-dragbar"
        onRepaintNeeded: root.refreshArt()
    }

    fullRepresentation: Item {
        id: face
        // E16 drew the button dragbar_width square: fill the panel's
        // thickness on both axes. On the desktop (planar) use the art's
        // natural size.
        readonly property int side: root.vertical ? width : height
        Layout.minimumWidth: root.vertical ? -1 : side
        Layout.maximumWidth: root.vertical ? Number.POSITIVE_INFINITY : side
        Layout.preferredWidth: root.vertical ? -1 : side
        Layout.minimumHeight: root.vertical ? side : -1
        Layout.maximumHeight: root.vertical ? side : Number.POSITIVE_INFINITY
        Layout.preferredHeight: root.vertical ? side : -1
        implicitWidth: art.naturalSize.width > 0 ? art.naturalSize.width : 16
        implicitHeight: art.naturalSize.height > 0 ? art.naturalSize.height : 16

        KSvg.SvgItem {
            id: art
            anchors.fill: parent
            imagePath: root.hasArt ? "widgets/themey-dragbar" : "widgets/arrows"
            elementId: root.hasArt
                ? root.baseElement + "-" + (mouse.pressed ? "pressed" : (mouse.containsMouse ? "hover" : "normal"))
                : (root.vertical
                    ? (root.direction === "next" ? "down-arrow" : "up-arrow")
                    : (root.direction === "next" ? "right-arrow" : "left-arrow"))
            opacity: root.hasArt ? 1 : (mouse.pressed ? 0.6 : (mouse.containsMouse ? 0.85 : 1))
        }

        MouseArea {
            id: mouse
            anchors.fill: parent
            hoverEnabled: true
            onClicked: root.step()
        }
    }
}
