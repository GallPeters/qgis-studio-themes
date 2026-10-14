# QGIS Studio Themes

🎨 A plugin that adds **modern UI** themes to QGIS.

🗺️ A professional look that reflects **QGIS’s true power**.

❤️‍🔥 Download, rate, and share to spread the word — **QGIS can look as great as it really is**.

🔥 Go **FOSS!**

https://github.com/user-attachments/assets/0ab0ae2d-79b5-44c5-9a6e-c7969d54c6bf

## Requirements

- QGIS **4.0** or later.

## Installation & Usage

1. Download the plugin using the  **Plugin mannager** or from the [**plugins website.**](https://plugins.qgis.org/plugins/qgis_studio_themes/)
2. Go to **Settings → Options → General**
3. Under **UI Theme**, select one of the themes
4. Restart QGIS to apply

## Themes

| Theme | Mode | Palette |
|---|---|---|
| Studio Premium | Dark | Deep navy with QGIS green accents |
| Studio Web | Dark | qgis.org website palette |
| Studio Pro | Light | Professional light grey with blue accents |
| Studio Dark | Dark | Classic dark |
| Studio Light Orange | Light | Warm paper with [Kartoza](https://kartoza.com) brand orange, blue and teal accents |
| Studio QGIS Light | Light | Fresh paper with the official [QGIS brand](https://qgis.org/styleguide/) greens and orange |

The light themes force a light Qt colour scheme even when your desktop is
in dark mode (and the dark themes force dark), so native widgets and
palette-drawn elements always match the stylesheet. Both light themes are
WCAG 2.2 AA contrast-audited — no light-on-light or dark-on-dark pairings.

## What the themes change

- **Modern icon set** — 350+ QGIS toolbar, menu, panel and dialog icons are
  redrawn as consistent line icons (based on [Tabler Icons](https://tabler.io/icons)),
  coloured for each theme, with accent badges for add / remove / new actions.
- **Inter typeface** — bundled and used whenever you have not chosen a custom
  font in QGIS options; your font size is always respected.
- **Clean layout language** — hairline dividers, rounded controls, underline
  tabs, slim scrollbars, accent-tinted selection, themed message bar.
- **Fast** — base colours come from the Qt palette instead of broad
  stylesheet rules, keeping theme switching, dialog opening and repainting
  close to stock QGIS speed (see `tools/benchmark.py`).

## How it works

Every theme shares one stylesheet (`themes/style.qss`), one set of design
tokens (`themes/base.qss`) and one icon set (`studio_icons.py`); a theme only
defines its palette in `themes/<theme>/variables.qss`. On startup the plugin
builds each theme into your QGIS profile's `themes` folder (rebuilt only when
the plugin changes). QGIS looks for theme icons in that folder, so dialogs
opened later get the modern icons natively.

### Developer tools

- `tools/screenshots.py` — capture every theme (main window, menu, attribute
  table, layer properties) for review.
- `tools/benchmark.py` — measure theme switching, dialog opening, repaint and
  scrolling cost per theme.

Both run inside QGIS: `qgis --code tools/<script>.py` (see the docstrings).
   

<kbd>
<img width="638" height="341" alt="image" src="https://github.com/user-attachments/assets/3d196242-4d97-4356-a96f-548a18c2642a" />
</kbd>

## Contributing

Pull requests are welcome. Please open an issue first to discuss major changes.

## License

[**GNU GPL v2**](LICENSE)

Bundled third-party assets:
- [Tabler Icons](https://github.com/tabler/tabler-icons) — MIT, see `icons/tabler/LICENSE`
- [Inter](https://rsms.me/inter/) typeface — SIL Open Font License 1.1, see `fonts/OFL.txt`
