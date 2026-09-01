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
    // E16 picks the sticky/sticky_active ImageState group for EVERY part of
    // a window on all desktops (borders.c:179 EoIsSticky(ewin)).
    readonly property bool clientOnAllDesktops: {
        var c = decoration ? decoration.client : null;
        return c ? c.onAllDesktops === true : false;
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
            // Source-less entries are server (XLFD/xft) fonts: family and
            // weight/slant only, no file to load.
            source: modelData.source ? Qt.resolvedUrl(modelData.source) : ""
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

    // KWin picks the mouse cursor from Decoration::sectionUnderMouse(),
    // computed from exactly two geometric inputs: the titleBar QRect
    // (checked first — wins outright: arrow cursor, move-drag,
    // double-click) and borders() (left/right/top tests → resize
    // sections). QML has no cursor channel; the only lever an Aurorae v1
    // theme has is the item handed to decoration.installTitleItem(),
    // which Aurorae maps to setTitleBar() and re-reads on the item's
    // x/y/width/height change signals. So this item is the union
    // bounding box of the full-width top band and every visible button
    // part's rect — E16-style corner/side buttons (e13's KILL, the
    // ICONIFY/SHADE/STICK stack) get the arrow cursor, and the border
    // strips between them act as titlebar. Resize survives on the
    // bottom border and on side borders below the lowest button. When
    // maximized the below-band buttons are hideWhenMaximized, so the
    // height collapses back to borders.top (== maximizedBorders.top).
    // MUST STAY CHILDLESS: with children present, Aurorae prefers
    // childrenRect() over the item's own geometry.
    Item {
        id: titleBandItem
        x: 0
        y: 0
        width: root.width
        height: {
            // Same reactive pattern as ThemeyPart.geo: the resolver and
            // property reads below register dependencies on
            // root.width/height, the client state and the caption
            // measurers, so resize/maximize/caption changes re-fire the
            // geometry signals Aurorae listens to.
            var bottom = root.themeData.borders.top;
            var parts = root.themeData.parts;
            for (var i = 0; i < parts.length; i++) {
                var p = parts[i];
                if (p.button === null)
                    continue;
                if (root.clientShaded && !p.keepWhenShaded)
                    continue;
                if (root.clientMaximized && p.hideWhenMaximized)
                    continue;
                var g = Resolver.partGeometry(
                    root.themeData, i, root.width, root.height,
                    function (j) { return root.titleTextWidth(j); });
                if (g.y + g.h > bottom)
                    bottom = g.y + g.h;
            }
            return bottom;
        }
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
