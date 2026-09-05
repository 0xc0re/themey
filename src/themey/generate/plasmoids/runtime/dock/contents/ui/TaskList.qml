/*
    SPDX-FileCopyrightText: 2024 Custom Developer
    SPDX-FileCopyrightText: 2026 themey contributors
    SPDX-License-Identifier: GPL-2.0-or-later
*/

import QtQuick
import org.kde.kirigami as Kirigami
import org.kde.ksvg as KSvg
import org.kde.taskmanager as TaskManager

import "code/TaskTools.js" as TaskTools

Item {
    id: taskListRoot

    property var model
    property bool vertical: false
    property int panelLocation: 4  // PlasmaCore.Types.BottomEdge default
    property int panelThickness: 48
    property bool zoomEnabled: true
    property real zoomFactor: 1.5
    property int zoomDuration: 150
    property bool zoomNeighbors: true
    property real neighborZoomFactor: 1.2
    property int iconSpacing: 1
    property bool widgetHovered: false
    property bool parabolicEnabled: true
    property int maxParabolicRise: 12
    property bool shrinkDistant: false
    property real distantShrinkFactor: 0.8
    property bool antiClip: false
    property int iconSizePercent: 100

    // The active Plasma Style has widgets/tasks art (probed in main.qml).
    property bool hasTaskArt: false
    // Plasmoid.configuration.taskHoverEffect.
    property bool hoverEffect: true

    // Auto-shrink properties
    property bool autoShrink: true
    property int minIconSize: 24
    property int availableSpace: 0  // Available space for icons (width for horizontal, height for vertical)

    // Audio
    property var pulseAudio: null
    property bool showAudioIndicator: false
    property bool allowVolumeControl: false

    property int hoveredIndex: -1

    // Continuous mouse position for smooth zoom transitions
    property real mousePos: -1  // Position along the icon row (x for horizontal, y for vertical)
    property bool mouseInArea: false

    // Tracks whether mouse has moved recently (to distinguish "left" from "stationary")
    property bool mouseMovedRecently: false

    // Drag state
    property int dragSourceIndex: -1
    property bool dragInProgress: false

    // Helper to get audio streams for a task
    function audioStreamsForTask(modelIndex) {
        if (!pulseAudio) return [];

        const start = modelIndex;
        const start_row = model.index(modelIndex, 0);

        const start_pid = model.data(start_row, TaskManager.AbstractTasksModel.AppPid) || 0;
        const start_appName = model.data(start_row, TaskManager.AbstractTasksModel.AppName) || "";

        let start_streams = [];

        if (start_pid > 0) {
            start_streams = pulseAudio.streamsForPid(start_pid);
            if (start_streams.length === 0 && start_appName.length > 0) {
                start_streams = pulseAudio.streamsForAppName(start_appName);
            }
        }

        return start_streams;
    }

    // Reset hover state
    function resetHoverState() {
        taskListRoot.hoveredIndex = -1;
        taskListRoot.mouseInArea = false;
        taskListRoot.mousePos = -1;
        taskListRoot.mouseMovedRecently = false;
    }

    // Force reset from parent (called by HoverHandler in main.qml)
    function forceResetHover() {
        activityTimer.stop();
        resetHoverState();
    }

    // Two-phase exit detection that doesn't rely on onExited or containsMouse:
    //
    // Phase 1: activityTimer fires 250ms after last mouse movement.
    //          Sets mouseMovedRecently=false and starts confirmTimer.
    //
    // Phase 2: confirmTimer fires 100ms later. If mouseMovedRecently
    //          is still false (no new movement), reset hover state.
    //          If mouse moved in between, it was just a pause — keep zoom.

    Timer {
        id: activityTimer
        interval: 250
        onTriggered: {
            taskListRoot.mouseMovedRecently = false;
            confirmTimer.start();
        }
    }

    Timer {
        id: confirmTimer
        interval: 100
        onTriggered: {
            if (!taskListRoot.mouseMovedRecently && !taskListRoot.widgetHovered) {
                resetHoverState();
            }
        }
    }

    // Update audio streams when PulseAudio streams change
    Connections {
        target: pulseAudio
        function onStreamsChanged() {
            // Force re-evaluation of audioStreams for all tasks
            for (let i = 0; i < taskRepeater.count; i++) {
                const task = taskRepeater.itemAt(i);
                if (task) {
                    task.audioStreams = taskListRoot.audioStreamsForTask(i);
                }
            }
        }
    }

    signal taskClicked(int index, int button, int modifiers)
    signal taskContextMenu(int index)
    signal taskFilesDropped(int index, var urls)
    signal taskLauncherDropped(var urls)
    signal taskDragHover(int index, bool isDragHovered)

    function getTaskAt(index) {
        return taskRepeater.itemAt(index);
    }

    // Counter that increments on model changes to force rebinding
    property int modelUpdateCounter: 0

    function getGroupChildCount(taskIndex) {
        // Reference counter to trigger updates
        var _ = modelUpdateCounter;
        var idx = model.makeModelIndex(taskIndex);
        return model.rowCount(idx);
    }

    function getActiveChildIndex(taskIndex) {
        // Reference counter to trigger updates
        var _ = modelUpdateCounter;
        var parentIdx = model.makeModelIndex(taskIndex);
        var count = model.rowCount(parentIdx);
        for (var i = 0; i < count; i++) {
            var childIdx = model.index(i, 0, parentIdx);
            if (model.data(childIdx, TaskManager.AbstractTasksModel.IsActive)) {
                return i;
            }
        }
        return -1;
    }

    // Update counter when model data changes
    Connections {
        target: taskListRoot.model
        function onDataChanged() {
            taskListRoot.modelUpdateCounter++;
        }
    }

    // The plate metrics every delegate insets its icon by. Invisible and
    // pinned to the `normal` prefix, exactly like upstream's taskFrame
    // (plasma-desktop Plasma/6.6 applets/taskmanager/qml/main.qml:356-363).
    KSvg.FrameSvgItem {
        id: taskMetricFrame
        visible: false
        imagePath: "widgets/tasks"
        prefix: TaskTools.taskPrefix("normal", taskListRoot.panelLocation)
    }

    // With theme art the padding is the plate's own margins, not Kirigami
    // spacing — but the cell still has to budget the ZOOM HEADROOM the
    // fork's `- smallSpacing * 4` was really buying: Task sizes itself
    // baseSize square and scales the icon by up to maxZoomFactor, so a
    // cell equal to the panel thickness would be clipped the moment it
    // was hovered. Dividing by that factor makes the plate exactly fill
    // the panel at FULL zoom, and the parabolic rise then overflows into
    // the floating panel's margin as the fork already relies on.
    readonly property int baseIconSize: hasTaskArt
        ? Math.round(panelThickness / Math.max(1, zoomFactor))
        : Math.max(panelThickness - Kirigami.Units.smallSpacing * 4, Kirigami.Units.iconSizes.medium)
    readonly property int preAntiClipSize: antiClip ? Math.round(baseIconSize * 0.9) : baseIconSize
    readonly property int itemSpacing: Kirigami.Units.smallSpacing * iconSpacing

    // Auto-shrink calculation
    readonly property int effectiveIconSize: {
        // Skip auto-shrink if disabled or invalid state
        if (!autoShrink || taskRepeater.count === 0) {
            return preAntiClipSize;
        }

        // Need reasonable available space (at least space for one icon at min size)
        if (availableSpace < minIconSize) {
            return preAntiClipSize;
        }

        // Calculate how much space icons would take at base size
        var totalSpacing = Math.max(0, taskRepeater.count - 1) * itemSpacing;
        var neededSpace = taskRepeater.count * preAntiClipSize + totalSpacing;

        // If they fit, use normal size
        if (neededSpace <= availableSpace) {
            return preAntiClipSize;
        }

        // Calculate shrunk size
        var shrunkSize = Math.floor((availableSpace - totalSpacing) / taskRepeater.count);

        // Clamp to minimum
        return Math.max(minIconSize, shrunkSize);
    }

    // Fixed implicit size based on item count - completely static
    readonly property int contentSize: taskRepeater.count * effectiveIconSize + Math.max(0, taskRepeater.count - 1) * itemSpacing
    // Extra strip after the last icon so a file can be dropped onto the dock
    // itself (pin default app) instead of onto an existing icon (open with).
    readonly property int launcherDropGutter: Kirigami.Units.gridUnit

    implicitWidth: vertical ? panelThickness : contentSize + launcherDropGutter
    implicitHeight: vertical ? contentSize + launcherDropGutter : panelThickness

    // Volume popup dialog
    property var volumeDialog: null
    readonly property Component volumePopupComponent: Qt.createComponent("VolumePopup.qml")

    function showVolumePopup(taskIndex, percent) {
        var task = taskRepeater.itemAt(taskIndex);
        if (!task) return;

        if (volumeDialog) {
            volumeDialog.volumePercent = percent;
            volumeDialog.restartHideTimer();
            return;
        }

        if (volumePopupComponent.status !== Component.Ready) {
            console.warn("VolumePopup component error:", volumePopupComponent.errorString());
            return;
        }

        volumeDialog = volumePopupComponent.createObject(taskListRoot, {
            visualParent: task,
            volumePercent: percent,
        });

        if (!volumeDialog) {
            console.warn("VolumePopup creation failed");
            return;
        }

        volumeDialog.onVisibleChanged.connect(function() {
            if (volumeDialog && !volumeDialog.visible) {
                volumeDialog.destroy();
                volumeDialog = null;
            }
        });
    }

    // --- delegate geometry publishing ----------------------------------
    //
    // KWin's minimize effects (Squash, Magic Lamp) animate a window into
    // the rect the task manager publishes for it. Upstream does this from
    // main.qml (plasma-desktop Plasma/6.6 applets/taskmanager/qml/main.qml:
    // 120-132 and 248-316) through the private C++ backend's globalRect();
    // the fork dropped the private plugin and the step with it, so every
    // minimize animated from nowhere. mapToGlobal is the pure-QML
    // equivalent of globalRect.
    //
    // The item handed over as the delegate is the STATIC cell, never the
    // zoomed icon: on Wayland KWin reads the item's own geometry and
    // ignores the rect, and the cell is the one rect that does not move
    // with the parabolic rise.
    function publishGeometries() {
        if (!model || !model.requestPublishDelegateGeometry) {
            return;
        }
        for (let i = 0; i < taskRepeater.count; ++i) {
            const task = taskRepeater.itemAt(i);
            if (!task || task.isLauncher) {
                continue;
            }
            const origin = task.mapToGlobal(0, 0);
            model.requestPublishDelegateGeometry(
                model.makeModelIndex(i),
                Qt.rect(origin.x, origin.y, task.width, task.height),
                task);
        }
    }

    // Upstream's 500 ms settle timer: the panel has usually not finished
    // moving when the property that triggered this changed.
    function schedulePublishGeometries() {
        publishTimer.restart();
    }

    Timer {
        id: publishTimer
        interval: 500
        repeat: false
        onTriggered: taskListRoot.publishGeometries()
    }

    Component.onCompleted: schedulePublishGeometries()
    onWidthChanged: schedulePublishGeometries()
    onHeightChanged: schedulePublishGeometries()
    onXChanged: schedulePublishGeometries()
    onYChanged: schedulePublishGeometries()
    onPanelLocationChanged: schedulePublishGeometries()

    // Container for manually positioned tasks - no layout recalculations
    Item {
        id: taskContainer
        anchors.fill: parent

        Repeater {
            id: taskRepeater
            model: taskListRoot.model

            onCountChanged: taskListRoot.schedulePublishGeometries()

            delegate: Task {
                id: taskDelegate

                required property var model
                required property int index

                // Manual positioning - no layout involvement
                x: vertical ? (taskListRoot.width - width) / 2 : index * (effectiveIconSize + itemSpacing)
                y: vertical ? index * (effectiveIconSize + itemSpacing) : (taskListRoot.height - height) / 2

                vertical: taskListRoot.vertical
                panelLocation: taskListRoot.panelLocation
                taskIndex: index
                iconSource: model.decoration
                taskName: model.display || ""
                isActive: model.IsActive || false
                isMinimized: model.IsMinimized || false
                isLauncher: model.IsLauncher || false
                isDemandingAttention: model.IsDemandingAttention || false
                isGroupParent: model.IsGroupParent || false

                // Group properties - use function to force recalculation (depend on modelUpdateCounter)
                groupChildCount: {
                    var _ = taskListRoot.modelUpdateCounter;
                    return isGroupParent ? taskListRoot.getGroupChildCount(index) : 0;
                }
                activeChildIndex: {
                    var _ = taskListRoot.modelUpdateCounter;
                    return isGroupParent ? taskListRoot.getActiveChildIndex(index) : -1;
                }

                // Audio properties
                maxVolume: taskListRoot.pulseAudio ? taskListRoot.pulseAudio.normalVolume : 65536
                volumeStep: Math.round(maxVolume * 0.05)  // 5% per scroll step
                showAudioIndicator: taskListRoot.showAudioIndicator
                allowVolumeControl: taskListRoot.allowVolumeControl

                // Audio streams for this task
                audioStreams: taskListRoot.audioStreamsForTask(index)

                baseSize: taskListRoot.effectiveIconSize
                iconSizePercent: taskListRoot.iconSizePercent
                hasTaskArt: taskListRoot.hasTaskArt
                hoverEffect: taskListRoot.hoverEffect
                metricFrame: taskMetricFrame
                // The dock zooms a neighbourhood, so the list's own pointer
                // tracking is the authority on which cell is hovered.
                hoveredByList: taskListRoot.hoveredIndex === index
                zoomEnabled: taskListRoot.zoomEnabled
                maxZoomFactor: taskListRoot.zoomFactor
                zoomDuration: taskListRoot.zoomDuration
                isTransitioning: taskListRoot.mouseInArea
                parabolicEnabled: taskListRoot.parabolicEnabled
                maxParabolicRise: taskListRoot.maxParabolicRise

                targetZoom: {
                    if (!taskListRoot.zoomEnabled) return 1.0;
                    if (!taskListRoot.mouseInArea || taskListRoot.mousePos < 0) return 1.0;

                    // Calculate center position of this icon
                    var itemSize = effectiveIconSize + itemSpacing;
                    var iconCenter = index * itemSize + effectiveIconSize / 2;

                    // Distance from mouse to icon center (in pixels)
                    var pixelDistance = Math.abs(taskListRoot.mousePos - iconCenter);

                    // Normalize distance: 0 = at center, 1 = one full icon away
                    var normalizedDistance = pixelDistance / itemSize;

                    // Smoothstep function for continuous transitions
                    function smoothstep(edge0, edge1, x) {
                        var t = Math.max(0, Math.min(1, (x - edge0) / (edge1 - edge0)));
                        return t * t * (3 - 2 * t);
                    }

                    // Define key points for interpolation
                    var maxZoom = taskListRoot.zoomFactor;
                    var borderZoom = taskListRoot.zoomNeighbors ? taskListRoot.neighborZoomFactor : 1.0;
                    var maxDist = taskListRoot.zoomNeighbors ? 2.5 : 0.5;
                    var minZoom = taskListRoot.shrinkDistant ? taskListRoot.distantShrinkFactor : 1.0;
                    var farDist = maxDist + 2.0;  // Distance at which icons reach minimum size

                    if (normalizedDistance <= 0.5) {
                        // Inside main icon: smooth from maxZoom to borderZoom
                        var t = smoothstep(0, 0.5, normalizedDistance);
                        return maxZoom + (borderZoom - maxZoom) * t;
                    } else if (normalizedDistance <= maxDist) {
                        // Neighbor icons: smooth from borderZoom to 1.0
                        var t = smoothstep(0.5, maxDist, normalizedDistance);
                        return borderZoom + (1.0 - borderZoom) * t;
                    } else if (taskListRoot.shrinkDistant && normalizedDistance <= farDist) {
                        // Distant icons: smooth from 1.0 to minZoom
                        var t = smoothstep(maxDist, farDist, normalizedDistance);
                        return 1.0 + (minZoom - 1.0) * t;
                    }

                    return minZoom;
                }

                targetRise: {
                    if (!taskListRoot.parabolicEnabled) return 0;
                    if (!taskListRoot.mouseInArea || taskListRoot.mousePos < 0) return 0;

                    var itemSize = effectiveIconSize + itemSpacing;
                    var iconCenter = index * itemSize + effectiveIconSize / 2;
                    var pixelDistance = Math.abs(taskListRoot.mousePos - iconCenter);
                    var normalizedDistance = pixelDistance / itemSize;

                    // Smoothstep function
                    function smoothstep(edge0, edge1, x) {
                        var t = Math.max(0, Math.min(1, (x - edge0) / (edge1 - edge0)));
                        return t * t * (3 - 2 * t);
                    }

                    var maxDist = 2.5;
                    if (normalizedDistance <= maxDist) {
                        var t = smoothstep(0, maxDist, normalizedDistance);
                        return taskListRoot.maxParabolicRise * (1 - t);
                    }
                    return 0;
                }

                onHoverChanged: function(isHovered) {
                    if (isHovered) {
                        taskListRoot.mouseMovedRecently = true;
                        activityTimer.restart();
                        taskListRoot.hoveredIndex = index;
                        taskListRoot.mouseInArea = true;
                        // Initialize mousePos to icon center to prevent stale position bug
                        var itemSize = effectiveIconSize + itemSpacing;
                        taskListRoot.mousePos = index * itemSize + effectiveIconSize / 2;
                    } else if (taskListRoot.hoveredIndex === index) {
                        activityTimer.restart();
                    }
                }

                onMouseMoved: function(localX, localY) {
                    // Convert local position to global position in the task list
                    var itemSize = effectiveIconSize + itemSpacing;
                    var globalPos;
                    if (vertical) {
                        globalPos = index * itemSize + localY;
                    } else {
                        globalPos = index * itemSize + localX;
                    }
                    taskListRoot.mousePos = globalPos;

                    // Handle drag reordering
                    if (isDragging && taskListRoot.dragInProgress) {
                        var targetIdx = Math.floor(globalPos / itemSize);
                        targetIdx = Math.max(0, Math.min(targetIdx, taskRepeater.count - 1));
                        if (targetIdx !== taskListRoot.dragSourceIndex) {
                            var sourceModelIndex = taskListRoot.model.makeModelIndex(taskListRoot.dragSourceIndex);
                            var targetModelIndex = taskListRoot.model.makeModelIndex(targetIdx);
                            taskListRoot.model.move(taskListRoot.dragSourceIndex, targetIdx);
                            taskListRoot.dragSourceIndex = targetIdx;
                        }
                    }
                }

                onClicked: function(button, modifiers) {
                    taskListRoot.taskClicked(index, button, modifiers);
                }

                onContextMenuRequested: {
                    taskListRoot.taskContextMenu(index);
                }

                onVolumeChanged: function(percent) {
                    taskListRoot.showVolumePopup(index, percent);
                }

                onDragStarted: {
                    taskListRoot.dragSourceIndex = index;
                    taskListRoot.dragInProgress = true;
                }

                onIsDraggingChanged: {
                    if (!isDragging && taskListRoot.dragInProgress) {
                        taskListRoot.dragInProgress = false;
                        taskListRoot.dragSourceIndex = -1;
                        // Sync launchers to persist the new order
                        taskListRoot.model.syncLaunchers();
                    }
                }

                onFilesDropped: function(urls) {
                    taskListRoot.taskFilesDropped(index, urls);
                }

                onLauncherDropped: function(urls) {
                    taskListRoot.taskLauncherDropped(urls);
                }

                onDragHoverChanged: function(isDragHovered) {
                    taskListRoot.taskDragHover(index, isDragHovered);
                }
            }
        }

        // Global hover sensor: tracks the pointer across all icons for the
        // parabolic zoom. Qt.NoButton so it is a sensor and nothing else —
        // it sits above every delegate (z: 1000), and accepting buttons
        // there meant hand-declining every press, release and click back
        // down to the task underneath.
        MouseArea {
            id: globalMouseArea
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.NoButton
            z: 1000

            onPositionChanged: function(mouse) {
                taskListRoot.mouseMovedRecently = true;
                activityTimer.restart();
                taskListRoot.mouseInArea = true;
                taskListRoot.mousePos = vertical ? mouse.y : mouse.x;

                var itemSize = effectiveIconSize + itemSpacing;
                var idx = Math.floor((vertical ? mouse.y : mouse.x) / itemSize);
                if (idx >= 0 && idx < taskRepeater.count) {
                    taskListRoot.hoveredIndex = idx;
                }
            }

            onExited: {
                activityTimer.stop();
                confirmTimer.stop();
                resetHoverState();
            }
        }
    }
}
