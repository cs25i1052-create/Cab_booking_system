"""
ui.py - presentation layer for the Cab Booking app.

Everything visual lives in this file:
  * the theme (one CSS block, injected once per run)
  * SVG artwork (logo, vehicle silhouettes, route map)
  * small HTML components (chips, route stops, ride tracker, notices ...)

app.py keeps all behaviour (session state, routing, database calls).
"""
from __future__ import annotations

import html as _html
import math
import random

import streamlit as st


# ============================================================================
# 1. SMALL HELPERS
# ============================================================================
def esc(value) -> str:
    """HTML-escape any value (names, locations and review text come from users)."""
    return _html.escape("" if value is None else str(value), quote=True)


def md(markup: str) -> None:
    """Render an HTML snippet.

    Lines are stripped and joined: Markdown treats blank lines and 4-space
    indents inside HTML as code blocks, which would break the layout.
    """
    st.markdown("".join(line.strip() for line in markup.strip().splitlines()), unsafe_allow_html=True)


def panel(key: str, *, border_fallback: bool = True):
    """A container whose key becomes a CSS hook (`.st-key-<key>`).

    Streamlit older than 1.39 has no container keys; fall back to a plain
    bordered container so the app still works (just less polished).
    """
    try:
        return st.container(key=key)
    except TypeError:
        return st.container(border=border_fallback)


def money(value) -> str:
    return f"₹{float(value):,.2f}"


def money_html(value, size: str = "md") -> str:
    """₹ amount with the paise de-emphasised (the way ride apps show fares)."""
    whole, frac = f"{float(value):,.2f}".split(".")
    return (
        f'<span class="money money--{size}"><span class="cur">₹</span>{whole}'
        f'<span class="frac">.{frac}</span></span>'
    )


def fmt_dt(value, seconds: bool = False) -> str:
    """'22 Oct 2026, 3:05 PM'. Falls back to the raw string for non-datetimes."""
    try:
        hour = value.hour % 12 or 12
        clock = f"{hour}:{value.minute:02d}"
        if seconds:
            clock += f":{value.second:02d}"
        clock += " AM" if value.hour < 12 else " PM"
        return f"{value.day} {value.strftime('%b %Y')}, {clock}"
    except AttributeError:
        return str(value)[: 19 if seconds else 16]


def short(name) -> str:
    """'Chennai Airport (MAA), Chennai' -> 'Chennai Airport (MAA)'."""
    return str(name).split(",")[0].strip()


def initials(name) -> str:
    parts = str(name or "").split()
    if not parts:
        return "?"
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()


def plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


# ============================================================================
# 2. ICONS (24x24 stroke icons)
# ============================================================================
_ICONS = {
    "phone": '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
    "mail": '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
    "user": '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    "id": '<rect x="2" y="5" width="20" height="14" rx="2"/><circle cx="8.5" cy="11" r="2"/><path d="M5.5 16.5c.7-1.3 1.7-1.8 3-1.8s2.3.5 3 1.8M14.5 10h4M14.5 14h2.5"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "check_circle": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "x": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "arrow_left": '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
    "refresh": '<path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>',
    "route": '<circle cx="6" cy="19" r="3"/><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/><circle cx="18" cy="5" r="3"/>',
    "pin": '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "star": '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    "power": '<path d="M12 2v10"/><path d="M18.4 6.6a9 9 0 1 1-12.77.04"/>',
    "alert": '<circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "log_out": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
    "trash": '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><path d="M10 11v6"/><path d="M14 11v6"/>',
    "car": '<path d="M19 17h2c.6 0 1-.4 1-1v-3c0-.9-.7-1.7-1.5-1.9C18.7 10.6 16 10 16 10s-1.3-1.4-2.2-2.3c-.5-.4-1.1-.7-1.8-.7H5c-.6 0-1.1.4-1.4.9l-1.4 2.9A3.7 3.7 0 0 0 2 12v4c0 .6.4 1 1 1h2"/><circle cx="7" cy="17" r="2"/><path d="M9 17h6"/><circle cx="17" cy="17" r="2"/>',
    "inbox": '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
    "seat": '<path d="M5 3v9a3 3 0 0 0 3 3h8"/><path d="M8 3h2.5a2 2 0 0 1 2 2v6"/><path d="M16 15v6"/><path d="M5 21h14"/>',
}


def icon(name: str, size: int = 18, *, fill: bool = False, sw: float = 2, cls: str = "") -> str:
    return (
        f'<svg class="ic {cls}" width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'fill="{"currentColor" if fill else "none"}" stroke="currentColor" stroke-width="{sw}" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{_ICONS[name]}</svg>'
    )


# ============================================================================
# 3. BRAND + VEHICLE ARTWORK
# ============================================================================
def logo_mark(size: int = 30, on_dark: bool = True) -> str:
    """Route glyph (pickup dot -> drop square) on a rounded tile."""
    tile, glyph = ("#fff", "#000") if on_dark else ("#000", "#fff")
    return (
        f'<svg class="logo" width="{size}" height="{size}" viewBox="0 0 28 28" fill="none" aria-hidden="true">'
        f'<rect width="28" height="28" rx="8" fill="{tile}"/>'
        f'<circle cx="9" cy="9" r="2.9" fill="{glyph}"/>'
        f'<path d="M9 12.2v4.3c0 1.7 1.3 3 3 3h4" stroke="{glyph}" stroke-width="2.2" stroke-linecap="round"/>'
        f'<rect x="16.6" y="16.9" width="5.2" height="5.2" rx="1" fill="{glyph}"/>'
        f"</svg>"
    )


def brand(tag: str | None = None, on_dark: bool = True) -> str:
    tag_html = f'<span class="brand-tag">{esc(tag)}</span>' if tag else ""
    return (
        f'<div class="brand {"brand--dark" if on_dark else "brand--light"}">'
        f'{logo_mark(30, on_dark)}<span class="brand-name">Cab Booking</span>{tag_html}</div>'
    )


# Vehicle silhouettes, side view facing right, drawn on a 120 x 48 canvas.
# Colours come from CSS variables (--car-b body, --car-w glass, --car-t tyres, --car-h hubs).
_CARS = {
    "sedan": {
        "body": "M6 34.5V30c0-3 1.8-4.6 4.6-5.2L26 22 37 10.6C38.8 8.8 41 8 43.5 8H78c3.4 0 5.6 1 7.6 3.2L95 22l12.6 2.6c4.4.9 6.4 3.3 6.4 7v2.9c0 1.2-.8 2-2 2h-7.5a12.5 12.5 0 0 0-25 0H43a12.5 12.5 0 0 0-25 0H8c-1.2 0-2-.8-2-2z",
        "glass": [
            "M30 21 38.6 12.2Q39.6 11.2 41.2 11.2H53.5V21Z",
            "M58 11.2H79.6Q81.4 11.2 82.8 12.7L91 21H58Z",
        ],
        "wheels": (30.5, 92, 36.5, 9.5),
    },
    "hatch": {
        "body": "M10 34.5V30c0-3 1.7-4.6 4.4-5.3L24 22.4 31 11.6C32.6 9.2 34.8 8 37.6 8H73c3.6 0 6 1.2 8 3.4L93 22.4l13 2.4c4 .8 5.8 3.2 5.8 6.8v2.9c0 1.2-.8 2-2 2h-6.8a12.5 12.5 0 0 0-25 0H43.5a12.5 12.5 0 0 0-25 0H12c-1.2 0-2-.8-2-2z",
        "glass": [
            "M28 21.4 33.6 13Q34.5 11.2 36.6 11.2H52.6V21.4Z",
            "M57 11.2H71.8Q73.8 11.2 75.2 12.7L83.6 21.4H57Z",
        ],
        "wheels": (31, 90.5, 36.5, 9.5),
    },
    "suv": {
        "body": "M6 36V27c0-2.6 1.4-4 4-4.6L14 21.6V12c0-3 2-5 5-5H72c3.4 0 5.8 1.2 7.8 3.4L95 22.4l12.6 2.4c4.6.9 6.4 3.2 6.4 7V36c0 1.2-.8 2-2 2h-7.5a13 13 0 0 0-26 0H45a13 13 0 0 0-26 0H8c-1.2 0-2-.8-2-2z",
        "glass": [
            "M18 21.4V12.6Q18 10.8 19.8 10.8H35.5V21.4Z",
            "M39.5 10.8H56.5V21.4H39.5Z",
            "M60.5 10.8H74.4Q76.2 10.8 77.6 12.2L87.4 21.4H60.5Z",
        ],
        "wheels": (32, 91.5, 38, 10),
    },
}


def car_kind(category_name: str) -> str:
    """Pick a silhouette from the category name (SUV / hatchback / sedan)."""
    n = str(category_name or "").lower()
    if any(k in n for k in ("suv", "xl", "van", "innova", "ertiga", "large", "premier", "prime suv")):
        return "suv"
    if any(k in n for k in ("hatch", "mini", "micro", "compact", "go", "economy", "small")):
        return "hatch"
    return "sedan"


def _car_inner(kind: str) -> str:
    spec = _CARS.get(kind, _CARS["sedan"])
    cx1, cx2, cy, r = spec["wheels"]
    parts = [
        f'<ellipse class="car-shadow" cx="60" cy="{cy + r + 1.2:.1f}" rx="47" ry="2.3"/>',
        f'<path class="b" d="{spec["body"]}"/>',
    ]
    parts += [f'<path class="w" d="{g}"/>' for g in spec["glass"]]
    for cx in (cx1, cx2):
        parts.append(f'<circle class="t" cx="{cx}" cy="{cy}" r="{r}"/><circle class="h" cx="{cx}" cy="{cy}" r="{r * 0.4:.1f}"/>')
    return "".join(parts)


def car_svg(kind: str = "sedan", width: int = 96, cls: str = "") -> str:
    height = round(width * 48 / 120)
    return (
        f'<svg class="car {cls}" width="{width}" height="{height}" viewBox="0 0 120 48" '
        f'fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">{_car_inner(kind)}</svg>'
    )


def favicon():
    """Browser-tab icon matching the logo. Falls back to an emoji if Pillow is missing."""
    try:
        from PIL import Image, ImageDraw

        size = 128
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((0, 0, size - 1, size - 1), radius=34, fill=(0, 0, 0, 255))
        d.ellipse((28, 28, 58, 58), fill="white")
        d.line([(43, 58), (43, 78), (52, 88), (74, 88)], fill="white", width=10, joint="curve")
        d.rounded_rectangle((74, 72, 102, 100), radius=5, fill="white")
        return img
    except Exception:
        return "🚖"


# ============================================================================
# 4. ROUTE MAP (schematic; positions come from the real coordinates)
# ============================================================================
_MAP_LIGHT = dict(land="#EEEEEE", road="#FFFFFF", minor="#F8F8F8", park="#E2E9DD", water="#D8E3EB",
                  casing="#FFFFFF", route="#000000", mark="#000000", ring="#FFFFFF",
                  pill="#FFFFFF", pill_ink="#000000", glow="rgba(0,0,0,.16)")
_MAP_DARK = dict(land="#0A0A0A", road="#1B1B1B", minor="#131313", park="#0F1510", water="#0C131A",
                 casing="#0A0A0A", route="#FFFFFF", mark="#FFFFFF", ring="#0A0A0A",
                 pill="#FFFFFF", pill_ink="#000000", glow="rgba(0,0,0,.55)")


def _bezier(p0, c, p1, t):
    u = 1 - t
    return (u * u * p0[0] + 2 * u * t * c[0] + t * t * p1[0], u * u * p0[1] + 2 * u * t * c[1] + t * t * p1[1])


def _pill(text, cx, top, c, W, H, icon_svg="", maxlen=24):
    text = text if len(text) <= maxlen else text[: maxlen - 1] + "…"
    h = 38
    w = 32 + 9.2 * len(text) + (22 if icon_svg else 0)
    left = min(max(cx - w / 2, 10), W - w - 10)
    top = min(max(top, 8), H - h - 8)
    tx = left + w / 2 + (11 if icon_svg else 0)
    icon_part = (
        f'<g transform="translate({left + 14:.0f} {top + 10:.0f})" style="color:{c["pill_ink"]}">{icon_svg}</g>'
        if icon_svg else ""
    )
    return (
        f'<rect x="{left:.0f}" y="{top + 2.5:.0f}" width="{w:.0f}" height="{h}" rx="19" fill="{c["glow"]}"/>'
        f'<rect x="{left:.0f}" y="{top:.0f}" width="{w:.0f}" height="{h}" rx="19" fill="{c["pill"]}"/>'
        f"{icon_part}"
        f'<text x="{tx:.0f}" y="{top + 24.5:.0f}" text-anchor="middle" font-size="17" font-weight="700" '
        f'fill="{c["pill_ink"]}" style="letter-spacing:-.01em">{esc(text)}</text>'
    )


def _grid_line(cx, cy, angle, offset, width, color):
    """A long line at `angle`, `offset` px from the centre measured along its normal."""
    nx, ny = -math.sin(angle), math.cos(angle)
    px, py = cx + nx * offset, cy + ny * offset
    dx, dy = math.cos(angle) * 700, math.sin(angle) * 700
    return (f'<path d="M{px - dx:.0f} {py - dy:.0f}L{px + dx:.0f} {py + dy:.0f}" '
            f'stroke="{color}" stroke-width="{width}"/>')


def route_map(a=None, b=None, a_name: str = "", b_name: str = "", km=None, progress=None,
              searching: bool = False, dark: bool = False, animate: bool = False,
              uid: str = "m", hint: str | None = None) -> str:
    """Return an SVG route preview.

    a / b          (lat, lon) of pickup / destination, or None for an empty map
    progress       0..1 puts a vehicle marker along the route
    searching      pulsing ring on the pickup (waiting for a driver)
    animate        draws the route line in once
    """
    W, H = 560, 320
    c = _MAP_DARK if dark else _MAP_LIGHT
    rng = random.Random(f"{uid}|{a}|{b}")
    s = [
        f'<svg class="rmap" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Route preview">',
        f'<rect width="{W}" height="{H}" fill="{c["land"]}"/>',
    ]

    # --- backdrop: a rotated city grid with parks and a river (seeded, so it is stable per route)
    theta = math.radians(rng.uniform(-16, 16))
    cx0, cy0 = W / 2, H / 2
    for _ in range(3):
        w, h = rng.uniform(70, 140), rng.uniform(44, 90)
        x, y = rng.uniform(40, W - w - 40), rng.uniform(30, H - h - 30)
        s.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="{w:.0f}" height="{h:.0f}" rx="14" fill="{c["park"]}" '
                 f'transform="rotate({math.degrees(theta):.1f} {x + w / 2:.0f} {y + h / 2:.0f})"/>')
    y0 = rng.uniform(H * 0.25, H * 0.75)
    s.append(f'<path d="M-20 {y0:.0f}C{W * .3:.0f} {y0 - 70:.0f} {W * .62:.0f} {y0 + 80:.0f} {W + 20} {y0 - 24:.0f}'
             f'L{W + 20} {y0 + 10:.0f}C{W * .62:.0f} {y0 + 112:.0f} {W * .3:.0f} {y0 - 38:.0f} -20 {y0 + 40:.0f}Z" fill="{c["water"]}"/>')
    s.append('<g fill="none" stroke-linecap="butt">')
    off = -330.0
    while off < 330:                                   # side streets (thin)
        s.append(_grid_line(cx0, cy0, theta, off, 3, c["minor"]))
        off += rng.uniform(26, 44)
    off = -420.0
    while off < 420:
        s.append(_grid_line(cx0, cy0, theta + math.pi / 2, off, 3, c["minor"]))
        off += rng.uniform(30, 52)
    off = -300.0
    while off < 300:                                   # avenues
        s.append(_grid_line(cx0, cy0, theta, off, rng.choice((7, 8, 9)), c["road"]))
        off += rng.uniform(70, 120)
    off = -400.0
    while off < 400:
        s.append(_grid_line(cx0, cy0, theta + math.pi / 2, off, rng.choice((6, 7, 8)), c["road"]))
        off += rng.uniform(80, 140)
    for _ in range(2):                                 # diagonal arterials
        s.append(_grid_line(cx0, cy0, theta + math.radians(rng.choice((-38, 38))), rng.uniform(-150, 150), 10, c["road"]))
    s.append("</g>")

    if not (a and b):
        if hint:
            s.append(_pill(hint, W / 2, H / 2 - 19, c, W, H, maxlen=60))
        s.append("</svg>")
        return "".join(s)

    # --- project the two real coordinates onto the canvas
    (lat1, lon1), (lat2, lon2) = a, b
    k = math.cos(math.radians((lat1 + lat2) / 2))
    dx, dy = (lon2 - lon1) * k, (lat1 - lat2)          # north is up
    pad_x, pad_y = 92, 88
    span = max(abs(dx), 1e-9), max(abs(dy), 1e-9)
    scale = min((W - 2 * pad_x) / span[0], (H - 2 * pad_y) / span[1])
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        dx, scale = 1.0, 120.0
    p0 = (W / 2 - dx * scale / 2, H / 2 - dy * scale / 2)
    p1 = (W / 2 + dx * scale / 2, H / 2 + dy * scale / 2)

    # gentle bend so the route reads like a road, not a ruler line
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    vx, vy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(vx, vy) or 1.0
    bend = min(0.2 * length, 50) * (1 if rng.random() < 0.5 else -1)
    ctrl = (mx - vy / length * bend, my + vx / length * bend)
    d = f"M{p0[0]:.1f} {p0[1]:.1f}Q{ctrl[0]:.1f} {ctrl[1]:.1f} {p1[0]:.1f} {p1[1]:.1f}"
    draw = ' pathLength="1" class="route-draw"' if animate else ""
    s.append(f'<path d="{d}" fill="none" stroke="{c["casing"]}" stroke-width="13" stroke-linecap="round" opacity=".95"/>')
    s.append(f'<path d="{d}" fill="none" stroke="{c["route"]}" stroke-width="5" stroke-linecap="round"{draw}/>')

    # --- pickup (dot) and destination (square)
    if searching:
        s.append(f'<circle class="map-pulse" cx="{p0[0]:.1f}" cy="{p0[1]:.1f}" r="10" fill="{c["mark"]}" opacity=".35"/>')
    s.append(f'<circle cx="{p0[0]:.1f}" cy="{p0[1] + 2.5:.1f}" r="12" fill="{c["glow"]}"/>')
    s.append(f'<circle cx="{p0[0]:.1f}" cy="{p0[1]:.1f}" r="10" fill="{c["mark"]}" stroke="{c["ring"]}" stroke-width="4"/>')
    s.append(f'<rect x="{p1[0] - 10:.1f}" y="{p1[1] - 7.5:.1f}" width="20" height="20" rx="3.5" fill="{c["glow"]}"/>')
    s.append(f'<rect x="{p1[0] - 10:.1f}" y="{p1[1] - 10:.1f}" width="20" height="20" rx="3.5" fill="{c["mark"]}" stroke="{c["ring"]}" stroke-width="4"/>')

    # --- labels sit outside the route so they never cover it
    drop_lower = p1[1] >= p0[1]
    top_a = p0[1] - 62 if drop_lower else p0[1] + 24
    top_b = p1[1] + 24 if drop_lower else p1[1] - 62
    if a_name:
        s.append(_pill(short(a_name), p0[0], top_a, c, W, H))
    if b_name:
        s.append(_pill(short(b_name), p1[0], top_b, c, W, H))

    if km is not None and progress is None:
        mid = _bezier(p0, ctrl, p1, 0.5)
        s.append(_pill(f"{km} km", mid[0], mid[1] - 19, c, W, H, icon_svg=icon("route", 18, sw=2.4)))

    # --- vehicle marker along the route
    if progress is not None:
        vx_, vy_ = _bezier(p0, ctrl, p1, max(0.0, min(1.0, float(progress))))
        vehicle_vars = ("--car-b:#000;--car-w:#fff;--car-t:#000;--car-h:#fff" if dark
                        else "--car-b:#fff;--car-w:#000;--car-t:#fff;--car-h:#000")
        s.append(f'<circle cx="{vx_:.1f}" cy="{vy_ + 3:.1f}" r="25" fill="{c["glow"]}"/>')
        s.append(f'<circle cx="{vx_:.1f}" cy="{vy_:.1f}" r="24" fill="{c["mark"]}" stroke="{c["ring"]}" stroke-width="4"/>')
        s.append(f'<svg x="{vx_ - 18:.1f}" y="{vy_ - 7.2:.1f}" width="36" height="14.4" viewBox="0 0 120 48" '
                 f'style="{vehicle_vars}" overflow="visible">{_car_inner("sedan").replace("car-shadow", "car-noshadow")}</svg>')

    s.append("</svg>")
    return "".join(s)


# Real coordinates used by the sign-in artwork.
_HERO_A, _HERO_B = (13.0827, 80.2707), (12.9941, 80.1709)


def route_card(a=None, b=None, a_name="", b_name="", km=None, progress=None, searching=False,
               hint="Choose pickup and destination to preview your route", uid="card") -> None:
    svg = route_map(a, b, a_name, b_name, km=km, progress=progress, searching=searching, uid=uid,
                    hint=None if (a and b) else hint)
    md(f'<div class="mapcard">{svg}</div>')


def auth_hero(headline: str, tag: str | None = None) -> None:
    art = route_map(_HERO_A, _HERO_B, "Chennai Central", "Chennai Airport (MAA)", dark=True,
                    animate=True, progress=0.58, uid="hero")
    md(
        f'<div class="hero">'
        f'<div class="hero-top">{brand(tag)}</div>'
        f'<div class="hero-title" role="heading" aria-level="1">{esc(headline)}</div>'
        f'<div class="hero-art">{art}</div>'
        f"</div>"
    )


# ============================================================================
# 5. HTML COMPONENTS
# ============================================================================
STATUS_LABEL = {
    "REQUESTED": "Requested", "ACCEPTED": "Accepted", "ONGOING": "Ongoing",
    "COMPLETED": "Completed", "CANCELLED": "Cancelled", "NO_DRIVERS": "No drivers",
    "AVAILABLE": "Available", "ON_TRIP": "On trip", "OFFLINE": "Offline",
}


def status_label(status) -> str:
    return STATUS_LABEL.get(str(status), str(status).replace("_", " ").title())


def chip(status, small: bool = False) -> str:
    key = str(status).lower().replace("_", "-")
    return f'<span class="chip chip--{key}{" chip--sm" if small else ""}"><i class="chip-dot"></i>{esc(status_label(status))}</span>'


def pill(text: str, icon_name: str | None = None, extra: str = "") -> str:
    ic = icon(icon_name, 15) if icon_name else ""
    return f'<span class="chip chip--plain {extra}">{ic}{esc(text)}</span>'


def avatar(name, size: int = 44, light: bool = False) -> str:
    return f'<span class="avatar{" avatar--light" if light else ""}" style="--s:{size}px">{esc(initials(name))}</span>'


def plate(text) -> str:
    return f'<span class="plate">{esc(text)}</span>'


def stars(rating, size: int = 15) -> str:
    try:
        r = max(0, min(5, int(round(float(rating)))))
    except (TypeError, ValueError):
        r = 0
    body = "".join(
        f'<span class="star{" on" if i < r else ""}">{icon("star", size, fill=True, sw=1.5)}</span>' for i in range(5)
    )
    return f'<span class="stars">{body}</span>'


def stops(pickup, drop, small: bool = False) -> str:
    """Pickup dot -> destination square, joined by a line (the ride-app signature)."""
    return (
        f'<div class="stops{" stops--sm" if small else ""}">'
        f'<div class="stop"><i class="stop-dot"></i><span>{esc(pickup)}</span></div>'
        f'<div class="stop"><i class="stop-sq"></i><span>{esc(drop)}</span></div>'
        f"</div>"
    )


def notice(kind: str, text: str, title: str | None = None) -> None:
    """kind: error | warn | info | success"""
    ic = {"error": "alert", "warn": "alert", "info": "info", "success": "check_circle"}[kind]
    head = f"<b>{esc(title)}</b> " if title else ""
    md(f'<div class="notice notice--{kind}" role="alert">{icon(ic, 20)}<div>{head}{esc(text)}</div></div>')


def empty(title: str, text: str | None = None, icon_name: str = "inbox") -> None:
    desc = f'<div class="empty-d">{esc(text)}</div>' if text else ""
    md(
        f'<div class="empty"><span class="empty-ic">{icon(icon_name, 22)}</span>'
        f'<div class="empty-t">{esc(title)}</div>{desc}</div>'
    )


def heading(text: str, level: int = 2) -> None:
    md(f'<div class="h{level}" role="heading" aria-level="{level}">{esc(text)}</div>')


def kv(rows) -> str:
    return '<div class="kv">' + "".join(
        f'<div class="kv-row"><span class="kv-k">{esc(k)}</span><span class="kv-v">{v}</span></div>' for k, v in rows
    ) + "</div>"


_TRACKER_STAGES = {
    "REQUESTED": (1, "Assigning a Driver...", "Contacting a nearby available driver in your category. If busy, another driver is approached automatically."),
    "ACCEPTED": (2, "Driver Accepted!", "Your driver has accepted the ride request and is heading to your pickup point."),
    "ONGOING": (3, "Ride Ongoing", "You are currently en route to your destination. Enjoy your ride!"),
    "COMPLETED": (4, "Ride Completed", "You have arrived at your destination. Thank you for riding with Cab Booking!"),
}
_TRACKER_STEPS = ("Assigning Driver", "Driver Accepted", "Ride Ongoing", "Ride Completed")


def tracker(status: str, car: str = "sedan") -> None:
    """Live ride progress: a car on a road with four stages."""
    if status not in _TRACKER_STAGES:
        notice("error", f"Ride Status: {status_label(status)}")
        return
    idx, headline, sub = _TRACKER_STAGES[status]
    f = (idx - 1) / 3
    done_all = status == "COMPLETED"
    steps = []
    for i, label in enumerate(_TRACKER_STEPS, 1):
        state = "done" if (i < idx or done_all) else ("now" if i == idx else "todo")
        inner = icon("check", 14, sw=3.2) if state == "done" else ""
        steps.append(f'<div class="trk-step {state}"><span class="trk-node">{inner}</span><span class="trk-label">{label}</span></div>')
    scan = '<i class="trk-scan"></i>' if status == "REQUESTED" else ""
    md(
        f'<div class="trk{" trk--done" if done_all else ""}" style="--f:{f:.4f}">'
        f'<div class="trk-title" role="heading" aria-level="2">{esc(headline)}</div>'
        f'<div class="trk-sub">{esc(sub)}</div>'
        f'<div class="trk-lane"><div class="trk-car">{car_svg(car, 92)}</div></div>'
        f'<div class="trk-steps">{scan}{"".join(steps)}</div>'
        f"</div>"
    )


# ============================================================================
# 6. THEME (CSS)
# ============================================================================
_CSS = r"""
@import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700;800&display=swap');

/* ==========================================================================
   0. TOKENS
   ========================================================================== */
:root {
  --font: 'Figtree', system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
  --ink: #000000;
  --ink-2: #3A3A3A;
  --ink-3: #6B6B6B;
  --ink-4: #A3A3A3;
  --line: #E6E6E6;
  --line-2: #F0F0F0;
  --fill: #F3F3F3;
  --fill-2: #E8E8E8;
  --fill-3: #D9D9D9;
  --blue: #276EF1;  --blue-bg: #E7EFFE;  --blue-ink: #1B4DB8;
  --green: #05944F; --green-bg: #E2F4EA; --green-ink: #036B38;
  --amber: #FFC043; --amber-bg: #FFF3D1; --amber-ink: #7A5100;
  --red: #E11900;   --red-bg: #FDE8E5;   --red-ink: #A11200;
  --max: 1180px;
  --ease: cubic-bezier(.22, .7, .2, 1);
  color-scheme: light;
}

/* ==========================================================================
   1. BASE + STREAMLIT CHROME
   ========================================================================== */
html, body { background: #fff; }
.stApp {
  background: #fff; color: var(--ink); font-family: var(--font);
  -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; text-rendering: optimizeLegibility;
}
body :where(*):not([data-testid="stIconMaterial"]):not(svg *) { font-family: var(--font); }
::selection { background: #000; color: #fff; }
* { scrollbar-width: thin; scrollbar-color: #CFCFCF transparent; }

[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], #MainMenu, footer { display: none !important; }
[data-testid="stAppViewContainer"], [data-testid="stMain"], section.main { background: #fff; }
[data-testid="stMainBlockContainer"], [data-testid="stAppViewBlockContainer"], .block-container {
  max-width: 100% !important; padding: 0 !important;
}
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"],
[data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlockBorderWrapper"] > div > [data-testid="stVerticalBlock"],
.block-container > [data-testid="stVerticalBlock"] { gap: 0 !important; }
/* the element that only carries our <style> must not take up layout space */
.element-container:has(> [data-testid="stMarkdown"] style), [data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] style) { display: none !important; }

/* Streamlit trims 16px off every markdown container; our blocks are layout, not paragraphs */
[data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }
[data-testid="stMarkdownContainer"] p { margin: 0 !important; }
.element-container:has([data-testid="stRadio"]), .element-container:has([data-testid="stSelectbox"]),
.element-container:has([data-testid="stTextInput"]) { width: 100% !important; }

/* older Streamlit sets inline pixel widths measured on the whole window; never let them exceed the container */
.element-container, [data-testid="stElementContainer"], [data-testid="stMarkdown"], [data-testid="stButton"],
[data-testid="stSelectbox"], [data-testid="stTextInput"], [data-testid="stRadio"] { max-width: 100% !important; box-sizing: border-box; }
[data-testid="stMarkdown"] { width: 100% !important; }

/* thin progress bar while the app is working (replaces the default 'running' widget) */
.stApp[data-test-script-state="running"]::before {
  content: ""; position: fixed; inset: 0 0 auto 0; height: 3px; z-index: 1000000;
  background: linear-gradient(90deg, transparent, var(--blue) 50%, transparent) 0 0 / 35% 100% no-repeat;
  animation: cb-load 1.15s ease-in-out infinite;
}
@keyframes cb-load { from { background-position: -40% 0; } to { background-position: 140% 0; } }
[data-stale="true"] { opacity: .55 !important; transition: opacity .25s ease .3s !important; }

:focus-visible { outline: 2px solid var(--blue); outline-offset: 2px; }
[data-testid="stTextInputRootElement"] input:focus-visible, [data-testid="stSelectbox"] input:focus-visible { outline: none !important; }

/* ==========================================================================
   2. APP BAR + PAGE FRAME
   ========================================================================== */
[data-testid="stLayoutWrapper"]:has(> .st-key-appbar),
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > .st-key-appbar),
.block-container > [data-testid="stVerticalBlock"] > .st-key-appbar { position: sticky; top: 0; z-index: 100; }
.st-key-appbar {
  background: #000; width: 100%; box-sizing: border-box; height: 68px !important;
  display: flex !important; flex-direction: row !important; align-items: center !important; gap: 12px !important;
  padding: 0 max(20px, calc((100% - var(--max)) / 2 + 24px)) !important;
}
.st-key-appbar > * { width: auto !important; min-width: 0; }
.st-key-appbar [data-testid="stMarkdown"], .st-key-pagehead [data-testid="stMarkdown"] { width: auto !important; }
.st-key-appbar > *:first-child { flex: 0 0 auto; }
.st-key-appbar > *:last-child { flex: 0 0 auto; margin-left: auto; }
.st-key-appbar > *:not(:first-child):not(:last-child) { flex: 1 1 auto; }

.brand { display: flex; align-items: center; gap: 10px; }
.brand .logo { flex: none; display: block; }
.brand-name { font-size: 20px; font-weight: 800; letter-spacing: -.03em; line-height: 1; }
.brand--dark .brand-name { color: #fff; }
.brand--light .brand-name { color: #000; }
.brand-tag { margin-left: 4px; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; line-height: 1; }
.brand--dark .brand-tag { background: #262626; color: #D9D9D9; }
.brand--light .brand-tag { background: var(--fill); color: var(--ink-2); }

.st-key-appnav { display: flex !important; flex-direction: row !important; align-items: center !important; gap: 4px !important; margin-left: 20px; }
.st-key-appnav > * { width: auto !important; flex: 0 0 auto; }
.st-key-appnav [data-testid="stButton"], .st-key-appnav .stButton, .st-key-pagehead [data-testid="stButton"], .st-key-pagehead .stButton, [class*="st-key-back_"] .stButton { width: auto !important; }
.st-key-appnav .stButton button {
  min-height: 40px; padding: 0 16px; border-radius: 999px; background: transparent; color: #C4C4C4;
  font-size: 15px; font-weight: 600;
}
.st-key-appnav .stButton button:hover { background: #1E1E1E; color: #fff; }
[class*="st-key-navon_"] .stButton button { background: #fff !important; color: #000 !important; }
[class*="st-key-nav_live"] .stButton button::before,
[class*="st-key-navon_live"] .stButton button::before {
  content: ""; width: 8px; height: 8px; border-radius: 50%; background: #06C167; margin-right: 8px;
  animation: cb-blink 1.6s ease-in-out infinite;
}
@keyframes cb-blink { 0%, 100% { opacity: 1; } 50% { opacity: .35; } }

/* profile menu trigger (single chevron, avatar glyph) */
.st-key-appbar [data-testid="stPopover"] button {
  background: #1E1E1E !important; color: #fff !important; border: 0 !important; border-radius: 999px !important;
  height: 44px; min-height: 44px !important; padding: 0 14px 0 6px !important; gap: 10px;
  font-size: 15px; font-weight: 600;
}
.st-key-appbar [data-testid="stPopover"] button:hover { background: #2C2C2C !important; }
.st-key-appbar [data-testid="stPopover"] button p,
.st-key-appbar [data-testid="stPopover"] button [data-testid="stMarkdownContainer"] { color: #fff !important; font-weight: 600 !important; margin: 0; }
.st-key-appbar [data-testid="stPopover"] button svg,
.st-key-appbar [data-testid="stPopover"] button [data-testid="stIconMaterial"] { display: none !important; }
.st-key-appbar [data-testid="stPopover"] button::before {
  content: ""; flex: none; width: 32px; height: 32px; border-radius: 50%;
  background: #fff url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2'/%3E%3Ccircle cx='12' cy='7' r='4'/%3E%3C/svg%3E") center / 17px 17px no-repeat;
}
.st-key-appbar [data-testid="stPopover"] button::after {
  content: ""; flex: none; width: 16px; height: 16px; opacity: .75;
  background: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23fff' stroke-width='2.6' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E") center / 16px 16px no-repeat;
}

/* menu panel */
[data-testid="stPopoverBody"] {
  min-width: 280px; padding: 10px !important; background: #fff !important;
  border: 1px solid var(--line-2) !important; border-radius: 18px !important; box-shadow: 0 16px 48px rgba(0,0,0,.18) !important;
}
[data-testid="stPopoverBody"] .stButton button {
  justify-content: flex-start; min-height: 46px; padding: 0 14px; border-radius: 12px; background: transparent;
  font-size: 15.5px; font-weight: 600;
}
[data-testid="stPopoverBody"] .stButton button:hover { background: var(--fill); }
[data-testid="stPopoverBody"] .stButton button > div { justify-content: flex-start !important; width: 100%; }
[data-testid="stPopoverBody"] .stButton button, [data-testid="stPopoverBody"] .stButton button p,
[data-testid="stPopoverBody"] .stButton button [data-testid="stMarkdownContainer"] { text-align: left !important; justify-content: flex-start !important; width: 100%; }
.menu-head { display: flex; align-items: center; gap: 12px; padding: 6px 6px 12px; }
.menu-name { font-size: 17px; font-weight: 700; letter-spacing: -.01em; line-height: 22px; }
.menu-sub { font-size: 13.5px; color: var(--ink-3); font-weight: 500; line-height: 20px; }
.menu-sep { height: 1px; background: var(--line-2); margin: 6px 4px; }

.st-key-pagehead { display: flex !important; flex-direction: row !important; flex-wrap: wrap; align-items: center !important; gap: 6px 12px !important; width: 100%; }
.st-key-pagehead > * { width: auto !important; flex: 0 0 auto; min-width: 0; }
.st-key-pagehead > *:nth-child(2) { order: 3; flex: 1 1 100%; }
.st-key-pagehead > *:nth-child(3) { margin-left: auto; }
[class*="st-key-back_"] { margin-left: -14px; }
.st-key-page { width: 100%; max-width: var(--max); margin: 0 auto; padding: 32px 24px 96px; box-sizing: border-box; gap: 24px !important; }
.st-key-narrow { width: 100%; max-width: 900px; margin: 0 auto; gap: 16px !important; }
.st-key-narrow-sm { width: 100%; max-width: 580px; margin: 0 auto; gap: 16px !important; }
[data-testid="stHorizontalBlock"] { gap: 24px; }

/* ==========================================================================
   3. TYPE
   ========================================================================== */
.h1 { font-size: 36px; line-height: 42px; font-weight: 700; letter-spacing: -.03em; color: #000; }
.h2 { font-size: 26px; line-height: 32px; font-weight: 700; letter-spacing: -.022em; color: #000; }
.h3 { font-size: 19px; line-height: 26px; font-weight: 700; letter-spacing: -.012em; color: #000; }
.h4 { font-size: 16px; line-height: 22px; font-weight: 700; letter-spacing: -.005em; color: #000; }
.meta { font-size: 14px; line-height: 20px; font-weight: 500; color: var(--ink-3); }
.meta b { color: var(--ink); font-weight: 600; }
.lbl { font-size: 13px; line-height: 16px; font-weight: 600; color: var(--ink-3); }
.inline { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.inline--between { justify-content: space-between; flex-wrap: nowrap; }
.on-dark .h3, .on-dark .h4, .on-dark .person-name { color: #fff; }
.on-dark .meta, .on-dark .lbl { color: #ADADAD; }
.on-dark .meta b { color: #fff; }
.page-head { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }

.money { font-variant-numeric: tabular-nums; font-weight: 700; letter-spacing: -.025em; white-space: nowrap; color: inherit; }
.money .cur { font-weight: 600; margin-right: 1px; }
.money .frac { font-size: .62em; font-weight: 600; color: var(--ink-3); letter-spacing: 0; margin-left: 1px; }
.money--lg { font-size: 44px; line-height: 48px; }
.money--md { font-size: 26px; line-height: 30px; }
.money--sm { font-size: 20px; line-height: 24px; }
.on-dark .money .frac { color: #A6A6A6; }

/* ==========================================================================
   4. BUTTONS
   ========================================================================== */
.stButton button {
  min-height: 48px; padding: 0 22px; border: 0 !important; border-radius: 10px;
  background: var(--fill); color: #000; font-size: 15px; font-weight: 600; letter-spacing: -.005em; line-height: 1.1;
  box-shadow: none; transition: background-color .15s ease, transform .1s ease, box-shadow .15s ease;
}
.stButton button:hover { background: var(--fill-2); color: #000; }
.stButton button:active { transform: scale(.985); }
.stButton button:focus-visible { outline: 2px solid #000; outline-offset: 2px; }
.stButton button p, .stButton button [data-testid="stMarkdownContainer"] { color: inherit !important; font: inherit !important; margin: 0 !important; }
.stButton button[kind="primary"], .stButton button[data-testid="stBaseButton-primary"] { background: #000; color: #fff; }
.stButton button[kind="primary"]:hover, .stButton button[data-testid="stBaseButton-primary"]:hover { background: #2B2B2B; color: #fff; }
.stButton button:disabled, .stButton button:disabled:hover { background: var(--fill); color: #ABABAB; cursor: not-allowed; transform: none; }
.stButton button[kind="primary"]:disabled, .stButton button[data-testid="stBaseButton-primary"]:disabled { background: #E3E3E3; color: #9C9C9C; }

/* large call-to-action */
[class*="st-key-cta_"] .stButton button { min-height: 54px; font-size: 16px; border-radius: 12px; }
/* compact buttons inside list rows */
[class*="st-key-row_"] .stButton button, [class*="st-key-cat_"] .stButton button, .st-key-panel_account .stButton button { min-height: 42px; padding: 0 18px; font-size: 14.5px; border-radius: 999px; }
/* ghost "back" links */
[class*="st-key-back_"] .stButton button { min-height: 42px; padding: 0 16px 0 40px; border-radius: 999px; background: transparent; position: relative; width: auto; }
[class*="st-key-back_"] .stButton button:hover { background: var(--fill); }
[class*="st-key-back_"] .stButton button::before {
  content: ""; position: absolute; left: 14px; top: 50%; width: 18px; height: 18px; margin-top: -9px;
  background: currentColor;
  -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m12 19-7-7 7-7'/%3E%3Cpath d='M19 12H5'/%3E%3C/svg%3E") center / contain no-repeat;
          mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m12 19-7-7 7-7'/%3E%3Cpath d='M19 12H5'/%3E%3C/svg%3E") center / contain no-repeat;
}
/* refresh pill */
[class*="st-key-refresh_"] .stButton button { min-height: 42px; padding: 0 18px 0 42px; border-radius: 999px; position: relative; }
[class*="st-key-refresh_"] .stButton button::before {
  content: ""; position: absolute; left: 16px; top: 50%; width: 17px; height: 17px; margin-top: -8.5px; background: currentColor;
  -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8'/%3E%3Cpath d='M21 3v5h-5'/%3E%3C/svg%3E") center / contain no-repeat;
          mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8'/%3E%3Cpath d='M21 3v5h-5'/%3E%3C/svg%3E") center / contain no-repeat;
}
/* white buttons on grey panels */
.st-key-panel_account .stButton button, .st-key-panel_profile .stButton button { background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,.08); }
.st-key-panel_account .stButton button:hover, .st-key-panel_profile .stButton button:hover { background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,.14); }
/* white button on black panels */
.st-key-panel_active .stButton button { background: #fff; color: #000; }
.st-key-panel_active .stButton button:hover { background: #E9E9E9; }

/* ==========================================================================
   5. FORM CONTROLS
   ========================================================================== */
[data-testid="stWidgetLabel"] { margin-bottom: 6px; min-height: 0; }
[data-testid="stWidgetLabel"] p, [data-testid="stWidgetLabel"] label { font-size: 13.5px !important; font-weight: 600 !important; color: var(--ink-2) !important; margin: 0 !important; }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { font-size: 13.5px !important; font-weight: 500 !important; color: var(--ink-3) !important; }

/* text input */
[data-testid="stTextInputRootElement"] {
  background: var(--fill) !important; border: 0 !important; border-radius: 12px !important; min-height: 54px;
  box-shadow: inset 0 0 0 2px transparent; transition: background-color .15s ease, box-shadow .15s ease;
}
[data-testid="stTextInputRootElement"]:hover { background: var(--fill-2) !important; }
[data-testid="stTextInputRootElement"]:focus-within { background: #fff !important; box-shadow: inset 0 0 0 2px #000 !important; }
[data-testid="stTextInputRootElement"] div[data-baseweb="base-input"] { background: transparent !important; }
[data-testid="stTextInputRootElement"] input {
  height: 54px; padding: 0 16px !important; font-size: 16px; font-weight: 500; color: #000 !important; -webkit-text-fill-color: #000;
  background: transparent !important;
}
[data-testid="stTextInputRootElement"] input::placeholder { color: #7C7C7C; opacity: 1; font-weight: 450; -webkit-text-fill-color: #7C7C7C; }
[data-testid="stTextInputRootElement"] input:disabled { -webkit-text-fill-color: #6B6B6B; cursor: not-allowed; }
[data-testid="stTextInputRootElement"]:has(input:disabled) { opacity: .7; }
[data-testid="stTextInputRootElement"] input:-webkit-autofill { -webkit-box-shadow: 0 0 0 100px var(--fill) inset; }

/* select box (Streamlit >= 1.5x markup, then the older BaseWeb markup) */
[data-testid="stSelectbox"] [role="group"] {
  background: var(--fill) !important; border: 0 !important; border-radius: 12px !important; min-height: 54px; height: 54px;
  box-shadow: inset 0 0 0 2px transparent; transition: background-color .15s ease, box-shadow .15s ease;
}
[data-testid="stSelectbox"] [role="group"]:hover { background: var(--fill-2) !important; }
[data-testid="stSelectbox"] [role="group"]:focus-within { background: #fff !important; box-shadow: inset 0 0 0 2px #000 !important; }
[data-testid="stSelectbox"] input { height: 100%; padding: 0 16px !important; font-size: 16px; font-weight: 500; color: #000 !important; -webkit-text-fill-color: #000; }
[data-testid="stSelectbox"] input::placeholder { color: #7C7C7C; opacity: 1; font-weight: 450; -webkit-text-fill-color: #7C7C7C; }
[data-testid="stSelectbox"] [role="group"] button { color: var(--ink-3); background: transparent !important; }
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
  background: var(--fill) !important; border: 0 !important; border-radius: 12px !important; min-height: 54px;
  box-shadow: inset 0 0 0 2px transparent;
}
[data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within { background: #fff !important; box-shadow: inset 0 0 0 2px #000 !important; }
[data-testid="stSelectbox"] div[data-baseweb="select"] > div { align-items: center !important; }
[data-testid="stSelectbox"] div[data-baseweb="select"] > div > div:first-child { padding-left: 16px; padding-top: 0; padding-bottom: 0; font-size: 16px; font-weight: 500; align-items: center !important; }

/* dropdown list */
[data-testid="stSelectboxVirtualDropdown"], div[data-baseweb="popover"] > div:has(ul[role="listbox"]) {
  background: #fff !important; border: 1px solid var(--line-2) !important; border-radius: 14px !important;
  box-shadow: 0 16px 48px rgba(0,0,0,.18) !important; overflow: hidden; margin-top: 6px;
}
[role="listbox"] { padding: 6px !important; background: #fff !important; }
[role="listbox"] [role="option"] { border-radius: 9px !important; padding: 11px 12px !important; font-size: 15px; font-weight: 500; color: #000; }
[role="listbox"] [role="option"]:hover, [role="listbox"] [role="option"][data-focused="true"], [role="listbox"] [role="option"][data-hovered="true"] { background: var(--fill) !important; }
[role="listbox"] [role="option"][aria-selected="true"] { background: var(--fill) !important; font-weight: 700; }

/* segmented control (st.radio, horizontal) */
[data-testid="stRadioGroup"], div[role="radiogroup"] {
  display: flex !important; flex-direction: row !important; gap: 4px !important; padding: 4px; width: 100%;
  background: var(--fill); border-radius: 999px; box-sizing: border-box; height: auto; min-height: 50px;
}
[data-testid="stRadioGroup"] > div, div[role="radiogroup"] > label { flex: 1 1 0; min-width: 0; }
div[role="radiogroup"] > label { width: auto !important; }
div[role="radiogroup"] { flex-wrap: nowrap !important; }
label[data-testid="stRadioOption"], label[data-baseweb="radio"] {
  display: flex !important; align-items: center; justify-content: center; width: 100%; height: 42px; margin: 0 !important; padding: 0 !important;
  border-radius: 999px; cursor: pointer; transition: background-color .15s ease, box-shadow .15s ease; box-sizing: border-box;
}
label[data-testid="stRadioOption"] > div { width: 100%; display: flex; align-items: center; justify-content: center; }
label[data-testid="stRadioOption"] > div > div:first-child, label[data-baseweb="radio"] > div:first-child { display: none !important; }
label[data-testid="stRadioOption"] p, label[data-baseweb="radio"] p { margin: 0 !important; font-size: 15px; font-weight: 600; color: var(--ink-3); }
label[data-testid="stRadioOption"]:has(input:checked), label[data-testid="stRadioOption"][data-selected="true"], label[data-baseweb="radio"]:has(input:checked) {
  background: #fff; box-shadow: 0 1px 2px rgba(0,0,0,.14), 0 2px 8px rgba(0,0,0,.06);
}
label[data-testid="stRadioOption"]:has(input:checked) p, label[data-testid="stRadioOption"][data-selected="true"] p, label[data-baseweb="radio"]:has(input:checked) p { color: #000; }
label[data-testid="stRadioOption"]:has(input:focus-visible), label[data-baseweb="radio"]:has(input:focus-visible) { outline: 2px solid var(--blue); outline-offset: 2px; }

/* the pickup-dot / destination-square connector beside the two route inputs */
.st-key-fields_route { position: relative; gap: 10px !important; margin-top: 2px; }
.st-key-fields_route::before {
  content: ""; position: absolute; left: 21px; top: 21px; width: 12px; height: 76px; pointer-events: none; z-index: 5;
  background:
    radial-gradient(circle at 6px 6px, #000 0 5.5px, transparent 6px) 0 0 / 12px 12px no-repeat,
    linear-gradient(#000, #000) 5px 18px / 2px 40px no-repeat,
    linear-gradient(#000, #000) 1px 64px / 10px 10px no-repeat;
}
.st-key-fields_route [data-testid="stSelectbox"] input { padding-left: 46px !important; }
.st-key-fields_route [data-testid="stSelectbox"] div[data-baseweb="select"] > div > div:first-child { padding-left: 46px; }

/* ==========================================================================
   6. SURFACES: panels, list rows, notices
   ========================================================================== */
[class*="st-key-panel_"] > *, .st-key-auth_card > *, .st-key-page > *, .st-key-narrow > *, .st-key-narrow-sm > * { width: 100%; box-sizing: border-box; }
.stack { display: flex; flex-direction: column; gap: 16px; }
[class*="st-key-panel_"] { background: #fff; border: 1px solid var(--line); border-radius: 20px; padding: 24px; box-sizing: border-box; gap: 16px !important; }
.st-key-panel_request { border-color: rgba(0,0,0,.05); box-shadow: 0 8px 32px rgba(0,0,0,.09), 0 2px 8px rgba(0,0,0,.05); padding: 28px; gap: 16px !important; }
.st-key-panel_account { background: var(--fill); border: 0; padding: 18px 20px; border-radius: 18px; }
.st-key-panel_profile { background: var(--fill); border: 0; padding: 20px 22px; border-radius: 18px; }
.st-key-panel_active { background: #000; border: 0; color: #fff; padding: 20px 24px; border-radius: 20px; gap: 14px !important; }
.st-key-panel_shift { padding: 24px 24px 22px; }
.st-key-panel_form { padding: 28px; gap: 18px !important; }

[class*="st-key-row_"] {
  background: #fff; border: 1px solid var(--line); border-radius: 18px; padding: 18px 20px; box-sizing: border-box; gap: 12px !important;
  transition: border-color .15s ease, box-shadow .2s ease;
}
[class*="st-key-row_"]:hover { border-color: var(--fill-3); box-shadow: 0 6px 20px rgba(0,0,0,.06); }
[class*="st-key-cat_"] {
  background: #fff; border: 1.5px solid var(--line); border-radius: 18px; padding: 16px 22px; box-sizing: border-box;
  transition: border-color .15s ease, box-shadow .2s ease;
}
[class*="st-key-cat_"]:hover { border-color: #000; box-shadow: 0 8px 24px rgba(0,0,0,.08); }
[class*="st-key-req_"] { background: #fff; border: 1.5px solid #000; border-radius: 20px; padding: 22px 24px; box-sizing: border-box; gap: 16px !important; }
.st-key-panel_active [data-testid="stMarkdownContainer"] { color: #fff; }

.notice { display: flex; gap: 12px; align-items: flex-start; padding: 14px 16px; border-radius: 14px; font-size: 14.5px; line-height: 21px; font-weight: 500; }
.notice .ic { flex: none; margin-top: 1px; }
.notice b { font-weight: 700; }
.notice--error { background: var(--red-bg); color: var(--red-ink); }
.notice--warn { background: var(--amber-bg); color: var(--amber-ink); }
.notice--info { background: var(--blue-bg); color: var(--blue-ink); }
.notice--success { background: var(--green-bg); color: var(--green-ink); }

.empty { display: flex; flex-direction: column; align-items: flex-start; gap: 4px; padding: 26px 26px 28px; border-radius: 18px; background: var(--fill); }
.empty-ic { width: 46px; height: 46px; border-radius: 50%; background: #fff; display: grid; place-items: center; margin-bottom: 10px; color: #000; }
.empty-t { font-size: 17px; line-height: 24px; font-weight: 700; letter-spacing: -.01em; }
.empty-d { font-size: 14.5px; line-height: 21px; color: var(--ink-3); font-weight: 500; max-width: 44ch; }

[data-testid="stToast"], div[data-baseweb="toast"] { background: #000 !important; color: #fff !important; border-radius: 14px !important; box-shadow: 0 12px 32px rgba(0,0,0,.28) !important; }
[data-testid="stToast"] *, div[data-baseweb="toast"] * { color: #fff !important; font-weight: 600; }

/* ==========================================================================
   7. COMPONENTS
   ========================================================================== */
.greet { display: flex; align-items: flex-end; justify-content: space-between; gap: 14px 24px; flex-wrap: wrap; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.chip { display: inline-flex; align-items: center; gap: 7px; height: 30px; padding: 0 12px; border-radius: 999px; background: var(--fill); color: #000; font-size: 13px; font-weight: 600; white-space: nowrap; line-height: 1; }
.chip .ic { flex: none; }
.chip-dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; flex: none; }
.chip--sm { height: 26px; padding: 0 10px; font-size: 12.5px; }
.chip--plain { background: var(--fill); color: #000; }
.chip--requested { background: var(--amber-bg); color: var(--amber-ink); }
.chip--accepted { background: var(--blue-bg); color: var(--blue-ink); }
.chip--ongoing, .chip--on-trip { background: #000; color: #fff; }
.chip--ongoing .chip-dot, .chip--on-trip .chip-dot { background: #06C167; animation: cb-blink 1.6s ease-in-out infinite; }
.chip--completed, .chip--available { background: var(--green-bg); color: var(--green-ink); }
.chip--available .chip-dot { animation: cb-blink 2s ease-in-out infinite; }
.chip--cancelled, .chip--offline { background: var(--fill); color: var(--ink-3); }
.chip--no-drivers { background: var(--red-bg); color: var(--red-ink); }
.chip--live { background: #000; color: #fff; }
.chip--live .chip-dot { background: #06C167; animation: cb-blink 1.6s ease-in-out infinite; }

.avatar { flex: none; width: var(--s, 44px); height: var(--s, 44px); border-radius: 50%; background: #000; color: #fff; display: inline-grid; place-items: center; font-size: calc(var(--s, 44px) * .38); font-weight: 700; letter-spacing: .01em; line-height: 1; }
.avatar--light { background: #fff; color: #000; }
.plate { display: inline-block; padding: 3px 9px; border: 1.5px solid #000; border-radius: 6px; background: #fff; color: #000; font-size: 12.5px; font-weight: 700; letter-spacing: .08em; line-height: 1.2; white-space: nowrap; }
.stars { display: inline-flex; gap: 2px; vertical-align: middle; }
.star { color: #D4D4D4; display: inline-flex; }
.star.on { color: #000; }

.stops { position: relative; display: flex; flex-direction: column; gap: 14px; min-width: 0; }
.stops::before { content: ""; position: absolute; left: 4px; top: 10px; bottom: 10px; width: 2px; background: #000; border-radius: 2px; }
.stop { position: relative; display: flex; align-items: center; gap: 14px; min-width: 0; font-size: 15.5px; line-height: 20px; font-weight: 600; }
.stop > span:last-child { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.stop-dot, .stop-sq { flex: none; display: block; width: 10px; height: 10px; background: #000; position: relative; z-index: 1; }
.stop-dot { border-radius: 50%; }
.stop-sq { border-radius: 2px; }
.stops--sm { gap: 10px; }
.stops--sm .stop { font-size: 14.5px; }
.on-dark .stops::before, .on-dark .stop-dot, .on-dark .stop-sq { background: #fff; }

.dist { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 13px 16px; border-radius: 12px; background: var(--fill); }
.dist-l { display: flex; align-items: center; gap: 10px; font-size: 14px; font-weight: 600; color: var(--ink-2); }
.dist-v { font-size: 17px; font-weight: 700; letter-spacing: -.01em; font-variant-numeric: tabular-nums; }

.kv { display: flex; flex-direction: column; }
.kv-row { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 13px 0; border-top: 1px solid var(--line-2); font-size: 14.5px; }
.kv-k { color: var(--ink-3); font-weight: 500; }
.kv-v { color: #000; font-weight: 600; text-align: right; }

.trip-meta { display: flex; flex-wrap: wrap; gap: 4px 18px; margin-top: 12px; font-size: 13.5px; color: var(--ink-3); font-weight: 500; line-height: 20px; }
.trip-meta b { color: var(--ink); font-weight: 600; }
.trip-price { text-align: right; display: flex; flex-direction: column; align-items: flex-end; gap: 8px; }
.cat { display: flex; align-items: center; gap: 20px; min-width: 0; }
.cat-ic { flex: none; width: 104px; display: grid; place-items: center; }
.cat-name { font-size: 20px; line-height: 26px; font-weight: 700; letter-spacing: -.015em; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.cat-meta { display: flex; flex-wrap: wrap; gap: 4px 16px; margin-top: 6px; font-size: 13.5px; color: var(--ink-3); font-weight: 500; line-height: 20px; }
.cat-meta span { display: inline-flex; align-items: center; gap: 6px; }
.cat-meta .cat-off { color: var(--red-ink); font-weight: 600; }
.cat-fare { text-align: right; }
.cat-fare .meta { margin-top: 2px; }
.person { display: flex; align-items: center; gap: 14px; min-width: 0; }
.person-name { font-size: 18px; line-height: 24px; font-weight: 700; letter-spacing: -.012em; }
.person-sub { display: flex; flex-wrap: wrap; gap: 2px 16px; margin-top: 3px; font-size: 14px; color: var(--ink-3); font-weight: 500; line-height: 20px; }
.person-sub span { display: inline-flex; align-items: center; gap: 6px; }
.fare-block { text-align: right; }
.fare-block .meta { margin-bottom: 2px; }
.req-top { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.req-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; padding-top: 16px; border-top: 1px solid var(--line-2); }
.req-grid .lbl { margin-bottom: 3px; }
.req-grid .v { font-size: 15.5px; font-weight: 700; letter-spacing: -.005em; line-height: 22px; }
.shift { display: flex; align-items: center; gap: 14px; }
.shift-dot { width: 14px; height: 14px; border-radius: 50%; background: var(--ink-4); flex: none; }
.shift-dot.available { background: #06C167; box-shadow: 0 0 0 6px rgba(6,193,103,.18); }
.shift-dot.on-trip { background: #000; box-shadow: 0 0 0 6px rgba(0,0,0,.12); }
.shift-t { font-size: 24px; line-height: 30px; font-weight: 700; letter-spacing: -.02em; }
.review { margin-top: 6px; font-size: 13.5px; line-height: 20px; color: var(--ink-3); font-weight: 500; max-width: 30ch; }
.rating-box { display: flex; flex-direction: column; align-items: flex-end; gap: 6px; text-align: right; }
.rating-n { font-size: 15px; font-weight: 700; }
.vehicle { display: flex; align-items: center; gap: 14px; }
.vehicle .car { flex: none; }

/* map */
.mapcard { position: relative; border-radius: 20px; overflow: hidden; background: #EEEEEE; box-shadow: inset 0 0 0 1px rgba(0,0,0,.06); }
.rmap { display: block; width: 100%; height: auto; }
.route-draw { stroke-dasharray: 1; stroke-dashoffset: 1; animation: cb-draw 1.9s var(--ease) .25s forwards; }
@keyframes cb-draw { to { stroke-dashoffset: 0; } }
.map-pulse { transform-box: fill-box; transform-origin: center; animation: cb-pulse 1.9s ease-out infinite; }
@keyframes cb-pulse { from { transform: scale(1); opacity: .4; } to { transform: scale(3.4); opacity: 0; } }

/* vehicles */
.car .b { fill: var(--car-b, #000); }
.car .w, .rmap .w { fill: var(--car-w, #DCDCDC); }
.car .t, .rmap .t { fill: var(--car-t, #000); }
.car .h, .rmap .h { fill: var(--car-h, #BDBDBD); }
.rmap .b { fill: var(--car-b, #000); }
.car-shadow { fill: rgba(0,0,0,.13); }
.car-noshadow { display: none; }

/* live ride tracker */
.trk { background: #000; color: #fff; border-radius: 24px; padding: 30px 32px 28px; }
.trk-title { font-size: 30px; line-height: 36px; font-weight: 700; letter-spacing: -.028em; color: #fff; }
.trk-sub { margin-top: 8px; max-width: 48ch; color: #ADADAD; font-size: 15px; line-height: 22px; font-weight: 500; }
.trk-lane { position: relative; height: 44px; margin: 30px 0 4px; }
.trk-car { position: absolute; bottom: 0; left: calc(12.5% + 75% * var(--f, 0)); transform: translateX(-50%); transition: left .6s var(--ease); }
.trk-car .car { --car-b: #fff; --car-w: #000; --car-t: #fff; --car-h: #000; display: block; }
.trk-car .car-shadow { display: none; }
.trk-steps { position: relative; display: grid; grid-template-columns: repeat(4, 1fr); }
.trk-steps::before, .trk-steps::after { content: ""; position: absolute; left: 12.5%; top: 10px; height: 4px; border-radius: 4px; }
.trk-steps::before { right: 12.5%; background: #2C2C2C; }
.trk-steps::after { width: calc(75% * var(--f, 0)); background: #fff; transition: width .6s var(--ease); }
.trk--done .trk-steps::after { background: #06C167; }
.trk-scan { position: absolute; left: 12.5%; top: 10px; width: 25%; height: 4px; border-radius: 4px; overflow: hidden; }
.trk-scan::after { content: ""; position: absolute; inset: 0 auto 0 0; width: 45%; background: linear-gradient(90deg, transparent, rgba(255,255,255,.95), transparent); animation: cb-scan 1.5s ease-in-out infinite; }
@keyframes cb-scan { from { transform: translateX(-100%); } to { transform: translateX(260%); } }
.trk-step { position: relative; z-index: 1; display: flex; flex-direction: column; align-items: center; gap: 12px; text-align: center; padding: 0 4px; }
.trk-node { width: 24px; height: 24px; border-radius: 50%; display: grid; place-items: center; background: #000; box-shadow: inset 0 0 0 3.5px #2C2C2C; color: #000; }
.trk-step.done .trk-node { background: #fff; box-shadow: none; }
.trk--done .trk-step.done .trk-node { background: #06C167; }
.trk-step.now .trk-node { background: #fff; box-shadow: 0 0 0 5px rgba(255,255,255,.2); animation: cb-halo 1.9s ease-out infinite; }
.trk-step.now .trk-node::after { content: ""; width: 8px; height: 8px; border-radius: 50%; background: #000; }
@keyframes cb-halo { 0% { box-shadow: 0 0 0 0 rgba(255,255,255,.45); } 100% { box-shadow: 0 0 0 12px rgba(255,255,255,0); } }
.trk-label { font-size: 14px; line-height: 18px; font-weight: 600; color: #777; }
.trk-step.done .trk-label, .trk-step.now .trk-label { color: #fff; }

/* ==========================================================================
   8. SIGN-IN (split screen)
   ========================================================================== */
.st-key-auth [data-testid="stHorizontalBlock"] { gap: 0 !important; align-items: stretch; }
.st-key-auth [data-testid="stColumn"], .st-key-auth [data-testid="column"] { min-width: 0; }
.st-key-auth [data-testid="stColumn"]:first-child, .st-key-auth [data-testid="column"]:first-child { background: #000; }
.hero { display: flex; flex-direction: column; gap: 28px; min-height: 100vh; box-sizing: border-box; padding: 40px clamp(28px, 4.5vw, 64px) 48px; background: #000; color: #fff; }
.hero-title { margin-top: auto; font-size: clamp(38px, 4.4vw, 62px); line-height: 1.03; font-weight: 700; letter-spacing: -.04em; color: #fff; max-width: 11em; }
.hero-art { border-radius: 24px; overflow: hidden; box-shadow: 0 0 0 1px #262626; margin-top: 4px; }
.st-key-auth_card { width: 100%; max-width: 416px; margin: 0 auto; min-height: 100vh; justify-content: center; padding: 48px 8px; box-sizing: border-box; gap: 18px !important; }
.auth-title { font-size: 30px; line-height: 36px; font-weight: 700; letter-spacing: -.028em; color: #000; margin: 8px 0 4px; }
.auth-sub { margin-top: -4px; font-size: 15px; line-height: 22px; color: var(--ink-3); font-weight: 500; }
.auth-mbrand { display: none; }
.or-rule { display: flex; align-items: center; gap: 14px; color: var(--ink-4); font-size: 13px; font-weight: 600; }
.or-rule::before, .or-rule::after { content: ""; flex: 1; height: 1px; background: var(--line); }
.st-key-auth_alt .stButton button { width: 100%; }

/* ==========================================================================
   9. RESPONSIVE + MOTION
   ========================================================================== */
@media (max-width: 960px) {
  .st-key-auth [data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
  .st-key-auth [data-testid="stColumn"], .st-key-auth [data-testid="column"] { flex: 1 1 100% !important; width: 100% !important; min-width: 100% !important; }
  .st-key-auth [data-testid="stColumn"]:first-child, .st-key-auth [data-testid="column"]:first-child { display: none; }
  .st-key-auth_card { min-height: 100vh; padding: 28px 4px 40px; }
  .auth-mbrand { display: block; margin-bottom: 8px; }
  .st-key-auth_card { padding-left: 20px; padding-right: 20px; }
}
@media (max-width: 760px) {
  .st-key-appnav { display: none !important; }
  .st-key-appbar { height: 60px; }
  .st-key-page { padding: 20px 16px 72px; gap: 20px !important; }
  .h1 { font-size: 28px; line-height: 34px; }
  .h2 { font-size: 23px; line-height: 29px; }
  .money--lg { font-size: 36px; line-height: 40px; }
  .trk { padding: 22px 18px 20px; border-radius: 20px; }
  .trk-title { font-size: 24px; line-height: 30px; }
  .trk-label { font-size: 12px; line-height: 16px; }
  .trk-car .car { width: 72px; height: auto; }
  .req-grid { grid-template-columns: 1fr 1fr; }
  .cat { gap: 12px; }
  .cat-ic { width: 76px; }
  .cat-ic .car { width: 76px; height: auto; }
  .trip-price, .cat-fare, .fare-block, .rating-box { align-items: flex-start; text-align: left; }
  .st-key-panel_request { padding: 22px 18px; }
  .st-key-panel_form { padding: 22px 18px; }
}
@media (max-width: 520px) {
  .st-key-appbar { gap: 8px !important; padding-left: 16px !important; padding-right: 16px !important; }
  .st-key-appbar [data-testid="stPopover"] button { padding: 0 10px 0 6px !important; gap: 6px; }
  .st-key-appbar [data-testid="stPopover"] button [data-testid="stMarkdownContainer"] {
    position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap;
  }
  .brand-name { font-size: 18px; }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: .001ms !important; animation-iteration-count: 1 !important; transition-duration: .001ms !important; }
  .route-draw { stroke-dashoffset: 0; }
}
"""


def inject_css() -> None:
    """Inject the theme once per run (call right after st.set_page_config)."""
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)
