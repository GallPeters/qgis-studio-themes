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
from qgis.PyQt.QtCore import QFile, Qt, QTimer, qVersion
from qgis.PyQt.QtGui import (
    QAction, QColor, QFont, QFontDatabase, QGuiApplication, QIcon, QImage, QPalette,
)
from qgis.PyQt.QtWidgets import QAbstractButton, QApplication, QListWidget, QTabBar

from . import studio_icons
from .studio_tokens import is_dark, parse_color, parse_tokens, render, resolve_tokens

PLUGIN_DIR = Path(__file__).parent
THEMES_DIR = PLUGIN_DIR / "themes"
SHARED_STYLE = THEMES_DIR / "style.qss"
SHARED_TOKENS = THEMES_DIR / "base.qss"
WIDGET_GLYPHS = THEMES_DIR / "icons"
FONTS_DIR = PLUGIN_DIR / "fonts"
STAMP = ".studio-build"
LOG_TAG = "Studio Themes"

# QGIS adds these rules to the main window's own stylesheet when it starts
# with a theme that is not registered yet (ours register a moment later).
# They paint the default theme's dark options sidebar and blue table
# selection, and as a widget stylesheet they beat the application one.
DEFAULT_THEME_RULES = re.compile(
    r"[^{}]*(?:mOptionsListWidget|mOptionsListFrame|mOptionsTreeView)[^{}]*\{[^{}]*\}"
    r"|\s*QTableView\s*\{[^{}]*\}"
)


def theme_sources(folder):
    """Every file a built theme depends on."""
    sources = [SHARED_STYLE, SHARED_TOKENS, THEMES_DIR / folder / "variables.qss",
               Path(studio_icons.__file__), Path(__file__)]
    sources += sorted(WIDGET_GLYPHS.glob("*.svg"))
    sources += sorted(studio_icons.GLYPHS_DIR.glob("*.svg"))
    return sources


def icon_file(name):
    """Override file for a QGIS icon name. Always SVG: QGIS's few .png icons
    are only replaced through IconSwapper (QGIS's own lookup keeps
    resolving those to its built-in PNGs)."""
    return Path(name).with_suffix(".svg")


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


def build_theme(folder, target):
    """Write the resolved stylesheet and all icons for one theme into
    `target`. Skipped when nothing changed since the last build, so
    startup costs only a few stat() calls."""
    sources = theme_sources(folder)
    stamp = build_stamp(sources)
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
        (role.Highlight, "@accent"), (role.HighlightedText, "@on_accent"),
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


class IconSwapper:
    """Replaces QGIS icons that were already created before the theme was
    active (main window toolbars, menus, panels). Icons created later come
    from the theme folder through QGIS's own lookup.

    Icons are identified by QIcon.cacheKey() first: getThemeIcon() caches
    one QIcon per name and every widget shares that instance. Icons loaded
    straight from Qt Designer .ui files are separate instances, so those
    fall back to comparing a 16px rendering against the built-in icon.
    Results are memoised per cacheKey. In the main window the rendering
    pass runs in small batches when the event loop is idle, so it never
    delays startup; the reference renderings are cached on disk."""

    PROPERTY = "_studioIconsTheme"
    RESOURCES = ":/images/themes/default/"
    BATCH = 40
    _UNKNOWN = object()

    def __init__(self, cache_file=None):
        self._cache_file = cache_file
        self._swapped = []
        self._watched = {}
        self._names = {}
        self._ours = {}
        self._pixels = None
        self._icons = {}
        self._pending = []
        self._theme = None
        self._icons_dir = None

    def apply(self, theme, icons_dir):
        self.restore()
        self._theme = theme
        self._icons = {}
        self._ours = {}
        self._names = {}
        self._icons_dir = icons_dir
        for name in studio_icons.ICON_MAP:
            self._names[QgsApplication.getThemeIcon(name).cacheKey()] = name
        for widget in QApplication.topLevelWidgets():
            self.apply_to(widget, deferred=True)
        if self._pending:
            QTimer.singleShot(0, self._drain)

    # ---- Identification ---------------------------------------------------

    @staticmethod
    def _fingerprint(icon):
        image = icon.pixmap(16, 16).toImage().convertToFormat(QImage.Format.Format_ARGB32)
        if image.isNull():
            return None
        bits = image.constBits()
        bits.setsize(image.sizeInBytes())
        return hashlib.sha1(bytes(bits)).hexdigest()

    def _reference(self):
        """Fingerprints of the built-in icons, cached on disk per QGIS/Qt
        build and screen scale (renderings depend on all three)."""
        if self._pixels is not None:
            return self._pixels
        key = f"{Qgis.version()}|{qVersion()}|{QApplication.instance().devicePixelRatio()}|" \
              f"{len(studio_icons.ICON_MAP)}"
        if self._cache_file is not None and self._cache_file.exists():
            try:
                cached = json.loads(self._cache_file.read_text(encoding="utf-8"))
                if cached.get("key") == key:
                    self._pixels = cached["fingerprints"]
                    return self._pixels
            except (OSError, ValueError):
                pass
        self._pixels = {}
        for name in studio_icons.ICON_MAP:
            # Check first: QIcon on a missing resource logs a Qt warning,
            # which QGIS surfaces in the message bar.
            if QFile.exists(self.RESOURCES + name):
                fingerprint = self._fingerprint(QIcon(self.RESOURCES + name))
                if fingerprint:
                    self._pixels.setdefault(fingerprint, name)
        if self._cache_file is not None:
            try:
                self._cache_file.write_text(
                    json.dumps({"key": key, "fingerprints": self._pixels}), encoding="utf-8"
                )
            except OSError:
                pass
        return self._pixels

    def _replacement(self, icon, render=True):
        """Our icon for `icon`, None if it has none, or _UNKNOWN when
        identifying it needs a rendering and `render` is False."""
        if icon.isNull():
            return None
        key = icon.cacheKey()
        name = self._names.get(key, self._UNKNOWN)
        if name is self._UNKNOWN:
            if not render:
                return self._UNKNOWN
            fingerprint = self._fingerprint(icon)
            name = self._reference().get(fingerprint) if fingerprint else None
            self._names[key] = name
        if name is None:
            return None
        if name not in self._icons:
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

    @staticmethod
    def _targets(root):
        """(owner, slot) for every icon in a widget tree: slot None is the
        owner's own icon, >= 0 a list row, < 0 a tab (-1 - index)."""
        widgets = [root] + root.findChildren(QAbstractButton) + root.findChildren(QListWidget) \
            + root.findChildren(QTabBar)
        actions = set(root.findChildren(QAction))
        for widget in widgets:
            actions.update(widget.actions())
        targets = [(action, None) for action in actions]
        for widget in widgets:
            if isinstance(widget, QAbstractButton):
                targets.append((widget, None))
            elif isinstance(widget, QListWidget):
                targets.extend((widget, row) for row in range(widget.count()))
            elif isinstance(widget, QTabBar):
                targets.extend((widget, -1 - index) for index in range(widget.count()))
        return targets

    @staticmethod
    def _icon_of(owner, slot):
        if slot is None:
            return owner.icon()
        if slot >= 0:
            return owner.item(slot).icon() if slot < owner.count() else QIcon()
        index = -1 - slot
        return owner.tabIcon(index) if index < owner.count() else QIcon()

    def _swap(self, owner, slot, render):
        if sip.isdeleted(owner):
            return
        icon = self._icon_of(owner, slot)
        new = self._replacement(icon, render)
        if new is self._UNKNOWN:
            self._pending.append((owner, slot))
            return
        if new is None:
            return
        if isinstance(owner, QAction):
            owner.setIcon(new)
            self._watch(owner)
            return
        self._swapped.append((owner, slot, icon))
        if slot is None:
            owner.setIcon(new)
        elif slot >= 0:
            owner.item(slot).setIcon(new)
        else:
            owner.setTabIcon(-1 - slot, new)

    def _drain(self):
        """Identify queued icons a batch at a time between events."""
        if self._theme is None:
            self._pending = []
            return
        batch, self._pending = self._pending[:self.BATCH], self._pending[self.BATCH:]
        for owner, slot in batch:
            self._swap(owner, slot, render=True)
        if self._pending:
            QTimer.singleShot(0, self._drain)

    def _watch(self, action):
        """QGIS re-sets some action icons from its cache later (for example
        Add Feature follows the active layer's geometry type); swap again
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

    def apply_to(self, root, deferred=False):
        """Swap icons in one widget tree; runs once per window."""
        if self._theme is None or sip.isdeleted(root):
            return
        if root.property(self.PROPERTY) == self._theme:
            return
        root.setProperty(self.PROPERTY, self._theme)
        for owner, slot in self._targets(root):
            self._swap(owner, slot, render=not deferred)

    def restore(self):
        self._theme = None
        self._pending = []
        for action, recheck in self._watched.items():
            if sip.isdeleted(action):
                continue
            action.changed.disconnect(recheck)
            builtin = self._builtin(action.icon())
            if builtin is not None:
                action.setIcon(builtin)
        self._watched = {}
        for owner, slot, icon in reversed(self._swapped):
            if sip.isdeleted(owner):
                continue
            if slot is None:
                owner.setIcon(icon)
            elif slot >= 0 and slot < owner.count():
                owner.item(slot).setIcon(icon)
            elif slot < 0 and -1 - slot < owner.count():
                owner.setTabIcon(-1 - slot, icon)
        self._swapped = []
        for widget in QApplication.topLevelWidgets():
            widget.setProperty(self.PROPERTY, None)


class QgisStudioThemesPlugin:
    """Registers the Studio themes and keeps the parts a stylesheet cannot
    reach (palette, font, icons, message bar) in sync with the active one."""

    # Display name (registered as "Studio <name>") -> folder under themes/
    THEMES = {
        "Premium": "premium",
        "Web": "web",
        "Pro": "pro",
        "Dark": "dark",
        "Light Orange": "light_orange",
        "QGIS Light": "qgis_light",
    }

    def __init__(self, iface):
        self.iface = iface
        self._connected = False
        self._active = None
        self._tokens = {}
        self._original_palette = QPalette(QApplication.palette())
        self._original_font = QFont(QApplication.font())
        self._icons = IconSwapper(
            Path(QgsApplication.userThemesFolder()) / ".studio-icon-fingerprints.json"
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
        configured = QgsSettings().value("UI/UITheme", "", type=str)
        if configured in self._studio_themes():
            self._prepare(configured)
        QgsApplication.instance().themeChanged.connect(self._sync)
        QGuiApplication.instance().focusWindowChanged.connect(self._on_focus_window)
        self.iface.messageBar().widgetAdded.connect(self._style_message_bar)
        self._connected = True
        for name, folder in self.THEMES.items():
            target = self.theme_target(name)
            try:
                build_theme(folder, target)
            except Exception as error:  # pylint: disable=broad-except
                QgsMessageLog.logMessage(
                    f"Could not build Studio {name}: {error}", LOG_TAG, Qgis.MessageLevel.Critical
                )
                continue
            QgsApplication.applicationThemeRegistry().addTheme(f"Studio {name}", target.as_posix())
        # When the configured theme is applied later, themeChanged syncs;
        # syncing now would undo the preparation above.
        if QgsApplication.themeName() in self._studio_themes():
            self._sync()

    def unload(self):
        if self._connected:
            QgsApplication.instance().themeChanged.disconnect(self._sync)
            QGuiApplication.instance().focusWindowChanged.disconnect(self._on_focus_window)
            self.iface.messageBar().widgetAdded.disconnect(self._style_message_bar)
            self._connected = False
        self._deactivate()
        for name in self.THEMES:
            QgsApplication.applicationThemeRegistry().removeTheme(f"Studio {name}")

    # ---- Theme state ------------------------------------------------------

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
            # Switched at runtime: QGIS already polished every widget with
            # the previous palette, and Qt's stylesheet engine keeps each
            # styled widget's palette from its first polish. Clear the
            # stylesheet, install the palette, then re-apply.
            # The main window's own stylesheet is cleared too, for the same
            # reason.
            app = QApplication.instance()
            window = self.iface.mainWindow()
            sheet, window_sheet = app.styleSheet(), window.styleSheet()
            window.setStyleSheet("")
            app.setStyleSheet("")
            self._prepare(theme, window_sheet)
            app.setStyleSheet(sheet)
        self._active = theme
        name = studio[theme][0]
        self._icons.apply(theme, self.theme_target(name) / "icons")
        self._style_message_bar()

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

    def _on_focus_window(self, window):
        if self._active is None or window is None:
            return
        widget = QApplication.activeWindow() or QApplication.activePopupWidget()
        if widget is not None:
            self._icons.apply_to(widget)

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
