"""
ThumbnailEngine — Generates YouTube thumbnails with Pillow.

Design: Dark gradient, bold title, NacArtha branding, decorative chart line.
Output: 1280×720 JPEG (YouTube recommended size).
"""
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("thumbnail_engine")

ASSETS   = Path(__file__).parent.parent / "assets"
FONT_PATH = ASSETS / "font.ttf"


class ThumbnailEngine:

    def generate(self, title: str, lang: str, out_path: Path) -> Path:
        W, H = 1280, 720
        img  = Image.new("RGB", (W, H))
        draw = ImageDraw.Draw(img)

        # Background: dark gradient (deep navy → dark teal)
        for y in range(H):
            t = y / H
            r = int(6  + 8  * t)
            g = int(6  + 14 * t)
            b = int(22 + 28 * t)
            draw.line([(0, y), (W, y)], fill=(r, g, b))

        # Subtle grid lines
        for x in range(0, W, 80):
            draw.line([(x, 0), (x, H)], fill=(255, 255, 255, 6))
        for y in range(0, H, 80):
            draw.line([(0, y), (W, y)], fill=(255, 255, 255, 6))

        # Left accent bar
        draw.rectangle([0, 0, 8, H], fill=(0, 212, 255))

        # Decorative chart (right side)
        _draw_chart(draw, W, H)

        # NacArtha logo — top left
        logo_f = _font(42)
        draw.text((26, 28), "NACARTHA", fill=(0, 212, 255), font=logo_f)
        sub_f  = _font(22)
        draw.text((28, 78), "AI · Finance · Truth", fill=(130, 170, 190), font=sub_f)

        # Language badge — top right (use ASCII so DejaVu Sans renders it correctly)
        if lang != "en":
            badge = "HINDI" if lang == "hi" else "TELUGU"
            bf    = _font(28)
            draw.rectangle([W - 130, 22, W - 18, 68], fill=(0, 212, 255))
            bb  = draw.textbbox((0, 0), badge, font=bf)
            bx  = W - 130 + (112 - (bb[2] - bb[0])) // 2
            draw.text((bx, 32), badge, fill=(0, 20, 40), font=bf)

        # Main title — centered vertically, bold white
        tf    = _font(76)
        lines = _wrap(title, draw, tf, W - 80)
        if len(lines) > 2:
            tf    = _font(60)
            lines = _wrap(title, draw, tf, W - 80)

        lh      = draw.textbbox((0, 0), "Ag", font=tf)[3] + 12
        total_h = lh * len(lines)
        y       = (H - total_h) // 2 + 30

        for line in lines:
            bb = draw.textbbox((0, 0), line, font=tf)
            lw = bb[2] - bb[0]
            x  = (W - lw) // 2
            # Drop shadow
            draw.text((x + 3, y + 3), line, fill=(0, 0, 0, 160), font=tf)
            draw.text((x,     y    ), line, fill=(255, 255, 255), font=tf)
            y += lh

        # Bottom bar
        draw.rectangle([0, H - 52, W, H], fill=(0, 18, 36))
        bar_f = _font(24)
        draw.text((26, H - 40),
                  "nacarthaai  ·  Daily AI Finance Analysis  ·  Subscribe",
                  fill=(0, 212, 255), font=bar_f)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(out_path), "JPEG", quality=95)
        log.info(f"Thumbnail → {out_path.name}")
        return out_path


def _draw_chart(draw: ImageDraw.Draw, W: int, H: int):
    import random
    rng    = random.Random(7)
    points = []
    x0, y0 = W - 320, H // 2 + 40
    for i in range(22):
        x = x0 + i * 14
        y = y0 + rng.randint(-70, 70)
        points.append((x, y))
    for i in range(len(points) - 1):
        going_up = points[i + 1][1] < points[i][1]
        col = (0, 220, 100, 55) if going_up else (220, 60, 60, 55)
        draw.line([points[i], points[i + 1]], fill=col, width=3)


def _font(size: int = 44):
    for p in [str(FONT_PATH),
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/System/Library/Fonts/Helvetica.ttc"]:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _wrap(text: str, draw: ImageDraw.Draw, font, max_w: int) -> list:
    words, lines, current = text.split(), [], []
    for word in words:
        test = " ".join(current + [word])
        if draw.textbbox((0, 0), test, font=font)[2] <= max_w:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return lines or [text]
