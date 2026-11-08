"""The Layers panel's search field and 'List by' row (while a Studio theme
is shown).

Above the layer tree: a search field, QGIS's own layer name filter
(QgsLayerTreeProxyModel.setFilterText), and a row of large buttons for
QGIS's own legend filters, which the row only presses:

- Drawing order: the whole tree; lit while none of the next three is on,
  and turns them off.
- Visible in map: QGIS's "Filter Legend by Map Content".
- By expression: QGIS's "Filter legend by expression" button (its dialog
  and its menu: edit, clear).
- Broken layers: QGIS's "Show Broken Layers Only".
- Private layers: QGIS's "Show Private Layers" (adds hidden layers; a
  toggle of its own, apart from the others).

QGIS's Filter Legend menu button and expression button in the panel's
toolbar are hidden while the row shows them, and come back with QGIS's
own look. Filters combine as in QGIS; the caption names those on.
"""
from qgis.core import QgsApplication
from qgis.gui import QgsFilterLineEdit
from qgis.PyQt import sip
from qgis.PyQt.QtCore import QCoreApplication, QEvent, QSize, Qt
from qgis.PyQt.QtGui import QAction, QFont, QIcon
from qgis.PyQt.QtWidgets import QDockWidget, QHBoxLayout, QLabel, QToolBar, QToolButton, QVBoxLayout, QWidget


def tr(text):
    return QCoreApplication.translate("QgisStudioThemes", text)


def qgis_text(text):
    """A QGIS app string as the user sees it (translated)."""
    return QCoreApplication.translate("QgisApp", text)


def plain(text):
    return text.replace("&", "").strip().lower()


# (key, ICON_MAP name, tooltip, caption)
BUTTONS = (
    ("order", "mIconLayerTree.svg", "List by drawing order (all layers)", "By drawing order"),
    ("map", "mLayoutItemMap.svg", "Filter Legend by Map Content", "Visible in map"),
    ("expression", "mIconExpressionFilter.svg", "Filter Legend by Expression", "By expression"),
    ("broken", "mActionUnlink.svg", "Show Broken Layers Only", "Broken layers only"),
    ("private", "mActionHideAllLayers.svg", "Show Private Layers", "With private layers"),
)
# The texts of QGIS's Filter Legend menu entries (English, as in QGIS).
MENU_TEXTS = {
    "map": "Filter Legend by Map Content",
    "private": "Show Private Layers",
    "broken": "Show Broken Layers Only",
}
# The row's icons: the size of the panel trees' (20 px at the default
# icon size, a step larger per larger setting).
ICON_SIZE = 20


class LayersListBy:
    """See the module docstring. attach() is safe to repeat (a theme
    switch re-themes the icons); detach() gives QGIS its panel back."""

    def __init__(self, iface, hub, icons):
        self.iface = iface
        self._hub = hub
        self._icons = icons
        self._panel = None
        self._search = None
        self._buttons = {}
        self._actions = {}
        self._caption = None
        # QGIS's own controls: key -> QAction (menu entries) or the
        # expression QToolButton; and the toolbar actions hidden.
        self._sources = {}
        self._hidden = []
        self._connections = []

    # ---- QGIS's controls ----------------------------------------------------

    def _find(self):
        """(view, body layout, toolbar) of the Layers panel, or None."""
        view = self.iface.layerTreeView()
        if view is None or sip.isdeleted(view):
            return None
        body = view.parentWidget()
        dock = body
        while dock is not None and not isinstance(dock, QDockWidget):
            dock = dock.parentWidget()
        if body is None or dock is None or body.layout() is None:
            return None
        toolbar = next((bar for bar in body.findChildren(QToolBar) if bar.parentWidget() is body), None)
        return view, body.layout(), toolbar

    def _find_sources(self, toolbar):
        """QGIS's Filter Legend menu entries and expression button, and the
        toolbar actions holding them (to hide)."""
        sources, holders = {}, []
        if toolbar is None:
            return sources, holders
        for action in toolbar.actions():
            widget = toolbar.widgetForAction(action)
            if widget is None:
                continue
            if widget.inherits("QgsLegendFilterButton"):
                sources["expression"] = widget
                holders.append(action)
                continue
            menu = widget.menu() if isinstance(widget, QToolButton) else None
            entries = [entry for entry in menu.actions() if entry.isCheckable()] if menu is not None else []
            found = {}
            for key, text in MENU_TEXTS.items():
                wanted = {plain(text), plain(qgis_text(text))}
                match = next((entry for entry in entries if plain(entry.text()) in wanted), None)
                if match is not None:
                    found[key] = match
            if "map" in found:
                sources.update(found)
                holders.append(action)
        return sources, holders

    # ---- Building -----------------------------------------------------------

    def attach(self):
        found = self._find()
        if found is None:
            return
        view, layout, toolbar = found
        if self._panel is not None and not sip.isdeleted(self._panel):
            self._theme_icons()
            return
        self._sources, holders = self._find_sources(toolbar)
        panel = QWidget()
        panel.setObjectName("studioListByPanel")
        column = QVBoxLayout(panel)
        column.setContentsMargins(8, 2, 8, 4)
        column.setSpacing(6)
        search = QgsFilterLineEdit(panel)
        search.setObjectName("studioLayerSearch")
        search.setShowSearchIcon(True)
        search.setPlaceholderText(tr("Search layers"))
        proxy = view.proxyModel() if hasattr(view, "proxyModel") else None
        if proxy is not None:
            search.textChanged.connect(proxy.setFilterText)
            column.addWidget(search)
            self._search = search
        else:
            search.deleteLater()
        row = QWidget(panel)
        row.setObjectName("studioListBy")
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(2)
        for key, name, tip, _caption in BUTTONS:
            if key != "order" and key not in self._sources:
                continue
            if key == "private":
                line.addSpacing(6)
            action = QAction(row)
            action.setCheckable(True)
            action.setToolTip(tr(tip))
            button = QToolButton(row)
            button.setObjectName("studioListByButton")
            button.setAutoRaise(True)
            button.setDefaultAction(action)
            action.triggered.connect(lambda _checked=False, key=key: self._pressed(key))
            if key == "expression":
                # QGIS's menu of the button (edit, clear the expression) on
                # a right-click: no drop-down arrow, so the row stays a row
                # of equal icons.
                menu = self._sources[key].menu()
                if menu is not None:
                    action.setToolTip(tr(tip) + " " + tr("(right-click to edit or clear)"))
                    button.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
                    button.customContextMenuRequested.connect(
                        lambda pos, button=button, menu=menu: menu.exec(button.mapToGlobal(pos)))
            line.addWidget(button)
            self._buttons[key] = button
            self._actions[key] = action
        caption = QLabel(row)
        caption.setObjectName("studioListByCaption")
        # Small capitals a step below the panel's text, like the ribbon's
        # group names.
        font = QFont(caption.font())
        font.setPointSizeF(max(6.0, font.pointSizeF() - 1.5))
        caption.setFont(font)
        line.addSpacing(8)
        line.addWidget(caption, 1)
        self._caption = caption
        if self._sources:
            column.addWidget(row)
        else:
            # QGIS's filters not found (another QGIS version): the search
            # field alone, rather than a row of one button.
            row.hide()
            self._buttons, self._actions, holders = {}, {}, []
        if column.count() == 0:
            panel.deleteLater()
            return
        layout.insertWidget(layout.indexOf(view), panel)
        self._panel = panel
        for action in holders:
            if action.isVisible():
                action.setVisible(False)
                self._hidden.append(action)
        # QGIS's state, whoever changes it (its menu, a project load...).
        for key, source in self._sources.items():
            signal = source.toggled
            signal.connect(self._update)
            self._connections.append((signal, self._update))
        expression = self._sources.get("expression")
        if expression is not None:
            self._hub.watch(expression, self, (QEvent.Type.EnabledChange,), lambda _obj, _event: self._update())
        self._theme_icons()
        self.resize()
        self._update()

    def _theme_icons(self):
        for key, name, _tip, _caption in BUTTONS:
            action = self._actions.get(key)
            if action is None:
                continue
            action.setIcon(QIcon())
            if self._icons is None or not self._icons.adopt(action, name):
                action.setIcon(QgsApplication.getThemeIcon("/" + name))

    def resize(self):
        """Icons a step larger per larger QGIS icon size, like the trees."""
        if self._panel is None or sip.isdeleted(self._panel):
            return
        step = self._icons._size_step() if self._icons is not None else 0  # pylint: disable=protected-access
        size = QSize(ICON_SIZE + step, ICON_SIZE + step)
        for button in self._buttons.values():
            button.setIconSize(size)

    # ---- State --------------------------------------------------------------

    def _on(self, key):
        source = self._sources.get(key)
        return source is not None and not sip.isdeleted(source) and source.isChecked()

    def _pressed(self, key):
        """Press QGIS's control (the row then shows QGIS's state)."""
        if key == "order":
            for other in ("map", "expression", "broken"):
                if self._on(other):
                    self._toggle(other)
        else:
            self._toggle(key)
        self._update()

    def _toggle(self, key):
        source = self._sources.get(key)
        if source is None or sip.isdeleted(source):
            return
        if isinstance(source, QAction):
            source.trigger()
        else:
            # The expression button: a click asks for an expression when
            # it has none (QGIS's behaviour).
            source.click()

    def _update(self, *_args):
        if self._caption is None or sip.isdeleted(self._caption):
            return
        filters = [key for key in ("map", "expression", "broken") if self._on(key)]
        for key, action in self._actions.items():
            action.setChecked(not filters if key == "order" else self._on(key))
        expression = self._sources.get("expression")
        if "expression" in self._actions and expression is not None and not sip.isdeleted(expression):
            self._actions["expression"].setEnabled(expression.isEnabled())
        captions = dict((key, caption) for key, _name, _tip, caption in BUTTONS)
        shown = [captions[key] for key in filters] or [captions["order"]]
        if self._on("private"):
            shown.append(captions["private"])
        self._caption.setText(" · ".join(tr(text) for text in shown).upper())

    # ---- Restoring ------------------------------------------------------------

    def detach(self):
        for signal, slot in self._connections:
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass
        self._connections = []
        expression = self._sources.get("expression")
        if expression is not None and not sip.isdeleted(expression):
            self._hub.unwatch(expression, self)
        for action in self._hidden:
            if not sip.isdeleted(action):
                action.setVisible(True)
        self._hidden = []
        if self._search is not None and not sip.isdeleted(self._search):
            # QGIS shows no layer search: its filter goes with the field.
            self._search.clear()
        if self._panel is not None and not sip.isdeleted(self._panel):
            self._panel.hide()
            self._panel.setParent(None)
            self._panel.deleteLater()
        self._panel = None
        self._search = None
        self._caption = None
        self._buttons = {}
        self._actions = {}
        self._sources = {}

