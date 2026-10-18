"""Small rotated labels on toolbar handles, naming each toolbar.

A transparent overlay is laid over the drag handle on the left (or top,
for vertical toolbars) of every toolbar of a main window. It ignores the
mouse, so dragging the toolbar works as before, and it is not a toolbar
action, so QGIS, plugins and Interface Customization never see it. The
handle is widened through the stylesheet only while a label is attached
(QToolBar[studioLabel="true"]).
"""
from qgis.PyQt import sip
from qgis.PyQt.QtCore import QEvent, QObject, QRect, Qt
from qgis.PyQt.QtGui import QColor, QFont, QFontMetrics, QPainter
from qgis.PyQt.QtWidgets import QApplication, QMainWindow, QStyle, QToolBar, QWidget

PROPERTY = "studioLabel"

# QGIS's own toolbars (main window and layout designer). Others, such as
# plugin toolbars, get an abbreviation of their title.
ABBREVIATIONS = {
    "mFileToolBar": "PROJ",
    "mLayerToolBar": "LAYER",
    "mDataSourceManagerToolBar": "DATA",
    "mDigitizeToolBar": "EDIT",
    "mAdvancedDigitizeToolBar": "ADV",
    "mShapeDigitizeToolBar": "SHP",
    "mMeshToolBar": "MESH",
    "mSnappingToolBar": "SNAP",
    "mMapNavToolBar": "NAV",
    "mAttributesToolBar": "ATTR",
    "mSelectionToolBar": "SEL",
    "mLabelToolBar": "LABEL",
    "mAnnotationsToolBar": "ANNO",
    "mPluginToolBar": "PLUG",
    "mHelpToolBar": "HELP",
    "mRasterToolBar": "RAST",
    "mVectorToolBar": "VECT",
    "mDatabaseToolBar": "DB",
    "mWebToolBar": "WEB",
    "mGpsToolBar": "GPS",
    "mLayoutToolbar": "LYT",
    "mToolsToolbar": "TOOLS",
    "mNavigationToolbar": "NAV",
    "mActionsToolbar": "ARNG",
    "mAtlasToolbar": "ATLAS",
    "mReportToolbar": "RPT",
}


def abbreviation(toolbar):
    known = ABBREVIATIONS.get(toolbar.objectName())
    if known:
        return known
    words = [w for w in toolbar.windowTitle().replace("&", "").split() if w.lower() != "toolbar"]
    return words[0][:5].upper() if words else ""


class _Label(QWidget):
    """The overlay painted over one toolbar's handle."""

    def __init__(self, toolbar, color):
        super().__init__(toolbar)
        self.setObjectName("studioToolbarLabel")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.color = color
        self.text = ""
        font = QFont(QApplication.font())
        font.setPixelSize(8)
        font.setWeight(QFont.Weight.DemiBold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.6)
        self.setFont(font)

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        if not self.text:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setPen(self.color)
        rect = self.rect()
        if rect.height() >= rect.width():
            # Horizontal toolbar: vertical text reading bottom to top.
            painter.translate(0, rect.height())
            painter.rotate(-90)
            rect = QRect(0, 0, rect.height(), rect.width())
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text)
        painter.end()


class ToolbarLabels(QObject):
    """Attaches labels to the toolbars of main windows, including toolbars
    added later (plugins), and keeps them placed on the handle."""

    def __init__(self):
        super().__init__()
        self._color = QColor()
        self._windows = []
        self._labels = {}
        self._tooltips = {}

    def attach(self, window, color):
        """Label every toolbar of `window` (a QMainWindow)."""
        self._color = QColor(color)
        if window not in self._windows:
            self._windows.append(window)
            window.installEventFilter(self)
        for toolbar in window.findChildren(QToolBar):
            if toolbar.parent() is window:
                self._add(toolbar)

    def set_color(self, color):
        self._color = QColor(color)
        for label in self._labels.values():
            if not sip.isdeleted(label):
                label.color = self._color
                label.update()

    def detach(self):
        for window in self._windows:
            if not sip.isdeleted(window):
                window.removeEventFilter(self)
        self._windows = []
        for toolbar, label in list(self._labels.items()):
            if sip.isdeleted(toolbar):
                continue
            toolbar.removeEventFilter(self)
            toolbar.setProperty(PROPERTY, None)
            if toolbar in self._tooltips:
                toolbar.setToolTip(self._tooltips[toolbar])
            self._repolish(toolbar)
            if not sip.isdeleted(label):
                label.deleteLater()
        self._labels = {}
        self._tooltips = {}

    def _add(self, toolbar):
        if toolbar in self._labels:
            return
        label = _Label(toolbar, self._color)
        self._labels[toolbar] = label
        toolbar.setProperty(PROPERTY, True)
        self._repolish(toolbar)
        toolbar.installEventFilter(self)
        place = lambda *_args, toolbar=toolbar: self._place(toolbar)  # noqa: E731
        for signal in (toolbar.windowTitleChanged, toolbar.topLevelChanged,
                       toolbar.movableChanged, toolbar.orientationChanged):
            signal.connect(place)
        toolbar.destroyed.connect(lambda _obj=None, toolbar=toolbar: self._labels.pop(toolbar, None))
        self._place(toolbar)

    @staticmethod
    def _repolish(toolbar):
        """Apply the (un)widened handle rule and relayout the toolbar."""
        style = toolbar.style()
        style.unpolish(toolbar)
        style.polish(toolbar)
        QApplication.sendEvent(toolbar, QEvent(QEvent.Type.StyleChange))

    def _place(self, toolbar):
        label = self._labels.get(toolbar)
        if label is None or sip.isdeleted(label) or sip.isdeleted(toolbar):
            return
        # The handle only exists on a movable, docked toolbar.
        if not toolbar.isMovable() or toolbar.isFloating():
            label.hide()
            return
        style = toolbar.style()
        frame = style.pixelMetric(QStyle.PixelMetric.PM_ToolBarFrameWidth, None, toolbar)
        extent = style.pixelMetric(QStyle.PixelMetric.PM_ToolBarHandleExtent, None, toolbar)
        if toolbar.orientation() == Qt.Orientation.Horizontal:
            rect = QRect(frame, frame, extent, toolbar.height() - 2 * frame)
            if toolbar.layoutDirection() == Qt.LayoutDirection.RightToLeft:
                rect.moveRight(toolbar.width() - frame - 1)
            length = rect.height()
        else:
            rect = QRect(frame, frame, toolbar.width() - 2 * frame, extent)
            length = rect.width()
        text = abbreviation(toolbar)
        metrics = QFontMetrics(label.font())
        while text and metrics.horizontalAdvance(text) > length - 4:
            text = text[:-1]
        label.text = text
        label.setGeometry(rect)
        # The label ignores the mouse; the toolbar shows the full name when
        # hovering its handle (unless it already has a tooltip of its own).
        if toolbar not in self._tooltips:
            self._tooltips[toolbar] = toolbar.toolTip()
        if not self._tooltips[toolbar]:
            toolbar.setToolTip(toolbar.windowTitle())
        label.show()
        label.raise_()
        label.update()

    def eventFilter(self, watched, event):  # pylint: disable=invalid-name
        kind = event.type()
        if isinstance(watched, QMainWindow):
            if kind == QEvent.Type.ChildPolished:
                child = event.child()
                if isinstance(child, QToolBar) and child.parent() is watched:
                    self._add(child)
        elif kind in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.ParentChange,
                      QEvent.Type.LayoutRequest):
            self._place(watched)
        return False
