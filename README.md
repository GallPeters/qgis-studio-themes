# QGIS Studio Themes

A QGIS plugin that adds six UI themes with a consistent, modern design:
a redesigned stylesheet, a unified line-icon set and the Inter typeface.

https://github.com/user-attachments/assets/0ab0ae2d-79b5-44c5-9a6e-c7969d54c6bf

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
| Studio Premium | Dark | Neutral grey with QGIS green accents |
| Studio Web | Dark | Navy, based on the qgis.org website |
| Studio Dark | Dark | Near-black with orange accents |
| Studio Pro | Light | Light grey with blue accents |
| Studio Light Orange | Light | Warm paper with [Kartoza](https://kartoza.com) brand colours |
| Studio QGIS Light | Light | Light paper with the [QGIS brand](https://qgis.org/styleguide/) colours |

Each theme sets the Qt colour scheme to match its mode, so native widgets
stay consistent with the stylesheet regardless of the desktop's light or
dark setting. The two light themes were checked against WCAG 2.2 AA
contrast requirements.

<kbd>
<img width="638" height="341" alt="Studio theme screenshot" src="https://github.com/user-attachments/assets/3d196242-4d97-4356-a96f-548a18c2642a" />
</kbd>

## Features

- **Icons** – over 350 QGIS toolbar, menu, panel and dialog icons are
  replaced with a consistent line-icon set based on
  [Tabler Icons](https://tabler.io/icons), coloured for each theme.
- **Typography** – the bundled Inter typeface is used unless a custom font
  is set in QGIS options. The configured font size is always kept.
- **Layout** – thin dividers, rounded controls, underlined tabs, slim
  scrollbars, accent-coloured selection and a message bar that follows
  the theme.
- **Performance** – base colours are set through the Qt palette rather than
  broad stylesheet rules, which keeps dialog opening and repainting faster
  than in previous versions.

## How it works

All themes share one stylesheet (`themes/style.qss`), one set of design
tokens (`themes/base.qss`) and one icon map (`studio_icons.py`). Each theme
only defines its colours in `themes/<theme>/variables.qss`.

At startup the plugin builds every theme into the `themes` folder of the
active QGIS profile. A theme is rebuilt only when the plugin files change.
QGIS looks up theme icons in that folder, so dialogs opened later also use
the new icons.

## Development

The `tools` folder contains two scripts that run inside QGIS:

- `tools/screenshots.py` captures the main window, a menu, the attribute
  table and the layer properties dialog for each theme.
- `tools/benchmark.py` measures the CPU time of applying a theme, opening
  dialogs, repainting and scrolling.

Run them with `qgis --code tools/<script>.py`. Configuration options are
described in each script's docstring.

## Contributing

Pull requests are welcome. For larger changes, please open an issue first.
Bug reports can be filed on the [issue tracker](https://github.com/GallPeters/qgis-studio-themes/issues).

## License

[GNU GPL v2](LICENSE)

Bundled third-party assets:

- [Tabler Icons](https://github.com/tabler/tabler-icons) – MIT License, see `icons/tabler/LICENSE`
- [Inter](https://rsms.me/inter/) – SIL Open Font License 1.1, see `fonts/OFL.txt`
