"""Design-token resolution for Studio themes (pure Python, no Qt).

Token files use the QGIS variables.qss syntax, one `@name: value;` per line.
Values may reference other tokens and use two colour functions:

    mix(a, b, t)   blend colour a towards b by t (0..1)
    alpha(c, a)    colour c with opacity a (0..1)

The plugin resolves tokens itself instead of relying on QGIS's substitution,
which replaces names in file order without word boundaries (so `@text` would
corrupt `@text_dark`) and keeps the trailing semicolon of every value.
"""
import re

TOKEN = re.compile(r"@[A-Za-z_][A-Za-z0-9_]*")
FUNCTION = re.compile(r"\b(mix|alpha)\(([^()]*)\)")
COMMENT = re.compile(r"/\*.*?\*/", re.S)


def parse_tokens(*texts):
    """Collect raw `@name: value` definitions; later texts override."""
    raw = {}
    for text in texts:
        for line in COMMENT.sub("", text).splitlines():
            line = line.strip()
            if line.startswith("@") and ":" in line:
                name, value = line.split(":", 1)
                raw[name.strip()] = value.strip().rstrip(";").strip()
    return raw


def parse_color(value):
    """Return (r, g, b, a) with a in 0..1 for #rgb, #rrggbb, rgb(), rgba()."""
    value = value.strip()
    if value.startswith("#"):
        digits = value[1:]
        if len(digits) == 3:
            digits = "".join(c * 2 for c in digits)
        if len(digits) != 6:
            raise ValueError(f"unsupported colour {value!r}")
        return tuple(int(digits[i:i + 2], 16) for i in (0, 2, 4)) + (1.0,)
    match = re.fullmatch(r"rgba?\(([^)]*)\)", value)
    if not match:
        raise ValueError(f"unsupported colour {value!r}")
    parts = [p.strip() for p in match.group(1).split(",")]
    rgb = tuple(int(float(p)) for p in parts[:3])
    return rgb + ((float(parts[3]) if len(parts) > 3 else 1.0),)


def format_color(rgba):
    r, g, b, a = rgba
    if a >= 0.999:
        return f"#{round(r):02x}{round(g):02x}{round(b):02x}"
    return f"rgba({round(r)}, {round(g)}, {round(b)}, {a:.3f})"


def _apply_function(match):
    name, args = match.group(1), [a.strip() for a in match.group(2).split(",")]
    if name == "mix":
        first, second, amount = parse_color(args[0]), parse_color(args[1]), float(args[2])
        return format_color(
            tuple(x + (y - x) * amount for x, y in zip(first, second))
        )
    color = parse_color(args[0])
    return format_color(color[:3] + (float(args[1]),))


def resolve_tokens(raw):
    """Resolve references and functions; raises KeyError on unknown or
    circular references so broken themes fail loudly."""
    resolved = {}

    def resolve(name, stack):
        if name in resolved:
            return resolved[name]
        if name not in raw:
            raise KeyError(f"unknown token {name} (used by {stack[-1] if stack else '?'})")
        if name in stack:
            raise KeyError(f"circular token reference: {' -> '.join(stack + (name,))}")
        value = TOKEN.sub(lambda m: resolve(m.group(0), stack + (name,)), raw[name])
        while True:
            evaluated = FUNCTION.sub(_apply_function, value)
            if evaluated == value:
                break
            value = evaluated
        resolved[name] = value
        return value

    for token_name in raw:
        resolve(token_name, ())
    return resolved


def render(template, tokens):
    """Substitute whole-word tokens; returns (text, unknown token names)."""
    unknown = set()

    def substitute(match):
        name = match.group(0)
        if name in tokens:
            return tokens[name]
        unknown.add(name)
        return name

    return TOKEN.sub(substitute, template), unknown


def is_dark(color):
    """Relative luminance test used to pick the Qt colour scheme."""
    r, g, b, _ = parse_color(color)
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 < 0.5


# Syntax colours that are not theme colours, per mode: on a dark editor
# light tints, on a light one darker shades that keep their contrast.
SYNTAX = {
    True: {"class": "#82aaff", "string": "#e5c07b", "number": "#c99cf0", "error": "#ff7070"},
    False: {"class": "#2a5db0", "string": "#94600b", "number": "#8a3fb8", "error": "#c62828"},
}


def code_editor_ini(tokens):
    """QGIS's code editors (expressions, Python console, SQL...) take
    their colours from qscintilla.ini in the theme folder; without one they
    stay white even in a dark theme. Built from the theme's colours: its
    base background and text, the accent for keywords and selection."""

    def color(name):
        return parse_color(tokens[name])

    def mix(first, second, amount):
        return format_color(tuple(a + (b - a) * amount for a, b in zip(first, second)))

    background, text, accent = color("@bg_base"), color("@text"), color("@accent")
    dark = is_dark(tokens["@bg_base"])
    syntax = SYNTAX[dark]
    black = (0, 0, 0, 1.0)
    paper = format_color(background)
    default = format_color(text)
    keyword = mix(accent, text, 0.3) if dark else mix(accent, black, 0.25)
    # Quieter than code, still readable (about 4.5:1 or more).
    comment = mix(background, text, 0.5 if dark else 0.66)
    operator = format_color(color("@text_dim"))
    general = {
        "cursorColor": default,
        "caretLineColor": mix(background, text, 0.06),
        "marginBackgroundColor": format_color(color("@bg_window")),
        "marginForegroundColor": format_color(color("@text_disabled")),
        "selectionBackgroundColor": mix(background, accent, 0.4),
        "selectionForegroundColor": default,
        "matchedBraceColor": mix(background, accent, 0.25),
        "stderrFontColor": syntax["error"],
        "edgeColor": format_color(color("@border")),
        "foldColor": format_color(color("@bg_window")),
    }
    strings = {key: syntax["string"] for key in (
        "singleQuoteFontColor", "doubleQuoteFontColor",
    )}
    sections = {
        "general": general,
        "python": {
            "paperBackgroundColor": paper, "defaultFontColor": default,
            "classFontColor": syntax["class"], "methodFontColor": syntax["class"],
            "keywordFontColor": keyword, "decoratorFontColor": keyword,
            "numberFontColor": syntax["number"],
            "commentFontColor": comment, "commentBlockFontColor": comment,
            **strings,
            "tripleSingleQuoteFontColor": syntax["string"],
            "tripleDoubleQuoteFontColor": syntax["string"],
        },
        "sql": {
            "paperBackgroundColor": paper, "defaultFontColor": default,
            "commentFontColor": comment, "commentLineFontColor": comment,
            "numberFontColor": syntax["number"], "keywordFontColor": keyword,
            **strings,
            "operatorFontColor": operator,
            "identifierFontColor": syntax["class"], "QuotedIdentifierFontColor": syntax["class"],
            "QuotedOperatorFontColor": operator,
        },
        "html": {
            "paperBackgroundColor": paper, "defaultFontColor": default,
            "tagFontColor": keyword, "unknownTagFontColor": syntax["error"],
            "numberFontColor": syntax["number"], **strings, "commentFontColor": comment,
        },
    }
    return "\n".join(
        f"[{section}]\n" + "".join(f"{key}={value}\n" for key, value in values.items())
        for section, values in sections.items()
    )
