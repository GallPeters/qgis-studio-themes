from qgis.core import QgsApplication
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QGuiApplication
from pathlib import Path


THEMES_DIR = Path(__file__).parent / "themes"
# Single stylesheet shared by every theme; only variables.qss differs.
SHARED_STYLE = THEMES_DIR / "style.qss"


def install_shared_style(theme_dir):
    """QGIS only loads style.qss from inside a theme folder, so copy the
    shared stylesheet there (rewritten only when it has changed)."""
    target = theme_dir / "style.qss"
    style = SHARED_STYLE.read_text(encoding="utf-8")
    if not target.exists() or target.read_text(encoding="utf-8") != style:
        target.write_text(style, encoding="utf-8")

class QgisStudioThemesPlugin:
    """
    QGIS theme plugin sample
    """

    # Display name (registered as "Studio <name>") -> folder under themes/
    THEMES = {
        "Premium": "premium",
        "Web": "web",
        "Pro": "pro",
        "Dark": "dark",
        "Light Orange": "light_orange",
        "QGIS Light": "qgis_light",
    }

    # Themes that must force the Qt palette colour scheme so unstyled /
    # native widgets follow the stylesheet even when the desktop is in
    # the opposite mode (e.g. a light theme on a dark desktop).
    LIGHT_THEMES = frozenset({"Studio Light Orange", "Studio QGIS Light"})
    DARK_THEMES = frozenset(
        {"Studio Premium", "Studio Web", "Studio Pro", "Studio Dark"}
    )

    def __init__(self, iface):
        """init"""
        self._theme_signal_connected = False

    def initGui(self):
        """startup"""
        for name, folder in self.THEMES.items():
            theme_dir = THEMES_DIR / folder
            install_shared_style(theme_dir)
            # Forward slashes: QGIS substitutes the folder for @theme_path
            # inside url(), where Windows backslashes would break parsing.
            QgsApplication.applicationThemeRegistry().addTheme(
                f'Studio {name}', theme_dir.as_posix()
            )
        app = QgsApplication.instance()
        if app is not None:
            app.themeChanged.connect(self._sync_color_scheme)
            self._theme_signal_connected = True
        self._sync_color_scheme()

    def unload(self):
        """teardown"""
        app = QgsApplication.instance()
        if self._theme_signal_connected and app is not None:
            app.themeChanged.disconnect(self._sync_color_scheme)
            self._theme_signal_connected = False
        self._set_color_scheme(Qt.ColorScheme.Unknown)
        for name in self.THEMES:
            QgsApplication.applicationThemeRegistry().removeTheme(f'Studio {name}')

    def _sync_color_scheme(self):
        """Pin the Qt colour scheme to the active Studio theme so the
        desktop's light/dark mode never bleeds through, and hand the
        choice back to the system for non-Studio themes."""
        theme = QgsApplication.themeName()
        if theme in self.LIGHT_THEMES:
            self._set_color_scheme(Qt.ColorScheme.Light)
        elif theme in self.DARK_THEMES:
            self._set_color_scheme(Qt.ColorScheme.Dark)
        else:
            self._set_color_scheme(Qt.ColorScheme.Unknown)

    @staticmethod
    def _set_color_scheme(scheme):
        hints = QGuiApplication.styleHints()
        if hasattr(hints, "setColorScheme"):  # requires Qt >= 6.8
            hints.setColorScheme(scheme)
