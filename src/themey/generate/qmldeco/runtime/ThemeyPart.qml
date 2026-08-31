// themey QML runtime v1 — one E16 border part.
// Geometry comes from resolver.js (live bindings against the decoration
// frame size and the measured caption); imagery is a BorderImage whose
// border insets are the part's pre-scaled __EDGE_SCALING; title parts draw
// the caption (with optional E16 shadow effect); button parts host a
// DecorationButton via ThemeyButton so clicks fire window requests from
// ANY border location. References main.qml's `root` id through the QML
// context chain, exactly like Plastik's PlastikButton does.
//
// Delegate contract: `modelData`/`index` are REQUIRED properties filled by
// the Repeater — declaring required properties disables context-property
// injection, so `part: modelData` in the instantiating file would receive
// undefined. Every binding also guards `part` for teardown ordering and
// the KCM preview.
import QtQuick
import "resolver.js" as Resolver

Item {
    id: partItem
    required property var modelData
    required property int index
    readonly property var part: modelData
    readonly property int partIndex: index
    readonly property int outScale: root.themeData.scale

    readonly property var geo: {
        // Dependencies (frame size, measured caption widths, font state)
        // are registered transparently through the calls below.
        if (!partItem.part)
            return { x: 0, y: 0, w: 0, h: 0 };
        return Resolver.partGeometry(
            root.themeData, partItem.partIndex, root.width, root.height,
            function (i) { return root.titleTextWidth(i); });
    }
    x: geo.x
    y: geo.y
    width: geo.w
    height: geo.h
    z: partIndex
    visible: {
        if (!partItem.part)
            return false;
        if (root.clientShaded && !partItem.part.keepWhenShaded)
            return false;
        if (root.clientMaximized && partItem.part.hideWhenMaximized)
            return false;
        return true;
    }

    readonly property bool hovered: buttonLoader.item ? buttonLoader.item.hovered === true : false
    readonly property bool pressed: buttonLoader.item ? buttonLoader.item.pressed === true : false
    // DecorationButton binds `toggled` for OnAllDesktops/Shade — without
    // this the toggle buttons work but give no visual feedback.
    readonly property bool toggled: buttonLoader.item ? buttonLoader.item.toggled === true : false
    readonly property var textCfg: partItem.part && partItem.part.text ? partItem.part.text : null

    BorderImage {
        anchors.fill: parent
        visible: partItem.part !== null && partItem.part.images !== null
        source: {
            var imgs = partItem.part ? partItem.part.images : null;
            if (!imgs)
                return "";
            var a = root.clientActive;
            if (partItem.pressed)
                return Qt.resolvedUrl(a && imgs.pressedActive ? imgs.pressedActive : (imgs.pressed || imgs.normal));
            if (partItem.hovered)
                return Qt.resolvedUrl(a && imgs.hoverActive ? imgs.hoverActive : (imgs.hover || imgs.normal));
            // `|| imgs.pressed` keeps a stale installed theme.js (no
            // toggled slots) degrading to clicked art instead of blank.
            if (partItem.toggled)
                return Qt.resolvedUrl(a && imgs.toggledActive ? imgs.toggledActive : (imgs.toggled || imgs.pressed || imgs.normal));
            return Qt.resolvedUrl(a && imgs.normalActive ? imgs.normalActive : imgs.normal);
        }
        border.left: partItem.part ? partItem.part.insets.left : 0
        border.right: partItem.part ? partItem.part.insets.right : 0
        border.top: partItem.part ? partItem.part.insets.top : 0
        border.bottom: partItem.part ? partItem.part.insets.bottom : 0
        smooth: false
    }

    // Caption text — only title parts carry a text config. The part is
    // already text-sized by the resolver, so the text fills the padding box
    // (pads are ref px; scale to output px for pixel positioning).
    Text {
        id: captionText
        visible: partItem.textCfg !== null && !partItem.part.vertical
        x: partItem.part ? partItem.part.padLeft * partItem.outScale : 0
        width: partItem.part
               ? Math.max(0, partItem.width
                          - (partItem.part.padLeft + partItem.part.padRight) * partItem.outScale)
               : 0
        anchors.verticalCenter: parent.verticalCenter
        anchors.verticalCenterOffset: partItem.part
            ? (partItem.part.padTop - partItem.part.padBottom) * partItem.outScale / 2
            : 0
        text: root.clientCaption
        elide: Text.ElideRight
        color: root.clientActive
               ? (partItem.textCfg ? partItem.textCfg.colorActive : "#ffffff")
               : (partItem.textCfg ? partItem.textCfg.colorNormal : "#c0c0c0")
        font.family: partItem.textCfg
                     ? root.fontFamilyAt(partItem.textCfg.fontIndex) : ""
        font.pixelSize: partItem.textCfg ? partItem.textCfg.pixelSize : 10
        font.italic: root.fontStyleAt(partItem.textCfg, "italic")
        font.bold: root.fontStyleAt(partItem.textCfg, "bold")
        style: partItem.textCfg && partItem.textCfg.shadow
               ? Text.Raised : Text.Normal
        styleColor: partItem.textCfg ? partItem.textCfg.shadowColor : "#000000"
    }

    // Vertical titles (best-effort): same text rotated to run down the part.
    Text {
        visible: partItem.textCfg !== null && partItem.part.vertical === true
        anchors.centerIn: parent
        rotation: 90
        text: root.clientCaption
        color: captionText.color
        font: captionText.font
        style: captionText.style
        styleColor: captionText.styleColor
    }

    Loader {
        id: buttonLoader
        anchors.fill: parent
        active: partItem.part !== null && partItem.part.button !== null
        sourceComponent: ThemeyButton {
            kind: partItem.part && partItem.part.button ? partItem.part.button : ""
        }
    }
}
