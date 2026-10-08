#!/usr/bin/env python3
"""Record a 60–90s captioned walkthrough of the local preview site.

Uses Playwright screenshots + ffmpeg (title cards, burn-in captions).
Output: web/public/video/walkthrough.mp4 (+ poster.jpg + walkthrough.vtt)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "web" / "public" / "video"
BASE = os.environ.get("WALKTHROUGH_BASE", "http://127.0.0.1:4173/Breast-ultrasound-lesion-segmentation/")

SCENES = [
    {
        "id": "title",
        "kind": "card",
        "duration": 4,
        "title": "Breast Ultrasound Lesion Segmentation",
        "subtitle": "Research demo · not for clinical use",
        "caption": "Research demo · not for clinical use · Surabhi Fadnavis",
    },
    {
        "id": "home",
        "kind": "page",
        "path": "",
        "duration": 10,
        "caption": "Educational tour and in-browser lesion segmentation on BUSI",
    },
    {
        "id": "demo",
        "kind": "page",
        "path": "demo",
        "duration": 18,
        "caption": "Try the detector — mask overlay and score run fully in your browser",
        "action": "demo_breast",
        "wait_ms": 20000,
    },
    {
        "id": "results",
        "kind": "page",
        "path": "results",
        "duration": 12,
        "caption": "Internal and external metrics from committed results JSON",
    },
    {
        "id": "birads",
        "kind": "page",
        "path": "bi-rads",
        "duration": 8,
        "caption": "A model score is not a BI-RADS category",
    },
    {
        "id": "surgeon",
        "kind": "page",
        "path": "surgeons-view",
        "duration": 8,
        "caption": "Imaging size is not pathologic T-stage or surgical margins",
    },
    {
        "id": "portfolio",
        "kind": "page",
        "path": "portfolio",
        "duration": 8,
        "caption": "Related oncology-AI student research demos",
    },
    {
        "id": "end",
        "kind": "card",
        "duration": 8,
        "title": "How this was built",
        "subtitle": "Code, analysis, and text produced with AI tools (Cursor).\nSurabhi owns research questions and review.",
        "caption": "Built with Cursor AI assistance · not for clinical use",
    },
]


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.check_call(cmd)


def make_card(path: Path, title: str, subtitle: str, w=1280, h=720) -> None:
    from PIL import Image, ImageDraw, ImageFont

    im = Image.new("RGB", (w, h), (41, 115, 115))
    draw = ImageDraw.Draw(im)
    # subtle grid
    for x in range(0, w, 48):
        draw.line([(x, 0), (x, h)], fill=(55, 130, 130), width=1)
    for y in range(0, h, 48):
        draw.line([(0, y), (w, y)], fill=(55, 130, 130), width=1)
    try:
        font_lg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
    except OSError:
        font_lg = ImageFont.load_default()
        font_sm = font_lg
    draw.rectangle([60, 200, w - 60, 520], fill=(255, 255, 255))
    draw.text((90, 240), title, fill=(14, 14, 14), font=font_lg)
    y = 320
    for line in subtitle.split("\n"):
        draw.text((90, y), line, fill=(31, 86, 86), font=font_sm)
        y += 36
    im.save(path, quality=92)


def write_vtt(scenes: list[dict], path: Path) -> None:
    lines = ["WEBVTT", ""]
    t = 0.0
    for s in scenes:
        start = t
        end = t + s["duration"]
        lines.append(f"{fmt_ts(start)} --> {fmt_ts(end)}")
        lines.append(s["caption"])
        lines.append("")
        t = end
    path.write_text("\n".join(lines))


def fmt_ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def capture_pages(tmpdir: Path) -> list[Path]:
    from playwright.sync_api import sync_playwright

    frames: list[Path] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            device_scale_factor=1,
        )
        page = context.new_page()
        for scene in SCENES:
            out = tmpdir / f"{scene['id']}.png"
            if scene["kind"] == "card":
                make_card(out, scene["title"], scene["subtitle"])
            else:
                url = BASE.rstrip("/") + "/" + scene["path"].lstrip("/")
                if scene["path"] == "":
                    url = BASE if BASE.endswith("/") else BASE + "/"
                page.goto(url, wait_until="networkidle", timeout=120_000)
                page.wait_for_timeout(800)
                if scene.get("action") == "demo_breast":
                    try:
                        # CC BY BrEaST thumbnails use alt="BrEaST …"
                        page.locator('img[alt^="BrEaST"]').first.click(timeout=10_000)
                        # Wait for model download + inference (score card or overlay)
                        page.wait_for_timeout(int(scene.get("wait_ms", 15000)))
                        page.locator(".score-card, canvas").first.wait_for(
                            state="visible", timeout=60_000
                        )
                        page.wait_for_timeout(1500)
                    except Exception as e:
                        print("demo action skipped:", e)
                elif scene.get("click"):
                    try:
                        page.locator(scene["click"]).first.click(timeout=5000)
                        page.wait_for_timeout(int(scene.get("wait_ms", 2000)))
                    except Exception as e:
                        print("click skipped:", e)
                # Prefer main content crop
                page.screenshot(path=str(out), full_page=False)
            frames.append(out)
        browser.close()
    return frames


def assemble(frames: list[Path], tmpdir: Path) -> Path:
    # Build concat list with durations
    list_file = tmpdir / "concat.txt"
    parts = []
    for scene, frame in zip(SCENES, frames):
        # ffmpeg concat demuxer: each image shown for duration via -t on intermediate clips
        clip = tmpdir / f"clip_{scene['id']}.mp4"
        # burn caption
        cap = scene["caption"].replace(":", "\\:").replace("'", "\\'")
        vf = (
            f"scale=1280:720:force_original_aspect_ratio=decrease,"
            f"pad=1280:720:(ow-iw)/2:(oh-ih)/2,"
            f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"text='{cap}':fontsize=28:fontcolor=white:borderw=2:bordercolor=black:"
            f"x=(w-text_w)/2:y=h-80"
        )
        run(
            [
                "ffmpeg",
                "-y",
                "-loop",
                "1",
                "-i",
                str(frame),
                "-vf",
                vf,
                "-t",
                str(scene["duration"]),
                "-r",
                "30",
                "-pix_fmt",
                "yuv420p",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "28",
                str(clip),
            ]
        )
        parts.append(clip)

    with list_file.open("w") as f:
        for clip in parts:
            f.write(f"file '{clip}'\n")

    raw = tmpdir / "raw.mp4"
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(raw),
        ]
    )
    return raw


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_vtt(SCENES, OUT_DIR / "walkthrough.vtt")

    with tempfile.TemporaryDirectory(prefix="walkthrough_") as td:
        tmpdir = Path(td)
        print("Capturing against", BASE)
        frames = capture_pages(tmpdir)
        raw = assemble(frames, tmpdir)
        final = OUT_DIR / "walkthrough.mp4"
        # Re-encode for size target
        run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(raw),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-crf",
                "28",
                "-movflags",
                "+faststart",
                "-an",
                str(final),
            ]
        )
        # Poster = home frame or title
        poster_src = frames[1] if len(frames) > 1 else frames[0]
        from PIL import Image

        im = Image.open(poster_src).convert("RGB").resize((1280, 720))
        im.save(OUT_DIR / "walkthrough-poster.jpg", quality=85)

    size = (OUT_DIR / "walkthrough.mp4").stat().st_size
    # duration
    probe = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(OUT_DIR / "walkthrough.mp4"),
        ]
    )
    dur = float(json.loads(probe)["format"]["duration"])
    print(f"Wrote {final} ({size / 1e6:.2f} MB, {dur:.1f}s)")
    if size > 15_000_000:
        print("WARNING: video exceeds 15 MB target")
    if dur < 55 or dur > 95:
        print("WARNING: duration outside 60–90s target band")
    return 0


if __name__ == "__main__":
    sys.exit(main())
