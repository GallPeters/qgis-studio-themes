"""GUI performance benchmark for QGIS UI themes.

Run inside QGIS (the plugin must be installed and enabled in the profile):

    STUDIO_THEMES="default,Studio Premium" STUDIO_OUT=bench.json \
        qgis --nologo --noversioncheck --code tools/benchmark.py

Add QT_QPA_PLATFORM=offscreen to run headless. For every theme it measures
the median CPU time (ms) of the operations whose cost a stylesheet
affects: applying the theme, building heavy dialogs (polish + layout +
first paint), repainting the whole main window and scrolling a table.

CPU time of the QGIS process (all threads) is used instead of wall time so
other load on the machine does not skew results, and themes are measured
in interleaved rounds so any remaining drift hits all of them equally.
STUDIO_EXTRA_THEMES="Name=/theme/folder;..." registers additional theme
folders first, e.g. a previous release, to compare within one session.
"""
import json
import os
import statistics
import time

from qgis.core import QgsApplication, QgsProject, QgsVectorLayer
from qgis.gui import QgsVectorLayerProperties
from qgis.PyQt.QtCore import QEvent, QTimer
from qgis.PyQt.QtWidgets import QApplication, QTableView
from qgis.utils import iface

LAYER = os.environ.get(
    "STUDIO_LAYER",
    "/usr/share/qgis/resources/data/world_map.gpkg|layername=countries",
)
THEMES = os.environ.get("STUDIO_THEMES", "default").split(",")
OUT = os.environ.get("STUDIO_OUT", "benchmark.json")
REPEAT = int(os.environ.get("STUDIO_REPEAT", "5"))


def pump():
    # processEvents() never runs deleteLater(); flush it explicitly so
    # closed dialogs do not pile up and inflate later measurements.
    for _ in range(5):
        QApplication.processEvents()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete.value)


def save(results):
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)


def cpu_ms(fn):
    start = time.process_time()
    fn()
    return (time.process_time() - start) * 1000


def run():
    for entry in filter(None, os.environ.get("STUDIO_EXTRA_THEMES", "").split(";")):
        name, folder = entry.split("=", 1)
        QgsApplication.applicationThemeRegistry().addTheme(name, folder)
    window = iface.mainWindow()
    window.resize(1600, 1000)
    layer = QgsVectorLayer(LAYER, "Countries", "ogr")
    QgsProject.instance().addMapLayer(layer)
    pump()

    def layer_properties():
        dialog = QgsVectorLayerProperties(iface.mapCanvas(), iface.messageBar(), layer, window)
        dialog.resize(1100, 750)
        dialog.show()
        pump()
        dialog.grab()
        dialog.close()
        dialog.deleteLater()
        pump()

    def attribute_table():
        dialog = iface.showAttributeTable(layer)
        pump()
        dialog.grab()
        dialog.close()
        dialog.deleteLater()
        pump()

    def scroll_table():
        table = iface.showAttributeTable(layer)
        table.resize(1100, 700)
        pump()
        view = table.findChild(QTableView)
        bar = view.verticalScrollBar()
        start = time.process_time()
        for value in range(0, bar.maximum() + 1, max(1, bar.maximum() // 40)):
            bar.setValue(value)
            view.viewport().repaint()
        elapsed = (time.process_time() - start) * 1000
        table.close()
        table.deleteLater()
        pump()
        return elapsed

    samples = {theme: {} for theme in THEMES}
    for _ in range(REPEAT):
        for theme in THEMES:
            QgsApplication.setUITheme("default")
            pump()
            record = samples[theme]

            def apply_theme(theme=theme):
                QgsApplication.setUITheme(theme)
                pump()

            record.setdefault("apply_theme", []).append(cpu_ms(apply_theme))
            record.setdefault("repaint_main_window", []).append(
                statistics.median(cpu_ms(window.grab) for _ in range(5))
            )
            record.setdefault("scroll_table", []).append(scroll_table())
            record.setdefault("attribute_table", []).append(cpu_ms(attribute_table))
            record.setdefault("layer_properties", []).append(cpu_ms(layer_properties))
        save({
            theme: {name: round(statistics.median(values), 1) for name, values in record.items()}
            for theme, record in samples.items()
        })
    QgsApplication.setUITheme("default")
    pump()
    QgsApplication.exit()


def safe_run():
    try:
        run()
    except Exception:  # pylint: disable=broad-except
        import traceback

        with open(OUT + ".error.txt", "w", encoding="utf-8") as handle:
            traceback.print_exc(file=handle)
        QgsApplication.exit(1)


QTimer.singleShot(3000, safe_run)
