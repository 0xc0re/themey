// themey QML runtime v1 — one E16 border part.
// Geometry comes from resolver.js (live bindings against the decoration
// frame size and the measured caption); imagery is a BorderImage whose
// border insets are the pre-scaled __EDGE_SCALING of the image SLOT being
// shown (E16 slices per image state — part.slotInsets[slot], part.insets
// as the fallback); title parts draw the caption positioned by E16's
// justification formula (text.c: x + ((limit - textw) * justh) >> 10),
// with the E16 shadow (+1,+1) / outline effect in the tclass state's
// __BACKGROUND_COLOR; button parts host a DecorationButton via
// ThemeyButton so clicks fire window requests from ANY border location.
// References main.qml's `root` id through the QML context chain, exactly
// like Plastik's PlastikButton does.
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
    // May be fractional (e.g. 1.5) — pad offsets Math.round at the end.
    readonly property real outScale: root.themeData.scale

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
    // E16 stacks __KEEP_ON_TOP __OFF parts under the client window; KWin's
    // client covers the deco there anyway, so the visible consequence is
    // that every off part sits under every on-top part, declaration order
    // within each group.
    z: (partItem.part && partItem.part.keepOnTop === false)
       ? partIndex - root.themeData.parts.length : partIndex
    visible: {
        if (!partItem.part)
            return false;
        if (root.clientShaded && !partItem.part.keepWhenShaded)
            return false;
        return true;
    }

    readonly property bool hovered: buttonLoader.item ? buttonLoader.item.hovered === true : false
    readonly property bool pressed: buttonLoader.item ? buttonLoader.item.pressed === true : false
    // DecorationButton binds `toggled` for OnAllDesktops/Shade — without
    // this the toggle buttons work but give no visual feedback.
    readonly property bool toggled: buttonLoader.item ? buttonLoader.item.toggled === true : false
    readonly property var textCfg: partItem.part && partItem.part.text ? partItem.part.text : null

    // The image slot currently shown — resolved once so the BorderImage
    // source and its per-slot insets can never disagree.
    readonly property string baseSlot: {
        var imgs = partItem.part ? partItem.part.images : null;
        if (!imgs)
            return "";
        var a = root.clientActive;
        if (partItem.pressed)
            return a && imgs.pressedActive ? "pressedActive" : (imgs.pressed ? "pressed" : "normal");
        if (partItem.hovered)
            return a && imgs.hoverActive ? "hoverActive" : (imgs.hover ? "hover" : "normal");
        // `|| pressed` keeps a stale installed theme.js (no toggled
        // slots) degrading to clicked art instead of blank.
        if (partItem.toggled)
            return a && imgs.toggledActive ? "toggledActive"
                 : (imgs.toggled ? "toggled" : (imgs.pressed ? "pressed" : "normal"));
        return a && imgs.normalActive ? "normalActive" : "normal";
    }
    // E16's sticky / sticky_active groups (iclass.c ImageclassGetImageState):
    // a window on all desktops wears the "<slot>Sticky" art on every part.
    // theme.js resolves those slots through ImageclassPopulate's chains, so
    // a theme without sticky art simply repeats its normal art here.
    readonly property string imageSlot: {
        var imgs = partItem.part ? partItem.part.images : null;
        var base = partItem.baseSlot;
        if (!imgs || !base)
            return base;
        if (root.clientOnAllDesktops && imgs[base + "Sticky"])
            return base + "Sticky";
        return base;
    }
    readonly property var slotInsets: {
        var p = partItem.part;
        if (!p)
            return { left: 0, right: 0, top: 0, bottom: 0 };
        if (p.slotInsets && p.slotInsets[partItem.imageSlot])
            return p.slotInsets[partItem.imageSlot];
        return p.insets;
    }

    BorderImage {
        anchors.fill: parent
        visible: partItem.part !== null && partItem.part.images !== null
        source: {
            var imgs = partItem.part ? partItem.part.images : null;
            if (!imgs || !partItem.imageSlot)
                return "";
            return Qt.resolvedUrl(imgs[partItem.imageSlot] || imgs.normal);
        }
        border.left: partItem.slotInsets.left
        border.right: partItem.slotInsets.right
        border.top: partItem.slotInsets.top
        border.bottom: partItem.slotInsets.bottom
        // E16 __FILLRULE per image state: __TILE / __TILE_H / __TILE_V
        // repeat the art at native size on that axis instead of
        // stretching it (iclass.c ImagestateMakeBg EImageTile).
        readonly property string tile: {
            var p = partItem.part;
            var tt = p && p.slotTile ? p.slotTile[partItem.imageSlot] : null;
            return tt ? tt : "";
        }
        horizontalTileMode: tile === "h" || tile === "both" ? BorderImage.Repeat : BorderImage.Stretch
        verticalTileMode: tile === "v" || tile === "both" ? BorderImage.Repeat : BorderImage.Stretch
        smooth: false
    }

    // Caption text — only title parts carry a text config. The caption
    // sits inside the padding box (pads are ref px; scale to output px)
    // at E16's justified offset: TextDraw's
    //   xx = x + (((textwidth_limit - ww) * justh) >> 10)
    // so 0 hugs the left pad, 512 centers, 1024 hugs the right pad. A
    // text-sized plaque leaves no slack (the resolver already placed the
    // part); a fixed-width title bar is where this matters.
    readonly property int captionAvail: partItem.part
        ? Math.max(0, partItem.width
                   - Math.round((partItem.part.padLeft + partItem.part.padRight)
                                * partItem.outScale))
        : 0
    // Natural width comes from main.qml's hidden measurer (titleTextWidth)
    // — reading this item's own implicitWidth while elide is set trips
    // QML's binding-loop detector.
    // E16 text state per WINDOW (borders.c:164): active × on-all-desktops
    // selects the tclass group; theme.js resolved each through
    // TextclassPopulate's chain. Orientation: FONT_TO_DOWN 1 reads
    // top-to-bottom (+90°), FONT_TO_UP 2 bottom-to-top (-90°, E16
    // EImageOrientate 3); RIGHT 0 / undefined tokens stay horizontal even
    // in a tall plaque, as E16 draws them.
    readonly property string textState: root.clientOnAllDesktops
        ? (root.clientActive ? "StickyActive" : "Sticky")
        : (root.clientActive ? "Active" : "Normal")
    readonly property int textOrientation: partItem.textCfg && partItem.textCfg.orientation !== undefined
        ? partItem.textCfg.orientation : 0
    // Rotation follows the tclass alone (text.c TextDrawRotBack), not the
    // part's geometry: Arietta's FONT_TO_UP title is an 18 px full-height
    // side strip with MAX_HEIGHT 99999, while the MAX_HEIGHT 0 plaque rule
    // (borders.c:371) only sizes the part.
    readonly property bool textRotated: partItem.textCfg !== null
        && (partItem.textOrientation === 1 || partItem.textOrientation === 2)
    function textField(prefix, fallback) {
        var cfg = partItem.textCfg;
        if (!cfg)
            return fallback;
        var v = cfg[prefix + partItem.textState];
        if (v !== undefined && v !== null)
            return v;
        v = cfg[prefix + (root.clientActive ? "Active" : "Normal")];
        return v !== undefined && v !== null ? v : fallback;
    }
    Text {
        id: captionText
        visible: partItem.textCfg !== null && !partItem.textRotated
        width: Math.min(partItem.captionAvail, root.titleTextWidth(partItem.partIndex))
        x: {
            if (!partItem.part)
                return 0;
            var just = partItem.part.justification === undefined ? 512 : partItem.part.justification;
            var slack = Math.max(0, partItem.captionAvail - width);
            return Math.round(partItem.part.padLeft * partItem.outScale)
                 + ((slack * just) >> 10);
        }
        anchors.verticalCenter: parent.verticalCenter
        anchors.verticalCenterOffset: partItem.part
            ? Math.round((partItem.part.padTop - partItem.part.padBottom)
                         * partItem.outScale / 2)
            : 0
        text: root.clientCaption
        // E16 TextstateTextFit1 keeps the head and tail ("..." in the middle).
        elide: Text.ElideMiddle
        color: partItem.textField("color", root.clientActive ? "#ffffff" : "#c0c0c0")
        font.family: partItem.textCfg
                     ? root.fontFamilyAt(partItem.textCfg.fontIndex) : ""
        font.pixelSize: partItem.textCfg ? partItem.textCfg.pixelSize : 10
        font.italic: root.fontStyleAt(partItem.textCfg, "italic")
        font.bold: root.fontStyleAt(partItem.textCfg, "bold")
        // E16 TsTextDraw: effect 1 = one bg_col copy at (+1,+1) — Qt's
        // Text.Raised; effect 2 = four bg_col copies at the orthogonal
        // neighbours — Text.Outline. The color is the state's bg_col.
        style: {
            var eff = partItem.textField("effect", partItem.textCfg ? partItem.textCfg.effect : "none");
            return eff === "shadow" ? Text.Raised : (eff === "outline" ? Text.Outline : Text.Normal);
        }
        styleColor: partItem.textField("effectColor", "#000000")
        rotation: partItem.textOrientation === 3 ? 180 : 0
    }

    // Vertical titles: the same text rotated to run along the part in
    // E16's reading direction.
    Text {
        visible: partItem.textCfg !== null && partItem.textRotated
        anchors.centerIn: parent
        rotation: partItem.textOrientation === 2 ? -90 : 90
        // Runs along the part's height; long captions elide in the middle.
        width: partItem.part
            ? Math.max(0, Math.min(
                  partItem.height - Math.round((partItem.part.padTop + partItem.part.padBottom)
                                               * partItem.outScale),
                  root.titleTextWidth(partItem.partIndex)))
            : 0
        elide: Text.ElideMiddle
        horizontalAlignment: Text.AlignHCenter
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

    // Capability-disabled buttons (e.g. shade — KWin removed shading in
    // Plasma 6) must absorb clicks, not fall through to the decoration
    // beneath: button rects sit inside the installed title item, so the
    // fallthrough would start a titlebar move-drag from a dead button.
    // A disabled Item's children can't receive events, so the absorber
    // sits here, above the Loader; while the button is enabled this
    // MouseArea is disabled and fully transparent to events.
    MouseArea {
        anchors.fill: parent
        enabled: buttonLoader.item ? buttonLoader.item.enabled === false : false
    }
}
