"""Toolbar names: a title above each toolbar's buttons.

A docked horizontal toolbar gets a title strip above its buttons, the name
centred between two hairlines whose ends turn down into short ticks:
┌──── Map Navigation ────┐, so each toolbar's edges show. The strip is
made by a top margin on every item of the toolbar (QToolBar[studioLabel=
"title"] in style.qss, @toolbar_title_height = TITLE_HEIGHT), so the items
keep their own layout and the toolbar simply grows by the strip; widgets
the stylesheet cannot push down (containers such as the snapping widget)
get the same space as a top contents margin, undone on detach. A
transparent overlay paints the strip. It ignores the mouse, so the buttons
and dragging work as before, and it is not a toolbar action, so QGIS,
plugins and Interface Customization never see it.

The title is horizontal text, drawn straight onto the window: Windows
smooths it with ClearType like all other UI text. The capitals are centred
in the strip with the baseline on a whole device pixel, and the hairlines
and ticks are one device pixel thick, so the strip stays sharp at every
scaling.

A vertical toolbar (docked left or right) has no room for a strip; it gets
a short three-letter name across the top of a taller handle
(QToolBar[studioLabel="handle"]). Floating toolbars show their name in
their own title bar and get nothing.
"""
from qgis.PyQt import sip
import functools

from qgis.PyQt.QtCore import QEvent, QMargins, QObject, QPointF, QRect, Qt, QTimer
from qgis.PyQt.QtGui import QColor, QFont, QFontDatabase, QFontMetrics, QFontMetricsF, QPainter, QPen
from qgis.PyQt.QtWidgets import (
    QAbstractSpinBox, QApplication, QComboBox, QLabel, QLineEdit, QMainWindow, QStyle, QToolBar,
    QToolButton, QWidget,
)

PROPERTY = "studioLabel"
# Height of the title strip (logical px), shared with style.qss.
TITLE_HEIGHT = 15
TITLE_SIZE = 11
# Regular weight, slightly spaced: SemiBold letters ran together,
# especially at 150 %.
TITLE_SPACING = 0.5
# Gap between the name and its hairlines.
RULE_GAP = 6
# Items the stylesheet pushes down itself (box model); any other widget in
# a titled toolbar gets a top contents margin instead.
STYLED_ITEMS = (QToolButton, QComboBox, QAbstractSpinBox, QLineEdit, QLabel)

# Shorter English names for QGIS's own toolbars, by their title without
# "Toolbar". Translated titles are used as they are.
SHORT_TITLES = {
    "Data Source Manager": "Data Sources",
    "Manage Layers": "Layers",
    "Label": "Labels",
    "Mesh Digitizing": "Mesh",
    "Shape Digitizing": "Shapes",
}

# Vertical toolbars: three-letter names across the top of the handle.
# Others, such as plugin toolbars, get the first three letters of their
# title.
ABBREVIATIONS = {
    "mFileToolBar": "PRJ",
    "mLayerToolBar": "LYR",
    "mDataSourceManagerToolBar": "DAT",
    "mDigitizeToolBar": "EDT",
    "mAdvancedDigitizeToolBar": "ADV",
    "mShapeDigitizeToolBar": "SHP",
    "mMeshToolBar": "MSH",
    "mSnappingToolBar": "SNP",
    "mMapNavToolBar": "NAV",
    "mAttributesToolBar": "ATR",
    "mSelectionToolBar": "SEL",
    "mLabelToolBar": "LBL",
    "mAnnotationsToolBar": "ANN",
    "mPluginToolBar": "PLG",
    "mHelpToolBar": "HLP",
    "mRasterToolBar": "RST",
    "mVectorToolBar": "VEC",
    "mDatabaseToolBar": "DBS",
    "mWebToolBar": "WEB",
    "mGpsToolBar": "GPS",
    "mLayoutToolbar": "LYT",
    "mToolsToolbar": "TLS",
    "mNavigationToolbar": "NAV",
    "mActionsToolbar": "ALN",
    "mAtlasToolbar": "ATL",
    "mReportToolbar": "RPT",
}
NAME_LENGTH = 3
# Handle names: largest first (see _fit), one shared size.
HANDLE_SIZES = (12, 11, 10, 9)
LETTER_SPACING = 1.0
# Whole pixels only: fractional spacing puts letters between pixels.
SPACINGS = (LETTER_SPACING, 0)


def title(toolbar):
    """The name shown above a toolbar: its title without "Toolbar"."""
    words = [w for w in toolbar.windowTitle().replace("&", "").split() if w.lower() != "toolbar"]
    text = " ".join(words)
    return SHORT_TITLES.get(text, text)


def abbreviation(toolbar):
    known = ABBREVIATIONS.get(toolbar.objectName())
    if known:
        return known
    words = [w for w in toolbar.windowTitle().replace("&", "").split() if w.lower() != "toolbar"]
    return words[0][:NAME_LENGTH].upper() if words else ""


@functools.lru_cache(maxsize=1)
def _face():
    """Segoe UI where installed (Windows): hand-hinted for small sizes,
    so small text keeps solid stems where a font with automatic hinting
    (Inter, the UI font) stays soft. Elsewhere the UI font."""
    return "Segoe UI" if "Segoe UI" in QFontDatabase.families() else None


def _font(size, weight, spacing=0.0):
    font = QFont(QApplication.font())
    if _face():
        font.setFamily(_face())
    font.setPixelSize(size)
    font.setWeight(weight)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    return font


def title_font():
    return _font(TITLE_SIZE, QFont.Weight.Normal, TITLE_SPACING)


def handle_font(size, spacing=LETTER_SPACING):
    # The bundled Inter has no Bold (a synthesised one is smeared).
    return _font(size, QFont.Weight.Bold if _face() else QFont.Weight.DemiBold, spacing)


def _snap(value, ratio):
    return round(value * ratio) / ratio


class _Label(QWidget):
    """The overlay painting one toolbar's name: a title strip above the
    buttons, or a short name across the top of a vertical toolbar."""

    def __init__(self, toolbar, color, rule):
        super().__init__(toolbar)
        self.setObjectName("studioToolbarLabel")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.color = color
        self.rule = rule
        self.text = ""
        self.titled = True
        # What _place last applied, so unchanged layout requests are free.
        self.placed = None

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        if not self.text:
            return
        painter = QPainter(self)
        ratio = self.devicePixelRatioF()
        metrics = QFontMetricsF(self.font())
        rect = self.rect()
        width = metrics.horizontalAdvance(self.text)
        # Capitals centred (centring the full line height would push them
        # up by the descender); baseline and start on whole device pixels,
        # where hinting keeps stems sharp.
        x = _snap((rect.width() - width) / 2, ratio)
        baseline = _snap((rect.height() + metrics.capHeight()) / 2, ratio)
        painter.setFont(self.font())
        painter.setPen(self.color)
        painter.drawText(QPointF(x, baseline), self.text)
        if self.titled:
            # Hairlines either side, one device pixel through the middle
            # of the capitals.
            y = (int((baseline - metrics.capHeight() / 2) * ratio) + 0.5) / ratio
            pen = QPen(self.rule)
            pen.setCosmetic(True)
            pen.setWidth(1)
            painter.setPen(pen)
            # Each end turns down into a tick, so the toolbar's edges show
            # without a separator: ┌── Name ──┐. Ticks on device pixel
            # columns, ending a pixel above the buttons.
            left = (round(1 * ratio) + 0.5) / ratio
            right = (round((rect.width() - 1) * ratio) - 0.5) / ratio
            bottom = (round(rect.height() * ratio) - 1.5) / ratio
            if x - RULE_GAP > left + 4:
                painter.drawLine(QPointF(left, y), QPointF(x - RULE_GAP, y))
                painter.drawLine(QPointF(left, y), QPointF(left, bottom))
            if x + width + RULE_GAP < right - 4:
                painter.drawLine(QPointF(x + width + RULE_GAP, y), QPointF(right, y))
                painter.drawLine(QPointF(right, y), QPointF(right, bottom))
        painter.end()


def fit(text, length):
    """The handle font for `text` across a handle `length` pixels wide
    (the size all handle names share, see _uniform), and the text
    (shortened only if it does not fit even at the smallest size)."""
    size, spacing, text = _fit(text, length, QApplication.font().family(), HANDLE_SIZES)
    return handle_font(size, spacing), text


def _candidates(sizes):
    """(size, spacing) pairs, largest first; tighter letter spacing before
    a smaller size."""
    return [(size, spacing) for size in sizes for spacing in SPACINGS]


@functools.lru_cache(maxsize=64)
def _uniform(length, _family, sizes):
    """Index of the first candidate at which every QGIS toolbar's short
    name fits `length` pixels: the size handle names share (the smallest if
    none fits; longer names are then cut)."""
    names = {name for name in ABBREVIATIONS.values() if len(name) <= NAME_LENGTH}
    candidates = _candidates(sizes)
    for index, (size, spacing) in enumerate(candidates):
        metrics = QFontMetrics(handle_font(size, spacing))
        if all(metrics.horizontalAdvance(name) <= length for name in names):
            return index
    return len(candidates) - 1


@functools.lru_cache(maxsize=256)
def _fit(text, length, family, sizes):
    # From the shared size down, so other names (plugin toolbars) match it
    # and only a name that does not fit gets smaller, then cut.
    candidates = _candidates(sizes)
    for size, spacing in candidates[_uniform(length, family, sizes):]:
        if QFontMetrics(handle_font(size, spacing)).horizontalAdvance(text) <= length:
            return size, spacing, text
    metrics = QFontMetrics(handle_font(sizes[-1], 0))
    while text and metrics.horizontalAdvance(text) > length:
        text = text[:-1]
    return sizes[-1], 0, text


class ToolbarLabels(QObject):
    """Attaches names to the toolbars of main windows, including toolbars
    added later (plugins), and keeps them placed."""

    def __init__(self):
        super().__init__()
        self._color = QColor()
        self._rule = QColor()
        self._windows = []
        self._labels = {}
        self._tooltips = {}
        # Signal connections per toolbar, undone on detach.
        self._slots = {}
        # Widgets given a top contents margin in titled toolbars, with
        # their own margins to restore: {toolbar: {widget: QMargins}}.
        self._shifted = {}

    def attach(self, window, color, rule):
        """Name every toolbar of `window` (a QMainWindow): text in
        `color`, hairlines in `rule`."""
        self._color = QColor(color)
        self._rule = QColor(rule)
        if window not in self._windows:
            self._windows.append(window)
            window.installEventFilter(self)
        for toolbar in window.findChildren(QToolBar):
            if toolbar.parent() is window:
                self._add(toolbar)

    def set_color(self, color, rule):
        self._color = QColor(color)
        self._rule = QColor(rule)
        for label in self._labels.values():
            if not sip.isdeleted(label):
                label.color = self._color
                label.rule = self._rule
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
            for signal, slot in self._slots.pop(toolbar, ()):
                signal.disconnect(slot)
            self._set_mode(toolbar, None)
            if toolbar in self._tooltips:
                toolbar.setToolTip(self._tooltips[toolbar])
            if not sip.isdeleted(label):
                label.deleteLater()
        self._labels = {}
        self._tooltips = {}
        self._slots = {}
        self._shifted = {}

    def _add(self, toolbar):
        if toolbar in self._labels:
            return
        label = _Label(toolbar, self._color, self._rule)
        self._labels[toolbar] = label
        toolbar.installEventFilter(self)
        place = lambda *_args, toolbar=toolbar: self._place(toolbar)  # noqa: E731
        forget = lambda _obj=None, toolbar=toolbar: self._forget(toolbar)  # noqa: E731
        slots = [(signal, place) for signal in (
            toolbar.windowTitleChanged, toolbar.topLevelChanged,
            toolbar.movableChanged, toolbar.orientationChanged,
        )] + [(toolbar.destroyed, forget)]
        for signal, slot in slots:
            signal.connect(slot)
        self._slots[toolbar] = slots
        self._place(toolbar)

    def _forget(self, toolbar):
        self._labels.pop(toolbar, None)
        self._tooltips.pop(toolbar, None)
        self._slots.pop(toolbar, None)
        self._shifted.pop(toolbar, None)

    # ---- Modes ------------------------------------------------------------

    @staticmethod
    def _mode(toolbar):
        """"title" (docked horizontal), "handle" (docked vertical, movable)
        or None (floating, or a fixed vertical toolbar: no handle)."""
        if toolbar.isFloating():
            return None
        if toolbar.orientation() == Qt.Orientation.Horizontal:
            return "title"
        return "handle" if toolbar.isMovable() else None

    def _set_mode(self, toolbar, mode):
        """Apply a mode's stylesheet rules (title strip or taller handle)
        and contents margins, and relayout the toolbar."""
        if toolbar.property(PROPERTY) == mode:
            if mode == "title":
                self._shift(toolbar)
            return
        toolbar.setProperty(PROPERTY, mode)
        if mode != "title":
            self._unshift(toolbar)
        # The rules select on the toolbar's property: its items need
        # repolishing too, and a style change event drops the size hints
        # they cache (combo boxes), so the toolbar relayouts with the strip.
        style = toolbar.style()
        for widget in [toolbar] + [c for c in toolbar.children() if isinstance(c, QWidget)]:
            if widget is self._labels.get(toolbar):
                continue
            style.unpolish(widget)
            style.polish(widget)
            QApplication.sendEvent(widget, QEvent(QEvent.Type.StyleChange))
        if mode == "title":
            self._shift(toolbar)

    def _shift(self, toolbar):
        """Give items the stylesheet cannot push down (containers) the
        title strip as a top contents margin."""
        shifted = self._shifted.setdefault(toolbar, {})
        for action in toolbar.actions():
            widget = toolbar.widgetForAction(action)
            if (widget is None or widget in shifted or isinstance(widget, STYLED_ITEMS)
                    or widget.metaObject().className() == "QToolBarSeparator"):
                continue
            margins = widget.contentsMargins()
            shifted[widget] = margins
            widget.setContentsMargins(margins + QMargins(0, TITLE_HEIGHT, 0, 0))

    def _unshift(self, toolbar):
        for widget, margins in self._shifted.pop(toolbar, {}).items():
            if not sip.isdeleted(widget):
                widget.setContentsMargins(margins)

    # ---- Placing ----------------------------------------------------------

    def _place(self, toolbar):
        label = self._labels.get(toolbar)
        if label is None or sip.isdeleted(label) or sip.isdeleted(toolbar):
            return
        mode = self._mode(toolbar)
        self._set_mode(toolbar, mode)
        if mode is None:
            label.hide()
            label.placed = None
            return
        style = toolbar.style()
        frame = style.pixelMetric(QStyle.PixelMetric.PM_ToolBarFrameWidth, None, toolbar)
        extent = style.pixelMetric(QStyle.PixelMetric.PM_ToolBarHandleExtent, None, toolbar)
        if mode == "title":
            # Above the buttons, beside the handle (if any). The last
            # toolbar of a row is stretched to the window's edge: the strip
            # spans its items, not the empty rest.
            handle = extent if toolbar.isMovable() else 0
            rect = QRect(frame + handle, frame, toolbar.width() - 2 * frame - handle, TITLE_HEIGHT)
            if toolbar.layoutDirection() == Qt.LayoutDirection.RightToLeft:
                rect.moveLeft(frame)
            items = self._items_span(toolbar)
            if items is not None:
                # A name wider than few buttons (one-button toolbars) may
                # spread into the toolbar's own room, if it has any:
                # centred on the buttons, shifted where an edge is near.
                need = QFontMetrics(title_font()).horizontalAdvance(title(toolbar)) + 2
                width = max(items[1] - items[0] + 1, need)
                left = (items[0] + items[1] + 1 - width) // 2
                left = max(rect.left(), min(left, rect.right() + 1 - width))
                rect.setLeft(max(rect.left(), left))
                rect.setRight(min(rect.right(), left + width - 1))
        else:
            rect = QRect(frame, frame, toolbar.width() - 2 * frame, extent)
        name = toolbar.windowTitle()
        placed = (mode, rect, name, toolbar.objectName(), QApplication.font().family())
        # Toolbars send layout requests often; only redo the work when the
        # strip or the name actually changed.
        if placed == label.placed and label.isVisible():
            return
        label.placed = placed
        label.titled = mode == "title"
        if label.titled:
            font = title_font()
            text = QFontMetrics(font).elidedText(title(toolbar), Qt.TextElideMode.ElideRight, rect.width() - 2)
        else:
            font, text = fit(abbreviation(toolbar), rect.width() - 4)
            # The full name on hovering the handle (unless the toolbar has a
            # tooltip of its own).
            if toolbar not in self._tooltips:
                self._tooltips[toolbar] = toolbar.toolTip()
            if not self._tooltips[toolbar]:
                toolbar.setToolTip(name)
        label.setFont(font)
        label.text = text
        label.setGeometry(rect)
        label.show()
        label.raise_()
        label.update()

    @staticmethod
    def _items_span(toolbar):
        """(left, right) of a toolbar's visible items (and its overflow
        button), or None before it is laid out."""
        widgets = [toolbar.widgetForAction(a) for a in toolbar.actions()]
        widgets.append(toolbar.findChild(QToolButton, "qt_toolbar_ext_button"))
        spans = [(w.x(), w.x() + w.width() - 1) for w in widgets if w is not None and w.isVisible()]
        if not spans:
            return None
        return min(s[0] for s in spans), max(s[1] for s in spans)

    def eventFilter(self, watched, event):  # pylint: disable=invalid-name
        kind = event.type()
        if isinstance(watched, QMainWindow):
            if kind == QEvent.Type.ChildPolished:
                child = event.child()
                if isinstance(child, QToolBar) and child.parent() is watched:
                    self._add(child)
        elif kind == QEvent.Type.ActionAdded:
            # A widget added later (a plugin's) exists once the toolbar has
            # handled the event.
            QTimer.singleShot(0, lambda toolbar=watched: self._refresh(toolbar))
        elif kind in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.ParentChange,
                      QEvent.Type.LayoutRequest):
            self._place(watched)
        return False

    def _refresh(self, toolbar):
        if toolbar in self._labels and not sip.isdeleted(toolbar) and toolbar.property(PROPERTY) == "title":
            self._shift(toolbar)
