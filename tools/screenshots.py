"""Capture screenshots of QGIS with each theme, for review and the README.

Run inside QGIS (the plugin must be installed and enabled in the profile,
and every theme built once, so its icons are pre-rendered):

    STUDIO_THEMES="Studio Premium Dark,Studio Pro Light" STUDIO_OUT=shots \
        qgis --nologo --noversioncheck --code tools/screenshots.py

For every theme it saves, named like docs/screenshots (premium-dark.png,
premium-dark_properties.png...): the main window (1600 x 1000) with the
countries layer drawn in the theme's colours (the canvas in the theme
background for dark themes, white for light ones; countries in a tint of
the accent, labelled) and the Layer Styling, Processing, Browser and Layers
panels open; the layer properties dialog on its Symbology page (the
Information page would show local paths); and, for review, the attribute
table and an open menu.
"""
import os
import traceback

from qgis.core import (
    QgsApplication, QgsFillSymbol, QgsPalLayerSettings, QgsProject, QgsTextFormat,
    QgsVectorLayer, QgsVectorLayerSimpleLabeling,
)
from qgis.gui import QgsVectorLayerProperties
from qgis.PyQt.QtCore import QPoint, Qt, QTimer
from qgis.PyQt.QtGui import QColor, QFont
from qgis.PyQt.QtWidgets import QApplication, QDockWidget, QToolBar
from qgis.utils import iface

from qgis_studio_themes.qgis_studio_themes import QgisStudioThemesPlugin, load_tokens
from qgis_studio_themes.studio_tokens import is_dark, parse_color

LAYER = os.environ.get(
    "STUDIO_LAYER",
    "/usr/share/qgis/resources/data/world_map.gpkg|layername=countries",
)
THEMES = [t for t in os.environ.get("STUDIO_THEMES", "").split(",") if t]
OUT = os.environ.get("STUDIO_OUT", "screenshots")
PANELS = ("Layers", "Browser", "LayerStyling", "ProcessingToolbox")


def pump(count=10):
    for _ in range(count):
        QApplication.processEvents()


def color(tokens, name):
    r, g, b, _alpha = parse_color(tokens[name])
    return QColor(r, g, b)


def mix(a, b, t):
    return QColor(*(round(x * (1 - t) + y * t) for x, y in zip(a.getRgb()[:3], b.getRgb()[:3])))


def style(layer, theme):
    """Draw `layer` and the canvas in the colours of Studio `theme`."""
    tokens = load_tokens(QgisStudioThemesPlugin.THEMES[theme.removeprefix("Studio ")])
    accent, text = color(tokens, "@accent"), color(tokens, "@text")
    dark = is_dark(tokens["@bg_window"])
    canvas = color(tokens, "@bg_window") if dark else QColor("#ffffff")
    layer.renderer().setSymbol(QgsFillSymbol.createSimple({
        "color": mix(canvas, accent, 0.45 if dark else 0.3).name(),
        "outline_color": mix(canvas, accent, 0.9 if dark else 0.6).name(),
        "outline_width": "0.2",
    }))
    labels = QgsPalLayerSettings()
    labels.fieldName = "NAME"
    text_format = QgsTextFormat()
    text_format.setFont(QFont("Inter", 9))
    text_format.setSize(9)
    text_format.setColor(text)
    labels.setFormat(text_format)
    layer.setLabeling(QgsVectorLayerSimpleLabeling(labels))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()
    iface.mapCanvas().setCanvasColor(canvas)
    # Panels showing the symbol (Layers swatch, Layer Styling) redraw it.
    layer.emitStyleChanged()
    view = iface.layerTreeView()
    view.refreshLayerSymbology(layer.id())
    view.setCurrentLayer(None)
    pump()
    view.setCurrentLayer(layer)


def capture(theme, layer):
    tag = theme.removeprefix("Studio ").lower().replace(" ", "-")
    QgsApplication.setUITheme(theme)
    pump()
    style(layer, theme)
    window = iface.mainWindow()
    canvas = iface.mapCanvas()
    canvas.refreshAllLayers()
    canvas.waitWhileRendering()
    pump(30)
    # No notices over the map (QGIS's startup messages).
    iface.messageBar().clearWidgets()
    pump()
    window.grab().save(os.path.join(OUT, f"{tag}.png"))

    menu = window.menuBar().actions()[1].menu()
    menu.popup(window.mapToGlobal(QPoint(120, 40)))
    pump()
    menu.grab().save(os.path.join(OUT, f"{tag}_menu.png"))
    menu.hide()

    table = iface.showAttributeTable(layer)
    table.resize(1000, 560)
    table.activateWindow()
    pump()
    table.grab().save(os.path.join(OUT, f"{tag}_table.png"))
    table.close()

    dialog = QgsVectorLayerProperties(canvas, iface.messageBar(), layer, window)
    dialog.resize(1100, 720)
    dialog.setCurrentPage("mOptsPage_Style")
    dialog.show()
    dialog.activateWindow()
    pump(20)
    dialog.grab().save(os.path.join(OUT, f"{tag}_properties.png"))
    dialog.close()
    dialog.deleteLater()
    pump()


def layout(window):
    """The same window layout whatever the profile saved: Browser over
    Layers on the left, Layer Styling over Processing on the right, and
    only the toolbars docked at the top."""
    docks = {dock.objectName(): dock for dock in window.findChildren(QDockWidget)}
    for dock in docks.values():
        if dock.objectName() not in PANELS:
            dock.hide()
    for name, area in (("Browser", Qt.DockWidgetArea.LeftDockWidgetArea),
                       ("Layers", Qt.DockWidgetArea.LeftDockWidgetArea),
                       ("LayerStyling", Qt.DockWidgetArea.RightDockWidgetArea),
                       ("ProcessingToolbox", Qt.DockWidgetArea.RightDockWidgetArea)):
        dock = docks[name]
        dock.setFloating(False)
        window.addDockWidget(area, dock, Qt.Orientation.Vertical)
        dock.show()
    for toolbar in window.findChildren(QToolBar):
        if toolbar.parent() is window and window.toolBarArea(toolbar) != Qt.ToolBarArea.TopToolBarArea:
            toolbar.hide()
    pump()
    left, right = [docks["Browser"], docks["Layers"]], [docks["LayerStyling"], docks["ProcessingToolbox"]]
    window.resizeDocks([left[0], right[0]], [345, 710], Qt.Orientation.Horizontal)
    window.resizeDocks(left, [240, 600], Qt.Orientation.Vertical)
    window.resizeDocks(right, [500, 400], Qt.Orientation.Vertical)


def run():
    os.makedirs(OUT, exist_ok=True)
    window = iface.mainWindow()
    window.showNormal()
    window.resize(1600, 1000)
    layer = QgsVectorLayer(LAYER, "Countries", "ogr")
    QgsProject.instance().addMapLayer(layer)
    layout(window)
    pump()
    iface.mapCanvas().setExtent(layer.extent())
    pump()
    for theme in THEMES or QgsApplication.applicationThemeRegistry().themes():
        if theme.removeprefix("Studio ") in QgisStudioThemesPlugin.THEMES:
            capture(theme, layer)
    QgsApplication.exit()


def safe_run():
    try:
        run()
    except Exception:  # pylint: disable=broad-except
        os.makedirs(OUT, exist_ok=True)
        with open(os.path.join(OUT, "error.txt"), "w", encoding="utf-8") as handle:
            traceback.print_exc(file=handle)
        QgsApplication.exit(1)


QTimer.singleShot(5000, safe_run)
