"""Toolbar names: a title above each toolbar's buttons.

A docked horizontal toolbar gets a title strip above its buttons, its name
centred over them. The strip is
made by a top margin on every item of the toolbar (QToolBar[studioLabel=
"title"] in style.qss, @toolbar_title_height = TITLE_SPACE), so the items
keep their own layout and the toolbar simply grows by the strip; widgets
the stylesheet cannot push down (containers such as the snapping widget)
get the same space as a top contents margin, undone on detach. A
transparent overlay paints the strip. It ignores the mouse, so the buttons
and dragging work as before, and it is not a toolbar action, so QGIS,
plugins and Interface Customization never see it. Toolbars side by side
are told apart by a divider line in the handle gap between them, the
toolbar's full height:  Project │ Map Navigation │, and a row is closed
by one after its last toolbar's buttons. Rows of toolbars are underlined
like the menu bar: the last toolbar of a row reaches the window's edge,
so the toolbars' lines join into one across the window. A toolbar wider
than its buttons (QMainWindow gives it the room left of a neighbour
dragged further right) has them centred, its name with them.

The title is horizontal text, drawn straight onto the window: Windows
smooths it with ClearType like all other UI text. The capitals are centred
in the strip with the baseline on a whole device pixel, and the dividers
are one device pixel thick, so both stay sharp at every scaling.

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
# Height of the title strip (logical px), and the gap between it and the
# buttons, so a hovered or checked button's fill keeps clear of the name.
# Their sum is the room the buttons are pushed down by (TITLE_SPACE,
# shared with style.qss).
TITLE_HEIGHT = 13
TITLE_GAP = 3
TITLE_SPACE = TITLE_HEIGHT + TITLE_GAP
# Small capitals: a quiet caption that never competes with the icons.
# Regular weight, spaced by a whole pixel: SemiBold letters ran together,
# especially at 150 %, and fractional spacing puts letters between pixels.
TITLE_SIZE = 10
TITLE_SPACING = 1.0
# Room either side of a name when a toolbar is widened to fit it.
RULE_ROOM = 6
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


def title(toolbar):
    """The name shown above a toolbar: its title without "Toolbar", in
    capitals."""
    words = [w for w in toolbar.windowTitle().replace("&", "").split() if w.lower() != "toolbar"]
    text = " ".join(words)
    return SHORT_TITLES.get(text, text).upper()


def has_items(toolbar):
    """Whether a toolbar shows anything: plugin toolbars (Database, Web,
    Vector...) stay empty until a plugin adds a button."""
    return any(action.isVisible() and not action.isSeparator() for action in toolbar.actions())


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
    return _title_font(QApplication.font().key())


@functools.lru_cache(maxsize=4)
def _title_font(_app_font):
    # Keyed by the application font, which the themes change.
    return _font(TITLE_SIZE, QFont.Weight.Normal, TITLE_SPACING)


@functools.lru_cache(maxsize=256)
def _title_width(text, _app_font):
    return QFontMetrics(_title_font(_app_font)).horizontalAdvance(text)


def title_width(text):
    """Width of a toolbar name in the title font (cached)."""
    return _title_width(text, QApplication.font().key())


def _snap(value, ratio):
    return round(value * ratio) / ratio


class _Label(QWidget):
    """The overlay painting one toolbar's name: a title strip above the
    buttons, or a short name across the top of a vertical toolbar."""

    def __init__(self, toolbar, color):
        super().__init__(toolbar)
        self.setObjectName("studioToolbarLabel")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.color = color
        self.text = ""
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
        painter.end()


class _Divider(QWidget):
    """A line one device pixel thick, in `rule`: down the middle of the
    widget (the divider between a titled toolbar and the one to its left,
    in this toolbar's handle gap), or along its bottom when `row` (the line
    under a row of toolbars)."""

    def __init__(self, toolbar, rule, row=False):
        super().__init__(toolbar)
        self.setObjectName("studioToolbarRowLine" if row else "studioToolbarDivider")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.rule = rule
        self.row = row

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        painter = QPainter(self)
        ratio = self.devicePixelRatioF()
        pen = QPen(self.rule)
        pen.setCosmetic(True)
        pen.setWidth(1)
        painter.setPen(pen)
        if self.row:
            y = (int(self.height() * ratio) - 0.5) / ratio
            painter.drawLine(QPointF(0, y), QPointF(self.width(), y))
        else:
            x = (int(self.width() / 2 * ratio) + 0.5) / ratio
            painter.drawLine(QPointF(x, 0), QPointF(x, self.height()))
        painter.end()


class ToolbarLabels(QObject):
    """Attaches names to the toolbars of main windows, including toolbars
    added later (plugins), and keeps them placed.

    Toolbars relayout often (QGIS enables and disables actions on every
    selection or layer change), so the work per layout request is kept
    small: the strip, the dividers and the centring of one toolbar, done
    at once (Qt has laid the toolbar out before an event filter sees the
    request, so centred buttons never show at the left first). Which
    toolbars share a row, and which is the last of it, is worked out once
    per window after toolbars move, show, hide or resize."""

    def __init__(self):
        super().__init__()
        self._color = QColor()
        self._rule = QColor()
        self._row_rule = QColor()
        self._windows = []
        self._window_slots = {}
        self._labels = {}
        self._dividers = {}
        self._row_lines = {}
        # Dividers closing a row after its last toolbar's buttons.
        self._ends = {}
        # Toolbars that are the last of their row (see _arrange_rows).
        self._last = {}
        # Overflow buttons, looked up once per toolbar.
        self._extensions = {}
        # Item widgets per toolbar, with its layout and the item count they
        # were read at, and frame and handle metrics: read once, not on
        # every layout request.
        self._widgets = {}
        self._frames = {}
        # Centring applied per toolbar: (offset, the items' x positions it
        # left), so it can be undone while the layout has not reset them.
        self._offsets = {}
        # Minimum widths raised so a name fits, with the toolbar's own.
        self._min_widths = {}
        # Windows whose rows are arranged on the next event-loop pass.
        self._rows_pending = set()
        self._tooltips = {}
        # Signal connections per toolbar, undone on detach.
        self._slots = {}
        # Widgets given a top contents margin in titled toolbars, with
        # their own margins to restore: {toolbar: {widget: QMargins}}.
        self._shifted = {}
        # Whether each toolbar shows anything (see has_items), and the
        # visibility of its actions as last seen, by id: action changes are
        # frequent (enabling), visibility changes rare.
        self._filled = {}
        self._action_visible = {}
        # Toolbars refreshed on the next event-loop pass.
        self._refresh_pending = set()
        # Empty toolbars already shrunk to their own size (_collapse_empty).
        self._collapsed = set()

    def attach(self, window, color, rule, row_rule=None):
        """Name every toolbar of `window` (a QMainWindow): text in
        `color`, dividers between toolbars in `rule`, lines under rows of
        toolbars in `row_rule` (by default `rule`)."""
        self._color = QColor(color)
        self._rule = QColor(rule)
        self._row_rule = QColor(rule if row_rule is None else row_rule)
        if window not in self._windows:
            self._windows.append(window)
            window.installEventFilter(self)
            # Layout designers close: forget them, not loop over them.
            # Disconnected on detach, or each theme switch would add one.
            slot = lambda _obj=None, window=window: self._drop_window(window)  # noqa: E731
            window.destroyed.connect(slot)
            self._window_slots[id(window)] = (window, slot)
        for toolbar in window.findChildren(QToolBar):
            if toolbar.parent() is window:
                self._add(toolbar)

    def _drop_window(self, window):
        self._window_slots.pop(id(window), None)
        if window in self._windows:
            self._windows.remove(window)
        self._rows_pending.discard(window)

    def set_color(self, color, rule, row_rule=None):
        self._color = QColor(color)
        self._rule = QColor(rule)
        self._row_rule = QColor(rule if row_rule is None else row_rule)
        self._frames = {}  # another theme, other metrics
        for label in self._labels.values():
            if not sip.isdeleted(label):
                label.color = self._color
                label.update()
        for lines, color in ((self._dividers, self._rule), (self._ends, self._rule),
                             (self._row_lines, self._row_rule)):
            for line in lines.values():
                if not sip.isdeleted(line):
                    line.rule = color
                    line.update()

    def detach(self):
        for window in self._windows:
            if not sip.isdeleted(window):
                window.removeEventFilter(self)
        for window, slot in self._window_slots.values():
            try:
                window.destroyed.disconnect(slot)
            except (TypeError, RuntimeError):
                pass  # already gone
        self._windows = []
        self._window_slots = {}
        for toolbar, label in list(self._labels.items()):
            if sip.isdeleted(toolbar):
                continue
            toolbar.removeEventFilter(self)
            for signal, slot in self._slots.pop(toolbar, ()):
                signal.disconnect(slot)
            self._set_mode(toolbar, None)
            self._fit_name(toolbar, None)
            if toolbar in self._tooltips:
                toolbar.setToolTip(self._tooltips[toolbar])
            for widget in (label, self._dividers.get(toolbar), self._row_lines.get(toolbar),
                           self._ends.get(toolbar)):
                if widget is not None and not sip.isdeleted(widget):
                    widget.deleteLater()
            # Buttons centred by hand go back to where the layout puts them.
            toolbar.updateGeometry()
            if toolbar.layout() is not None:
                toolbar.layout().invalidate()
        self._labels = {}
        self._dividers = {}
        self._row_lines = {}
        self._ends = {}
        self._last = {}
        self._extensions = {}
        self._widgets = {}
        self._frames = {}
        self._offsets = {}
        self._min_widths = {}
        self._rows_pending = set()
        self._tooltips = {}
        self._slots = {}
        self._shifted = {}
        self._filled = {}
        self._action_visible = {}
        self._refresh_pending = set()
        self._collapsed = set()

    def _add(self, toolbar):
        if toolbar in self._labels:
            return
        self._filled[toolbar] = has_items(toolbar)
        label = _Label(toolbar, self._color)
        self._labels[toolbar] = label
        self._dividers[toolbar] = _Divider(toolbar, self._rule)
        self._row_lines[toolbar] = _Divider(toolbar, self._row_rule, row=True)
        self._ends[toolbar] = _Divider(toolbar, self._rule)
        self._extensions[toolbar] = toolbar.findChild(QToolButton, "qt_toolbar_ext_button")
        toolbar.installEventFilter(self)
        moved = lambda *_args, toolbar=toolbar: self._moved(toolbar)  # noqa: E731
        forget = lambda _obj=None, toolbar=toolbar: self._forget(toolbar)  # noqa: E731
        slots = [(signal, moved) for signal in (
            toolbar.windowTitleChanged, toolbar.topLevelChanged,
            toolbar.movableChanged, toolbar.orientationChanged,
        )] + [(toolbar.destroyed, forget)]
        for signal, slot in slots:
            signal.connect(slot)
        self._slots[toolbar] = slots
        self._moved(toolbar)

    def _forget(self, toolbar):
        for table in (self._labels, self._dividers, self._row_lines, self._ends, self._last,
                      self._extensions, self._widgets, self._frames, self._offsets, self._min_widths,
                      self._tooltips, self._slots, self._shifted, self._filled):
            table.pop(toolbar, None)
        self._refresh_pending.discard(toolbar)
        self._collapsed.discard(toolbar)

    def _overlays(self, toolbar):
        return (self._labels.get(toolbar), self._dividers.get(toolbar), self._row_lines.get(toolbar),
                self._ends.get(toolbar))

    # ---- Modes ------------------------------------------------------------

    def _mode(self, toolbar):
        """"title" (docked horizontal), "handle" (docked vertical, movable)
        or None (floating, empty, or a fixed vertical toolbar: no handle).
        An empty toolbar gets no name, strip or dividers: it shrinks to a
        sliver instead of showing a labelled empty box."""
        if toolbar.isFloating() or not self._filled.get(toolbar, True):
            return None
        if toolbar.orientation() == Qt.Orientation.Horizontal:
            return "title"
        return "handle" if toolbar.isMovable() else None

    def _set_mode(self, toolbar, mode):
        """Apply a mode's stylesheet rules (title strip or taller handle)
        and contents margins, and relayout the toolbar."""
        if toolbar.property(PROPERTY) == mode:
            return
        toolbar.setProperty(PROPERTY, mode)
        self._frames.pop(toolbar, None)
        if mode != "title":
            self._unshift(toolbar)
        # The rules select on the toolbar's property: its items need
        # repolishing too, and a style change event drops the size hints
        # they cache (combo boxes), so the toolbar relayouts with the strip.
        style = toolbar.style()
        overlays = self._overlays(toolbar)
        for widget in [toolbar] + [c for c in toolbar.children() if isinstance(c, QWidget)]:
            if widget in overlays:
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
        for widget in self._layout_widgets(toolbar):
            if (widget in shifted or isinstance(widget, STYLED_ITEMS)
                    or widget.metaObject().className() == "QToolBarSeparator"):
                continue
            margins = widget.contentsMargins()
            shifted[widget] = margins
            widget.setContentsMargins(margins + QMargins(0, TITLE_SPACE, 0, 0))

    def _unshift(self, toolbar):
        for widget, margins in self._shifted.pop(toolbar, {}).items():
            if not sip.isdeleted(widget):
                widget.setContentsMargins(margins)

    def _fit_name(self, toolbar, mode):
        """A titled toolbar at least as wide as its name, so no name is cut
        short when toolbars with few buttons sit side by side; the
        toolbar's own minimum width otherwise."""
        own = self._min_widths.get(toolbar)
        need = None
        if mode == "title":
            frame, extent = self._metrics(toolbar)
            handle = extent if toolbar.isMovable() else 0
            need = title_width(title(toolbar)) + 2 * RULE_ROOM + 2 * frame + handle
        if need is not None and need > (toolbar.minimumWidth() if own is None else own):
            if own is None:
                self._min_widths[toolbar] = toolbar.minimumWidth()
            if toolbar.minimumWidth() != need:
                toolbar.setMinimumWidth(need)
        elif own is not None:
            del self._min_widths[toolbar]
            toolbar.setMinimumWidth(own)

    # ---- Placing ----------------------------------------------------------

    def _metrics(self, toolbar):
        """(frame width, handle extent) of a toolbar, as its style has them."""
        metrics = self._frames.get(toolbar)
        if metrics is None:
            style = toolbar.style()
            metrics = self._frames[toolbar] = (
                style.pixelMetric(QStyle.PixelMetric.PM_ToolBarFrameWidth, None, toolbar),
                style.pixelMetric(QStyle.PixelMetric.PM_ToolBarHandleExtent, None, toolbar),
            )
        return metrics

    def _moved(self, toolbar):
        """The toolbar moved, showed, hid or changed mode: place it, and
        arrange its window's rows once things settle."""
        self._update(toolbar)
        self._schedule_rows(toolbar.parentWidget())

    def _update(self, toolbar):
        """Place one toolbar's strip and dividers, and centre its buttons:
        cheap, run on every layout request."""
        if toolbar not in self._labels or sip.isdeleted(toolbar):
            return
        mode = self._mode(toolbar)
        self._set_mode(toolbar, mode)
        self._fit_name(toolbar, mode)
        frame, extent = self._metrics(toolbar)
        items = self._items_span(toolbar) if mode == "title" else None
        items = self._fit_items(toolbar, mode, frame, extent, items)
        self._place_divider(toolbar, mode, frame, extent)
        line = self._row_lines.get(toolbar)
        if line is not None and not sip.isdeleted(line) and line.isVisible():
            self._show(line, QRect(0, toolbar.height() - 2, toolbar.width(), 2))
        self._place(toolbar, mode, frame, extent, items)

    def _place(self, toolbar, mode, frame, extent, items):
        label = self._labels.get(toolbar)
        if label is None or sip.isdeleted(label):
            return
        if mode is None:
            label.hide()
            label.placed = None
            return
        if mode == "title":
            # Above the buttons, beside the handle (if any). The last
            # toolbar of a row is stretched to the window's edge: the strip
            # spans its items, not the empty rest.
            handle = extent if toolbar.isMovable() else 0
            rect = QRect(frame + handle, frame, toolbar.width() - 2 * frame - handle, TITLE_HEIGHT)
            if toolbar.layoutDirection() == Qt.LayoutDirection.RightToLeft:
                rect.moveLeft(frame)
            if items is not None:
                # A name wider than few buttons (one-button toolbars) may
                # spread into the toolbar's own room, if it has any:
                # centred on the buttons, shifted where an edge is near.
                need = title_width(title(toolbar)) + 2
                width = max(items[1] - items[0] + 1, need)
                left = (items[0] + items[1] + 1 - width) // 2
                left = max(rect.left(), min(left, rect.right() + 1 - width))
                rect.setLeft(max(rect.left(), left))
                rect.setRight(min(rect.right(), left + width - 1))
        else:
            rect = QRect(frame, frame, toolbar.width() - 2 * frame, extent)
            # Centred on the column of buttons (the toolbar can be a few
            # pixels wider on one side), like a title on its buttons.
            span = self._items_span(toolbar)
            if span is not None:
                centre = (span[0] + span[1] + 1) / 2
                half = min(centre - rect.left(), rect.right() + 1 - centre)
                if half > 0:
                    rect = QRect(round(centre - half), rect.top(), round(2 * half), rect.height())
        name = toolbar.windowTitle()
        placed = (mode, rect, name, toolbar.objectName(), title_font())
        # Toolbars send layout requests often; only redo the work when the
        # strip or the name actually changed.
        if placed == label.placed and label.isVisible():
            return
        label.placed = placed
        # Vertical toolbars' short names in the same small capitals as the
        # titles of horizontal ones.
        font = title_font()
        if mode == "title":
            text = QFontMetrics(font).elidedText(title(toolbar), Qt.TextElideMode.ElideRight, rect.width() - 2)
        else:
            text = abbreviation(toolbar)
            metrics = QFontMetrics(font)
            while text and metrics.horizontalAdvance(text) > rect.width() - 2:
                text = text[:-1]
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

    def _place_divider(self, toolbar, mode, frame, extent):
        """The divider between a titled toolbar and its left neighbour, in
        the handle gap (the toolbar's own left edge when it has no handle);
        none for the first toolbar of a row."""
        divider = self._dividers.get(toolbar)
        if divider is None or sip.isdeleted(divider):
            return
        right_to_left = toolbar.layoutDirection() == Qt.LayoutDirection.RightToLeft
        parent = toolbar.parentWidget()
        if right_to_left:
            first = parent is None or toolbar.geometry().right() >= parent.width() - 1
        else:
            first = toolbar.x() <= 0
        if mode != "title" or first:
            divider.hide()
            return
        middle = frame + extent // 2 if toolbar.isMovable() else 0
        if right_to_left:
            middle = toolbar.width() - 1 - middle
        # The toolbar's full height, title strip included, meeting the lines
        # under the rows: it divides the names too, and is never mistaken
        # for a separator inside a toolbar.
        self._show(divider, QRect(middle - 1, 0, 3, toolbar.height()))

    def _fit_items(self, toolbar, mode, frame, extent, items):
        """Centre a toolbar's buttons in its width (not the last of a row,
        whose extra width is the rest of the window), and close a row after
        the last toolbar's buttons with a divider. Returns the buttons'
        span, as moved."""
        end = self._ends.get(toolbar)
        if end is None or sip.isdeleted(end):
            return items
        if mode != "title" or items is None or toolbar.layoutDirection() == Qt.LayoutDirection.RightToLeft:
            end.hide()
            return items
        middle = frame + extent // 2 if toolbar.isMovable() else 0
        # Where the layout put the buttons: the current positions, less a
        # centring still in place (a relayout puts them back at the left).
        widgets = [w for w in self._layout_widgets(toolbar) if w.isVisible()]
        offset, moved = self._offsets.get(toolbar, (0, None))
        if moved != tuple(w.x() for w in widgets):
            offset = 0
        items = (items[0] - offset, items[1] - offset)
        extension = self._extensions.get(toolbar)
        overflowing = extension is not None and not sip.isdeleted(extension) and extension.isVisible()
        delta = 0
        if not self._last.get(toolbar) and not overflowing:
            room_left = frame + (extent if toolbar.isMovable() else 0)
            room = toolbar.width() - frame - room_left - (items[1] - items[0] + 1)
            if room > 1:
                delta = room_left + room // 2 - items[0]
        if delta != offset:
            for widget in widgets:
                widget.move(widget.x() + delta - offset, widget.y())
        if delta:
            self._offsets[toolbar] = (delta, tuple(w.x() for w in widgets))
        else:
            self._offsets.pop(toolbar, None)
        items = (items[0] + delta, items[1] + delta)
        if not self._last.get(toolbar):
            end.hide()
            return items
        # The space between the start divider and the first button,
        # mirrored after the last one.
        x = items[1] + (items[0] - middle)
        if x >= toolbar.width() - 2:
            end.hide()
        else:
            self._show(end, QRect(x - 1, 0, 3, toolbar.height()))
        return items

    def _schedule_rows(self, window):
        """Arrange `window`'s rows once the current layout changes have
        settled: one toolbar moving changes its row for all."""
        if not isinstance(window, QMainWindow) or window in self._rows_pending:
            return
        self._rows_pending.add(window)
        QTimer.singleShot(0, lambda window=window: self._arrange_rows(window))

    def _arrange_rows(self, window):
        """Which titled toolbars of the top area share a row, and which is
        the last of each: each gets a line along its bottom (they join
        across the window, like the menu bar's), the last a divider closing
        the row, the others their buttons centred."""
        if window not in self._rows_pending:
            return
        self._rows_pending.discard(window)
        if sip.isdeleted(window):
            return
        rows = {}
        # Only toolbars whose part in their row changed are placed again:
        # each toolbar placed itself already on its own move or resize.
        changed = set()
        for toolbar, line in self._row_lines.items():
            if sip.isdeleted(toolbar) or sip.isdeleted(line) or toolbar.parentWidget() is not window:
                continue
            # Empty toolbars stay in their row: the line under it runs on
            # beneath them, never broken by a gap.
            if (toolbar.isVisible() and (toolbar.property(PROPERTY) == "title" or self._empty_docked(toolbar))
                    and window.toolBarArea(toolbar) == Qt.ToolBarArea.TopToolBarArea):
                rows.setdefault(toolbar.y(), []).append(toolbar)
                if not line.isVisible():
                    line.show()
                    changed.add(toolbar)
            else:
                line.hide()
                self._last[toolbar] = False
        for row in rows.values():
            # The row is closed after its last named toolbar (an empty one
            # after it shows nothing to close).
            titled = [toolbar for toolbar in row if toolbar.property(PROPERTY) == "title"]
            last = max(titled, key=lambda toolbar: toolbar.x()) if titled else None
            for toolbar in row:
                is_last = toolbar is last
                if self._last.get(toolbar) is not is_last:
                    self._last[toolbar] = is_last
                    changed.add(toolbar)
            self._collapse_empty(window, row)
        for toolbar in changed:
            self._update(toolbar)

    def _empty_docked(self, toolbar):
        """An empty toolbar docked in a horizontal row (see _mode)."""
        return (not self._filled.get(toolbar, True) and not toolbar.isFloating()
                and toolbar.orientation() == Qt.Orientation.Horizontal)

    def _collapse_empty(self, window, row):
        """Shrink empty toolbars to their own small size. QMainWindow keeps
        the width a toolbar was once dragged to (saved with the window
        layout), so an empty one can hold a wide blank gap between its
        neighbours. Inserting it again at the same place drops that width;
        the room goes to the row's last toolbar, which reaches the window's
        edge anyway. Once per toolbar and session."""
        for toolbar in row:
            if (self._filled.get(toolbar, True) or toolbar in self._collapsed
                    or toolbar.width() <= toolbar.sizeHint().width() + 1):
                continue
            after = [other for other in row if other.x() > toolbar.x()]
            if not after:
                continue
            self._collapsed.add(toolbar)
            window.insertToolBar(min(after, key=lambda other: other.x()), toolbar)
            toolbar.show()

    @staticmethod
    def _show(line, rect):
        if line.geometry() != rect or not line.isVisible():
            line.setGeometry(rect)
            line.show()
            line.raise_()

    def _layout_widgets(self, toolbar):
        """A toolbar's item widgets, read in one pass over its layout
        (QToolBar.widgetForAction searches the layout for each action) and
        kept until items are added or removed (the cache is dropped when a
        child is removed, so it never holds a deleted widget)."""
        cached = self._widgets.get(toolbar)
        layout = cached[0] if cached is not None else toolbar.layout()
        if layout is None or sip.isdeleted(layout):
            return []
        count = layout.count()
        if cached is not None and cached[1] == count:
            return cached[2]
        widgets = []
        for index in range(count):
            item = layout.itemAt(index)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widgets.append(widget)
        self._widgets[toolbar] = (layout, count, widgets)
        return widgets

    def _item_widgets(self, toolbar):
        """A toolbar's visible items and its overflow button."""
        widgets = [w for w in self._layout_widgets(toolbar) if w.isVisible()]
        extension = self._extensions.get(toolbar)
        if extension is not None and not sip.isdeleted(extension) and extension.isVisible():
            widgets.append(extension)
        return widgets

    def _items_span(self, toolbar):
        """(left, right) of a toolbar's visible items (and its overflow
        button), or None before it is laid out."""
        spans = [(w.x(), w.x() + w.width() - 1) for w in self._item_widgets(toolbar)]
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
        elif kind == QEvent.Type.LayoutRequest:
            # Qt has laid the toolbar out already (layouts see events before
            # event filters): re-centre now, before anything is painted.
            self._update(watched)
        elif kind == QEvent.Type.ActionChanged:
            # Sent for every enable and disable; only a change of an
            # action's visibility can empty or fill the toolbar.
            action = event.action()
            visible = action.isVisible()
            if self._action_visible.get(id(action)) is not visible:
                self._action_visible[id(action)] = visible
                self._schedule_refresh(watched)
        elif kind in (QEvent.Type.ActionAdded, QEvent.Type.ActionRemoved):
            # A widget added later (a plugin's) exists once the toolbar has
            # handled the event.
            self._schedule_refresh(watched)
        elif kind == QEvent.Type.ChildRemoved:
            self._widgets.pop(watched, None)
        elif kind == QEvent.Type.Move:
            # Only a toolbar's divider depends on where it is (none at the
            # start of a row); which toolbar ends a row is settled once all
            # have moved.
            frame, extent = self._metrics(watched)
            self._place_divider(watched, watched.property(PROPERTY), frame, extent)
            self._schedule_rows(watched.parentWidget())
        elif kind in (QEvent.Type.Resize, QEvent.Type.Show, QEvent.Type.ParentChange, QEvent.Type.Hide):
            # Hide: a whole row may go. Resize: the last toolbar of a row
            # may change.
            self._moved(watched)
        return False

    def _schedule_refresh(self, toolbar):
        """Refresh a toolbar once on the next event-loop pass, however many
        of its actions changed meanwhile."""
        if toolbar not in self._refresh_pending:
            self._refresh_pending.add(toolbar)
            QTimer.singleShot(0, lambda toolbar=toolbar: self._refresh(toolbar))

    def _refresh(self, toolbar):
        self._refresh_pending.discard(toolbar)
        self._widgets.pop(toolbar, None)
        if toolbar in self._labels and not sip.isdeleted(toolbar):
            filled = has_items(toolbar)
            if filled != self._filled.get(toolbar):
                self._filled[toolbar] = filled
                # An emptied or filled toolbar changes its row.
                self._schedule_rows(toolbar.parentWidget())
            if toolbar.property(PROPERTY) == "title":
                self._shift(toolbar)
            self._update(toolbar)
