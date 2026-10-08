#!/usr/bin/env python3
"""Record a 60–90s captioned walkthrough with real rendered site frames.

Uses Playwright (wait for networkidle + visible content), then ffmpeg.
Also writes a contact sheet (one frame every 5s) and refuses blank frames.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "web" / "public" / "video"
CONTACT = Path("/opt/cursor/artifacts/screenshots/phase3b-video-contact.png")
BASE = os.environ.get("WALKTHROUGH_BASE", "http://127.0.0.1:4173/")

CREDIT = "Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (Cursor)."

# Total target ~80s
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
        "path": "/",
        "duration": 6,
        "wait_for": "h1",
        "caption": "Home — educational tour and in-browser lesion segmentation",
    },
    {
        "id": "demo_gallery",
        "kind": "page",
        "path": "/demo",
        "duration": 7,
        "wait_for": ".gallery-grid",
        "scroll": ".gallery-grid",
        "caption": "Demo gallery — BUSI samples and CC BY BrEaST images",
    },
    {
        "id": "demo_overlay",
        "kind": "page",
        "path": "/demo",
        "duration": 12,
        "action": "run_demo",
        "wait_for": ".score-card",
        "caption": "Mask overlay and benign vs malignant score — fully in the browser",
    },
    {
        "id": "demo_controls",
        "kind": "page",
        "path": "/demo",
        "duration": 8,
        "action": "demo_controls",
        "wait_for": ".score-card",
        "caption": "Expert compare, threshold sliders, and research measurements",
    },
    {
        "id": "results_charts",
        "kind": "page",
        "path": "/results",
        "duration": 8,
        "wait_for": "h1",
        "scroll": ".charts-grid, table, .section-title",
        "caption": "Results — Dice, ROC, and calibration from committed JSON",
    },
    {
        "id": "results_external",
        "kind": "page",
        "path": "/results",
        "duration": 7,
        "wait_for": "#external-validation, h1",
        "scroll": "#external-validation",
        "caption": "External validation on BUS-BRA and BrEaST",
    },
    {
        "id": "mistakes",
        "kind": "page",
        "path": "/mistakes",
        "duration": 6,
        "wait_for": "h1",
        "caption": "Mistakes explorer — outline-only silhouettes for hard cases",
    },
    {
        "id": "birads",
        "kind": "page",
        "path": "/bi-rads",
        "duration": 6,
        "wait_for": "h1",
        "caption": "BI-RADS context — a model score is not a BI-RADS category",
    },
    {
        "id": "surgeon",
        "kind": "page",
        "path": "/surgeons-view",
        "duration": 6,
        "wait_for": "h1",
        "scroll": ".example-grid",
        "caption": "Surgeon's view — imaging size is not pathologic T-stage",
    },
    {
        "id": "portfolio",
        "kind": "page",
        "path": "/portfolio",
        "duration": 5,
        "wait_for": "h1",
        "caption": "Portfolio — related oncology-AI student research demos",
    },
    {
        "id": "end",
        "kind": "card",
        "duration": 7,
        "title": "How this was built",
        "subtitle": CREDIT,
        "caption": CREDIT,
    },
]


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd[:8]), "..." if len(cmd) > 8 else "")
    subprocess.check_call(cmd)


def make_card(path: Path, title: str, subtitle: str, w=1280, h=720) -> None:
    from PIL import Image, ImageDraw, ImageFont

    im = Image.new("RGB", (w, h), (41, 115, 115))
    draw = ImageDraw.Draw(im)
    for x in range(0, w, 48):
        draw.line([(x, 0), (x, h)], fill=(55, 130, 130), width=1)
    for y in range(0, h, 48):
        draw.line([(0, y), (w, y)], fill=(55, 130, 130), width=1)
    font_lg = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
    font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    draw.rectangle([50, 160, w - 50, 560], fill=(255, 255, 255))
    draw.text((80, 200), title, fill=(14, 14, 14), font=font_lg)
    y = 270
    # wrap subtitle
    words = subtitle.split()
    line = ""
    for word in words:
        trial = (line + " " + word).strip()
        if font_sm.getlength(trial) > w - 180:
            draw.text((80, y), line, fill=(31, 86, 86), font=font_sm)
            y += 30
            line = word
        else:
            line = trial
    if line:
        draw.text((80, y), line, fill=(31, 86, 86), font=font_sm)
    im.save(path, quality=92)


def is_blank(path: Path, thresh: float = 0.97) -> bool:
    from PIL import Image
    import numpy as np

    im = Image.open(path).convert("RGB").resize((160, 90))
    arr = np.asarray(im).astype("float32")
    # Nearly all pixels very light
    white = (arr > 245).all(axis=2).mean()
    # Or nearly uniform
    std = arr.std()
    return white >= thresh or std < 8.0


def write_vtt(scenes: list[dict], path: Path) -> None:
    lines = ["WEBVTT", ""]
    t = 0.0
    for s in scenes:
        start, end = t, t + s["duration"]
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


def wait_visible(page, selector: str, timeout: int = 60_000) -> None:
    # Allow comma-separated alternatives
    last = None
    for part in selector.split(","):
        part = part.strip()
        try:
            page.locator(part).first.wait_for(state="visible", timeout=timeout)
            return
        except Exception as e:
            last = e
    if last:
        raise last


def capture_pages(tmpdir: Path) -> list[Path]:
    from playwright.sync_api import sync_playwright

    frames: list[Path] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 720}, device_scale_factor=1)
        page = context.new_page()
        page.set_default_timeout(90_000)

        # Warm home once
        page.goto(BASE, wait_until="networkidle")
        wait_visible(page, "h1")

        demo_ready = False
        for scene in SCENES:
            out = tmpdir / f"{scene['id']}.png"
            if scene["kind"] == "card":
                make_card(out, scene["title"], scene["subtitle"])
            else:
                url = BASE.rstrip("/") + scene["path"]
                page.goto(url, wait_until="networkidle")
                wait_visible(page, scene.get("wait_for", "h1"))
                page.wait_for_timeout(400)

                if scene.get("action") == "run_demo":
                    # Click first BrEaST sample
                    page.locator('img[alt^="BrEaST"]').first.click()
                    # Wait for model + score
                    wait_visible(page, ".score-card", timeout=120_000)
                    page.locator("canvas").first.wait_for(state="visible", timeout=60_000)
                    page.wait_for_timeout(1500)
                    demo_ready = True
                elif scene.get("action") == "demo_controls":
                    if not demo_ready:
                        page.locator('img[alt^="BrEaST"]').first.click()
                        wait_visible(page, ".score-card", timeout=120_000)
                        demo_ready = True
                    # Expert toggle if present
                    try:
                        page.get_by_role("button", name="Expert").click(timeout=3000)
                        page.wait_for_timeout(600)
                    except Exception:
                        pass
                    try:
                        page.get_by_role("button", name="Both").click(timeout=2000)
                        page.wait_for_timeout(400)
                    except Exception:
                        pass
                    # Nudge sliders
                    for label in ["overlay-opacity", "Mask threshold", "Class threshold"]:
                        try:
                            page.locator("input[type=range]").nth(0).evaluate(
                                "el => { el.value = 0.55; el.dispatchEvent(new Event('input', {bubbles:true})); el.dispatchEvent(new Event('change', {bubbles:true})); }"
                            )
                            break
                        except Exception:
                            pass
                    # Uncertainty checkbox
                    try:
                        page.get_by_text("Estimate uncertainty", exact=False).click(timeout=3000)
                        page.wait_for_timeout(8000)
                    except Exception as e:
                        print("uncertainty skipped:", e)
                    # Scroll to controls / measurements
                    try:
                        page.locator(".measure-card, .opacity-control").first.scroll_into_view_if_needed()
                    except Exception:
                        pass
                    page.wait_for_timeout(800)

                if scene.get("scroll"):
                    for part in scene["scroll"].split(","):
                        part = part.strip()
                        try:
                            page.locator(part).first.scroll_into_view_if_needed(timeout=3000)
                            page.wait_for_timeout(500)
                            break
                        except Exception:
                            continue

                # Smooth scroll a bit for dynamism
                page.evaluate("window.scrollBy({top: 120, left: 0, behavior: 'instant'})")
                page.wait_for_timeout(300)
                page.screenshot(path=str(out), full_page=False)

                if is_blank(out):
                    raise SystemExit(f"Blank frame captured for scene {scene['id']}: {out}")

            frames.append(out)
            print("captured", scene["id"], out.stat().st_size)
        browser.close()
    return frames


def assemble(frames: list[Path], tmpdir: Path) -> Path:
    parts = []
    for scene, frame in zip(SCENES, frames):
        clip = tmpdir / f"clip_{scene['id']}.mp4"
        cap = scene["caption"].replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        # Escape for drawtext
        vf = (
            "scale=1280:720:force_original_aspect_ratio=decrease,"
            "pad=1280:720:(ow-iw)/2:(oh-ih)/2,"
            "drawbox=x=0:y=ih-90:w=iw:h=90:color=black@0.55:t=fill,"
            f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
            f"text='{cap}':fontsize=22:fontcolor=white:"
            f"x=(w-text_w)/2:y=h-58"
        )
        run(
            [
                "ffmpeg", "-y", "-loop", "1", "-i", str(frame),
                "-vf", vf,
                "-t", str(scene["duration"]),
                "-r", "30",
                "-pix_fmt", "yuv420p",
                "-c:v", "libx264",
                "-preset", "medium",
                "-crf", "23",
                str(clip),
            ]
        )
        parts.append(clip)

    list_file = tmpdir / "concat.txt"
    with list_file.open("w") as f:
        for clip in parts:
            f.write(f"file '{clip}'\n")
    raw = tmpdir / "raw.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(raw)])
    return raw


def contact_sheet(video: Path, out: Path) -> None:
    from PIL import Image
    import numpy as np

    # Extract one frame every 5s
    probe = json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(video)]
        )
    )
    dur = float(probe["format"]["duration"])
    times = list(range(0, int(dur), 5))
    if times[-1] != int(dur) - 1:
        times.append(max(0, int(dur) - 1))

    thumbs = []
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for i, t in enumerate(times):
            fp = td / f"f{i:02d}.png"
            run(
                [
                    "ffmpeg", "-y", "-ss", str(t), "-i", str(video),
                    "-frames:v", "1", "-q:v", "2", str(fp),
                ]
            )
            if is_blank(fp):
                # Allow title/end cards which are intentional white panels on teal —
                # but reject pure white full frames from failed page captures.
                from PIL import Image as I
                import numpy as np

                arr = np.asarray(I.open(fp).convert("RGB"))
                # teal title cards have mean G around 115 in bg — fail only if almost all white
                if (arr > 250).all(axis=2).mean() > 0.92:
                    raise SystemExit(f"Contact sheet frame at t={t}s is blank white")
            thumbs.append(Image.open(fp).convert("RGB").resize((320, 180)))

    cols = 4
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * 320, rows * 180), (255, 255, 255))
    for i, th in enumerate(thumbs):
        sheet.paste(th, ((i % cols) * 320, (i // cols) * 180))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    print(f"Wrote contact sheet {out} ({len(thumbs)} frames)")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    total = sum(s["duration"] for s in SCENES)
    print(f"Planned duration {total}s against {BASE}")
    write_vtt(SCENES, OUT_DIR / "walkthrough.vtt")

    with tempfile.TemporaryDirectory(prefix="walkthrough_") as td:
        tmpdir = Path(td)
        frames = capture_pages(tmpdir)
        raw = assemble(frames, tmpdir)
        final = OUT_DIR / "walkthrough.mp4"
        run(
            [
                "ffmpeg", "-y", "-i", str(raw),
                "-c:v", "libx264", "-pix_fmt", "yuv420p",
                "-crf", "23", "-movflags", "+faststart", "-an",
                str(final),
            ]
        )
        # Poster from demo_overlay frame (real content) with duration label
        from PIL import Image, ImageDraw, ImageFont

        demo = next(f for s, f in zip(SCENES, frames) if s["id"] == "demo_overlay")
        poster = Image.open(demo).convert("RGB").resize((1280, 720))
        draw = ImageDraw.Draw(poster)
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
        draw.rectangle([0, 620, 1280, 720], fill=(41, 115, 115))
        draw.text((40, 650), f"Site walkthrough · {total}s · research demo only", fill=(255, 255, 255), font=font)
        poster.save(OUT_DIR / "walkthrough-poster.jpg", quality=88)

        contact_sheet(final, CONTACT)

    size = final.stat().st_size
    probe = json.loads(
        subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration,bit_rate", "-of", "json", str(final)]
        )
    )
    dur = float(probe["format"]["duration"])
    br = int(probe["format"].get("bit_rate") or 0)
    print(f"Wrote {final} ({size/1e6:.2f} MB, {dur:.1f}s, bitrate={br})")
    if size > 15_000_000:
        raise SystemExit("Video exceeds 15 MB")
    if dur < 55 or dur > 95:
        raise SystemExit(f"Duration {dur} outside 60–90s")
    if br and br < 100_000:
        raise SystemExit(f"Bitrate too low ({br}) — captures likely blank")
    return 0


if __name__ == "__main__":
    sys.exit(main())
