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
import threading
from pathlib import Path

from qgis.core import Qgis, QgsApplication, QgsMessageLog, QgsSettings
from qgis.gui import QgsFilterLineEdit
from qgis.PyQt import sip
from qgis.PyQt.QtCore import (
    QAbstractProxyModel, QByteArray, QDataStream, QEvent, QFile, QIODevice, QModelIndex, QObject,
    QPersistentModelIndex, QSize, Qt, QTimer, pyqtSignal, qVersion,
)
from qgis.PyQt.QtGui import (
    QAction, QColor, QFont, QFontDatabase, QGuiApplication, QIcon, QImage, QPainter, QPalette,
    QStandardItemModel,
)
from qgis.PyQt.QtSvg import QSvgRenderer
from qgis.PyQt.QtWidgets import (
    QAbstractButton, QAbstractItemView, QAbstractSpinBox, QApplication, QComboBox, QDockWidget,
    QListWidget, QMenu, QMenuBar, QStackedWidget, QTabBar, QToolBar, QToolButton,
)

from . import studio_icons
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
BUILD_FORMAT = "5"
FULL_STYLE = "style.full.qss"
# What QGIS loads for every Studio theme except the configured one (see
# QgisStudioThemesPlugin._select_style): a runtime switch then costs QGIS
# a near-empty pass, and the plugin applies the real stylesheet once,
# after installing the palette.
STUB_STYLE = b"/* Studio theme: the plugin applies the stylesheet. */\n"
LOG_TAG = "Studio Themes"
LABELS_SETTING = "studio_themes/toolbarLabels"
MENU_BAR_EXTRA_PT = 1
# Icon size of toolbars inside panels (QGIS uses 16 px there).
DOCK_ICON_SIZE = 20

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


PNG_SIZES = (16, 24, 32, 48)


def png_path(icons_dir, name, size):
    """Shared by every icon name with the same drawing (spec)."""
    return icons_dir / "png" / studio_icons.ICON_MAP[name] / f"{size}.png"


def render_pngs(icons_dir, name):
    """Pre-render one icon at the common sizes: decoding a small PNG is
    about 2.5x cheaper than drawing the SVG the first time it is shown.
    Safe in a worker thread (QImage painting needs no GUI thread)."""
    renderer = QSvgRenderer(str(icons_dir / icon_file(name)))
    for size in PNG_SIZES:
        image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        path = png_path(icons_dir, name, size)
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


def prerender_pngs(icons_dir, stop):
    """Pre-render every distinct icon of a built theme (worker thread).
    Returns True once all are written, False if stopped or failed."""
    try:
        for name in studio_icons.unique_icons():
            if stop.is_set():
                return False
            render_pngs(icons_dir, name)
        (icons_dir / "png" / ".done").write_bytes(b"")
    except OSError:
        return False
    return True


def build_theme(folder, target, shared_stamp, active, extra_tokens=None):
    """Write the resolved stylesheet and all icons for one theme into
    `target`; style.qss gets the real stylesheet only when `active` (see
    STUB_STYLE). Skipped when nothing changed since the last build, so
    startup costs only a few stat() calls. Thread-safe (no Qt calls)."""
    stamp = build_stamp([THEMES_DIR / folder / "variables.qss"]) + shared_stamp
    stamp_file = target / STAMP
    if stamp_file.exists() and stamp_file.read_text(encoding="utf-8") == stamp:
        return
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
    colors = {
        "icon": tokens["@icon"],
        "accent": tokens["@icon_accent"],
        # Badge marks (+, -, x, check) are white in every theme: a dark mark
        # on the badge read as a hole against dark toolbars. Buttons and
        # other text on accent colours keep the theme's @on_accent.
        "on_accent": "#ffffff",
        "danger": tokens["@danger"],
    }
    folders = set()
    svgs = {}
    for name, spec in studio_icons.ICON_MAP.items():
        path = target / "icons" / icon_file(name)
        if path.parent not in folders:
            path.parent.mkdir(parents=True, exist_ok=True)
            folders.add(path.parent)
        if spec not in svgs:
            svgs[spec] = studio_icons.render_icon(spec, colors)
        path.write_text(svgs[spec], encoding="utf-8")
    (target / FULL_STYLE).write_text(style, encoding="utf-8")
    if active:
        shutil.copyfile(target / FULL_STYLE, target / "style.qss")
    else:
        (target / "style.qss").write_bytes(STUB_STYLE)
    stamp_file.write_text(stamp, encoding="utf-8")


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
    WARM_BATCH = 25
    _DECORATION = Qt.ItemDataRole.DecorationRole
    _UNKNOWN = object()
    _CHILD_POLISHED = QEvent.Type.ChildPolished
    _SHOW = QEvent.Type.Show

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
        self._png = False
        self._scanned = []
        self._names = {}
        self._base_names = {}
        self._compact_at = self.COMPACT_MIN
        self._ours = {}
        self._reference_table = None
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
        self._png = (icons_dir / "png" / ".done").exists()
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
        self._icons_dir = icons_dir
        self._png = (icons_dir / "png" / ".done").exists()
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

    def _rethemed(self, icon):
        """The current theme's version of one of our icons (None if `icon`
        is not one of ours, e.g. the application replaced it since)."""
        name = self._ours.get(icon.cacheKey())
        return None if name is None else self._icon(name)

    def use_pngs(self, icons_dir):
        """The active theme's PNGs are ready: icons handed out from now on
        use them. Icons already shown keep their (rendered) SVG versions."""
        if self._theme is not None and icons_dir == self._icons_dir and not self._png:
            self._png = True
            self._icons = {}

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
        self._watched = {action: recheck for action, recheck in self._watched.items() if alive(action)}
        for table in (self._stacks, self._menus, self._models):
            for key in [key for key, (obj, _slot) in table.items() if not alive(obj)]:
                del table[key]
        self._names = dict(self._base_names)
        self._names.update(dict.fromkeys(self._ours))
        self._compact_at = max(self.COMPACT_MIN, 2 * (len(self._scanned) + len(self._swapped)))

    def _filter(self, obj):
        obj.installEventFilter(self)
        self._filtered.append(obj)

    def eventFilter(self, watched, event):  # pylint: disable=invalid-name
        if event.type() == self._SHOW and isinstance(watched, QMenu):
            self._menu_shown(watched)
        elif event.type() == self._CHILD_POLISHED:
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
            table = self._reference()
            # Pixmap-based icons (symbol previews, colour swatches, legend
            # items) list their pixmap sizes; fingerprinting them would
            # PNG-encode every pixmap. Only the few built-in PNG icons share
            # such a signature, so anything else is not ours to replace.
            signature = self._signature(icon)
            if signature and signature not in self._png_signatures:
                name = None
            else:
                name = table.get(self._digest(icon))
            self._names[key] = name
        if name is None:
            return None
        return self._icon(name)

    def _icon(self, name):
        """Our icon for a QGIS icon name, in the active theme."""
        if name not in self._icons:
            if self._png:
                ours = QIcon()
                for size in PNG_SIZES:
                    ours.addFile(str(png_path(self._icons_dir, name, size)), QSize(size, size))
            else:
                ours = QIcon(str(self._icons_dir / icon_file(name)))
            self._icons[name] = ours
            # Never examine our own icons again.
            self._names[ours.cacheKey()] = None
            self._ours[ours.cacheKey()] = name
        return self._icons[name]

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
        elif isinstance(widget, QMenu):
            self._hook_menu(widget)
        elif isinstance(widget, (QToolBar, QMenuBar)):
            for action in widget.actions():
                self._swap(action, None, None, deferred)
        elif isinstance(widget, QAbstractButton):
            self._swap(widget, None, None, deferred)
        elif isinstance(widget, QListWidget):
            self._rows(widget, "row", deferred)
        elif isinstance(widget, QComboBox):
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

    def _hook_menu(self, menu):
        """Swap a menu's icons right before it opens, not at startup. The
        Show event comes after every aboutToShow handler, so actions that
        QGIS (re)creates there are covered too."""
        if id(menu) in self._menus:
            return
        self._filter(menu)
        self._menus[id(menu)] = (menu, None)

    def _menu_shown(self, menu):
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
        for stacked, current_changed in self._stacks.values():
            if not sip.isdeleted(stacked):
                stacked.currentChanged.disconnect(current_changed)
        self._stacks = {}
        self._menus = {}
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
        "Premium": "premium",
        "Web": "web",
        "Pro Light": "pro",
        "Dark": "dark",
        "Light Orange": "light_orange",
        "QGIS Light": "qgis_light",
    }
    # Former display names -> current ones (kept so saved settings follow).
    RENAMED = {"Studio Pro": "Studio Pro Light"}

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
        self._rendering = set()
        self._relay = _Relay()
        self._relay.pngs_ready.connect(self._icons.use_pngs)
        self._labels = ToolbarLabels()
        self._labels_action = None
        self._extra_tokens = {}
        self._dock_icon_sizes = {}

    @staticmethod
    def theme_target(name):
        return Path(QgsApplication.userThemesFolder()) / f"Studio {name}"

    def initGui(self):
        # QGIS applies the configured theme as soon as it is registered.
        # Install palette and font first so that single stylesheet pass
        # already sees them (no second, full repolish at startup).
        settings = QgsSettings()
        configured = settings.value("UI/UITheme", "", type=str)
        for old_name, new_name in self.RENAMED.items():
            old_target = Path(QgsApplication.userThemesFolder()) / old_name
            if (old_target / STAMP).exists():
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
        # The main menu is one point larger than the UI font, so it reads as
        # the top level. The size goes into the theme stylesheet (a widget
        # stylesheet on the bar would give every menu, all children of the
        # bar, a slower style chain of its own) and into the build stamp, so
        # a changed QGIS font size rebuilds the themes.
        menu_size = self.iface.mainWindow().menuBar().font().pointSizeF() + MENU_BAR_EXTRA_PT
        self._extra_tokens = {"@menu_font_size": f"{menu_size:g}pt"}
        self._shared_stamp = (
            BUILD_FORMAT + build_stamp(shared_sources()) + f"|menu{menu_size:g}"
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
        # When the configured theme is applied later, themeChanged syncs;
        # syncing now would undo the preparation above.
        if QgsApplication.themeName() in self._studio_themes():
            self._sync()
        QTimer.singleShot(2000, lambda: self._start(self._build_pending, pending))

    def _build(self, name, active=False):
        """Build one theme (no-op when up to date); False if it failed."""
        with self._locks[name]:
            try:
                build_theme(
                    self.THEMES[name], self.theme_target(name), self._shared_stamp, active,
                    self._extra_tokens,
                )
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
        """Run `target` in a worker thread that unload() waits for."""
        if self._stop.is_set():
            return
        self._threads = [thread for thread in self._threads if thread.is_alive()]
        thread = threading.Thread(target=target, args=args, daemon=True)
        self._threads.append(thread)
        thread.start()

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
        if self._labels_action is not None:
            self.iface.viewMenu().removeAction(self._labels_action)
            self._labels_action.deleteLater()
            self._labels_action = None
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
        if self._active is None:
            return
        size = QSize(DOCK_ICON_SIZE, DOCK_ICON_SIZE)
        for dock in self.iface.mainWindow().findChildren(QDockWidget):
            for toolbar in dock.findChildren(QToolBar):
                if toolbar.iconSize().width() < DOCK_ICON_SIZE:
                    self._dock_icon_sizes.setdefault(toolbar, toolbar.iconSize())
                    toolbar.setIconSize(size)

    # ---- Toolbar labels ---------------------------------------------------

    def _labels_enabled(self):
        return self._labels_action is not None and self._labels_action.isChecked()

    def _label_color(self):
        """A third of the way from the dimmed to the normal text colour:
        readable at 9 px, still quieter than the icons."""
        dim, text = parse_color(self._tokens["@text_dim"]), parse_color(self._tokens["@text"])
        r, g, b, a = (x + (y - x) / 3 for x, y in zip(dim, text))
        return QColor(round(r), round(g), round(b), round(a * 255))

    def _apply_labels(self):
        """Attach (or update) the toolbar labels for the active theme."""
        if self._active is None or not self._labels_enabled():
            self._labels.detach()
            return
        self._labels.set_color(self._label_color())
        self._labels.attach(self.iface.mainWindow(), self._label_color())

    def _toggle_labels(self, checked):
        QgsSettings().setValue(LABELS_SETTING, checked)
        self._apply_labels()

    def _label_designer(self, designer):
        if self._active is not None and self._labels_enabled():
            self._labels.attach(designer.window(), self._label_color())

    def _prerender(self, icons_dir):
        """Pre-render the theme's icons as PNGs in a worker thread, off
        startup's critical path; icons requested afterwards use them."""
        if icons_dir in self._rendering or (icons_dir / "png" / ".done").exists():
            return
        self._rendering.add(icons_dir)

        def work():
            if prerender_pngs(icons_dir, self._stop):
                self._relay.pngs_ready.emit(icons_dir)

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
