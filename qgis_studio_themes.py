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
from pathlib import Path

from qgis.core import Qgis, QgsApplication, QgsMessageLog, QgsSettings
from qgis.PyQt import sip
from qgis.PyQt.QtCore import (
    QByteArray, QDataStream, QEvent, QFile, QIODevice, QObject, QSize, Qt, QTimer, qVersion,
)
from qgis.PyQt.QtGui import (
    QAction, QColor, QFont, QFontDatabase, QGuiApplication, QIcon, QImage, QPainter, QPalette,
)
from qgis.PyQt.QtSvg import QSvgRenderer
from qgis.PyQt.QtWidgets import (
    QAbstractButton, QApplication, QComboBox, QListWidget, QMenu, QMenuBar, QStackedWidget,
    QTabBar, QToolBar, QToolButton, QWidget,
)

from . import studio_icons
from .studio_tokens import is_dark, parse_color, parse_tokens, render, resolve_tokens

PLUGIN_DIR = Path(__file__).parent
THEMES_DIR = PLUGIN_DIR / "themes"
SHARED_STYLE = THEMES_DIR / "style.qss"
SHARED_TOKENS = THEMES_DIR / "base.qss"
WIDGET_GLYPHS = THEMES_DIR / "icons"
FONTS_DIR = PLUGIN_DIR / "fonts"
STAMP = ".studio-build"
FULL_STYLE = "style.full.qss"
# What QGIS loads for every Studio theme except the configured one (see
# QgisStudioThemesPlugin._select_style): a runtime switch then costs QGIS
# a near-empty pass, and the plugin applies the real stylesheet once,
# after installing the palette.
STUB_STYLE = "/* Studio theme: the plugin applies the stylesheet. */\n"
LOG_TAG = "Studio Themes"

# QGIS adds these rules to the main window's own stylesheet when it starts
# with a theme that is not registered yet (ours register a moment later).
# They paint the default theme's dark options sidebar and blue table
# selection, and as a widget stylesheet they beat the application one.
DEFAULT_THEME_RULES = re.compile(
    r"[^{}]*(?:mOptionsListWidget|mOptionsListFrame|mOptionsTreeView)[^{}]*\{[^{}]*\}"
    r"|\s*QTableView\s*\{[^{}]*\}"
)


def shared_sources():
    """Files every built theme depends on (one stat() each per startup)."""
    sources = [SHARED_STYLE, SHARED_TOKENS, Path(studio_icons.__file__), Path(__file__)]
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
    return icons_dir / "png" / Path(name).with_suffix("") / f"{size}.png"


def render_pngs(icons_dir, name):
    """Pre-render one icon at the common sizes: decoding a small PNG is
    about 2.5x cheaper than drawing the SVG the first time it is shown."""
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


def build_theme(folder, target, shared_stamp):
    """Write the resolved stylesheet and all icons for one theme into
    `target`. Skipped when nothing changed since the last build, so
    startup costs only a few stat() calls."""
    stamp = build_stamp([THEMES_DIR / folder / "variables.qss"]) + shared_stamp
    stamp_file = target / STAMP
    if stamp_file.exists() and stamp_file.read_text(encoding="utf-8") == stamp:
        return
    tokens = load_tokens(folder)
    # Forward slashes: Windows backslashes would break url() parsing.
    tokens["@theme_path"] = target.as_posix()
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
        "on_accent": tokens["@on_accent"],
        "danger": tokens["@danger"],
    }
    for name, spec in studio_icons.ICON_MAP.items():
        path = target / "icons" / icon_file(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(studio_icons.render_icon(spec, colors), encoding="utf-8")
    (target / FULL_STYLE).write_text(style, encoding="utf-8")
    (target / "style.qss").write_text(style, encoding="utf-8")
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
    _UNKNOWN = object()
    _CHILD_POLISHED = QEvent.Type.ChildPolished

    def __init__(self, cache_file=None):
        super().__init__()
        self._cache_file = cache_file
        self._swapped = []
        self._watched = {}
        self._models = {}
        self._filtered = []
        self._stacks = {}
        self._menus = {}
        self._png = False
        self._scanned = []
        self._names = {}
        self._ours = {}
        self._reference_table = None
        self._icons = {}
        self._pending = []
        self._theme = None
        self._icons_dir = None

    def apply(self, theme, icons_dir, main_window):
        self.restore()
        self._theme = theme
        self._icons = {}
        self._ours = {}
        self._names = {}
        self._icons_dir = icons_dir
        self._png = (icons_dir / "png" / ".done").exists()
        for name in studio_icons.ICON_MAP:
            self._names[QgsApplication.getThemeIcon(name).cacheKey()] = name
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

    def _filter(self, obj):
        obj.installEventFilter(self)
        self._filtered.append(obj)

    def eventFilter(self, watched, event):  # pylint: disable=invalid-name
        if event.type() == self._CHILD_POLISHED:
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

    def _reference(self):
        """Digests of the built-in icons, cached on disk per QGIS/Qt build."""
        if self._reference_table is not None:
            return self._reference_table
        names = "|".join(studio_icons.ICON_MAP)
        key = f"{Qgis.version()}|{qVersion()}|{hashlib.sha1(names.encode()).hexdigest()}"
        if self._cache_file is not None and self._cache_file.exists():
            try:
                cached = json.loads(self._cache_file.read_text(encoding="utf-8"))
                if cached.get("key") == key:
                    self._reference_table = cached["digests"]
                    return self._reference_table
            except (OSError, ValueError):
                pass
        self._reference_table = {}
        for name in studio_icons.ICON_MAP:
            # Check first: QIcon on a missing resource logs a Qt warning,
            # which QGIS surfaces in the message bar.
            if QFile.exists(self.RESOURCES + name):
                self._reference_table.setdefault(self._digest(QIcon(self.RESOURCES + name)), name)
        if self._cache_file is not None:
            try:
                self._cache_file.write_text(
                    json.dumps({"key": key, "digests": self._reference_table}), encoding="utf-8"
                )
            except OSError:
                pass
        return self._reference_table

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
            name = self._reference().get(self._digest(icon))
            self._names[key] = name
        if name is None:
            return None
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
        if name is None or not QFile.exists(self.RESOURCES + name):
            return None
        return QIcon(self.RESOURCES + name)

    # ---- Applying ---------------------------------------------------------

    # Icon slots: (None, None) is the owner's own icon, ("row", i) a list
    # row, ("tab", i) a tab, ("item", i) a combo box item.
    @staticmethod
    def _get(owner, kind, index):
        if kind is None:
            return owner.icon()
        if index >= owner.count():
            return QIcon()
        if kind == "row":
            return owner.item(index).icon()
        if kind == "tab":
            return owner.tabIcon(index)
        return owner.itemIcon(index)

    @staticmethod
    def _set(owner, kind, index, icon):
        if kind is None:
            owner.setIcon(icon)
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
        they become current."""
        if self._theme is None or sip.isdeleted(root) or root.property(self.PROPERTY) == self._theme:
            return
        self._mark(root)
        stack = [root]
        while stack:
            widget = stack.pop()
            self._visit(widget, deferred)
            if isinstance(widget, QStackedWidget):
                self._hook_stack(widget)
                page = widget.currentWidget()
                if page is not None and page.property(self.PROPERTY) != self._theme:
                    self._mark(page)
                    stack.append(page)
            else:
                stack.extend(widget.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly))

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

    def _hook_menu(self, menu):
        """Swap a menu's icons right before it opens, not at startup."""
        if id(menu) in self._menus:
            return

        def about_to_show(menu=menu):
            if self._theme is not None and not sip.isdeleted(menu):
                for action in menu.actions():
                    self._swap(action, None, None, False)

        menu.aboutToShow.connect(about_to_show)
        self._menus[id(menu)] = (menu, about_to_show)

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
        for stacked, current_changed in self._stacks.values():
            if not sip.isdeleted(stacked):
                stacked.currentChanged.disconnect(current_changed)
        self._stacks = {}
        for menu, about_to_show in self._menus.values():
            if not sip.isdeleted(menu):
                menu.aboutToShow.disconnect(about_to_show)
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
            if not sip.isdeleted(owner) and (kind is None or index < owner.count()):
                self._set(owner, kind, index, icon)
        self._swapped = []
        for root in self._scanned:
            if not sip.isdeleted(root):
                root.setProperty(self.PROPERTY, None)
        self._scanned = []


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
        self._connected = True
        shared_stamp = build_stamp(shared_sources())
        built = []
        for name, folder in self.THEMES.items():
            try:
                build_theme(folder, self.theme_target(name), shared_stamp)
                built.append(name)
            except Exception as error:  # pylint: disable=broad-except
                QgsMessageLog.logMessage(
                    f"Could not build Studio {name}: {error}", LOG_TAG, Qgis.MessageLevel.Critical
                )
        # Before registering: QGIS loads the configured theme's style.qss
        # as soon as that theme is registered.
        self._select_style(configured)
        for name in built:
            QgsApplication.applicationThemeRegistry().addTheme(
                f"Studio {name}", self.theme_target(name).as_posix()
            )
        # When the configured theme is applied later, themeChanged syncs;
        # syncing now would undo the preparation above.
        if QgsApplication.themeName() in self._studio_themes():
            self._sync()

    def unload(self):
        if self._connected:
            QgsApplication.instance().themeChanged.disconnect(self._sync)
            self.iface.messageBar().widgetAdded.disconnect(self._style_message_bar)
            self._connected = False
        self._deactivate()
        for name in self.THEMES:
            QgsApplication.applicationThemeRegistry().removeTheme(f"Studio {name}")

    # ---- Theme state ------------------------------------------------------

    def _select_style(self, active):
        """Give QGIS the real stylesheet only for `active` (the theme it
        will load at startup) and the placeholder for the others."""
        for name in self.THEMES:
            target = self.theme_target(name)
            full = target / FULL_STYLE
            if not full.exists():
                continue
            wanted = full.read_text(encoding="utf-8") if f"Studio {name}" == active else STUB_STYLE
            current = target / "style.qss"
            if not current.exists() or current.read_text(encoding="utf-8") != wanted:
                current.write_text(wanted, encoding="utf-8")

    def _studio_themes(self):
        return {f"Studio {name}": (name, folder) for name, folder in self.THEMES.items()}

    def _prepare(self, theme, window_sheet=None):
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
        sheet = window.styleSheet() if window_sheet is None else window_sheet
        cleaned = DEFAULT_THEME_RULES.sub("", sheet)
        if cleaned != sheet and self._main_window_sheet is None:
            self._main_window_sheet = sheet
        if cleaned != sheet or window_sheet is not None:
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
        if self._prepared != theme:
            # Switched at runtime: QGIS applied the near-empty placeholder,
            # so its pass was cheap. Qt keeps palette copies on widgets that
            # were styled under the previous theme; clearing the stylesheet
            # drops them, then the palette goes in before the real
            # stylesheet so every widget is polished with the right colours.
            # The main window's own stylesheet is cleared for the same reason.
            app = QApplication.instance()
            window = self.iface.mainWindow()
            window_sheet = window.styleSheet()
            window.setStyleSheet("")
            app.setStyleSheet("")
            self._prepare(theme, window_sheet)
            full = self.theme_target(studio[theme][0]) / FULL_STYLE
            app.setStyleSheet(full.read_text(encoding="utf-8"))
            self._select_style(theme)
        self._active = theme
        name = studio[theme][0]
        icons_dir = self.theme_target(name) / "icons"
        self._icons.apply(theme, icons_dir, self.iface.mainWindow())
        self._style_message_bar()
        self._prerender(theme, icons_dir)

    def _prerender(self, theme, icons_dir):
        """Pre-render the theme's icons as PNGs in idle time, a few per
        event-loop pass; used from the next start (or theme switch) on."""
        done = icons_dir / "png" / ".done"
        if done.exists():
            return
        queue = list(studio_icons.ICON_MAP)

        def step():
            if self._active != theme:
                return
            for name in queue[:6]:
                try:
                    render_pngs(icons_dir, name)
                except OSError:
                    return
            del queue[:6]
            if queue:
                QTimer.singleShot(0, step)
            else:
                done.write_text("", encoding="utf-8")

        QTimer.singleShot(3000, step)

    def _deactivate(self):
        if self._active is None and self._prepared is None:
            return
        self._active = None
        self._prepared = None
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
