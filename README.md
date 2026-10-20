# QGIS Studio Themes

A QGIS plugin that adds six UI themes with a consistent, modern design:
a redesigned stylesheet, a unified line-icon set and the Inter typeface.

## Requirements

QGIS 4.0 or later.

## Installation

1. Install **QGIS Studio Themes** from **Plugins → Manage and Install Plugins**,
   or download it from the [QGIS plugin repository](https://plugins.qgis.org/plugins/qgis_studio_themes/).
2. Open **Settings → Options → General**.
3. Select a Studio theme under **UI Theme**.
4. Restart QGIS.

## Themes

| Theme | Mode | Palette |
|---|---|---|
| Studio Premium Dark | Dark | Neutral grey with QGIS green accents |
| Studio Web Dark | Dark | Navy, based on the qgis.org website |
| Studio Orange Dark | Dark | Near-black with orange accents |
| Studio Pro Light | Light | Light grey with blue accents |
| Studio Orange Light | Light | Warm paper with [Kartoza](https://kartoza.com) brand colours |
| Studio QGIS Light | Light | Light paper with the [QGIS brand](https://qgis.org/styleguide/) colours |

Each theme sets the Qt colour scheme to match its mode, so native widgets
stay consistent with the stylesheet regardless of the desktop's light or
dark setting. The two light themes were checked against WCAG 2.2 AA
contrast requirements.

## Screenshots

| Studio Premium Dark | Studio Web Dark |
|---|---|
| ![Studio Premium Dark](docs/screenshots/premium-dark.png) | ![Studio Web Dark](docs/screenshots/web-dark.png) |
| **Studio Orange Dark** | **Studio Pro Light** |
| ![Studio Orange Dark](docs/screenshots/orange-dark.png) | ![Studio Pro Light](docs/screenshots/pro-light.png) |
| **Studio Orange Light** | **Studio QGIS Light** |
| ![Studio Orange Light](docs/screenshots/orange-light.png) | ![Studio QGIS Light](docs/screenshots/qgis-light.png) |

Layer properties dialog in Studio Premium Dark and Studio Pro Light:

| | |
|---|---|
| ![Layer properties, Studio Premium Dark](docs/screenshots/premium-dark_properties.png) | ![Layer properties, Studio Pro Light](docs/screenshots/pro-light_properties.png) |

## Features

- **Icons** – over 600 QGIS toolbar, menu, panel and dialog icons are
  replaced with a consistent line-icon set based on
  [Tabler Icons](https://tabler.io/icons), coloured for each theme. Small
  marks show what an action does: + add or new, - remove from, a check
  mark for save, a red dot for delete.
- **Sharp on every screen** – icons are pre-rendered for the exact pixel
  size each screen draws them at (100%, 125%, 150%... scaling), with their
  lines snapped to the pixel grid, so they stay crisp instead of blurring
  on large monitors. Arrows, check marks and other widget glyphs are drawn
  at their exact size. Plugging in another monitor or changing the display
  scaling keeps them sharp. Selected rows show their icon in the colour
  of their text.
- **Toolbar titles** – each toolbar's name sits centred above its buttons
  in small capitals, with a divider between toolbars and a line under each
  row of toolbars (vertical toolbars show a short name on their handle).
  Empty toolbars collapse instead of showing a labelled empty box.
- **Typography** – the bundled Inter typeface is used unless a custom font
  is set in QGIS options. The configured font size is always kept.
- **Sizes for every screen** – on large, low-density desktop monitors the
  plugin picks compact sizes (smaller menu and panel icons, toolbar icons
  the size of QGIS's own), while laptops keep the roomier look. It is chosen
  automatically from the screen's pixel density.
- **Layout** – thin dividers and splitter lines, rounded controls of one
  height, flat buttons, underlined dialog tabs and segmented panel tabs,
  dialog sections instead of nested boxes, soft rounded rows in the main
  panels, slim scrollbars, a visible focus ring, accent-coloured selection,
  menus lifted off the window, pill-shaped panel search fields, a quiet
  status bar and a message bar that follows the theme.
- **Performance** – base colours are set through the Qt palette rather than
  broad stylesheet rules, icons are loaded from a few pre-rendered atlas
  images, and the panels and toolbars do no heavy work while drawing or
  resizing, which keeps dialogs, panels and window resizing fast.

## Contributing

Pull requests are welcome. For larger changes, please open an issue first.
Bug reports can be filed on the [issue tracker](https://github.com/GallPeters/qgis-studio-themes/issues).

## License

[GNU GPL v2](LICENSE)

Bundled third-party assets:

- [Tabler Icons](https://github.com/tabler/tabler-icons) – MIT License, see `icons/tabler/LICENSE`
- [Inter](https://rsms.me/inter/) – SIL Open Font License 1.1, see `fonts/OFL.txt`
