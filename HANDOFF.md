# Handoff — QGIS Studio Themes

## 1. Project
QGIS 4 (Qt 6) plugin that themes the whole QGIS UI. Repo: github.com/GallPeters/qgis-studio-themes, branch `main`.
- `themes/` — `style.qss` with `@tokens`, per-theme `variables.qss`, `base.qss`. Six themes: Pro Light, Orange Light, QGIS Light, Premium Dark, Web Dark, Orange Dark.
- `studio_icons.py` — the icon set (`ICON_MAP`: QGIS icon name → Tabler glyph + optional badge), Monochrome / Colourful Pro / QGIS classic styles (Colourful is the base drawing of Colourful Pro), detailed hand-drawn Colourful drawings (`DETAILED`, 32-unit grid).
- `qgis_studio_themes.py` — plugin core: theme building, `IconSwapper` (replaces icons on live widgets), `SharpIconEngine`, sizing.
- `studio_ribbon.py` (optional ribbon), `studio_toolbars.py` (toolbar names), `studio_layers.py` (Layers panel search + List by Data Source), `studio_tokens.py`, `studio_events.py`.

Goal: a modern, mature GUI that **looks** like ArcGIS Pro but **behaves** like QGIS. Never mention ArcGIS/Esri in `metadata.txt`'s changelog.

## 2. Status (15.11.2026)
**v1.5 is finished and released to GitHub** (`main` pushed, `releases/qgis_studio_themes-1.5.zip`; changelog dated 15.11.2026). The user uploads it to the QGIS plugins portal themselves. Next work goes into 1.6: add a `** v1.6 (dd.mm.yyyy):` section above v1.5 in `metadata.txt` and bump `version=`.

v1.5:
- GitHub issue (Easy Search): plugins that shadow `QToolButton.menu()` / `QAction.menu()` with an attribute crashed `IconSwapper._visit`. Every `.menu()` call now goes through `studio_events.menu_of()` (calls Qt's method through the class, returns only a live `QMenu`). `_scan` also wraps each `_visit` in try/except (logged once per class, `_visit_failed`).
- Ribbon settings (`studio_ribbon`): `ribbonSize` (auto/small/medium/large = toolbar size None/16/24/32), `ribbonDensity` (**compact by default**, `DEFAULT_DENSITY`; compact: rows icon+2, `COMPACT_MARGINS` (6,6,6,6), tabs 8 px lower with names at most 12 px, `density` / `studioDensity` properties in `style.qss`), `ribbonNamePosition` / `ribbonNameText` (group names: off/top/bottom/left/left_vertical; full/short/auto; own keys, default bottom/full; font shared with toolbar names). `StudioRibbon.set_style()` replaces `set_caption_font()`.
- Large buttons: `ribbon_sizes` spreads the rows (`ROW_SPACING`) until icon + two-line label (measured in the ribbon buttons' font, `_label_height`) fits, so labels are never cut at larger UI fonts.
- Large buttons with a one-line label get half a label line more padding above and below (`_centre_large`, per-button stylesheet built from `LARGE_PADDING`, which mirrors style.qss's large padding): icon and label centred on the middle row. Group margins: compact (6,6,6,6), standard (6,9,6,7) — 4 px more height than before.
- The host toolbar's layout margins are zeroed (it took a plain QToolBar's 4 px padding before getting its name).
- Measured at QGIS icon size 24, UI font 12 px (Linux, offscreen probe): compact 125 px (121 before the margin change), others about 4 px more than measured then: compact + names off/left 105, small compact 112, large compact 145, standard 143. ArcGIS Pro is ~118 px (estimate, not measured).
- A user screenshot showed "Qt: QMetaEnum::keysToValue: empty keys string" in the message bar; not reproducible here (no plugin code sets an empty enum value). If it comes back, find which setting/stylesheet triggers it.

### Colourful Pro (in v1.6, 25.11.2026)
The only colour icon style is **Colourful Pro** (`color_pro`, `studio_pro.py`); plain Colourful was removed from the settings (a saved `color` reads as `color_pro`), its drawing remains the base. The Colourful drawing is rendered crisp, then restyled in device pixels with numpy: soft fills, greyish outlines in each object's own hue (a little deeper at 20 px and under; `PRO_BRIGHT` glyphs, photo and sitemap, lighter at every size), inner lines a step softer, gradients flattened to the average of their stops, and from 16 px a flat shadow beyond one arc across the whole drawing (`CURVE_*`, about the lower right half, edge smoothed over a pixel, no highlight; lighter instead of darker on fills darker than `DARK_FILL`; white/paper surfaces unshaded; translucent later shapes count as covering). PDF/CSV/SVG page letters are `class="heavy"` (2 px on whole pixels from 20 px). Each drawing is enlarged to fill its whole square (drawn natively larger, cropped; badged icons are not enlarged, their accent masks are drawn apart). The colour layer holds everything (ink baked in `THEME_INK`), the ink layer is empty. Internally it is the outline look `"pro"` (own mask folder and build stamp). `processingModel.svg` is `sitemap`. Project Properties (`file-settings`) keeps its page with the gear (not a badge). The settings screenshot in `docs/` still shows the old rows, and `pro-light_icons-color.png` the old Colourful.

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

- **Linux probe (15.11.2026 session):** QGIS 4.3 is installed (`/usr/bin/qgis`). Isolated profile under the session scratchpad `probe/root/profiles/tests` (plugin copied into its `python/plugins`); run `PROBE_OUT=<dir> QT_QPA_PLATFORM=offscreen qgis --profiles-path <probe>/root --profile tests --nologo --noversioncheck --code probe.py` (no window on the user's display). An installed copy (no `.git`) rebuilds its theme only when `metadata.txt` changes: `touch` it after copying a changed `style.qss`.

## 6. Release workflow
1. Edit → changelog in `metadata.txt` (short, plain bullets) → commit.
2. Rebuild zip from `git archive HEAD` of: LICENSE, `__init__.py`, fonts, icon.png, icon.svg, icons, metadata.txt, the 7 `.py` modules, themes; prefix `qgis_studio_themes/`, no directory entries → `releases/qgis_studio_themes-<ver>.zip` → commit "Rebuild v<ver> release zip".
3. Push (`git push` sometimes fails transiently; retry). Commit/push only when the user asks.
