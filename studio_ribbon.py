"""The ribbon: QGIS's toolbars as tabs of grouped buttons (Plugins > QGIS
Studio Themes > Settings > Interface).

A row in place of the menu bar holds the tabs (Project, Home, Layer...),
with Help and a collapse button at their right, and under them the current tab's
page, a surface of its own the current tab opens into (a folder tab, its
name underlined in the accent): groups of large buttons (a 28 px icon, the
label under it) and small ones (20 px icons, labelled or not) in rows,
each group named in small capitals beneath. The sizes are ones the icons
are pre-rendered at, so every icon is pixel-sharp.

Every action of every main window toolbar is on the ribbon, by
construction: TABS places QGIS's toolbars, a group listing no actions
takes those of its toolbar no group names (so actions plugins add to
QGIS's toolbars land there too), and any other toolbar (a plugin's, added
at any time) gets a group of its own on the Plugins tab. So is every
command of QGIS's menus: TABS places the ones on no toolbar, each menu's
"More" group shows what else it holds (what plugins add, at any time),
and menus plugins add to the menu bar get groups on the Plugins tab;
commands QGIS gives no icon get one of the theme's (ICON_FALLBACKS). The
menu bar itself is folded away. The buttons are
the toolbars' own actions (QToolButton.setDefaultAction), so their icons
(the theme's, swapped by the plugin), checked, enabled and visible states
follow QGIS's at no cost. QGIS's tool buttons that switch between tools
(Select, Measure, Vertex Tool...) are cloned, the chosen tool passed back
to QGIS's button, and widgets other than buttons (the snapping tolerance
and units) are borrowed from their hidden toolbar while the ribbon shows
and given back after.

The toolbars are hidden, not removed, so QGIS keeps their places: turning
the ribbon off shows the ones it hid (remembered across sessions, as QGIS
saves them hidden). Pages are built when first shown and again when their
toolbars change, so startup builds one page and nothing runs while the
ribbon simply shows; all styling comes from the theme's stylesheet
(style.qss, object names and the studioRibbon property).
"""
import re

from qgis.core import QgsSettings
from qgis.PyQt import sip
from qgis.PyQt.QtCore import QEvent, QObject, QSize, Qt, QTimer
from qgis.PyQt.QtGui import QFontMetrics, QIcon, QPainter, QPalette, QPixmap
from qgis.PyQt.QtWidgets import (
    QAction, QFrame, QGridLayout, QHBoxLayout, QLabel, QMenu, QScrollArea, QSizePolicy, QStackedWidget, QTabBar,
    QToolBar, QToolButton, QVBoxLayout, QWidget, QWidgetAction,
)

from . import studio_toolbars

HOST_NAME = "studioRibbonHost"
# The tab shown, whether the ribbon is collapsed to its tabs, and the
# toolbars it hid (shown again when the ribbon is turned off, also in a
# later session: QGIS saves them hidden).
TAB_SETTING = "studio_themes/ribbonTab"
COLLAPSED_SETTING = "studio_themes/ribbonCollapsed"
HIDDEN_SETTING = "studio_themes/ribbonHiddenToolbars"
# Qt's "no maximum" widget size.
QWIDGETSIZE_MAX = (1 << 24) - 1

# Sizes (logical px): icons (pre-rendered sizes, see qgis_studio_themes
# PNG_SIZES), the rows of small buttons and the groups' room.
LARGE_ICON = 28
SMALL_ICON = 20
ROW_HEIGHT = 24
ROWS = 3
SPACING = 2
BODY = ROWS * ROW_HEIGHT + (ROWS - 1) * SPACING
LARGE_MIN_WIDTH = 52
# The current tab's top margin in style.qss (studioRibbonTabs::tab:top:selected).
TAB_TOP = 4
GROUP_MARGINS = (6, 8, 6, 6)

# Layouts of a group's small buttons: labelled, or icons only; or (plugins'
# groups) large labelled buttons for up to AUTO_LARGE actions, else icons.
LABELS, ICONS, AUTO = "labels", "icons", "auto"
AUTO_LARGE = 3
# A group: (title, sources, large, layout[, rows]). Sources are (toolbar
# objectName, action objectNames, or None for those of the toolbar no
# group names); ("@", objectNames) for actions of the main window not on
# a toolbar (Raster Calculator...) or menus, shown as a button opening the
# menu; or ("menu", menu objectNames) for what those menus hold that the
# ribbon has nowhere else (see StudioRibbon._covered: QGIS's commands
# missed here, and what plugins add). Large: objectNames shown as large
# buttons. Rows: explicit rows of small buttons (lists of objectNames)
# instead of columns of ROWS. Every command of QGIS's menus is on some tab,
# so the menu bar is folded away (set_menu_bar_folded).
TABS = (
    ("Project", (
        ("Project", (("@", (
            "mActionNewProject", "mActionOpenProject", "mActionSaveProject", "mProjectFromTemplateMenu",
            "mRecentProjectsMenu", "mProjectFromStorageMenu", "mActionSaveProjectAs", "mProjectToStorageMenu",
            "mActionRevertProject", "mActionCloseProject", "mActionExit")),),
         ("mActionNewProject", "mActionOpenProject", "mActionSaveProject"), LABELS),
        ("Settings", (("@", ("mActionProjectProperties", "mActionSnappingOptions", "mActionStyleManager")),),
         ("mActionProjectProperties",), LABELS),
        ("Import and Export", (("@", (
            "mActionSaveMapAsImage", "mActionSaveMapAsPdf", "mActionDxfExport", "mActionDwgImport")),), (), LABELS),
        ("Layouts", (("@", ("mActionNewPrintLayout", "mActionNewReport", "mActionShowLayoutManager", "mLayoutsMenu")),),
         ("mActionNewPrintLayout",), LABELS),
        ("More", (("menu", ("mProjectMenu",)),), (), LABELS),
    )),
    ("Home", (
        ("Project", (("mFileToolBar", None),),
         ("mActionNewProject", "mActionOpenProject", "mActionSaveProject"), LABELS),
        ("Navigate", (("mMapNavToolBar", (
            "mActionPan", "mActionPanToSelected", "mActionZoomIn", "mActionZoomOut", "mActionZoomFullExtent",
            "mActionZoomToSelected", "mActionZoomToLayers", "mActionZoomActualSize", "mActionZoomLast",
            "mActionZoomNext", "mActionDraw")),), ("mActionPan",), ICONS),
        ("Select", (("mSelectionToolBar", None),), ("ActionSelect",), ICONS),
        ("Inspect", (("mAttributesToolBar", None),), ("mActionIdentify", "ActionOpenTable"), LABELS),
    )),
    ("Data", (
        ("Add Data", (("mDataSourceManagerToolBar", ("mActionDataSourceManager",)),),
         ("mActionDataSourceManager",), LABELS),
        ("Add Layer", (("mLayerToolBar", (
            "mActionAddOgrLayer", "mActionAddRasterLayer", "mActionAddMeshLayer", "mActionAddDelimitedText",
            "mActionAddSpatiaLiteLayer", "mActionAddVirtualLayer", "ActionAddDbLayer", "mActionAddWmsLayer",
            "mActionAddWcsLayer", "mActionAddWfsLayer", "mActionAddStacLayer")),), (), LABELS),
        ("Create Layer", (("mDataSourceManagerToolBar", None), ("mLayerToolBar", None)),
         ("mActionNewGeoPackageLayer",), LABELS),
        ("More Data", (("@", (
            "mAddLayerMenu", "mNewLayerMenu", "mActionEmbedLayers", "mActionAddLayerDefinition")),), (), LABELS),
    )),
    ("Layer", (
        ("Layer", (("@", (
            "mActionLayerProperties", "mActionLayerSubsetString", "mActionDuplicateLayer", "mActionSetLayerCRS",
            "mActionSetProjectCRSFromLayer", "mActionSetLayerScaleVisibility", "mActionLayerSaveAs",
            "mActionSaveLayerDefinition", "mActionRemoveLayer")),), ("mActionLayerProperties",), LABELS),
        ("Copy and Paste", (("@", (
            "mActionCopyStyle", "mActionPasteStyle", "mActionCopyLayer", "mActionPasteLayer")),), (), LABELS),
        ("Overview", (("@", ("mActionAddToOverview", "mActionAddAllToOverview", "mActionRemoveAllFromOverview")),),
         (), LABELS),
        ("More", (("menu", ("mLayerMenu",)),), (), LABELS),
    )),
    ("Edit", (
        ("Editing", (("mDigitizeToolBar", ("mActionToggleEditing", "mActionSaveLayerEdits", "mActionAllEdits")),),
         ("mActionToggleEditing",), LABELS),
        ("Digitize", (("mDigitizeToolBar", ("mActionAddFeature", "ActionVertexTool", "mDigitizeModeToolButton")),),
         ("mActionAddFeature", "ActionVertexTool"), LABELS),
        ("Features", (("mDigitizeToolBar", (
            "mActionMultiEditAttributes", "mActionDeleteSelected", "mActionCutFeatures", "mActionCopyFeatures",
            "mActionPasteFeatures")), ("@", ("mMenuPasteAs",))), (), LABELS),
        ("History", (("mDigitizeToolBar", None),), (), LABELS),
        ("Snapping", (("mSnappingToolBar", None),), (), ICONS, (
            ("EnableSnappingAction", "mModeAction", "mEditAdvancedConfigAction", "mTypeAction", "mToleranceAction",
             "mUnitAction"),
            ("TopologicalEditingAction", "mAvoidIntersectionsModeAction", "IntersectionSnappingAction",
             "EnableTracingAction", "SelfSnappingAction"),
        )),
        ("Shapes", (("mShapeDigitizeToolBar", None),), (), ICONS),
        ("More", (("menu", ("mEditMenu",)),), (), LABELS),
    )),
    ("Modify", (
        ("Advanced", (("mAdvancedDigitizeToolBar", ("mEnableAction",)),), ("mEnableAction",), LABELS),
        ("Transform", (("mAdvancedDigitizeToolBar", (
            "ActionMoveFeatureTool", "mActionRotateFeature", "mActionScaleFeature", "mActionSimplifyFeature",
            "mActionOffsetCurve", "mActionReverseLine")),), (), LABELS),
        ("Rings and Parts", (("mAdvancedDigitizeToolBar", (
            "mActionAddRing", "mActionAddPart", "mActionFillRing", "mActionDeleteRing", "mActionDeletePart")),),
         (), LABELS),
        ("Reshape", (("mAdvancedDigitizeToolBar", (
            "mActionReshapeFeatures", "mActionChamferFillet", "mActionTrimExtendFeature", "mActionSplitFeatures",
            "mActionSplitParts", "mActionMergeFeatures", "mActionMergeFeatureAttributes")),), (), LABELS),
        ("Point Symbols", (("mAdvancedDigitizeToolBar", None),), (), LABELS),
    )),
    ("Annotate", (
        ("Labels", (("mLabelToolBar", ("mActionLabeling", "mActionDiagramProperties")),),
         ("mActionLabeling", "mActionDiagramProperties"), LABELS),
        ("Label Tools", (("mLabelToolBar", None),), (), LABELS),
        ("Annotations", (("mAnnotationsToolBar", (
            "annotationLayerToolButtonAction", "mActionSelectAnnotation", "mActionModifyAnnotation")),),
         ("annotationLayerToolButtonAction",), LABELS),
        ("Draw", (("mAnnotationsToolBar", (
            "mActionPolygonAnnotation", "mActionLineAnnotation", "mActionMarkerAnnotation",
            "mActionTextAnnotationatPoint", "mActionTextAnnotationalongLine", "mActionTextAnnotationinRectangle",
            "mActionPictureAnnotation")),), (), ICONS),
        ("Map Annotations", (("mAnnotationsToolBar", None),), (), LABELS),
    )),
    ("View", (
        ("Map Views", (("mMapNavToolBar", ("mActionNewMapCanvas", "mActionNew3DMapCanvas")),
                       ("@", ("mActionNew3DMapCanvasGlobe", "mActionManage3DMapViews"))),
         ("mActionNewMapCanvas", "mActionNew3DMapCanvas"), LABELS),
        ("Bookmarks", (("mMapNavToolBar", ("mActionNewBookmark", "mActionShowBookmarks")),
                       ("@", ("mActionShowBookmarkManager",))), (), LABELS),
        ("Time", (("mMapNavToolBar", None),), ("mActionTemporalController",), LABELS),
        ("Elevation", (("@", (
            "mActionElevationProfile", "mActionManageElevationProfiles", "mActionElevationController")),),
         ("mActionElevationProfile",), LABELS),
        ("Map Display", (("@", ("mMenuDecorations", "mMenuPreviewMode", "mMenuLayerVisibility")),), (), LABELS),
        ("Window", (("@", (
            "mPanelMenu", "mActionToggleFullScreen", "mActionTogglePanelsVisibility", "mActionToggleMapOnly")),),
         (), LABELS),
        ("More", (("menu", ("mViewMenu",)),), (), LABELS),
    )),
    ("Vector", (
        ("Vector Tools", (("menu", ("mVectorMenu",)),), (), LABELS),
        ("Vector Plugins", (("mVectorToolBar", None),), (), AUTO),
    )),
    ("Raster", (
        ("Tools", (("@", ("mActionShowRasterCalculator", "mActionShowGeoreferencer")),),
         ("mActionShowRasterCalculator", "mActionShowGeoreferencer"), LABELS),
        ("Raster Tools", (("menu", ("mRasterMenu",)),), (), LABELS),
        ("Stretch", (("mRasterToolBar", (
            "mActionLocalCumulativeCutStretch", "mActionFullCumulativeCutStretch", "mActionLocalHistogramStretch",
            "mActionFullHistogramStretch")),), (), ICONS, (
            ("mActionLocalCumulativeCutStretch", "mActionLocalHistogramStretch"),
            ("mActionFullCumulativeCutStretch", "mActionFullHistogramStretch"),
        )),
        ("Adjust", (("mRasterToolBar", (
            "mActionIncreaseBrightness", "mActionDecreaseBrightness", "mActionIncreaseContrast",
            "mActionDecreaseContrast", "mActionIncreaseGamma", "mActionDecreaseGamma")),), (), ICONS, (
            ("mActionIncreaseBrightness", "mActionIncreaseContrast", "mActionIncreaseGamma"),
            ("mActionDecreaseBrightness", "mActionDecreaseContrast", "mActionDecreaseGamma"),
        )),
        ("Raster Plugins", (("mRasterToolBar", None),), (), ICONS),
    )),
    ("Mesh", (
        ("Calculator", (("@", ("mActionShowMeshCalculator", "mActionReindexMesh")),),
         ("mActionShowMeshCalculator",), LABELS),
        ("Mesh Editing", (("mMeshToolBar", None),), (), LABELS),
        ("More", (("menu", ("mMeshMenu",)),), (), LABELS),
    )),
    ("Processing", (
        ("Toolbox", (("@", ("toolboxAction", "modelerAction", "mMenuProjectModels")),),
         ("toolboxAction", "modelerAction"), LABELS),
        ("Results", (("@", ("historyAction", "resultsViewer", "editInPlaceFeatures")),), (), LABELS),
        ("More", (("menu", ("processing",)),), (), LABELS),
    )),
    ("GPS", (
        ("Connection", (("mGpsToolBar", ("mConnectAction", "mRecenterAction")),), ("mConnectAction",), LABELS),
        ("Tracking", (("mGpsToolBar", (
            "mDestinationLayerButtonAction", "mAddTrackVertexAction", "mCreateFeatureAction",
            "mResetFeatureAction")),), (), LABELS),
        ("Display", (("mGpsToolBar", None),), (), LABELS),
    )),
    ("Plugins", (
        ("Plugins", (("@", ("mActionManagePlugins",)),), ("mActionManagePlugins",), LABELS),
        ("Python", (("mPluginToolBar", None),), (), AUTO),
        ("Plugin Menus", (("menu", ("mPluginMenu",)),), (), LABELS),
        ("Database", (("mDatabaseToolBar", None), ("menu", ("mDatabaseMenu",))), ("dbManager",), LABELS),
        ("Web", (("mWebToolBar", None), ("menu", ("mWebMenu",))), ("action_run",), LABELS),
    )),
    ("Settings", (
        ("Options", (("@", ("mActionOptions",)),), ("mActionOptions",), LABELS),
        ("Customize", (("@", (
            "mActionConfigureShortcuts", "mActionCustomization", "mActionStyleManager", "mActionCustomProjection")),),
         (), LABELS),
        ("Profiles", (("@", ("mUserProfileMenu",)),), (), LABELS),
        ("More", (("menu", ("mSettingsMenu",)),), (), LABELS),
    )),
    ("Help", (
        ("Help", (("@", ("mActionHelpContents", "mActionHelpAPI", "mActionHelpPyQgisAPI", "mMenuPluginHelp")),),
         ("mActionHelpContents",), LABELS),
        ("QGIS", (("@", ("mActionQgisHomePage", "mActionCheckQgisVersion", "mActionAbout")),), ("mActionAbout",),
         LABELS),
        ("Community", (("@", (
            "mActionReportaBug", "mActionGetInvolved", "mActionNeedSupport", "mActionDonate", "mActionSponsors")),),
         (), LABELS),
        ("More", (("menu", ("mHelpMenu",)),), (), LABELS),
    )),
)
# The tab shown when none was chosen yet.
DEFAULT_TAB = "Home"
# Menu items the ribbon leaves out: View > Toolbars (the ribbon stands for
# the toolbars) and submenus whose commands QGIS's tool buttons on the
# ribbon already offer (Measure, Select...).
SKIPPED_MENU_ITEMS = (
    "mToolbarMenu", "menuData_Filtering", "mMenuMeasure", "mMenuEditAttributes", "m3DMapViewsMenu",
    "mMenuElevationProfiles", "menuImport_Export",
    # Web > MetaSearch: its button is on the Web toolbar, its help in Help >
    # Plugins.
    "MetaSearch",
)
# Icons for commands QGIS gives none (studio_icons ICON_MAP names), by
# action or menu objectName; GENERIC_MENU_ICON for other icon-less menus.
ICON_FALLBACKS = {
    "mActionCloseProject": "ribbon/close.svg", "mActionExit": "ribbon/exit.svg",
    "mActionRevertProject": "ribbon/revert.svg", "mActionSnappingOptions": "ribbon/snapping.svg",
    "mActionDxfExport": "ribbon/export.svg", "mActionDwgImport": "ribbon/import.svg",
    "mProjectFromTemplateMenu": "ribbon/template.svg", "mRecentProjectsMenu": "ribbon/recent.svg",
    "mProjectFromStorageMenu": "ribbon/open-from.svg", "mProjectToStorageMenu": "ribbon/save-to.svg",
    "mLayoutsMenu": "ribbon/layouts.svg", "mMenuProjectModels": "ribbon/models.svg",
    "mMenuPasteAs": "ribbon/paste-as.svg", "mMenuAnnotation": "ribbon/annotation.svg",
    "mActionManage3DMapViews": "ribbon/manage.svg", "mActionManageElevationProfiles": "ribbon/manage.svg",
    "mMenuDecorations": "ribbon/decorations.svg", "mMenuPreviewMode": "ribbon/preview.svg",
    "mMenuLayerVisibility": "ribbon/preview.svg", "mPanelMenu": "ribbon/panels.svg",
    "mActionToggleFullScreen": "ribbon/full-screen.svg", "mActionTogglePanelsVisibility": "ribbon/panels.svg",
    "mActionToggleMapOnly": "ribbon/map-only.svg",
    "mAddLayerMenu": "ribbon/add-layer.svg", "mNewLayerMenu": "ribbon/create-layer.svg",
    "mActionEmbedLayers": "ribbon/embed.svg", "mActionAddLayerDefinition": "ribbon/layer-definition.svg",
    "mMenuFilterTable": "ribbon/filter.svg", "mActionLayerSaveAs": "ribbon/export.svg",
    "mActionSaveLayerDefinition": "ribbon/layer-definition.svg", "mActionSetLayerScaleVisibility": "ribbon/preview.svg",
    "mActionSetLayerCRS": "ribbon/crs.svg", "mActionSetProjectCRSFromLayer": "ribbon/project-crs.svg",
    "mActionLayerProperties": "ribbon/properties.svg", "mActionLayerSubsetString": "ribbon/filter.svg",
    "mUserProfileMenu": "ribbon/profiles.svg", "mActionShowMeshCalculator": "ribbon/calculator.svg",
    "mActionHelpAPI": "ribbon/docs.svg", "mActionHelpPyQgisAPI": "ribbon/docs.svg", "mMenuPluginHelp": "ribbon/docs.svg",
    "mActionReportaBug": "ribbon/bug.svg", "mActionDonate": "ribbon/donate.svg",
    "mActionGetInvolved": "ribbon/community.svg", "mActionNeedSupport": "ribbon/support.svg",
    "MetaSearch": "ribbon/web.svg",
}
GENERIC_MENU_ICON = "ribbon/tools.svg"
# The tab other toolbars (plugins') get a group on, and the toolbar whose
# actions are the buttons right of the tabs.
PLUGIN_TAB = "Plugins"
CORNER_TOOLBAR = "mHelpToolBar"

# Shorter labels than the actions' own (tooltips keep the full text), by
# objectName; for QGIS's tool buttons, the group's name for whichever tool
# is chosen.
LABELS_BY_NAME = {
    "mActionNewProject": "New", "mActionOpenProject": "Open", "mActionSaveProject": "Save",
    "mActionNewPrintLayout": "New Layout", "mActionShowLayoutManager": "Layouts",
    "mActionStyleManager": "Style Manager",
    "ActionSelect": "Select",
    "mActionIdentify": "Identify", "ActionOpenTable": "Attribute Table", "mActionOpenFieldCalc": "Field Calculator",
    "mActionStatisticalSummary": "Statistics", "mActionShowProcessingToolbox": "Toolbox",
    "ActionMeasure": "Measure", "mActionMapTips": "Map Tips", "ActionFeatureAction": "Actions",
    "mActionDataSourceManager": "Data Source Manager",
    "mActionAddOgrLayer": "Vector", "mActionAddRasterLayer": "Raster", "mActionAddMeshLayer": "Mesh",
    "mActionAddDelimitedText": "Delimited Text", "mActionAddSpatiaLiteLayer": "SpatiaLite",
    "mActionAddVirtualLayer": "Virtual", "ActionAddDbLayer": "Database", "mActionAddWmsLayer": "WMS/WMTS",
    "mActionAddWcsLayer": "WCS", "mActionAddWfsLayer": "WFS", "mActionAddStacLayer": "STAC",
    "ActionNewLayer": "Other Layer",
    "mActionNewGeoPackageLayer": "GeoPackage Layer", "mActionNewVectorLayer": "Shapefile",
    "mActionNewSpatiaLiteLayer": "SpatiaLite", "mActionNewMemoryLayer": "Scratch Layer",
    "mActionNewMeshLayer": "Mesh Layer", "mActionNewVirtualLayer": "Virtual Layer",
    "mActionToggleEditing": "Toggle Editing", "mActionSaveLayerEdits": "Save Edits", "mActionAllEdits": "All Edits",
    "mActionAddFeature": "Add Feature", "ActionVertexTool": "Vertex Tool", "mDigitizeModeToolButton": "Digitize Mode",
    "mActionMultiEditAttributes": "Edit Attributes", "mActionDeleteSelected": "Delete",
    "mActionCutFeatures": "Cut", "mActionCopyFeatures": "Copy", "mActionPasteFeatures": "Paste",
    "mActionUndo": "Undo", "mActionRedo": "Redo",
    "mEnableAction": "Advanced Digitizing",
    "ActionMoveFeatureTool": "Move", "mActionRotateFeature": "Rotate", "mActionScaleFeature": "Scale",
    "mActionSimplifyFeature": "Simplify", "mActionOffsetCurve": "Offset Curve", "mActionReverseLine": "Reverse Line",
    "mActionAddRing": "Add Ring", "mActionAddPart": "Add Part", "mActionFillRing": "Fill Ring",
    "mActionDeleteRing": "Delete Ring", "mActionDeletePart": "Delete Part",
    "mActionReshapeFeatures": "Reshape", "mActionChamferFillet": "Chamfer/Fillet",
    "mActionTrimExtendFeature": "Trim/Extend", "mActionSplitFeatures": "Split Features",
    "mActionSplitParts": "Split Parts", "mActionMergeFeatures": "Merge Features",
    "mActionMergeFeatureAttributes": "Merge Attributes", "ActionPointSymbolTools": "Point Symbols",
    "mActionLabeling": "Labels", "mActionDiagramProperties": "Diagrams",
    "mActionShowPinnedLabels": "Pinned Labels", "mActionShowUnplacedLabels": "Unplaced Labels",
    "mActionPinLabels": "Pin/Unpin", "mActionShowHideLabels": "Show/Hide", "mActionMoveLabel": "Move",
    "mActionRotateLabel": "Rotate", "mActionChangeLabelProperties": "Properties",
    "annotationLayerToolButtonAction": "Annotation Layer", "mActionSelectAnnotation": "Select",
    "mActionModifyAnnotation": "Edit Nodes", "ActionAnnotation": "Map Annotations",
    "mActionNewMapCanvas": "New Map View", "mActionNew3DMapCanvas": "New 3D Map View",
    "mActionNewBookmark": "New Bookmark", "mActionShowBookmarks": "Bookmarks",
    "mActionTemporalController": "Temporal Controller",
    "mActionShowRasterCalculator": "Raster Calculator", "mActionShowGeoreferencer": "Georeferencer",
    "mActionShowMeshCalculator": "Mesh Calculator",
    "mConnectAction": "Connect", "mRecenterAction": "Recenter",
    "mDestinationLayerButtonAction": "Destination Layer", "mAddTrackVertexAction": "Add Vertex",
    "mCreateFeatureAction": "Create Feature", "mResetFeatureAction": "Reset Track",
    "mShowInfoAction": "Information", "mSettingsMenuAction": "Settings",
    "mActionShowPythonDialog": "Python Console",
    # Menu commands and menus (by the menu's objectName).
    "mActionSaveProjectAs": "Save As", "mActionRevertProject": "Revert", "mActionCloseProject": "Close",
    "mActionExit": "Exit QGIS", "mProjectFromTemplateMenu": "From Template", "mRecentProjectsMenu": "Recent",
    "mProjectFromStorageMenu": "Open From", "mProjectToStorageMenu": "Save To",
    "mActionProjectProperties": "Properties", "mActionSnappingOptions": "Snapping Options",
    "mActionSaveMapAsImage": "Export Image", "mActionSaveMapAsPdf": "Export PDF", "mActionDxfExport": "Export DXF",
    "mActionDwgImport": "Import DWG/DXF", "mActionNewReport": "New Report", "mLayoutsMenu": "Open Layout",
    "mMenuProjectModels": "Project Models", "mMenuPasteAs": "Paste As",
    "mActionNew3DMapCanvasGlobe": "New 3D Globe", "mActionManage3DMapViews": "Manage 3D Views",
    "mActionShowBookmarkManager": "Bookmark Manager", "mActionElevationProfile": "Elevation Profile",
    "mActionManageElevationProfiles": "Manage Profiles", "mActionElevationController": "Elevation Controller",
    "mMenuDecorations": "Decorations", "mMenuPreviewMode": "Preview Mode", "mMenuLayerVisibility": "Layer Visibility",
    "mPanelMenu": "Panels", "mActionToggleFullScreen": "Full Screen", "mActionTogglePanelsVisibility": "Hide Panels",
    "mActionToggleMapOnly": "Map Only",
    "mAddLayerMenu": "All Layer Types", "mNewLayerMenu": "All New Layers", "mActionEmbedLayers": "Embed Layers",
    "mActionAddLayerDefinition": "Layer Definition", "mActionLayerProperties": "Layer Properties",
    "mActionLayerSubsetString": "Filter", "mActionDuplicateLayer": "Duplicate", "mActionSetLayerCRS": "Set Layer CRS",
    "mActionSetProjectCRSFromLayer": "Set Project CRS", "mActionSetLayerScaleVisibility": "Scale Visibility",
    "mActionLayerSaveAs": "Save As", "mActionSaveLayerDefinition": "Save as Definition",
    "mActionRemoveLayer": "Remove", "mActionCopyStyle": "Copy Style", "mActionPasteStyle": "Paste Style",
    "mActionCopyLayer": "Copy Layer", "mActionPasteLayer": "Paste Layer",
    "mActionAddToOverview": "Show in Overview", "mActionAddAllToOverview": "Show All",
    "mActionRemoveAllFromOverview": "Hide All", "mActionReindexMesh": "Reindex",
    "toolboxAction": "Toolbox", "modelerAction": "Model Designer", "historyAction": "History",
    "resultsViewer": "Results Viewer", "editInPlaceFeatures": "Edit In-Place", "optionsAction": "Options",
    "mActionManagePlugins": "Manage Plugins", "dbManager": "DB Manager", "mActionQueryHistory": "Query History",
    "mActionOptions": "Options", "mActionConfigureShortcuts": "Shortcuts", "mActionCustomization": "Customization",
    "mActionCustomProjection": "Custom CRS", "mUserProfileMenu": "User Profiles",
    "mActionHelpContents": "Help", "mActionHelpAPI": "C++ API", "mActionHelpPyQgisAPI": "PyQGIS API",
    "mMenuPluginHelp": "Plugin Help", "mActionQgisHomePage": "Home Page", "mActionCheckQgisVersion": "Check Version",
    "mActionAbout": "About", "mActionReportaBug": "Report Issue", "mActionGetInvolved": "Get Involved",
    "mActionNeedSupport": "Support", "mActionDonate": "Donate", "mActionSponsors": "Sponsors",
}
# Widgets QGIS puts on toolbars that the ribbon leaves out: the snapping
# widget's own container (its buttons and fields are on the ribbon).
SKIPPED_WIDGETS = ("QgsSnappingWidget",)


def clean(text):
    """An action's text as a label: no mnemonic, ellipsis or markup."""
    text = re.sub(r"<[^>]+>", "", (text or "").replace("&&", "\0").replace("&", "").replace("\0", "&"))
    return text.replace("…", "").replace("...", "").strip()


def two_lines(text):
    """A large button's label on at most two lines, broken at the space
    nearest the middle."""
    if len(text) <= 9 or " " not in text:
        return text
    middle = len(text) / 2
    spaces = [i for i, char in enumerate(text) if char == " "]
    cut = min(spaces, key=lambda i: abs(i - middle))
    return text[:cut] + "\n" + text[cut + 1:]


def _uses_widget_actions(menu):
    return menu is not None and any(isinstance(a, QWidgetAction) for a in menu.actions())


def _key(action):
    """An action's name in TABS and the tables above: its objectName, or for
    a menu's own action (which has none) the menu's."""
    if action.objectName():
        return action.objectName()
    menu = action.menu()
    return menu.objectName() if menu is not None else ""


class _Button(QToolButton):
    """A ribbon button. With a fixed `label`, it keeps it when its action
    changes (QToolButton takes the action's text again on every change)."""

    def __init__(self, kind, label="", parent=None):
        super().__init__(parent)
        self._label = label
        self._placeholder = None
        self.setProperty("studioRibbon", kind)
        self.setAutoRaise(True)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def actionEvent(self, event):  # pylint: disable=invalid-name
        super().actionEvent(event)
        if event.type() != QEvent.Type.ActionChanged:
            return
        if self._label and self.text() != self._label:
            self.setText(self._label)
        if self._placeholder is not None and self.icon().isNull():
            self.setIcon(self._placeholder)

    def set_placeholder(self, size):
        """An empty icon for an action without one, so its label lines up
        with its neighbours'."""
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        self._placeholder = QIcon(pixmap)
        self.setIcon(self._placeholder)

    def set_label(self, label):
        self._label = label
        if label:
            self.setText(label)


class _BorrowingMenu(QMenu):
    """A menu showing another menu's actions while it is open. A menu
    holding widgets (QWidgetAction: a spin box...) closes again at once when
    shown for a button other than its own, and a widget can only be in one
    menu: the actions move here while this one is open and go back when it
    closes."""

    def __init__(self, source, parent):
        super().__init__(parent)
        self._source = source
        self._borrowed = []
        self.aboutToShow.connect(self._borrow)
        self.aboutToHide.connect(lambda: QTimer.singleShot(0, self._give_back))

    def _borrow(self):
        if self._borrowed or sip.isdeleted(self._source):
            return
        self._borrowed = self._source.actions()
        for action in self._borrowed:
            self._source.removeAction(action)
        self.addActions(self._borrowed)

    def _give_back(self):
        if sip.isdeleted(self) or sip.isdeleted(self._source) or not self._borrowed:
            return
        for action in self._borrowed:
            self.removeAction(action)
        self._source.addActions(self._borrowed)
        self._borrowed = []


class _Tabs(QTabBar):
    """The ribbon's tabs: the current one's name underlined in the accent
    (the palette's Link colour), as wide as the name, which a stylesheet
    cannot size."""

    UNDERLINE = 2
    GAP = 3  # between the underline and the tab's bottom edge

    def paintEvent(self, event):  # pylint: disable=invalid-name
        super().paintEvent(event)
        index = self.currentIndex()
        if index < 0:
            return
        tab = self.tabRect(index)
        width = self.fontMetrics().horizontalAdvance(self.tabText(index)) + 4
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.palette().color(QPalette.ColorRole.Link))
        y = tab.bottom() + 1 - self.GAP - self.UNDERLINE
        painter.drawRoundedRect(tab.center().x() + 1 - width // 2, y, width, self.UNDERLINE, 1, 1)
        painter.end()


class Ribbon(QWidget):
    """The tabs and the current page (see the module docstring). Pages
    are built by `build(index, page)` when first shown and after
    invalidate()."""

    def __init__(self, titles, build, corner, parent=None):
        super().__init__(parent)
        self.setObjectName("studioRibbon")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._build = build
        self._built = set()
        # A page's height (see page_height), set by the ribbon's owner.
        self.page_height = page_height(studio_toolbars.title_font())
        layout = QVBoxLayout(self)
        # Room under the page for the ribbon's bottom line (none when
        # collapsed: the tab row's line closes the ribbon off then).
        layout.setContentsMargins(0, 0, 0, 1)
        layout.setSpacing(0)
        # The tab row draws the line over the page; the current tab, a
        # child drawn after it, covers the line where it opens into the page.
        bar = QWidget()
        bar.setObjectName("studioRibbonBar")
        bar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        top = QHBoxLayout(bar)
        # Room above the tabs: the ribbon is the window's top row.
        top.setContentsMargins(6, 5, 6, 0)
        top.setSpacing(2)
        self.tabs = _Tabs()
        self.tabs.setObjectName("studioRibbonTabs")
        self.tabs.setDrawBase(False)
        self.tabs.setExpanding(False)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for title in titles:
            self.tabs.addTab(title)
        top.addWidget(self.tabs, 0, Qt.AlignmentFlag.AlignBottom)
        top.addStretch(1)
        # Help and collapse centred on the tabs' names, which sit below
        # the row's middle (the tabs' top margin).
        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, TAB_TOP, 0, 0)
        buttons.setSpacing(2)
        buttons.addWidget(corner)
        self.collapse = QToolButton()
        self.collapse.setObjectName("studioRibbonCollapse")
        self.collapse.setAutoRaise(True)
        self.collapse.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.collapse.setCheckable(True)
        self.collapse.setToolTip("Collapse the ribbon to its tabs (double-click a tab)")
        self.collapse.toggled.connect(self.set_collapsed)
        buttons.addWidget(self.collapse)
        top.addLayout(buttons)
        layout.addWidget(bar)
        self.pages = QStackedWidget()
        self.pages.setObjectName("studioRibbonPages")
        for _title in titles:
            page = QScrollArea()
            page.setObjectName("studioRibbonPage")
            page.setFrameShape(QFrame.Shape.NoFrame)
            page.setWidgetResizable(True)
            # No scroll bar: the ribbon keeps one height (a change would lay
            # the whole window out again); the wheel scrolls a wide page.
            page.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            page.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.pages.addWidget(page)
        layout.addWidget(self.pages)
        self.tabs.currentChanged.connect(self._show_page)
        self.tabs.tabBarDoubleClicked.connect(lambda _index: self.collapse.toggle())
        self.tabs.tabBarClicked.connect(self._tab_clicked)

    def show_tab(self, index):
        index = max(0, min(index, self.tabs.count() - 1))
        if self.tabs.currentIndex() != index:
            self.tabs.setCurrentIndex(index)
        else:
            self._show_page(index)

    def invalidate(self, index):
        """The page's toolbars changed: built again now if it shows, else
        when it is next shown."""
        self._built.discard(index)
        if index == self.tabs.currentIndex():
            self._show_page(index)

    def _show_page(self, index):
        if index < 0:
            return
        page = self.pages.widget(index)
        if index not in self._built:
            self._built.add(index)
            old = page.takeWidget()
            content = self._build(index, old)
            page.setWidget(content)
        self.pages.setCurrentIndex(index)
        self._fit_height()

    def _tab_clicked(self, _index):
        # Collapsed: a tab shows its page again.
        if self.collapse.isChecked():
            self.collapse.setChecked(False)

    def set_collapsed(self, collapsed):
        if self.collapse.isChecked() != collapsed:
            self.collapse.setChecked(collapsed)
            return
        self.collapse.setProperty("collapsed", "true" if collapsed else None)
        self.collapse.style().unpolish(self.collapse)
        self.collapse.style().polish(self.collapse)
        # Collapsed, the current tab opens into no page: a plain tab, its
        # name still underlined (style.qss, [collapsed]).
        self.tabs.setProperty("collapsed", "true" if collapsed else None)
        self.tabs.style().unpolish(self.tabs)
        self.tabs.style().polish(self.tabs)
        self.layout().setContentsMargins(0, 0, 0, 0 if collapsed else 1)
        self.pages.setVisible(not collapsed)
        self._fit_height()

    def wheelEvent(self, event):  # pylint: disable=invalid-name
        """The wheel scrolls a page wider than the window sideways."""
        page = self.pages.currentWidget()
        bar = page.horizontalScrollBar() if page is not None else None
        if bar is None or bar.maximum() <= 0:
            super().wheelEvent(event)
            return
        delta = event.angleDelta().y() or event.angleDelta().x()
        bar.setValue(bar.value() - delta)
        event.accept()

    def _fit_height(self):
        """The pages' one height (see page_height)."""
        if self.pages.height() != self.page_height or self.pages.minimumHeight() != self.page_height:
            self.pages.setFixedHeight(self.page_height)


def set_menu_bar_folded(window, folded):
    """The menu bar folded away while the ribbon shows (its commands are on
    the ribbon's tabs): no height and no line (style.qss,
    QMenuBar[studioRibbon]). Not hidden: Alt with a menu's letter (Alt+P
    for Project...) opens it only from a visible menu bar."""
    menu_bar = window.menuBar()
    if menu_bar is None or bool(menu_bar.property("studioRibbon")) == folded:
        return
    menu_bar.setProperty("studioRibbon", True if folded else None)
    menu_bar.style().unpolish(menu_bar)
    menu_bar.style().polish(menu_bar)
    # After polishing, which restores the size limits a stylesheet saw.
    menu_bar.setMaximumHeight(0 if folded else QWIDGETSIZE_MAX)


def page_height(caption_font):
    """A page's height: a group's buttons, margins and caption."""
    caption = QFontMetrics(caption_font).height()
    return GROUP_MARGINS[1] + BODY + SPACING + caption + GROUP_MARGINS[3]


class StudioRibbon(QObject):
    """Shows the ribbon in place of the main window's toolbars and keeps it
    up to date (see the module docstring)."""

    WINDOW_EVENTS = (QEvent.Type.ChildPolished,)
    MENU_BAR_EVENTS = (QEvent.Type.StyleChange, QEvent.Type.ActionAdded, QEvent.Type.ActionRemoved)
    MENU_EVENTS = (QEvent.Type.ActionAdded, QEvent.Type.ActionRemoved)
    TOOLBAR_EVENTS = (QEvent.Type.ActionAdded, QEvent.Type.ActionRemoved, QEvent.Type.ActionChanged)

    def __init__(self, iface, hub, icons=None):
        super().__init__()
        self._iface = iface
        self._hub = hub
        # The plugin's IconSwapper: the theme's icons for the commands
        # placed (swap_action), also those QGIS gives none (adopt); the
        # actions given one.
        self._icons = icons
        self._adopted = []
        self._window = None
        self._host = None
        self._ribbon = None
        # Toolbars hidden for the ribbon (by objectName, so they survive a
        # session), toolbars watched, and the tab index of each toolbar's
        # groups (QGIS's own; others are on PLUGIN_TAB).
        self._hidden = []
        self._watched = []
        self._tab_of = {}
        # The tab indexes of each menu whose items a group shows ("menu"
        # sources), the menus watched, and every name TABS places itself.
        self._menu_tabs = {}
        self._menus = {}
        self._placed_names = set()
        for index, (_title, groups) in enumerate(TABS):
            for group in groups:
                for source, names in group[1]:
                    if source == "menu":
                        for name in names:
                            self._menu_tabs.setdefault(name, set()).add(index)
                        continue
                    self._placed_names.update(names or ())
                    if source != "@":
                        self._tab_of.setdefault(source, set()).add(index)
        # Actions named in TABS, per toolbar: a group listing none takes
        # the others.
        self._named = {}
        for _title, groups in TABS:
            for group in groups:
                for toolbar, names in group[1]:
                    if toolbar not in ("@", "menu"):
                        self._named.setdefault(toolbar, set()).update(names or ())
        # Names already on the ribbon while a page is built (see _covered).
        self._covered = set()
        # Widgets borrowed from toolbars: [(widget, toolbar, action)].
        self._borrowed = []
        # Action visibility as last seen, by C++ object (ActionChanged is
        # frequent; only a visibility change changes a page). Python ids
        # are no keys: QGIS's objects get a new wrapper on each access.
        self._visible = {}
        self._dirty = set()
        # The actions on the ribbon (by C++ object), as last built.
        self.placed = set()
        self._caption_font = studio_toolbars.title_font()
        self._corner = None

    @property
    def active(self):
        return self._ribbon is not None

    def set_caption_font(self, size, weight):
        """The groups' captions: the toolbar names' font (the settings')."""
        font = studio_toolbars.title_font(size, weight)
        if font == self._caption_font:
            return
        self._caption_font = font
        if self._ribbon is not None:
            self._ribbon.page_height = page_height(self._caption_font)
            for index in range(self._ribbon.tabs.count()):
                self._ribbon.invalidate(index)

    # ---- Showing and hiding -----------------------------------------------

    def activate(self):
        if self._ribbon is not None:
            return
        window = self._iface.mainWindow()
        self._window = window
        self._hidden = []
        hidden_before = QgsSettings().value(HIDDEN_SETTING, [], type=list) or []
        for toolbar in self._toolbars():
            if toolbar.isVisible() or toolbar.objectName() in hidden_before:
                self._hidden.append(toolbar.objectName())
            toolbar.hide()
        QgsSettings().setValue(HIDDEN_SETTING, self._hidden)
        for toolbar in self._toolbars():
            self._watch(toolbar)
        self._hub.watch(window, self, self.WINDOW_EVENTS, self._window_event)
        self._corner = QWidget()
        self._corner.setObjectName("studioRibbonCorner")
        corner_layout = QHBoxLayout(self._corner)
        corner_layout.setContentsMargins(0, 0, 0, 0)
        corner_layout.setSpacing(2)
        self._watch_menus()
        self._ribbon = Ribbon([title for title, _groups in TABS], self._build_page, self._corner)
        self._ribbon.page_height = page_height(self._caption_font)
        self._fill_corner()
        host = self._host = QToolBar("Ribbon", window)
        host.setObjectName(HOST_NAME)
        host.setMovable(False)
        host.setFloatable(False)
        host.setContextMenuPolicy(Qt.ContextMenuPolicy.PreventContextMenu)
        host.toggleViewAction().setVisible(False)
        host.addWidget(self._ribbon)
        first = next((t for t in self._toolbars() if window.toolBarArea(t) == Qt.ToolBarArea.TopToolBarArea), None)
        if first is not None:
            window.insertToolBar(first, host)
            window.insertToolBarBreak(first)
        else:
            window.addToolBar(Qt.ToolBarArea.TopToolBarArea, host)
        host.show()
        set_menu_bar_folded(window, True)
        if window.menuBar() is not None:
            self._hub.watch(window.menuBar(), self, self.MENU_BAR_EVENTS, self._menu_bar_event)
        settings = QgsSettings()
        self._ribbon.set_collapsed(settings.value(COLLAPSED_SETTING, False, type=bool))
        # The tab by its title (before 1.2's last tabs: by its index).
        titles = [title for title, _groups in TABS]
        tab = settings.value(TAB_SETTING, DEFAULT_TAB, type=str)
        self._ribbon.show_tab(titles.index(tab if tab in titles else DEFAULT_TAB))
        self._ribbon.tabs.currentChanged.connect(lambda index: QgsSettings().setValue(TAB_SETTING, titles[index]))
        self._ribbon.collapse.toggled.connect(lambda collapsed: QgsSettings().setValue(COLLAPSED_SETTING, collapsed))

    def deactivate(self, forget=False):
        """Hide the ribbon and show the toolbars it hid. Only `forget` (the
        ribbon turned off in the settings) forgets which: on QGIS's exit the
        plugin is unloaded after QGIS saved the toolbars hidden, so the next
        session must know to show them again."""
        if self._ribbon is None:
            return
        window = self._window
        self._give_back()
        if not sip.isdeleted(window):
            self._hub.unwatch(window, self)
            if window.menuBar() is not None:
                self._hub.unwatch(window.menuBar(), self)
            set_menu_bar_folded(window, False)
        for toolbar in self._watched:
            if not sip.isdeleted(toolbar):
                self._hub.unwatch(toolbar, self)
        self._watched = []
        for menu in self._menus.values():
            if not sip.isdeleted(menu):
                self._hub.unwatch(menu, self)
        self._menus = {}
        # Icons given for the ribbon go: QGIS's menus show none there.
        for action in self._adopted:
            if not sip.isdeleted(action):
                action.setIcon(QIcon())
        self._adopted = []
        if self._host is not None and not sip.isdeleted(self._host):
            window.removeToolBar(self._host)
            self._host.hide()
            self._host.deleteLater()
        self._host = None
        self._ribbon = None
        self._corner = None
        hidden = set(self._hidden)
        for toolbar in self._toolbars():
            if toolbar.objectName() in hidden:
                toolbar.show()
        self._hidden = []
        self._visible = {}
        self._dirty = set()
        if forget:
            QgsSettings().remove(HIDDEN_SETTING)

    def _toolbars(self):
        """The main window's toolbars (its own children: a search of every
        widget below it would take far longer), not the ribbon's."""
        window = self._window or self._iface.mainWindow()
        return [t for t in window.findChildren(QToolBar, options=Qt.FindChildOption.FindDirectChildrenOnly)
                if t.objectName() != HOST_NAME]

    def _watch(self, toolbar):
        if toolbar in self._watched:
            return
        self._watched.append(toolbar)
        self._hub.watch(toolbar, self, self.TOOLBAR_EVENTS, self._toolbar_event)
        for action in toolbar.actions():
            self._visible[sip.unwrapinstance(action)] = action.isVisible()

    # ---- Changes ----------------------------------------------------------

    def _window_event(self, watched, event):
        """A toolbar added to the main window (a plugin's): hidden, and on
        the ribbon."""
        child = event.child()
        if (isinstance(child, QToolBar) and child.parent() is watched and child.objectName() != HOST_NAME
                and child not in self._watched):
            self._watch(child)
            if child.objectName() and child.objectName() not in self._hidden:
                self._hidden.append(child.objectName())
                QgsSettings().setValue(HIDDEN_SETTING, self._hidden)
            QTimer.singleShot(0, lambda toolbar=child: self._hide_new(toolbar))
            self._changed(child)

    def _menu_bar_event(self, menu_bar, event):
        """A stylesheet change (a theme switch) gives the menu bar its size
        limits back: folded again once it is polished. A menu added or
        removed (a plugin's): on the Plugins tab, or a menu TABS shows that
        was missing until now (Processing's)."""
        if event.type() != QEvent.Type.StyleChange:
            self._watch_menus()
            self._mark({self._tab_index(PLUGIN_TAB)})
            return
        if menu_bar.maximumHeight() != 0:
            QTimer.singleShot(0, lambda: self._fold_again(menu_bar))

    def _watch_menus(self):
        """Watch the menus whose items groups show, once they exist; a
        page showing one found only now is built again."""
        if self._window is None:
            return
        for name, indexes in self._menu_tabs.items():
            menu = self._menus.get(name)
            if menu is not None and not sip.isdeleted(menu):
                continue
            # A plugin's menu may have no parent (Processing's): found
            # through the menu bar.
            menu_bar = self._window.menuBar()
            menu = next((a.menu() for a in (menu_bar.actions() if menu_bar is not None else ())
                         if a.menu() is not None and a.menu().objectName() == name), None)
            menu = menu or self._window.findChild(QMenu, name)
            if menu is None:
                continue
            self._menus[name] = menu
            self._hub.watch(menu, self, self.MENU_EVENTS, self._menu_event)
            self._mark(indexes)

    def _menu_event(self, menu, _event):
        """A command added to or removed from a menu groups show."""
        self._mark(self._menu_tabs.get(menu.objectName(), set()))

    def _fold_again(self, menu_bar):
        if self._ribbon is not None and not sip.isdeleted(menu_bar):
            menu_bar.setMaximumHeight(0)

    def _hide_new(self, toolbar):
        # After the plugin shows it (addToolBar shows toolbars it adds).
        if self._ribbon is not None and not sip.isdeleted(toolbar):
            toolbar.hide()

    def _toolbar_event(self, watched, event):
        if event.type() == QEvent.Type.ActionChanged:
            action = event.action()
            visible = action.isVisible()
            key = sip.unwrapinstance(action)
            if self._visible.get(key) is visible:
                return
            self._visible[key] = visible
        elif event.type() == QEvent.Type.ActionAdded:
            self._visible[sip.unwrapinstance(event.action())] = event.action().isVisible()
        self._changed(watched)

    def _changed(self, toolbar):
        """A toolbar's actions changed: its tabs are built again, once the
        changes of this event-loop pass are done."""
        if self._ribbon is None:
            return
        name = toolbar.objectName()
        if name == CORNER_TOOLBAR:
            indexes = {-1}
        else:
            indexes = self._tab_of.get(name) or {self._tab_index(PLUGIN_TAB)}
        self._mark(indexes)

    def _mark(self, indexes):
        """Tabs (-1: the corner) built again once this event-loop pass's
        changes are done."""
        if self._ribbon is None or not indexes:
            return
        if not self._dirty:
            QTimer.singleShot(0, self._rebuild)
        self._dirty.update(indexes)

    def _rebuild(self):
        dirty, self._dirty = self._dirty, set()
        if self._ribbon is None:
            return
        for index in dirty:
            if index == -1:
                self._fill_corner()
            else:
                self._ribbon.invalidate(index)

    @staticmethod
    def _tab_index(title):
        return next(i for i, (name, _groups) in enumerate(TABS) if name == title)

    # ---- Building pages ---------------------------------------------------

    def _build_page(self, index, old):
        """The page of tab `index`: its groups, and on PLUGIN_TAB a group
        per toolbar TABS does not place and one for the menus plugins add to
        the menu bar. `old`, the page it replaces, gives back the widgets it
        borrowed."""
        if old is not None:
            self._give_back(old)
            old.deleteLater()
        content = QWidget()
        content.setObjectName("studioRibbonContent")
        layout = QHBoxLayout(content)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(0)
        title, groups = TABS[index]
        all_toolbars = self._toolbars()
        toolbars = {t.objectName(): t for t in all_toolbars if t.objectName()}
        # What "menu" sources leave out: what TABS places, every toolbar's
        # actions (on some tab) and SKIPPED_MENU_ITEMS; and, by C++ object,
        # what this page shows already.
        self._covered = self._placed_names | set(SKIPPED_MENU_ITEMS) | {
            a.objectName() for t in all_toolbars for a in t.actions() if a.objectName()}
        seen = set()
        for group in groups:
            widget = self._group(content, group, toolbars, seen)
            if widget is not None:
                layout.addWidget(widget)
        if title == PLUGIN_TAB:
            for toolbar in all_toolbars:
                name = toolbar.objectName()
                if name in self._tab_of or name == CORNER_TOOLBAR:
                    continue
                spec = (toolbar.windowTitle() or name or "Plugin", ((toolbar, None),), (), AUTO)
                widget = self._group(content, spec, toolbars, seen)
                if widget is not None:
                    layout.addWidget(widget)
            menu_bar = self._window.menuBar()
            extra = [] if menu_bar is None else [
                a for a in menu_bar.actions() if a.menu() is not None and a.menu().objectName() not in self._menu_tabs]
            widget = self._group(content, ("Menus", (("actions", extra),), (), LABELS), toolbars, seen)
            if widget is not None:
                layout.addWidget(widget)
        layout.addStretch(1)
        # Never squeezed (large buttons' labels would be cut short): a page
        # wider than the window scrolls with the wheel (Ribbon.wheelEvent).
        content.setMinimumWidth(content.sizeHint().width())
        return content

    def _actions(self, sources, toolbars, seen):
        """[(action, toolbar or None)] of a group's sources, in order."""
        found = []
        for name, names in sources:
            if name == "@":
                for action_name in names:
                    action = self._window.findChild(QAction, action_name)
                    if action is None:
                        menu = self._window.findChild(QMenu, action_name)
                        action = menu.menuAction() if menu is not None else None
                    if action is not None:
                        found.append((action, None))
                continue
            if name == "actions":
                found += [(action, None) for action in names]
                continue
            if name == "menu":
                for menu_name in names:
                    menu = self._menus.get(menu_name)
                    if menu is None or sip.isdeleted(menu):
                        continue
                    for action in menu.actions():
                        if (action.isSeparator() or isinstance(action, QWidgetAction)
                                or _key(action) in self._covered or sip.unwrapinstance(action) in seen):
                            continue
                        found.append((action, None))
                continue
            toolbar = name if isinstance(name, QToolBar) else toolbars.get(name)
            if toolbar is None:
                continue
            actions = [a for a in toolbar.actions() if not a.isSeparator()]
            if names is None:
                named = self._named.get(toolbar.objectName(), set()) if toolbar.objectName() else set()
                found += [(a, toolbar) for a in actions if a.objectName() not in named or not a.objectName()]
            else:
                by_name = {}
                for action in actions:
                    by_name.setdefault(action.objectName(), action)
                found += [(by_name[n], toolbar) for n in names if n in by_name]
        return [(a, t) for a, t in found if a.isVisible()]

    def _group(self, parent, spec, toolbars, seen):
        title, sources, large_names, layout_kind = spec[:4]
        rows = spec[4] if len(spec) > 4 else None
        entries = self._actions(sources, toolbars, seen)
        if not entries:
            return None
        seen.update(sip.unwrapinstance(action) for action, _toolbar in entries)
        large_all = layout_kind == AUTO and len(entries) <= AUTO_LARGE
        if layout_kind == AUTO:
            layout_kind = ICONS
        group = QFrame(parent)
        group.setObjectName("studioRibbonGroup")
        outer = QVBoxLayout(group)
        outer.setContentsMargins(*GROUP_MARGINS)
        outer.setSpacing(SPACING)
        body = QHBoxLayout()
        body.setSpacing(SPACING)
        body.setContentsMargins(0, 0, 0, 0)
        small = []
        for action, toolbar in entries:
            large = large_all or _key(action) in large_names
            widget = self._widget(group, action, toolbar, "large" if large else (
                "small" if layout_kind == LABELS else "icon"))
            if widget is None:
                continue
            if large:
                body.addWidget(widget, 0, Qt.AlignmentFlag.AlignTop)
            else:
                small.append((_key(action), widget))
        if small:
            grid = QGridLayout()
            grid.setContentsMargins(0, 0, 0, 0)
            grid.setHorizontalSpacing(SPACING if layout_kind == ICONS else 4)
            grid.setVerticalSpacing(SPACING)
            placed = set()
            if rows:
                by_name = {}
                for name, widget in small:
                    by_name.setdefault(name, []).append(widget)
                for row, names in enumerate(rows):
                    for column, name in enumerate(names):
                        if by_name.get(name):
                            widget = by_name[name].pop(0)
                            grid.addWidget(widget, row, column, Qt.AlignmentFlag.AlignLeft)
                            placed.add(id(widget))
            rest = [w for _n, w in small if id(w) not in placed]
            start = grid.columnCount() if placed else 0
            for i, widget in enumerate(rest):
                grid.addWidget(widget, i % ROWS, start + i // ROWS, Qt.AlignmentFlag.AlignLeft)
            for row in range(ROWS):
                grid.setRowMinimumHeight(row, ROW_HEIGHT)
            body.addLayout(grid)
            body.setAlignment(grid, Qt.AlignmentFlag.AlignTop)
        if body.count() == 0:
            group.deleteLater()
            return None
        outer.addLayout(body)
        outer.addStretch(1)
        caption = QLabel(title.upper(), group)
        caption.setObjectName("studioRibbonCaption")
        caption.setFont(self._caption_font)
        caption.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        outer.addWidget(caption)
        return group

    def _widget(self, parent, action, toolbar, kind):
        """The ribbon's widget for an action: a button for it, a clone of
        QGIS's tool button, or the toolbar's widget, borrowed; None for
        widgets left out."""
        shown = toolbar.widgetForAction(action) if toolbar is not None else None
        self.placed.add(sip.unwrapinstance(action))
        if isinstance(shown, QToolButton) and shown.defaultAction() is not action:
            return self._clone(parent, action, shown, kind)
        if shown is not None and not isinstance(shown, QToolButton):
            return self._borrow(parent, action, toolbar, shown)
        if isinstance(action, QWidgetAction) and shown is None and toolbar is not None:
            return None
        button = _Button(kind, parent=parent)
        button.setDefaultAction(action)
        if isinstance(shown, QToolButton):
            button.setPopupMode(shown.popupMode())
        elif action.menu() is not None:
            button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        if _uses_widget_actions(action.menu()):
            button.setMenu(_BorrowingMenu(action.menu(), button))
        if action.icon().isNull():
            self._give_icon(button, action, kind)
        elif self._icons is not None:
            self._icons.swap_action(action)
        self._style(button, kind, LABELS_BY_NAME.get(_key(action)) or clean(action.text()))
        return button

    def _give_icon(self, button, action, kind):
        """A command QGIS gives no icon (most only in its menus): one of the
        theme's (ICON_FALLBACKS), or an empty one keeping labels in line."""
        name = ICON_FALLBACKS.get(_key(action)) or (GENERIC_MENU_ICON if action.menu() is not None else None)
        if name is not None and self._icons is not None and self._icons.adopt(action, name):
            self._adopted.append(action)
        elif kind != "icon":
            button.set_placeholder(LARGE_ICON if kind == "large" else SMALL_ICON)

    def _clone(self, parent, action, source, kind):
        """A button standing for one of QGIS's tool buttons (a tool picked
        from its menu becomes its default): the same tools, the chosen one
        passed back to QGIS's button (its own handler remembers it)."""
        button = _Button(kind, parent=parent)
        menu = source.menu()
        if menu is not None:
            button.setMenu(_BorrowingMenu(menu, button) if _uses_widget_actions(menu) else menu)
        else:
            button.addActions(source.actions())
        button.setPopupMode(source.popupMode())
        default = source.defaultAction()
        if default is not None:
            button.setDefaultAction(default)
        else:
            button.setIcon(source.icon())
            button.setToolTip(source.toolTip())
            button.clicked.connect(source.click)

        def chosen(picked, button=button, source=source):
            if sip.isdeleted(source) or sip.isdeleted(button):
                return
            if picked is not source.defaultAction():
                source.triggered.emit(picked)
            current = source.defaultAction()
            if current is not None and button.defaultAction() is not current:
                button.setDefaultAction(current)
                button.set_label(button._label)  # pylint: disable=protected-access

        button.triggered.connect(chosen)
        label = LABELS_BY_NAME.get(action.objectName()) or clean(default.text() if default else source.toolTip())
        self._style(button, kind, label)
        return button

    def _borrow(self, parent, action, toolbar, widget):
        """A toolbar's own widget (a spin box, a combo box...), moved here
        while the ribbon shows; None for SKIPPED_WIDGETS and empty ones."""
        if widget.metaObject().className() in SKIPPED_WIDGETS or widget.sizeHint().width() <= 0:
            return None
        for entry in self._borrowed:
            if entry[0] is widget:
                self._borrowed.remove(entry)
                break
        self._borrowed.append((widget, toolbar, action))
        widget.setParent(parent)
        widget.setFixedHeight(ROW_HEIGHT)
        widget.show()
        return widget

    def _give_back(self, page=None):
        """Widgets borrowed (on `page`, or all) go back to their toolbars."""
        keep = []
        for widget, toolbar, action in self._borrowed:
            if sip.isdeleted(widget) or sip.isdeleted(toolbar):
                continue
            if page is not None and not page.isAncestorOf(widget):
                keep.append((widget, toolbar, action))
                continue
            widget.setParent(toolbar)
            widget.setMinimumHeight(0)
            widget.setMaximumHeight(16777215)
            widget.setVisible(action.isVisible())
            if toolbar.layout() is not None:
                toolbar.layout().invalidate()
        self._borrowed = keep

    @staticmethod
    def _style(button, kind, label):
        if kind == "large":
            button.setIconSize(QSize(LARGE_ICON, LARGE_ICON))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.set_label(two_lines(label))
            button.setFixedHeight(BODY)
            button.setMinimumWidth(LARGE_MIN_WIDTH)
        elif kind == "small":
            button.setIconSize(QSize(SMALL_ICON, SMALL_ICON))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            button.set_label(label)
            button.setFixedHeight(ROW_HEIGHT)
        else:
            button.setIconSize(QSize(SMALL_ICON, SMALL_ICON))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            button.setFixedHeight(ROW_HEIGHT)
            button.setMinimumWidth(ROW_HEIGHT + 4)

    def _fill_corner(self):
        """The Help toolbar's buttons right of the tabs."""
        if self._corner is None:
            return
        layout = self._corner.layout()
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        toolbar = next((t for t in self._toolbars() if t.objectName() == CORNER_TOOLBAR), None)
        if toolbar is None:
            return
        for action in toolbar.actions():
            if action.isSeparator() or not action.isVisible():
                continue
            widget = self._widget(self._corner, action, toolbar, "icon")
            if widget is not None:
                layout.addWidget(widget)

