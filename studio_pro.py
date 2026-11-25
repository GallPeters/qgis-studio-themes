"""Colourful Pro icons (Settings > Icons > Colourful Pro).

The Colourful drawings (studio_icons) with a softer, more finished look:
- fills a little softer (less saturated, a touch lighter);
- every outline a greyish shade of its own object's colour (blue for blue
  objects, green for green, grey for grey), never near-black: a little
  deeper on small icons (20 px and under), always readable on the fill
  and on the window;
- lines drawn inside a fill (a globe's meridians, a table's grid) in the
  outline's shade, 2 px from 20 px (INNER_LINE_FROM), so they show;
- gradients flattened to one colour (the average of their stops);
- from 16 px: a flat shadow on the lower right of each coloured shape,
  bounded by one gentle curve across the whole drawing, about half of it
  (as if lit from the top left): one flat colour, no gradient, no
  highlight edge, its edge smoothed over a pixel; on dark fills the part
  is lighter instead, so it shows; white and paper surfaces unshaded;
- the exterior outline (where the drawing meets the background) one
  pixel thicker, inwards (a full 2 px line), so the icon keeps its size, in one darker, richer shade of the
  fill it surrounds per shape (not the greyish outline), painted evenly
  over the whole band so it reads as one line; lines inside the drawing
  keep their width and colour;
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
GRADIENT_BLOCK = re.compile(r'<linearGradient id="(\w+)"[^>]*>(.*?)</linearGradient>', re.S)
STOP_COLOR = re.compile(r'stop-color="(#[0-9a-fA-F]{6})"')
HEX = re.compile(r"#[0-9a-f]{6}")
URL = re.compile(r"url\(#(\w+)\)")
# Badge dots (studio_icons.BADGE_COLORS) keep their colours and get no shading.
BADGES = frozenset(("#36a447", "#e5463c", "#2f7fe0"))
BLACK = "#000000"
# Pure black fills (a pencil's tip, small marks): a soft near-black.
SOFT_BLACK = "#2a2e33"
# Shading from this many device pixels up; shapes thinner than SHADE_MIN
# px get none.
EFFECTS_FROM = 16
SHADE_MIN = 6
# The shadow's edge: an arc of the circle centred at (CURVE_CX, CURVE_CY),
# radius CURVE_R, in units of the drawing's width and height from its top
# left. It runs from the top edge near the right corner through about the
# middle and sweeps to the lower left: about the lower right half in
# shadow.
CURVE_CX, CURVE_CY, CURVE_R = -0.3, -0.2, 1.13
# How much darker the shadow is (lightness); on fills darker than
# DARK_FILL, how much lighter (a dark shadow on a dark body hid).
SHADOW_DARKER = 0.13
DARK_FILL, SHADOW_LIGHTER = 0.4, 0.12
# Icons of SMALL_DETAIL px and under: the shadow this much stronger, and
# lines inside a fill in the full outline shade.
SMALL_DETAIL, SMALL_SHADOW_EXTRA = 20, 0.06
# White and paper surfaces (this light and this grey) get no shadow.
UNSHADED_LIGHTNESS, UNSHADED_SATURATION = 0.9, 0.25
# The exterior outline's colour: its fill's colour times EXTERIOR_DARKER,
# the brightest channel at most EXTERIOR_MAX, then more saturated
# (EXTERIOR_SATURATE, same lightness) so it reads in the object's colour.
EXTERIOR_DARKER, EXTERIOR_MAX = 0.87, 0.75
# Firm outlines (upgrade(firm=True)): this much darker and capped.
FIRM_DARKER, FIRM_MAX = 0.68, 0.55
EXTERIOR_SATURATE, GREY = 1.35, 0.1
# The pixel added inside the outline: how far it takes the outline's
# colour (the rest stays fill): all of it, a full 2 px line.
EXTERIOR_INNER = 1.0
# Free lines (no fill of their own and none under them: a clock, arrows, a
# sigma, in the theme's ink or a colour) from FREE_LINE_FROM px: drawn
# 2 px wide, moved half a pixel so the even width covers whole pixels
# (crisp, not a 1 px line with a faint second pixel beside it).
FREE_LINE_FROM = 20
# All lines 2 px (inner ones too) from this size (_upgrade), but small
# details (under DETAIL_SHARE of the icon wide and high) keep 1 px.
INNER_LINE_FROM = 20
DETAIL_SHARE = 0.45
# Small filled details' outlines: this much darker (lightness).
DETAIL_DARKER = 0.1
# Their smoothed edges: coverage below this cleared, above 1 - it solid.
FIRM_LOW = 0.15


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


def outline_for(fill, size, bright=False):
    """The outline of a shape filled `fill`: a greyish mid-dark shade of
    its own hue, a little deeper on small icons; at least 2.3:1 on the
    fill and readable on a light window. `bright`: a lighter one at every
    size (still 1.8:1 on the fill, 3:1 on the window)."""
    h, l, s = _hls(fill)  # noqa: E741
    target = 0.5 if bright else 0.33 if size <= 20 else 0.40
    color = _from_hls(h, target, s * 0.5) if s < 0.12 else _from_hls(h, target, min(s * 0.6, 0.34))
    on_fill, on_window = (1.8, 3.0) if bright else (3.0 if size <= 20 else 2.3, 5.0 if size <= 20 else 4.0)
    return _darken_until(color, lambda c: _contrast(c, fill) >= on_fill and _contrast(c, "#ffffff") >= on_window)


def shadow_for(fill, small=False):
    """The flat shadow colour on a shape filled `fill` (lighter on a dark
    fill); stronger on `small` icons, where it hardly showed."""
    h, l, s = _hls(fill)  # noqa: E741
    extra = SMALL_SHADOW_EXTRA if small else 0.0
    if l < DARK_FILL:
        return _from_hls(h, l + SHADOW_LIGHTER + extra, s)
    if s < 0.06:
        return _from_hls(h, l - SHADOW_DARKER - extra - 0.01, s)
    return _from_hls(h, l - SHADOW_DARKER - extra, min(1.0, s * 1.06))


def _badge_edge(fill):
    h, _l, s = _hls(fill)
    return _from_hls(h, 0.28, s)


# ---- SVG elements ------------------------------------------------------------
def _attr(tag, name):
    match = re.search(rf'\b{name}="([^"]*)"', tag)
    return match.group(1) if match else None


def _number(text):
    """A number attribute's value (0 if unreadable)."""
    try:
        return float(text)
    except ValueError:
        return 0.0


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


def upgrade(draw, size, ink, fill=True, bright=False, line=1, shade=True, firm=False):
    """A Colourful icon at `size` px in the Pro look, as an SVG of that
    size. draw(px) is its studio_icons SVG at px (black outlines, ink parts
    in `ink`). With `fill`, drawn at the largest size whose drawing still
    fits `size` px and cropped around it, so it fills the whole square.
    With `bright`, lighter outlines at every size (a small drawing of
    small shapes turned dark). `line`: the drawing's line width in px.
    Without `shade`, no shadow (flat symbols); with `firm`, darker exterior
    outlines (light objects that faded into dark themes)."""
    svg = draw(size)
    if np is None:
        return svg
    big, box = size, None
    if fill:
        # A pixel to spare (right and bottom) where free lines widen
        # (FREE_LINE_FROM), so they are not cut off at the edge.
        big, svg, box = _filling(draw, size, svg, size - 1 if size >= FREE_LINE_FROM else size)
    image = _upgrade(svg, big, ink, bright, line, shade, firm)
    if box is not None and big > size:
        x0, y0, x1, y1 = box
        # Centred, an odd spare pixel on the right and at the bottom.
        left = min(max(0, (x0 + x1 - size + 1) // 2), big - size)
        top = min(max(0, (y0 + y1 - size + 1) // 2), big - size)
        image = image[top:top + size, left:left + size]
    return _png_svg((image.clip(0, 1) * 255 + 0.5).astype(np.uint8))


def _extent(svg, px):
    """(left, top, right, bottom) of what `svg` draws at `px` px, or None."""
    ys, xs = np.nonzero(_raster(svg, px)[..., 3] > 0.15)
    if not len(xs):
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def _filling(draw, size, svg, room=None):
    """(px, SVG at px, its extent): the largest px up to FILL_GROW times
    `size` whose drawing is at most `room` (`size`) px wide and high;
    `size` itself when nothing larger fits."""
    room = size if room is None else room
    box = _extent(svg, size)
    if box is None:
        return size, svg, None
    span = max(box[2] - box[0], box[3] - box[1])
    # A first guess from the drawing's span, then down until it fits.
    big = min(int(size * FILL_GROW), size * room // max(1, span))
    while big > size:
        candidate = draw(big)
        found = _extent(candidate, big)
        if found is not None and max(found[2] - found[0], found[3] - found[1]) <= room:
            return big, candidate, found
        big -= 1
    return size, svg, box


def _upgrade(svg, size, ink, bright=False, line_px=1, shade=True, firm=False):
    gradients = dict(GRADIENT.findall(svg))
    # Each gradient as one flat colour: the average of its stops.
    flat = {}
    for gid, stops in GRADIENT_BLOCK.findall(svg):
        colors = [_rgb(c) for c in STOP_COLOR.findall(stops)]
        if colors:
            flat[gid] = _hex(tuple(sum(c[k] for c in colors) / len(colors) for k in range(3)))

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
        url = URL.match(raw)
        if url and url.group(1) in flat:
            tag = _set(tag, "fill", soften(flat[url.group(1)]))
        elif fill == BLACK:
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

    # Free lines (FREE_LINE_FROM): no fill, none within a pixel of them.
    free = set()
    if size >= FREE_LINE_FROM:
        near_fill = _dilated(top >= 0)
        for i in range(count):
            if fills[i] is None and stroke_masks[i] is not None:
                drawn = stroke_masks[i] > 0.4
                if drawn.any() and (near_fill & drawn).sum() < 0.3 * drawn.sum():
                    free.add(i)
    # Widened towards the right and bottom, or inwards where the lines
    # already touch that edge (never cut off).
    # From INNER_LINE_FROM px (on screens of 1 px lines) every line is 2 px:
    # the lines inside a drawing (bands, folds, meridians) were barely seen
    # at 1 px; fine details drawn thinner than a pixel keep their width.
    bold = set(free)
    # Small details (a gear on a page, a lock's plate): kept 1 px below,
    # their lines a touch darker so they stay readable.
    details = set()
    for i in range(count):
        if fills[i] not in BADGES and stroke_masks[i] is not None and i not in free:
            drawn = stroke_masks[i] > 0.4
            if drawn.any():
                ys, xs = np.nonzero(drawn)
                if max(xs.max() - xs.min(), ys.max() - ys.min()) + 1 < DETAIL_SHARE * size:
                    details.add(i)
    if size >= INNER_LINE_FROM and line_px == 1:
        solid = np.zeros((size, size), bool)
        for mask in fill_masks:
            if mask is not None:
                solid |= mask > 0.99
        for i, (_s, _e, tag) in enumerate(leaves):
            width = _attr(tag, "stroke-width")
            if stroke_masks[i] is None or fills[i] in BADGES or (width is not None and _number(width) < 1):
                continue
            # A shape's own outline, or a line well inside a fill; not a
            # frame drawn along a shape's edge (it turned the edge heavy),
            # nor a small detail (a gear, a mark: 2 px filled it in).
            drawn = stroke_masks[i] > 0.4
            if not drawn.any():
                continue
            ys, xs = np.nonzero(drawn)
            if max(xs.max() - xs.min(), ys.max() - ys.min()) + 1 < DETAIL_SHARE * size:
                continue
            if fills[i] is not None or solid[drawn].mean() > 0.7:
                bold.add(i)
    shift = [".5", ".5"]
    if bold:
        reach = np.maximum.reduce([stroke_masks[i] for i in bold]) > 0.1
        if reach[-1, :].any():
            shift[1] = "-.5"
        if reach[:, -1].any():
            shift[0] = "-.5"

    # Outlines in each object's own colour; lines on a fill from that fill.
    tags = []
    for i, (_s, _e, tag) in enumerate(leaves):
        if strokes[i] == BLACK:
            if fills[i] in BADGES:
                tag = _set(tag, "stroke", _badge_edge(fills[i]))
            elif fills[i]:
                edge = outline_for(fills[i], size, bright)
                if i in details:
                    h, l, s = _hls(edge)  # noqa: E741
                    edge = _from_hls(h, l - DETAIL_DARKER, s)
                tag = _set(tag, "stroke", edge)
            elif stroke_masks[i] is not None:
                line = stroke_masks[i] > 0.4
                under = [j for j in top[line].tolist() if j >= 0 and j != i]
                if under and len(under) >= 0.3 * line.sum():
                    j = max(set(under), key=under.count)
                    inside = (fill_masks[j] > 0.99)[line].mean()
                    # Lines on a fill in the full outline shade at every
                    # size (the softer inner shade vanished in the fill).
                    edge = outline_for(fills[j], size, bright)
                    if i in details:
                        h, l, s = _hls(edge)  # noqa: E741
                        edge = _from_hls(h, l - DETAIL_DARKER, s)
                    tag = _set(tag, "stroke", edge)
                else:
                    tag = _set(tag, "stroke", ink)
        if i in bold:
            moved = _attr(tag, "transform")
            tag = _set(tag, "stroke-width", "2")
            tag = _set(tag, "transform", f"translate({shift[0]} {shift[1]})" + (f" {moved}" if moved else ""))
        tags.append(tag)
    svg = _rebuild(svg, leaves, tags)
    out = _raster(svg, size)
    badges = np.zeros((size, size), bool)
    for i, mask in enumerate(fill_masks):
        if mask is not None and fills[i] in BADGES:
            badges |= mask > 0.25
    if shade and size >= EFFECTS_FROM:
        _shade(out, size, fills, fill_masks, stroke_masks)
    if free:
        # Free lines' smoothed edge pixels firmer, so curves read as one
        # solid colour, not a lighter rim like a shadow.
        alone = ~_dilated(top >= 0) & (out[..., 3] < 1)
        out[..., 3] = np.where(alone, np.clip((out[..., 3] - FIRM_LOW) / (1 - 2 * FIRM_LOW), 0, 1), out[..., 3])
    # Outlines drawn 2 px (INNER_LINE_FROM) are already the exterior's two
    # pixels: recoloured as one band, no pixel added inside them.
    widened = any(fills[i] is not None for i in bold)
    out = _exterior(out, size, top, fills, badges, 2 if widened else line_px, firm, add=not widened)
    return out


_FOUR = ((-1, 0), (1, 0), (0, -1), (0, 1))
_EIGHT = _FOUR + ((-1, -1), (-1, 1), (1, -1), (1, 1))


def _neighbours(mask, steps=_FOUR):
    """Shifted copies of `mask` (False beyond its border), as (copy, dy,
    dx): copy[y, x] is mask[y + dy, x + dx]."""
    result = []
    for dy, dx in steps:
        shifted = np.zeros_like(mask)
        ys = slice(max(0, -dy), mask.shape[0] - max(0, dy))
        xs = slice(max(0, -dx), mask.shape[1] - max(0, dx))
        yt = slice(max(0, dy), mask.shape[0] - max(0, -dy))
        xt = slice(max(0, dx), mask.shape[1] - max(0, -dx))
        shifted[ys, xs] = mask[yt, xt]
        result.append((shifted, dy, dx))
    return result


def _shifted(values, dy, dx):
    """values[y + dy, x + dx] at each pixel (edge pixels repeated)."""
    h, w = values.shape[:2]
    ys = np.clip(np.arange(h) + dy, 0, h - 1)
    xs = np.clip(np.arange(w) + dx, 0, w - 1)
    return values[ys][:, xs]


def _eroded(mask):
    result = mask.copy()
    for shifted, _dy, _dx in _neighbours(mask):
        result &= shifted
    return result


def _dilated(mask, steps=_EIGHT):
    result = mask.copy()
    for shifted, _dy, _dx in _neighbours(mask, steps):
        result |= shifted
    return result


def _exterior(out, size, top, fills, badges, line_px=1, firm=False, add=True):
    """The exterior outline (where the drawing meets the background) one
    pixel thicker, inwards, in one colour per shape: a darker shade of the
    fill it surrounds (_exterior_color), on the whole band (the outline,
    the pixel added inside it, the smoothed pixels just outside), so it
    reads as one line. Thin parts keep their fill beyond the outline only
    where there is room. Outlines with no fill inside (lines) and badge
    dots are left as drawn."""
    # Each shape's outline colour, where that shape is the topmost fill.
    colour = np.zeros((size, size, 3), np.float32)
    known = np.zeros((size, size), bool)
    for i, fill in enumerate(fills):
        if fill is None or fill in BADGES or fill in (BLACK, SOFT_BLACK) or not fill.startswith("#"):
            continue
        where = top == i
        if where.any():
            colour[where] = np.array(_rgb(_exterior_color(fill, firm)), np.float32)
            known |= where
    known &= ~badges
    if not known.any():
        return out
    alpha = out[..., 3]
    solid = alpha > 0.5
    inner = solid
    for _step in range(max(1, line_px)):
        inner = _eroded(inner)
    edge = solid & ~inner
    core = _eroded(inner)
    # The added pixel: just inside the outline, on a fill, with a fill
    # beyond it within two pixels (corners included), so a bar a few pixels
    # wide is not all outline.
    ring = inner & ~core & known & _dilated(_dilated(core))
    if not add:
        ring &= False
    # The outline band and the smoothed pixels outside it.
    fringe = (alpha > 0.02) & ~solid & _dilated(solid, _FOUR)
    band = (edge | fringe) & ~_dilated(badges)
    # Carry each shape's colour outwards from its fill over the band.
    for _step in range(max(1, line_px) + 2):
        grow = band & ~known
        if not grow.any():
            break
        reached = np.zeros_like(known)
        for shifted, dy, dx in _neighbours(known, _EIGHT):
            take = grow & shifted & ~reached
            if take.any():
                colour[take] = _shifted(colour, dy, dx)[take]
                reached |= take
        known |= reached
    # Only bands that touch a shape's fill: outline-only drawings keep
    # their lines.
    near = ring | (known & inner)
    for _step in range(max(1, line_px) + 1):
        near = _dilated(near)
    band &= known & near
    out[..., :3][band] = colour[band]
    inner_only = ring & ~band
    out[..., :3][inner_only] = (out[..., :3][inner_only] * (1 - EXTERIOR_INNER)
                                + colour[inner_only] * EXTERIOR_INNER)
    return out


def _exterior_color(fill, firm=False):
    """The exterior outline on a shape filled `fill` (hex): the fill's own
    colour darker (EXTERIOR_DARKER, the brightest channel at most
    EXTERIOR_MAX so white and pale fills still get a visible edge), then
    more saturated at that lightness (greys stay grey); `firm`: darker."""
    rgb = _rgb(fill)
    darker, cap = (FIRM_DARKER, FIRM_MAX) if firm else (EXTERIOR_DARKER, EXTERIOR_MAX)
    factor = min(darker, cap / max(max(rgb), 1e-3))
    h, l, sat = colorsys.rgb_to_hls(*(v * factor for v in rgb))  # noqa: E741
    if sat >= GREY:
        sat = min(1.0, sat * EXTERIOR_SATURATE)
    return _from_hls(h, l, sat)


def _shade(out, size, fills, fill_masks, stroke_masks):
    """The flat curved shadow (see the module docstring), in place."""

    # A flat shadow on each coloured shape where it shows (not under a
    # later shape, not on a line), beyond one arc across the whole drawing.
    lines = np.zeros((size, size), np.float32)
    for mask in stroke_masks:
        if mask is not None:
            lines = np.maximum(lines, mask)
    drawn = np.zeros((size, size), bool)
    for mask in fill_masks:
        if mask is not None:
            drawn |= mask > 0.5
    gy, gx = np.nonzero(drawn)
    if not len(gx):
        return
    x0, y0 = gx.min(), gy.min()
    width, height = gx.max() + 1 - x0, gy.max() + 1 - y0
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) + 0.5
    u, v = (xx - x0) / width - CURVE_CX, (yy - y0) / height - CURVE_CY
    beyond = np.clip((np.sqrt(u * u + v * v) - CURVE_R) * (width + height) / 2 + 0.5, 0, 1)
    for i, mask in enumerate(fill_masks):
        fill = fills[i]
        if mask is None or fill is None or fill in BADGES or fill in (BLACK, SOFT_BLACK):
            continue
        _h, light, saturation = _hls(fill)
        if light > UNSHADED_LIGHTNESS and saturation < UNSHADED_SATURATION:
            continue
        solid = mask > 0.5
        ys, xs = np.nonzero(solid)
        if len(ys) < 30 or min(xs.max() - xs.min() + 1, ys.max() - ys.min() + 1) < SHADE_MIN:
            continue
        # Later shapes cover it, translucent ones too (a toolbox's seam).
        later = np.zeros((size, size), bool)
        for other in fill_masks[i + 1:]:
            if other is not None:
                later |= other > 0.25
        cover = beyond * (solid & ~later & (lines < 0.25))
        if cover.any():
            color = np.array(_rgb(shadow_for(fill, size <= SMALL_DETAIL)), np.float32)
            out[..., :3] = out[..., :3] * (1 - cover[..., None]) + color * cover[..., None]
