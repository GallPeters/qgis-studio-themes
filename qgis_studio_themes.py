"""QGIS Studio Themes plugin.

Each theme is built from shared sources (themes/style.qss, themes/base.qss,
widget glyph templates in themes/icons/ and the modern QGIS icon set in
studio_icons.py) plus the theme's own themes/<folder>/variables.qss.
Built themes live in the profile's themes folder, which QGIS also searches
for theme icons, so dialogs opened later pick up the modern icons natively.
"""
import hashlib
import json
import re
import shutil
import queue
import threading
import time
from pathlib import Path

from qgis.core import Qgis, QgsApplication, QgsMessageLog, QgsSettings
from qgis.gui import QgsFilterLineEdit, QgsProcessingToolboxTreeView
from qgis.PyQt import sip
from qgis.PyQt.QtCore import (
    QAbstractProxyModel, QByteArray, QDataStream, QEvent, QFile, QIODevice, QModelIndex, QObject,
    QPersistentModelIndex, QSize, Qt, QTimer, pyqtSignal, qVersion,
)
from qgis.PyQt.QtGui import (
    QAction, QColor, QFont, QFontDatabase, QGuiApplication, QIcon, QImage, QPainter, QPalette,
    QPixmap, QStandardItemModel,
)
from qgis.PyQt.QtSvg import QSvgRenderer
from qgis.PyQt.QtWidgets import (
    QAbstractButton, QAbstractItemView, QAbstractSpinBox, QApplication, QComboBox, QDockWidget,
    QListWidget, QMenu, QMenuBar, QStackedWidget, QStyledItemDelegate, QTabBar, QToolBar,
    QToolButton,
)

from . import studio_icons
from . import studio_toolbars
from .studio_toolbars import ToolbarLabels
from .studio_tokens import is_dark, parse_color, parse_tokens, render, resolve_tokens

PLUGIN_DIR = Path(__file__).parent
THEMES_DIR = PLUGIN_DIR / "themes"
SHARED_STYLE = THEMES_DIR / "style.qss"
SHARED_TOKENS = THEMES_DIR / "base.qss"
WIDGET_GLYPHS = THEMES_DIR / "icons"
FONTS_DIR = PLUGIN_DIR / "fonts"
METADATA = PLUGIN_DIR / "metadata.txt"
STAMP = ".studio-build"
# Bump when the layout of a built theme changes, so old builds are redone.
BUILD_FORMAT = "11"
FULL_STYLE = "style.full.qss"
# What QGIS loads for every Studio theme except the configured one (see
# QgisStudioThemesPlugin._select_style): a runtime switch then costs QGIS
# a near-empty pass, and the plugin applies the real stylesheet once,
# after installing the palette.
STUB_STYLE = b"/* Studio theme: the plugin applies the stylesheet. */\n"
LOG_TAG = "Studio Themes"
LABELS_SETTING = "studio_themes/toolbarLabels"
# Compact sizes: "auto" (by the screen's pixel density), "on" or "off".
COMPACT_SETTING = "studio_themes/compactSizes"
# Below this many (logical) pixels per inch every pixel is physically large,
# e.g. a 1920x1200 desktop monitor (~95 PPI) against a 14" laptop (~160).
COMPACT_MAX_PPI = 120
MENU_BAR_EXTRA_PT = 2
COMPACT_MENU_BAR_EXTRA_PT = 1
# Icon size of toolbars inside panels (QGIS uses 16 px there).
DOCK_ICON_SIZE = 20
PANEL_ICON_RULES = (
    "QDockWidget QToolBar { qproperty-iconSize: 20px 20px; }\n"
    "QgsBrowserTreeView, QgsLayerTreeView, QgsProcessingToolboxTreeView"
    " { qproperty-iconSize: 20px 20px; }"
)

# QGIS adds these rules to the main window's own stylesheet when it starts
# with a theme that is not registered yet (ours register a moment later).
# They paint the default theme's dark options sidebar and blue table
# selection, and as a widget stylesheet they beat the application one.
DEFAULT_THEME_RULES = re.compile(
    r"[^{}]*(?:mOptionsListWidget|mOptionsListFrame|mOptionsTreeView)[^{}]*\{[^{}]*\}"
    r"|\s*QTableView\s*\{[^{}]*\}"
)


def shared_sources():
    """Files every built theme depends on. An installed release changes
    them only together with metadata.txt, so that one stat() is enough; a
    git checkout (development) tracks every source file."""
    if not (PLUGIN_DIR / ".git").exists():
        return [METADATA]
    sources = [METADATA, SHARED_STYLE, SHARED_TOKENS, Path(studio_icons.__file__), Path(__file__)]
    sources += sorted(WIDGET_GLYPHS.glob("*.svg"))
    sources += sorted(studio_icons.GLYPHS_DIR.glob("*.svg"))
    return sources


def icon_file(name):
    """Override file for a QGIS icon name. Always SVG: QGIS's few .png icons
    are only replaced through IconSwapper (QGIS's own lookup keeps
    resolving those to its built-in PNGs)."""
    return Path(name).with_suffix(".svg")


# Icon sizes (logical px) that get pixel-snapped PNGs: menus and trees (16),
# panel toolbars (20), toolbars (24, or QGIS's configured toolbar size,
# added at runtime) and the larger toolbar sizes QGIS offers.
PNG_SIZES = (16, 20, 24, 32, 48)
# On scaled screens every PNG is loaded up front (see IconSwapper._icon),
# so only the sizes in common use are kept there.
SCALED_PNG_SIZES = (16, 20, 24)


def screen_ratios():
    """The device pixel ratios of all screens (1.0, 1.25, 1.5...)."""
    return frozenset(round(screen.devicePixelRatio(), 2) for screen in QGuiApplication.screens()) or {1.0}


def logical_sizes(ratios, toolbar_size):
    """The logical icon sizes to provide PNGs for on these screens."""
    sizes = set(PNG_SIZES if ratios == {1.0} else SCALED_PNG_SIZES)
    if 8 <= toolbar_size <= 96:
        sizes.add(toolbar_size)
    return tuple(sorted(sizes))


def device_sizes(ratios, sizes):
    """Pixel sizes of the PNGs needed for `sizes` on screens at `ratios`."""
    return frozenset(round(size * ratio) for size in sizes for ratio in ratios)


def icon_colors(tokens):
    """Colours of the normal and the disabled icons of a theme."""
    colors = {
        "icon": tokens["@icon"],
        "accent": tokens["@icon_accent"],
        "danger": tokens["@danger"],
    }
    # Disabled state: glyph and badge both in the theme's disabled colour.
    return colors, dict.fromkeys(colors, tokens["@text_disabled"])


def png_marker(icons_dir):
    return icons_dir / "png" / ".done"


def rendered_sizes(icons_dir):
    """Pixel sizes whose PNGs are complete for a built theme."""
    try:
        return frozenset(json.loads(png_marker(icons_dir).read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return frozenset()


def disabled_path(icons_dir, name):
    """Disabled-state drawing of an icon, shared by every name with the same
    spec. Qt's own disabled rendering fades icons almost into the
    background; these use the theme's @text_disabled instead."""
    return icons_dir / "disabled" / f"{studio_icons.ICON_MAP[name]}.svg"


def png_path(icons_dir, name, size, disabled=False):
    """Shared by every icon name with the same drawing (spec)."""
    suffix = "-disabled" if disabled else ""
    return icons_dir / "png" / studio_icons.ICON_MAP[name] / f"{size}{suffix}.png"


def render_pngs(icons_dir, name, sizes, colors, scale):
    """Pre-render one icon at each pixel size, drawn for that exact size
    with its lines on the pixel grid (studio_icons.render_icon_px), so it
    is shown 1:1, never resampled. Decoding a small PNG is also cheaper
    than drawing an SVG. `colors` is (normal, disabled). Safe in a worker
    thread (QImage painting needs no GUI thread)."""
    spec = studio_icons.ICON_MAP[name]
    for disabled, state_colors in zip((False, True), colors):
        for size in sizes:
            path = png_path(icons_dir, name, size, disabled)
            if path.exists():
                continue
            svg = studio_icons.render_icon_px(spec, state_colors, size, scale)
            renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
            image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            renderer.render(painter)
            painter.end()
            path.parent.mkdir(parents=True, exist_ok=True)
            image.save(str(path))


def build_stamp(sources):
    digest = hashlib.sha1()
    for source in sources:
        stat = source.stat()
        digest.update(f"{source.name}:{stat.st_size}:{stat.st_mtime_ns};".encode())
    return digest.hexdigest()


def load_tokens(folder):
    return resolve_tokens(parse_tokens(
        SHARED_TOKENS.read_text(encoding="utf-8"),
        (THEMES_DIR / folder / "variables.qss").read_text(encoding="utf-8"),
    ))


def prerender_pngs(icons_dir, sizes, colors, scale, stop):
    """Pre-render every distinct icon of a built theme at the pixel sizes
    `sizes` that are not done yet (worker thread). Returns True once all
    are written, False if stopped or failed."""
    done = rendered_sizes(icons_dir)
    missing = sorted(set(sizes) - done)
    try:
        for name in studio_icons.unique_icons():
            if stop.is_set():
                return False
            render_pngs(icons_dir, name, missing, colors, scale)
            time.sleep(0.002)  # yield Python's lock to the GUI thread
        png_marker(icons_dir).parent.mkdir(parents=True, exist_ok=True)
        png_marker(icons_dir).write_text(json.dumps(sorted(done | set(sizes))), encoding="utf-8")
    except OSError:
        return False
    return True


def build_theme(folder, target, shared_stamp, active, extra_tokens=None,
                icon_scale=studio_icons.SCALE):
    """Write the resolved stylesheet and all icons for one theme into
    `target`; style.qss gets the real stylesheet only when `active` (see
    STUB_STYLE). Skipped when nothing changed since the last build, so
    startup costs only a few stat() calls. Thread-safe (no Qt calls).
    Returns True when it (re)built the theme."""
    stamp = build_stamp([THEMES_DIR / folder / "variables.qss"]) + shared_stamp
    stamp_file = target / STAMP
    if stamp_file.exists() and stamp_file.read_text(encoding="utf-8") == stamp:
        return False
    tokens = load_tokens(folder)
    # Forward slashes: Windows backslashes would break url() parsing.
    tokens["@theme_path"] = target.as_posix()
    # Values that depend on the user's QGIS settings (part of shared_stamp).
    tokens.update(extra_tokens or {})
    if (target / "icons").exists():
        shutil.rmtree(target / "icons")
    (target / "icons" / "studio").mkdir(parents=True)

    style, unknown = render(SHARED_STYLE.read_text(encoding="utf-8"), tokens)
    for template in WIDGET_GLYPHS.glob("*.svg"):
        svg, missing = render(template.read_text(encoding="utf-8"), tokens)
        unknown |= missing
        (target / "icons" / "studio" / template.name).write_text(svg, encoding="utf-8")
    if unknown:
        QgsMessageLog.logMessage(
            f"{folder}: unresolved tokens {sorted(unknown)}", LOG_TAG, Qgis.MessageLevel.Warning
        )
    colors, disabled_colors = icon_colors(tokens)
    folders = set()
    svgs = {}
    for name, spec in studio_icons.ICON_MAP.items():
        path = target / "icons" / icon_file(name)
        if path.parent not in folders:
            path.parent.mkdir(parents=True, exist_ok=True)
            folders.add(path.parent)
        if spec not in svgs:
            svgs[spec] = studio_icons.render_icon(spec, colors, icon_scale)
            disabled = target / "icons" / "disabled" / f"{spec}.svg"
            if disabled.parent not in folders:
                disabled.parent.mkdir(parents=True, exist_ok=True)
                folders.add(disabled.parent)
            disabled.write_text(
                studio_icons.render_icon(spec, disabled_colors, icon_scale), encoding="utf-8"
            )
        path.write_text(svgs[spec], encoding="utf-8")
    (target / FULL_STYLE).write_text(style, encoding="utf-8")
    if active:
        shutil.copyfile(target / FULL_STYLE, target / "style.qss")
    else:
        (target / "style.qss").write_bytes(STUB_STYLE)
    stamp_file.write_text(stamp, encoding="utf-8")
    return True


def make_palette(tokens):
    """Qt palette for the theme: plain widgets get their colours from here
    instead of from broad stylesheet rules."""
    def color(token):
        r, g, b, a = parse_color(tokens[token])
        return QColor(r, g, b, round(a * 255))

    role = QPalette.ColorRole
    group = QPalette.ColorGroup
    palette = QPalette()
    for target_role, token in (
        (role.Window, "@bg_window"), (role.WindowText, "@text"),
        (role.Base, "@bg_base"), (role.AlternateBase, "@header_bg"),
        (role.Text, "@text"), (role.Button, "@control_bg"),
        (role.ButtonText, "@text"), (role.BrightText, "@text_bright"),
        # Lists, trees and tables draw selection natively from these.
        (role.Highlight, "@row_selected"), (role.HighlightedText, "@text_bright"),
        (role.ToolTipBase, "@bg_menu"), (role.ToolTipText, "@text"),
        (role.PlaceholderText, "@text_placeholder"), (role.Link, "@accent"),
        (role.LinkVisited, "@accent_pressed"), (role.Light, "@divider_strong"),
        (role.Midlight, "@divider"), (role.Mid, "@divider_strong"),
        (role.Dark, "@field_border"), (role.Shadow, "@border_darker"),
    ):
        palette.setColor(group.All, target_role, color(token))
    for target_role in (role.WindowText, role.Text, role.ButtonText):
        palette.setColor(group.Disabled, target_role, color("@text_disabled"))
    palette.setColor(group.Disabled, role.Base, color("@bg_window"))
    palette.setColor(group.Disabled, role.Button, color("@control_pressed"))
    palette.setColor(group.Inactive, role.Highlight, color("@row_selected_inactive"))
    palette.setColor(group.Inactive, role.HighlightedText, color("@text"))
    return palette


class _IconDelegate(QStyledItemDelegate):
    """Draws a view's rows with the theme's icons, for views whose model
    cannot be edited: the Processing Toolbox, whose icons come from QGIS's
    icon cache (filled before the Studio themes were registered) or from
    the Processing plugin's own image files."""

    def __init__(self, swapper, parent):
        super().__init__(parent)
        self._swapper = swapper

    def initStyleOption(self, option, index):  # pylint: disable=invalid-name
        super().initStyleOption(option, index)
        if option.icon.isNull():
            return
        # Keyed by the row (tool and its group), not by the icon object:
        # Processing plugin tools create a new QIcon on every paint.
        parent = index.parent()
        row = (index.data(), parent.data(), parent.parent().data())
        group = index.model().hasChildren(index)
        icon = self._swapper.row_icon(row, option.icon, group)
        if icon is not None:
            option.icon = icon


class IconSwapper(QObject):
    """Replaces QGIS icons that QGIS created from its built-in set.

    Existing widgets are swapped once when the theme becomes active. New
    windows and pages are swapped when Qt polishes them, right before they
    are first shown, so they never appear with the old icons: dialogs are
    caught through the main window's ChildPolished events, pages that
    panels build later (Labels, renderer and symbol panels) through the
    ChildPolished events of the stacked widgets that host them. Each new
    window or page is scanned once, and only a handful of objects carry an
    event filter, so nothing runs per event across the application.
    Popups and windows without a parent are caught when they get focus.

    Icons are identified by QIcon.cacheKey() first: getThemeIcon() caches
    one QIcon per name and every widget shares that instance. Icons loaded
    straight from Qt Designer .ui files are separate instances; those are
    identified by their serialized SVG data, compared with the built-in
    icon. That reference table is cached on disk per QGIS build."""

    PROPERTY = "_studioIconsTheme"
    RESOURCES = ":/images/themes/default/"
    BATCH = 60
    # Bookkeeping is pruned of deleted objects once it doubles (see _compact).
    COMPACT_MIN = 500
    # The only widgets _visit acts on: a scan asks Qt for these in one call
    # instead of walking every widget of a window from Python.
    ICON_TYPES = (
        QAbstractButton, QToolBar, QMenuBar, QListWidget, QComboBox, QTabBar, QMenu, QStackedWidget,
        QAbstractItemView, QgsFilterLineEdit, QDockWidget,
    )
    # Item views on a QStandardItemModel (e.g. the Options page tree) are
    # swapped item by item; larger models hold data, not navigation icons.
    MODEL_LIMIT = 200
    # The built-in icon fingerprints are computed this long after the theme
    # is applied, WARM_BATCH icons per event-loop pass, so the first dialog
    # opened never pays for all of them at once.
    WARM_DELAY = 4000
    # Processing Toolbox: icons that say "QGIS tool" rather than what the
    # row is; on group rows they are replaced by a folder.
    GENERIC_ICONS = frozenset({"providerQgis.svg", "processingAlgorithm.svg"})
    GROUP_ICON = "mIconFolder.svg"
    # Options > General > UI Theme: QGIS fills it in hash order.
    THEME_COMBO = "cmbUITheme"
    WARM_BATCH = 25
    _DECORATION = Qt.ItemDataRole.DecorationRole
    _UNKNOWN = object()
    _CHILD_POLISHED = QEvent.Type.ChildPolished
    _SHOW = QEvent.Type.Show
    _ACTION_ADDED = QEvent.Type.ActionAdded

    def __init__(self, cache_file=None):
        super().__init__()
        self._cache_file = cache_file
        self._swapped = []
        self._watched = {}
        self._models = {}
        self._filtered = []
        self._stacks = {}
        self._menus = {}
        self._docks = set()
        # Toolbars and menu bars watched for actions added later (a plugin
        # turned on, Processing re-enabled...).
        self._bars = set()
        self._delegates = {}
        # Icon names of rows drawn by delegated views, per row identity.
        self._view_names = {}
        # (screen ratios, logical sizes) while the active theme's PNGs are
        # used, else None (see _pngs_usable).
        self._png = None
        # Loaded PNGs per (spec, pixel size, disabled, ratio), shared by
        # every icon name with the same drawing.
        self._pixmaps = {}
        # QGIS's toolbar icon size, which gets PNGs of its own.
        self._toolbar_size = 24
        self._scanned = []
        self._names = {}
        self._base_names = {}
        self._compact_at = self.COMPACT_MIN
        self._ours = {}
        self._reference_table = None
        # The disk cache is read once; a stale or missing one is recomputed.
        self._cache_checked = False
        # Built incrementally in idle time (see _warm_reference).
        self._reference_partial = None
        self._reference_queue = None
        # availableSizes() signatures of the built-in PNG icons: the only
        # pixmap-based icons worth fingerprinting (see _replacement).
        self._png_signatures = None
        self._icons = {}
        self._pending = []
        self._theme = None
        self._icons_dir = None

    def apply(self, theme, icons_dir, main_window):
        if self._theme is not None:
            self._retheme(theme, icons_dir)
            return
        self.restore()
        self._theme = theme
        self._icons = {}
        self._ours = {}
        self._names = {}
        self._icons_dir = icons_dir
        self._pixmaps = {}
        self._toolbar_size = main_window.iconSize().width()
        self._png = self._pngs_usable(icons_dir)
        self._base_names = {
            QgsApplication.getThemeIcon(name).cacheKey(): name for name in studio_icons.ICON_MAP
        }
        self._names = dict(self._base_names)
        QTimer.singleShot(self.WARM_DELAY, self._warm_reference)
        # Existing widgets: identify cheap matches now, the rest in idle
        # time. Hidden windows are left to the focus fallback and menus are
        # swapped when they are about to open.
        for window in QApplication.topLevelWidgets():
            if window.isVisible() or isinstance(window, QMenu):
                self._scan(window, deferred=True)
        if self._pending:
            QTimer.singleShot(0, self._drain)
        self._filter(main_window)
        QGuiApplication.instance().focusWindowChanged.connect(self._on_focus_window)

    def _retheme(self, theme, icons_dir):
        """Switch from one Studio theme to another in place: every swapped
        icon goes straight to the new theme's version. Restoring the
        built-in icons first would update each action twice, and every
        update relays out the toolbars and menus that show it. Hooks and
        identified icons carry over unchanged."""
        self._compact()
        self._theme = theme
        self._icons = {}
        self._pixmaps = {}
        self._icons_dir = icons_dir
        self._png = self._pngs_usable(icons_dir)
        # Each setIcon repaints its toolbar or menu: suspend painting and
        # repaint every window once at the end.
        windows = [w for w in QApplication.topLevelWidgets() if w.isVisible() and w.updatesEnabled()]
        for window in windows:
            window.setUpdatesEnabled(False)
        try:
            self._retheme_icons(theme)
        finally:
            for window in windows:
                if not sip.isdeleted(window):
                    window.setUpdatesEnabled(True)

    def _retheme_icons(self, theme):
        for action in self._watched:
            if not sip.isdeleted(action):
                new = self._rethemed(action.icon())
                if new is not None:
                    action.setIcon(new)
        for owner, kind, index, _icon in self._swapped:
            if not sip.isdeleted(owner) and self._valid(owner, kind, index):
                new = self._rethemed(self._get(owner, kind, index))
                if new is not None:
                    self._set(owner, kind, index, new)
        for root in self._scanned:
            if not sip.isdeleted(root):
                root.setProperty(self.PROPERTY, theme)
        for view, _original, _delegate in self._delegates.values():
            if not sip.isdeleted(view):
                view.viewport().update()

    def _rethemed(self, icon):
        """The current theme's version of one of our icons (None if `icon`
        is not one of ours, e.g. the application replaced it since)."""
        name = self._ours.get(icon.cacheKey())
        return None if name is None else self._icon(name)

    def use_pngs(self, icons_dir):
        """The active theme's PNGs are ready: every icon handed out so far
        (drawn from the SVGs meanwhile) moves to its pixel-snapped version
        in place, with a single repaint."""
        if self._theme is not None and icons_dir == self._icons_dir and not self._png:
            if self._pngs_usable(icons_dir):
                self._retheme(self._theme, icons_dir)

    def needed_png_sizes(self):
        """Pixel sizes of the PNGs these screens need."""
        ratios = screen_ratios()
        return device_sizes(ratios, logical_sizes(ratios, self._toolbar_size))

    def _pngs_usable(self, icons_dir):
        """(screen ratios, logical sizes) when the theme's PNGs cover every
        size on every screen, else None: the SVGs are used until then."""
        ratios = screen_ratios()
        sizes = logical_sizes(ratios, self._toolbar_size)
        if device_sizes(ratios, sizes) <= rendered_sizes(icons_dir):
            return ratios, sizes
        return None

    def _compact(self):
        """Forget deleted widgets, actions and the icons of closed dialogs,
        so bookkeeping, re-theming and restoring stay proportional to what
        is alive rather than to every dialog opened this session."""
        def alive(obj):
            return not sip.isdeleted(obj)

        self._swapped = [entry for entry in self._swapped if alive(entry[0])]
        self._scanned = [widget for widget in self._scanned if alive(widget)]
        self._filtered = [obj for obj in self._filtered if alive(obj)]
        self._docks = {id(obj) for obj in self._filtered if isinstance(obj, QDockWidget)}
        self._bars = {id(obj) for obj in self._filtered if isinstance(obj, (QToolBar, QMenuBar))}
        self._watched = {action: recheck for action, recheck in self._watched.items() if alive(action)}
        for table in (self._stacks, self._menus, self._models, self._delegates):
            for key in [key for key, entry in table.items() if not alive(entry[0])]:
                del table[key]
        self._names = dict(self._base_names)
        self._names.update(dict.fromkeys(self._ours))
        self._compact_at = max(self.COMPACT_MIN, 2 * (len(self._scanned) + len(self._swapped)))

    def _filter(self, obj):
        obj.installEventFilter(self)
        self._filtered.append(obj)

    def eventFilter(self, watched, event):  # pylint: disable=invalid-name
        kind = event.type()
        if kind == self._SHOW and isinstance(watched, QMenu):
            self._menu_shown(watched)
        elif kind == self._ACTION_ADDED and isinstance(watched, (QToolBar, QMenuBar)):
            # Swap once the code adding the action has finished setting it
            # up (some set the icon after addAction).
            action = event.action()
            QTimer.singleShot(0, lambda action=action: self._swap(action, None, None, False))
        elif kind == self._CHILD_POLISHED:
            child = event.child()
            if child is not None and child.isWidgetType() and (
                not isinstance(watched, QStackedWidget) or watched.currentWidget() is child
            ):
                self._scan(child, deferred=False)
        return False

    def _on_focus_window(self, _window):
        widget = QApplication.activePopupWidget() or QApplication.activeWindow()
        if widget is not None:
            self._scan(widget, deferred=False)

    # ---- Identification ---------------------------------------------------

    @staticmethod
    def _digest(icon):
        data = QByteArray()
        stream = QDataStream(data, QIODevice.OpenModeFlag.WriteOnly)
        stream << icon  # pylint: disable=pointless-statement
        return hashlib.sha1(bytes(data)).hexdigest()

    def _reference_key(self):
        names = "|".join(studio_icons.ICON_MAP)
        return f"{Qgis.version()}|{qVersion()}|{hashlib.sha1(names.encode()).hexdigest()}"

    def _load_reference(self):
        """The fingerprint table from the disk cache (per QGIS/Qt build and
        icon map), or False when it has to be computed."""
        if self._reference_table is not None:
            return True
        if self._cache_checked:
            return False
        self._cache_checked = True
        if self._cache_file is None or not self._cache_file.exists():
            return False
        try:
            cached = json.loads(self._cache_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if cached.get("key") != self._reference_key() or "png_sizes" not in cached:
            return False
        self._reference_table = cached["digests"]
        self._png_signatures = {tuple(map(tuple, sig)) for sig in cached["png_sizes"]}
        return True

    def _reference_step(self, count):
        """Fingerprint up to `count` more built-in icons; True when done."""
        if self._reference_queue is None:
            self._reference_queue = list(studio_icons.ICON_MAP)
            self._reference_partial = {}
            self._png_signatures = set()
        for name in self._reference_queue[:count]:
            # Check first: QIcon on a missing resource logs a Qt warning,
            # which QGIS surfaces in the message bar.
            source = self._source(name)
            if source is None:
                continue
            icon = QIcon(source)
            self._reference_partial.setdefault(self._digest(icon), name)
            if not source.lower().endswith(".svg"):
                self._png_signatures.add(self._signature(icon))
        del self._reference_queue[:count]
        if self._reference_queue:
            return False
        self._reference_table = self._reference_partial
        self._reference_queue = self._reference_partial = None
        if self._cache_file is not None:
            try:
                self._cache_file.write_text(json.dumps({
                    "key": self._reference_key(),
                    "digests": self._reference_table,
                    "png_sizes": sorted(self._png_signatures),
                }), encoding="utf-8")
            except OSError:
                pass
        return True

    def _warm_reference(self):
        """Compute the fingerprint table a batch at a time between events."""
        if self._theme is None or self._load_reference():
            return
        if not self._reference_step(self.WARM_BATCH):
            QTimer.singleShot(0, self._warm_reference)

    def _reference(self):
        """Fingerprints of the built-in icons (finishing them now if the
        idle-time warm-up has not yet)."""
        if not self._load_reference():
            self._reference_step(len(studio_icons.ICON_MAP))
        return self._reference_table

    @staticmethod
    def _signature(icon):
        return tuple(sorted((size.width(), size.height()) for size in icon.availableSizes()))

    def _replacement(self, icon, deferred=False):
        """Our icon for `icon`, None if it has none, or _UNKNOWN when it
        needs the (slower) data comparison and `deferred` is set."""
        if icon.isNull():
            return None
        key = icon.cacheKey()
        name = self._names.get(key, self._UNKNOWN)
        if name is self._UNKNOWN:
            if deferred:
                return self._UNKNOWN
            name = self._identify(icon)
            self._names[key] = name
        if name is None:
            return None
        return self._icon(name)

    def _identify(self, icon):
        """The QGIS icon name of `icon` by its data (None if not ours)."""
        table = self._reference()
        # Pixmap-based icons (symbol previews, colour swatches, legend
        # items) list their pixmap sizes; fingerprinting them would
        # PNG-encode every pixmap. Only the few built-in PNG icons share
        # such a signature, so anything else is not ours to replace.
        signature = self._signature(icon)
        if signature and signature not in self._png_signatures:
            return None
        return table.get(self._digest(icon))

    def row_icon(self, row, icon, group=False):
        """Our version of the icon a delegated view draws for `row` (a
        hashable row identity), or None to keep it. Identified once per row.
        Group rows that only repeat the provider's or the generic tool icon
        get a folder, so groups and tools are told apart at a glance."""
        if self._theme is None:
            return None
        row = (row, group)
        name = self._view_names.get(row, self._UNKNOWN)
        if name is self._UNKNOWN:
            name = self._names.get(icon.cacheKey(), self._UNKNOWN)
            if name is self._UNKNOWN:
                name = self._identify(icon)
            if group and name in self.GENERIC_ICONS:
                name = self.GROUP_ICON
            if len(self._view_names) > 8192:
                self._view_names.clear()
            self._view_names[row] = name
        return None if name is None else self._icon(name)

    def _delegate_view(self, view):
        """Draw `view`'s rows with our icons (only over Qt's plain
        delegate, so no custom drawing is lost)."""
        if id(view) in self._delegates:
            return
        original = view.itemDelegate()
        if original is None or original.metaObject().className() != "QStyledItemDelegate":
            return
        delegate = _IconDelegate(self, view)
        view.setItemDelegate(delegate)
        self._delegates[id(view)] = (view, original, delegate)

    def _icon(self, name):
        """Our icon for a QGIS icon name, in the active theme."""
        if name not in self._icons:
            disabled = str(disabled_path(self._icons_dir, name))
            if self._png:
                ratios, sizes = self._png
                ours = QIcon()
                if ratios == {1.0}:
                    # Loaded lazily, only at the sizes actually drawn.
                    for size in sizes:
                        ours.addFile(str(png_path(self._icons_dir, name, size)), QSize(size, size))
                        ours.addFile(
                            str(png_path(self._icons_dir, name, size, True)), QSize(size, size),
                            QIcon.Mode.Disabled,
                        )
                else:
                    # Qt matches lazily loaded files by size alone and would
                    # stretch them on scaled screens; pixmaps tagged with
                    # their ratio are picked at exactly the device size.
                    for ratio in sorted(ratios):
                        for size in sizes:
                            for disabled, mode in ((False, QIcon.Mode.Normal), (True, QIcon.Mode.Disabled)):
                                ours.addPixmap(self._pixmap(name, round(size * ratio), disabled, ratio), mode)
            else:
                ours = QIcon(str(self._icons_dir / icon_file(name)))
                ours.addFile(disabled, QSize(), QIcon.Mode.Disabled)
            self._icons[name] = ours
            # Never examine our own icons again.
            self._names[ours.cacheKey()] = None
            self._ours[ours.cacheKey()] = name
        return self._icons[name]

    def _pixmap(self, name, size, disabled, ratio):
        key = (studio_icons.ICON_MAP[name], size, disabled, ratio)
        pixmap = self._pixmaps.get(key)
        if pixmap is None:
            pixmap = QPixmap(str(png_path(self._icons_dir, name, size, disabled)))
            pixmap.setDevicePixelRatio(ratio)
            self._pixmaps[key] = pixmap
        return pixmap

    def _builtin(self, icon):
        """The stock icon for one of our icons (used when restoring)."""
        name = self._ours.get(icon.cacheKey())
        source = None if name is None else self._source(name)
        return None if source is None else QIcon(source)

    def _source(self, name):
        """Where QGIS loads the stock icon `name` from (None if missing).
        Checked first: QIcon on a missing file logs a Qt warning, which QGIS
        surfaces in the message bar."""
        if QFile.exists(self.RESOURCES + name):
            return self.RESOURCES + name
        external = studio_icons.EXTERNAL.get(name)
        if external is not None:
            path = Path(QgsApplication.pkgDataPath()) / external
            if path.exists():
                return str(path)
        return None

    # ---- Applying ---------------------------------------------------------

    # Icon slots: (None, None) is the owner's own icon, ("row", i) a list
    # row, ("tab", i) a tab, ("item", i) a combo box item, ("model", p) the
    # item at persistent index p of a QStandardItemModel.
    @staticmethod
    def _valid(owner, kind, index):
        if kind is None:
            return True
        if kind == "model":
            return index.isValid()
        return index < owner.count()

    @classmethod
    def _get(cls, owner, kind, index):
        if kind is None:
            return owner.icon()
        if not cls._valid(owner, kind, index):
            return QIcon()
        if kind == "model":
            icon = owner.data(QModelIndex(index), cls._DECORATION)
            return icon if isinstance(icon, QIcon) else QIcon()
        if kind == "row":
            return owner.item(index).icon()
        if kind == "tab":
            return owner.tabIcon(index)
        return owner.itemIcon(index)

    @classmethod
    def _set(cls, owner, kind, index, icon):
        if kind is None:
            owner.setIcon(icon)
        elif kind == "model":
            owner.setData(QModelIndex(index), icon, cls._DECORATION)
        elif kind == "row":
            owner.item(index).setIcon(icon)
        elif kind == "tab":
            owner.setTabIcon(index, icon)
        else:
            owner.setItemIcon(index, icon)

    def _swap(self, owner, kind, index, deferred):
        if self._theme is None or sip.isdeleted(owner):
            return
        icon = self._get(owner, kind, index)
        new = self._replacement(icon, deferred)
        if new is self._UNKNOWN:
            self._pending.append((owner, kind, index))
            return
        if new is None:
            return
        if isinstance(owner, QAction):
            owner.setIcon(new)
            self._watch(owner)
            return
        self._swapped.append((owner, kind, index, icon))
        self._set(owner, kind, index, new)

    def _scan(self, root, deferred):
        """Swap every icon in a widget tree; each tree is scanned once.

        Only the current page of each stacked widget is entered (dialogs
        and panels keep most pages hidden); other pages are scanned when
        they become current. Qt returns the candidates parents first, so a
        stacked widget is always seen before the pages it excludes."""
        if self._theme is None or sip.isdeleted(root) or root.property(self.PROPERTY) == self._theme:
            return
        if len(self._scanned) + len(self._swapped) >= self._compact_at:
            self._compact()
        self._mark(root)
        widgets = root.findChildren(self.ICON_TYPES)
        if isinstance(root, self.ICON_TYPES):
            widgets.insert(0, root)
        skipped = set()
        for widget in widgets:
            if widget in skipped:
                continue
            self._visit(widget, deferred)
            if isinstance(widget, QStackedWidget):
                self._hook_stack(widget)
                current = widget.currentWidget()
                for index in range(widget.count()):
                    page = widget.widget(index)
                    if page is current and page.property(self.PROPERTY) != self._theme:
                        self._mark(page)
                    else:
                        skipped.add(page)
                        skipped.update(page.findChildren(self.ICON_TYPES))

    def _mark(self, widget):
        widget.setProperty(self.PROPERTY, self._theme)
        self._scanned.append(widget)

    def _hook_stack(self, stacked):
        """Scan pages when they are shown, and pages added later (panels
        build them on demand) before they are first shown."""
        if id(stacked) in self._stacks:
            return

        def current_changed(index, stacked=stacked):
            if self._theme is not None and not sip.isdeleted(stacked):
                page = stacked.widget(index)
                if page is not None:
                    self._scan(page, deferred=False)

        stacked.currentChanged.connect(current_changed)
        self._stacks[id(stacked)] = (stacked, current_changed)
        self._filter(stacked)

    def _visit(self, widget, deferred):
        """Swap the icons one widget shows itself (not its children)."""
        if isinstance(widget, QToolButton):
            action = widget.defaultAction()
            if action is not None:
                self._swap(action, None, None, deferred)
            else:
                self._swap(widget, None, None, deferred)
            # Drop-down choices (align, distribute, export...): actions added
            # to the button itself, or a menu outside the scanned tree.
            for extra in widget.actions():
                if extra is not action:
                    self._swap(extra, None, None, deferred)
            menu = widget.menu() or (action.menu() if action is not None else None)
            if menu is not None:
                self._hook_menu(menu)
                # Mode buttons (snapping type, overlap...): QGIS later makes
                # one of these choices the button's default action, so swap
                # them now rather than only when the menu first opens.
                for choice in menu.actions():
                    self._swap(choice, None, None, deferred)
        elif isinstance(widget, QMenu):
            self._hook_menu(widget)
        elif isinstance(widget, (QToolBar, QMenuBar)):
            for action in widget.actions():
                self._swap(action, None, None, deferred)
            if id(widget) not in self._bars:
                self._bars.add(id(widget))
                self._filter(widget)
        elif isinstance(widget, QAbstractButton):
            self._swap(widget, None, None, deferred)
        elif isinstance(widget, QListWidget):
            self._rows(widget, "row", deferred)
        elif isinstance(widget, QComboBox):
            if widget.objectName() == self.THEME_COMBO:
                self._sort_themes(widget)
            self._rows(widget, "item", deferred)
        elif isinstance(widget, QTabBar):
            for index in range(widget.count()):
                self._swap(widget, "tab", index, deferred)
        elif isinstance(widget, QgsFilterLineEdit):
            # Embedded actions (clear, search). Spin boxes' editors are
            # skipped: big dialogs hold hundreds of them.
            if not isinstance(widget.parent(), QAbstractSpinBox):
                for action in widget.actions():
                    self._swap(action, None, None, deferred)
        elif isinstance(widget, QDockWidget):
            # Panels may get (or replace) their contents after the window
            # was scanned.
            if id(widget) not in self._docks:
                self._docks.add(id(widget))
                self._filter(widget)
        elif isinstance(widget, QAbstractItemView):
            if isinstance(widget, QgsProcessingToolboxTreeView):
                self._delegate_view(widget)
            if isinstance(widget, QgsProcessingToolboxTreeView):
                # Every row has the same height (theme rule): let Qt measure
                # one row instead of each, when expanding and scrolling. (Not
                # the Browser: it is filled lazily, and a row measured while
                # it is still empty collapses every row to nothing.)
                widget.setUniformRowHeights(True)
            model = widget.model()
            while isinstance(model, QAbstractProxyModel):
                model = model.sourceModel()
            # Only navigation-style lists (one column, few rows, e.g. the
            # Options page tree); data tables are skipped outright. A combo
            # box's popup view shares the model already hooked by _rows.
            if (
                isinstance(model, QStandardItemModel)
                and id(model) not in self._models
                and model.columnCount() == 1
                and model.rowCount() <= self.MODEL_LIMIT
            ):
                self._model_items(model, deferred)

    @staticmethod
    def _sort_themes(combo):
        """Alphabetical theme list, so the Studio themes sit together. The
        selection is kept and no change signal is sent (QGIS would treat it
        as a theme choice)."""
        current = combo.currentText()
        names = sorted((combo.itemText(i) for i in range(combo.count())), key=str.casefold)
        if names == [combo.itemText(i) for i in range(combo.count())]:
            return
        blocked = combo.blockSignals(True)
        try:
            combo.clear()
            combo.addItems(names)
            combo.setCurrentIndex(max(0, combo.findText(current)))
        finally:
            combo.blockSignals(blocked)

    def _hook_menu(self, menu):
        """Swap a menu's icons right before it opens, not at startup. The
        swap happens on the Show event, after every aboutToShow handler, so
        actions QGIS (re)creates there are covered too; the event filter is
        installed only while the menu opens, not for every hover event."""
        if id(menu) in self._menus:
            return

        def about_to_show(menu=menu):
            if self._theme is not None and not sip.isdeleted(menu):
                menu.installEventFilter(self)

        menu.aboutToShow.connect(about_to_show)
        self._menus[id(menu)] = (menu, about_to_show)

    def _menu_shown(self, menu):
        menu.removeEventFilter(self)
        if self._theme is None:
            return
        for action in menu.actions():
            self._swap(action, None, None, False)
            if action.menu() is not None:
                self._hook_menu(action.menu())

    def _rows(self, widget, kind, deferred):
        for index in range(widget.count()):
            self._swap(widget, kind, index, deferred)
        model = widget.model()
        if id(model) in self._models:
            return

        def inserted(_parent, first, last, widget=widget, kind=kind):
            if self._theme is None or sip.isdeleted(widget):
                return
            for index in range(first, last + 1):
                self._swap(widget, kind, index, False)

        model.rowsInserted.connect(inserted)
        self._models[id(model)] = (model, inserted)

    def _model_items(self, model, deferred):
        """Swap the item icons of a small QStandardItemModel, and of rows
        added to it later."""
        def walk(parent, budget):
            for row in range(model.rowCount(parent)):
                if budget[0] <= 0:
                    return
                budget[0] -= 1
                index = model.index(row, 0, parent)
                if isinstance(model.data(index, self._DECORATION), QIcon):
                    self._swap(model, "model", QPersistentModelIndex(index), deferred)
                if model.hasChildren(index):
                    walk(index, budget)

        walk(QModelIndex(), [self.MODEL_LIMIT])

        def inserted(parent, first, last, model=model):
            if self._theme is None or sip.isdeleted(model):
                return
            for row in range(first, last + 1):
                index = model.index(row, 0, parent)
                if isinstance(model.data(index, self._DECORATION), QIcon):
                    self._swap(model, "model", QPersistentModelIndex(index), False)

        model.rowsInserted.connect(inserted)
        self._models[id(model)] = (model, inserted)

    def _drain(self):
        """Identify queued icons a batch at a time between events."""
        if self._theme is None:
            self._pending = []
            return
        batch, self._pending = self._pending[:self.BATCH], self._pending[self.BATCH:]
        for owner, kind, index in batch:
            self._swap(owner, kind, index, False)
        if self._pending:
            QTimer.singleShot(0, self._drain)

    def _watch(self, action):
        """QGIS re-sets some action icons from its cache later; swap again
        whenever that happens."""
        if action in self._watched:
            return

        def recheck(action=action):
            if self._theme is None or sip.isdeleted(action):
                return
            new = self._replacement(action.icon())
            if new is not None:
                action.setIcon(new)

        action.changed.connect(recheck)
        self._watched[action] = recheck

    def restore(self):
        if self._theme is not None:
            QGuiApplication.instance().focusWindowChanged.disconnect(self._on_focus_window)
        self._theme = None
        self._pending = []
        for obj in self._filtered:
            if not sip.isdeleted(obj):
                obj.removeEventFilter(self)
        self._filtered = []
        self._docks = set()
        self._bars = set()
        for stacked, current_changed in self._stacks.values():
            if not sip.isdeleted(stacked):
                stacked.currentChanged.disconnect(current_changed)
        self._stacks = {}
        for menu, about_to_show in self._menus.values():
            if not sip.isdeleted(menu):
                menu.aboutToShow.disconnect(about_to_show)
                menu.removeEventFilter(self)
        self._menus = {}
        for view, original, delegate in self._delegates.values():
            if not sip.isdeleted(view):
                view.setItemDelegate(original)
                view.viewport().update()
            if not sip.isdeleted(delegate):
                delegate.deleteLater()
        self._delegates = {}
        self._view_names = {}
        for model, inserted in self._models.values():
            if not sip.isdeleted(model):
                model.rowsInserted.disconnect(inserted)
        self._models = {}
        for action, recheck in self._watched.items():
            if sip.isdeleted(action):
                continue
            action.changed.disconnect(recheck)
            builtin = self._builtin(action.icon())
            if builtin is not None:
                action.setIcon(builtin)
        self._watched = {}
        for owner, kind, index, icon in reversed(self._swapped):
            if not sip.isdeleted(owner) and self._valid(owner, kind, index):
                self._set(owner, kind, index, icon)
        self._swapped = []
        for root in self._scanned:
            if not sip.isdeleted(root):
                root.setProperty(self.PROPERTY, None)
        self._scanned = []
        self._compact_at = self.COMPACT_MIN


class _Relay(QObject):
    """Carries worker-thread results to the GUI thread (queued signal)."""
    pngs_ready = pyqtSignal(object)


class QgisStudioThemesPlugin:
    """Registers the Studio themes and keeps the parts a stylesheet cannot
    reach (palette, font, icons, message bar) in sync with the active one."""

    # Display name (registered as "Studio <name>") -> folder under themes/
    THEMES = {
        "Premium Dark": "premium",
        "Web Dark": "web",
        "Orange Dark": "dark",
        "Pro Light": "pro",
        "Orange Light": "light_orange",
        "QGIS Light": "qgis_light",
    }
    # Former display names -> current ones (kept so saved settings follow).
    RENAMED = {
        "Studio Pro": "Studio Pro Light",
        "Studio Premium": "Studio Premium Dark",
        "Studio Web": "Studio Web Dark",
        "Studio Dark": "Studio Orange Dark",
        "Studio Light Orange": "Studio Orange Light",
    }

    def __init__(self, iface):
        self.iface = iface
        self._connected = False
        self._active = None
        self._tokens = {}
        self._original_palette = QPalette(QApplication.palette())
        self._original_font = QFont(QApplication.font())
        self._icons = IconSwapper(
            Path(QgsApplication.userThemesFolder()) / ".studio-icon-digests.json"
        )
        self._message_bar_items = []
        self._main_window_sheet = None
        self._prepared = None
        self._fonts_loaded = False
        self._shared_stamp = None
        # One lock per theme serialises its build (background builder vs.
        # a runtime switch) and its style.qss.
        self._locks = {name: threading.Lock() for name in self.THEMES}
        self._stop = threading.Event()
        self._threads = []
        self._jobs = queue.Queue()
        self._worker_lock = threading.Lock()
        self._worker_running = False
        self._rendering = set()
        self._relay = _Relay()
        self._relay.pngs_ready.connect(self._icons.use_pngs)
        self._labels = ToolbarLabels()
        self._labels_action = None
        self._compact_action = None
        self._compact = False
        self._extra_tokens = {}
        self._dock_icon_sizes = {}
        # Themes (re)built by this plugin load, i.e. new or updated.
        self._rebuilt = set()

    @staticmethod
    def theme_target(name):
        return Path(QgsApplication.userThemesFolder()) / f"Studio {name}"

    def initGui(self):
        # QGIS applies the configured theme as soon as it is registered.
        # Install palette and font first so that single stylesheet pass
        # already sees them (no second, full repolish at startup).
        settings = QgsSettings()
        configured = settings.value("UI/UITheme", "", type=str)
        # The theme QGIS already shows: a Studio theme when the plugin is
        # installed or upgraded in a running QGIS (Plugin Manager), and its
        # icons, cached by QGIS, come from that theme's current files.
        running = QgsApplication.themeName()
        renamed_running = None
        for old_name, new_name in self.RENAMED.items():
            old_target = Path(QgsApplication.userThemesFolder()) / old_name
            if running == old_name:
                # Removed at the next start instead: deleting the files now
                # would blank the icons QGIS cached from them.
                renamed_running = new_name
            elif (old_target / STAMP).exists():
                shutil.rmtree(old_target, ignore_errors=True)
            if configured == old_name:
                configured = new_name
                settings.setValue("UI/UITheme", configured)
        if configured in self._studio_themes():
            self._prepare(configured)
        QgsApplication.instance().themeChanged.connect(self._sync)
        self.iface.messageBar().widgetAdded.connect(self._style_message_bar)
        self.iface.layoutDesignerOpened.connect(self._label_designer)
        self._connected = True
        self._labels_action = QAction("Studio Toolbar Labels", self.iface.mainWindow())
        self._labels_action.setObjectName("mActionStudioToolbarLabels")
        self._labels_action.setCheckable(True)
        self._labels_action.setChecked(QgsSettings().value(LABELS_SETTING, True, type=bool))
        self._labels_action.setToolTip("Show each toolbar's name on its handle (Studio themes)")
        self._labels_action.toggled.connect(self._toggle_labels)
        self.iface.viewMenu().addAction(self._labels_action)
        self._compact = self._compact_sizes()
        studio_toolbars.set_compact(self._compact)
        self._compact_action = QAction("Studio Compact Sizes", self.iface.mainWindow())
        self._compact_action.setObjectName("mActionStudioCompactSizes")
        self._compact_action.setCheckable(True)
        self._compact_action.setChecked(self._compact)
        self._compact_action.setToolTip(
            "Smaller menu, panel icons and toolbar labels for large desktop monitors"
            " (chosen automatically by the screen; applies after restarting QGIS)"
        )
        self._compact_action.toggled.connect(self._toggle_compact)
        self.iface.viewMenu().addAction(self._compact_action)
        # The main menu is one point larger than the UI font, so it reads as
        # the top level. The size goes into the theme stylesheet (a widget
        # stylesheet on the bar would give every menu, all children of the
        # bar, a slower style chain of its own) and into the build stamp, so
        # a changed QGIS font size rebuilds the themes.
        # From QGIS's font-size option (or the font QGIS started with), not
        # from the menu bar, which already carries this theme's larger size
        # when the plugin is reloaded while a Studio theme is active.
        base_size = QgsSettings().value(
            "qgis/stylesheet/fontPointSize", self._original_font.pointSizeF(), type=float
        )
        # Compact sizes: the menu and panel titles stay closer to the UI
        # font, panels keep QGIS's own icon size and icons are enlarged less.
        compact = self._compact
        menu_size = base_size + (COMPACT_MENU_BAR_EXTRA_PT if compact else MENU_BAR_EXTRA_PT)
        self._extra_tokens = {
            "@menu_font_size": f"{menu_size:g}pt",
            "@panel_title_font_size": f"{base_size + (0 if compact else 1):g}pt",
            "@ui_font_size": f"{base_size:g}pt",
            "@menu_item_padding_x": "11px" if compact else "14px",
            "@panel_icon_rules": "" if compact else PANEL_ICON_RULES,
        }
        self._shared_stamp = (
            BUILD_FORMAT + build_stamp(shared_sources()) + f"|menu{menu_size:g}"
            + ("|compact" if compact else "")
        )
        # Only the configured theme is built now; the others only need a
        # placeholder style.qss to be registered and are built in the
        # background (or on demand, if selected first).
        registered = []
        pending = []
        for name in self.THEMES:
            if f"Studio {name}" == configured:
                if self._build(name, active=True):
                    registered.append(name)
                continue
            style = self.theme_target(name) / "style.qss"
            if not style.exists():
                style.parent.mkdir(parents=True, exist_ok=True)
                style.write_bytes(STUB_STYLE)
            registered.append(name)
            pending.append(name)
        # Before registering: QGIS loads the configured theme's style.qss
        # as soon as that theme is registered.
        self._select_style(configured)
        for name in registered:
            QgsApplication.applicationThemeRegistry().addTheme(
                f"Studio {name}", self.theme_target(name).as_posix()
            )
        if renamed_running is not None and renamed_running == configured:
            # Upgraded while QGIS shows a theme under its former name: move
            # QGIS to the new name now, not only at the next start.
            QgsApplication.setUITheme(configured)
        # When the configured theme is applied later, themeChanged syncs;
        # syncing now would undo the preparation above.
        studio = self._studio_themes()
        if QgsApplication.themeName() in studio:
            self._sync()
        if (running in studio or running in self.RENAMED) and configured in studio and (
            studio[configured][0] in self._rebuilt
        ):
            # QGIS cached some icons from the previous version's files
            # (e.g. Browser provider icons) and offers no way to drop them.
            self.iface.messageBar().pushMessage(
                "Studio Themes", "Updated. Restart QGIS once so every icon shows the new version.",
                Qgis.MessageLevel.Info, 30,
            )
        QTimer.singleShot(2000, lambda: self._start(self._build_pending, pending))

    def _build(self, name, active=False):
        """Build one theme (no-op when up to date); False if it failed."""
        scale = studio_icons.COMPACT_SCALE if self._compact else studio_icons.SCALE
        with self._locks[name]:
            try:
                if build_theme(
                    self.THEMES[name], self.theme_target(name), self._shared_stamp, active,
                    self._extra_tokens, scale,
                ):
                    self._rebuilt.add(name)
            except Exception as error:  # pylint: disable=broad-except
                QgsMessageLog.logMessage(
                    f"Could not build Studio {name}: {error}", LOG_TAG, Qgis.MessageLevel.Critical
                )
                return False
        return True

    def _build_pending(self, names):
        for name in names:
            if self._stop.is_set():
                return
            self._build(name)

    def _start(self, target, *args):
        """Queue `target` for the single background worker: theme builds
        and PNG pre-rendering run one after another, never in parallel, so
        they compete less with the GUI thread for Python's lock."""
        if self._stop.is_set():
            return
        with self._worker_lock:
            self._jobs.put((target, args))
            if not self._worker_running:
                self._worker_running = True
                thread = threading.Thread(target=self._work, daemon=True)
                self._threads = [thread]
                thread.start()

    def _work(self):
        while not self._stop.is_set():
            try:
                target, args = self._jobs.get(timeout=0.5)
            except queue.Empty:
                # Exit only if nothing was queued meanwhile; _start checks
                # the same flag under the same lock, so no job is dropped.
                with self._worker_lock:
                    if self._jobs.empty():
                        self._worker_running = False
                        return
                continue
            target(*args)
        with self._worker_lock:
            self._worker_running = False

    def unload(self):
        self._stop.set()
        for thread in self._threads:
            thread.join()
        self._threads = []
        if self._connected:
            QgsApplication.instance().themeChanged.disconnect(self._sync)
            self.iface.messageBar().widgetAdded.disconnect(self._style_message_bar)
            self.iface.layoutDesignerOpened.disconnect(self._label_designer)
            self._connected = False
        for action in (self._labels_action, self._compact_action):
            if action is not None:
                self.iface.viewMenu().removeAction(action)
                action.deleteLater()
        self._labels_action = self._compact_action = None
        self._deactivate()
        for name in self.THEMES:
            QgsApplication.applicationThemeRegistry().removeTheme(f"Studio {name}")

    # ---- Theme state ------------------------------------------------------

    def _select_style(self, active):
        """Give QGIS the real stylesheet only for `active` (the theme it
        will load at startup) and the placeholder for the others. Sizes
        tell them apart (style.qss is only ever one of the two), so this
        costs a few stat() calls instead of reading every stylesheet."""
        for name in self.THEMES:
            is_active = f"Studio {name}" == active
            lock = self._locks[name]
            # A theme being built in the background gets the placeholder
            # from its build; the active one must not be skipped.
            if not lock.acquire(blocking=is_active):
                continue
            try:
                target = self.theme_target(name)
                full = target / FULL_STYLE
                current = target / "style.qss"
                if not full.exists():
                    continue
                size = current.stat().st_size if current.exists() else -1
                if is_active:
                    if size != full.stat().st_size:
                        shutil.copyfile(full, current)
                elif size != len(STUB_STYLE):
                    current.write_bytes(STUB_STYLE)
            finally:
                lock.release()

    def _studio_themes(self):
        return {f"Studio {name}": (name, folder) for name, folder in self.THEMES.items()}

    def _prepare(self, theme):
        """Everything that must be in place before the stylesheet is
        polished: Qt bakes the current palette and font into each styled
        widget during polish, so later changes would not reach them."""
        name, folder = self._studio_themes()[theme]
        self._tokens = load_tokens(folder)
        dark = is_dark(self._tokens["@bg_window"])
        self._set_color_scheme(Qt.ColorScheme.Dark if dark else Qt.ColorScheme.Light)
        QApplication.setPalette(make_palette(self._tokens))
        if not QgsSettings().contains("app/fontFamily"):
            if not self._fonts_loaded:
                for font_file in sorted(FONTS_DIR.glob("*.ttf")):
                    QFontDatabase.addApplicationFont(str(font_file))
                self._fonts_loaded = True
            font = QFont(self._original_font)
            font.setFamily(self._tokens["@font_family"].strip("\"'"))
            QApplication.setFont(font)
        window = self.iface.mainWindow()
        sheet = window.styleSheet()
        cleaned = DEFAULT_THEME_RULES.sub("", sheet)
        if cleaned != sheet:
            if self._main_window_sheet is None:
                self._main_window_sheet = sheet
            window.setStyleSheet(cleaned)
        self._prepared = theme

    def _sync(self):
        theme = QgsApplication.themeName()
        studio = self._studio_themes()
        if theme not in studio:
            self._deactivate()
            return
        if theme == self._active:
            return
        if not self._build(studio[theme][0]):
            self._deactivate()
            return
        if self._prepared != theme:
            # Switched at runtime: QGIS has just applied the near-empty
            # placeholder, which already dropped the palette copies Qt kept
            # on widgets styled under the previous theme. The palette goes
            # in before the real stylesheet, so every widget is polished
            # once, with the right colours.
            self._prepare(theme)
            full = self.theme_target(studio[theme][0]) / FULL_STYLE
            QApplication.instance().setStyleSheet(full.read_text(encoding="utf-8"))
            self._select_style(theme)
        self._active = theme
        name = studio[theme][0]
        icons_dir = self.theme_target(name) / "icons"
        self._icons.apply(theme, icons_dir, self.iface.mainWindow())
        self._style_message_bar()
        self._apply_labels()
        # After QGIS's own startup sizing, which would undo it.
        QTimer.singleShot(0, self._size_dock_toolbars)
        self._prerender(icons_dir)

    def _size_dock_toolbars(self):
        """Panel toolbars (Browser, Layers, Processing Toolbox...) get
        slightly larger icons. The stylesheet rule covers panels polished
        later; existing ones are resized here and restored on leaving."""
        if self._active is None or self._compact:
            return
        size = QSize(DOCK_ICON_SIZE, DOCK_ICON_SIZE)
        for dock in self.iface.mainWindow().findChildren(QDockWidget):
            for toolbar in dock.findChildren(QToolBar):
                if toolbar.iconSize().width() < DOCK_ICON_SIZE:
                    self._dock_icon_sizes.setdefault(toolbar, toolbar.iconSize())
                    toolbar.setIconSize(size)

    # ---- Compact sizes ----------------------------------------------------

    def _compact_sizes(self):
        """Compact sizes on screens with large pixels (low density), unless
        the user chose otherwise. In logical pixels per inch, a 14 inch
        1920x1200 laptop has ~160 and a 24 inch monitor at the same
        resolution ~95: the same UI is ~1.7x larger there."""
        mode = QgsSettings().value(COMPACT_SETTING, "auto", type=str)
        if mode in ("on", "off"):
            return mode == "on"
        window = self.iface.mainWindow()
        screen = (window.screen() if window is not None else None) or QGuiApplication.primaryScreen()
        if screen is None:
            return False
        # Screens that report no (or a nonsense) physical size keep the default.
        return 50 <= screen.physicalDotsPerInch() < COMPACT_MAX_PPI

    def _toggle_compact(self, checked):
        QgsSettings().setValue(COMPACT_SETTING, "on" if checked else "off")
        self.iface.messageBar().pushMessage(
            "Studio Themes", "Restart QGIS to apply the new sizes.", Qgis.MessageLevel.Info, 10
        )

    # ---- Toolbar labels ---------------------------------------------------

    def _labels_enabled(self):
        return self._labels_action is not None and self._labels_action.isChecked()

    def _label_color(self):
        """Halfway from the dimmed to the normal text colour: crisp and
        readable at 10 px, still quieter than the icons."""
        dim, text = parse_color(self._tokens["@text_dim"]), parse_color(self._tokens["@text"])
        r, g, b, a = (x + (y - x) / 2 for x, y in zip(dim, text))
        return QColor(round(r), round(g), round(b), round(a * 255))

    def _label_background(self):
        """The toolbars' background (QToolBar in style.qss), which the
        labels blend their ClearType smoothing onto."""
        r, g, b, a = parse_color(self._tokens["@bg_window"])
        return QColor(round(r), round(g), round(b), round(a * 255))

    def _apply_labels(self):
        """Attach (or update) the toolbar labels for the active theme."""
        if self._active is None or not self._labels_enabled():
            self._labels.detach()
            return
        color, background = self._label_color(), self._label_background()
        self._labels.set_color(color, background)
        self._labels.attach(self.iface.mainWindow(), color, background)
        for designer in self.iface.openLayoutDesigners():
            self._labels.attach(designer.window(), color, background)

    def _toggle_labels(self, checked):
        QgsSettings().setValue(LABELS_SETTING, checked)
        self._apply_labels()

    def _label_designer(self, designer):
        if self._active is not None and self._labels_enabled():
            self._labels.attach(designer.window(), self._label_color(), self._label_background())

    def _prerender(self, icons_dir):
        """Pre-render the theme's icons as pixel-snapped PNGs for these
        screens in a worker thread, off startup's critical path; icons
        shown meanwhile move to them once they are ready."""
        sizes = self._icons.needed_png_sizes()
        if icons_dir in self._rendering or sizes <= rendered_sizes(icons_dir):
            return
        self._rendering.add(icons_dir)
        colors = icon_colors(self._tokens)
        scale = studio_icons.COMPACT_SCALE if self._compact else studio_icons.SCALE

        def work():
            if prerender_pngs(icons_dir, sizes, colors, scale, self._stop):
                self._relay.pngs_ready.emit(icons_dir)
            self._rendering.discard(icons_dir)

        QTimer.singleShot(3000, lambda: self._start(work))

    def _deactivate(self):
        if self._active is None and self._prepared is None:
            return
        self._active = None
        self._prepared = None
        self._labels.detach()
        for toolbar, size in self._dock_icon_sizes.items():
            if not sip.isdeleted(toolbar):
                toolbar.setIconSize(size)
        self._dock_icon_sizes = {}
        self._icons.restore()
        QApplication.setPalette(self._original_palette)
        QApplication.setFont(self._original_font)
        self._set_color_scheme(Qt.ColorScheme.Unknown)
        if self._main_window_sheet is not None:
            self.iface.mainWindow().setStyleSheet(self._main_window_sheet)
            self._main_window_sheet = None
        bar = self.iface.messageBar()
        item = bar.currentItem()
        if item is not None and hasattr(item, "getStyleSheet"):
            bar.setStyleSheet(item.getStyleSheet())

    # ---- Message bar ------------------------------------------------------

    def _style_message_bar(self, item=None):
        """QGIS styles the bar per message level with fixed light colours
        (widget-level, so the app stylesheet cannot override it). Replace
        them with tinted theme colours after QGIS applied its own."""
        if self._active is None:
            return
        bar = self.iface.messageBar()
        # widgetAdded passes the item typed as a plain QWidget; the bar's
        # current item is the same object with its full API.
        item = bar.currentItem()
        if item is None:
            return
        if item not in self._message_bar_items:
            self._message_bar_items.append(item)
            item.styleChanged.connect(lambda _sheet, item=item: self._style_message_bar(item))
            item.destroyed.connect(lambda _obj=None, item=item: self._forget_item(item))
        level = {
            Qgis.MessageLevel.Info: "info",
            Qgis.MessageLevel.Success: "success",
            Qgis.MessageLevel.Warning: "warning",
            Qgis.MessageLevel.Critical: "danger",
        }.get(item.level(), "info")
        t = self._tokens
        bar.setStyleSheet(
            f"QgsMessageBar {{ background-color: {t[f'@{level}_bg']};"
            f" border: 1px solid {t[f'@{level}_border']}; border-radius: {t['@radius']}; }}"
            f" QLabel, QTextEdit {{ color: {t['@text']}; background: transparent; border: none; }}"
            " QLabel#mItemCount { font-style: italic; }"
        )

    def _forget_item(self, item):
        if item in self._message_bar_items:
            self._message_bar_items.remove(item)

    @staticmethod
    def _set_color_scheme(scheme):
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "setColorScheme"):  # requires Qt >= 6.8
            hints.setColorScheme(scheme)
