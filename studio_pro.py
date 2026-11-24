"""Colourful Pro icons (Settings > Icons > Colourful Pro).

The Colourful drawings (studio_icons) with a softer, more finished look:
- fills a little softer (less saturated, a touch lighter);
- every outline a greyish shade of its own object's colour (blue for blue
  objects, green for green, grey for grey), never near-black: a little
  deeper on small icons (20 px and under), always readable on the fill
  and on the window;
- lines drawn inside a fill (a globe's meridians, a table's grid) a step
  softer than the outline;
- from 24 px: a soft, sharp-edged inner shadow along each shape's lower
  right (as if lit from the top left) and a 1 px highlight inside its top
  left edge, in whole pixels so the icons stay crisp;
- each drawing fills its whole square: drawn natively at a larger size
  and cropped around it (badged icons keep their place, as their badge
  masks are drawn separately).

It works on the SVG studio_icons draws (outlines black, the "crisp" look)
and paints the shading in device pixels with numpy, so every edge falls
on the pixel grid. The result goes back as an SVG holding the PNG, drawn
1:1 into the atlas cell. Without numpy, Colourful Pro is plain Colourful.
"""
import base64
import colorsys
import re

from qgis.PyQt.QtCore import QBuffer, QByteArray, QIODevice, QRectF
from qgis.PyQt.QtGui import QImage, QPainter
from qgis.PyQt.QtSvg import QSvgRenderer

try:
    import numpy as np
except ImportError:  # pragma: no cover - QGIS ships numpy
    np = None

AVAILABLE = np is not None

LEAF = re.compile(r"<(path|rect|circle|ellipse|polygon|polyline|line)\b[^>]*?/>")
DEFS = re.compile(r"<defs>.*?</defs>", re.S)
GRADIENT = re.compile(r'<linearGradient id="(\w+)"><stop offset="0" stop-color="(#[0-9a-fA-F]{6})"')
STOP_COLOR = re.compile(r'stop-color="(#[0-9a-fA-F]{6})"')
HEX = re.compile(r"#[0-9a-f]{6}")
URL = re.compile(r"url\(#(\w+)\)")
# Badge dots (studio_icons.BADGE_COLORS) keep their colours and get no shading.
BADGES = frozenset(("#36a447", "#e5463c", "#2f7fe0"))
BLACK = "#000000"
# Pure black fills (a pencil's tip, small marks): a soft near-black.
SOFT_BLACK = "#2a2e33"
# Shading from this many device pixels up; shapes thinner than SHADE_MIN
# px get none, a highlight needs HIGHLIGHT_MIN.
EFFECTS_FROM = 24
SHADE_MIN, HIGHLIGHT_MIN = 6, 8


# ---- Colours -----------------------------------------------------------------
def _rgb(color):
    return tuple(int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))


def _hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(v * 255))):02x}" for v in rgb)


def _hls(color):
    return colorsys.rgb_to_hls(*_rgb(color))


def _from_hls(h, l, s):  # noqa: E741
    return _hex(colorsys.hls_to_rgb(h, max(0.0, min(1.0, l)), max(0.0, min(1.0, s))))


def _luminance(color):
    def channel(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(v) for v in _rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _darken_until(color, ok):
    while not ok(color) and _hls(color)[1] > 0.06:
        h, l, s = _hls(color)  # noqa: E741
        color = _from_hls(h, l - 0.03, s)
    return color


def soften(color):
    """A fill a little less saturated and a touch lighter; greys, white
    and near-black kept."""
    h, l, s = _hls(color)  # noqa: E741
    if s < 0.06 or l > 0.97 or l < 0.12:
        return color
    return _from_hls(h, l + (1 - l) * 0.03, s * 0.92)


def outline_for(fill, size):
    """The outline of a shape filled `fill`: a greyish mid-dark shade of
    its own hue, a little deeper on small icons; at least 2.3:1 on the
    fill and readable on a light window."""
    h, l, s = _hls(fill)  # noqa: E741
    target = 0.33 if size <= 20 else 0.40
    color = _from_hls(h, target, s * 0.5) if s < 0.12 else _from_hls(h, target, min(s * 0.6, 0.34))
    on_window = 5.0 if size <= 20 else 4.0
    return _darken_until(color, lambda c: _contrast(c, fill) >= 2.3 and _contrast(c, "#ffffff") >= on_window)


def inner_line_for(fill, size):
    """A line drawn inside a fill: a step softer than its outline."""
    h, l, s = _hls(outline_for(fill, size))  # noqa: E741
    return _darken_until(_from_hls(h, l + 0.06, s), lambda c: _contrast(c, fill) >= 2.0)


def shadow_for(fill):
    h, l, s = _hls(fill)  # noqa: E741
    if s < 0.06:
        return _from_hls(h, l - 0.085, s)
    return _from_hls(h, l - 0.08, s * 1.04)


def highlight_for(fill):
    h, l, s = _hls(fill)  # noqa: E741
    return _from_hls(h, l + (1 - l) * 0.4, s)


def _badge_edge(fill):
    h, _l, s = _hls(fill)
    return _from_hls(h, 0.28, s)


# ---- SVG elements ------------------------------------------------------------
def _attr(tag, name):
    match = re.search(rf'\b{name}="([^"]*)"', tag)
    return match.group(1) if match else None


def _set(tag, name, value):
    if re.search(rf'\b{name}="', tag):
        return re.sub(rf'\b{name}="[^"]*"', f'{name}="{value}"', tag, count=1)
    return tag.replace("/>", f' {name}="{value}"/>', 1)


def _leaves(svg):
    """[(start, end, tag)] of the drawn elements (not those in <defs>)."""
    hidden = [(m.start(), m.end()) for m in DEFS.finditer(svg)]
    return [(m.start(), m.end(), m.group(0)) for m in LEAF.finditer(svg)
            if not any(a <= m.start() < b for a, b in hidden)]


def _rebuild(svg, leaves, tags):
    parts, last = [], 0
    for (start, end, _old), new in zip(leaves, tags):
        parts += [svg[last:start], new]
        last = end
    parts.append(svg[last:])
    return "".join(parts)


def _greyline(color):
    """A dark neutral line: drawn as an outline (the theme's ink on light
    themes, grey paper edges)."""
    if not HEX.fullmatch(color):
        return False
    return _hls(color)[2] < 0.15 and _luminance(color) < 0.45


# ---- Raster ------------------------------------------------------------------
def _raster(svg, size):
    """`svg` drawn at `size` px: float RGBA (straight alpha), rows first."""
    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(painter, QRectF(0, 0, size, size))
    painter.end()
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    bits = image.constBits()
    bits.setsize(size * size * 4)
    return np.frombuffer(bits, np.uint8).reshape(size, size, 4).astype(np.float32) / 255


def _shift(mask, dx, dy):
    out = np.zeros_like(mask)
    h, w = mask.shape
    out[max(0, dy):h + min(0, dy), max(0, dx):w + min(0, dx)] = \
        mask[max(0, -dy):h + min(0, -dy), max(0, -dx):w + min(0, -dx)]
    return out


def _png_svg(rgba):
    """An SVG holding `rgba` (uint8, straight alpha) as a PNG, 1:1."""
    size = rgba.shape[0]
    image = QImage(rgba.tobytes(), size, size, 4 * size, QImage.Format.Format_RGBA8888).copy()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    buffer.close()
    encoded = base64.b64encode(bytes(data)).decode("ascii")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'width="{size}" height="{size}" viewBox="0 0 {size} {size}"><image width="{size}" '
            f'height="{size}" xlink:href="data:image/png;base64,{encoded}"/></svg>')


# ---- The Pro look ------------------------------------------------------------
# A drawing is enlarged until it fills its square, by at most this much.
FILL_GROW = 1.4


def upgrade(draw, size, ink, fill=True):
    """A Colourful icon at `size` px in the Pro look, as an SVG of that
    size. draw(px) is its studio_icons SVG at px (black outlines, ink parts
    in `ink`). With `fill`, drawn at the largest size whose drawing still
    fits `size` px and cropped around it, so it fills the whole square."""
    svg = draw(size)
    if np is None:
        return svg
    big, box = size, None
    if fill:
        big, svg, box = _filling(draw, size, svg)
    image = _upgrade(svg, big, ink)
    if box is not None and big > size:
        x0, y0, x1, y1 = box
        left = min(max(0, (x0 + x1 - size) // 2), big - size)
        top = min(max(0, (y0 + y1 - size) // 2), big - size)
        image = image[top:top + size, left:left + size]
    return _png_svg((image.clip(0, 1) * 255 + 0.5).astype(np.uint8))


def _extent(svg, px):
    """(left, top, right, bottom) of what `svg` draws at `px` px, or None."""
    ys, xs = np.nonzero(_raster(svg, px)[..., 3] > 0.15)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _filling(draw, size, svg):
    """(px, SVG at px, its extent): the largest px up to FILL_GROW times
    `size` whose drawing is at most `size` px wide and high; `size`
    itself when nothing larger fits."""
    box = _extent(svg, size)
    if box is None:
        return size, svg, None
    span = max(box[2] - box[0], box[3] - box[1])
    # A first guess from the drawing's span, then down until it fits.
    big = min(int(size * FILL_GROW), size * size // max(1, span))
    while big > size:
        candidate = draw(big)
        found = _extent(candidate, big)
        if found is not None and max(found[2] - found[0], found[3] - found[1]) <= size:
            return big, candidate, found
        big -= 1
    return size, svg, box


def _upgrade(svg, size, ink):
    gradients = dict(GRADIENT.findall(svg))

    def fill_of(tag):
        fill = _attr(tag, "fill")
        if not fill or fill == "none":
            return None
        match = URL.match(fill)
        if match:
            return gradients.get(match.group(1))
        return fill.lower() if fill.startswith("#") else None

    # Dark neutral lines are outlines too: black, recoloured below.
    leaves = _leaves(svg)
    tags = []
    for _start, _end, tag in leaves:
        stroke = (_attr(tag, "stroke") or "").lower()
        tags.append(_set(tag, "stroke", BLACK) if _greyline(stroke) else tag)
    svg = _rebuild(svg, leaves, tags)

    # Soft fills.
    leaves = _leaves(svg)
    tags = []
    for _start, _end, tag in leaves:
        fill, raw = fill_of(tag), _attr(tag, "fill") or ""
        if fill == BLACK:
            tag = _set(tag, "fill", SOFT_BLACK)
        elif fill and fill not in BADGES and not raw.startswith("url"):
            tag = _set(tag, "fill", soften(fill))
        tags.append(tag)
    svg = _rebuild(svg, leaves, tags)
    svg = STOP_COLOR.sub(lambda m: f'stop-color="{soften(m.group(1))}"', svg)
    gradients = dict(GRADIENT.findall(svg))
    leaves = _leaves(svg)
    count = len(leaves)
    fills = [fill_of(tag) for _s, _e, tag in leaves]
    strokes = [(_attr(tag, "stroke") or "").lower() for _s, _e, tag in leaves]

    def alone(index, fill, stroke):
        """Coverage of element `index` alone: its fill or its line."""
        tags = []
        for j, (_s, _e, tag) in enumerate(leaves):
            if j != index:
                tags.append("")
                continue
            tag = _set(tag, "fill", "#ffffff" if fill else "none")
            tags.append(_set(tag, "stroke", "#ffffff" if stroke else "none"))
        return _raster(_rebuild(svg, leaves, tags), size)[..., 3]

    fill_masks = [alone(i, True, False) if fills[i] else None for i in range(count)]
    stroke_masks = [alone(i, False, True) if strokes[i] not in ("", "none") else None for i in range(count)]
    # The topmost fill at each pixel.
    top = np.full((size, size), -1)
    for i, mask in enumerate(fill_masks):
        if mask is not None:
            top[mask > 0.5] = i

    # Outlines in each object's own colour; lines on a fill from that fill.
    tags = []
    for i, (_s, _e, tag) in enumerate(leaves):
        if strokes[i] == BLACK:
            if fills[i] in BADGES:
                tag = _set(tag, "stroke", _badge_edge(fills[i]))
            elif fills[i]:
                tag = _set(tag, "stroke", outline_for(fills[i], size))
            elif stroke_masks[i] is not None:
                line = stroke_masks[i] > 0.4
                under = [j for j in top[line].tolist() if j >= 0 and j != i]
                if under and len(under) >= 0.3 * line.sum():
                    j = max(set(under), key=under.count)
                    inside = (fill_masks[j] > 0.99)[line].mean()
                    tag = _set(tag, "stroke", (inner_line_for if inside > 0.7 else outline_for)(fills[j], size))
                else:
                    tag = _set(tag, "stroke", ink)
        tags.append(tag)
    svg = _rebuild(svg, leaves, tags)
    out = _raster(svg, size)
    if size < EFFECTS_FROM:
        return out

    # Sharp inner shadow (lower right) and highlight (upper left) on each
    # shape where it shows: not under a later shape, not on a line.
    lines = np.zeros((size, size), np.float32)
    for mask in stroke_masks:
        if mask is not None:
            lines = np.maximum(lines, mask)
    for i, mask in enumerate(fill_masks):
        fill = fills[i]
        if mask is None or fill is None or fill in BADGES or fill in (BLACK, SOFT_BLACK):
            continue
        solid = mask > 0.5
        ys, xs = np.nonzero(solid)
        if len(ys) < 30:
            continue
        thin = min(xs.max() - xs.min() + 1, ys.max() - ys.min() + 1)
        if thin < SHADE_MIN:
            continue
        later = np.zeros((size, size), bool)
        for other in fill_masks[i + 1:]:
            if other is not None:
                later |= other > 0.5
        free = solid & ~later & (lines < 0.25)
        depth = int(max(1, min(4, round(thin * 0.15 * (size / 32) ** 0.3))))
        shade = free & ~_shift(solid, -depth, -depth)
        light = (free & ~_shift(solid, 2, 2) & ~shade) if thin >= HIGHLIGHT_MIN else None
        for region, color in ((shade, shadow_for(fill)), (light, highlight_for(fill))):
            if region is not None and region.any():
                out[..., :3][region] = np.array(_rgb(color), np.float32)
    return out
