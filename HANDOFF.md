# Handoff — QGIS Studio Themes

## 1. Project
QGIS 4 (Qt 6) plugin that themes the whole QGIS UI. Repo: github.com/GallPeters/qgis-studio-themes, branch `main`.
- `themes/` — `style.qss` with `@tokens`, per-theme `variables.qss`, `base.qss`. Six themes: Pro Light, Orange Light, QGIS Light, Premium Dark, Web Dark, Orange Dark.
- `studio_icons.py` — the icon set (`ICON_MAP`: QGIS icon name → Tabler glyph + optional badge), Monochrome / Colourful / QGIS classic styles, detailed hand-drawn Colourful drawings (`DETAILED`, 32-unit grid).
- `qgis_studio_themes.py` — plugin core: theme building, `IconSwapper` (replaces icons on live widgets), `SharpIconEngine`, sizing.
- `studio_ribbon.py` (optional ribbon), `studio_toolbars.py` (toolbar names), `studio_layers.py` (Layers panel search + List by Data Source), `studio_tokens.py`, `studio_events.py`.

Goal: a modern, mature GUI that **looks** like ArcGIS Pro but **behaves** like QGIS. Never mention ArcGIS/Esri in `metadata.txt`'s changelog.

## 2. Status (09.11.2026)
**v1.4 is finished and released to GitHub** (`main` pushed, `releases/qgis_studio_themes-1.4.zip` rebuilt; changelog dated 10.11.2026). The user uploads it to the QGIS plugins portal themselves. Next work goes into a new version (1.5): add a `** v1.5 (dd.mm.yyyy):` section above v1.4 in `metadata.txt` and bump `version=`.

Last change in v1.4: `IconSwapper` now also swaps
- widgets added to an already-scanned toolbar with `addWidget()` (`_action_added`: Identify Results' mode and settings buttons, Layer Styling's back/menu/undo/redo),
- the status bar CRS button after every project CRS change (`_hook_crs` / `_crs_changed`; QGIS re-sets it from its own icon cache),
- the magnifier of the plugin's own Layers search field (`studio_layers._theme_icons`).

## 3. Open ideas (not approved, not built)
Previewed to the user but not requested for building:
- Redesigned Colourful drawings for weak icons (SQL/SHP/CSV letter icons, slate funnel, expand/collapse, edit-in-place, About, deselect, select-by-rectangle, copy, forms, SpatiaLite, scratch layer, vector, mesh). Preview script: `redesign.py` (see §5).
- Visual polish list: Monochrome badges as solid discs, eye variants with standard badges, one hue for media controls, lighter outline-only lines on dark themes, white paper on dark themes, one data colour for charts, tonal Layers stack. Preview script: `preview.py`.
Ask the user before building any of them.

## 4. Key facts (verified)
- **Icon pipeline:** glyph masks per (size, line width, scale) rendered to atlases in the profile, composed per theme (`compose_atlas`); `SharpIconEngine` serves exact-size pixmaps. Mask cache is keyed by a hash of `studio_icons.py` (editing it forces a redraw).
- **Swapper identification:** by `QIcon.cacheKey()` first, else by serialized data vs. a fingerprint table of built-in icons (cached on disk per QGIS build: `.studio-icon-digests.json` in the user themes folder). Widgets are scanned once (on ChildPolished / focus / stacked page change); later changes need a hook.
- Almost every theme-icon name QGIS 4 references is already in `ICON_MAP` (checked by scanning the QGIS DLLs); missed icons are nearly always a **runtime swapping gap**, not a missing map entry.
- Icons left unswapped by design: those in hidden dialogs/menus until they are shown, the dock float/close buttons, cursors (`NOT_REPLACED`).

## 5. Testing
- The plugin cannot be imported in plain Python here (qgis.core DLL mismatch); `OSGeo4W\bin\python-qgis-qt6.bat` works for `qgis.PyQt` + QtSvg rendering only.
- **Real QGIS probe** (works, isolated): `scratchpad\probe\` of the 09.11.2026 session (`C:\Users\P0026701\AppData\Local\Temp\claude\a6ede2dda5cc80b7\70ffe1d8-3fd9-4e07-8016-3e23b7adaef9\scratchpad\probe\`). It holds a copy of the user's `tests` profile under `profiles\tests`, with the plugin copied into `python\plugins\qgis_studio_themes`.
  - `run.bat` launches `qgis-bin.exe` (the user's QGIS 4 build, `apps\qgis`) with `--profiles-path` that folder and `--code probe.py`. `probe.py` opens Identify Results and writes `report.txt` (every visible icon not replaced, with its QGIS file) and `identify.png`.
  - `shots.sh <name> "<Theme>" <mono|color|classic> <0|1>` sets theme/style in the profile ini and runs `shot.py`, producing the README screenshots (1600×1000, + `_properties` 1100×720) into `probe\shots\`. Sample data: Natural Earth countries in `scratchpad\ne_data\countries.geojson`.
  - After shots, reset `iconStyle=color` in `profiles\tests\QGIS\QGIS4.ini`, or the probe runs in classic style and reports everything unswapped.
  - Copy changed `.py` files into the probe profile before each run. Never touch the user's own running QGIS (a `qgis-bin.exe` without `--profiles-path`).
- Earlier render scripts (icon sheets, `check.py`, `qss_check.py`): `...\c605fdb6-86c3-4955-bdd1-cab307e62e93\scratchpad\sheet\`; this session's `preview.py`, `redesign.py`, `allsheet.py` are in this session's scratchpad. Scratch folders may be cleaned by the system; copy what you need.

## 6. Release workflow
1. Edit → changelog in `metadata.txt` (short, plain bullets) → commit.
2. Rebuild zip from `git archive HEAD` of: LICENSE, `__init__.py`, fonts, icon.png, icon.svg, icons, metadata.txt, the 7 `.py` modules, themes; prefix `qgis_studio_themes/`, no directory entries → `releases/qgis_studio_themes-<ver>.zip` → commit "Rebuild v<ver> release zip".
3. Push (`git push` sometimes fails transiently; retry). Commit/push only when the user asks.
