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
    "mActionAddRasterLayer.svg": "grid-4x4+plus",
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
    "mActionNewVectorLayer.svg": "file-vector+star",
    "mActionNewGeoPackageLayer.svg": "package+star",
    "mActionNewSpatiaLiteLayer.svg": "feather+star",
    "mActionCreateMemory.svg": "cpu+star",
    "mActionNewMeshLayer.svg": "triangle-square-circle+star",
    "mActionNewVirtualLayer.svg": "sql-raised+star",
    # ---- Layers panel -----------------------------------------------------
    "mActionAddGroup.svg": "folder+plus",
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
    "mIconLayerTree.svg": "stack-2",
    # ---- Layer types (layer tree, browser, combo boxes) -------------------
    "mIconPointLayer.svg": "point",
    "mIconLineLayer.svg": "line",
    "mIconPolygonLayer.svg": "polygon",
    "mIconTableLayer.svg": "table",
    "mIconRaster.svg": "grid-4x4",
    "mIconRasterLayer.svg": "grid-4x4",
    "mIconMeshLayer.svg": "triangle-square-circle",
    "mIconVectorTileLayer.svg": "layout-grid",
    "mIconGeometryCollectionLayer.svg": "shape",
    "mIconFolder.svg": "folder",
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
    "mActionZoomFullExtent.svg": "arrows-maximize",
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
    "mActionRefresh.svg": "refresh",
    "mActionDraw.svg": "refresh",
    "tracking.svg": "route",
    # ---- Attributes / analysis --------------------------------------------
    "mActionIdentify.svg": "info-circle",
    "mActionMapIdentification.svg": "info-circle",
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
    "mIconSnappingVertex.svg": "point",
    "mIconSnappingSegment.svg": "line",
    "mIconSnappingArea.svg": "square",
    "mIconSnappingCentroid.svg": "circle-dot",
    "mIconSnappingMiddle.svg": "separator-vertical",
    "mIconSnappingEndpoint.svg": "arrow-bar-to-right",
    "mIconSnappingOnScale.svg": "ruler",
    "mIconTopologicalEditing.svg": "topology-star-ring-3",
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
    "console/iconClearConsole.svg": "clear-all",
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
    "mIconIterate.svg": "repeat",
    "mIconModelInput.svg": "forms",
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
}

# Icons that QGIS core plugins load from their own folder instead of the
# theme: name -> path relative to QgsApplication.pkgDataPath().
EXTERNAL = {
    "MetaSearch.svg": "python/plugins/MetaSearch/images/MetaSearch.svg",
    "db_manager/mActionDBImport.svg": "python/plugins/db_manager/icons/mActionDBImport.svg",
    "db_manager/mActionDBExport.svg": "python/plugins/db_manager/icons/mActionDBExport.svg",
    "db_manager/mActionSQLWindow.svg": "python/plugins/db_manager/icons/mActionSQLWindow.svg",
    "db_manager/dbmanager.svg": "python/plugins/db_manager/icons/dbmanager.svg",
    "processing/interpolation.png": "python/plugins/processing/images/interpolation.png",
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
SCALE = 1.15
COMPACT_SCALE = 1.0
# Glyphs with a badge are shrunk towards the top-left instead.
BADGED_SCALE = 0.9
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
#   the "L" stays clear of the badge's cut-out.
CUSTOM_GLYPHS = {
    "info-circle": (
        '<path d="M3 12a9 9 0 1 0 18 0a9 9 0 0 0 -18 0"/>'
        '<path d="M11 7.5a1 1 0 1 0 2 0a1 1 0 1 0 -2 0" fill="currentColor"/>'
        '<path d="M10.5 10.5h1.5v6.5h1.5"/>'
    ),
    "sql": (
        '<path d="M12 6.4A2.1 2.8 0 0 1 14.1 9.2L14.1 14.8A2.1 2.8 0 1 1 9.9 14.8L9.9 9.2A2.1 2.8 0 0 1 12 6.4"/>'
        '<path d="M17.25 6.4L17.25 17.6L21.45 17.6"/>'
        '<path d="M13.05 16.2L14.1 17.6"/>'
        '<path d="M2.55 16.2A1.05 1.4 0 0 0 3.6 17.6L5.7 17.6A1.05 1.4 0 0 0 6.75 16.2L6.75 13.4'
        'A1.05 1.4 0 0 0 5.7 12L3.6 12A1.05 1.4 0 0 1 2.55 10.6L2.55 7.8A1.05 1.4 0 0 1 3.6 6.4'
        'L5.7 6.4A1.05 1.4 0 0 1 6.75 7.8"/>'
    ),
    "sql-raised": (
        '<path d="M12 3.4A2.1 2.8 0 0 1 14.1 6.2L14.1 11.8A2.1 2.8 0 1 1 9.9 11.8L9.9 6.2A2.1 2.8 0 0 1 12 3.4"/>'
        '<path d="M17.25 3.4L17.25 14.6L21.45 14.6"/>'
        '<path d="M13.05 13.2L14.1 14.6"/>'
        '<path d="M2.55 13.2A1.05 1.4 0 0 0 3.6 14.6L5.7 14.6A1.05 1.4 0 0 0 6.75 13.2L6.75 10.4'
        'A1.05 1.4 0 0 0 5.7 9L3.6 9A1.05 1.4 0 0 1 2.55 7.6L2.55 4.8A1.05 1.4 0 0 1 3.6 3.4'
        'L5.7 3.4A1.05 1.4 0 0 1 6.75 4.8"/>'
    ),
}


@functools.lru_cache(maxsize=None)
def _glyph_body(name):
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
    monitor (0.27 mm) is close to 2 px on a laptop at 150 % (0.32 mm),
    while 2 px there (0.53 mm) looked heavy and crowded detailed glyphs."""
    return max(1, math.floor(STROKE * size / 24 + 0.25))


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
    reach = 0.0
    for segments, _ in _glyph_paths(name):
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


def render_icon_px(spec, colors, size, scale=SCALE):
    """Compose one icon for exactly `size` device pixels, with its lines on
    the pixel grid (see the module docstring). Same design as render_icon:
    same glyph enlargement, badge and visible weight, in whole pixels."""
    glyph, _, badge = spec.partition("+")
    px = size / 24
    width = stroke_px(size)
    if badge:
        unit = BADGED_SCALE * px

        def place(x, y):
            return (0.2 + BADGED_SCALE * x) * px, (0.2 + BADGED_SCALE * y) * px
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
    parts.append(f'<g{mask} stroke="{icon}" stroke-width="{width}">{paths}</g>')
    if badge in BADGE_MARKS:
        # On the same pixel grid as the glyph's lines, with square ends so
        # straight marks end on whole pixels.
        mark = BADGE_MARKS[badge]
        middle = snap(BADGE_CENTER * px)
        arm = max(2, round(MARK_ARM * px))
        cap = "round" if mark == "check" else "square"
        parts.append(
            f'<path d="{_mark_path(mark, middle, arm)}" stroke="{icon}" stroke-width="{width}" '
            f'stroke-linecap="{cap}"/>'
        )
    elif badge:
        fill = colors["danger"] if badge == "x" else colors["accent"]
        parts.append(f'<circle cx="{_num(center)}" cy="{_num(center)}" r="{_num(radius)}" fill="{fill}"/>')
    parts.append("</svg>")
    return "".join(parts)
