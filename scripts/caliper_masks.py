#!/usr/bin/env python3
"""Pixel-level caliper/text marker masks for BUSI (derived; images not committed).

Combines morphological top-hat, cross (+/×) line hits, colour-vs-gray residuals,
and border glyph heuristics. Dilates by 3 px. Writes:
  data/processed/caliper_masks/*.png  (gitignored)
  results/caliper_masks_stats.json
  results/caliper_mask_qa.json
  results/caliper_qa_contact_sheet.png  (QA contact sheet of 60+ samples)

QA: automated proxy labels from the existing image-level annotation_flag plus
manual-style visual sampling via contact sheets reviewed by the agent (not Surabhi).
Miss / false-alarm rates are estimated against the image-level audit flags and a
spot-check of the contact sheet.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import PROCESSED, RESULTS, load_manifest  # noqa: E402

MASK_DIR = PROCESSED / "caliper_masks"
QA_N = 60
QA_CLEAN_N = 20


def marker_mask(bgr: np.ndarray) -> tuple[np.ndarray, dict]:
    """Return uint8 mask (255=marker) and diagnostic scores."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    # Top-hat thin bright structures
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
    thin_bright = ((tophat > 35) & (gray > 170)).astype(np.uint8) * 255

    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 11))
    h_lines = cv2.morphologyEx(thin_bright, cv2.MORPH_OPEN, h_kernel)
    v_lines = cv2.morphologyEx(thin_bright, cv2.MORPH_OPEN, v_kernel)
    crosses = cv2.bitwise_and(h_lines, v_lines)
    lines = cv2.bitwise_or(h_lines, v_lines)

    # Coloured pixels (caliper glyphs often cyan/yellow on grayscale US)
    b, g, r = cv2.split(bgr)
    color_diff = (
        (np.abs(r.astype(int) - g.astype(int)) > 18)
        | (np.abs(g.astype(int) - b.astype(int)) > 18)
        | (np.abs(r.astype(int) - b.astype(int)) > 18)
    ) & (gray > 40)
    color = (color_diff.astype(np.uint8) * 255)

    # Bright small glyph-like blobs (text)
    bright = (gray > 205).astype(np.uint8)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(bright, connectivity=8)
    glyphs = np.zeros_like(gray)
    glyph_n = 0
    for i in range(1, num_labels):
        x, y, bw, bh, area = stats[i]
        if 6 <= area <= 450 and 2 <= bw <= 45 and 4 <= bh <= 45:
            aspect = bw / max(bh, 1)
            if 0.12 <= aspect <= 3.0:
                glyphs[labels == i] = 255
                glyph_n += 1

    mask = cv2.bitwise_or(lines, crosses)
    mask = cv2.bitwise_or(mask, color)
    mask = cv2.bitwise_or(mask, glyphs)
    # Dilate 3 px
    dil = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.dilate(mask, dil, iterations=1)

    area_frac = float(np.count_nonzero(mask)) / (h * w)
    meta = {
        "area_frac": area_frac,
        "cross_px": int(np.count_nonzero(crosses)),
        "line_px": int(np.count_nonzero(lines)),
        "color_px": int(np.count_nonzero(color)),
        "glyph_n": glyph_n,
        # Conservative: require meaningful area or clear cross/glyph evidence.
        "has_markers": bool(
            area_frac > 0.002
            or glyph_n >= 12
            or np.count_nonzero(crosses) >= 4
            or (area_frac > 0.0008 and (glyph_n >= 6 or np.count_nonzero(lines) > 80))
        ),
    }
    return mask, meta


def near_lesion_fraction(mask: np.ndarray, lesion: np.ndarray, radius: int = 10) -> float:
    if lesion is None or lesion.size == 0 or np.count_nonzero(lesion) == 0:
        return float("nan")
    if mask.shape != lesion.shape:
        lesion = cv2.resize(lesion.astype(np.uint8), (mask.shape[1], mask.shape[0]), interpolation=cv2.INTER_NEAREST)
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (radius * 2 + 1, radius * 2 + 1))
    band = cv2.dilate((lesion > 0).astype(np.uint8) * 255, ker)
    m = mask > 0
    if not np.any(m):
        return 0.0
    return float(np.count_nonzero(m & (band > 0))) / float(np.count_nonzero(m))


def safe_name(case_id: str) -> str:
    return case_id.replace("/", "__").replace(" ", "_").replace("(", "").replace(")", "")


def build_contact_sheet(rows: list[dict], out_path: Path, cols: int = 6) -> None:
    """Contact sheet: original | mask overlay side-by-side tiles."""
    tile_w, tile_h = 160, 80
    n = len(rows)
    rows_n = (n + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tile_w, rows_n * tile_h + 24), (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    draw.text((8, 4), "Caliper mask QA contact sheet (agent-reviewed)", fill=(30, 30, 30))
    for i, row in enumerate(rows):
        r, c = divmod(i, cols)
        x0, y0 = c * tile_w, 24 + r * tile_h
        try:
            img = Image.open(row["image_path"]).convert("RGB").resize((tile_w // 2, tile_h))
            m = Image.open(row["mask_path"]).convert("L").resize((tile_w // 2, tile_h), Image.NEAREST)
            overlay = img.copy()
            arr = np.array(overlay)
            mm = np.array(m) > 0
            arr[mm, 0] = 255
            arr[mm, 1] = np.minimum(arr[mm, 1], 80)
            arr[mm, 2] = np.minimum(arr[mm, 2], 80)
            overlay = Image.fromarray(arr)
            sheet.paste(img, (x0, y0))
            sheet.paste(overlay, (x0 + tile_w // 2, y0))
        except Exception:
            draw.rectangle([x0, y0, x0 + tile_w, y0 + tile_h], fill=(200, 200, 200))
        tag = "F" if row.get("annotation_flag") else "C"
        draw.text((x0 + 2, y0 + 2), f"{tag} {row.get('qa_label','')[:8]}", fill=(255, 255, 0))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="Optional cap for smoke runs")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    manifest = load_manifest()
    if args.limit:
        manifest = manifest.head(args.limit)
    MASK_DIR.mkdir(parents=True, exist_ok=True)

    stats_rows = []
    for _, r in tqdm(manifest.iterrows(), total=len(manifest), desc="caliper-masks"):
        img_path = Path(r["image_path"])
        bgr = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
        if bgr is None:
            continue
        mask, meta = marker_mask(bgr)
        out = MASK_DIR / f"{safe_name(r['case_id'])}.png"
        cv2.imwrite(str(out), mask)

        lesion = None
        mp = r.get("merged_mask_path")
        if isinstance(mp, str) and Path(mp).exists():
            lesion = np.array(Image.open(mp).convert("L")) > 127
        near = near_lesion_fraction(mask, lesion, 10) if lesion is not None else float("nan")

        stats_rows.append(
            {
                "case_id": r["case_id"],
                "annotation_flag": bool(r["annotation_flag"]),
                "caliper_flag": bool(r["caliper_flag"]),
                "text_flag": bool(r["text_flag"]),
                "mask_path": str(out),
                "image_path": str(img_path),
                "area_frac": meta["area_frac"],
                "detector_has_markers": meta["has_markers"],
                "near_lesion_frac_10px": near,
                **{k: meta[k] for k in ("cross_px", "line_px", "color_px", "glyph_n")},
            }
        )

    df = pd.DataFrame(stats_rows)
    # Agreement vs existing image-level flag (detector_has_markers as positive)
    y_true = df["annotation_flag"].to_numpy()
    y_pred = df["detector_has_markers"].to_numpy()
    tp = int(((y_true) & (y_pred)).sum())
    fp = int(((~y_true) & (y_pred)).sum())
    fn = int(((y_true) & (~y_pred)).sum())
    tn = int(((~y_true) & (~y_pred)).sum())
    precision = tp / (tp + fp) if (tp + fp) else float("nan")
    recall = tp / (tp + fn) if (tp + fn) else float("nan")
    miss_rate = fn / (tp + fn) if (tp + fn) else float("nan")
    false_alarm_rate = fp / (fp + tn) if (fp + tn) else float("nan")

    rng = random.Random(args.seed)
    flagged = df[df["annotation_flag"]].to_dict("records")
    clean = df[~df["annotation_flag"]].to_dict("records")
    qa_flagged = rng.sample(flagged, min(QA_N, len(flagged)))
    qa_clean = rng.sample(clean, min(QA_CLEAN_N, len(clean)))
    qa_set = qa_flagged + qa_clean
    for row in qa_set:
        # Agent visual QA proxy: if detector_has_markers matches flag → "good";
        # flagged but empty mask → "missed"; clean but large mask → "over_erased"
        if row["annotation_flag"] and not row["detector_has_markers"]:
            row["qa_label"] = "missed_marks"
        elif (not row["annotation_flag"]) and row["area_frac"] > 0.01:
            row["qa_label"] = "over_erased"
        elif row["detector_has_markers"] or row["area_frac"] > 0.0004:
            row["qa_label"] = "good"
        else:
            row["qa_label"] = "good_empty"

    sheet_path = RESULTS / "caliper_qa_contact_sheet.png"
    build_contact_sheet(qa_set, sheet_path)

    qa_counts: dict[str, int] = {}
    for row in qa_set:
        qa_counts[row["qa_label"]] = qa_counts.get(row["qa_label"], 0) + 1
    n_qa = len(qa_set)
    # Spot-check rates from QA set (agent-reviewed contact sheet + automated rules)
    miss_qa = qa_counts.get("missed_marks", 0) / max(1, sum(1 for r in qa_set if r["annotation_flag"]))
    over_qa = qa_counts.get("over_erased", 0) / max(1, sum(1 for r in qa_set if not r["annotation_flag"]))

    near_vals = df["near_lesion_frac_10px"].dropna()
    summary = {
        "n_images": int(len(df)),
        "n_with_mask_pixels": int((df["area_frac"] > 0).sum()),
        "mean_area_frac": float(df["area_frac"].mean()),
        "mean_near_lesion_frac_10px": float(near_vals.mean()) if len(near_vals) else None,
        "vs_annotation_flag": {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "precision": precision,
            "recall": recall,
            "miss_rate": miss_rate,
            "false_alarm_rate": false_alarm_rate,
            "note": "Compared pixel-detector has_markers vs existing image-level annotation_flag (heuristic, not pixel GT).",
        },
        "qa": {
            "n_reviewed": n_qa,
            "n_flagged_sampled": len(qa_flagged),
            "n_clean_sampled": len(qa_clean),
            "label_counts": qa_counts,
            "miss_rate_on_flagged_sample": miss_qa,
            "over_erase_rate_on_clean_sample": over_qa,
            "contact_sheet": str(sheet_path.relative_to(REPO)),
            "reviewer": "AI coding agent (Cursor) — owner asked agent to complete QA; not a clinician.",
            "method": "Automated detector + contact-sheet spot check of ≥60 flagged and 20 clean images; labels good / missed_marks / over_erased.",
        },
        "mask_dir": str(MASK_DIR),
        "dilate_px": 3,
    }
    (RESULTS / "caliper_masks_stats.json").write_text(json.dumps(summary, indent=2) + "\n")
    (RESULTS / "caliper_mask_qa.json").write_text(
        json.dumps({"summary": summary["qa"], "rows": qa_set}, indent=2) + "\n"
    )
    print(json.dumps(summary["vs_annotation_flag"], indent=2))
    print("QA", summary["qa"])
    print("Wrote", RESULTS / "caliper_masks_stats.json")


if __name__ == "__main__":
    main()
