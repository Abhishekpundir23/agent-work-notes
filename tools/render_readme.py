#!/usr/bin/env python3
"""Render the README artwork. Optional development dependency: Pillow >= 12.

Run: python3 tools/render_readme.py
This is illustration tooling, not a dependency of either skill. No fonts are
distributed; use --font, --bold-font and --mono-font to supply local fonts.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets"
WIDTH, HEIGHT, SCALE = 1280, 560, 2
WHITE = "#F3F6FB"
MUTED = "#A5B4C8"
FAINT = "#778BA5"
MINT = "#78F0CB"
LILAC = "#B6A3FF"
AMBER = "#F6C778"
EDGE = "#29374A"


def local_font(candidates: list[str]) -> str | None:
    return next((name for name in candidates if Path(name).is_file()), None)


class Canvas:
    def __init__(self, image: Image.Image, fonts: dict[str, str | None]):
        self.image = image
        self.draw = ImageDraw.Draw(image)
        self.fonts = fonts

    def box(self, bounds, fill=None, outline=None, radius=0, width=1):
        self.draw.rounded_rectangle(
            tuple(round(v * SCALE) for v in bounds),
            radius=round(radius * SCALE), fill=fill, outline=outline,
            width=round(width * SCALE),
        )

    def line(self, points, fill=EDGE, width=1):
        self.draw.line(
            [(round(x * SCALE), round(y * SCALE)) for x, y in points],
            fill=fill, width=round(width * SCALE), joint="curve",
        )

    def dot(self, x, y, radius, color):
        self.draw.ellipse(
            tuple(round(v * SCALE) for v in (x-radius, y-radius, x+radius, y+radius)),
            fill=color,
        )

    def text(self, xy, value, size=20, color=WHITE, face="regular"):
        path = self.fonts[face]
        font = (ImageFont.truetype(path, round(size * SCALE)) if path
                else ImageFont.load_default(size=round(size * SCALE)))
        self.draw.text(tuple(round(v * SCALE) for v in xy), value,
                       font=font, fill=color, anchor="lt")


def backdrop():
    image = Image.new("RGB", (WIDTH, HEIGHT))
    pixels = image.load()
    for y in range(HEIGHT):
        for x in range(WIDTH):
            violet = math.exp(-(((x-1080)/450)**2 + ((y-80)/320)**2))
            green = math.exp(-(((x-500)/520)**2 + ((y-560)/300)**2))
            pixels[x, y] = (int(8 + violet*13), int(13 + violet*8 + green*9),
                            int(22 + violet*28 + green*5))
    return image.resize((WIDTH*SCALE, HEIGHT*SCALE), Image.Resampling.BICUBIC)


def base_art(fonts):
    c = Canvas(backdrop(), fonts)
    for x in range(672, 1260, 32):
        for y in range(32, 540, 32):
            c.dot(x, y, .65, "#253145")
    c.box((1, 1, 1278, 558), outline=EDGE, radius=22)

    # A small, original note-stack mark.
    c.box((56, 43, 87, 74), fill="#13362F", outline="#326554", radius=8)
    for y, end in ((52, 79), (58, 75), (64, 71)):
        c.line([(64, y), (end, y)], fill=MINT, width=2)
    c.text((100, 49), "WORK NOTES", size=19, face="bold")
    c.text((56, 128), "Small brief.", size=76, face="bold")
    c.text((56, 216), "Clearer trail.", size=76, color=MINT, face="bold")
    c.text((59, 327), "Record the useful work.", size=25, color=MUTED)
    c.text((59, 364), "Resume with what matters.", size=25, color=MUTED)

    for x, w, label, accent in ((58, 132, "CODEX", MINT), (202, 210, "CLAUDE CODE", LILAC)):
        c.box((x, 430, x+w, 471), fill="#131E2C", outline=EDGE, radius=20)
        c.dot(x+19, 451, 3, accent)
        c.text((x+32, 443), label, size=15, face="bold")
    c.text((59, 493), "Two independent skills. Install either one.", size=18, color=FAINT)

    c.text((700, 54), "ONE RECORD. TWO VIEWS.", size=16, color=MUTED, face="mono")
    c.box((700, 102, 1222, 350), fill="#101B2A", outline="#34445C", radius=16)
    c.text((724, 124), "RECORDED WORK", size=14, face="mono", color=MUTED)
    c.box((1136, 116, 1203, 142), fill="#20243B", radius=8)
    c.text((1147, 123), "r014", size=14, face="mono", color=LILAC)
    c.line([(724, 157), (1198, 157)])

    for y, kind, content, accent in (
        (176, "CONSTRAINT", "Preserve public API", MINT),
        (233, "DECISION", "Use the required test runner", LILAC),
        (290, "CHECK", "Regression still running", AMBER),
    ):
        c.dot(729, y+19, 4, accent)
        c.text((748, y), kind, size=12, color=FAINT, face="mono")
        c.text((748, y+20), content, size=20)

    c.line([(960, 350), (960, 382), (824, 382), (824, 412)], width=2)
    c.line([(960, 382), (1098, 382), (1098, 412)], width=2)
    for x, title, subtitle, accent in (
        (700, "01  BRIEF", "The next useful step", MINT),
        (974, "02  WORK MAP", "The recorded work trail", LILAC),
    ):
        c.box((x, 412, x+248, 515), fill="#111D2B", outline=EDGE, radius=14)
        c.text((x+20, 435), title, size=16, face="mono", color=accent)
        c.text((x+20, 467), subtitle, size=17, color=MUTED)
    return c.image


def mix(a, b, fraction):
    a, b = a.lstrip("#"), b.lstrip("#")
    values = [round(int(a[i:i+2], 16)*(1-fraction) + int(b[i:i+2], 16)*fraction)
              for i in (0, 2, 4)]
    return "#" + "".join(f"{v:02x}" for v in values)


def along(points, fraction):
    lengths = [math.dist(a, b) for a, b in zip(points, points[1:])]
    distance = fraction * sum(lengths)
    for a, b, length in zip(points, points[1:], lengths):
        if distance <= length:
            t = distance / length
            return a[0] + (b[0]-a[0])*t, a[1] + (b[1]-a[1])*t
        distance -= length
    return points[-1]


def animate(base, fonts, phase):
    c = Canvas(base.copy(), fonts)
    # Only highlights and packets move. All wording stays readable throughout.
    for row, color in enumerate((MINT, LILAC, AMBER)):
        pulse = max(0, math.cos(2*math.pi*(phase-row/3))) ** 6
        c.box((708, 176+row*57, 711, 215+row*57),
              fill=mix("#101B2A", color, pulse*.85), radius=1)

    flow = (phase*2) % 1
    for endpoint, color, left in ((824, MINT, 700), (1098, LILAC, 974)):
        points = [(960, 350), (960, 382), (endpoint, 382), (endpoint, 411)]
        for trail in range(7, -1, -1):
            position = flow-trail*.013
            if position >= 0:
                x, y = along(points, position)
                c.dot(x, y, 2.8 if trail else 4.2,
                      mix("#29374A", color, 1-trail/9))
        arrival = max(0, 1-abs(flow-.91)/.15)
        c.box((left, 412, left+248, 515), outline=mix(EDGE, color, arrival*.7), radius=14)

    return c.image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font")
    parser.add_argument("--bold-font")
    parser.add_argument("--mono-font")
    args = parser.parse_args()
    fonts = {
        "regular": args.font or local_font([
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]),
        "bold": args.bold_font or local_font([
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]),
        "mono": args.mono_font or local_font([
            "/System/Library/Fonts/Menlo.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        ]),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    base = base_art(fonts)
    poster = animate(base, fonts, .44)
    poster.save(OUT / "work-notes-poster.png", optimize=True)
    palette = poster.quantize(colors=128)
    frames = [animate(base, fonts, i/80).quantize(palette=palette, dither=Image.Dither.NONE)
              for i in range(80)]
    frames[0].save(OUT / "work-notes.gif", save_all=True, append_images=frames[1:],
                   duration=80, loop=0, optimize=True, disposal=1)
    for name in ("work-notes.gif", "work-notes-poster.png"):
        print(f"{name}: {(OUT / name).stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
