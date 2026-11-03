"""Modern icon set for QGIS, built from Tabler outline glyphs.

Every entry maps a QGIS theme icon file name (as passed to
QgsApplication.getThemeIcon) to a Tabler glyph, optionally followed by a
badge: ``"glyph+badge"``, drawn bottom-right in place of QGIS's mixed
per-icon decorations: a small mark in the icon's own colour for what the
action does (+ add or new, - remove from, a check mark for save or
accept), a red dot for delete, and an accent dot for an "active" variant.

Icons are rendered per theme into the profile theme folder, where QGIS's
own icon lookup (QgsApplication.iconPath) finds them.

Those SVGs scale to any size, which costs sharpness: Tabler's lines sit on
whole units of a 24 unit grid, and once enlarged and drawn at 16 or 20 px
they fall between device pixels, so each 1 px line is smeared over two
grey ones. For the sizes widgets actually ask for, render_icon_px instead
draws every glyph in device pixels with its points moved onto the pixel
grid and a stroke of whole pixels, like a hand-hinted icon: straight lines
come out solid and sharp. Those are pre-rendered as PNGs (see the plugin).
"""
import functools
import math
import re
from pathlib import Path

GLYPHS_DIR = Path(__file__).parent / "icons" / "tabler"

ICON_MAP = {
    # ---- Project / files --------------------------------------------------
    "mActionFileNew.svg": "file+star",
    "mActionFileOpen.svg": "folder-open",
    "mActionFileSave.svg": "device-floppy",
    "mActionFileSaveAs.svg": "file-export",
    "mActionNewLayout.svg": "layout+star",
    "mActionNewReport.svg": "report+star",
    "mActionLayoutManager.svg": "layout-board",
    "mActionStyleManager.svg": "palette",
    "mActionProjectProperties.svg": "file-settings",
    "mActionSaveAsPDF.svg": "file-type-pdf",
    "mActionSaveMapAsImage.svg": "photo-down",
    "mActionOptions.svg": "settings",
    "mActionInterfaceCustomization.svg": "layout-dashboard",
    "mActionKeyboardShortcuts.svg": "keyboard",
    "mActionShowPluginManager.svg": "puzzle",
    "mActionCustomProjection.svg": "world-cog",
    "mActionSharing.svg": "share",
    "mActionHelpContents.svg": "help-circle",
    "mActionHelpAbout.svg": "info-square-rounded",
    "mActionHelpSponsors.png": "heart",
    "mActionQgisHomePage.png": "world-www",
    "console/mIconRunConsole.svg": "brand-python",
    "mMessageLog.svg": "message-report",
    "user.svg": "user",
    "search.svg": "search",
    "lockedGray.svg": "lock",
    "mIconClose.svg": "x",
    "mIconSuccess.svg": "circle-check",
    "mIconCollapse.svg": "chevron-up",
    "mIconExpand.svg": "chevron-down",
    # ---- Data sources -----------------------------------------------------
    "mActionDataSourceManager.svg": "database",
    "mActionAddOgrLayer.svg": "vector-triangle+plus",
    "mActionAddRasterLayer.svg": "photo+plus",
    "mActionAddMeshLayer.svg": "triangle-square-circle+plus",
    "mActionAddDelimitedTextLayer.svg": "file-type-csv+plus",
    "mActionAddSpatiaLiteLayer.svg": "feather+plus",
    "mActionAddVirtualLayer.svg": "sql-raised+plus",
    "mActionAddPostgisLayer.svg": "database+plus",
    "mActionAddMssqlLayer.svg": "database+plus",
    "mActionAddHanaLayer.svg": "database+plus",
    "mActionAddWmsLayer.svg": "world+plus",
    "mActionAddWcsLayer.svg": "world-download",
    "mActionAddWfsLayer.svg": "world-share",
    "mActionAddAfsLayer.svg": "cloud+plus",
    "mActionAddXyzLayer.svg": "map-2+plus",
    "mActionAddVectorTileLayer.svg": "layout-grid+plus",
    "mActionAddStacLayer.svg": "stack-3+plus",
    "mActionNewVectorLayer.svg": "shp-raised+star",
    "mActionNewGeoPackageLayer.svg": "package+star",
    "mActionNewSpatiaLiteLayer.svg": "feather+star",
    "mActionCreateMemory.svg": "cpu+star",
    "mActionNewMeshLayer.svg": "triangle-square-circle+star",
    "mActionNewVirtualLayer.svg": "sql-raised+star",
    # ---- Layers panel -----------------------------------------------------
    "mActionAddGroup.svg": "box-multiple+plus",
    "mActionRemoveLayer.svg": "stack-2+x",
    "mActionDuplicateLayer.svg": "copy",
    "mActionShowAllLayers.svg": "eye",
    "mActionHideAllLayers.svg": "eye-off",
    "mActionShowSelectedLayers.svg": "eye-check",
    "mActionHideSelectedLayers.svg": "eye-x",
    "mActionHideDeselectedLayers.svg": "eye-minus",
    "mActionExpandTree.svg": "chevrons-down",
    "mActionCollapseTree.svg": "chevrons-up",
    "mActionFilter2.svg": "filter",
    "mActionPropertiesWidget.svg": "brush",
    "mActionAddAllToOverview.svg": "map+plus",
    "mActionRemoveAllFromOverview.svg": "map+minus",
    "mActionInOverview.svg": "map",
    "mIconExpression.svg": "math-function",
    "mIconExpressionFilter.svg": "filter-code",
    "mIconExpressionSelect.svg": "math-function+check",
    "mIconFormSelect.svg": "forms",
    "mIconProjectionEnabled.svg": "world",
    "propertyicons/symbology.svg": "palette",
    "propertyicons/diagram.svg": "chart-pie",
    "propertyicons/temporal.svg": "clock",
    "symbologyAdd.svg": "plus",
    "symbologyRemove.svg": "minus",
    "processingResult.svg": "list-check",
    "processingModel.svg": "hierarchy-2",
    "processingScript.svg": "file-code",
    "processingAlgorithm.svg": "tool",
    # Not a QGIS icon: the plugin's own for the Processing Toolbox's groups
    # (see IconSwapper.GROUP_ICON).
    "processingToolbox.svg": "toolbox",
    "mIconLayerTree.svg": "stack-2",
    # ---- Layer types (layer tree, browser, combo boxes) -------------------
    "mIconPointLayer.svg": "point",
    "mIconLineLayer.svg": "line",
    "mIconPolygonLayer.svg": "polygon",
    "mIconTableLayer.svg": "table",
    # A picture, not a pixel grid: a 4x4 grid reads as "#" at 16 px.
    "mIconRaster.svg": "photo",
    "mIconRasterLayer.svg": "photo",
    "mIconMeshLayer.svg": "triangle-square-circle",
    "mIconVectorTileLayer.svg": "layout-grid",
    "mIconGeometryCollectionLayer.svg": "shape",
    "mIconFolder.svg": "folder",
    # Layer tree groups: layers held together, like layout Group Items.
    "mActionFolder.svg": "box-multiple",
    "mIconFolderOpen.svg": "folder-open",
    "mIconFolderHome.svg": "home",
    "mIconFavorites.svg": "star",
    "mIconGeoPackage.svg": "package",
    "mIconSpatialite.svg": "feather",
    "mIconPostgis.svg": "database",
    "mIconZip.svg": "file-zip",
    "mIconFile.svg": "file",
    # ---- Map navigation ---------------------------------------------------
    "mActionPan.svg": "hand-stop",
    "mActionPanToSelected.svg": "focus-centered",
    "mActionZoomIn.svg": "zoom-in",
    "mActionZoomOut.svg": "zoom-out",
    # A magnifier framed, "zoom to everything" (arrows read as fullscreen).
    "mActionZoomFullExtent.svg": "zoom-scan",
    "mActionZoomToSelected.svg": "zoom-check",
    "mActionZoomToLayer.svg": "zoom-in-area",
    "mActionZoomActual.svg": "zoom-reset",
    "mActionZoomLast.svg": "arrow-back",
    "mActionZoomNext.svg": "arrow-forward",
    "mActionNewMap.svg": "map-2+plus",
    "mActionNew3DMap.svg": "cube+plus",
    "mActionNewBookmark.svg": "bookmark+plus",
    "mActionShowBookmarks.svg": "bookmarks",
    "temporal.svg": "clock-play",
    # Temporal Controller panel: navigation modes and playback.
    "mTemporalNavigationOff.svg": "clock-off",
    "mTemporalNavigationFixedRange.svg": "calendar-time",
    "mTemporalNavigationAnimated.svg": "clock-play",
    "mTemporalNavigationMovie.svg": "movie",
    "temporal_navigation/back.svg": "player-play-back",
    "temporal_navigation/forward.svg": "player-play",
    "temporal_navigation/next.svg": "player-track-next",
    "temporal_navigation/previous.svg": "player-track-prev",
    "temporal_navigation/pause.svg": "player-pause",
    "temporal_navigation/stop.svg": "player-stop",
    "temporal_navigation/rewindToStart.svg": "player-skip-back",
    "temporal_navigation/skipToEnd.svg": "player-skip-forward",
    "mActionPlay.svg": "player-play",
    "mActionStop.svg": "player-stop",
    "mActionNext.svg": "player-track-next",
    "mActionPrevious.svg": "player-track-prev",
    "mActionRefresh.svg": "refresh",
    "mActionDraw.svg": "refresh",
    "tracking.svg": "route",
    # ---- Attributes / analysis --------------------------------------------
    "mActionIdentify.svg": "info-circle",
    "mActionMapIdentification.svg": "info-circle",
    # Identify Results panel: its pick modes match the selection tools.
    "mActionIdentifyByRectangle.svg": "marquee-2",
    "mActionIdentifyByPolygon.svg": "lasso-polygon",
    "mActionIdentifyByFreehand.svg": "lasso",
    "mActionIdentifyByRadius.svg": "circle-dashed",
    "mActionIdentifyByMouseOver.svg": "pointer",
    "mActionExpandNewTree.svg": "chevrons-down+star",
    "mIconProperties.svg": "tool",
    "mActionCalculateField.svg": "calculator",
    "mActionSum.svg": "sum",
    "mActionOpenTable.svg": "table",
    "mActionOpenTableSelected.svg": "table+check",
    "mActionOpenTableVisible.svg": "table+dot",
    "mActionOpenTableEdited.svg": "table+star",
    "mActionMeasure.svg": "ruler-measure",
    "mActionMeasureArea.svg": "ruler-2",
    "mActionMeasureAngle.svg": "angle",
    "mActionMeasureBearing.svg": "compass",
    "mActionMapTips.svg": "message-dots",
    "mAction.svg": "bolt",
    "mActionShowRasterCalculator.png": "math",
    "mActionShowMeshCalculator.svg": "calculator",
    # ---- Selection --------------------------------------------------------
    "mActionSelectRectangle.svg": "marquee-2",
    "mActionSelectPolygon.svg": "lasso-polygon",
    "mActionSelectFreehand.svg": "lasso",
    "mActionSelectRadius.svg": "circle-dashed",
    "mActionSelectAll.svg": "select-all",
    "mActionDeselectAll.svg": "deselect",
    "mActionDeselectActiveLayer.svg": "deselect",
    "mActionInvertSelection.svg": "arrows-exchange",
    "algorithms/mAlgorithmSelectLocation.svg": "map-pin-search",
    # ---- Editing ----------------------------------------------------------
    "mActionAllEdits.svg": "pencil-cog",
    "mActionToggleEditing.svg": "pencil",
    "mActionSaveEdits.svg": "device-floppy+check",
    "mActionSaveAllEdits.svg": "device-floppy+check",
    "mActionCancelEdits.svg": "pencil-cancel",
    "mActionCancelAllEdits.svg": "pencil-cancel",
    "mActionRollbackEdits.svg": "arrow-back-up",
    "mActionRollbackAllEdits.svg": "arrow-back-up",
    "mActionCapturePoint.svg": "point+plus",
    "mActionCaptureLine.svg": "line+plus",
    "mActionCapturePolygon.svg": "polygon+plus",
    "mActionVertexTool.svg": "vector",
    "mActionVertexToolActiveLayer.svg": "vector+dot",
    "mActionDeleteSelectedFeatures.svg": "trash",
    "mActionDeleteSelected.svg": "trash",
    "mActionEditCut.svg": "cut",
    "mActionEditCopy.svg": "copy",
    "mActionEditPaste.svg": "clipboard",
    "mActionUndo.svg": "arrow-back-up",
    "mActionRedo.svg": "arrow-forward-up",
    "mActionMoveFeature.svg": "arrows-move",
    "mActionMoveFeaturePoint.svg": "arrows-move",
    "mActionMoveFeatureCopyPoint.svg": "copy",
    "mActionRotateFeature.svg": "rotate-clockwise",
    "mActionScaleFeature.svg": "arrows-diagonal",
    "mActionSimplify.svg": "ease-in-out-control-points",
    "mActionAddRing.svg": "circle-dashed+plus",
    "mActionFillRing.svg": "circle-dashed+check",
    "mActionDeleteRing.svg": "circle-dashed+x",
    "mActionAddPart.svg": "squares+plus",
    "mActionDeletePart.svg": "squares+x",
    "mActionReshape.svg": "vector-bezier-2",
    "mActionOffsetCurve.svg": "baseline-density-medium",
    "mActionChamferFillet.svg": "border-corner-rounded",
    "mActionReverseLine.svg": "arrows-exchange",
    "mActionTrimExtendFeature.svg": "arrow-autofit-width",
    "mActionSplitFeatures.svg": "slice",
    "mActionSplitParts.svg": "arrows-split",
    "mActionMergeFeatures.svg": "arrows-join",
    "mActionMergeFeatureAttributes.svg": "arrow-merge",
    "mActionRotatePointSymbols.svg": "rotate-dot",
    "mActionOffsetPointSymbols.svg": "arrows-move-horizontal",
    "mActionFeatureArrayPoint.svg": "grid-dots",
    "mActionMultiEditAttributes.svg": "forms",
    "mActionCircle2Points.svg": "circle",
    "mActionCircularStringRadius.svg": "circle-half",
    "mActionEllipseCenter2Points.svg": "oval",
    "mActionRectangleCenter.svg": "rectangle",
    "mActionRegularPolygon2Points.svg": "hexagon",
    "mActionTracing.svg": "route",
    "mActionAllowIntersections.svg": "layers-intersect",
    "mActionAvoidIntersectionsCurrentLayer.svg": "layers-difference",
    "mActionAvoidIntersectionsLayers.svg": "layers-difference",
    # ---- Snapping ---------------------------------------------------------
    "mIconSnapping.svg": "magnet",
    "mIconSnappingAllLayers.svg": "stack-2",
    "mIconSnappingActiveLayer.svg": "stack-2+dot",
    "mIconSnappingAdvanced.svg": "adjustments-alt",
    "mIconSnappingIntersection.svg": "x",
    "mIconSnappingSelf.svg": "magnet+dot",
    # A shape's vertices: a lone point read as a tiny circle on the
    # snapping type button.
    "mIconSnappingVertex.svg": "vector",
    "mIconSnappingSegment.svg": "line",
    "mIconSnappingArea.svg": "square",
    "mIconSnappingCentroid.svg": "circle-dot",
    "mIconSnappingMiddle.svg": "separator-vertical",
    "mIconSnappingEndpoint.svg": "arrow-bar-to-right",
    "mIconSnappingOnScale.svg": "ruler",
    # Shared borders, and as light as the other icons (the star ring was a
    # dense mesh).
    "mIconTopologicalEditing.svg": "hexagons",
    # ---- Labels / annotations ---------------------------------------------
    "mActionLabeling.svg": "abc",
    "mActionShowPinnedLabels.svg": "pin",
    "mActionShowUnplacedLabel.svg": "abc+x",
    "mActionPinLabels.svg": "pinned",
    "mActionShowHideLabels.svg": "eye",
    "mActionMoveLabel.svg": "arrows-move",
    "mActionRotateLabel.svg": "rotate",
    "mActionChangeLabelProperties.svg": "adjustments",
    "mActionText.svg": "typography",
    "mActionTextAlongLine.svg": "text-direction-ltr",
    "mActionTextInsideRect.svg": "text-size",
    "mActionAddMarker.svg": "map-pin+plus",
    "mActionAddPolyline.svg": "line+plus",
    "mActionAddPolygon.svg": "polygon+plus",
    "mActionAddImage.svg": "photo+plus",
    "mActionHtmlAnnotation.svg": "file-code",
    "mActionFormAnnotation.svg": "forms",
    "mActionScaleBar.svg": "ruler-2",
    "north_arrow.svg": "navigation-north",
    "title_label.svg": "heading",
    "copyright_label.svg": "copyright",
    "grid.svg": "grid-dots",
    # ---- Raster -----------------------------------------------------------
    "mActionLocalHistogramStretch.svg": "chart-histogram",
    "mActionFullHistogramStretch.svg": "chart-bar",
    "mActionLocalCumulativeCutStretch.svg": "chart-histogram",
    "mActionFullCumulativeCutStretch.svg": "chart-bar",
    "mActionIncreaseBrightness.svg": "brightness-up",
    "mActionDecreaseBrightness.svg": "brightness-down",
    "mActionIncreaseContrast.svg": "contrast+plus",
    "mActionDecreaseContrast.svg": "contrast+minus",
    "mActionIncreaseGamma.svg": "sun-high+plus",
    "mActionDecreaseGamma.svg": "sun-high+minus",
    # ---- Mesh -------------------------------------------------------------
    "mActionMeshDigitizing.svg": "triangle-square-circle",
    "mActionMeshSelectPolygon.svg": "lasso-polygon",
    "mActionMeshEditForceByVectorLines.svg": "line",
    "mActionMeshTransformByExpression.svg": "math-function",
    "mActionMeshReindex.svg": "list-numbers",
    "mActionMeshSelectAll.svg": "select-all",
    "mActionMeshSelectExpression.svg": "math-function",
    "mActionMeshSelectIsolatedVertices.svg": "point",
    # ---- Property pages (layer properties, styling panel, options) --------
    "propertyicons/metadata.svg": "info-circle",
    "propertyicons/editmetadata.svg": "file-pencil",
    "propertyicons/system.svg": "database-cog",
    "propertyicons/general.svg": "settings",
    "propertyicons/settings.svg": "settings",
    "propertyicons/layerconfiguration.svg": "settings",
    "propertyicons/labels.svg": "abc",
    "propertyicons/labeltext.svg": "typography",
    "propertyicons/labelformatting.svg": "text-size",
    "propertyicons/labelbuffer.svg": "border-outer",
    "propertyicons/labelbackground.svg": "background",
    "propertyicons/labelshadow.svg": "shadow",
    "propertyicons/labelcallout.svg": "message",
    "propertyicons/labelplacement.svg": "map-pin",
    "propertyicons/labelmask.svg": "mask",
    "propertyicons/attributes.svg": "list-details",
    "propertyicons/sourcefieldsandforms.svg": "forms",
    "propertyicons/join.svg": "link",
    "propertyicons/relations.svg": "affiliate",
    "propertyicons/action.svg": "bolt",
    "propertyicons/display.svg": "message-dots",
    "propertyicons/rendering.svg": "adjustments-horizontal",
    "propertyicons/render.svg": "adjustments-horizontal",
    "propertyicons/transparency.svg": "droplet-half",
    "propertyicons/histogram.svg": "chart-histogram",
    "propertyicons/pyramids.svg": "pyramid",
    "propertyicons/colors.svg": "color-swatch",
    "propertyicons/overlay.svg": "layers-subtract",
    "propertyicons/digitizing.svg": "pencil",
    "propertyicons/map_tools.svg": "tool",
    "propertyicons/CRS.svg": "world-latitude",
    "propertyicons/gdal.svg": "file-database",
    "propertyicons/database.svg": "database",
    "propertyicons/network_and_proxy.svg": "network",
    "propertyicons/locale.svg": "language",
    "propertyicons/notes.svg": "notes",
    "propertyicons/sensor.svg": "antenna",
    "propertyicons/elevationscale.svg": "mountain",
    "propertyicons/stylepreset.svg": "stack-3",
    "propertyicons/datadefined.svg": "variable",
    "propertyicons/plugins.svg": "puzzle",
    "propertyicons/plugin.svg": "puzzle",
    "propertyicons/plugin-installed.svg": "puzzle+check",
    "propertyicons/plugin-new.svg": "puzzle+star",
    "propertyicons/plugin-upgrade.svg": "puzzle+dot",
    "propertyicons/plugin-incompatible.svg": "puzzle+x",
    "propertyicons/plugin-install_from_zip.svg": "file-zip",
    "propertyicons/meshframe.svg": "triangles",
    "propertyicons/meshcontours.svg": "chart-area-line",
    "propertyicons/meshvectors.svg": "arrows-up-right",
    "propertyicons/meshaveraging.svg": "chart-dots",
    "3d.svg": "cube",
    "labelingSingle.svg": "abc",
    "legend.svg": "list",
    "dependencies.svg": "hierarchy-3",
    "mIconAuxiliaryStorage.svg": "database-plus",
    "mActionFormView.svg": "forms",
    "mActionHistory.svg": "history",
    "mIconStopwatch.svg": "stopwatch",
    "mShadingRenderer.svg": "sun",
    "mIconPaintEffects.svg": "sparkles",
    "mSourceFields.svg": "list-details",
    "mActionArrowUp.svg": "arrow-up",
    "mActionArrowDown.svg": "arrow-down",
    "mActionIconView.svg": "layout-grid",
    "mIconAutoPlacementSettings.svg": "adjustments",
    "mIconLabelingRules.svg": "list-tree",
    # ---- Renderers --------------------------------------------------------
    "rendererSingleSymbol.svg": "square-rounded",
    "rendererCategorizedSymbol.svg": "category",
    "rendererGraduatedSymbol.svg": "chart-bar-popular",
    "classification_methods/mClassificationEqualCount.svg": "class-equal-count",
    "classification_methods/mClassificationEqualInterval.svg": "class-equal-interval",
    "classification_methods/mClassificationFixedInterval.svg": "class-fixed-interval",
    "classification_methods/mClassificationLogarithmic.svg": "class-logarithmic",
    "classification_methods/mClassificationNaturalBreak.svg": "class-natural-breaks",
    "classification_methods/mClassificationPrettyBreak.svg": "class-pretty-breaks",
    "classification_methods/mClassificationStandardDeviation.svg": "class-std-dev",
    "rendererRuleBasedSymbol.svg": "list-tree",
    "rendererPointDisplacementSymbol.svg": "circles",
    "rendererPointClusterSymbol.svg": "circles-relation",
    "rendererHeatmapSymbol.svg": "flame",
    "renderer25dSymbol.svg": "box",
    "rendererInvertedSymbol.svg": "square-off",
    "rendererNullSymbol.svg": "circle-off",
    "rendererEmbeddedSymbol.svg": "file-symlink",
    # ---- Attribute table & fields -----------------------------------------
    "mActionNewAttribute.svg": "column-insert-right",
    "mActionDeleteAttribute.svg": "column-remove",
    "mActionNewTableRow.svg": "row-insert-bottom",
    "mActionOpenTableInvalid.svg": "table+x",
    "mActionSelectedToTop.svg": "arrow-bar-to-up",
    "mActionHandleStoreFilterExpressionUnchecked.svg": "bookmark",
    "mActionHandleStoreFilterExpressionChecked.svg": "bookmark+check",
    "mDockify.svg": "app-window",
    "mIconExpressionPreview.svg": "eye",
    "mIconSelectAdd.svg": "pointer-plus",
    "mIconSelectRemove.svg": "pointer-minus",
    "mIconSelectIntersect.svg": "pointer",
    "sort.svg": "sort-ascending",
    "sort-reverse.svg": "sort-descending",
    "mIconFieldInteger.svg": "number-123",
    "mIconFieldFloat.svg": "decimal",
    "mIconFieldText.svg": "letter-case",
    "mIconFieldDate.svg": "calendar",
    "mIconFieldDateTime.svg": "calendar-time",
    "mIconFieldTime.svg": "clock",
    "mIconFieldBool.svg": "toggle-left",
    "mIconFieldGeometry.svg": "shape",
    "mIconFieldBinary.svg": "binary",
    "mIconFieldJson.svg": "braces",
    "mIconClearText.svg": "backspace",
    "mActionSetProjection.svg": "world-cog",
    "mActionFeatureArray.svg": "grid-dots",
    "mActionMoveFeatureCopy.svg": "copy",
    "unlocked.svg": "lock-open",
    "locked.svg": "lock",
    # ---- GPS --------------------------------------------------------------
    "gpsicons/mIconGpsConnect.svg": "gps",
    "gpsicons/mActionAddTrackPoint.svg": "map-pin+plus",
    "gpsicons/mActionRecenter.svg": "current-location",
    "gpsicons/mActionReset.svg": "refresh",
    "gpsicons/mIconGpsDestinationLayer.svg": "stack-2",
    # ---- Advanced digitizing ---------------------------------------------
    "cadtools/cad.svg": "ruler-3",
    "cadtools/circlesintersection.svg": "circles-relation",
    "cadtools/construction.svg": "line-dashed",
    "cadtools/floater.svg": "cursor-text",
    "cadtools/parallel.svg": "equal",
    "cadtools/perpendicular.svg": "border-corner-square",
    # ---- Data sources / browser ------------------------------------------
    "mActionAddLayer.svg": "stack-2+plus",
    "mActionAddGeoPackageLayer.svg": "package+plus",
    "mActionAddGpsLayer.svg": "gps+plus",
    "mActionAddOracleLayer.svg": "database+plus",
    "mActionAddPointCloudLayer.svg": "grain+plus",
    "mActionAddSensorThingsLayer.svg": "antenna+plus",
    "mActionAddTiledSceneLayer.svg": "buildings+plus",
    "mActionNewGpx.svg": "gps+star",
    "mGeoPackage.svg": "package",
    "mIconCloud.svg": "cloud",
    "mIconEsriRest.svg": "api",
    "mIconHana.svg": "database",
    "mIconMssql.svg": "database",
    "mIconSensorThings.svg": "antenna",
    "mIconStac.svg": "stack-3",
    "mIconTiledScene.svg": "buildings",
    "mIconWcs.svg": "world-download",
    "mIconWfs.svg": "world-share",
    "mIconWms.svg": "world",
    "mIconXyz.svg": "map-2",
    "mIconVector.svg": "vector-triangle",
    "mIconAnnotationLayer.svg": "note",
    "dbmanager.svg": "database-cog",
    "mIconQueryHistory.svg": "history",
    "MetaSearch.svg": "world-search",
    # ---- Options / project properties ------------------------------------
    "transformation.svg": "transform",
    "relation.svg": "affiliate",
    "mIconFonts.svg": "typography",
    "mIconLayout.svg": "layout",
    "mIconGPU.svg": "cpu",
    "mIconGps.svg": "gps",
    "mIconCodeEditor.svg": "code",
    "mIconWarning.svg": "alert-triangle",
    "mActionNewPage.svg": "file+plus",
    "mActionStart.svg": "player-play",
    "symbologyEdit.svg": "pencil",
    "mIconDataDefine.svg": "variable",
    "mActionContextHelp.png": "help-circle",
    # ---- Panels / toolbars -----------------------------------------------
    "mActionSelect.svg": "pointer",
    "mActionEditNodesItem.svg": "vector",
    "mActionCreateAnnotationLayer.svg": "note+plus",
    "mActionMultiEdit.svg": "forms",
    "mActionProcessSelected.svg": "pencil-bolt",
    "mIconHistory.svg": "history",
    "mActionToggleSelectedLayers.svg": "eye",
    "mActionZoomToBookmark.svg": "zoom-pan",
    "mActionSharingExport.svg": "file-export",
    "mActionSharingImport.svg": "file-import",
    "mActionRecord.svg": "player-record",
    "mIconQt.svg": "book",
    "mActionDigitizeWithSegment.svg": "line",
    "mActionNew3DMapGlobe.svg": "world+plus",
    "mActionNewElevationProfile.svg": "mountain+plus",
    "georeferencer/mGeorefRun.svg": "map-pins",
    "mActionTerminal.svg": "terminal-2",
    "mIconPythonFile.svg": "brand-python",
    "console/iconClearConsole.svg": "eraser",
    "console/iconTabEditorConsole.svg": "file-code",
    "mActionAdd.svg": "plus",
    "mActionListActions.svg": "list-details",
    "mActionSelectAllTree.svg": "list-check",
    # ---- Attribute table / field calculator ------------------------------
    "mActionConditionalFormatting.svg": "paint",
    "mActionEditTable.svg": "table-options",
    "mActionHighlightFeature.svg": "highlight",
    "mActionPanTo.svg": "hand-stop",
    "mActionZoomTo.svg": "zoom-in-area",
    "mActionArrowLeft.svg": "arrow-left",
    "mActionArrowRight.svg": "arrow-right",
    "mActionDoubleArrowLeft.svg": "chevrons-left",
    "mActionDoubleArrowRight.svg": "chevrons-right",
    "mIconFieldArrayFloat.svg": "brackets",
    "mIconFieldArrayInteger.svg": "brackets",
    "mIconFieldArrayString.svg": "brackets",
    "mActionFindReplace.svg": "replace",
    "mActionSaveAsSVG.svg": "file-type-svg",
    "mIconPhongMaterial.svg": "sphere",
    # ---- Styling: renderers, diagrams, labels ----------------------------
    "rendererMergedFeatures.svg": "arrows-join",
    "diagramNone.svg": "chart-pie-off",
    "histogram.svg": "chart-histogram",
    "pie-chart.svg": "chart-pie",
    "stacked-bar.svg": "chart-bar",
    "stacked-diagram.svg": "chart-arcs",
    "text.svg": "typography",
    "labelingNone.svg": "circle-off",
    "labelingObstacle.svg": "barrier-block",
    "labelingRuleBased.svg": "list-tree",
    "heatmap.svg": "flame",
    "mIconRenderOnTerrain.svg": "mountain",
    "styleicons/color.svg": "color-swatch",
    "styleicons/multibandcolor.svg": "palette",
    "styleicons/paletted.svg": "color-swatch",
    "styleicons/singlebandgray.svg": "contrast",
    "styleicons/singlebandpseudocolor.svg": "color-filter",
    "styleicons/singlecolor.svg": "droplet",
    # ---- Layout designer -------------------------------------------------
    "mActionAdd3DMap.svg": "cube+plus",
    "mActionAddArrow.svg": "arrow-narrow-right",
    "mActionAddBasicCircle.svg": "oval",
    "mActionAddBasicRectangle.svg": "rectangle",
    "mActionAddBasicShape.svg": "shape",
    "mActionAddBasicTriangle.svg": "triangle",
    "mActionAddChart.svg": "chart-bar",
    "mActionAddHtml.svg": "html",
    "mActionAddLegend.svg": "list",
    "mActionAddManualTable.svg": "table+plus",
    "mActionAddMap.svg": "map+plus",
    "mActionAddNodesItem.svg": "vector-spline",
    "mActionAddTable.svg": "table",
    "mActionElevationProfile.svg": "mountain",
    "mActionLabel.svg": "label",
    "mLayoutItemLabel.svg": "label",
    "mLayoutItemMap.svg": "map",
    "mActionAlignBottom.svg": "layout-align-bottom",
    "mActionAlignHCenter.svg": "layout-align-center",
    "mActionAlignLeft.svg": "layout-align-left",
    "mActionAlignRight.svg": "layout-align-right",
    "mActionAlignTop.svg": "layout-align-top",
    "mActionAlignVCenter.svg": "layout-align-middle",
    "mActionDistributeBottom.svg": "layout-distribute-horizontal",
    "mActionDistributeTop.svg": "layout-distribute-horizontal",
    "mActionDistributeVCenter.svg": "layout-distribute-horizontal",
    "mActionDistributeVSpace.svg": "layout-distribute-horizontal",
    "mActionDistributeLeft.svg": "layout-distribute-vertical",
    "mActionDistributeRight.svg": "layout-distribute-vertical",
    "mActionDistributeHCenter.svg": "layout-distribute-vertical",
    "mActionDistributeHSpace.svg": "layout-distribute-vertical",
    "mActionResizeNarrowest.svg": "arrow-autofit-width",
    "mActionResizeWidest.svg": "arrow-autofit-width",
    "mActionResizeShortest.svg": "arrow-autofit-height",
    "mActionResizeTallest.svg": "arrow-autofit-height",
    "mActionResizeSquare.svg": "square",
    "mActionRaiseItems.svg": "arrow-bar-up",
    "mActionLowerItems.svg": "arrow-bar-down",
    "mActionMoveItemsToTop.svg": "arrow-bar-to-up",
    "mActionMoveItemsToBottom.svg": "arrow-bar-to-down",
    "mActionGroupItems.svg": "box-multiple",
    "mActionUngroupItems.svg": "box-multiple+x",
    "mActionLockItems.svg": "lock",
    "mActionUnlockAll.svg": "lock-open",
    "mActionMoveItemContent.svg": "arrows-move",
    "mActionZoomToArea.svg": "zoom-in-area",
    "mActionDuplicateLayout.svg": "copy",
    "mActionFilePrint.svg": "printer",
    "mActionLayers.svg": "stack-2",
    "mActionSetToCanvasExtent.svg": "frame",
    "mActionSetToCanvasScale.svg": "ruler",
    "mActionViewExtentInCanvas.svg": "focus-2",
    "mActionViewScaleInCanvas.svg": "zoom-scan",
    "mActionAtlasFirst.svg": "player-skip-back",
    "mActionAtlasLast.svg": "player-skip-forward",
    "mActionAtlasNext.svg": "chevron-right",
    "mActionAtlasPrev.svg": "chevron-left",
    "mActionAtlasSettings.svg": "book-2",
    "mIconAtlas.svg": "book-2",
    "vector_grid.svg": "grid-dots",
    # ---- Processing ------------------------------------------------------
    "providerGdal.svg": "file-database",
    "providerGrass.svg": "plant",
    "providerQgis.svg": "hexagon-letter-q",
    "qgis_icon.svg": "hexagon-letter-q",
    "mIconIterate.svg": "repeat",
    "mIconModelInput.svg": "plus",
    "mActionRunSelected.svg": "player-play+check",
    "mesh/Elevation.svg": "mountain",
    "mActionEditHelpContent.svg": "message-question",
    "mActionSaveAsPython.svg": "brand-python",
    "mAddToProject.svg": "file-import",
    "algorithms/mAlgorithmAddGeometryAttributes.svg": "ruler-measure",
    "algorithms/mAlgorithmBasicStatistics.svg": "chart-bar",
    "algorithms/mAlgorithmBuffer.svg": "border-outer",
    "algorithms/mAlgorithmCellStatistics.svg": "grid-dots",
    "algorithms/mAlgorithmCellStatisticsPercentRank.svg": "percentage",
    "algorithms/mAlgorithmCellStatisticsPercentile.svg": "percentage",
    "algorithms/mAlgorithmCentroids.svg": "circle-dot",
    "algorithms/mAlgorithmCheckGeometry.svg": "shield-check",
    "algorithms/mAlgorithmClip.svg": "cut",
    "algorithms/mAlgorithmCollect.svg": "packages",
    "algorithms/mAlgorithmConcaveHull.svg": "polygon",
    "algorithms/mAlgorithmConstantRaster.svg": "grid-4x4",
    "algorithms/mAlgorithmConvexHull.svg": "hexagon",
    "algorithms/mAlgorithmCreateGrid.svg": "layout-grid",
    "algorithms/mAlgorithmDelaunay.svg": "triangles",
    "algorithms/mAlgorithmDifference.svg": "layers-difference",
    "algorithms/mAlgorithmDissolve.svg": "layers-union",
    "algorithms/mAlgorithmDistanceMatrix.svg": "table",
    "algorithms/mAlgorithmExtractLayerExtent.svg": "crop",
    "algorithms/mAlgorithmExtractVertices.svg": "point",
    "algorithms/mAlgorithmFillNoData.svg": "paint",
    "algorithms/mAlgorithmFuzzifyGaussian.svg": "wave-sine",
    "algorithms/mAlgorithmFuzzifyLarge.svg": "wave-sine",
    "algorithms/mAlgorithmFuzzifyLinear.svg": "wave-sine",
    "algorithms/mAlgorithmFuzzifyNear.svg": "wave-sine",
    "algorithms/mAlgorithmFuzzifyPower.svg": "wave-sine",
    "algorithms/mAlgorithmFuzzifySmall.svg": "wave-sine",
    "algorithms/mAlgorithmIntersect.svg": "layers-intersect",
    "algorithms/mAlgorithmLineDensity.svg": "grain",
    "algorithms/mAlgorithmLineIntersections.svg": "x",
    "algorithms/mAlgorithmLineToPolygon.svg": "polygon",
    "algorithms/mAlgorithmMeanCoordinates.svg": "target",
    "algorithms/mAlgorithmMergeLayers.svg": "arrows-join",
    "algorithms/mAlgorithmMultiToSingle.svg": "arrows-split",
    "algorithms/mAlgorithmNearestNeighbour.svg": "chart-dots",
    "algorithms/mAlgorithmNetworkAnalysis.svg": "route",
    "algorithms/mAlgorithmNormalRaster.svg": "dice",
    "algorithms/mAlgorithmOffsetLines.svg": "baseline-density-medium",
    "algorithms/mAlgorithmPolygonToLine.svg": "line",
    "algorithms/mAlgorithmRandomExponentialRaster.svg": "dice",
    "algorithms/mAlgorithmRandomGammaRaster.svg": "dice",
    "algorithms/mAlgorithmRandomPointsInPolygons.svg": "chart-scatter",
    "algorithms/mAlgorithmRandomPointsOnLines.svg": "chart-scatter",
    "algorithms/mAlgorithmRandomPointsWithinExtent.svg": "chart-scatter",
    "algorithms/mAlgorithmRandomPointsWithinPolygon.svg": "chart-scatter",
    "algorithms/mAlgorithmRandomPoissonRaster.svg": "dice",
    "algorithms/mAlgorithmRandomRaster.svg": "dice",
    "algorithms/mAlgorithmRasterCalculator.svg": "calculator",
    "algorithms/mAlgorithmRectanglesOvalsDiamonds.svg": "shape-2",
    "algorithms/mAlgorithmRegularPoints.svg": "grid-dots",
    "algorithms/mAlgorithmRoundRastervalues.svg": "decimal",
    "algorithms/mAlgorithmSelectDistance.svg": "radar",
    "algorithms/mAlgorithmSelectRandom.svg": "dice",
    "algorithms/mAlgorithmSimplify.svg": "ease-in-out-control-points",
    "algorithms/mAlgorithmSingleToMulti.svg": "arrows-join",
    "algorithms/mAlgorithmSplitLayer.svg": "arrows-split",
    "algorithms/mAlgorithmSumLengthLines.svg": "sum",
    "algorithms/mAlgorithmSumPoints.svg": "sum",
    "algorithms/mAlgorithmSymmetricalDifference.svg": "layers-difference",
    "algorithms/mAlgorithmUnion.svg": "layers-union",
    "algorithms/mAlgorithmUniqueValues.svg": "list",
    "algorithms/mAlgorithmVoronoi.svg": "hexagons",
    # ---- Python console / script editors --------------------------------
    "console/iconClassBrowserConsole.svg": "list-tree",
    "console/iconCodepadConsole.svg": "code",
    "console/iconCommentEditorConsole.svg": "message",
    "console/iconFileTabsMenuConsole.svg": "files",
    "console/iconFormatCode.svg": "indent-increase",
    "console/iconHelpConsole.svg": "help-circle",
    "console/iconHideToolConsole.svg": "eye-off",
    "console/iconNewTabEditorConsole.svg": "file+plus",
    "console/iconRestoreTabsConsole.svg": "history",
    "console/iconSearchEditorConsole.svg": "search",
    "console/iconSettingsConsole.svg": "settings",
    "console/iconShowEditorConsole.svg": "layout-sidebar-right",
    "console/iconSyntaxErrorConsole.svg": "alert-triangle",
    "mActionScriptOpen.svg": "folder-open",
    "mActionIncreaseFont.svg": "text-increase",
    "mActionDecreaseFont.svg": "text-decrease",
    "mIconQgsProjectFile.svg": "file-settings",
    # ---- Processing images loaded from the plugin folder (EXTERNAL) -------
    # ---- More providers / DB Manager ------------------------------------
    "mIconOracle.svg": "database",
    "mIconDbSchema.svg": "folder",
    "mIconVirtualLayer.svg": "sql",
    "mActionCreateTable.svg": "table+plus",
    "mActionDeleteTable.svg": "table+x",
    "mIconAfs.svg": "world-share",
    "mIconAms.svg": "map-2",
    "mIconEsriI3s.svg": "buildings",
    "mIconPointCloudLayer.svg": "grain",
    "mIconTiledSceneLayer.svg": "buildings",
    "mIconFolderParams.svg": "folder",
    "mIconFolderOpenParams.svg": "folder-open",
    "mIconFolderHomeParams.svg": "home",
    "mIconFolderLinkParams.svg": "folder",
    "db_manager/mActionDBImport.svg": "database-import",
    "db_manager/mActionDBExport.svg": "database-export",
    "db_manager/mActionSQLWindow.svg": "sql",
    "db_manager/dbmanager.svg": "database-cog",
    "processing/interpolation.png": "grain",
    "processing/menu.png": "menu-2",
    "processing/gdaltools/24-to-8-bits.png": "color-swatch",
    "processing/gdaltools/8-to-24-bits.png": "palette",
    "processing/gdaltools/contour.png": "chart-area-line",
    "processing/gdaltools/grid.png": "grid-dots",
    "processing/gdaltools/merge.png": "arrows-join",
    "processing/gdaltools/nearblack.png": "contrast",
    "processing/gdaltools/polygonize.png": "polygon",
    "processing/gdaltools/projection-add.png": "world-cog",
    "processing/gdaltools/projection-export.png": "file-export",
    "processing/gdaltools/proximity.png": "radar",
    "processing/gdaltools/raster-clip.png": "crop",
    "processing/gdaltools/raster-info.png": "info-circle",
    "processing/gdaltools/raster-overview.png": "pyramid",
    "processing/gdaltools/rasterize.png": "grid-4x4",
    "processing/gdaltools/sieve.png": "filter",
    "processing/gdaltools/tiles.png": "layout-grid",
    "processing/gdaltools/translate.png": "transform",
    "processing/gdaltools/vrt.png": "stack-2",
    "processing/gdaltools/warp.png": "world",
    # ---- Everything else QGIS draws (1.3): layout designer, form widgets,
    # shape tools, indicators, tasks, certificates, console, georeferencer.
    # Left to QGIS in every style: mouse cursors, the easing-curve previews
    # (their shape is the information), rating stars, the transparency
    # checkerboard and an empty spacer (see NOT_REPLACED).
    "cap_flat.svg": "cap-flat", "cap_round.svg": "cap-round", "cap_square.svg": "cap-square",
    "join_bevel.svg": "join-bevel", "join_miter.svg": "join-miter", "join_round.svg": "join-round",
    "downloading_svg.svg": "cloud-download", "extents.svg": "frame",
    "grass_location.svg": "map-2", "grass_mapset.svg": "folder", "grass_mapset_open.svg": "folder-open",
    "grass_mapset_search.svg": "folder-open",
    "labelingCalloutCurved.svg": "vector-spline", "labelingCalloutManhattan.svg": "corner-down-right",
    "labelingCalloutSimple.svg": "line", "locked_repeating.svg": "repeat",
    "mAction3DNavigation.svg": "cube", "mActionActive.svg": "circle-check", "mActionAddAmsLayer.svg": "world+plus",
    "mActionAddExpression.svg": "math-function+plus", "mActionCaptureCurveFromFeature.svg": "vector-spline",
    "mActionCircle2TangentsPoint.svg": "circle", "mActionCircle3Points.svg": "circle-dashed",
    "mActionCircle3Tangents.svg": "circles", "mActionCircleCenterPoint.svg": "circle-dot",
    "mActionCircularStringCurvePoint.svg": "vector-spline", "mActionComposerManager.svg": "layout-board",
    "mActionCopyProfileSettings.svg": "copy", "mActionDeleteModelComponent.svg": "trash",
    "mActionDeselectAllTree.svg": "deselect", "mActionDigitizeShape.svg": "shape",
    "mActionDigitizeWithBezier.svg": "vector-bezier-2", "mActionDigitizeWithCurve.svg": "vector-spline",
    "mActionDigitizeWithNURBS.svg": "vector-spline", "mActionDuplicateComposer.svg": "copy",
    "mActionDuplicateFeature.svg": "copy", "mActionDuplicateFeatureDigitized.svg": "copy+plus",
    "mActionEditBold.svg": "bold", "mActionEditCutDisabled.svg": "cut", "mActionEditHtml.svg": "html",
    "mActionEditIndentLess.svg": "indent-decrease", "mActionEditIndentMore.svg": "indent-increase",
    "mActionEditInsertImage.svg": "photo+plus", "mActionEditInsertLink.svg": "link",
    "mActionEditItalic.svg": "italic", "mActionEditModelComponent.svg": "pencil",
    "mActionEditUnderline.svg": "underline", "mActionStrikeOut.svg": "strikethrough",
    "mActionEllipseCenterPoint.svg": "oval", "mActionEllipseExtent.svg": "oval", "mActionEllipseFoci.svg": "oval",
    "mActionExport.svg": "file-export", "mActionFeatureArrayLine.svg": "grid-dots", "mActionFileExit.svg": "logout",
    "mActionFilter.svg": "filter", "mActionFilterTableFields.svg": "filter",
    "mActionFirst.svg": "player-skip-back", "mActionLast.svg": "player-skip-forward",
    "mActionFromLargestFeature.svg": "focus-2", "mActionFromSelectedFeature.svg": "focus-2",
    "mActionLabelAnchorCenter.svg": "focus-centered", "mActionLabelAnchorCustom.svg": "target",
    "mActionLabelAnchorEnd.svg": "arrow-bar-to-right", "mActionLabelAnchorStart.svg": "arrow-bar-to-left",
    "mActionLink.svg": "link", "mActionUnlink.svg": "link-off", "mActionLockExtent.svg": "lock",
    "mActionMapSettings.svg": "settings", "mActionMoveFeatureCopyLine.svg": "arrows-move",
    "mActionMoveFeatureLine.svg": "arrows-move", "mActionMoveVertex.svg": "point",
    "mActionNewComposer.svg": "layout+star", "mActionNewFileGeodatabase.svg": "database+plus",
    "mActionNewFolder.svg": "folder+plus", "mActionPanHighlightFeature.svg": "hand-stop",
    "mActionScaleHighlightFeature.svg": "zoom-scan", "mActionPropertyItem.svg": "list-details",
    "mActionRectangle3PointsDistance.svg": "rectangle", "mActionRectangle3PointsProjected.svg": "rectangle",
    "mActionRectangleExtent.svg": "rectangle", "mActionRegularPolygonCenterCorner.svg": "hexagon",
    "mActionRegularPolygonCenterPoint.svg": "hexagon", "mActionReload.svg": "refresh", "mActionRemove.svg": "minus",
    "mActionRemoveSelectedFeature.svg": "deselect", "mActionReplace.svg": "replace",
    "mActionSelectAboveLine.svg": "arrow-bar-up", "mActionSelectBelowLine.svg": "arrow-bar-down",
    "mActionSelectPan.svg": "hand-stop", "mActionShowAllLayersGray.svg": "eye",
    "mActionStreamingDigitize.svg": "vector-spline", "mActionSvgAnnotation.svg": "file-type-svg",
    "mActionTextAnnotation.svg": "message", "mActionTiltDown.svg": "arrow-down", "mActionTiltUp.svg": "arrow-up",
    "mActionToggleAllLayers.svg": "eye", "mActionTouch.svg": "pointer", "mActionTouch2.png": "pointer",
    "mActionWhatsThis.svg": "help-circle", "mActionZoomInXAxis.svg": "zoom-in",
    "mEditorWidgetAction.svg": "bolt", "mEditorWidgetAttachment.svg": "paperclip",
    "mEditorWidgetBinary.svg": "binary", "mEditorWidgetCheckbox.svg": "square-check",
    "mEditorWidgetClassification.svg": "category", "mEditorWidgetColor.svg": "palette",
    "mEditorWidgetDateTime.svg": "calendar-time", "mEditorWidgetGeometry.svg": "shape",
    "mEditorWidgetHidden.svg": "eye-off", "mEditorWidgetHtml.svg": "html", "mEditorWidgetJsonView.svg": "braces",
    "mEditorWidgetList.svg": "list", "mEditorWidgetQml.svg": "code", "mEditorWidgetRange.svg": "adjustments-horizontal",
    "mEditorWidgetRelationEditor.svg": "hierarchy-2", "mEditorWidgetRelationReference.svg": "link",
    "mEditorWidgetSpacer.svg": "separator-vertical", "mEditorWidgetText.svg": "cursor-text",
    "mEditorWidgetTextEdit.svg": "align-left", "mEditorWidgetUuid.svg": "binary",
    "mEditorWidgetValueMap.svg": "list-details", "mEditorWidgetValueRelation.svg": "list-tree",
    "mIcon3dAxis.svg": "cube", "mIconAlignBottom.svg": "layout-align-bottom", "mIconAlignCenter.svg": "align-center",
    "mIconAlignJustify.svg": "align-justified", "mIconAlignLeft.svg": "align-left",
    "mIconAlignRight.svg": "align-right", "mIconAlignTop.svg": "layout-align-top",
    "mIconAlignVCenter.svg": "layout-align-middle", "mIconAllRings.svg": "circles",
    "mIconExteriorRing.svg": "circle", "mIconInteriorRings.svg": "circle-dot",
    "mIconArrangeSymbolsLeft.svg": "arrow-bar-to-left", "mIconArrangeSymbolsRight.svg": "arrow-bar-to-right",
    "mIconBrowserRelations.svg": "hierarchy-2", "mIconCamera.svg": "photo",
    "mIconCertificate.svg": "shield-check", "mIconCertificateMissing.svg": "alert-triangle",
    "mIconCertificateTrusted.svg": "shield-check", "mIconCertificateUntrusted.svg": "shield-check+x",
    "mIconCesium3dTiles.svg": "cube", "mIconClearItem.svg": "x", "mIconClearTextHover.svg": "backspace",
    "mIconCloseTab.svg": "x", "mIconCloseTabHover.svg": "x", "mIconCollapseSmall.svg": "chevron-up",
    "mIconExpandSmall.svg": "chevron-down", "mIconColorBox.svg": "color-swatch", "mIconColorLocked.svg": "lock",
    "mIconColorPicker.svg": "droplet", "mIconColorSwatches.svg": "color-swatch", "mIconColorUnlocked.svg": "lock-open",
    "mIconColorWheel.svg": "palette", "mIconConnect.svg": "network", "mIconCritical.svg": "alert-triangle",
    "mIconDataDefine.svg": "variable", "mIconDataDefineOn.svg": "variable+dot",
    "mIconDataDefineError.svg": "variable+x", "mIconDataDefineExpression.svg": "math-function",
    "mIconDataDefineExpressionOn.svg": "math-function+dot", "mIconDataDefineExpressionError.svg": "math-function+x",
    "mIconDataDefineColor.svg": "palette", "mIconDataDefineColorOn.svg": "palette+dot",
    "mIconDelete.svg": "trash", "mIconDelimitedText.svg": "file-type-csv", "mIconDeselected.svg": "square",
    "mIconSelected.svg": "square-check", "mIconDropDownMenu.svg": "chevron-down", "mIconHamburgerMenu.svg": "menu-2",
    "mIconEditableEdits.svg": "pencil", "mIconFileLink.svg": "file-symlink", "mIconFolderLink.svg": "folder",
    "mIconFolder24.svg": "folder", "mIconFolderProject.svg": "folder", "mIconFloaterCartesian.svg": "ruler",
    "mIconFloaterEllipsoid.svg": "world", "mIconGoochMaterial.svg": "sphere",
    "mIconPhongTexturedMaterial.svg": "sphere", "mIconSimpleLineMaterial.svg": "sphere", "mIconGpx.svg": "route",
    "mIconHtml.svg": "html", "mIconImageServer.svg": "photo", "mIconInfo.svg": "info-circle",
    "mIconJoinHasNotUpsertOnEdit.svg": "link-off", "mIconJoinNotEditable.svg": "link-off",
    "mIconJoinedLayerNotEditable.svg": "link-off", "mIconLabelQuadrantCenter.svg": "focus-centered",
    "mIconLabelQuadrantOffset.svg": "arrows-up-right", "mIconLayer.png": "stack-2", "mIconListView.svg": "list",
    "mIconTreeView.svg": "list-tree", "mIconMemory.svg": "cpu", "mIconModelOutput.svg": "arrow-bar-to-right",
    "mIconModelerCollapse.svg": "chevron-up", "mIconModelerExpand.svg": "chevron-down",
    "mIconNetworkLogger.svg": "network", "mIconNoPyramid.svg": "pyramid+minus", "mIconPyramid.svg": "pyramid",
    "mIconOws.svg": "world", "mIconProjectionDisabled.svg": "world+x", "mIconQptFile.svg": "template",
    "mIconRasterGroup.svg": "photo", "mIconRasterLink.svg": "photo", "mIconRasterVector.svg": "transform",
    "mIconRememberDisabled.svg": "bookmark+minus", "mIconRememberEnabled.svg": "bookmark",
    "mIconReport.svg": "report", "mIconSearchCaseSensitive.svg": "letter-case", "mIconSearchRegex.svg": "brackets",
    "mIconSearchWholeWord.svg": "abc", "mIconSearchWrapAround.svg": "repeat", "mIconSelectLocked.svg": "lock",
    "mIconSelectUnlocked.svg": "lock-open", "mIconShadow.svg": "shadow", "mIconStoredQueries.svg": "sql",
    "mIconSurfaceElevationFillAbove.svg": "mountain", "mIconSurfaceElevationFillBelow.svg": "mountain",
    "mIconSurfaceElevationLine.svg": "mountain", "mIconTemporalRaster.svg": "clock",
    "mIconTimerContinue.svg": "player-play", "mIconTimerPause.svg": "player-pause",
    "mIconVertexCoordinates.svg": "point", "mIconZoom.svg": "zoom-in",
    "mIndicatorBadLayer.svg": "alert-triangle", "mIndicatorEmbedded.svg": "link",
    "mIndicatorFieldComment.svg": "message", "mIndicatorFilter.svg": "filter",
    "mIndicatorLayerError.svg": "alert-triangle", "mIndicatorLowAccuracy.svg": "alert-triangle",
    "mIndicatorMemory.svg": "cpu", "mIndicatorNoCRS.svg": "world+x", "mIndicatorNonRemovable.svg": "lock",
    "mIndicatorNotes.svg": "notes", "mIndicatorOffline.svg": "cloud+x", "mIndicatorTemporal.svg": "clock",
    "mIndicatorTimeFromProject.svg": "clock", "mItemBookmark.svg": "bookmark",
    "mLayoutItem.svg": "frame", "mLayoutItem3DMap.svg": "cube", "mLayoutItemChart.svg": "chart-bar",
    "mLayoutItemElevationProfile.svg": "mountain", "mLayoutItemHtml.svg": "html",
    "mLayoutItemLegend.svg": "list-details", "mLayoutItemMarker.svg": "map-pin", "mLayoutItemPicture.svg": "photo",
    "mLayoutItemPolygon.svg": "polygon", "mLayoutItemPolyline.svg": "line", "mLayoutItemScaleBar.svg": "ruler",
    "mLayoutItemShapeEllipse.svg": "oval", "mLayoutItemShapeRectangle.svg": "rectangle",
    "mLayoutItemShapeTriangle.svg": "triangle", "mLayoutItemTable.svg": "table",
    "mMessageLogRead.svg": "message", "mSensor.svg": "antenna",
    "mTaskCancel.svg": "x", "mTaskComplete.svg": "circle-check", "mTaskOnHold.svg": "player-pause",
    "mTaskQueued.svg": "clock", "mTaskRunning.svg": "player-play", "mTaskTerminated.svg": "alert-triangle",
    "mToggleAliases.svg": "label", "multieditChangedValues.svg": "pencil", "multieditMixedValues.svg": "equal-not",
    "multieditSameValues.svg": "equal", "pin.svg": "pin", "pluginDeprecated.svg": "alert-triangle",
    "pluginExperimental.png": "flame", "pluginNew.svg": "sparkles", "pluginUpgrade.svg": "arrow-up",
    "providerOtb.svg": "photo", "providerSaga.svg": "tool", "rendererGrassSymbol.svg": "plant",
    "repositoryConnected.svg": "network", "repositoryDisabled.svg": "network+minus",
    "repositoryUnavailable.svg": "alert-triangle", "sync_views.svg": "arrows-exchange", "transformed.svg": "transform",
    "unlockedGray.svg": "lock-open", "styleicons/pointcloudextent.svg": "frame",
    "cadtools/delta.svg": "triangle", "cadtools/lock.svg": "lock",
    "checks/InvalidGeometry.svg": "alert-triangle", "checks/MissingVertex.svg": "point",
    "checks/Overlap.svg": "layers-intersect", "checks/SliverOrGap.svg": "layers-difference",
    "console/classBrowserHelp.png": "help-circle", "console/consoleHelp.png": "help-circle",
    "console/editorHelp.png": "help-circle", "console/iconClassTreeWidgetConsole.svg": "box",
    "console/iconFunctionTreeWidgetConsole.svg": "math-function", "console/iconMethodTreeWidgetConsole.svg": "code",
    "console/iconProcessingConsole.svg": "tool", "console/iconQtCoreConsole.svg": "code",
    "console/iconQtGuiConsole.svg": "app-window", "console/iconSearchNextEditorConsole.svg": "arrow-down",
    "console/iconSearchPrevEditorConsole.svg": "arrow-up", "console/iconSyntaxErrorConsoleParams.svg": "alert-triangle",
    "console/iconUncommentEditorConsole.svg": "code",
    "field_indicators/mIndicatorConstraint.svg": "lock", "field_indicators/mIndicatorConstraintHard.svg": "lock",
    "field_indicators/mIndicatorDefaultValue.svg": "variable",
    "field_indicators/mIndicatorDefaultValueApplyOnUpdate.svg": "refresh",
    "georeferencer/mActionAddGCPPoint.svg": "map-pin+plus", "georeferencer/mActionDeleteGCPPoint.svg": "map-pin+x",
    "georeferencer/mActionGDALScript.svg": "terminal-2", "georeferencer/mActionLinkGeorefToQgis.svg": "link",
    "georeferencer/mActionLinkQGisToGeoref.svg": "link", "georeferencer/mActionLoadGCPpoints.svg": "file-import",
    "georeferencer/mActionMoveGCPPoint.svg": "arrows-move",
    "georeferencer/mActionSaveGCPpointsAs.svg": "device-floppy", "georeferencer/mPushButtonPencil.svg": "pencil",
    "gpsicons/barchart.svg": "chart-bar", "gpsicons/mIconGpsDisconnect.svg": "network+x",
    "gpsicons/polarchart.svg": "radar",
    "mesh/Depth.svg": "arrow-bar-to-down", "mesh/Height.svg": "arrow-bar-to-up", "mesh/MultiBottom.svg": "stack-2",
    "mesh/MultiTop.svg": "stack-2", "mesh/Sigma.svg": "sum", "mesh/SingleBottom.svg": "arrow-bar-down",
    "mesh/SingleTop.svg": "arrow-bar-up",
    "propertyicons/meshcontoursoff.svg": "wave-sine", "propertyicons/meshvectorsoff.svg": "arrows-up-right",
    # DB Manager's and Processing's own images (EXTERNAL).
    "db_manager/about.png": "info-circle", "db_manager/layer_unknown.png": "stack-2",
    "db_manager/namespace.png": "folder", "db_manager/plugged.png": "network",
    "db_manager/unplugged.png": "network+x", "db_manager/view.png": "table",
    "db_manager/view_materialized.png": "table+check", "db_manager/warning-20px.png": "alert-triangle",
    "processing/dem.png": "mountain",
    # ---- Ribbon: menu-only commands QGIS gives no icon ----------------------
    # (studio_ribbon.ICON_FALLBACKS; QGIS has no files of these names).
    "ribbon/close.svg": "file-x",
    "ribbon/exit.svg": "logout",
    "ribbon/revert.svg": "arrow-back-up",
    "ribbon/snapping.svg": "magnet",
    "ribbon/export.svg": "file-export",
    "ribbon/import.svg": "file-import",
    "ribbon/template.svg": "template",
    "ribbon/recent.svg": "clock",
    "ribbon/open-from.svg": "cloud-download",
    "ribbon/save-to.svg": "cloud-upload",
    "ribbon/layouts.svg": "layout",
    "ribbon/models.svg": "sitemap",
    "ribbon/paste-as.svg": "clipboard",
    "ribbon/select.svg": "pointer",
    "ribbon/annotation.svg": "message",
    "ribbon/attributes.svg": "forms",
    "ribbon/geometry.svg": "shape",
    "ribbon/3d.svg": "cube",
    "ribbon/filter.svg": "filter",
    "ribbon/measure.svg": "ruler-measure",
    "ribbon/elevation.svg": "mountain",
    "ribbon/decorations.svg": "frame",
    "ribbon/preview.svg": "eye",
    "ribbon/panels.svg": "layout-sidebar",
    "ribbon/full-screen.svg": "maximize",
    "ribbon/map-only.svg": "arrows-maximize",
    "ribbon/add-layer.svg": "stack-2+plus",
    "ribbon/create-layer.svg": "stack-2+star",
    "ribbon/embed.svg": "box-multiple",
    "ribbon/layer-definition.svg": "file-code",
    "ribbon/crs.svg": "world-cog",
    "ribbon/project-crs.svg": "world",
    "ribbon/properties.svg": "adjustments",
    "ribbon/manage.svg": "settings",
    "ribbon/profiles.svg": "user",
    "ribbon/tools.svg": "tool",
    "ribbon/calculator.svg": "calculator",
    "ribbon/docs.svg": "book",
    "ribbon/bug.svg": "bug",
    "ribbon/donate.svg": "heart",
    "ribbon/community.svg": "users",
    "ribbon/support.svg": "lifebuoy",
    "ribbon/web.svg": "world-www",
}

# Images QGIS keeps in its theme folder that are no icons of a command and
# keep their own look in every style: mouse cursors (their hot spot is
# part of the drawing), the easing-curve previews (their shape is the
# information), rating stars, the transparency checkerboard and an empty
# spacer.
NOT_REPLACED = (
    "cursors/", "interpolation/", "stars_empty.svg", "stars_full.svg", "transp-background_8x8.png",
    "propertyicons/spacer.svg",
)

# Icons QGIS loads from its resources outside the theme folder: name ->
# resource path (the QGIS logo on the Dev Tools documentation page).
RESOURCE_PATHS = {
    "qgis_icon.svg": ":/images/icons/qgis_icon.svg",
}

# Icons that QGIS core plugins load from their own folder instead of the
# theme: name -> path relative to QgsApplication.pkgDataPath().
EXTERNAL = {
    "MetaSearch.svg": "python/plugins/MetaSearch/images/MetaSearch.svg",
    "db_manager/mActionDBImport.svg": "python/plugins/db_manager/icons/mActionDBImport.svg",
    "db_manager/mActionDBExport.svg": "python/plugins/db_manager/icons/mActionDBExport.svg",
    "db_manager/mActionSQLWindow.svg": "python/plugins/db_manager/icons/mActionSQLWindow.svg",
    "db_manager/dbmanager.svg": "python/plugins/db_manager/icons/dbmanager.svg",
    "db_manager/about.png": "python/plugins/db_manager/icons/about.png",
    "db_manager/layer_unknown.png": "python/plugins/db_manager/icons/layer_unknown.png",
    "db_manager/namespace.png": "python/plugins/db_manager/icons/namespace.png",
    "db_manager/plugged.png": "python/plugins/db_manager/icons/plugged.png",
    "db_manager/unplugged.png": "python/plugins/db_manager/icons/unplugged.png",
    "db_manager/view.png": "python/plugins/db_manager/icons/view.png",
    "db_manager/view_materialized.png": "python/plugins/db_manager/icons/view_materialized.png",
    "db_manager/warning-20px.png": "python/plugins/db_manager/icons/warning-20px.png",
    "processing/dem.png": "python/plugins/processing/images/dem.png",
    "processing/interpolation.png": "python/plugins/processing/images/interpolation.png",
    "processing/menu.png": "python/plugins/processing/images/menu.png",
    "processing/gdaltools/24-to-8-bits.png": "python/plugins/processing/images/gdaltools/24-to-8-bits.png",
    "processing/gdaltools/8-to-24-bits.png": "python/plugins/processing/images/gdaltools/8-to-24-bits.png",
    "processing/gdaltools/contour.png": "python/plugins/processing/images/gdaltools/contour.png",
    "processing/gdaltools/grid.png": "python/plugins/processing/images/gdaltools/grid.png",
    "processing/gdaltools/merge.png": "python/plugins/processing/images/gdaltools/merge.png",
    "processing/gdaltools/nearblack.png": "python/plugins/processing/images/gdaltools/nearblack.png",
    "processing/gdaltools/polygonize.png": "python/plugins/processing/images/gdaltools/polygonize.png",
    "processing/gdaltools/projection-add.png": "python/plugins/processing/images/gdaltools/projection-add.png",
    "processing/gdaltools/projection-export.png": "python/plugins/processing/images/gdaltools/projection-export.png",
    "processing/gdaltools/proximity.png": "python/plugins/processing/images/gdaltools/proximity.png",
    "processing/gdaltools/raster-clip.png": "python/plugins/processing/images/gdaltools/raster-clip.png",
    "processing/gdaltools/raster-info.png": "python/plugins/processing/images/gdaltools/raster-info.png",
    "processing/gdaltools/raster-overview.png": "python/plugins/processing/images/gdaltools/raster-overview.png",
    "processing/gdaltools/rasterize.png": "python/plugins/processing/images/gdaltools/rasterize.png",
    "processing/gdaltools/sieve.png": "python/plugins/processing/images/gdaltools/sieve.png",
    "processing/gdaltools/tiles.png": "python/plugins/processing/images/gdaltools/tiles.png",
    "processing/gdaltools/translate.png": "python/plugins/processing/images/gdaltools/translate.png",
    "processing/gdaltools/vrt.png": "python/plugins/processing/images/gdaltools/vrt.png",
    "processing/gdaltools/warp.png": "python/plugins/processing/images/gdaltools/warp.png",
}

# Visible stroke width (in 24x24 icon units) of every glyph, and how much a
# glyph is enlarged around the centre: Tabler glyphs leave a ~3 unit margin,
# so 1.15 makes icons read bigger without changing any widget's icon size.
# Compact sizes (low-density screens, where every pixel is physically
# larger) keep Tabler's own size, which matches the footprint of QGIS's
# native toolbar icons there.
STROKE = 1.5
# Extra width (device pixels) of pixel-snapped lines, beyond their whole
# pixels (see render_icon_px).
STROKE_EXTRA = 0.25
SCALE = 1.15
COMPACT_SCALE = 1.0
# Glyphs with a badge are shrunk towards the top-left instead; less so in
# icons of 20 px and below, where 0.9 left a glyph of about 9 px.
BADGED_SCALE = 0.9
BADGED_SCALE_SMALL = 1.0
# Badges sit bottom-right with a transparent ring cut out of the glyph
# around them, so they read cleanly on any button background, hovered or
# checked (needs Qt >= 6.7 for SVG masks; older Qt draws them touching).
# Add, new, remove-from and accept get a mark drawn like the glyph (same
# colour and line weight), which keeps toolbars calm; delete keeps a red
# dot so destructive buttons stand out, and "dot" (an active-layer or
# update variant) an accent dot.
BADGE_CENTER = 18.7
BADGE_RADIUS = 3.05
BADGE_GAP = 2.3
BADGE_MARKS = {"plus": "plus", "star": "plus", "minus": "minus", "check": "check"}
# Half the width of a mark, in units.
MARK_ARM = 3.0

# ---- Colourful icons --------------------------------------------------------
# The Colourful style (Plugins > QGIS Studio Themes > Settings > Icons), in
# the manner of professional colour icon sets (Fluent, Office, ArcGIS Pro):
# objects have solid bodies in medium tones with a deeper edge of their own
# hue: gold folders, blue databases, floppy disks and globes, green maps
# and terrain, red pins, bookmarks and erasers. Gold is kept for folders
# and a few things that are gold (a star, the sun); tools and objects such
# as rulers, pencils and locks are grey. Each part of a
# glyph (one of its paths) has a material (COLOR_RECIPES). Actions (zoom,
# pan, settings) and glyphs without a recipe keep the theme's icon colour
# ("ink"), with at most one coloured detail. Documents are white sheets on
# light themes and soft grey ones on dark themes, the lines on them dark.
# The medium tones read on light and dark windows alike.
#
# A part's material: "name" fills its closed outlines with the hue's light
# body (strong names, ending in S, and folders: its medium body) and draws
# its line in the hue's edge; "name!" fills its open lines too (closed by
# a straight line, as SVG does: a cylinder's band, a hill under the sky);
# "name/" draws the line only; "ink" draws only the line, in the theme's
# icon colour.
COLOR_HUES = {  # (light body, medium body, edge)
    # 90% of the hues' full saturation, every hue alike.
    "blue": ("#a0c0e2", "#6193c9", "#396da0"),
    "green": ("#a9d09e", "#66a466", "#417a43"),
    "red": ("#eaada7", "#ca6961", "#9e4a44"),
    "amber": ("#eccc78", "#d7a648", "#9e7827"),
    "orange": ("#edb98f", "#d58d53", "#a2642e"),
    "purple": ("#c1b3e3", "#8f7ac8", "#65509f"),
    "teal": ("#9accc6", "#4b9e94", "#30746d"),
    "neutral": ("#d7dbe0", "#9ba3ac", "#6c747f"),
    # Wood: a clipboard's board, a brush's handle.
    "wood": ("#d8b48e", "#b88352", "#7d5429"),
    # The toolbox's red (ArcGIS's red toolboxes).
    "toolred": ("#ca6961", "#bd4d45", "#8a3630"),
}
# Paper (fill, edge) on light and dark themes.
COLOR_MODES = ("light", "dark")
PAPER = {"light": ("#ffffff", "#8a939d"), "dark": ("#c9ced4", "#9aa2ab")}
# A magnifier's light glass, in an ink frame.
GLASS = "#c8dcef"
# Signs (info, help, warning, OK): solid, in the hue's medium body, with a
# white (or dark) mark.
SIGNS = frozenset(("info-circle", "info-square-rounded", "help-circle", "alert-triangle", "circle-check"))
DARK_MARK = "#33383e"
# Details on a fill (a clock's hands, a gear on a page, the lines of a
# message) are drawn in a colour with at least this contrast to it (WCAG's
# minimum for graphics), so they read on light and dark themes alike.
DETAIL_CONTRAST = 3.0
# What the theme's icon colour is like on light and dark themes, to tell
# whether it reads on a fill.
THEME_INK = {"light": "#3a3d42", "dark": "#d4d6d8"}
# The hue of each material.
MATERIAL_HUES = {
    "paper": "paper", "gray": "neutral", "grayS": "neutral", "white": "white", "dark": "dark",
    "folder": "amber", "yellow": "amber", "yellowS": "amber", "brown": "amber", "brownS": "amber",
    "glass": "glass", "blue": "blue", "blueS": "blue", "green": "green", "greenS": "green",
    "red": "red", "redS": "red", "pink": "red", "pinkS": "red", "orange": "orange", "orangeS": "orange",
    "purple": "purple", "purpleS": "purple", "teal": "teal", "tealS": "teal", "toolred": "toolred", "wood": "wood", "woodS": "wood",
    "toolredS": "toolred",
}
# The colour of the +, - and check marks of badges (add, remove, accept).
COLOR_MARKS = dict.fromkeys(COLOR_MODES, {"plus": "#539653", "minus": "#c25a53", "check": "#539653"})


def _mark_path(mark, c, arm):
    """Path data of a badge mark centred on (c, c), `arm` from centre to
    end, in whatever units the caller draws in."""
    if mark == "plus":
        return f"M{_num(c - arm)} {_num(c)}H{_num(c + arm)}M{_num(c)} {_num(c - arm)}V{_num(c + arm)}"
    if mark == "minus":
        return f"M{_num(c - arm)} {_num(c)}H{_num(c + arm)}"
    # A check mark: short stroke down to the right, long stroke up.
    return (f"M{_num(c - arm)} {_num(c + arm * 0.05)}L{_num(c - arm * 0.3)} {_num(c + arm * 0.7)}"
            f"L{_num(c + arm)} {_num(c - arm * 0.65)}")

_BODY = re.compile(r"<svg[^>]*>(.*)</svg>", re.S)
_FRAME = re.compile(r'<path stroke="none" d="M0 0h24v24H0z" fill="none"\s*/>')
_PATH = re.compile(r'<path\s+d="([^"]*)"([^>]*?)\s*/>')
_TOKEN = re.compile(r"[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
_ARGS = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "A": 7}


def glyph_names():
    """Every Tabler glyph the map references."""
    return sorted({spec.split("+")[0] for spec in ICON_MAP.values()})


def unique_icons():
    """One icon name per distinct spec (several names share a drawing)."""
    first = {}
    for name, spec in ICON_MAP.items():
        first.setdefault(spec, name)
    return list(first.values())


# Glyphs redrawn from their Tabler original (same 24 unit grid and style),
# where a detail read too weak at toolbar sizes:
# - info-circle: Tabler's "i" is a 4 unit stem and a dot drawn as a
#   zero-length line, one pixel at 1 px strokes; here a solid dot and a
#   taller stem with a foot.
# - sql: the letters, 8 units tall, stretched to 11.2 (and 5 % wider) so
#   they fill more of the button; sql-raised (with a badge) sits higher, so
#   the "L" stays clear of the badge's cut-out. The "Q" is drawn like the
#   "S" (and the "SHP" letters): straight sides with small rounded corners,
#   its tail a short slant below the bowl, so the bowl stays as open as an
#   "H" or "P" at 1 px lines (a tail inside it filled it in).
# - shp-raised: "SHP" for shapefiles, drawn like sql-raised.
# - feather (SpatiaLite): Tabler's three barbs, small steps along the
#   quill, blurred together at toolbar sizes; here without the middle one,
#   and the quill only below the vane.
# Globes leaving a corner for their symbol (gear, arrow, magnifier): Tabler
# draws their outline as one three-quarter arc, which the pixel snapping
# can only move (see _snapped_path), a pixel off the latitude lines ending
# on it; a half and a quarter circle are fitted to their snapped ends.
GLOBE_OUTLINE = '<path d="M21 12a9 9 0 0 0 -18 0a9 9 0 0 0 9 9"/>'
CUSTOM_GLYPHS = {
    "world-cog": GLOBE_OUTLINE + (
        '<path d="M3.6 9h16.8"/><path d="M3.6 15h8.9"/><path d="M11.5 3a17 17 0 0 0 0 18"/>'
        '<path d="M12.5 3a16.992 16.992 0 0 1 2.522 10.376"/>'
        '<path d="M17.001 19a2 2 0 1 0 4 0a2 2 0 1 0 -4 0"/><path d="M19.001 15.5v1.5"/>'
        '<path d="M19.001 21v1.5"/><path d="M22.032 17.25l-1.299 .75"/><path d="M17.27 20l-1.3 .75"/>'
        '<path d="M15.97 17.25l1.3 .75"/><path d="M20.733 20l1.3 .75"/>'
    ),
    "world-download": GLOBE_OUTLINE + (
        '<path d="M3.6 9h16.8"/><path d="M3.6 15h8.4"/><path d="M11.578 3a17 17 0 0 0 0 18"/>'
        '<path d="M12.5 3c1.719 2.755 2.5 5.876 2.5 9"/><path d="M18 14v7m-3 -3l3 3l3 -3"/>'
    ),
    "world-search": GLOBE_OUTLINE + (
        '<path d="M3.6 9h16.8"/><path d="M3.6 15h7.9"/><path d="M11.5 3a17 17 0 0 0 0 18"/>'
        '<path d="M12.5 3a16.984 16.984 0 0 1 2.574 8.62"/>'
        '<path d="M15 18a3 3 0 1 0 6 0a3 3 0 1 0 -6 0"/><path d="M20.2 20.2l1.8 1.8"/>'
    ),
    "world-share": GLOBE_OUTLINE + (
        '<path d="M3.6 9h16.8"/><path d="M3.6 15h9.4"/><path d="M11.5 3a17 17 0 0 0 0 18"/>'
        '<path d="M12.5 3a16.991 16.991 0 0 1 2.529 10.294"/><path d="M16 22l5 -5"/>'
        '<path d="M21 21.5v-4.5h-4.5"/>'
    ),
    # A toolbox, as ArcGIS shows its toolboxes: a box, its lid, the handle
    # and a latch.
    "toolbox": ('<path d="M2 10h20v10h-20z"/><path d="M2 10l2 -3h16l2 3z"/><path d="M9 7v-3h6v3"/>'
                '<path d="M10.5 11.5h3v3h-3z"/>'),
    # Playing backwards (Temporal Controller): Tabler's play, mirrored.
    "player-play-back": '<path d="M17 4v16l-13 -8l13 -8"/>',
    # Drawn after Tabler's glyphs of these names (same grid and style), for
    # the 1.3 icons (text formatting, alignment, line caps and joins...).
    "arrow-bar-to-left": '<path d="M10 12l10 0"/><path d="M10 12l4 4"/><path d="M10 12l4 -4"/><path d="M4 4l0 16"/>',
    "bold": '<path d="M7 5h6a3.5 3.5 0 0 1 0 7h-6z"/><path d="M13 12h1a3.5 3.5 0 0 1 0 7h-7v-7"/>',
    "italic": '<path d="M11 5l6 0"/><path d="M7 19l6 0"/><path d="M14 5l-4 14"/>',
    "underline": '<path d="M7 5v5a5 5 0 0 0 10 0v-5"/><path d="M5 19h14"/>',
    "strikethrough": (
        '<path d="M5 12l14 0"/><path d="M16 6.5a4 2 0 0 0 -4 -1.5h-1a3.5 3.5 0 0 0 0 7h2'
        'a3.5 3.5 0 0 1 0 7h-1.5a4 2 0 0 1 -4 -1.5"/>'
    ),
    "align-left": '<path d="M4 6l16 0"/><path d="M4 12l10 0"/><path d="M4 18l14 0"/>',
    "align-center": '<path d="M4 6l16 0"/><path d="M8 12l8 0"/><path d="M6 18l12 0"/>',
    "align-right": '<path d="M4 6l16 0"/><path d="M10 12l10 0"/><path d="M6 18l14 0"/>',
    "align-justified": '<path d="M4 6l16 0"/><path d="M4 12l16 0"/><path d="M4 18l12 0"/>',
    "indent-decrease": (
        '<path d="M20 6l-7 0"/><path d="M20 12l-9 0"/><path d="M20 18l-7 0"/><path d="M8 8l-4 4l4 4"/>'
    ),
    "square-check": (
        '<path d="M3 5a2 2 0 0 1 2 -2h14a2 2 0 0 1 2 2v14a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2z"/>'
        '<path d="M9 12l2 2l4 -4"/>'
    ),
    "paperclip": (
        '<path d="M15 7l-6.5 6.5a1.5 1.5 0 0 0 3 3l6.5 -6.5a3 3 0 0 0 -6 -6l-6.5 6.5a4.5 4.5 0 0 0 9 9l6.5 -6.5"/>'
    ),
    "corner-down-right": '<path d="M6 6v6a3 3 0 0 0 3 3h10"/><path d="M15 11l4 4l-4 4"/>',
    "link-off": (
        '<path d="M9 15l3 -3m2 -2l1 -1"/><path d="M11 6l.463 -.536a5 5 0 0 1 7.071 7.072l-.534 .464"/>'
        '<path d="M13 18l-.397 .534a5.068 5.068 0 0 1 -7.127 0a4.972 4.972 0 0 1 0 -7.071l.524 -.463"/>'
        '<path d="M3 3l18 18"/>'
    ),
    "equal-not": '<path d="M5 10h14"/><path d="M5 14h14"/><path d="M19 5l-14 14"/>',
    # Line caps and joins (symbol stroke options): a wide stroke's outline
    # ending at, or turning round, the line through its middle.
    "cap-flat": '<path d="M3 8h12v8h-12"/><path d="M3 12h12"/>',
    "cap-square": '<path d="M3 8h16v8h-16"/><path d="M3 12h12"/>',
    "cap-round": '<path d="M3 8h12a4 4 0 0 1 0 8h-12"/><path d="M3 12h12"/>',
    "join-miter": '<path d="M4 21v-17h17"/><path d="M10 21v-11h11"/>',
    "join-bevel": '<path d="M4 21v-12l5 -5h12"/><path d="M10 21v-11h11"/>',
    "join-round": '<path d="M4 21v-11a6 6 0 0 1 6 -6h11"/><path d="M10 21v-11h11"/>',
    # Classification methods (Graduated renderer > Mode): a bell curve over
    # a baseline, the class breaks rising from the baseline to the curve,
    # spaced as each method spaces them.
    "class-equal-interval": (
        '<path d="M3 20h18"/><path d="M3 19c4.5 0 5.5 -12 9 -12s4.5 12 9 12"/>'
        '<path d="M8 20V12.69"/><path d="M12 20V7"/><path d="M16 20V12.69"/>'
    ),
    "class-equal-count": (
        '<path d="M3 20h18"/><path d="M3 19c4.5 0 5.5 -12 9 -12s4.5 12 9 12"/>'
        '<path d="M9.5 20V9.33"/><path d="M12 20V7"/><path d="M14.5 20V9.33"/>'
    ),
    "class-fixed-interval": (
        '<path d="M3 20h18"/><path d="M3 19c4.5 0 5.5 -12 9 -12s4.5 12 9 12"/>'
        '<path d="M6.5 20V15.98"/><path d="M10 20V8.46"/><path d="M14 20V8.46"/><path d="M17.5 20V15.98"/>'
    ),
    "class-logarithmic": (
        '<path d="M3 20h18"/><path d="M3 19c4.5 0 5.5 -12 9 -12s4.5 12 9 12"/>'
        '<path d="M7 20V14.99"/><path d="M9 20V10.34"/><path d="M13.5 20V7.8"/>'
    ),
    "class-natural-breaks": (
        '<path d="M3 20h18"/><path d="M3 19c4.5 0 5.5 -12 9 -12s4.5 12 9 12"/>'
        '<path d="M7.5 20V13.9"/><path d="M11 20V7.35"/><path d="M16.5 20V13.9"/>'
    ),
    "class-pretty-breaks": (
        '<path d="M3 20h18"/><path d="M3 19c4.5 0 5.5 -12 9 -12s4.5 12 9 12"/>'
        '<path d="M8 20V10.69"/><path d="M6.75 10.69h2.5"/><path d="M12 20V5"/><path d="M10.75 5h2.5"/><path d="M16 20V10.69"/><path d="M14.75 10.69h2.5"/>'
    ),
    "class-std-dev": (
        '<path d="M3 20h18"/><path d="M3 19c4.5 0 5.5 -12 9 -12s4.5 12 9 12"/>'
        '<path d="M12 20V4"/><path d="M8.5 20V11.48"/><path d="M15.5 20V11.48"/>'
    ),
    # Tabler's help-circle with a larger question mark: its own one is too
    # small to read inside the circle at toolbar and rail sizes.
    "help-circle": (
        '<path d="M3 12a9 9 0 1 0 18 0a9 9 0 0 0 -18 0"/>'
        '<path d="M9.5 9.5a2.5 2.5 0 1 1 4.42 1.61c-1.2 .55 -1.92 1.1 -1.92 2.1v.4"/>'
        '<path d="M12 16.75v.01"/>'
    ),
    "info-circle": (
        '<path d="M3 12a9 9 0 1 0 18 0a9 9 0 0 0 -18 0"/>'
        '<path d="M11 7.5a1 1 0 1 0 2 0a1 1 0 1 0 -2 0" fill="currentColor"/>'
        '<path d="M10.5 10.5h1.5v6.5h1.5"/>'
    ),
    "sql": (
        '<path d="M10.95 6.4L13.05 6.4A1.05 1.4 0 0 1 14.1 7.8L14.1 16.2A1.05 1.4 0 0 1 13.05 17.6'
        'L10.95 17.6A1.05 1.4 0 0 1 9.9 16.2L9.9 7.8A1.05 1.4 0 0 1 10.95 6.4"/>'
        '<path d="M12.6 17.6L13.6 19.2"/>'
        '<path d="M17.25 6.4L17.25 17.6L21.45 17.6"/>'
        '<path d="M2.55 16.2A1.05 1.4 0 0 0 3.6 17.6L5.7 17.6A1.05 1.4 0 0 0 6.75 16.2L6.75 13.4'
        'A1.05 1.4 0 0 0 5.7 12L3.6 12A1.05 1.4 0 0 1 2.55 10.6L2.55 7.8A1.05 1.4 0 0 1 3.6 6.4'
        'L5.7 6.4A1.05 1.4 0 0 1 6.75 7.8"/>'
    ),
    "sql-raised": (
        '<path d="M10.95 3.4L13.05 3.4A1.05 1.4 0 0 1 14.1 4.8L14.1 13.2A1.05 1.4 0 0 1 13.05 14.6'
        'L10.95 14.6A1.05 1.4 0 0 1 9.9 13.2L9.9 4.8A1.05 1.4 0 0 1 10.95 3.4"/>'
        '<path d="M12.6 14.6L13.6 16.2"/>'
        '<path d="M17.25 3.4L17.25 14.6L21.45 14.6"/>'
        '<path d="M2.55 13.2A1.05 1.4 0 0 0 3.6 14.6L5.7 14.6A1.05 1.4 0 0 0 6.75 13.2L6.75 10.4'
        'A1.05 1.4 0 0 0 5.7 9L3.6 9A1.05 1.4 0 0 1 2.55 7.6L2.55 4.8A1.05 1.4 0 0 1 3.6 3.4'
        'L5.7 3.4A1.05 1.4 0 0 1 6.75 4.8"/>'
    ),
    "shp-raised": (
        '<path d="M2.55 13.2A1.05 1.4 0 0 0 3.6 14.6L5.7 14.6A1.05 1.4 0 0 0 6.75 13.2L6.75 10.4'
        'A1.05 1.4 0 0 0 5.7 9L3.6 9A1.05 1.4 0 0 1 2.55 7.6L2.55 4.8A1.05 1.4 0 0 1 3.6 3.4'
        'L5.7 3.4A1.05 1.4 0 0 1 6.75 4.8"/>'
        '<path d="M9.9 3.4L9.9 14.6M14.1 3.4L14.1 14.6M9.9 9L14.1 9"/>'
        '<path d="M17.25 14.6L17.25 3.4L20.4 3.4A1.05 1.4 0 0 1 21.45 4.8L21.45 7.6'
        'A1.05 1.4 0 0 1 20.4 9L17.25 9"/>'
    ),
    "feather": (
        '<path d="M4 20l2 -2m8 -13v5h5m-13 3v5h5m-5 -5l8 -8"/>'
        '<path d="M19 10c.638 -.636 1 -1.515 1 -2.486a3.515 3.515 0 0 0 -3.517 -3.514'
        'c-.97 0 -1.847 .367 -2.483 1m-3 13l4 -4l4 -4"/>'
    ),
}


@functools.lru_cache(maxsize=None)
def _glyph_body(name):
    if name.startswith(COLOR_PREFIX):
        return COLOR_GLYPHS[name[len(COLOR_PREFIX):]]
    if name in CUSTOM_GLYPHS:
        return CUSTOM_GLYPHS[name]
    svg = (GLYPHS_DIR / f"{name}.svg").read_text(encoding="utf-8")
    return _FRAME.sub("", _BODY.search(svg).group(1)).strip()


def render_icon(spec, colors, scale=SCALE):
    """Compose one icon. ``colors`` provides icon, accent and danger (used
    for remove badges); ``scale`` enlarges unbadged glyphs."""
    glyph, _, badge = spec.partition("+")
    body = _glyph_body(glyph).replace("currentColor", colors["icon"])
    if badge:
        # Shrink the glyph towards the top-left to leave room for the badge.
        scale, transform = BADGED_SCALE, f"translate(0.2 0.2) scale({BADGED_SCALE})"
    else:
        # Never enlarged so far that a line would be cut off at the edge.
        reach = _glyph_reach(glyph)
        if reach > 0:
            scale = min(scale, (12 - STROKE / 2) / reach)
        offset = round(12 * (1 - scale), 3)
        transform = f"translate({offset} {offset}) scale({scale})"
    # The stroke is scaled with the glyph: compensate so every icon ends up
    # with the same visible line weight.
    stroke = round(STROKE / scale, 3)
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
        'viewBox="0 0 24 24" fill="none" stroke-linecap="round" '
        'stroke-linejoin="round">',
    ]
    mask = ""
    if badge:
        parts.append(
            '<defs><mask id="b" maskUnits="userSpaceOnUse" x="0" y="0" width="24" height="24">'
            '<rect width="24" height="24" fill="#fff"/>'
            f'<circle cx="{BADGE_CENTER}" cy="{BADGE_CENTER}" r="{BADGE_RADIUS + BADGE_GAP}" fill="#000"/>'
            '</mask></defs>'
        )
        mask = ' mask="url(#b)"'
    parts.append(
        f'<g{mask}><g transform="{transform}" stroke="{colors["icon"]}" '
        f'stroke-width="{stroke}">{body}</g></g>'
    )
    if badge in BADGE_MARKS:
        parts.append(
            f'<path d="{_mark_path(BADGE_MARKS[badge], BADGE_CENTER, MARK_ARM)}" '
            f'stroke="{colors["icon"]}" stroke-width="{STROKE}"/>'
        )
    elif badge:
        fill = colors["danger"] if badge == "x" else colors["accent"]
        parts.append(
            f'<circle cx="{BADGE_CENTER}" cy="{BADGE_CENTER}" r="{BADGE_RADIUS}" fill="{fill}"/>'
        )
    parts.append("</svg>")
    return "".join(parts)


# ---- Pixel-snapped rendering (pre-rendered PNGs) ---------------------------

def stroke_px(size):
    """Line width in whole device pixels for an icon of `size` px: 1 px up
    to 25 px, 2 px from 28 to 40 px, 3 px at 48 px. That keeps the line
    about as thick on paper on every screen: 1 px on a ~95 PPI desktop
    monitor (0.27 mm) is close to 2 px on a laptop at 150 percent
    (0.32 mm), while 2 px there (0.53 mm) looked heavy and crowded
    detailed glyphs."""
    return max(1, math.floor(STROKE * size / 24 + 0.25))


def screen_stroke_px(ratio):
    """Line width in device pixels of every icon on a screen at `ratio`:
    that of a 24 px toolbar icon there (1 px at 100 percent, 2 px at
    125-175, 3 px at 200), whatever the icon's size, so menus, panels,
    toolbars and dialog page lists all share one line weight."""
    return stroke_px(round(24 * ratio))


def _parse(d):
    """Path data as absolute segments: ("M"|"L", x, y),
    ("C", x1, y1, x2, y2, x, y), ("A", rx, ry, rot, large, sweep, x, y)
    and ("Z",). Covers the commands Tabler uses (M L H V C S A Z)."""
    tokens = _TOKEN.findall(d)
    segments = []
    x = y = start_x = start_y = 0.0
    control = None  # second control point of the previous C/S, for S
    command = None
    i = 0
    while i < len(tokens):
        if tokens[i].isalpha():
            command = tokens[i]
            i += 1
            if command in "Zz":
                segments.append(("Z",))
                x, y = start_x, start_y
                control = None
                continue
        kind = command.upper()
        count = _ARGS[kind]
        args = [float(v) for v in tokens[i:i + count]]
        if len(args) < count:
            raise ValueError(f"bad path data: {d}")
        i += count
        dx, dy = (x, y) if command.islower() else (0.0, 0.0)
        if kind == "M":
            x, y = args[0] + dx, args[1] + dy
            start_x, start_y = x, y
            segments.append(("M", x, y))
            # Further pairs after a moveto are linetos.
            command = "l" if command.islower() else "L"
            control = None
        elif kind in "LHV":
            if kind == "L":
                x, y = args[0] + dx, args[1] + dy
            elif kind == "H":
                x = args[0] + dx
            else:
                y = args[0] + dy
            segments.append(("L", x, y))
            control = None
        elif kind in "CS":
            if kind == "C":
                x1, y1 = args[0] + dx, args[1] + dy
                rest = args[2:]
            else:
                x1, y1 = (2 * x - control[0], 2 * y - control[1]) if control else (x, y)
                rest = args
            x2, y2 = rest[0] + dx, rest[1] + dy
            x, y = rest[2] + dx, rest[3] + dy
            segments.append(("C", x1, y1, x2, y2, x, y))
            control = (x2, y2)
        else:
            x, y = args[5] + dx, args[6] + dy
            segments.append(("A", *args[:5], x, y))
            control = None
    return segments


@functools.lru_cache(maxsize=None)
def _glyph_paths(name):
    """(segments, extra attributes) of every path of a glyph."""
    return tuple((tuple(_parse(d)), attrs) for d, attrs in _PATH.findall(_glyph_body(name)))


def _num(value):
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _subpaths(segments):
    """A path's subpaths, each with whether it is closed (ends with Z or
    where it starts): only closed ones are filled unless a material says
    "!"."""
    out = []
    current = []
    for segment in segments + (("M", None, None),):
        if segment[0] == "M" and current:
            start, last = current[0], current[-1]
            closed = last[0] == "Z" or (
                last[0] != "M" and abs(last[-2] - start[1]) < 0.01 and abs(last[-1] - start[2]) < 0.01)
            if len(current) > 1:
                out.append((tuple(current), closed))
            current = []
        if segment[1:2] != (None,):
            current.append(segment)
    return out


def _plain_path(segments):
    """Path data of absolute segments, unchanged (render_icon_color)."""
    return "".join(segment[0] + " ".join(_num(v) for v in segment[1:]) for segment in segments)


def _arc_kind(rx, ry, dx, dy):
    """How an arc may follow its snapped ends: "quarter" (a rounded corner,
    its ends one radius apart on each axis), "half" (half a circle, its
    ends a diameter apart) or "other" (any other part of a circle)."""
    dx, dy = abs(dx), abs(dy)
    if abs(dx - rx) <= 0.15 * rx and abs(dy - ry) <= 0.15 * ry:
        return "quarter"
    if abs(math.hypot(dx, dy) - 2 * rx) <= 0.1 * rx:
        return "half"
    return "other"


def _snapped_path(segments, place, snap, unit):
    """Path data in device pixels: endpoints moved onto the pixel grid,
    curve controls moved with their endpoint. Arcs keep their shape:
    a rounded corner stretches per axis with its snapped ends (so it still
    meets its straight edges), half a circle scales evenly with them (so a
    circle stays round), and any other arc is moved as a whole with its
    start point. Stretching those by their ends would distort them: the
    330 degree arc of "history" has ends 0.5 units apart, and stretching it
    by how much snapping changed that gap collapsed or doubled the circle."""
    out = []
    here = here_snapped = start = start_snapped = (0.0, 0.0)
    for segment in segments:
        kind = segment[0]
        if kind == "Z":
            out.append("Z")
            here, here_snapped = start, start_snapped
            continue
        end = place(segment[-2], segment[-1])
        end_snapped = (snap(end[0]), snap(end[1]))
        if kind == "M":
            out.append(f"M{_num(end_snapped[0])} {_num(end_snapped[1])}")
            start, start_snapped = end, end_snapped
        elif kind == "L":
            dx, dy = end[0] - here[0], end[1] - here[1]
            if end_snapped == here_snapped and math.hypot(dx, dy) >= 0.5:
                # A short tick (a sun ray) snapped onto its own start would
                # vanish: keep it one pixel long, in its main direction.
                step = (math.copysign(1, dx), 0) if abs(dx) >= abs(dy) else (0, math.copysign(1, dy))
                if abs(dx) > 1e-6 and abs(dy) > 1e-6 and 0.5 < abs(dx / dy) < 2:
                    step = (math.copysign(1, dx), math.copysign(1, dy))
                end_snapped = (here_snapped[0] + step[0], here_snapped[1] + step[1])
            out.append(f"L{_num(end_snapped[0])} {_num(end_snapped[1])}")
        elif kind == "C":
            c1, c2 = place(segment[1], segment[2]), place(segment[3], segment[4])
            c1 = (c1[0] + here_snapped[0] - here[0], c1[1] + here_snapped[1] - here[1])
            c2 = (c2[0] + end_snapped[0] - end[0], c2[1] + end_snapped[1] - end[1])
            out.append("C" + " ".join(_num(v) for v in (*c1, *c2, *end_snapped)))
        else:
            rx, ry, rotation, large, sweep = segment[1:6]
            dx, dy = end[0] - here[0], end[1] - here[1]
            sdx, sdy = end_snapped[0] - here_snapped[0], end_snapped[1] - here_snapped[1]
            arc = _arc_kind(rx * unit, ry * unit, dx, dy)
            if arc == "quarter":
                fx = sdx / dx if abs(dx) > 1e-6 else 1.0
                fy = sdy / dy if abs(dy) > 1e-6 else 1.0
            elif arc == "half":
                fx = fy = math.hypot(sdx, sdy) / math.hypot(dx, dy)
            else:
                fx = fy = 1.0
                end_snapped = (here_snapped[0] + dx, here_snapped[1] + dy)
            if fx > 0 and fy > 0:
                out.append("A" + " ".join(_num(v) for v in (
                    rx * unit * fx, ry * unit * fy, rotation, large, sweep, *end_snapped,
                )))
            else:
                # A tiny corner collapsed onto one pixel: a dot or nothing.
                out.append(f"L{_num(end_snapped[0])} {_num(end_snapped[1])}")
        here, here_snapped = end, end_snapped
    return "".join(out)


def _arc_points(x1, y1, rx, ry, large, sweep, x2, y2, steps=24):
    """Points along an SVG arc (rotation 0), for measuring a glyph."""
    hx, hy = (x1 - x2) / 2, (y1 - y2) / 2
    if (hx == 0 and hy == 0) or rx == 0 or ry == 0:
        return [(x2, y2)]
    grow = hx * hx / (rx * rx) + hy * hy / (ry * ry)
    if grow > 1:
        rx, ry = rx * math.sqrt(grow), ry * math.sqrt(grow)
    num = rx * rx * ry * ry - rx * rx * hy * hy - ry * ry * hx * hx
    den = rx * rx * hy * hy + ry * ry * hx * hx
    coef = math.sqrt(max(0.0, num / den)) * (-1 if large == sweep else 1)
    cx = coef * rx * hy / ry + (x1 + x2) / 2
    cy = -coef * ry * hx / rx + (y1 + y2) / 2
    a1 = math.atan2((y1 - cy) / ry, (x1 - cx) / rx)
    a2 = math.atan2((y2 - cy) / ry, (x2 - cx) / rx)
    span = a2 - a1
    if sweep and span < 0:
        span += 2 * math.pi
    elif not sweep and span > 0:
        span -= 2 * math.pi
    return [(cx + rx * math.cos(a1 + span * i / steps), cy + ry * math.sin(a1 + span * i / steps))
            for i in range(steps + 1)]


@functools.lru_cache(maxsize=None)
def _glyph_reach(name):
    """How far a glyph's lines reach from the centre (12, 12), in units."""
    return _paths_reach(_glyph_paths(name))


def _paths_reach(paths):
    """How far the lines of (segments, attributes) paths reach from the
    centre (12, 12), in units."""
    reach = 0.0
    for segments, _ in paths:
        here = start = (12.0, 12.0)
        for segment in segments:
            if segment[0] == "Z":
                here = start
                continue
            if segment[0] == "A":
                points = _arc_points(*here, segment[1], segment[2], *segment[4:8])
            elif segment[0] == "C":
                points = [segment[1:3], segment[3:5], segment[5:7]]
            else:
                points = [segment[1:3]]
            for x, y in points:
                reach = max(reach, abs(x - 12), abs(y - 12))
            here = (segment[-2], segment[-1])
            if segment[0] == "M":
                start = here
    return reach


def _snap_circle(center, radius):
    """A dot's centre and radius with its bounding box on whole pixels."""
    diameter = max(2, round(2 * radius))
    offset = 0.0 if diameter % 2 == 0 else 0.5
    return math.floor(center - offset + 0.5) + offset, diameter / 2


def render_icon_px(spec, colors, size, scale=SCALE, width=None):
    """Compose one icon for exactly `size` device pixels, with its lines on
    the pixel grid (see the module docstring), `width` device pixels wide
    (by default the width for its size, see stroke_px). Same design as
    render_icon: same glyph enlargement and badge, in whole pixels."""
    glyph, _, badge = spec.partition("+")
    px = size / 24
    width = stroke_px(size) if width is None else width
    if badge:
        badged = BADGED_SCALE_SMALL if size <= 20 else BADGED_SCALE
        unit = badged * px

        def place(x, y):
            return (0.2 + badged * x) * px, (0.2 + badged * y) * px
    else:
        # Enlarged, but never so far that a line (with its round cap)
        # would be cut off at the icon's edge.
        reach = _glyph_reach(glyph)
        unit = scale * px
        if reach > 0:
            unit = min(unit, (size / 2 - width / 2) / reach)
        middle = size / 2

        def place(x, y):
            return middle + (x - 12) * unit, middle + (y - 12) * unit
    # Odd widths are centred on pixel centres, even ones on pixel edges;
    # lines stay a half width inside the icon.
    offset = 0.5 if width % 2 else 0.0
    low, high = width / 2, size - width / 2

    def snap(value):
        return min(max(math.floor(value - offset + 0.5) + offset, low), high)

    icon = colors["icon"]
    paths = "".join(
        f'<path d="{_snapped_path(segments, place, snap, unit)}"'
        f'{attrs.replace("currentColor", icon)}/>'
        for segments, attrs in _glyph_paths(glyph)
    )
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}" fill="none" stroke-linecap="round" '
        'stroke-linejoin="round">',
    ]
    mask = ""
    if badge:
        center, radius = _snap_circle(BADGE_CENTER * px, BADGE_RADIUS * px)
        gap = max(1, round(BADGE_GAP * px))
        parts.append(
            f'<defs><mask id="b" maskUnits="userSpaceOnUse" x="0" y="0" width="{size}" height="{size}">'
            f'<rect width="{size}" height="{size}" fill="#fff"/>'
            f'<circle cx="{_num(center)}" cy="{_num(center)}" r="{_num(radius + gap)}" fill="#000"/>'
            '</mask></defs>'
        )
        mask = ' mask="url(#b)"'
    # Lines stay centred on the pixel grid for `width`; STROKE_EXTRA widens
    # them by a fraction of a pixel, a faint edge either side of the solid
    # core, for a touch more weight without blurring the line.
    drawn = _num(width + STROKE_EXTRA)
    parts.append(f'<g{mask} stroke="{icon}" stroke-width="{drawn}">{paths}</g>')
    if badge in BADGE_MARKS:
        # On the same pixel grid as the glyph's lines, with square ends so
        # straight marks end on whole pixels.
        mark = BADGE_MARKS[badge]
        middle = snap(BADGE_CENTER * px)
        arm = max(2, round(MARK_ARM * px))
        cap = "round" if mark == "check" else "square"
        parts.append(
            f'<path d="{_mark_path(mark, middle, arm)}" stroke="{icon}" stroke-width="{drawn}" '
            f'stroke-linecap="{cap}"/>'
        )
    elif badge:
        fill = colors["danger"] if badge == "x" else colors["accent"]
        parts.append(f'<circle cx="{_num(center)}" cy="{_num(center)}" r="{_num(radius)}" fill="{fill}"/>')
    parts.append("</svg>")
    return "".join(parts)


# ---- Colourful rendering ----------------------------------------------------

# Materials of each part (path) of a glyph, in path order (see Colourful
# icons above); the last one repeats for any further parts. Glyphs not
# listed are drawn in ink.
COLOR_RECIPES = {
    # Files and folders: white paper, a yellow folder.
    "folder": ("folder!",), "folder-open": ("folder!",),
    "file": ("paper/", "paper!"), "files": ("paper/", "paper!", "paper!"),
    "file-export": ("paper/", "paper!"), "file-import": ("paper/", "paper!"),
    "file-code": ("paper/", "paper!", "blueS/"), "file-pencil": ("paper/", "paper!", "orangeS/"),
    "file-settings": ("grayS/",) * 7 + ("paper/", "paper!"), "file-database": ("paper/", "paper!", "blue!"),
    "file-symlink": ("paper/", "paper!", "blueS/"), "file-zip": ("paper/", "paper!", "brownS/"),
    "file-x": ("paper/", "paper!", "redS/"), "file-type-pdf": ("paper/", "paper!", "redS/"),
    "file-type-csv": ("paper/", "paper!", "greenS/"), "file-type-svg": ("paper/", "paper!", "orangeS/"),
    "template": ("blue", "green", "ink"),
    "report": ("paper!", "ink", "ink", "gray!", "glass", "ink", "ink"),
    "device-floppy": ("blueS!", "grayS", "gray!"),
    # Magnifiers: light blue glass in an ink frame.
    "search": ("glass", "ink"), "zoom-in": ("glass", "green/", "green/", "ink"),
    "zoom-out": ("glass", "red/", "ink"), "zoom-check": ("glass", "ink", "dark/"),
    "zoom-pan": ("glass", "ink", "tealS/"), "zoom-scan": ("glass", "ink", "grayS/"),
    "zoom-in-area": ("dark/", "dark/", "glass", "ink", "grayS/"), "zoom-reset": ("ink", "ink", "tealS/"),
    "map-pin-search": ("redS/", "redS/", "glass", "ink"),
    "world-search": ("blue!", "blueS/", "blueS/", "blueS/", "blueS/", "glass", "ink"),
    # Data: databases, tables, layers, maps, the world.
    "database": ("blue", "blue!", "blue!"),
    "database-cog": ("blue/", "blue!", "blue/", "blue!", "grayS", "grayS/"),
    "database-plus": ("blue/", "blue!", "blue/", "blue!", "greenS/"),
    "database-export": ("blue/", "blue!", "blue/", "blue!", "greenS/"),
    "database-import": ("blue/", "blue!", "blue!", "greenS/"),
    "table": ("paper", "blueS/"), "table-options": ("paper", "blueS/"),
    "stack-2": ("yellowS", "greenS/", "blueS/"), "stack-3": ("yellowS", "greenS/", "blueS/", "tealS/"),
    "map": ("green!", "greenS/"), "map-2": ("green!", "greenS/", "greenS/", "redS", "white/"),
    "world": ("blue", "blueS/"), "world-www": ("blue!", "blueS/", "blueS/", "blue!", "blueS/", "blueS/", "ink"),
    "world-cog": ("blue!", "blueS/"), "world-download": ("blue!", "blueS/"), "world-share": ("blue!", "blueS/"),
    "world-latitude": ("blue", "blueS/"), "sphere": ("blueS/", "blue"), "cube": ("blue!", "blueS/"),
    "package": ("brown", "brownS/"), "box": ("blue", "blueS/"), "packages": ("gray", "grayS/"),
    "cloud": ("glass!",), "cloud-download": ("glass!", "greenS/"),
    "cloud-upload": ("glass!", "blueS/"),
    "network": ("blue", "blueS/", "blueS/", "blueS/", "ink", "ink", "greenS", "ink"),
    "link": ("blueS/",), "link-off": ("blueS/", "blueS/", "blueS/", "red/"),
    # Raster and nature: photos, terrain, sun, plants, water.
    "photo": ("yellowS/", "glass", "greenS!", "greenS!"),
    "photo-down": ("yellowS/", "glass!", "greenS!", "greenS!", "blueS/"),
    "mountain": ("green!", "greenS/"), "sun": ("yellowS", "orangeS/"), "sun-high": ("yellowS", "orangeS/"),
    "plant": ("brownS!", "greenS!", "greenS!", "greenS/"), "droplet": ("blueS",), "droplet-half": ("blueS",),
    "flame": ("orangeS",), "pyramid": ("yellow!", "orangeS/"),
    # Editing: pencils, erasers, scissors, rulers, magnets, shapes.
    "pencil": ("yellowS!", "ink"), "pencil-bolt": ("yellowS!", "ink", "orangeS"),
    "pencil-cog": ("yellowS!", "ink", "grayS"), "pencil-cancel": ("yellowS!", "ink", "redS/"),
    "eraser": ("pinkS!", "ink"), "highlight": ("yellowS!", "ink", "ink", "yellowS!"),
    "cut": ("redS", "redS", "grayS/", "grayS/"),
    "copy": ("paper", "paper!"), "clipboard": ("woodS!", "gray!"),
    "ruler": ("gray!", "ink"), "ruler-2": ("gray!", "ink"),
    "ruler-3": ("gray!", "ink"), "ruler-measure": ("gray!", "ink"),
    "magnet": ("redS!", "white/", "white/"),
    "polygon": ("greenS", "greenS", "greenS", "greenS", "greenS/"), "point": ("redS",),
    "line": ("blueS", "blueS", "ink"),
    # Analysis: tools, charts, maths, code, Python.
    "tool": ("grayS!",), "bolt": ("yellowS",), "puzzle": ("greenS",),
    "toolbox": ("toolredS", "toolredS", "grayS/", "paper"),
    "calculator": ("gray!", "paper!", "ink"),
    "chart-bar": ("tealS", "orangeS", "blueS", "ink"), "chart-pie": ("blueS", "orangeS"),
    "chart-dots": ("ink", "redS", "blueS", "greenS", "ink"),
    
    "terminal-2": ("greenS/", "greenS/", "grayS"), "code": ("blueS/", "blueS/", "grayS/"),
    "filter": ("grayS",), "filter-code": ("grayS", "blueS/"),
    # Viewing: eyes, pins, bookmarks, clocks, calendars, pointers.
    "eye": ("blueS", "paper!"), "eye-off": ("blueS/", "ink", "redS/"),
    "eye-check": ("blueS", "paper!", "greenS/"), "eye-minus": ("blueS", "paper!", "redS/"),
    "map-pin": ("paper", "redS!"), "map-pins": ("redS!", "white/", "blueS!", "white/"),
    "bookmark": ("redS",), "bookmarks": ("redS", "redS/"),
    "clock": ("paper", "ink"), "clock-play": ("paper", "ink", "greenS"),
    "calendar": ("paper!", "ink", "ink", "redS/", "ink"),
    "calendar-time": ("paper!", "glass", "ink", "ink", "redS/", "ink"),
    "pointer": ("paper",), "hand-stop": ("ink",), "compass": ("redS!", "paper", "ink"),
    "gps": ("paper", "blueS!"), "route": ("greenS", "redS", "blueS/"),
    "player-play": ("greenS",), "player-pause": ("blueS",), "player-stop": ("redS",),
    "player-record": ("redS",), "movie": ("gray!", "ink"),
    # Style, labels and layouts.
    "palette": ("paper!", "redS", "blueS", "greenS"),
    "color-swatch": ("blueS!", "yellowS!", "redS!", "white/"), "paint": ("orangeS", "grayS/", "grayS"),
    "label": ("gray",), "notes": ("paper!", "grayS/"),
    "message": ("ink", "ink", "blue!"), "message-dots": ("ink", "ink", "ink", "blue!"),
    "printer": ("gray!", "paper!", "paper!"),
    "layout": ("blue", "green", "yellow"), "layout-board": ("paper", "ink"),
    "star": ("yellowS",), "heart": ("redS",), "sparkles": ("yellowS",),
    "book": ("blue!", "blue!", "blueS/"),
    # Signs: information, help, warnings, ok, delete.
    "info-circle": ("blueS", "white", "white/"), "info-square-rounded": ("white/", "white/", "blueS"),
    "help-circle": ("blueS", "white/", "white/"), "alert-triangle": ("dark/", "yellowS", "dark/"),
    "circle-check": ("greenS", "white/"), "shield-check": ("blue", "greenS/"),
    "square-check": ("paper", "greenS/"),
    "x": ("red/",), "plus": ("green/",), "minus": ("red/",),
    "trash": ("grayS/", "grayS/", "grayS/", "gray!", "grayS/"),
    "bug": ("greenS", "greenS", "ink"), "logout": ("gray!", "redS/", "redS/"),
    # Places, people and things.
    "home": ("redS/", "paper!", "grayS!"), "user": ("gray", "blueS!"),
    "users": ("gray", "blueS!", "gray/", "blue!"), "settings": ("grayS", "paper"),
    "lock": ("grayS", "dark/", "grayS/"), "lock-open": ("grayS", "dark/", "grayS/"),
    "keyboard": ("gray", "ink"), "app-window": ("paper", "redS/", "yellowS/"),
    "list-details": ("ink", "ink", "ink", "ink", "blue", "green"),
    # Renderers and labelling (Layer Styling, Layer Properties).
    "square-rounded": ("blue",), "category": ("redS", "blueS", "greenS", "yellowS"),
    "chart-bar-popular": ("yellowS", "orangeS", "redS", "ink"),
    "list-tree": ("ink", "ink", "ink", "blueS/", "greenS/", "redS/"),
    "square-off": ("ink", "redS/"), "circle-off": ("ink", "redS/"),
    "arrows-join": ("greenS/", "blueS/", "ink"), "circles": ("blueS", "redS", "greenS"),
    "circles-relation": ("blueS/", "greenS/"),
    "barrier-block": ("redS", "ink", "white/", "white/", "white/", "ink"),
    "vector-spline": ("ink", "ink", "blueS/"), "corner-down-right": ("blueS/",),
    "typography": ("ink", "ink", "blueS/", "blueS/", "blueS/"),
    "text-size": ("blueS/", "blueS/", "blueS/", "ink"),
    "border-outer": ("glass", "ink"), "shadow": ("gray", "ink"), "mask": ("paper", "blue"),
    "background": ("yellow", "ink"), "adjustments-horizontal": ("blueS", "ink", "ink") * 3,
    # Objects and data drawn in lines until 1.4.
    "book-2": ("blue!", "ink", "ink"), "box-multiple": ("blue!", "blue!"), "note": ("ink", "yellow!"),
    "chart-area-line": ("green!", "blueS/"), "color-filter": ("redS/", "greenS/", "blue"),
    "layers-union": ("blue!",), "layers-intersect": ("blue", "glass"), "layers-subtract": ("blue", "ink"),
    "layers-difference": ("blue!", "ink"), "hexagons": ("green",), "squares": ("blue", "glass"),
    "triangles": ("green", "greenS"), "triangle-square-circle": ("yellowS", "greenS", "blueS"),
    "circle": ("blue",), "square": ("blue",), "triangle": ("blue",), "oval": ("blue",),
    "rectangle": ("blue",), "hexagon": ("blue",),
    "dice": ("paper", "ink"), "cpu": ("gray", "blueS", "ink"), "stopwatch": ("paper", "ink"),
    "message-report": ("yellow!", "dark/", "dark/"), "lifebuoy": ("paper", "redS", "white/"),
    "navigation-north": ("redS!", "ink"), "target": ("redS", "paper", "redS"),
    "current-location": ("blueS", "ink"), "focus-2": ("redS", "ink"),
    "player-play-back": ("greenS",), "player-skip-back": ("blueS", "ink"), "player-skip-forward": ("blueS", "ink"),
    "player-track-next": ("blueS",), "player-track-prev": ("blueS",),
}

# The Colourful drawings of the objects seen most, in the manner of QGIS's
# own icons and professional sets: square corners, straight edges and small
# real parts (a floppy's shutter and label, a document's lines of text, a
# table's header row), on the same 24-unit grid. (body, materials), the
# materials replacing the line drawing's recipe; Monochrome keeps the line
# drawings. Parts lie back to front: a sheet behind another is drawn only
# where it shows, as every fill is drawn under every line.
_COLOR_DRAWINGS = {
    # Save: a floppy with a metal shutter and its slot, a label with lines.
    "device-floppy": ('<path d="M4 3h13l4 4v14h-17z"/><path d="M8 3h8v6h-8z"/><path d="M13 4.5v3"/>'
                      '<path d="M7 13h10v8h-10z"/><path d="M9 16h6M9 18.5h6"/>',
                      ("blueS", "gray", "grayS/", "paper", "ink")),
    # Save As: a document with an arrow out.
    "file-export": ('<path d="M4 2h10l4 4v16h-14z"/><path d="M14 2v4h4z"/><path d="M7 10h7M7 13h5"/>'
                    '<path d="M11 17h10M18 14l3 3l-3 3"/>', ("paper", "gray", "ink", "blueS/")),
    # Folders: a back with its tab and a front; open, the front tilted.
    "folder": ('<path d="M2 4h7l2 2h11v14h-20z"/><path d="M2 9h20v11h-20z"/>', ("folder", "folder")),
    "folder-open": ('<path d="M2 20v-16h7l2 2h9v4h-14.5z"/><path d="M2 20l3.5 -10h17.5l-3.5 10z"/>',
                    ("yellow", "folder")),
    # Documents: a folded corner and lines of text.
    "file": ('<path d="M5 2h10l5 5v15h-15z"/><path d="M15 2v5h5z"/><path d="M8 11h9M8 14h9M8 17h6"/>',
             ("paper", "gray", "ink")),
    "files": ('<path d="M8 6v-4h9l4 4v12h-5v-8l-4 -4z"/><path d="M3 6h9l4 4v12h-13z"/><path d="M12 6v4h4z"/>'
              '<path d="M6 14h7M6 17h7"/>', ("paper", "paper", "gray", "ink")),
    "copy": ('<path d="M8 8v-6h12v13h-4v-7z"/><path d="M4 8h12v14h-12z"/><path d="M7 12h6M7 15h6M7 18h4"/>',
             ("paper", "paper", "ink")),
    "clipboard": ('<path d="M4 4h16v18h-16z"/><path d="M7 7h10v12h-10z"/><path d="M9 2h6v4h-6z"/>'
                  '<path d="M9 11h6M9 14h6M9 17h4"/>', ("woodS", "paper", "grayS", "ink")),
    "printer": ('<path d="M7 2h10v6h-10z"/><path d="M3 8h18v9h-18z"/><path d="M7 14h10v8h-10z"/>'
                '<path d="M9 17h6M9 19.5h4"/><path d="M17 10.5h1.5"/>',
                ("paper", "grayS", "paper", "ink", "greenS/")),
    # Data: a cylinder with bands, stacked layers, a table with its header.
    "database": ('<path d="M4 6v12c0 1.7 3.6 3 8 3s8 -1.3 8 -3v-12"/>'
                 '<path d="M4 6c0 -1.7 3.6 -3 8 -3s8 1.3 8 3s-3.6 3 -8 3s-8 -1.3 -8 -3z"/>'
                 '<path d="M4 10.5c0 1.7 3.6 3 8 3s8 -1.3 8 -3"/><path d="M4 14.5c0 1.7 3.6 3 8 3s8 -1.3 8 -3"/>',
                 ("blueS!", "blue", "white/", "white/")),
    "stack-2": ('<path d="M12 3l9 4.5l-9 4.5l-9 -4.5z"/><path d="M3 12.5l5 -2.5l4 2l4 -2l5 2.5l-9 4.5z"/>'
                '<path d="M3 17.5l5 -2.5l4 2l4 -2l5 2.5l-9 4.5z"/>', ("yellowS", "greenS", "blueS")),
    "table": ('<path d="M3 4h18v16h-18z"/><path d="M3 4h18v4h-18z"/><path d="M3 12h18M3 16h18M9 8v12M15 8v12"/>',
              ("paper", "blueS", "grayS/")),
    # Magnifiers: light glass with a glint, a solid handle.
    "search": ('<path d="M3 10a7 7 0 1 0 14 0a7 7 0 1 0 -14 0"/><path d="M15 14l7 7l-1.5 1.5l-7 -7z"/>'
               '<path d="M6.5 9a3.5 3.5 0 0 1 3 -2.5"/>', ("glass", "grayS", "white/")),
    "zoom-in": ('<path d="M3 10a7 7 0 1 0 14 0a7 7 0 1 0 -14 0"/><path d="M15 14l7 7l-1.5 1.5l-7 -7z"/>'
                '<path d="M7 10h6M10 7v6"/>', ("glass", "grayS", "dark/")),
    "zoom-out": ('<path d="M3 10a7 7 0 1 0 14 0a7 7 0 1 0 -14 0"/><path d="M15 14l7 7l-1.5 1.5l-7 -7z"/>'
                 '<path d="M7 10h6"/>', ("glass", "grayS", "dark/")),
    # Objects.
    "package": ('<path d="M12 3l9 4.5l-9 4.5l-9 -4.5z"/><path d="M3 7.5v9.5l9 4.5v-9.5z"/>'
                '<path d="M21 7.5v9.5l-9 4.5v-9.5z"/><path d="M7.5 5.25l9 4.5v3"/>',
                ("blue", "blueS", "blue", "blueS/")),
    "map": ('<path d="M3 5l6 -2l6 2l6 -2v16l-6 2l-6 -2l-6 2z"/><path d="M9 3v16M15 5v16"/>'
            '<path d="M5 15l3 -3l3 2l3 -4l4 2"/>', ("green", "greenS/", "redS/")),
    "photo": ('<path d="M3 4h18v16h-18z"/><path d="M3 18l5 -6l4 4l3 -3l6 6v1h-18z"/>'
              '<path d="M14 8.5a1.5 1.5 0 1 0 3 0a1.5 1.5 0 1 0 -3 0"/>', ("blue", "greenS", "yellowS")),
    "lock": ('<path d="M5 11h14v10h-14z"/><path d="M8 11v-4a4 4 0 0 1 8 0v4"/><path d="M12 14.5v3"/>',
             ("grayS", "grayS/", "dark/")),
    "calendar": ('<path d="M3 5h18v16h-18z"/><path d="M3 5h18v4h-18z"/><path d="M8 3v4M16 3v4"/>'
                 '<path d="M6 13h2M11 13h2M16 13h2M6 17h2M11 17h2"/>', ("paper", "redS", "grayS/", "ink")),
    "home": ('<path d="M5 11h14v10h-14z"/><path d="M2.5 12l9.5 -8.5l9.5 8.5z"/><path d="M10 15h4v6h-4z"/>',
             ("paper", "redS", "grayS")),
    "chart-bar": ('<path d="M3 21h18"/><path d="M5 12h4v9h-4z"/><path d="M10 6h4v15h-4z"/><path d="M15 9h4v12h-4z"/>',
                  ("ink", "blueS", "greenS", "yellowS")),
    # A wrench: a thin handle with a rounded end and an open-end head, its
    # curves arcs (a polygon's many corners bend when fitted to pixels).
    "tool": ('<path d="M5.35 20.35L14.52 11.17A4.2 4.2 0 0 0 20.4 5.86L17.37 8.89L15.11 6.63L18.14 3.6'
             'A4.2 4.2 0 0 0 12.83 9.48L3.65 18.65A1.2 1.2 0 1 0 5.35 20.35z"/>', ("grayS",)),
    # About: a square sign with the i of the round info sign.
    "info-square-rounded": ('<path d="M3 3h18v18h-18z"/><path d="M12 9h.01"/><path d="M11 12h1v4h1"/>',
                            ("blueS", "white/", "white/")),
    # Labels: a small abc on a yellow label pointed at its right end, like
    # QGIS's own, with a margin of yellow around the letters.
    "abc": ('<path d="M1.5 6h18l3 6l-3 6h-18z"/><path d="M7.25 12v3"/>'
            '<path d="M7.25 12.75v.75a1.5 1.5 0 1 1 -3 0v-.75a1.5 1.5 0 1 1 3 0"/>'
            '<path d="M9.5 9v4.5a1.5 1.5 0 1 0 3 0v-.75a1.5 1.5 0 1 0 -3 0v.75"/>'
            '<path d="M17.549 12a1.5 1.5 0 0 0 -2.799 .75v.75a1.5 1.5 0 0 0 2.795 .758"/>',
            ("yellow", "ink")),
    # A label's background: a shape under its hatching.
    "background": ('<path d="M4 4h16v16h-16z"/><path d="M4 8l4 -4"/><path d="M14 4l-10 10"/>'
                   '<path d="M4 20l16 -16"/><path d="M20 10l-10 10"/><path d="M20 16l-4 4"/>', ("yellow", "ink")),
    # Python's two snakes as closed shapes, with their eyes.
    "brand-python": ('<path d="M8 9v-4a2 2 0 0 1 2 -2h4a2 2 0 0 1 2 2v5a2 2 0 0 1 -2 2h-4a2 2 0 0 0 -2 2v3h-3'
                     'a2 2 0 0 1 -2 -2v-4a2 2 0 0 1 2 -2z"/>'
                     '<path d="M16 15v4a2 2 0 0 1 -2 2h-4a2 2 0 0 1 -2 -2v-5a2 2 0 0 1 2 -2h4a2 2 0 0 0 2 -2v-3h3'
                     'a2 2 0 0 1 2 2v4a2 2 0 0 1 -2 2z"/><path d="M11 6l0 .01"/><path d="M13 18l0 .01"/>',
                     ("blueS", "yellowS", "white/", "white/")),
    # A brush: its head, a closed handle, the ferrule.
    "brush": ('<path d="M3 21v-4a4 4 0 1 1 4 4h-4"/>'
              '<path d="M21 3a16 16 0 0 0 -12.8 10.2l2.6 2.6a16 16 0 0 0 10.2 -12.8z"/>'
              '<path d="M10.6 9a9 9 0 0 1 4.4 4.4"/>', ("blueS!", "wood", "woodS/")),
    # Layouts and reports: a page with a map frame, a legend and a title;
    # a report page with a chart.
    "layout": ('<path d="M3 3h18v18h-18z"/><path d="M5 5h10v9h-10z"/><path d="M17 6h2M17 9h2M17 12h2"/>'
               '<path d="M5 17h10M5 19h7"/>', ("paper", "green", "ink", "ink")),
    "report": ('<path d="M4 2h12l4 4v16h-16z"/><path d="M16 2v4h4z"/><path d="M8 18v-4M11.5 18v-7M15 18v-5"/>'
               '<path d="M7 7h6"/>', ("paper", "gray", "blueS/", "ink")),
    # Tools and devices.
    "calculator": ('<path d="M5 2h14v20h-14z"/><path d="M7 4h10v5h-10z"/>'
                   '<path d="M7.5 12.5h1.5M11.25 12.5h1.5M15 12.5h1.5M7.5 15.75h1.5M11.25 15.75h1.5M15 15.75h1.5'
                   'M7.5 19h1.5M11.25 19h1.5M15 19h1.5"/>', ("gray", "paper", "ink")),
    "terminal-2": ('<path d="M2 4h20v16h-20z"/><path d="M2 4h20v3h-20z"/><path d="M6 11l3 2.5l-3 2.5"/>'
                   '<path d="M11 16h5"/>', ("grayS", "blueS", "white/", "white/")),
    "pencil": ('<path d="M4 20l1 -4l11 -11l3 3l-11 11z"/><path d="M14.5 6.5l3 3"/><path d="M4 20l1 -4l3 3z"/>',
               ("yellowS", "ink", "paper")),
    "trash": ('<path d="M3 6h18v2h-18z"/><path d="M9 6v-2h6v2"/><path d="M5 8h14l-1 13h-12z"/>'
              '<path d="M9.5 11v7M14.5 11v7"/>', ("grayS", "grayS/", "gray", "grayS/")),
    # Marks, labels, messages, people, time.
    "bookmark": ('<path d="M6 2h12v20l-6 -5l-6 5z"/>', ("redS",)),
    "label": ('<path d="M2 7h14l6 5l-6 5h-14z"/><path d="M15 12a1 1 0 1 0 2 0a1 1 0 1 0 -2 0"/>',
              ("gray", "grayS/")),
    "message": ('<path d="M3 4h18v12h-9l-5 4v-4h-4z"/><path d="M7 8h10M7 11.5h7"/>', ("blue", "blueS/")),
    "user": ('<path d="M8 7a4 4 0 1 0 8 0a4 4 0 1 0 -8 0"/><path d="M4 21v-3l3 -4h10l3 4v3z"/>',
             ("gray", "blueS")),
    "clock": ('<path d="M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0"/><path d="M12 4v1.5M20 12h-1.5M12 20v-1.5M4 12h1.5"/>'
              '<path d="M12 7.5v4.5l3 2"/>', ("paper", "ink", "ink")),
}
COLOR_GLYPHS = {name: body for name, (body, _materials) in _COLOR_DRAWINGS.items()}
COLOR_RECIPES.update({name: materials for name, (_body, materials) in _COLOR_DRAWINGS.items()})
# How the paths of COLOR_GLYPHS are named for _glyph_paths.
COLOR_PREFIX = "color:"
# Colourful lines: round ends (they end inside the shapes they meet), sharp
# joins, with acute ones cut flat rather than spiking.
COLOR_STROKE = 'stroke-linecap="round" stroke-linejoin="miter" stroke-miterlimit="2"'
# Rounded corners up to this radius (units) are drawn square in Colourful
# icons; larger arcs (circles, curves) keep their shape.
SQUARE_RADIUS = 3.6


def _square_corners(segments):
    """Segments with every small rounded corner (a quarter arc) turned into
    a right angle: two straight lines meeting where the arc's tangents do."""
    out = []
    here = start = (12.0, 12.0)
    for segment in segments:
        if segment[0] == "A":
            rx, ry, _rotation, large, sweep, x, y = segment[1:8]
            if rx <= SQUARE_RADIUS and _arc_kind(rx, ry, x - here[0], y - here[1]) == "quarter":
                points = _arc_points(*here, rx, ry, large, sweep, x, y, steps=4)
                mx, my = points[len(points) // 2]
                # Of the two corners of the arc's box, the one it bulges to.
                a, b = (x, here[1]), (here[0], y)
                corner = a if (a[0] - mx) ** 2 + (a[1] - my) ** 2 < (b[0] - mx) ** 2 + (b[1] - my) ** 2 else b
                out += [("L", *corner), ("L", x, y)]
                here = (x, y)
                continue
        out.append(segment)
        if segment[0] == "Z":
            here = start
        else:
            here = (segment[-2], segment[-1])
            if segment[0] == "M":
                start = here
    return tuple(out)


@functools.lru_cache(maxsize=None)
def _color_paths(glyph):
    """The paths of a glyph's Colourful drawing: its own (COLOR_GLYPHS) or
    the line drawing, with square corners."""
    name = COLOR_PREFIX + glyph if glyph in COLOR_GLYPHS else glyph
    return tuple((_square_corners(segments), attrs) for segments, attrs in _glyph_paths(name))


@functools.lru_cache(maxsize=None)
def _color_reach(glyph):
    return _paths_reach(_color_paths(glyph))


def _material(name, mode, sign):
    """(fill colour or None, line colour or None for the theme's icon
    colour, fill open lines too) of a part's material on a `mode` ("light"
    or "dark") theme, in a sign or not."""
    if name == "ink":
        return None, None, False
    base = name.rstrip("/!")
    whole = name.endswith("!")
    line_only = name.endswith("/")
    hue = MATERIAL_HUES[base]
    if hue == "white":
        return (None if line_only else "#ffffff"), "#ffffff", whole
    if hue == "dark":
        return None, DARK_MARK, whole
    if hue == "paper":
        fill, edge = PAPER[mode]
        return (None if line_only else fill), edge, whole
    if hue == "glass":
        return (None if line_only else GLASS), None, whole
    light, medium, edge = COLOR_HUES[hue]
    if line_only:
        return None, medium if mode == "dark" else edge, whole
    if sign:
        return medium, medium, whole
    return (medium if base.endswith("S") or base == "folder" else light), edge, whole


def _area(segments):
    """The area of a path's bounding box, in square units."""
    left, top, right, bottom = _extent(segments)
    return (right - left) * (bottom - top)


def _extent(segments):
    """(left, top, right, bottom) of a path's segments, in units."""
    xs, ys = [], []
    here = start = (12.0, 12.0)
    for segment in segments:
        if segment[0] == "Z":
            here = start
            continue
        if segment[0] == "A":
            points = _arc_points(*here, segment[1], segment[2], *segment[4:8])
        elif segment[0] == "C":
            points = [segment[1:3], segment[3:5], segment[5:7]]
        else:
            points = [segment[1:3]]
        for x, y in points:
            xs.append(x)
            ys.append(y)
        here = (segment[-2], segment[-1])
        if segment[0] == "M":
            start = here
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0.0, 0.0, 0.0, 0.0)


def _luminance(color):
    """Relative luminance (WCAG) of a #rrggbb colour."""
    def channel(value):
        value /= 255
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(int(color[i:i + 2], 16)) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _legible(candidates, under):
    """The first of `candidates` that reads on the fill colour `under`
    (DETAIL_CONTRAST), else the one that reads best."""
    for color in candidates:
        if _contrast(color, under) >= DETAIL_CONTRAST:
            return color
    return max(candidates, key=lambda color: _contrast(color, under))


def _color_body(glyph, mode, ink, draw):
    """A glyph's parts in colour as SVG: (the coloured parts, the ink parts
    in `ink`), drawn by draw(segments) -> path data. Every fill comes
    first, the largest first (a body under its window), then the lines."""
    recipe = COLOR_RECIPES.get(glyph, ("ink",))
    sign = glyph in SIGNS
    paths = _color_paths(glyph)
    parts = [_material(recipe[min(i, len(recipe) - 1)], mode, sign) for i in range(len(paths))]
    # The fills, to give the details drawn on them a colour that reads.
    areas = [
        (_extent(shape), fill)
        for (segments, attrs), (fill, _line, whole) in zip(paths, parts) if fill and "fill=" not in attrs
        for shape, closed in _subpaths(segments) if closed or whole
    ]
    fills, colored, inked = [], [], []
    for i, (segments, attrs) in enumerate(paths):
        fill, line, whole = parts[i]
        # Signs keep their designed marks (white on the disc).
        if not sign and (fill is None or "fill=" in attrs):
            line = _on_fill(segments, line, areas, mode, recipe[min(i, len(recipe) - 1)])
        lines = colored if line else inked
        if "fill=" in attrs:
            # A part the glyph fills itself (a dot): solid, like its line.
            lines.append(f'<path d="{draw(segments)}" fill="{fill or line or ink}" stroke="none"/>')
            continue
        if fill:
            for shape, closed in _subpaths(segments):
                if closed or whole:
                    fills.append((-_area(shape), i, f'<path d="{draw(shape)}" fill="{fill}" stroke="none"/>'))
        lines.append(f'<path d="{draw(segments)}" stroke="{line or ink}"/>')
    return [path for _, _, path in sorted(fills)] + colored, inked


def _on_fill(segments, line, areas, mode, material):
    """The colour of a detail (a part without a fill of its own): `line`
    (None: the theme's icon colour), or, when it lies on a fill it does
    not read on, a deeper shade of its hue, dark grey or white."""
    left, top, right, bottom = _extent(segments)
    under = [
        (area, fill) for area, fill in areas
        if left >= area[0] - 0.5 and top >= area[1] - 0.5 and right <= area[2] + 0.5 and bottom <= area[3] + 0.5
    ]
    if not under:
        return line
    # The smallest fill holding it lies on top.
    _area_box, color = min(under, key=lambda item: (item[0][2] - item[0][0]) * (item[0][3] - item[0][1]))
    # The theme's icon colour is drawn in one layer for every theme: it
    # must read in both kinds of theme, or the detail gets a fixed colour.
    current = [line] if line else list(THEME_INK.values())
    if min(_contrast(c, color) for c in current) >= DETAIL_CONTRAST:
        return line
    hue = MATERIAL_HUES.get(material.rstrip("/!"))
    deeper = [COLOR_HUES[hue][2]] if hue in COLOR_HUES else []
    return _legible(deeper + [DARK_MARK, "#ffffff"], color)


def render_icon_color(spec, colors, scale=SCALE, mode="light"):
    """The Colourful version of render_icon (same glyph placement and
    badges) for a `mode` theme: ink parts in colors["icon"]."""
    glyph, _, badge = spec.partition("+")
    if badge:
        scale, transform = BADGED_SCALE, f"translate(0.2 0.2) scale({BADGED_SCALE})"
    else:
        reach = _color_reach(glyph)
        if reach > 0:
            scale = min(scale, (12 - STROKE / 2) / reach)
        offset = round(12 * (1 - scale), 3)
        transform = f"translate({offset} {offset}) scale({scale})"
    stroke = round(STROKE / scale, 3)
    colored, inked = _color_body(glyph, mode, colors["icon"], _plain_path)
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
             f'fill="none" {COLOR_STROKE}>']
    mask = ""
    if badge:
        parts.append(
            '<defs><mask id="b" maskUnits="userSpaceOnUse" x="0" y="0" width="24" height="24">'
            '<rect width="24" height="24" fill="#fff"/>'
            f'<circle cx="{BADGE_CENTER}" cy="{BADGE_CENTER}" r="{BADGE_RADIUS + BADGE_GAP}" fill="#000"/>'
            '</mask></defs>'
        )
        mask = ' mask="url(#b)"'
    body = "".join(colored + inked)
    parts.append(f'<g{mask}><g transform="{transform}" stroke-width="{stroke}">{body}</g></g>')
    if badge in BADGE_MARKS:
        mark = BADGE_MARKS[badge]
        parts.append(f'<path d="{_mark_path(mark, BADGE_CENTER, MARK_ARM)}" '
                     f'stroke="{COLOR_MARKS[mode][mark]}" stroke-width="{STROKE}"/>')
    elif badge:
        fill = colors["danger"] if badge == "x" else colors["accent"]
        parts.append(f'<circle cx="{BADGE_CENTER}" cy="{BADGE_CENTER}" r="{BADGE_RADIUS}" fill="{fill}"/>')
    parts.append("</svg>")
    return "".join(parts)


def render_icon_color_px(spec, size, scale=SCALE, width=None, layer="all", ink="#000000",
                         accent="#000000", danger="#000000", mode="light"):
    """The Colourful version of render_icon_px for a `mode` theme, on the
    same pixel grid. `layer`: "color" draws the coloured parts and the
    badge marks (fixed colours), "ink" the ink parts in `ink` (a mask the
    theme tints), "all" everything (badge dots in `accent` and `danger`)."""
    glyph, _, badge = spec.partition("+")
    px = size / 24
    width = stroke_px(size) if width is None else width
    if badge:
        badged = BADGED_SCALE_SMALL if size <= 20 else BADGED_SCALE
        unit = badged * px

        def place(x, y):
            return (0.2 + badged * x) * px, (0.2 + badged * y) * px
    else:
        reach = _color_reach(glyph)
        unit = scale * px
        if reach > 0:
            unit = min(unit, (size / 2 - width / 2) / reach)
        middle = size / 2

        def place(x, y):
            return middle + (x - 12) * unit, middle + (y - 12) * unit
    offset = 0.5 if width % 2 else 0.0
    low, high = width / 2, size - width / 2

    def snap(value):
        return min(max(math.floor(value - offset + 0.5) + offset, low), high)

    colored, inked = _color_body(glyph, mode, ink, lambda segments: _snapped_path(segments, place, snap, unit))
    body = {"color": colored, "ink": inked}.get(layer, colored + inked)
    drawn = _num(width + STROKE_EXTRA)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" '
        f'viewBox="0 0 {size} {size}" fill="none" {COLOR_STROKE}>',
    ]
    mask = ""
    if badge:
        center, radius = _snap_circle(BADGE_CENTER * px, BADGE_RADIUS * px)
        gap = max(1, round(BADGE_GAP * px))
        parts.append(
            f'<defs><mask id="b" maskUnits="userSpaceOnUse" x="0" y="0" width="{size}" height="{size}">'
            f'<rect width="{size}" height="{size}" fill="#fff"/>'
            f'<circle cx="{_num(center)}" cy="{_num(center)}" r="{_num(radius + gap)}" fill="#000"/>'
            '</mask></defs>'
        )
        mask = ' mask="url(#b)"'
    parts.append(f'<g{mask} stroke-width="{drawn}">{"".join(body)}</g>')
    if badge in BADGE_MARKS and layer in ("color", "all"):
        mark = BADGE_MARKS[badge]
        middle = snap(BADGE_CENTER * px)
        arm = max(2, round(MARK_ARM * px))
        cap = "round" if mark == "check" else "square"
        parts.append(f'<path d="{_mark_path(mark, middle, arm)}" stroke="{COLOR_MARKS[mode][mark]}" '
                     f'stroke-width="{drawn}" stroke-linecap="{cap}"/>')
    elif badge and badge not in BADGE_MARKS and layer == "all":
        fill = danger if badge == "x" else accent
        parts.append(f'<circle cx="{_num(center)}" cy="{_num(center)}" r="{_num(radius)}" fill="{fill}"/>')
    parts.append("</svg>")
    return "".join(parts)
