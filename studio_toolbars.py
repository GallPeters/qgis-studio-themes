"""Small labels on toolbar handles, naming each toolbar.

A transparent overlay is laid over the drag handle on the left (or top,
for vertical toolbars) of every toolbar of a main window. It ignores the
mouse, so dragging the toolbar works as before, and it is not a toolbar
action, so QGIS, plugins and Interface Customization never see it. The
handle is widened through the stylesheet only while a label is attached
(QToolBar[studioLabel="true"]).

Horizontal toolbars get the name rotated to read bottom to top, like a
chart's y-axis title: the baseline faces the toolbar's icons. Text drawn
rotated loses Windows' font hinting and looks blurry at this size, so it is
drawn upright into an image that is then turned by exactly 90 degrees
(lossless). Vertical toolbars get the name across the top.

Sharpness at small sizes: bold capitals of 8 px turn into blobs on a
normal-density monitor, so labels are SemiBold, fully hinted, and the
baseline sits on a whole device pixel with the capitals (not the font's
full line height) centred on the handle. Labels share one size, the
largest at which every short (up to four letter) QGIS toolbar name fits the
handle (10 px on 24 px toolbars, larger on larger ones), so no name looks
louder than the rest; only a longer name steps down as far as it must.
"""
from qgis.PyQt import sip
import functools
import math

from qgis.PyQt.QtCore import QEvent, QObject, QPointF, QRect, Qt
from qgis.PyQt.QtGui import QColor, QFont, QFontMetrics, QFontMetricsF, QImage, QPainter, QTransform
from qgis.PyQt.QtWidgets import QApplication, QMainWindow, QStyle, QToolBar, QWidget

PROPERTY = "studioLabel"
# Largest first (see _fit); 8 px only where nothing else fits the handle.
# Compact sizes (see set_compact) start one size smaller.
FONT_SIZES = (11, 10, 9, 8)
COMPACT_FONT_SIZES = (10, 9, 8)
_font_sizes = FONT_SIZES
LETTER_SPACING = 1.0
# Whole pixels only: fractional spacing puts letters between pixels.
SPACINGS = (LETTER_SPACING, 0)

# QGIS's own toolbars (main window and layout designer): short, plain words
# (shrunk to fit if needed). Others, such as plugin toolbars, get the first
# four letters of their title.
ABBREVIATIONS = {
    "mFileToolBar": "PROJ",
    "mLayerToolBar": "LAYER",
    "mDataSourceManagerToolBar": "DATA",
    "mDigitizeToolBar": "EDIT",
    "mAdvancedDigitizeToolBar": "ADV",
    "mShapeDigitizeToolBar": "SHAPE",
    "mMeshToolBar": "MESH",
    "mSnappingToolBar": "SNAP",
    "mMapNavToolBar": "NAV",
    "mAttributesToolBar": "ATTR",
    "mSelectionToolBar": "SEL",
    "mLabelToolBar": "LABEL",
    "mAnnotationsToolBar": "NOTE",
    "mPluginToolBar": "PLUG",
    "mHelpToolBar": "HELP",
    "mRasterToolBar": "RAST",
    "mVectorToolBar": "VECT",
    "mDatabaseToolBar": "DB",
    "mWebToolBar": "WEB",
    "mGpsToolBar": "GPS",
    "mLayoutToolbar": "PAGE",
    "mToolsToolbar": "TOOL",
    "mNavigationToolbar": "NAV",
    "mActionsToolbar": "ALIGN",
    "mAtlasToolbar": "ATLAS",
    "mReportToolbar": "REPT",
}


def abbreviation(toolbar):
    known = ABBREVIATIONS.get(toolbar.objectName())
    if known:
        return known
    words = [w for w in toolbar.windowTitle().replace("&", "").split() if w.lower() != "toolbar"]
    return words[0][:4].upper() if words else ""


class _Label(QWidget):
    """The overlay painted over one toolbar's handle."""

    def __init__(self, toolbar, color):
        super().__init__(toolbar)
        self.setObjectName("studioToolbarLabel")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.color = color
        self.text = ""
        self.setFont(label_font(_font_sizes[0]))
        # The rotated text image, rendered once per text/size/colour/scale.
        self._image = None
        self._image_key = None
        # What _place last applied, so unchanged layout requests are free.
        self.placed = None

    def paintEvent(self, _event):  # pylint: disable=invalid-name
        if not self.text:
            return
        painter = QPainter(self)
        rect = self.rect()
        ratio = self.devicePixelRatioF()
        if rect.height() < rect.width():
            # Vertical toolbar: the name runs across the top.
            painter.setPen(self.color)
            painter.drawText(self._origin(rect.width(), rect.height(), ratio), self.text)
            painter.end()
            return
        key = (self.text, self.font().pixelSize(), self.color.rgba(), rect.size(), ratio)
        if key != self._image_key:
            self._image = self._render(rect, ratio)
            self._image_key = key
        painter.drawImage(rect.topLeft(), self._image)
        painter.end()

    def _origin(self, width, height, ratio):
        """Where to draw the text so it is centred in width x height:
        capitals centred vertically (centring the full line height would
        push them up by the descender) and the baseline and the start on
        whole device pixels, where hinting keeps stems sharp."""
        metrics = QFontMetricsF(self.font())
        x = (width - metrics.horizontalAdvance(self.text)) / 2
        baseline = (height + metrics.capHeight()) / 2
        return QPointF(round(x * ratio) / ratio, round(baseline * ratio) / ratio)

    def _render(self, rect, ratio):
        """Draw the text upright (hinted, sharp), then turn the image
        anticlockwise by exactly 90 degrees so it reads bottom to top."""
        image = QImage(
            math.ceil(rect.height() * ratio), math.ceil(rect.width() * ratio),
            QImage.Format.Format_ARGB32_Premultiplied,
        )
        image.setDevicePixelRatio(ratio)
        image.fill(Qt.GlobalColor.transparent)
        upright = QPainter(image)
        upright.setFont(self.font())
        upright.setPen(self.color)
        upright.drawText(self._origin(rect.height(), rect.width(), ratio), self.text)
        upright.end()
        image = image.transformed(QTransform().rotate(-90))
        image.setDevicePixelRatio(ratio)
        return image


def set_compact(compact):
    """Use the smaller label sizes of compact mode."""
    global _font_sizes  # pylint: disable=global-statement
    _font_sizes = COMPACT_FONT_SIZES if compact else FONT_SIZES


def label_font(size, spacing=LETTER_SPACING):
    font = QFont(QApplication.font())
    font.setPixelSize(size)
    font.setWeight(QFont.Weight.DemiBold)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, spacing)
    # Snap outlines to the pixel grid: crisp stems at 9-11 px.
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    return font


def fit(text, length):
    """The label font for `text` on a handle `length` pixels long (the
    size all labels share, see _uniform), and the text (shortened only if
    it does not fit even at the smallest size)."""
    size, spacing, text = _fit(text, length, QApplication.font().family(), _font_sizes)
    return label_font(size, spacing), text


def _candidates(sizes):
    """(size, spacing) pairs, largest first; tighter letter spacing before
    a smaller size."""
    return [(size, spacing) for size in sizes for spacing in SPACINGS]


@functools.lru_cache(maxsize=64)
def _uniform(length, _family, sizes):
    """Index of the first candidate at which every short QGIS toolbar
    name fits `length` pixels: the size labels share (the smallest if none
    fits; longer names are then cut). The few five letter names would
    shrink every label for their sake, so they only shrink themselves."""
    names = {name for name in ABBREVIATIONS.values() if len(name) <= 4}
    candidates = _candidates(sizes)
    for index, (size, spacing) in enumerate(candidates):
        metrics = QFontMetrics(label_font(size, spacing))
        if all(metrics.horizontalAdvance(name) <= length for name in names):
            return index
    return len(candidates) - 1


@functools.lru_cache(maxsize=256)
def _fit(text, length, family, sizes):
    # From the shared size down, so other names (plugin toolbars) match it
    # and only a name that does not fit gets smaller, then cut.
    candidates = _candidates(sizes)
    for size, spacing in candidates[_uniform(length, family, sizes):]:
        if QFontMetrics(label_font(size, spacing)).horizontalAdvance(text) <= length:
            return size, spacing, text
    metrics = QFontMetrics(label_font(sizes[-1], 0))
    while text and metrics.horizontalAdvance(text) > length:
        text = text[:-1]
    return sizes[-1], 0, text


class ToolbarLabels(QObject):
    """Attaches labels to the toolbars of main windows, including toolbars
    added later (plugins), and keeps them placed on the handle."""

    def __init__(self):
        super().__init__()
        self._color = QColor()
        self._windows = []
        self._labels = {}
        self._tooltips = {}
        # Signal connections per toolbar, undone on detach.
        self._slots = {}

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
            for signal, slot in self._slots.pop(toolbar, ()):
                signal.disconnect(slot)
            toolbar.setProperty(PROPERTY, None)
            if toolbar in self._tooltips:
                toolbar.setToolTip(self._tooltips[toolbar])
            self._repolish(toolbar)
            if not sip.isdeleted(label):
                label.deleteLater()
        self._labels = {}
        self._tooltips = {}
        self._slots = {}

    def _add(self, toolbar):
        if toolbar in self._labels:
            return
        label = _Label(toolbar, self._color)
        self._labels[toolbar] = label
        toolbar.setProperty(PROPERTY, True)
        self._repolish(toolbar)
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
        title = toolbar.windowTitle()
        placed = (rect, title, toolbar.objectName(), QApplication.font().family())
        # Toolbars send layout requests often; only redo the work when the
        # handle or the name actually changed.
        if placed == label.placed and label.isVisible():
            return
        label.placed = placed
        font, text = fit(abbreviation(toolbar), length - 4)
        label.setFont(font)
        label.text = text
        label.setGeometry(rect)
        # The label ignores the mouse; the toolbar shows the full name when
        # hovering its handle (unless it already has a tooltip of its own).
        if toolbar not in self._tooltips:
            self._tooltips[toolbar] = toolbar.toolTip()
        if not self._tooltips[toolbar]:
            toolbar.setToolTip(title)
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
