"""Capture screenshots of QGIS with each theme, for review and the README.

Run inside QGIS (the plugin must be installed and enabled in the profile):

    STUDIO_THEMES="Studio Premium,Studio Pro Light" STUDIO_OUT=shots \
        qgis --nologo --noversioncheck --code tools/screenshots.py

For every theme it saves the main window with a layer loaded and the
Layer Styling, Processing and Layers panels open, the layer properties
dialog, the attribute table and an open menu.
"""
import os
import traceback

from qgis.core import QgsApplication, QgsProject, QgsVectorLayer
from qgis.gui import QgsVectorLayerProperties
from qgis.PyQt.QtCore import QPoint, QTimer
from qgis.PyQt.QtWidgets import QApplication, QDockWidget
from qgis.utils import iface

LAYER = os.environ.get(
    "STUDIO_LAYER",
    "/usr/share/qgis/resources/data/world_map.gpkg|layername=countries",
)
THEMES = [t for t in os.environ.get("STUDIO_THEMES", "").split(",") if t]
OUT = os.environ.get("STUDIO_OUT", "screenshots")
PANELS = ("Layers", "Browser", "LayerStyling", "ProcessingToolbox")


def pump():
    for _ in range(10):
        QApplication.processEvents()


def capture(theme, layer):
    tag = theme.replace(" ", "_")
    QgsApplication.setUITheme(theme)
    pump()
    window = iface.mainWindow()
    iface.mapCanvas().refreshAllLayers()
    pump()
    window.grab().save(os.path.join(OUT, f"{tag}_main.png"))

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

    dialog = QgsVectorLayerProperties(iface.mapCanvas(), iface.messageBar(), layer, window)
    dialog.resize(1100, 760)
    dialog.show()
    dialog.activateWindow()
    pump()
    dialog.grab().save(os.path.join(OUT, f"{tag}_properties.png"))
    dialog.close()
    dialog.deleteLater()
    pump()


def run():
    os.makedirs(OUT, exist_ok=True)
    window = iface.mainWindow()
    window.resize(1600, 1000)
    layer = QgsVectorLayer(LAYER, "Countries", "ogr")
    QgsProject.instance().addMapLayer(layer)
    iface.mapCanvas().setExtent(layer.extent())
    for dock in window.findChildren(QDockWidget):
        if dock.objectName() in PANELS:
            dock.show()
    iface.messageBar().pushInfo("Studio", "Message bar sample — info level")
    pump()
    for theme in THEMES or QgsApplication.applicationThemeRegistry().themes():
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


QTimer.singleShot(3000, safe_run)
