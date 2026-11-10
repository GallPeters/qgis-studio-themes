"""The Layers panel's additions (while a Studio theme is shown).

- A search field at the top of the panel: QGIS's own layer name filter
  (QgsLayerTreeProxyModel.setFilterText).
- List by Data Source, a button at the end of QGIS's own toolbar row:
  while it is on, the layer tree gives way to the project's layers grouped
  by where their data comes from (a GeoPackage, a shapefile, a PostgreSQL
  or Oracle database, a web service...). Each layer keeps its checkbox
  (QGIS's visibility), symbol and legend; clicking a layer makes it the
  current layer, double-clicking opens its properties and right-clicking
  shows QGIS's own layer menu. The drawing order is never changed; turning
  the button off shows QGIS's tree again.
- Layer names in the regular weight (QGIS draws them bold); groups stay
  bold.

QGIS's toolbar keeps its own buttons in its own order; everything is
removed and QGIS's look restored with the theme.
"""
import os
from pathlib import Path

from qgis.core import QgsApplication, QgsDataSourceUri, QgsLayerTreeNode, QgsProject, QgsProviderRegistry
from qgis.gui import QgsFilterLineEdit
from qgis.PyQt import sip
from qgis.PyQt.QtCore import QCoreApplication, Qt, QTimer
from qgis.PyQt.QtGui import QAction, QFont, QIcon
from qgis.PyQt.QtWidgets import QDockWidget, QToolBar, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget


def tr(text):
    return QCoreApplication.translate("QgisStudioThemes", text)


# The List by Data Source button's icon (studio_icons.ICON_MAP).
SOURCE_ICON = "studio/listByDataSource.svg"
# Files by extension: (kind shown, QGIS icon name).
FILE_KINDS = {
    ".gpkg": ("GeoPackage", "mIconGeoPackage.svg"),
    ".shp": ("Shapefile", "mIconFile.svg"),
    ".sqlite": ("SpatiaLite", "mIconSpatialite.svg"),
    ".db": ("SpatiaLite", "mIconSpatialite.svg"),
    ".geojson": ("GeoJSON", "mIconFile.svg"),
    ".json": ("GeoJSON", "mIconFile.svg"),
    ".kml": ("KML", "mIconFile.svg"),
    ".gdb": ("File Geodatabase", "mIconDbSchema.svg"),
    ".csv": ("Delimited Text", "mIconDelimitedText.svg"),
    ".txt": ("Delimited Text", "mIconDelimitedText.svg"),
    ".tif": ("GeoTIFF", "mIconRaster.svg"),
    ".tiff": ("GeoTIFF", "mIconRaster.svg"),
}
# Databases by provider key: (kind shown, QGIS icon name).
DATABASES = {
    "postgres": ("PostgreSQL", "mIconPostgis.svg"),
    "oracle": ("Oracle", "mIconOracle.svg"),
    "mssql": ("SQL Server", "mIconMssql.svg"),
    "hana": ("SAP HANA", "mIconHana.svg"),
    "spatialite": ("SpatiaLite", "mIconSpatialite.svg"),
}
WEB = {"wms", "wfs", "wcs", "arcgisfeatureserver", "arcgismapserver", "vectortile", "xyzvectortiles",
       "oapif", "sensorthings", "stac", "WFS", "virtualraster"}


def source_of(layer):
    """(key, label, QGIS icon name, tooltip) of where `layer` reads from."""
    provider = layer.providerType()
    source = layer.source()
    if provider in DATABASES and provider != "spatialite":
        kind, icon = DATABASES[provider]
        uri = QgsDataSourceUri(source)
        name = uri.database() or uri.service() or ""
        host = uri.host()
        label = f"{kind} · {name}" + (f" @ {host}" if host else "")
        return f"db:{provider}:{host}:{name}", label, icon, label
    try:
        parts = QgsProviderRegistry.instance().decodeUri(provider, source) or {}
    except Exception:  # pylint: disable=broad-except
        parts = {}
    path = parts.get("path") or ""
    if path:
        suffix = Path(path).suffix.lower()
        kind, icon = FILE_KINDS.get(suffix, (suffix[1:].upper() if suffix else tr("File"), "mIconFile.svg"))
        return "file:" + os.path.normcase(os.path.abspath(path)), f"{kind} · {Path(path).name}", icon, path
    if provider == "memory":
        return "memory", tr("Temporary Scratch Layers"), "mIconMemory.svg", tr("Layers kept in memory")
    if provider in WEB or "url=" in source:
        url = QgsDataSourceUri(source).param("url") or parts.get("url") or ""
        host = url.split("//", 1)[-1].split("/", 1)[0] if url else provider
        return f"web:{host}", f"{tr('Web service')} · {host}", "mIconWms.svg", url or source
    return f"other:{provider}", provider or tr("Other"), "mIconFile.svg", source


class LayersPanel:
    """See the module docstring. attach() is safe to repeat (a theme
    switch re-themes the icons); detach() gives QGIS its panel back."""

    def __init__(self, iface, hub, icons):
        self.iface = iface
        self._hub = hub
        self._icons = icons
        self._view = None
        self._top = None
        self._search = None
        self._tree = None
        self._toolbar = None
        self._action = None
        self._model = None
        self._layer_font = None
        self._connections = []
        self._collapsed = set()
        self._building = False
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(60)
        self._timer.timeout.connect(self._rebuild)

    # ---- Building -----------------------------------------------------------

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

    def attach(self):
        found = self._find()
        if found is None:
            return
        view, layout, toolbar = found
        if self._top is not None and not sip.isdeleted(self._top):
            self._theme_icons()
            return
        self._view = view
        # The search field, at the very top of the panel.
        top = QWidget()
        top.setObjectName("studioLayerSearchPanel")
        column = QVBoxLayout(top)
        column.setContentsMargins(8, 4, 8, 2)
        search = QgsFilterLineEdit(top)
        search.setObjectName("studioLayerSearch")
        search.setShowSearchIcon(True)
        search.setPlaceholderText(tr("Search layers"))
        search.textChanged.connect(self._filter)
        column.addWidget(search)
        layout.insertWidget(0, top)
        self._top, self._search = top, search
        # The layers by data source, in the tree's place while shown.
        tree = QTreeWidget()
        tree.setObjectName("studioSourceTree")
        tree.setHeaderHidden(True)
        tree.setIconSize(view.iconSize())
        tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        tree.customContextMenuRequested.connect(self._menu)
        tree.itemChanged.connect(self._checked)
        tree.currentItemChanged.connect(self._current)
        tree.itemDoubleClicked.connect(self._properties)
        tree.itemExpanded.connect(lambda item: self._collapsed.discard(item.data(0, Qt.ItemDataRole.UserRole)))
        tree.itemCollapsed.connect(lambda item: self._collapsed.add(item.data(0, Qt.ItemDataRole.UserRole)))
        tree.hide()
        layout.insertWidget(layout.indexOf(view) + 1, tree)
        self._tree = tree
        # The button, at the end of QGIS's own row.
        action = QAction(tr("List by Data Source"))
        action.setCheckable(True)
        action.setToolTip(tr("List by Data Source: the layers grouped by the file, database or service "
                             "they come from"))
        action.toggled.connect(self._toggled)
        if toolbar is not None:
            toolbar.addAction(action)
            self._toolbar = toolbar
        self._action = action
        self._theme_icons()
        self._regular_names(view)

    def _theme_icons(self):
        if self._action is None:
            return
        self._action.setIcon(QIcon())
        if self._icons is None or not self._icons.adopt(self._action, SOURCE_ICON):
            self._action.setIcon(QgsApplication.getThemeIcon("/mIconDbSchema.svg"))
        # The search field's magnifier (QGIS's own, set by setShowSearchIcon).
        if self._icons is not None and self._search is not None and not sip.isdeleted(self._search):
            for action in self._search.actions():
                self._icons.swap_action(action)
        if self._tree is not None and self._tree.isVisible():
            self._rebuild()

    def _regular_names(self, view):
        """Layer names in the regular weight (QGIS draws them bold), so a
        long list reads calmly; groups keep QGIS's bold."""
        model = view.layerTreeModel() if hasattr(view, "layerTreeModel") else None
        if model is None:
            return
        kind = QgsLayerTreeNode.NodeType.NodeLayer
        font = model.layerTreeNodeFont(kind)
        if not font.bold():
            return
        self._model, self._layer_font = model, QFont(font)
        font = QFont(font)
        font.setBold(False)
        model.setLayerTreeNodeFont(kind, font)
        view.viewport().update()

    def resize(self):
        if self._tree is not None and self._view is not None and not sip.isdeleted(self._view):
            self._tree.setIconSize(self._view.iconSize())

    # ---- Search ---------------------------------------------------------------

    def _filter(self, text=None):
        text = (self._search.text() if text is None else text) if self._search is not None else ""
        view = self._view
        if view is not None and not sip.isdeleted(view) and hasattr(view, "proxyModel"):
            view.proxyModel().setFilterText(text)
        if self._tree is None:
            return
        needle = text.strip().lower()
        for i in range(self._tree.topLevelItemCount()):
            group = self._tree.topLevelItem(i)
            shown = 0
            for j in range(group.childCount()):
                child = group.child(j)
                hide = bool(needle) and needle not in child.text(0).lower()
                child.setHidden(hide)
                shown += not hide
            group.setHidden(shown == 0)

    # ---- List by data source ------------------------------------------------

    def _toggled(self, on):
        view = self._view
        if self._tree is None or view is None or sip.isdeleted(view):
            return
        root = QgsProject.instance().layerTreeRoot()
        if on:
            for signal in (root.addedChildren, root.removedChildren, root.visibilityChanged, root.nameChanged,
                           QgsProject.instance().layersAdded, QgsProject.instance().layersRemoved,
                           self.iface.currentLayerChanged):
                signal.connect(self._later)
                self._connections.append((signal, self._later))
            model = self._model or (view.layerTreeModel() if hasattr(view, "layerTreeModel") else None)
            if model is not None:
                model.dataChanged.connect(self._later)
                self._connections.append((model.dataChanged, self._later))
            self._rebuild()
            view.hide()
            self._tree.show()
        else:
            self._disconnect()
            self._timer.stop()
            self._tree.hide()
            view.show()

    def _disconnect(self):
        for signal, slot in self._connections:
            try:
                signal.disconnect(slot)
            except (TypeError, RuntimeError):
                pass
        self._connections = []

    def _later(self, *_args):
        if not self._building:
            self._timer.start()

    def _icon(self, name):
        icon = self._icons.themed_icon(name) if self._icons is not None else None
        return icon if icon is not None else QgsApplication.getThemeIcon("/" + name)

    def _rebuild(self):
        tree, view = self._tree, self._view
        if tree is None or view is None or sip.isdeleted(view):
            return
        model = view.layerTreeModel() if hasattr(view, "layerTreeModel") else None
        root = QgsProject.instance().layerTreeRoot()
        current = self.iface.activeLayer()
        self._building = True
        scroll = tree.verticalScrollBar().value()
        tree.blockSignals(True)
        tree.clear()
        groups = {}
        bold = QFont(tree.font())
        bold.setBold(True)
        selected = None
        for node in root.findLayers():
            layer = node.layer()
            if layer is None:
                continue
            key, label, icon, tip = source_of(layer)
            group = groups.get(key)
            if group is None:
                group = QTreeWidgetItem([label])
                group.setIcon(0, self._icon(icon))
                group.setToolTip(0, tip)
                group.setFont(0, bold)
                group.setData(0, Qt.ItemDataRole.UserRole, key)
                group.setFlags(Qt.ItemFlag.ItemIsEnabled)
                tree.addTopLevelItem(group)
                groups[key] = group
            item = QTreeWidgetItem([node.name()])
            item.setData(0, Qt.ItemDataRole.UserRole, layer.id())
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(0, Qt.CheckState.Checked if node.itemVisibilityChecked() else Qt.CheckState.Unchecked)
            item.setToolTip(0, layer.publicSource() if hasattr(layer, "publicSource") else layer.source())
            if model is not None:
                index = model.node2index(node)
                icon = model.data(index, Qt.ItemDataRole.DecorationRole)
                if isinstance(icon, QIcon):
                    ours = self._icons.keyed_icon(icon) if self._icons is not None else None
                    item.setIcon(0, ours or icon)
                legend = model.layerLegendNodes(node)
                if len(legend) > 1:
                    for entry in legend:
                        child = QTreeWidgetItem([str(entry.data(Qt.ItemDataRole.DisplayRole) or "")])
                        child.setFlags(Qt.ItemFlag.ItemIsEnabled)
                        symbol = entry.data(Qt.ItemDataRole.DecorationRole)
                        if isinstance(symbol, QIcon):
                            child.setIcon(0, symbol)
                        item.addChild(child)
            group.addChild(item)
            if current is not None and layer.id() == current.id():
                selected = item
        for key, group in groups.items():
            group.setExpanded(key not in self._collapsed)
        if selected is not None:
            tree.setCurrentItem(selected)
        tree.blockSignals(False)
        tree.verticalScrollBar().setValue(scroll)
        self._building = False
        self._filter()

    def _layer(self, item):
        if item is None or item.parent() is None:
            return None
        layer_id = item.data(0, Qt.ItemDataRole.UserRole)
        return QgsProject.instance().mapLayer(layer_id) if layer_id else None

    def _checked(self, item, _column):
        layer = self._layer(item)
        node = QgsProject.instance().layerTreeRoot().findLayer(layer.id()) if layer is not None else None
        if node is not None:
            self._building = True
            node.setItemVisibilityChecked(item.checkState(0) == Qt.CheckState.Checked)
            self._building = False

    def _current(self, item, _previous):
        layer = self._layer(item)
        if layer is not None and layer is not self.iface.activeLayer():
            self._building = True
            self.iface.setActiveLayer(layer)
            self._building = False

    def _properties(self, item, _column):
        layer = self._layer(item)
        if layer is not None:
            self.iface.showLayerProperties(layer)

    def _menu(self, pos):
        """QGIS's own layer menu, for the layer under the pointer."""
        layer = self._layer(self._tree.itemAt(pos))
        view = self._view
        if layer is None or view is None or sip.isdeleted(view) or view.menuProvider() is None:
            return
        view.setCurrentLayer(layer)
        menu = view.menuProvider().createContextMenu()
        if menu is not None:
            menu.exec(self._tree.viewport().mapToGlobal(pos))
            menu.deleteLater()

    # ---- Restoring ------------------------------------------------------------

    def detach(self):
        self._timer.stop()
        self._disconnect()
        if self._action is not None:
            if self._toolbar is not None and not sip.isdeleted(self._toolbar):
                self._toolbar.removeAction(self._action)
            self._action.deleteLater()
        if self._view is not None and not sip.isdeleted(self._view):
            self._view.show()
        if self._model is not None and not sip.isdeleted(self._model) and self._layer_font is not None:
            self._model.setLayerTreeNodeFont(QgsLayerTreeNode.NodeType.NodeLayer, self._layer_font)
        if self._search is not None and not sip.isdeleted(self._search):
            # QGIS shows no layer search: its filter goes with the field.
            self._search.clear()
        for widget in (self._top, self._tree):
            if widget is not None and not sip.isdeleted(widget):
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()
        self._view = self._top = self._search = self._tree = self._toolbar = self._action = None
        self._model = self._layer_font = None
