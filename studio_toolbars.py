"""Toolbar names: each docked toolbar's name beside its buttons.

Where the name of a docked horizontal toolbar goes is a setting (Plugins >
QGIS Studio Themes > Settings, see POSITIONS):

  top            a title strip above the buttons, the name centred on them;
  bottom         the name in the line under the row, breaking it, in a
                 strip less than half as tall;
  left           the name left of the buttons, across;
  left_vertical  the name left of the buttons, reading upwards: the
                 narrowest, for short names.

The top strip is made by a top margin on every item of the toolbar
(QToolBar[studioLabel="top"] in style.qss, @toolbar_title_height =
TITLE_SPACE), so the items keep their own layout and the toolbar simply
grows by the strip; widgets the stylesheet cannot push down (containers
such as the snapping widget) get the same space as a top contents margin,
undone on detach. The bottom strip is made the same way, below the items
(LINE_SPACE). Names left of the buttons get their room in a wider handle
(QToolBar[studioLead="<px>"], rules made by side_rules): QToolBar counts
the handle in its size and lays its items out after it, so the toolbar
grows by the name, nothing overflows that would fit, and the name drags
the toolbar like the handle. QToolBar also makes a toolbar at least as tall
as its handle is wide, so such a toolbar's height is capped at its items'
own. A toolbar that cannot be moved has no handle and shows its name above
its buttons instead.

Which name shows is a setting too (NAME_STYLES): the full one, a short one
of up to four letters (SHORT_NAMES, else made from the title), or "auto":
the full name where it is no wider than the buttons, the short one
otherwise. A
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

The title is horizontal text, drawn onto the toolbar's own background
colour, so Windows smooths it with ClearType like all other UI text. The
capitals are centred in the strip with the baseline on a whole device
pixel, and the dividers are one device pixel thick, so both stay sharp at
every scaling. Names and lines are drawn into pictures once, when they
change, and Qt paints them from then on: buttons reach into the title
strip, so every hover repaints it, without running any Python.

A vertical toolbar (docked left or right) has no room for a strip; it gets
a short three-letter name across the top of a taller handle
(QToolBar[studioLabel="handle"]), whatever the setting. Floating toolbars
show their name in their own title bar and get nothing.
"""
from qgis.PyQt import sip
import functools
import re

from qgis.PyQt.QtCore import QEvent, QMargins, QObject, QPointF, QRect, Qt, QTimer
from qgis.PyQt.QtGui import QColor, QFont, QFontDatabase, QFontMetrics, QFontMetricsF, QPainter, QPen, QPixmap
from qgis.PyQt.QtWidgets import (
    QAbstractSpinBox, QApplication, QComboBox, QLabel, QLineEdit, QMainWindow, QStyle, QStyleOptionToolBar,
    QToolBar, QToolButton, QWidget,
)

PROPERTY = "studioLabel"
# The room for a name left of the buttons, added to the handle's width.
LEAD_PROPERTY = "studioLead"
# Where a docked horizontal toolbar's name goes ("off": no names at all,
# handled by the plugin), and which name it shows (see the docstring).
POSITIONS = ("off", "top", "bottom", "left", "left_vertical")
NAME_STYLES = ("auto", "full", "short")
# Modes of a toolbar named in a row (the positions, as the property's
# value), and those with the name left of the buttons.
ROW_MODES = ("top", "bottom", "left", "left_vertical")
SIDE_MODES = ("left", "left_vertical")
# Height of the title strip (logical px), and the gap between it and the
# buttons, so a hovered or checked button's fill keeps clear of the name.
# Their sum is the room the buttons are pushed down by (TITLE_SPACE,
# shared with style.qss).
TITLE_HEIGHT = 13
TITLE_GAP = 3
TITLE_SPACE = TITLE_HEIGHT + TITLE_GAP
# Small capitals: a quiet caption that never competes with the icons.
# Bold, so the name reads at 10 px and stands apart from the UI text
# (Segoe UI's Bold; Inter, the fallback, its SemiBold, the heaviest face
# bundled), spaced by a whole pixel so the letters stay apart (fractional
# spacing puts letters between pixels).
TITLE_SIZE = 10
TITLE_SPACING = 1.0
# Room either side of a name when a toolbar is widened to fit it.
RULE_ROOM = 6
# "bottom": the strip below the buttons (logical px), shared with
# style.qss (@toolbar_line_title_height). The name's strip reaches into
# the toolbar's padding under it, and the row's line runs through its
# middle; the name breaks the line with LINE_GAP either side.
LINE_SPACE = 7
LINE_GAP = 4
# Names left of the buttons: the room taken beside a name across (its width
# plus this), and the column for a name reading upwards. The room is
# rounded up to LEAD_STEP, the steps the stylesheet has rules for, up to
# LEAD_MAX (longer names show the short one).
SIDE_ROOM = 8
UPRIGHT_ROOM = 12
LEAD_STEP = 4
LEAD_MAX = 240
# The handle's own width (QToolBar::handle in style.qss).
HANDLE_WIDTH = 6
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

# Short names (up to four letters), by object name: QGIS's own toolbars,
# in the main window and the layout designer. Others, such as plugin
# toolbars, get one made from their title (short_candidates).
SHORT_NAMES = {
    "mFileToolBar": "PROJ",
    "mLayerToolBar": "LAYR",
    "mDataSourceManagerToolBar": "DATA",
    "mDigitizeToolBar": "EDIT",
    "mAdvancedDigitizeToolBar": "ADV",
    "mShapeDigitizeToolBar": "SHAP",
    "mMeshToolBar": "MESH",
    "mSnappingToolBar": "SNAP",
    "mMapNavToolBar": "NAV",
    "mAttributesToolBar": "ATTR",
    "mSelectionToolBar": "SEL",
    "mLabelToolBar": "LABL",
    "mAnnotationsToolBar": "ANNO",
    "mPluginToolBar": "PLUG",
    "mHelpToolBar": "HELP",
    "mRasterToolBar": "RAST",
    "mVectorToolBar": "VECT",
    "mDatabaseToolBar": "DB",
    "mWebToolBar": "WEB",
    "mGpsToolBar": "GPS",
    "mLayoutToolbar": "LAYT",
    "mToolsToolbar": "TOOL",
    "mNavigationToolbar": "NAV",
    "mActionsToolbar": "ACTN",
    "mAtlasToolbar": "ATLS",
    "mReportToolbar": "RPRT",
}
SHORT_LENGTH = 4
# Words left out when a short name is made from a title.
GENERIC_WORDS = {"toolbar", "tools", "tool", "plugin"}

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


def side_rules():
    """Stylesheet rules widening a toolbar's handle by the room for its
    name (LEAD_PROPERTY), one per LEAD_STEP."""
    return "\n".join(
        f'QToolBar[{LEAD_PROPERTY}="{lead}"]::handle {{ width: {HANDLE_WIDTH + lead}px; }}'
        for lead in range(LEAD_STEP, LEAD_MAX + 1, LEAD_STEP)
    )


def short_candidates(text):
    """Short names for a toolbar titled `text`, best first: its first
    word's first letters, mixed with the next word's, or the initials of a
    longer title. Generic words (Toolbar, Tools...) are left out."""
    words = [w for w in re.split(r"[\s_/-]+", text.replace("&", "")) if w and w.lower() != "toolbar"]
    words = [w.upper() for w in ([w for w in words if w.lower() not in GENERIC_WORDS] or words)]
    if not words:
        return []
    first = words[0]
    initials = "".join(w[0] for w in words[:SHORT_LENGTH])
    candidates = [initials] if len(words) >= 3 else []
    candidates.append(first[:SHORT_LENGTH])
    if len(words) >= 2:
        second = words[1]
        candidates += [first[:3] + second[:1], first[:2] + second[:2], first[:1] + second[:3]]
    candidates.append(initials)
    candidates += [f"{first[:3]}{n}" for n in range(2, 10)]
    return list(dict.fromkeys(c for c in candidates if c))


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
    weight = QFont.Weight.Bold if _face() else QFont.Weight.DemiBold
    return _font(TITLE_SIZE, weight, TITLE_SPACING)


@functools.lru_cache(maxsize=256)
def _title_width(text, _app_font):
    return QFontMetrics(_title_font(_app_font)).horizontalAdvance(text)


def title_width(text):
    """Width of a toolbar name in the title font (cached)."""
    return _title_width(text, QApplication.font().key())


def _snap(value, ratio):
    return round(value * ratio) / ratio


class _Overlay(QLabel):
    """A picture over a toolbar, drawn by _paint into a pixmap of the
    widget's size whenever it changes (see refresh); Qt paints it from
    then on, so repainting the toolbar runs no Python. A QLabel, which
    paints its pixmap in C++ (the stylesheet leaves these alone by name,
    see style.qss)."""

    def __init__(self, toolbar, name):
        super().__init__(toolbar)
        self.setObjectName(name)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._drawn = None

    def refresh(self):
        """Draw the picture again if its size, screen scaling or content
        (_content) changed since it was last drawn."""
        ratio = self.devicePixelRatioF()
        key = (self.width(), self.height(), ratio, self._content())
        if key == self._drawn or self.width() <= 0 or self.height() <= 0:
            return
        self._drawn = key
        pixmap = QPixmap(max(1, round(self.width() * ratio)), max(1, round(self.height() * ratio)))
        pixmap.setDevicePixelRatio(ratio)
        pixmap.fill(self._background())
        painter = QPainter(pixmap)
        self._paint(painter, ratio)
        painter.end()
        self.setPixmap(pixmap)

    def _background(self):
        return QColor(Qt.GlobalColor.transparent)

    def _content(self):
        raise NotImplementedError

    def _paint(self, painter, ratio):
        raise NotImplementedError


class _Label(_Overlay):
    """One toolbar's name: in a strip above or below the buttons, left of
    them (across, or reading upwards when `upright`), or a short name
    across the top of a vertical toolbar. Drawn on the toolbar's background
    colour (when known): text on an opaque picture keeps ClearType's
    subpixel smoothing, like text drawn on the window, and a name in the
    row's line breaks the line."""

    def __init__(self, toolbar, color, background=None):
        super().__init__(toolbar, "studioToolbarLabel")
        self.color = color
        self.background = background
        self.text = ""
        self.upright = False
        self.title_font = QFont()
        # What _place last applied, so unchanged layout requests are free.
        self.placed = None

    def _background(self):
        if self.background is None or not self.background.isValid():
            return super()._background()
        return self.background

    def _content(self):
        background = self.background.rgba() if self.background is not None else None
        return self.text, self.upright, self.color.rgba(), background, self.title_font.key()

    def _paint(self, painter, ratio):
        if not self.text:
            return
        metrics = QFontMetricsF(self.title_font)
        width = metrics.horizontalAdvance(self.text)
        across, high = self.width(), self.height()
        if self.upright:
            # Reading upwards: drawn across a turned painter, whose width is
            # the widget's height.
            painter.translate(0, high)
            painter.rotate(-90)
            across, high = high, across
        # Capitals centred (centring the full line height would push them
        # up by the descender); baseline and start on whole device pixels,
        # where hinting keeps stems sharp.
        x = _snap((across - width) / 2, ratio)
        baseline = _snap((high + metrics.capHeight()) / 2, ratio)
        painter.setFont(self.title_font)
        painter.setPen(self.color)
        painter.drawText(QPointF(x, baseline), self.text)


class _Divider(_Overlay):
    """A line one device pixel thick, in `rule`: down the middle of the
    widget (the divider between a titled toolbar and the one to its left,
    in this toolbar's handle gap), or along its bottom when `row` (the line
    under a row of toolbars)."""

    def __init__(self, toolbar, rule, row=False):
        super().__init__(toolbar, "studioToolbarRowLine" if row else "studioToolbarDivider")
        self.rule = rule
        self.row = row

    def _content(self):
        return self.rule.rgba(), self.row

    def _paint(self, painter, ratio):
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

    # Events each part watches for (see _window_event, _toolbar_event).
    WINDOW_EVENTS = (QEvent.Type.ChildPolished,) + tuple(
        # Moved to a screen with another scaling: pictures drawn again.
        getattr(QEvent.Type, name) for name in ("DevicePixelRatioChange", "ScreenChangeInternal")
        if hasattr(QEvent.Type, name)
    )
    TOOLBAR_EVENTS = (
        QEvent.Type.LayoutRequest, QEvent.Type.ActionChanged, QEvent.Type.ActionAdded,
        QEvent.Type.ActionRemoved, QEvent.Type.ChildRemoved, QEvent.Type.Move, QEvent.Type.Resize,
        QEvent.Type.Show, QEvent.Type.ParentChange, QEvent.Type.Hide,
    )

    def __init__(self, hub=None):
        super().__init__()
        # The event filter shared with the icon swapper (studio_events).
        if hub is None:
            from .studio_events import EventHub  # pylint: disable=import-outside-toplevel
            hub = EventHub()
        self._hub = hub
        self._color = QColor()
        self._rule = QColor()
        self._row_rule = QColor()
        self._background = None
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
        # The setting: where names go and which name shows (see POSITIONS).
        self._position = "top"
        self._names = "auto"
        # Short names given to toolbars without one of their own, so two
        # in a window never share one.
        self._shorts = {}
        # The room in each toolbar's handle for a name left of its buttons,
        # and the maximum heights capped for it, with the toolbar's own.
        self._leads = {}
        self._max_heights = {}
        # Toolbars being placed: a change made while placing one may send
        # it events at once (a resize), handled by the placing itself.
        self._updating = set()

    def attach(self, window, color, rule, row_rule=None, background=None):
        """Name every toolbar of `window` (a QMainWindow): text in
        `color` on the toolbars' `background`, dividers between toolbars in
        `rule`, lines under rows of toolbars in `row_rule` (by default
        `rule`)."""
        self._color = QColor(color)
        self._rule = QColor(rule)
        self._row_rule = QColor(rule if row_rule is None else row_rule)
        self._background = None if background is None else QColor(background)
        if window not in self._windows:
            self._windows.append(window)
            self._hub.watch(window, self, self.WINDOW_EVENTS, self._window_event)
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

    def set_color(self, color, rule, row_rule=None, background=None):
        self._color = QColor(color)
        self._rule = QColor(rule)
        self._row_rule = QColor(rule if row_rule is None else row_rule)
        self._background = None if background is None else QColor(background)
        self._frames = {}  # another theme, other metrics
        for label in self._labels.values():
            if not sip.isdeleted(label):
                label.color = self._color
                label.background = self._background
                label.refresh()
        for lines, color in ((self._dividers, self._rule), (self._ends, self._rule),
                             (self._row_lines, self._row_rule)):
            for line in lines.values():
                if not sip.isdeleted(line):
                    line.rule = color
                    line.refresh()

    def set_style(self, position, names):
        """Where names go and which name shows (POSITIONS other than "off",
        NAME_STYLES): every named toolbar is placed again at once."""
        position = position if position in ROW_MODES else "top"
        names = names if names in NAME_STYLES else "auto"
        if (position, names) == (self._position, self._names):
            return
        self._position, self._names = position, names
        for toolbar, label in list(self._labels.items()):
            if sip.isdeleted(toolbar) or sip.isdeleted(label):
                continue
            label.placed = None
            self._moved(toolbar)

    def _rescaled(self):
        """A window moved to a screen with another scaling: every picture
        is drawn again at the new scaling (each skips it if unchanged)."""
        for table in (self._labels, self._dividers, self._ends, self._row_lines):
            for overlay in table.values():
                if not sip.isdeleted(overlay):
                    overlay.refresh()

    def detach(self):
        for window in self._windows:
            self._hub.unwatch(window, self)
        for window, slot in self._window_slots.values():
            try:
                window.destroyed.disconnect(slot)
            except (TypeError, RuntimeError):
                pass  # already gone
        self._windows = []
        self._window_slots = {}
        for toolbar, label in list(self._labels.items()):
            self._hub.unwatch(toolbar, self)
            if sip.isdeleted(toolbar):
                continue
            for signal, slot in self._slots.pop(toolbar, ()):
                signal.disconnect(slot)
            self._set_mode(toolbar, None)
            self._fit_name(toolbar, None, "")
            if toolbar in self._tooltips:
                toolbar.setToolTip(self._tooltips[toolbar])
            for widget in (label, self._dividers.get(toolbar), self._row_lines.get(toolbar),
                           self._ends.get(toolbar)):
                if widget is not None and not sip.isdeleted(widget):
                    # Gone at once, even before Qt deletes it (deleteLater
                    # waits for the event loop the call was made from).
                    widget.hide()
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
        self._shorts = {}
        self._leads = {}
        self._max_heights = {}
        self._updating = set()

    def _add(self, toolbar):
        if toolbar in self._labels:
            return
        self._filled[toolbar] = has_items(toolbar)
        label = _Label(toolbar, self._color, self._background)
        self._labels[toolbar] = label
        self._dividers[toolbar] = _Divider(toolbar, self._rule)
        self._row_lines[toolbar] = _Divider(toolbar, self._row_rule, row=True)
        self._ends[toolbar] = _Divider(toolbar, self._rule)
        self._extensions[toolbar] = toolbar.findChild(QToolButton, "qt_toolbar_ext_button")
        self._hub.watch(toolbar, self, self.TOOLBAR_EVENTS, self._toolbar_event)
        moved = lambda *_args, toolbar=toolbar: self._moved(toolbar)  # noqa: E731
        renamed = lambda *_args, toolbar=toolbar: self._renamed(toolbar)  # noqa: E731
        forget = lambda _obj=None, toolbar=toolbar: self._forget(toolbar)  # noqa: E731
        slots = [(signal, moved) for signal in (
            toolbar.topLevelChanged, toolbar.movableChanged, toolbar.orientationChanged,
        )] + [(toolbar.windowTitleChanged, renamed), (toolbar.destroyed, forget)]
        for signal, slot in slots:
            signal.connect(slot)
        self._slots[toolbar] = slots
        self._moved(toolbar)

    def _renamed(self, toolbar):
        """A new title: a short name made from it is made again."""
        self._shorts.pop(toolbar, None)
        self._moved(toolbar)

    def _forget(self, toolbar):
        for table in (self._labels, self._dividers, self._row_lines, self._ends, self._last,
                      self._extensions, self._widgets, self._frames, self._offsets, self._min_widths,
                      self._tooltips, self._slots, self._shifted, self._filled, self._shorts,
                      self._leads, self._max_heights):
            table.pop(toolbar, None)
        self._refresh_pending.discard(toolbar)
        self._collapsed.discard(toolbar)

    def _overlays(self, toolbar):
        return (self._labels.get(toolbar), self._dividers.get(toolbar), self._row_lines.get(toolbar),
                self._ends.get(toolbar))

    # ---- Modes ------------------------------------------------------------

    def _mode(self, toolbar):
        """The position set (ROW_MODES) for a docked horizontal toolbar,
        "handle" (docked vertical, movable) or None (floating, empty, or a
        fixed vertical toolbar: no handle). An empty toolbar gets no name,
        strip or dividers: it shrinks to a sliver instead of showing a
        labelled empty box."""
        if toolbar.isFloating() or not self._filled.get(toolbar, True):
            return None
        if toolbar.orientation() == Qt.Orientation.Horizontal:
            # No handle to hold a name left of the buttons: above them.
            if self._position in SIDE_MODES and not toolbar.isMovable():
                return "top"
            return self._position
        return "handle" if toolbar.isMovable() else None

    def _set_mode(self, toolbar, mode):
        """Apply a mode's stylesheet rules (title strip or taller handle)
        and contents margins, and relayout the toolbar."""
        if toolbar.property(PROPERTY) == mode:
            return
        toolbar.setProperty(PROPERTY, mode)
        self._frames.pop(toolbar, None)
        self._unshift(toolbar)
        if mode not in SIDE_MODES:
            self._fit_side(toolbar, 0)
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
        self._shift(toolbar)

    @staticmethod
    def _strip(mode):
        """The room a strip mode adds above or below the items."""
        if mode == "top":
            return QMargins(0, TITLE_SPACE, 0, 0)
        if mode == "bottom":
            return QMargins(0, 0, 0, LINE_SPACE)
        return None

    def _shift(self, toolbar):
        """Give items the stylesheet cannot push away from the strip
        (containers) the strip as a contents margin."""
        strip = self._strip(toolbar.property(PROPERTY))
        if strip is None:
            return
        shifted = self._shifted.setdefault(toolbar, {})
        for widget in self._layout_widgets(toolbar):
            if (widget in shifted or isinstance(widget, STYLED_ITEMS)
                    or widget.metaObject().className() == "QToolBarSeparator"):
                continue
            margins = widget.contentsMargins()
            shifted[widget] = margins
            widget.setContentsMargins(margins + strip)

    def _unshift(self, toolbar):
        for widget, margins in self._shifted.pop(toolbar, {}).items():
            if not sip.isdeleted(widget):
                widget.setContentsMargins(margins)

    def _fit_name(self, toolbar, mode, text):
        """A toolbar with a strip at least as wide as its name, so no name
        is cut short when toolbars with few buttons sit side by side; the
        toolbar's own minimum width otherwise."""
        own = self._min_widths.get(toolbar)
        need = None
        if mode in ("top", "bottom") and text:
            frame, extent = self._metrics(toolbar)
            handle = extent if toolbar.isMovable() else 0
            need = title_width(text) + 2 * RULE_ROOM + 2 * frame + handle
        if need is not None and need > (toolbar.minimumWidth() if own is None else own):
            if own is None:
                self._min_widths[toolbar] = toolbar.minimumWidth()
            if toolbar.minimumWidth() != need:
                toolbar.setMinimumWidth(need)
        elif own is not None:
            del self._min_widths[toolbar]
            toolbar.setMinimumWidth(own)

    def _fit_side(self, toolbar, lead):
        """Room for a name left of the buttons (`lead` px, see _lead) in the
        toolbar's handle; none for 0. Only the toolbar is restyled: its
        handle width changes, and with it its size and layout."""
        if self._leads.get(toolbar, 0) == lead:
            return
        if lead:
            self._leads[toolbar] = lead
        else:
            self._leads.pop(toolbar, None)
            self._cap_height(toolbar, 0)
        toolbar.setProperty(LEAD_PROPERTY, str(lead) if lead else None)
        self._frames.pop(toolbar, None)
        style = toolbar.style()
        style.unpolish(toolbar)
        style.polish(toolbar)
        QApplication.sendEvent(toolbar, QEvent(QEvent.Type.StyleChange))

    def _cap_height(self, toolbar, lead):
        """Keep a toolbar whose handle holds a name (`lead`) as tall as its
        items, not its handle's width (QToolBar's minimum, which the main
        window keeps within the maximum); its own maximum otherwise."""
        own = self._max_heights.get(toolbar)
        if lead:
            layout = toolbar.layout()
            widgets = self._layout_widgets(toolbar)
            shown = [w for w in widgets if w.isVisible()] or widgets
            if layout is None or not shown:
                return
            margins = layout.contentsMargins() + toolbar.contentsMargins()
            height = max(w.sizeHint().height() for w in shown) + margins.top() + margins.bottom()
            if own is None:
                own = self._max_heights[toolbar] = toolbar.maximumHeight()
            height = min(height, own)
            if toolbar.maximumHeight() != height:
                toolbar.setMaximumHeight(height)
        elif own is not None:
            del self._max_heights[toolbar]
            toolbar.setMaximumHeight(own)

    def _fit_extension(self, toolbar, frame):
        """The overflow button of a squeezed toolbar whose handle holds a
        name: QToolBar makes it as tall as the handle is wide, its arrow
        below the toolbar's capped height; as tall as the toolbar here."""
        extension = self._extensions.get(toolbar)
        if extension is None or sip.isdeleted(extension) or not extension.isVisible():
            return
        height = toolbar.height() - 2 * frame
        if height > 0 and extension.height() != height:
            extension.setGeometry(extension.x(), frame, extension.width(), height)

    @staticmethod
    def _lead(mode, text):
        """The room a name left of the buttons takes, in the stylesheet's
        steps."""
        if mode == "left" and text:
            need = title_width(text) + SIDE_ROOM
        elif mode == "left_vertical" and text:
            need = UPRIGHT_ROOM
        else:
            return 0
        return min(LEAD_MAX, -(-need // LEAD_STEP) * LEAD_STEP)

    def _short(self, toolbar):
        """The toolbar's short name: its own (SHORT_NAMES), or one made from
        its title that no other toolbar of its window shows."""
        name = self._shorts.get(toolbar)
        if name is not None:
            return name
        name = SHORT_NAMES.get(toolbar.objectName())
        if name is None:
            window = toolbar.parentWidget()
            taken = set()
            for other in self._labels:
                if other is not toolbar and not sip.isdeleted(other) and other.parentWidget() is window:
                    taken.add(self._shorts.get(other) or SHORT_NAMES.get(other.objectName()))
            candidates = short_candidates(toolbar.windowTitle())
            name = next((c for c in candidates if c not in taken), candidates[0] if candidates else "")
        self._shorts[toolbar] = name
        return name

    def _text(self, toolbar, mode):
        """The name a toolbar shows in `mode`. "auto" picks the full name
        where it is no wider than the room it is measured against: the
        buttons, all of them as the layout wants them (not those shown
        while the toolbar is squeezed, or the choice would change the
        squeeze and so itself), or the toolbar's height for a name reading
        upwards (which never shows the full name otherwise)."""
        if mode == "handle":
            return abbreviation(toolbar)
        if mode not in ROW_MODES:
            return ""
        full, short = title(toolbar), self._short(toolbar)
        names = self._names
        if mode == "left_vertical" and names == "full":
            names = "auto"
        if names == "full" or not short:
            return full
        if names == "short":
            return short
        frame, extent = self._metrics(toolbar)
        if mode == "left_vertical":
            # The label's height (see _place), less a pixel either end.
            room = toolbar.height() - 4
        else:
            layout = toolbar.layout()
            if layout is None:
                return full
            handle = extent if toolbar.isMovable() else 0
            room = layout.sizeHint().width() - 2 * frame - handle
        return full if title_width(full) <= room else short

    # ---- Placing ----------------------------------------------------------

    def _metrics(self, toolbar):
        """(frame width, handle extent) of a toolbar, as its style has them."""
        metrics = self._frames.get(toolbar)
        if metrics is None:
            style = toolbar.style()
            # The orientation decides which of the handle's sizes (width or
            # height in the stylesheet) is its extent.
            option = QStyleOptionToolBar()
            option.initFrom(toolbar)
            if toolbar.orientation() == Qt.Orientation.Horizontal:
                option.state |= QStyle.StateFlag.State_Horizontal
            metrics = self._frames[toolbar] = (
                style.pixelMetric(QStyle.PixelMetric.PM_ToolBarFrameWidth, option, toolbar),
                style.pixelMetric(QStyle.PixelMetric.PM_ToolBarHandleExtent, option, toolbar),
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
        if toolbar not in self._labels or sip.isdeleted(toolbar) or toolbar in self._updating:
            return
        self._updating.add(toolbar)
        try:
            self._place_toolbar(toolbar)
        finally:
            self._updating.discard(toolbar)

    def _place_toolbar(self, toolbar):
        mode = self._mode(toolbar)
        self._set_mode(toolbar, mode)
        frame, extent = self._metrics(toolbar)
        text = self._text(toolbar, mode)
        self._fit_name(toolbar, mode, text)
        lead = self._lead(mode, text)
        if lead != self._leads.get(toolbar, 0):
            self._fit_side(toolbar, lead)
            frame, extent = self._metrics(toolbar)
        if lead:
            self._cap_height(toolbar, lead)
            self._fit_extension(toolbar, frame)
        # Measured once the room for a side name is made: QToolBar may lay
        # its items out again at once.
        items = self._items_span(toolbar) if mode in ROW_MODES else None
        items = self._fit_items(toolbar, mode, frame, extent, items, lead)
        self._place_divider(toolbar, mode, frame, extent)
        line = self._row_lines.get(toolbar)
        if line is not None and not sip.isdeleted(line) and line.isVisible():
            y = self._line_y(toolbar, frame) if self._position == "bottom" else toolbar.height() - 1
            if self._show(line, QRect(0, y - 1, toolbar.width(), 2)) and mode == "bottom":
                # The name stays on top: it breaks the line.
                label = self._labels.get(toolbar)
                if label is not None and not sip.isdeleted(label) and label.isVisible():
                    label.raise_()
        self._place(toolbar, mode, frame, extent, items, text, lead)

    @staticmethod
    def _line_y(toolbar, frame):
        """The row's line with names in it ("bottom"): through the middle of
        the strip under the buttons and the toolbar's padding below it."""
        strip = LINE_SPACE + frame
        return toolbar.height() - strip + strip // 2

    def _place(self, toolbar, mode, frame, extent, items, text, lead):
        label = self._labels.get(toolbar)
        if label is None or sip.isdeleted(label):
            return
        if mode is None or (mode in SIDE_MODES and items is None):
            label.hide()
            label.placed = None
            return
        handle = extent if toolbar.isMovable() else 0
        right_to_left = toolbar.layoutDirection() == Qt.LayoutDirection.RightToLeft
        if mode in ("top", "bottom"):
            # Above or below the buttons, beside the handle (if any). The
            # last toolbar of a row is stretched to the window's edge: the
            # strip spans its items, not the empty rest.
            if mode == "top":
                rect = QRect(frame + handle, frame, toolbar.width() - 2 * frame - handle, TITLE_HEIGHT)
            else:
                strip = LINE_SPACE + frame
                rect = QRect(frame + handle, toolbar.height() - strip, toolbar.width() - 2 * frame - handle, strip)
            if right_to_left:
                rect.moveLeft(frame)
            if items is not None:
                # A name wider than few buttons (one-button toolbars) may
                # spread into the toolbar's own room, if it has any:
                # centred on the buttons, shifted where an edge is near. In
                # the line, the name only covers the line where it is.
                if mode == "top":
                    width = max(items[1] - items[0] + 1, title_width(text) + 2)
                else:
                    width = title_width(text) + 2 * LINE_GAP
                left = (items[0] + items[1] + 1 - width) // 2
                left = max(rect.left(), min(left, rect.right() + 1 - width))
                rect.setLeft(max(rect.left(), left))
                rect.setRight(min(rect.right(), left + width - 1))
        elif mode in SIDE_MODES:
            # Right before the buttons (after them right to left), in the
            # room the handle makes, inside the toolbar's frame; a name
            # reading upwards gets the full height but the row's line.
            top, height = (1, toolbar.height() - 2) if mode == "left_vertical" else (
                frame, toolbar.height() - 2 * frame)
            if right_to_left:
                rect = QRect(items[1] + 1, top, lead, height)
            else:
                rect = QRect(items[0] - lead, top, lead, height)
        else:
            rect = QRect(frame, frame, toolbar.width() - 2 * frame, extent)
            # Centred on the column of icons, like a title on its buttons.
            centre = self._icon_column_centre(toolbar)
            if centre is not None:
                half = min(centre - rect.left(), rect.right() + 1 - centre)
                if half > 0:
                    rect = QRect(round(centre - half), rect.top(), round(2 * half), rect.height())
        name = toolbar.windowTitle()
        placed = (mode, rect, text, toolbar.objectName(), title_font())
        # Toolbars send layout requests often; only redo the work when the
        # strip or the name actually changed.
        if placed == label.placed and label.isVisible():
            return
        label.placed = placed
        # Vertical toolbars' short names in the same small capitals as the
        # titles of horizontal ones.
        font = title_font()
        metrics = QFontMetrics(font)
        upright = mode == "left_vertical"
        if mode in ("top", "bottom"):
            text = metrics.elidedText(text, Qt.TextElideMode.ElideRight, rect.width() - 2)
        elif mode == "left" and metrics.horizontalAdvance(text) > rect.width() - 2:
            # Squeezed (a crowded row): the short name, or none.
            short = self._short(toolbar)
            text = short if metrics.horizontalAdvance(short) <= rect.width() - 2 else ""
        else:
            room = (rect.height() if upright else rect.width()) - 2
            while text and metrics.horizontalAdvance(text) > room:
                text = text[:-1]
        # The full name on hovering a toolbar showing less of it (unless
        # the toolbar has a tooltip of its own).
        if toolbar not in self._tooltips:
            self._tooltips[toolbar] = toolbar.toolTip()
        if not self._tooltips[toolbar]:
            toolbar.setToolTip(name if text != title(toolbar) else "")
        label.title_font = font
        label.upright = upright
        label.text = text
        label.setGeometry(rect)
        label.refresh()
        label.show()
        label.raise_()

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
        if mode not in ROW_MODES or first:
            divider.hide()
            return
        middle = self._middle(toolbar, frame, extent)
        if right_to_left:
            middle = toolbar.width() - 1 - middle
        # The toolbar's full height, title strip included, meeting the lines
        # under the rows: it divides the names too, and is never mistaken
        # for a separator inside a toolbar.
        self._show(divider, QRect(middle - 1, 0, 3, self._rule_height(toolbar, mode, frame)))

    def _middle(self, toolbar, frame, extent):
        """Where the divider goes: the middle of the handle's own width (a
        name left of the buttons widens it), or the toolbar's edge."""
        if not toolbar.isMovable():
            return 0
        return frame + (extent - self._leads.get(toolbar, 0)) // 2

    def _rule_height(self, toolbar, mode, frame):
        """Dividers run down to the row's line: the toolbar's bottom, or
        the line through the names under the buttons."""
        return self._line_y(toolbar, frame) + 1 if mode == "bottom" else toolbar.height()

    def _fit_items(self, toolbar, mode, frame, extent, items, lead=0):
        """Centre a toolbar's buttons in its width (not the last of a row,
        whose extra width is the rest of the window), and close a row after
        the last toolbar's buttons (and a name left of them, `lead` px)
        with a divider. Returns the buttons' span, as moved."""
        end = self._ends.get(toolbar)
        if end is None or sip.isdeleted(end):
            return items
        if mode not in ROW_MODES or items is None or toolbar.layoutDirection() == Qt.LayoutDirection.RightToLeft:
            end.hide()
            return items
        middle = self._middle(toolbar, frame, extent)
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
            # The handle includes the room for a name left of the buttons,
            # which moves with them.
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
        # The space between the start divider and the first button (or the
        # name left of it), mirrored after the last one.
        x = items[1] + (items[0] - lead - middle)
        if x >= toolbar.width() - 2:
            end.hide()
        else:
            self._show(end, QRect(x - 1, 0, 3, self._rule_height(toolbar, mode, frame)))
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
            if (toolbar.isVisible() and (toolbar.property(PROPERTY) in ROW_MODES or self._empty_docked(toolbar))
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
            titled = [toolbar for toolbar in row if toolbar.property(PROPERTY) in ROW_MODES]
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
        """Place and show a line; True if it moved or was hidden."""
        if line.geometry() != rect or not line.isVisible():
            line.setGeometry(rect)
            line.refresh()
            line.show()
            line.raise_()
            return True
        return False

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

    def _icon_column_centre(self, toolbar):
        """Horizontal centre of a vertical toolbar's icons, or None before
        it is laid out. Buttons with a drop-down arrow are wider, on their
        right, so only the narrowest buttons (icon only) count."""
        widgets = [w for w in self._layout_widgets(toolbar) if w.isVisible() and w.width() > 0]
        if not widgets:
            return None
        narrowest = min(w.width() for w in widgets)
        column = [w for w in widgets if w.width() == narrowest]
        return sum(w.x() + w.width() / 2 for w in column) / len(column)

    def _items_span(self, toolbar):
        """(left, right) of a toolbar's visible items (and its overflow
        button), or None before it is laid out."""
        spans = [(w.x(), w.x() + w.width() - 1) for w in self._item_widgets(toolbar)]
        if not spans:
            return None
        return min(s[0] for s in spans), max(s[1] for s in spans)

    def _window_event(self, watched, event):
        """Events of the named windows (WINDOW_EVENTS, via the hub)."""
        if event.type() == QEvent.Type.ChildPolished:
            child = event.child()
            if isinstance(child, QToolBar) and child.parent() is watched:
                self._add(child)
        else:
            self._rescaled()

    def _toolbar_event(self, watched, event):
        """Events of the named toolbars (TOOLBAR_EVENTS, via the hub)."""
        kind = event.type()
        if kind == QEvent.Type.LayoutRequest:
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
            self._shift(toolbar)
            self._update(toolbar)
