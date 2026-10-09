#!/usr/bin/env python3
"""Generate 1200×630 Open Graph preview using a CC BY BrEaST sample (not BUSI pixels)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "web" / "public" / "samples" / "external" / "breast_03_malignant.png"
OUT = ROOT / "web" / "public" / "og-image.png"


def main() -> None:
    w, h = 1200, 630
    canvas = Image.new("RGB", (w, h), (41, 115, 115))
    draw = ImageDraw.Draw(canvas)

    # Atmosphere: teal grid
    for x in range(0, w, 40):
        draw.line([(x, 0), (x, h)], fill=(55, 130, 130), width=1)
    for y in range(0, h, 40):
        draw.line([(0, y), (w, y)], fill=(55, 130, 130), width=1)

    us = Image.open(SRC).convert("RGB")
    # Full-bleed-ish right panel of ultrasound (CC BY)
    side = us.resize((560, 560), Image.Resampling.LANCZOS)
    canvas.paste(side, (w - 580, (h - 560) // 2))

    # Left copy block
    panel = Image.new("RGBA", (620, 520), (255, 255, 255, 235))
    canvas.paste(panel, (40, 55), panel)
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        font_body = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except OSError:
        font_title = font_body = font_tiny = ImageFont.load_default()

    draw = ImageDraw.Draw(canvas)
    draw.text((70, 90), "Breast Ultrasound", fill=(14, 14, 14), font=font_title)
    draw.text((70, 140), "Lesion Segmentation", fill=(14, 14, 14), font=font_title)
    draw.text((70, 210), "Student research demo · in-browser ONNX", fill=(31, 86, 86), font=font_body)
    draw.text((70, 250), "Not for clinical use", fill=(200, 30, 74), font=font_body)
    draw.text(
        (70, 320),
        "Surabhi Fadnavis · high-school senior, Georgia",
        fill=(92, 107, 107),
        font=font_tiny,
    )
    draw.text(
        (70, 360),
        "Preview image: BrEaST sample (CC BY 4.0) — not BUSI pixels",
        fill=(92, 107, 107),
        font=font_tiny,
    )
    draw.rectangle([70, 420, 280, 470], fill=(41, 115, 115))
    draw.text((90, 432), "Try the demo", fill=(255, 255, 255), font=font_body)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT, optimize=True)
    print(f"Wrote {OUT} {canvas.size}")


if __name__ == "__main__":
    main()
