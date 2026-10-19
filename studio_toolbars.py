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

ClearType: Windows draws all other UI text with sub-pixel smoothing, which
places stems at a third of a pixel horizontally; text drawn into a
transparent image (as the turned label must be) only gets greyscale
smoothing and looks soft next to it. When ClearType is on, the label is
therefore drawn upright at three samples per device pixel across the
handle (the axis that turns horizontal), filtered like ClearType and
blended per colour channel onto the toolbar's background, so it matches
the rest of the UI. The finished image is blitted 1:1 onto whole device
pixels: at 125 % a widget can start between two, and Qt would resample.
"""
from qgis.PyQt import sip
import ctypes
import functools
import math
import sys

from qgis.PyQt.QtCore import QEvent, QObject, QPoint, QPointF, QRect, Qt
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
# FreeType's default LCD filter (weights out of 256): spreads each sample
# over its neighbours so stems get no colour fringes.
LCD_FILTER = (8, 77, 86, 77, 8)


@functools.lru_cache(maxsize=1)
def subpixel_order():
    """"rgb" or "bgr" when Windows smooths text with ClearType (the
    order of the screen's colour stripes), else None: greyscale smoothing,
    as on other systems by default."""
    if sys.platform != "win32":
        return None
    try:
        user32 = ctypes.windll.user32
        value = ctypes.c_uint(0)
        # SPI_GETFONTSMOOTHING, SPI_GETFONTSMOOTHINGTYPE (2 = ClearType),
        # SPI_GETFONTSMOOTHINGORIENTATION (0 = BGR, 1 = RGB).
        if not user32.SystemParametersInfoW(0x004A, 0, ctypes.byref(value), 0) or not value.value:
            return None
        if not user32.SystemParametersInfoW(0x200A, 0, ctypes.byref(value), 0) or value.value != 2:
            return None
        if user32.SystemParametersInfoW(0x2012, 0, ctypes.byref(value), 0) and value.value == 0:
            return "bgr"
        return "rgb"
    except (AttributeError, OSError):
        return None

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

    def __init__(self, toolbar, color, background):
        super().__init__(toolbar)
        self.setObjectName("studioToolbarLabel")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.color = color
        # The toolbar's background, for ClearType blending (see _render).
        self.background = background
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
        key = (
            self.text, self.font().pixelSize(), self.color.rgba(), self.background.rgba(),
            rect.size(), ratio,
        )
        if key != self._image_key:
            self._image = self._render(rect, ratio)
            self._image_key = key
        # Onto whole device pixels: shift by the fraction of a pixel this
        # widget starts at in its window (only at fractional scaling).
        origin = self.mapTo(self.window(), QPoint(0, 0))
        painter.translate(
            (round(origin.x() * ratio) - origin.x() * ratio) / ratio,
            (round(origin.y() * ratio) - origin.y() * ratio) / ratio,
        )
        painter.drawImage(QPointF(0, 0), self._image)
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
        order = subpixel_order()
        if order is not None and self.background.alpha() == 255:
            return self._render_subpixel(rect, ratio, order)
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

    def _render_subpixel(self, rect, ratio, order):
        """The label with ClearType-style smoothing (see the module
        docstring), as an opaque image on the toolbar's background."""
        width, height = math.ceil(rect.height() * ratio), math.ceil(rect.width() * ratio)
        # Upright text coverage at three samples per pixel vertically; the
        # top of the upright image becomes the left of the turned one.
        coverage = QImage(width, 3 * height, QImage.Format.Format_ARGB32_Premultiplied)
        coverage.fill(Qt.GlobalColor.transparent)
        painter = QPainter(coverage)
        painter.setFont(self.font())
        painter.setPen(QColor(255, 255, 255))
        painter.scale(ratio, 3 * ratio)
        painter.drawText(self._origin(rect.height(), rect.width(), ratio), self.text)
        painter.end()
        stride = coverage.bytesPerLine()
        data = coverage.constBits().asstring(coverage.sizeInBytes())
        # Alpha (byte 3 of each little-endian ARGB pixel) per sample row,
        # padded for the filter.
        blank = bytes(width)
        rows = [blank, blank] + [
            data[y * stride + 3:y * stride + 4 * width:4] for y in range(3 * height)
        ] + [blank, blank]
        a, b, c, d, e = LCD_FILTER
        filtered = [
            bytes((a * p + b * q + c * r + d * s + e * t) >> 8 for p, q, r, s, t in zip(*rows[y:y + 5]))
            for y in range(3 * height)
        ]
        # Per channel: the background blended towards the text colour by its
        # sample's coverage, through lookup tables.
        alpha = self.color.alphaF()
        luts = [
            bytes(round(back + (fore - back) * alpha * v / 255) for v in range(256))
            for fore, back in (
                (self.color.red(), self.background.red()),
                (self.color.green(), self.background.green()),
                (self.color.blue(), self.background.blue()),
            )
        ]
        red, green, blue = (0, 1, 2) if order == "rgb" else (2, 1, 0)
        pixels = bytearray(4 * width * height)
        opaque = b"\xff" * width
        for y in range(height):
            start, end = 4 * width * y, 4 * width * (y + 1)
            samples = filtered[3 * y:3 * y + 3]
            # Format_RGB32 is stored as B, G, R, X.
            pixels[start + 2:end:4] = samples[red].translate(luts[0])
            pixels[start + 1:end:4] = samples[green].translate(luts[1])
            pixels[start:end:4] = samples[blue].translate(luts[2])
            pixels[start + 3:end:4] = opaque
        image = QImage(bytes(pixels), width, height, 4 * width, QImage.Format.Format_RGB32).copy()
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
        self._background = QColor()
        self._windows = []
        self._labels = {}
        self._tooltips = {}
        # Signal connections per toolbar, undone on detach.
        self._slots = {}

    def attach(self, window, color, background):
        """Label every toolbar of `window` (a QMainWindow); `background`
        is the toolbars' background colour."""
        self._color = QColor(color)
        self._background = QColor(background)
        if window not in self._windows:
            self._windows.append(window)
            window.installEventFilter(self)
        for toolbar in window.findChildren(QToolBar):
            if toolbar.parent() is window:
                self._add(toolbar)

    def set_color(self, color, background):
        self._color = QColor(color)
        self._background = QColor(background)
        for label in self._labels.values():
            if not sip.isdeleted(label):
                label.color = self._color
                label.background = self._background
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
        label = _Label(toolbar, self._color, self._background)
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
