// themey QML runtime v1 — generic E16-faithful KWin decoration.
// Copied verbatim into every generated package; all per-theme data lives
// in theme.js. Loaded by the Aurorae v1 plugin (org.kde.kwin.aurorae) as a
// KWin/Decoration KPackage. Every decoration.client access is guarded so
// the Window Decorations KCM preview (which may hand us partial bridges)
// cannot crash.
import QtQuick
import QtQml
import org.kde.kwin.decoration
import "theme.js" as ThemeData
import "resolver.js" as Resolver

Decoration {
    id: root
    alpha: true

    readonly property var themeData: ThemeData.theme
    readonly property bool clientActive: {
        var c = decoration ? decoration.client : null;
        return c ? c.active === true : false;
    }
    readonly property bool clientShaded: {
        var c = decoration ? decoration.client : null;
        return c ? c.shaded === true : false;
    }
    readonly property bool clientMaximized: {
        var c = decoration ? decoration.client : null;
        return c ? c.maximized === true : false;
    }
    readonly property string clientCaption: {
        var c = decoration ? decoration.client : null;
        return (c && c.caption !== undefined && c.caption !== null)
            ? c.caption : "";
    }

    // ------------------------------------------------------------------
    // Theme fonts. QML tracks property reads through function calls, so
    // bindings calling fontFamilyAt re-evaluate when a loader's status or
    // name changes; the count read covers the not-yet-created window.
    // (Never bump a counter from a change handler here — reading
    // implicitWidth/status forces evaluation synchronously and the write
    // trips QML's binding-loop detector.)
    Instantiator {
        id: fontInstantiator
        model: root.themeData.fonts
        delegate: FontLoader {
            source: Qt.resolvedUrl(modelData.source)
        }
    }
    function fontFamilyAt(idx) {
        var created = fontInstantiator.count;  // reactive dependency
        if (idx < 0 || idx >= root.themeData.fonts.length)
            return "";
        var loader = idx < created ? fontInstantiator.objectAt(idx) : null;
        if (loader && loader.status === FontLoader.Ready && loader.name !== "")
            return loader.name;
        var f = root.themeData.fonts[idx];
        return f.family ? f.family : "";
    }

    // ------------------------------------------------------------------
    // Hidden caption measurers — one per part; only title parts carry a
    // text config, the rest measure an empty string. Geometry bindings
    // read implicitWidth through titleTextWidth, which registers the
    // reactive dependency transparently.
    Repeater {
        id: measurers
        model: root.themeData.parts
        delegate: Text {
            visible: false
            text: modelData.text ? root.clientCaption : ""
            font.family: modelData.text
                ? root.fontFamilyAt(modelData.text.fontIndex) : ""
            font.pixelSize: modelData.text ? modelData.text.pixelSize : 10
            font.italic: root.fontStyleAt(modelData.text, "italic")
            font.bold: root.fontStyleAt(modelData.text, "bold")
        }
    }
    function fontStyleAt(textCfg, key) {
        if (!textCfg || textCfg.fontIndex < 0
                || textCfg.fontIndex >= root.themeData.fonts.length)
            return false;
        return root.themeData.fonts[textCfg.fontIndex][key] === true;
    }
    function titleTextWidth(idx) {
        var created = measurers.count;  // reactive dependency
        var t = idx < created ? measurers.itemAt(idx) : null;
        return t ? Math.ceil(t.implicitWidth) : 0;
    }

    // The title band doubles as the drag/double-click region; KWin derives
    // the titleBar rect from this installed item. It excludes the side
    // borders (like stock Aurorae) so a corner button such as e13's KILL
    // is NOT inside the titleBar QRect — keeping the arrow cursor and
    // button hit-testing correct over it. When maximized the side borders
    // collapse to 0 and the band spans the full width.
    Item {
        id: titleBandItem
        x: root.clientMaximized ? 0 : root.themeData.borders.left
        y: 0
        width: root.width - x
               - (root.clientMaximized ? 0 : root.themeData.borders.right)
        height: root.themeData.borders.top
    }

    // ------------------------------------------------------------------
    // Parts — declaration order is z order (later parts draw on top).
    Repeater {
        // ThemeyPart declares required modelData/index; the Repeater fills
        // them (required properties disable context-property injection).
        model: root.themeData.parts
        delegate: ThemeyPart {}
    }

    Component.onCompleted: {
        var b = root.themeData.borders;
        borders.left = b.left;
        borders.right = b.right;
        borders.top = b.top;
        borders.bottom = b.bottom;
        // Maximized: side/bottom borders collapse; the title band stays.
        maximizedBorders.left = 0;
        maximizedBorders.right = 0;
        maximizedBorders.top = b.top;
        maximizedBorders.bottom = 0;
        if (decoration && typeof decoration.installTitleItem === "function")
            decoration.installTitleItem(titleBandItem);
    }
}
