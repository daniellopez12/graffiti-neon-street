#!/usr/bin/env python3
"""Build the Graffiti Neon Street Chrome theme and its Chrome Web Store assets.

Outputs: theme/ (unpacked theme), store/ (icon, screenshots, promo tiles,
preview) and dist/graffiti-neon-street-<version>.zip (Web Store upload).


By default the new-tab image is the supplied artwork (--image, default
source/wall.jpg). Use --random to instead draw a random wall: random letters
(no words), handstyle scribble tags, arrows, drips and spray.
    generate-graffiti-theme.py [--image PATH] [--image-bg #rrggbb]
    generate-graffiti-theme.py --random [seed]
"""
import argparse
import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Chromium never scales theme new-tab images, so the art is kept compact and
# bottom-anchored, and its edges fade into the solid ntp_background colour.
W, H = 2400, 1100
FRAME_W, FRAME_H = 3840, 240
OUT = Path(__file__).resolve().parent
WORK = Path(tempfile.gettempdir()) / "graffiti-neon-street-build"
THEME_ID = "graffiti-neon-street"
THEME_DIR = OUT / "theme"
STORE_DIR = OUT / "store"
DIST_DIR = OUT / "dist"
SOURCE_IMAGE = OUT / "source/wall.jpg"
NAME = "Graffiti Neon Street"
VERSION = "1.0.1"
IMAGE_W, IMAGE_H, FEATHER = 2400, 1200, 110
# Consonant-only letters sampled without replacement can't spell words.
LETTERS = "BKRSTZXWMQVHJ"
WIDTHS = {"M": .92, "W": 1.0, "J": .5, "Z": .62, "S": .6, "T": .6, "V": .68, "X": .68, "K": .7, "H": .74, "Q": .8}

COLORS = {
    "bg": "#2b2f2d",
    "frame": "#0b1f0a",
    # Active tab/toolbar is lifted well above the frame so the selected tab is
    # obvious, while white text on it stays AAA (>= 7:1).
    "toolbar": "#1d6020",
    "tab_text": "#ffffff",
    # Dimmer than the active tab's white text but still AAA on the frame.
    "inactive_text": "#aed9b8",
    "accent": "#39ff88",
    "omnibox": "#061405",
    "texture": ["#39ff88", "#00ff9c", "#9aa39f"],
}


def rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return [int(hex_color[i:i + 2], 16) for i in (0, 2, 4)]


def lum(hex_color):
    def channel(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(v) for v in rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def spray(rng, cx, cy, color, n=160, spread=260, max_r=18, opacity=0.9):
    out = []
    for _ in range(n):
        a = rng.uniform(0, math.tau)
        d = abs(rng.gauss(0, spread / 2.2))
        r = max(1.5, rng.expovariate(1 / (max_r / 3)))
        r = min(r, max_r * (1.2 - min(d / spread, 1)))
        out.append(f'<circle cx="{cx + math.cos(a) * d:.1f}" cy="{cy + math.sin(a) * d:.1f}" r="{max(r, 1.5):.1f}" fill="{color}" opacity="{opacity * rng.uniform(.55, 1):.2f}"/>')
    for _ in range(6):
        a = rng.uniform(0, math.tau)
        length = rng.uniform(spread * .5, spread * 1.3)
        x = cx + math.cos(a) * length
        y = cy + math.sin(a) * length
        out.append(f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{rng.uniform(4, 10):.1f}" ry="{rng.uniform(16, 40):.1f}" fill="{color}" opacity="{opacity:.2f}" transform="rotate({math.degrees(a) + 90:.1f} {x:.1f} {y:.1f})"/>')
    return "\n".join(out)


def sparkle(x, y, s, color="#ffffff", opacity=1):
    p = f"M{x},{y - s} C{x + s * .12},{y - s * .12} {x + s * .12},{y - s * .12} {x + s},{y} C{x + s * .12},{y + s * .12} {x + s * .12},{y + s * .12} {x},{y + s} C{x - s * .12},{y + s * .12} {x - s * .12},{y + s * .12} {x - s},{y} C{x - s * .12},{y - s * .12} {x - s * .12},{y - s * .12} {x},{y - s}Z"
    return f'<path d="{p}" fill="{color}" opacity="{opacity}"/>'


def drips(rng, x0, x1, y, color, count, max_h=420, width=(26, 54)):
    out = []
    for _ in range(count):
        x = rng.uniform(x0, x1)
        w = rng.uniform(*width)
        h = rng.uniform(max_h * .25, max_h)
        out.append(f'<rect x="{x - w / 2:.1f}" y="{y - 30:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{w / 2:.1f}" fill="{color}"/>')
        out.append(f'<circle cx="{x:.1f}" cy="{y - 30 + h:.1f}" r="{w * .62:.1f}" fill="{color}"/>')
    return "\n".join(out)


def piece(word, cx, baseline, size, rng, style):
    advance = size * style.get("advance", .72)
    widths = [size * WIDTHS.get(ch, .66) * style.get("tight", .9) for ch in word]
    total = sum(widths)
    x = cx - total / 2
    letters = []
    jitter = size * .04
    for ch, w in zip(word, widths):
        letters.append((ch, x + w / 2 + rng.uniform(-jitter, jitter), baseline + rng.uniform(-jitter * 1.5, jitter * 1.5), rng.uniform(-7, 7), rng.uniform(.96, 1.08)))
        x += w

    def text(ch, x, y, rot, scale, attrs, dx=0, dy=0):
        return f'<text x="{x + dx:.1f}" y="{y + dy:.1f}" text-anchor="middle" font-family="Noto Sans" font-weight="900" font-size="{size * scale:.1f}" transform="rotate({rot:.1f} {x:.1f} {y:.1f}) skewX({style.get("skew", -10)})" {attrs}>{esc(ch)}</text>'

    out = []
    if style.get("glow"):
        out.append(f'<g filter="url(#{style["glow_filter"]})" opacity=".95">')
        for ch, x, y, rot, scale in letters:
            out.append(text(ch, x, y, rot, scale, f'fill="none" stroke="{style["glow"]}" stroke-width="{style["outline"] * 2.4:.1f}" stroke-linejoin="round"'))
        out.append("</g>")
    for ch, x, y, rot, scale in letters:
        for k in range(style["depth"], 0, -6):
            out.append(text(ch, x, y, rot, scale, f'fill="{style["extrude"]}" stroke="{style["extrude"]}" stroke-width="{style["outline"] * .45:.1f}" stroke-linejoin="round"', k * style["ex"], k * style["ey"]))
    for ch, x, y, rot, scale in letters:
        out.append(text(ch, x, y, rot, scale, f'fill="{style["halo"]}" stroke="{style["halo"]}" stroke-width="{style["outline"] * 1.7:.1f}" stroke-linejoin="round"'))
    for ch, x, y, rot, scale in letters:
        out.append(text(ch, x, y, rot, scale, f'fill="{style["fill"]}" stroke="{style["line"]}" stroke-width="{style["outline"]:.1f}" stroke-linejoin="round" paint-order="stroke"'))
    for i, (ch, x, y, rot, scale) in enumerate(letters):
        cid = f'{style["id"]}-clip-{i}'
        out.append(f'<clipPath id="{cid}">{text(ch, x, y, rot, scale, "")}</clipPath>')
        stripes = []
        for j in range(-4, 7):
            sx = x - size * .7 + j * size * .23
            stripes.append(f'<path d="M{sx:.1f},{y - size:.1f} l{size * .45:.1f},{size * 1.25:.1f}" stroke="{style["shine"]}" stroke-width="{size * .025:.1f}" opacity=".42"/>')
        out.append(f'<g clip-path="url(#{cid})">{"".join(stripes)}</g>')
        out.append(text(ch, x, y, rot, scale, f'fill="none" stroke="{style["shine"]}" stroke-width="{max(5, size / 70):.1f}" opacity=".85"', -size * .018, -size * .022))
    left = letters[0][1] - advance * .45
    right = letters[-1][1] + advance * .45
    out.append(drips(rng, left + advance * .3, right - advance * .3, baseline + size * .02, style["drip"], style.get("drips", 20), max_h=style.get("drip_h", 430), width=(size * .02, size * .045)))
    for _ in range(style.get("sparkles", 8)):
        out.append(sparkle(rng.uniform(left, right), rng.uniform(baseline - size * .9, baseline - size * .1), rng.uniform(42, 110), style["shine"], .95))
    return "\n".join(out)


def grain_filter(fid, opacity=.18, freq=".85"):
    return f'''<filter id="{fid}" x="0" y="0" width="100%" height="100%">
<feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="2" seed="7" result="noise"/>
<feColorMatrix in="noise" type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 {opacity} 0"/>
</filter>'''


def arrows(color, items, width=58):
    out = []
    for x, y, scale, rot in items:
        out.append(f'<g transform="translate({x} {y}) rotate({rot}) scale({scale})"><path d="M0,0 C180,-120 390,-80 520,40 L470,-80 M520,40 L380,70" fill="none" stroke="#050505" stroke-width="{width + 28}" stroke-linecap="round" stroke-linejoin="round"/><path d="M0,0 C180,-120 390,-80 520,40 L470,-80 M520,40 L380,70" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/></g>')
    return "\n".join(out)




def scribble(rng, x, y, size, color, opacity):
    """A handstyle-like tag: varied strokes, loops and an underline, no real letters."""
    d = [f"M{x:.1f},{y:.1f}"]
    cx = x
    for _ in range(rng.randint(3, 6)):
        w = size * rng.uniform(.3, .65)
        up = size * rng.uniform(.5, 1.25)
        kind = rng.random()
        if kind < .3:
            d.append(f"l{w * .15:.1f},{-up:.1f} l{w * .25:.1f},{up * rng.uniform(.6, 1):.1f}")
        elif kind < .55:
            d.append(f"c{w * .9:.1f},{-up:.1f} {-w * .5:.1f},{-up:.1f} {w * .6:.1f},{size * .05:.1f}")
        elif kind < .8:
            d.append(f"c{w * .2:.1f},{-up:.1f} {w * .9:.1f},{-up * .3:.1f} {w * .4:.1f},{up * .15:.1f}")
        else:
            d.append(f"l{w * .5:.1f},{-up * .5:.1f} m{-w * .5:.1f},{-up * .3:.1f} l{w:.1f},0 m{-w * .4:.1f},{up * .8:.1f}")
        cx += w * .6
    swoosh = f'M{x - size * .1:.1f},{y + size * .25:.1f} q{(cx - x) * .6:.1f},{size * rng.uniform(.1, .45):.1f} {(cx - x) * rng.uniform(1, 1.4):.1f},{-size * rng.uniform(0, .35):.1f}'
    rot = rng.uniform(-14, 10)
    sw = max(3, size / rng.uniform(10, 18))
    extra = ""
    if rng.random() < .35:
        extra = f'<circle cx="{cx + size * .3:.1f}" cy="{y - size * .9:.1f}" r="{size * .08:.1f}"/>'
    return (f'<g opacity="{opacity:.2f}" transform="rotate({rot:.1f} {x:.1f} {y:.1f}) skewX({rng.uniform(-22, -4):.0f})" fill="none" stroke="{color}" stroke-width="{sw:.1f}" stroke-linecap="round" stroke-linejoin="round">'
            f'<path d="{" ".join(d)}"/><path d="{swoosh}"/>{extra}</g>')


def brick_wall(rng, base, mortar, jitter):
    out = [f'<rect width="{W}" height="{H}" fill="{mortar}"/>']
    bw, bh, gap = 180, 76, 9
    for row, y in enumerate(range(-10, H + bh, bh + gap)):
        x = 0 if row % 2 else -(bw + gap) / 2
        while x < W + bw:
            v = rng.randint(-jitter, jitter)
            color = "#%02x%02x%02x" % tuple(max(0, min(255, ch + v + rng.randint(-3, 3))) for ch in rgb(base))
            out.append(f'<rect x="{x:.1f}" y="{y}" width="{bw}" height="{bh}" rx="6" fill="{color}"/>')
            x += bw + gap
    return "\n".join(out)


def crown(x, y, s, color):
    return f'<path d="M{x},{y} l{s * .15},{-s * .7} l{s * .2},{s * .4} l{s * .15},{-s * .6} l{s * .15},{s * .6} l{s * .2},{-s * .4} l{s * .15},{s * .7}z" fill="none" stroke="{color}" stroke-width="{s / 12:.1f}" stroke-linejoin="round"/>'


def art(rng):
    main_word = "".join(rng.sample(LETTERS, rng.randint(3, 4)))
    side_word = "".join(rng.sample([c for c in LETTERS if c not in main_word], 2))
    bg = COLORS["bg"]
    defs = grain_filter("grain", .10, ".9") + f'''
<filter id="haze" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="90"/></filter>
<filter id="p-glow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="16"/></filter>
<linearGradient id="p-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#6c7470"/><stop offset=".5" stop-color="#454c48"/><stop offset="1" stop-color="#2a2f2c"/></linearGradient>
<linearGradient id="t-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e9efeb"/><stop offset="1" stop-color="#aeb6b1"/></linearGradient>
<linearGradient id="fade-l" x1="0" x2="1"><stop offset="0" stop-color="{bg}"/><stop offset="1" stop-color="{bg}" stop-opacity="0"/></linearGradient>
<linearGradient id="fade-r" x1="1" x2="0"><stop offset="0" stop-color="{bg}"/><stop offset="1" stop-color="{bg}" stop-opacity="0"/></linearGradient>
<linearGradient id="fade-t" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{bg}"/><stop offset="1" stop-color="{bg}" stop-opacity="0"/></linearGradient>'''
    body = [brick_wall(rng, "#3c423f", "#262a28", 5)]
    hx = [rng.uniform(400, 800), rng.uniform(1600, 2000)]
    body.append(f'<g filter="url(#haze)" opacity=".22"><ellipse cx="1200" cy="900" rx="820" ry="200" fill="#22ff66"/><circle cx="{hx[0]:.0f}" cy="620" r="220" fill="#00c46a"/><circle cx="{hx[1]:.0f}" cy="680" r="240" fill="#39ff14"/></g>')
    for _ in range(34):
        body.append(scribble(rng, rng.uniform(260, 2000), rng.uniform(320, 1060), rng.uniform(40, 110),
                             rng.choice(["#b9c2bd", "#8e9792", "#39ff88", "#d8ffe6", "#0f1210"]), rng.uniform(.25, .6)))
    for _ in range(3):
        body.append(spray(rng, rng.uniform(350, 2050), rng.uniform(450, 1000), rng.choice(["#39ff88", "#00ff9c", "#b9c2bd"]), 150, 190, 12, .55))
    body.append(crown(rng.uniform(1650, 1900), rng.uniform(380, 460), 120, "#39ff88"))
    body.append(piece(side_word, rng.uniform(640, 760), 600, 280, rng, {"id": "t", "advance": .62, "depth": 30, "ex": .9, "ey": .6, "extrude": "#0d6e3a", "halo": "#0f1210", "fill": "url(#t-fill)", "line": "#0f1210", "outline": 16, "shine": "#ffffff", "drip": "#d8ffe6", "drips": 6, "drip_h": 80, "skew": -6, "sparkles": 0}))
    body.append(arrows("#39ff88", [(330, 1020, .55, -18), (1880, 1000, .55, 196), (1980, 640, .4, 150)], 40))
    body.append(piece(main_word, 1280, 900, 450, rng, {"id": "p", "advance": .74, "depth": 44, "ex": .82, "ey": .72, "extrude": "#0b0d0c", "halo": "#121513", "fill": "url(#p-fill)", "line": "#39ff88", "outline": 17, "shine": "#d8ffe6", "drip": "#39ff88", "drips": 14, "drip_h": 110, "skew": -12, "sparkles": 0, "glow": "#22ff66", "glow_filter": "p-glow"}))
    for _ in range(6):
        body.append(sparkle(rng.uniform(700, 1850), rng.uniform(560, 900), rng.uniform(18, 42), "#d8ffe6", .9))
    body.append(f'<rect width="{W}" height="{H}" filter="url(#grain)"/>')
    body.append(f'<rect width="320" height="{H}" fill="url(#fade-l)"/><rect x="{W - 320}" width="320" height="{H}" fill="url(#fade-r)"/><rect width="{W}" height="380" fill="url(#fade-t)"/>')
    return defs, body, main_word, side_word


def image_ntp(src, out, bg):
    """Resize the artwork and feather its edges into the solid new-tab colour."""
    mask = WORK / "ntp-mask.png"
    inset = FEATHER * 2
    run(["magick", "-size", f"{IMAGE_W}x{IMAGE_H}", "xc:black", "-fill", "white", "-draw",
         f"rectangle {inset},{inset} {IMAGE_W - inset},{IMAGE_H - inset}", "-blur", f"0x{FEATHER}", str(mask)])
    run(["magick", str(src), "-colorspace", "sRGB", "-resize", f"{IMAGE_W}x{IMAGE_H}^", "-gravity", "center", "-extent", f"{IMAGE_W}x{IMAGE_H}",
         str(mask), "-alpha", "off", "-compose", "CopyOpacity", "-composite",
         "-background", bg, "-compose", "Over", "-flatten", "-alpha", "off",
         "-strip", "-define", "png:compression-level=9", str(out)])


def frame_svg(rng):
    c = COLORS
    body = [f'<rect width="{FRAME_W}" height="{FRAME_H}" fill="{c["frame"]}"/>']
    for _ in range(30):
        body.append(scribble(rng, rng.uniform(0, FRAME_W), rng.uniform(70, FRAME_H - 30), rng.uniform(30, 60), rng.choice(c["texture"]), .05))
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{FRAME_W}" height="{FRAME_H}" viewBox="0 0 {FRAME_W} {FRAME_H}">{"".join(body)}</svg>'


def manifest(ntp_bg, alignment, description):
    c = COLORS
    colors = {
        "frame": rgb(c["frame"]),
        "frame_inactive": rgb(c["frame"]),
        "frame_incognito": rgb("#1c1f1d"),
        "frame_incognito_inactive": rgb("#1c1f1d"),
        "toolbar": rgb(c["toolbar"]),
        "tab_text": rgb(c["tab_text"]),
        "tab_background_text": rgb(c["inactive_text"]),
        "tab_background_text_inactive": rgb(c["inactive_text"]),
        "background_tab_text": rgb(c["inactive_text"]),
        "bookmark_text": rgb(c["tab_text"]),
        "toolbar_text": rgb(c["tab_text"]),
        "toolbar_button_icon": rgb(c["tab_text"]),
        "omnibox_background": rgb(c["omnibox"]),
        "omnibox_text": rgb(c["tab_text"]),
        "ntp_background": rgb(ntp_bg),
        "ntp_text": rgb(c["tab_text"]),
        "ntp_link": rgb(c["accent"]),
        "ntp_header": rgb(c["toolbar"]),
        "button_background": rgb(c["toolbar"]),
    }
    return {
        "manifest_version": 3,
        "name": NAME,
        "version": VERSION,
        "description": description,
        "icons": {"16": "icons/icon16.png", "48": "icons/icon48.png", "128": "icons/icon128.png"},
        "theme": {
            "images": {
                "theme_frame": "images/frame.png",
                "theme_frame_inactive": "images/frame.png",
                "theme_ntp_background": "images/ntp.png",
            },
            "colors": colors,
            "tints": {"buttons": [-1, -1, -1]},
            "properties": {"ntp_background_alignment": alignment, "ntp_background_repeat": "no-repeat"},
        },
    }


def run(cmd):
    subprocess.run(cmd, check=True)


def frame_luma_ok(path, text):
    stats = subprocess.check_output(["magick", str(path), "-colorspace", "RGB", "-format", "%[fx:maxima.r] %[fx:maxima.g] %[fx:maxima.b]", "info:"], text=True).split()
    r, g, b = [float(v) for v in stats]
    max_lum = .2126 * r + .7152 * g + .0722 * b
    return (lum(text) + .05) / (max_lum + .05)


def screen_preview(ntp, name, vw, vh, bg, gravity):
    """Simulate the new-tab page: the unscaled image placed on the solid ntp colour."""
    out = WORK / f"{THEME_ID}-{name}.png"
    run(["magick", "-size", f"{vw}x{vh}", f"xc:{bg}", str(ntp), "-gravity", gravity, "-composite", "-resize", "1600x", str(out)])
    return out


def browser_mock(ntp, out, width, height):
    """A mock browser window (tabs, toolbar, new-tab page) using the theme colours."""
    c = COLORS
    scale = width / 1280
    ntp_view = WORK / "mock-ntp.png"
    bg = json.loads((THEME_DIR / "manifest.json").read_text())["theme"]["colors"]["ntp_background"]
    run(["magick", "-size", "1920x1080", "xc:#%02x%02x%02x" % tuple(bg), str(ntp), "-gravity", "center", "-composite", str(ntp_view)])
    mock = WORK / "mock.svg"
    mock.write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="800" viewBox="0 0 1280 800">
<image href="{ntp_view}" x="0" y="80" width="1280" height="720" preserveAspectRatio="xMidYMid slice"/>
<image href="{THEME_DIR / "images/frame.png"}" x="0" y="0" width="1920" height="120" preserveAspectRatio="none"/>
<path d="M14,40 L26,12 Q30,6 38,6 H232 Q240,6 244,12 L256,40Z" fill="{c["toolbar"]}"/>
<text x="42" y="30" font-family="Liberation Sans" font-size="14" font-weight="700" fill="{c["tab_text"]}">New Tab</text>
<text x="290" y="30" font-family="Liberation Sans" font-size="14" fill="{c["inactive_text"]}">Street Art Gallery</text>
<text x="520" y="30" font-family="Liberation Sans" font-size="14" fill="{c["inactive_text"]}">Music</text>
<rect x="0" y="40" width="1280" height="40" fill="{c["toolbar"]}"/>
<text x="16" y="67" font-family="Noto Sans Symbols 2" font-size="19" fill="{c["tab_text"]}">← → ↻</text>
<rect x="120" y="46" width="1040" height="28" rx="14" fill="{c["omnibox"]}"/>
<text x="140" y="65" font-family="Liberation Sans" font-size="14" fill="{c["tab_text"]}">Search Google or type a URL</text>
<rect x="0" y="80" width="1280" height="1" fill="#000" opacity=".4"/>
</svg>''')
    run(["rsvg-convert", "-w", str(width), "-h", str(height), str(mock), "-o", str(out)])
    run(["magick", str(out), "-alpha", "off", str(out)])


def store_assets(src, theme_dir, ntp):
    icons = theme_dir / "icons"
    icons.mkdir(exist_ok=True)
    crop = WORK / "icon-crop.png"
    # Square crop of the artwork's lightning bolt + arrow corner.
    run(["magick", str(src), "-colorspace", "sRGB", "-gravity", "northwest", "-crop", "47%x94%+0+0", "+repage",
         "-gravity", "center", "-extent", "1:1", "-resize", "512x512!", crop.as_posix()])
    mask = WORK / "icon-mask.png"
    run(["magick", "-size", "96x96", "xc:black", "-fill", "white", "-draw", "roundrectangle 0,0 95,95 18,18", str(mask)])
    # Web Store icons: 96x96 artwork centred in 128x128 with transparent padding.
    run(["magick", str(crop), "-resize", "96x96", str(mask), "-alpha", "off", "-compose", "CopyOpacity", "-composite",
         "-background", "none", "-compose", "Over", "-gravity", "center", "-extent", "128x128", str(icons / "icon128.png")])
    for size in (48, 16):
        run(["magick", str(crop), "-resize", f"{size}x{size}", str(icons / f"icon{size}.png")])
    shutil.copy2(icons / "icon128.png", STORE_DIR / "icon-128.png")
    browser_mock(ntp, STORE_DIR / "screenshot-1280x800.png", 1280, 800)
    for name, w, h, pt in (("promo-small-440x280.png", 440, 280, 38), ("promo-marquee-1400x560.png", 1400, 560, 96)):
        run(["magick", str(src), "-colorspace", "sRGB", "-resize", f"{w}x{h}^", "-gravity", "center", "-extent", f"{w}x{h}",
             "(", "-size", f"{w}x{int(h * .34)}", f"xc:{COLORS['toolbar']}", "-alpha", "set", "-channel", "A", "-evaluate", "set", "88%", "+channel", ")",
             "-gravity", "south", "-composite",
             "-font", "Liberation-Sans-Bold", "-pointsize", str(pt), "-fill", "#ffffff", "-annotate", f"+0+{int(h * .09)}", NAME,
             "-alpha", "off", str(STORE_DIR / name)])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--random", nargs="?", const=-1, type=int, metavar="SEED", help="draw a random wall instead of using --image")
    ap.add_argument("--image", type=Path, default=SOURCE_IMAGE, help="artwork for the new-tab page")
    ap.add_argument("--image-bg", default="#061405", help="solid colour the artwork edges fade into")
    args = ap.parse_args()
    seed = args.random if args.random not in (None, -1) else random.SystemRandom().randrange(10**6)
    rng = random.Random(seed)
    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)
    theme_dir = THEME_DIR
    if theme_dir.exists():
        shutil.rmtree(theme_dir)
    (theme_dir / "images").mkdir(parents=True)
    ntp = theme_dir / "images/ntp.png"
    info = {}

    if args.random is None:
        ntp_bg, alignment = args.image_bg, "center"
        description = "Dark-mode street-art theme: neon green and pink graffiti wall with deep-green, AAA-contrast tabs and toolbar."
        image_ntp(args.image, ntp, ntp_bg)
        info["image"] = str(args.image)
    else:
        ntp_bg, alignment = COLORS["bg"], "bottom"
        description = "Grey brick wall with random neon-green graffiti that blends into any screen size."
        defs, body, main_word, side_word = art(rng)
        art_svg = WORK / f"{THEME_ID}.svg"
        art_svg.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><defs>{defs}</defs>{"".join(body)}</svg>')
        run(["rsvg-convert", "-w", str(W), "-h", str(H), str(art_svg), "-o", str(ntp)])
        run(["magick", str(ntp), "-strip", "-define", "png:compression-level=9", str(ntp)])
        info.update(seed=seed, letters=[main_word, side_word])

    frame_file = WORK / f"{THEME_ID}-frame.svg"
    frame_file.write_text(frame_svg(rng))
    frame = theme_dir / "images/frame.png"
    run(["rsvg-convert", "-w", str(FRAME_W), "-h", str(FRAME_H), str(frame_file), "-o", str(frame)])
    (theme_dir / "manifest.json").write_text(json.dumps(manifest(ntp_bg, alignment, description), indent=2) + "\n")

    c = COLORS
    checks = {
        "active_tab_text_on_toolbar": contrast(c["tab_text"], c["toolbar"]),
        "inactive_tab_text_on_textured_frame_worst_case": frame_luma_ok(frame, c["inactive_text"]),
        "address_text_on_omnibox": contrast(c["tab_text"], c["omnibox"]),
    }
    assert min(checks.values()) >= 7, checks
    checks["active_tab_vs_frame"] = contrast(c["toolbar"], c["frame"])
    assert checks["active_tab_vs_frame"] >= 2, checks
    gravity = "center" if alignment == "center" else "south"
    laptop = screen_preview(ntp, "laptop-1920", 1920, 960, ntp_bg, gravity)
    big = screen_preview(ntp, "43in-3840", 3840, 2040, ntp_bg, gravity)
    STORE_DIR.mkdir(exist_ok=True)
    run(["magick", str(laptop), str(big), "-background", "#111", "-splice", "0x20", "-append", "-quality", "85", str(STORE_DIR / "preview-laptop-and-43in.jpg")])
    store_assets(args.image if args.random is None else ntp, theme_dir, ntp)
    zip_path = DIST_DIR / f"{THEME_ID}-{VERSION}.zip"
    DIST_DIR.mkdir(exist_ok=True)
    zip_path.unlink(missing_ok=True)
    subprocess.run(["zip", "-q", "-r", "-X", str(zip_path), "."], cwd=theme_dir, check=True)
    info["zip"] = str(zip_path)
    info["contrast"] = {k: round(v, 2) for k, v in checks.items()}
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
