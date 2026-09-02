/*
    themey pager — E16's pager in LIVE mode, replayed at runtime.

    E16's pager (pager.c) shows, per desktop, the real desktop background
    scaled into the cell plus one PAGER_WIN-framed rectangle per window
    at its true position, with PAGER_SEL marking the current desk. The
    stock Plasma pager is nearly untheme-able (three FrameSvg prefixes and
    Kirigami.Theme.textColor rects), so this applet paints the same model
    from theme-agnostic QML:

      * grid from TaskManager.VirtualDesktopInfo (desktopLayoutRows ×
        ceil(n / rows), desktopIds order);
      * per cell, bottom to top: widgets/pager `normal-` frame (absent =
        invisible, exactly like the stock pager — a transparent
        PAGER_BACKGROUND) → the live wallpaper mini, clipped inside the
        frame margins → the window layer → the `active-` frame on the
        current desktop → the `hover-` frame under the mouse;
      * the window layer is one TasksModel per cell (filtered by that
        desktop and, by default, this screen; minimized windows hidden —
        E16's iconbox owns those), each rect painted by the style's
        `window-`/`window-active-` prefixes (PAGER_WIN art, written by
        themey's plasmastyle generator) or, when the style has no
        `window-center`, stock-style textColor rects;
      * the wallpaper is read at RUNTIME from plasmashell over D-Bus
        (org.kde.PlasmaShell.wallpaper <screen>: `Image:` + `FillMode:`
        lines), on load, every wallpaperPollSeconds and on every desktop
        switch — never baked, so a KCM change can't go stale (chris's
        rule, 2026-08-31);
      * cell click → desktop switch through KWin's readwrite
        VirtualDesktopManager.current D-Bus property; rect click →
        TasksModel.requestActivate.

    D-Bus goes through the Plasma5Support executable DataSource: the only
    in-stack D-Bus shim applet QML gets on Plasma 6.6 (deprecated-but-
    shipped). Not replayed: E16 pager areas (Plasma has none), window drag
    between desks, the middle/right-click menus.
*/
import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.kde.ksvg as KSvg
import org.kde.kirigami as Kirigami
import org.kde.taskmanager as TaskManager

PlasmoidItem {
    id: root

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: fullRepresentation
    Plasmoid.title: i18n("E16 Pager")
    toolTipMainText: i18n("E16 Pager")
    toolTipSubText: i18n("Live desktop minis with window rectangles in theme art")

    readonly property bool vertical: Plasmoid.formFactor === PlasmaCore.Types.Vertical
    readonly property bool planar: Plasmoid.formFactor === PlasmaCore.Types.Planar
    // The applet's screen rect (TasksModel screen filter) — on a panel
    // this is the panel's screen; plasmoidviewer reports its own window
    // instead, which is why the aspect comes from the Screen attached
    // property (the window's real output) and not from this rect.
    readonly property rect screenRect: root.screenGeometry
    readonly property real screenAspect: (Screen.width > 0 && Screen.height > 0)
        ? Screen.width / Screen.height : 16 / 9
    // True when screenRect really is a screen: plasmoidviewer hands the
    // applet its own window as "screen geometry", and filtering windows
    // by THAT rect drops every one of them (2026-09-01). On a panel the
    // rect matches the panel window's output exactly.
    readonly property bool screenRectIsReal: screenRect.width === Screen.width
        && screenRect.height === Screen.height
    readonly property int desktopCount: Math.max(1, desktopInfo.numberOfDesktops)
    readonly property int gridRows: Math.max(1, Math.min(desktopInfo.desktopLayoutRows, desktopCount))
    readonly property int gridColumns: Math.ceil(desktopCount / gridRows)
    readonly property int cellSpacing: 1

    property string wallpaperImage: ""
    property int wallpaperFillMode: Image.PreserveAspectCrop
    // Re-evaluated on repaint (theme swap): a plain binding on
    // hasElement() would only run once.
    property bool hasWindowArt: false

    function refreshArt() {
        hasWindowArt = pagerSvg.isValid() && pagerSvg.hasElement("window-center");
    }
    Component.onCompleted: {
        refreshArt();
        refreshWallpaper();
    }

    TaskManager.VirtualDesktopInfo { id: desktopInfo }

    KSvg.Svg {
        id: pagerSvg
        imagePath: "widgets/pager"
        onRepaintNeeded: root.refreshArt()
    }

    P5Support.DataSource {
        id: shell
        engine: "executable"
        connectedSources: []
        onNewData: (sourceName, data) => {
            disconnectSource(sourceName);
            if (sourceName.indexOf("PlasmaShell.wallpaper") < 0) {
                return;
            }
            var out = String(data["stdout"] || "");
            var image = "";
            var fill = -1;
            var lines = out.split("\n");
            for (var i = 0; i < lines.length; i++) {
                var line = lines[i];
                if (line.indexOf("Image: ") === 0) {
                    image = line.substring(7).trim();
                } else if (line.indexOf("FillMode: ") === 0) {
                    fill = parseInt(line.substring(10).trim(), 10);
                }
            }
            if (image !== "") {
                root.wallpaperImage = image;
            }
            if (fill >= 0 && fill <= 6) {
                root.wallpaperFillMode = fill;
            }
        }
    }

    function refreshWallpaper() {
        if (!Plasmoid.configuration.showWallpaper) {
            return;
        }
        var screen = root.screen >= 0 ? root.screen : 0;
        shell.connectSource("qdbus6 org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.wallpaper " + screen);
    }

    function switchTo(desktopId) {
        shell.connectSource(
            "qdbus6 org.kde.KWin /VirtualDesktopManager "
            + "org.freedesktop.DBus.Properties.Set "
            + "org.kde.KWin.VirtualDesktopManager current '"
            + String(desktopId).replace(/'/g, "") + "'");
    }

    Timer {
        interval: Math.max(1, Plasmoid.configuration.wallpaperPollSeconds) * 1000
        running: Plasmoid.configuration.showWallpaper
        repeat: true
        onTriggered: root.refreshWallpaper()
    }
    Connections {
        target: desktopInfo
        function onCurrentDesktopChanged() { root.refreshWallpaper(); }
    }
    Connections {
        target: Plasmoid.configuration
        // KConfigPropertyMap signals valueChanged(key, value), not one
        // signal per key.
        function onValueChanged(key, value) {
            if (key === "showWallpaper") {
                root.refreshWallpaper();
            }
        }
    }

    fullRepresentation: Item {
        id: face

        // Cell geometry: on a vertical panel the cell width is the panel
        // width (minus spacing), height follows the screen aspect; on a
        // horizontal panel the height is the thickness; on the desktop
        // the width is what the user gave the applet.
        readonly property real cellW: root.vertical || root.planar
            ? Math.max(8, (width - (root.gridColumns - 1) * root.cellSpacing) / root.gridColumns)
            : cellH * root.screenAspect
        readonly property real cellH: root.vertical || root.planar
            ? cellW / root.screenAspect
            : Math.max(8, (height - (root.gridRows - 1) * root.cellSpacing) / root.gridRows)
        readonly property real gridW: root.gridColumns * cellW + (root.gridColumns - 1) * root.cellSpacing
        readonly property real gridH: root.gridRows * cellH + (root.gridRows - 1) * root.cellSpacing

        // Horizontal panel: width follows the grid, height is the
        // panel's. Vertical panel: height follows the grid. Desktop:
        // width is the user's, height follows the aspect.
        Layout.minimumWidth: root.vertical || root.planar ? -1 : gridW
        Layout.preferredWidth: root.vertical || root.planar ? -1 : gridW
        Layout.maximumWidth: root.vertical || root.planar ? Number.POSITIVE_INFINITY : gridW
        Layout.minimumHeight: root.vertical || root.planar ? gridH : -1
        Layout.preferredHeight: root.vertical || root.planar ? gridH : -1
        Layout.maximumHeight: root.vertical ? gridH : Number.POSITIVE_INFINITY
        // Desktop (planar) default size: readable cells.
        implicitWidth: 240
        implicitHeight: gridH

        Grid {
            id: grid
            anchors.left: parent.left
            anchors.top: parent.top
            // columns only: Grid derives the rows itself, and a bound
            // rows × columns races the desktop count during startup
            // ("more visible items than rows*columns").
            columns: root.gridColumns
            rowSpacing: root.cellSpacing
            columnSpacing: root.cellSpacing

            Repeater {
                model: desktopInfo.desktopIds

                // The ToolTipArea is the cell's CONTAINER (the stock
                // Plasma idiom: MouseAreas nest inside it), so its hover
                // tracking and the click areas never compete.
                delegate: PlasmaCore.ToolTipArea {
                    id: cell
                    required property int index
                    required property var modelData
                    readonly property string desktopId: String(modelData)
                    readonly property bool current: desktopId === String(desktopInfo.currentDesktop)
                    readonly property string desktopName: index < desktopInfo.desktopNames.length
                        ? desktopInfo.desktopNames[index] : ""

                    width: face.cellW
                    height: face.cellH
                    mainText: desktopName !== "" ? desktopName : i18n("Desktop %1", index + 1)
                    subText: {
                        var titles = [];
                        for (var i = 0; i < tasks.count && i < 8; i++) {
                            var t = tasks.data(tasks.makeModelIndex(i), Qt.DisplayRole);
                            if (t) {
                                titles.push(t);
                            }
                        }
                        if (tasks.count > 8) {
                            titles.push(i18n("… and %1 more", tasks.count - 8));
                        }
                        return titles.join("\n");
                    }

                    KSvg.FrameSvgItem {
                        id: normalFrame
                        anchors.fill: parent
                        imagePath: "widgets/pager"
                        prefix: "normal"
                    }

                    Item {
                        id: content
                        anchors.fill: parent
                        anchors.leftMargin: normalFrame.margins.left
                        anchors.rightMargin: normalFrame.margins.right
                        anchors.topMargin: normalFrame.margins.top
                        anchors.bottomMargin: normalFrame.margins.bottom
                        clip: true

                        Image {
                            id: mini
                            anchors.fill: parent
                            visible: Plasmoid.configuration.showWallpaper && root.wallpaperImage !== ""
                            source: visible ? root.wallpaperImage : ""
                            fillMode: root.wallpaperFillMode
                            asynchronous: true
                            cache: false
                            smooth: true
                            // A decoded 4K wallpaper per cell is wasteful:
                            // decode at twice the cell size (tile modes
                            // need the source's own size, so leave those).
                            sourceSize.width: (fillMode >= Image.Tile && fillMode <= Image.TileHorizontally)
                                ? 0 : Math.ceil(width * 2)
                            sourceSize.height: (fillMode >= Image.Tile && fillMode <= Image.TileHorizontally)
                                ? 0 : Math.ceil(height * 2)
                        }

                        TaskManager.TasksModel {
                            id: tasks
                            filterByVirtualDesktop: true
                            virtualDesktop: cell.desktopId
                            filterByScreen: Plasmoid.configuration.showOnlyCurrentScreen
                                && root.screenRectIsReal
                            screenGeometry: root.screenRect
                            filterMinimized: true
                            filterHidden: true
                            groupMode: TaskManager.TasksModel.GroupDisabled
                            sortMode: TaskManager.TasksModel.SortDisabled
                        }

                        Repeater {
                            model: tasks

                            delegate: PlasmaCore.ToolTipArea {
                                id: win
                                required property int index
                                required property var model
                                mainText: model.display
                                subText: cell.desktopName
                                icon: model.decoration
                                readonly property rect g: model.Geometry
                                // The screen the window is on; the applet's
                                // own screen when the role is empty.
                                readonly property rect sg: (model.ScreenGeometry
                                    && model.ScreenGeometry.width > 0)
                                    ? model.ScreenGeometry : root.screenRect
                                readonly property real sx: sg.width > 0 ? content.width / sg.width : 0
                                readonly property real sy: sg.height > 0 ? content.height / sg.height : 0

                                x: Math.round((g.x - sg.x) * sx)
                                y: Math.round((g.y - sg.y) * sy)
                                width: Math.max(2, Math.round(g.width * sx))
                                height: Math.max(2, Math.round(g.height * sy))
                                z: model.StackingOrder

                                KSvg.FrameSvgItem {
                                    anchors.fill: parent
                                    visible: root.hasWindowArt
                                    imagePath: "widgets/pager"
                                    prefix: model.IsActive ? ["window-active", "window"] : "window"
                                }

                                // Stock-pager style fallback: textColor
                                // rects at the six alphas the stock
                                // applet uses.
                                Rectangle {
                                    anchors.fill: parent
                                    visible: !root.hasWindowArt
                                    color: Qt.rgba(Kirigami.Theme.textColor.r,
                                                   Kirigami.Theme.textColor.g,
                                                   Kirigami.Theme.textColor.b,
                                                   model.IsActive ? 0.5 : 0.3)
                                    border.width: 1
                                    border.color: Qt.rgba(Kirigami.Theme.textColor.r,
                                                          Kirigami.Theme.textColor.g,
                                                          Kirigami.Theme.textColor.b,
                                                          model.IsActive ? 0.9 : 0.6)
                                }

                                Kirigami.Icon {
                                    anchors.centerIn: parent
                                    visible: Plasmoid.configuration.showWindowIcons
                                        && win.width >= 12 && win.height >= 12
                                    width: Math.min(win.width, win.height, Kirigami.Units.iconSizes.small)
                                    height: width
                                    source: model.decoration
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: tasks.requestActivate(tasks.makeModelIndex(win.index))
                                }
                            }
                        }
                    }

                    KSvg.FrameSvgItem {
                        anchors.fill: parent
                        imagePath: "widgets/pager"
                        prefix: "active"
                        visible: cell.current
                    }

                    KSvg.FrameSvgItem {
                        anchors.fill: parent
                        imagePath: "widgets/pager"
                        prefix: "hover"
                        visible: cellMouse.containsMouse && !cell.current
                    }

                    MouseArea {
                        id: cellMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        // Under the window rects (declared earlier) so a
                        // rect click activates the window, not the desk.
                        z: -1
                        onClicked: root.switchTo(cell.desktopId)
                    }
                }
            }
        }
    }
}
