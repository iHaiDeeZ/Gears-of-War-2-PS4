#!/usr/bin/env python3
"""The README's banner (docs/images/banner.png, 1600x480): a burning dusk over a broken skyline, a big steel gear
wheel in front of it, and the title, in Crema's layout. Original art: nothing from the game - a plain gear wheel drawn
here (not the game's emblems), the title in Lato (the quick menu's font in patches/fonts, SIL Open Font License).

    python3 scripts/make-banner.py
"""
import math
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
W, H = 1600, 480
SKY_TOP, SKY_MID, SKY_LOW = (14, 10, 12), (64, 18, 14), (196, 70, 24)
STEEL_LIGHT, STEEL_DARK = (196, 198, 204), (58, 60, 68)
TEXT_TOP, TEXT_LOW = (236, 238, 242), (150, 154, 164)
CRIMSON = (204, 38, 38)
MUTED = (196, 176, 170)


def font(size, name="Lato-Black.ttf"):
    for path in (os.path.join(ROOT, "patches", "fonts", name), "C:/Windows/Fonts/arialbd.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def sky():
    """Smoke-dark at the top, burning low over the horizon, with a glow where the fires are."""
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    horizon = int(H * 0.78)
    for y in range(H):
        t = y / horizon
        d.line([(0, y), (W, y)], fill=lerp(SKY_TOP, SKY_MID, t / 0.55) if t < 0.55
               else lerp(SKY_MID, SKY_LOW, (t - 0.55) / 0.45))
    glow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(glow).ellipse([W * 0.05, horizon - 150, W * 0.62, horizon + 170], fill=150)
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    img = Image.composite(Image.new("RGB", (W, H), (255, 120, 40)), img, glow)
    # Drifting smoke: soft dark bands.
    smoke = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(smoke)
    rnd = random.Random(2)
    for _ in range(18):
        x, y = rnd.randint(-200, W), rnd.randint(20, int(H * 0.6))
        sd.ellipse([x, y, x + rnd.randint(260, 620), y + rnd.randint(30, 80)], fill=rnd.randint(40, 90))
    smoke = smoke.filter(ImageFilter.GaussianBlur(26))
    return Image.composite(Image.new("RGB", (W, H), (20, 14, 14)), img, smoke), horizon


def skyline(img, horizon):
    """A broken city along the horizon: blocks with jagged, shot-up tops, and a few leaning spires."""
    d = ImageDraw.Draw(img)
    rnd = random.Random(7)
    x = -20
    while x < W:
        w = rnd.randint(40, 120)
        top = horizon - rnd.randint(30, 150)
        pts = [(x, H), (x, top)]
        steps = rnd.randint(2, 5)
        for k in range(1, steps + 1):
            pts.append((x + w * k // steps, top + rnd.randint(-18, 26)))
        pts.append((x + w, H))
        d.polygon(pts, fill=(18, 12, 12))
        # A few lit windows, low and dim.
        for _ in range(rnd.randint(0, 3)):
            wx, wy = x + rnd.randint(6, max(7, w - 12)), rnd.randint(top + 20, horizon + 20)
            d.rectangle([wx, wy, wx + 4, wy + 6], fill=(150, 64, 24))
        x += w - rnd.randint(0, 10)
    for sx in (210, 640, 930):
        d.polygon([(sx, H), (sx + 10, horizon - 210), (sx + 22, horizon - 196), (sx + 30, H)], fill=(16, 10, 10))
    d.rectangle([0, horizon + 34, W, H], fill=(12, 8, 8))


def embers(img):
    d = ImageDraw.Draw(img)
    rnd = random.Random(11)
    for _ in range(140):
        x, y = rnd.randint(0, int(W * 0.75)), rnd.randint(30, H - 40)
        r = rnd.choice((1, 1, 1, 2, 2, 3))
        c = lerp((255, 200, 120), (255, 90, 30), rnd.random())
        d.ellipse([x - r, y - r, x + r, y + r], fill=c)
    return img


def gear(cx, cy, r_out, r_root, teeth, r_hub, spokes):
    """A plain gear wheel as a mask: the toothed rim, a ring of spokes and a hub with a bore."""
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    pts = []
    for i in range(teeth):
        a0 = 2 * math.pi * i / teeth
        for frac, r in ((0.0, r_root), (0.14, r_out), (0.36, r_out), (0.5, r_root)):
            a = a0 + frac * 2 * math.pi / teeth
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    d.polygon(pts, fill=255)
    # The web between rim and hub, cut into windows between the spokes.
    rim = r_root * 0.80
    d.ellipse([cx - rim, cy - rim, cx + rim, cy + rim], fill=0)
    for i in range(spokes):
        a = 2 * math.pi * i / spokes
        half = 0.13
        d.polygon([(cx + r_hub * math.cos(a - half * 1.8), cy + r_hub * math.sin(a - half * 1.8)),
                   (cx + rim * 1.02 * math.cos(a - half), cy + rim * 1.02 * math.sin(a - half)),
                   (cx + rim * 1.02 * math.cos(a + half), cy + rim * 1.02 * math.sin(a + half)),
                   (cx + r_hub * math.cos(a + half * 1.8), cy + r_hub * math.sin(a + half * 1.8))], fill=255)
    d.ellipse([cx - r_hub, cy - r_hub, cx + r_hub, cy + r_hub], fill=255)
    bore = r_hub * 0.42
    d.ellipse([cx - bore, cy - bore, cx + bore, cy + bore], fill=0)
    return mask


def steel(mask, cx, cy, light_angle=-2.3):
    """Brushed steel lit from the upper left, darker away from the light, with a fire-lit lower edge."""
    shade = Image.new("RGB", (W, H))
    sd = ImageDraw.Draw(shade)
    lx, ly = math.cos(light_angle), math.sin(light_angle)
    box = mask.getbbox()
    for y in range(box[1], box[3] + 1):
        for x0 in range(box[0], box[2] + 1, 4):
            dx, dy = (x0 - cx), (y - cy)
            n = math.hypot(dx, dy) or 1.0
            t = 0.5 + 0.5 * ((dx * lx + dy * ly) / n)
            c = lerp(STEEL_DARK, STEEL_LIGHT, t ** 1.4)
            # Fire below: a warm tint on the lower half.
            warm = max(0.0, dy / n) * 0.35
            c = lerp(c, (230, 110, 50), warm)
            sd.line([(x0, y), (x0 + 3, y)], fill=c)
    return shade


def place_gear(img):
    cx, cy = int(W * 0.25), int(H * 0.52)
    mask = gear(cx, cy, 236, 204, 18, 62, 6)
    # A dark rim around the wheel, then the steel, then its glow on the sky.
    halo = mask.filter(ImageFilter.GaussianBlur(22))
    halo = ImageChops.multiply(halo, Image.new("L", (W, H), 120))
    img = Image.composite(Image.new("RGB", (W, H), (255, 96, 36)), img, halo)
    edge = mask.filter(ImageFilter.MaxFilter(7))
    img = Image.composite(Image.new("RGB", (W, H), (10, 8, 8)), img, edge)
    img = Image.composite(steel(mask, cx, cy), img, mask)
    # Bolts round the hub, and a crimson ring inside the rim.
    d = ImageDraw.Draw(img)
    for i in range(6):
        a = 2 * math.pi * (i + 0.5) / 6
        bx, by = cx + 44 * math.cos(a), cy + 44 * math.sin(a)
        d.ellipse([bx - 5, by - 5, bx + 5, by + 5], fill=(40, 40, 46), outline=(170, 172, 180))
    ring = 204 * 0.80
    d.ellipse([cx - ring, cy - ring, cx + ring, cy + ring], outline=CRIMSON, width=3)
    return img


def text_panel(img):
    """The right side darkens towards the title, so the text reads over the sky."""
    shade = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(shade)
    start = int(W * 0.44)
    for x in range(start, W):
        sd.line([(x, 0), (x, H)], fill=int(210 * min(1.0, ((x - start) / (W * 0.2)) ** 1.2)))
    return Image.composite(Image.new("RGB", (W, H), (12, 8, 8)), img, shade)


def gradient_text(img, xy, text, f, top, low, glow=None):
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=f, fill=255)
    box = mask.getbbox()
    if glow:
        halo = mask.filter(ImageFilter.GaussianBlur(14))
        halo = ImageChops.multiply(halo, Image.new("L", img.size, glow[1]))
        img = Image.composite(Image.new("RGB", img.size, glow[0]), img, halo)
    fill = Image.new("RGB", img.size)
    fd = ImageDraw.Draw(fill)
    for y in range(box[1], box[3] + 1):
        fd.line([(box[0], y), (box[2], y)], fill=lerp(top, low, (y - box[1]) / max(1, box[3] - box[1])))
    return Image.composite(fill, img, mask)


def main():
    img, horizon = sky()
    img = embers(img)
    skyline(img, horizon)
    img = place_gear(img)
    img = text_panel(img)
    x = int(W * 0.53)
    img = gradient_text(img, (x, 96), "GEARS OF WAR", font(96), TEXT_TOP, TEXT_LOW, glow=((255, 90, 40), 110))
    img = gradient_text(img, (x + 2, 196), "2", font(118), (255, 96, 80), CRIMSON, glow=((255, 60, 40), 150))
    d = ImageDraw.Draw(img)
    d.text((x + 6, 336), "Xbox 360 recomp  \u00b7  native on PS4", font=font(34, "Lato-Regular.ttf"), fill=MUTED)
    for i in range(540):
        d.point((x + 6 + i, 390), fill=lerp(CRIMSON, (12, 8, 8), (i / 540) ** 0.8))
    out = os.path.join(ROOT, "docs", "images", "banner.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out, optimize=True)
    print("wrote", out)


if __name__ == "__main__":
    main()
