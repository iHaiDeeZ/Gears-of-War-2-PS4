#!/usr/bin/env python3
"""The pkg's icon0.png (512x512) and pic1.png (1920x1080): original art, no game assets (a plain cog wheel and text
over an ember-lit dusk; no logo or emblem of the game). Your own pictures go in sce_sys/local/ (kept out of the
repository), which scripts/build-gow2.sh pkg prefers.

    make-icon.py <sce_sys folder>
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageFont


def font(size):
    for name in ("DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "arialbd.ttf",
                 "C:/Windows/Fonts/arialbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def backdrop(w, h):
    """Ash grey at the top to a deep red ember glow at the bottom, with a soft light behind the centre."""
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    top, low = (22, 22, 26), (92, 14, 12)
    for y in range(h):
        t = (y / max(1, h - 1)) ** 1.8
        d.line([(0, y), (w, y)], fill=tuple(int(top[i] + (low[i] - top[i]) * t) for i in range(3)))
    glow = Image.new("L", (w, h), 0)
    gd = ImageDraw.Draw(glow)
    r = int(min(w, h) * 0.42)
    gd.ellipse([w // 2 - r, int(h * 0.45) - r, w // 2 + r, int(h * 0.45) + r], fill=110)
    glow = glow.filter(ImageFilter.GaussianBlur(min(w, h) // 9))
    img = Image.composite(Image.new("RGB", (w, h), (170, 44, 30)), img, glow)
    return img


def cog(d, cx, cy, r, teeth, fill, hole):
    """A plain cog wheel: a ring of square teeth around a disc, a round hole in the middle."""
    pts = []
    inner, outer = r * 0.80, r
    for k in range(teeth * 4):
        a = 2 * math.pi * k / (teeth * 4) - math.pi / 2
        rr = outer if (k % 4) in (1, 2) else inner
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill)
    h = r * 0.52
    d.ellipse([cx - h, cy - h, cx + h, cy + h], fill=hole)


def centered(d, w, text, y, size, fill, shadow=None):
    f = font(size)
    tw = d.textlength(text, font=f)
    if shadow:
        d.text(((w - tw) / 2 + size // 18 + 2, y + size // 18 + 2), text, font=f, fill=shadow)
    d.text(((w - tw) / 2, y), text, font=f, fill=fill)


def main():
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    img = backdrop(512, 512)
    d = ImageDraw.Draw(img)
    cog(d, 256, 210, 150, 12, (150, 146, 140), (34, 30, 32))
    centered(d, 512, "2", 118, 176, (236, 60, 44), shadow=(0, 0, 0))
    centered(d, 512, "GEARS", 372, 64, (232, 226, 214), shadow=(0, 0, 0))
    centered(d, 512, "PS4", 446, 40, (236, 60, 44), shadow=(0, 0, 0))
    img.save(os.path.join(out, "icon0.png"))
    pic = backdrop(1920, 1080)
    pd = ImageDraw.Draw(pic)
    cog(pd, 1500, 560, 330, 12, (60, 56, 56), (30, 24, 26))
    pic.save(os.path.join(out, "pic1.png"))
    print("wrote", os.path.join(out, "icon0.png"), "and pic1.png")


if __name__ == "__main__":
    main()
