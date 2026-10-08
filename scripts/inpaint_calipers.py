#!/usr/bin/env python3
"""Telea-inpaint BUSI images using caliper masks (synthetic alterations).

Writes data/processed/inpainted/<safe_case_id>.png (gitignored).
Also can write random-region control inpaints for E-b.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import PROCESSED, load_manifest  # noqa: E402
from caliper_masks import MASK_DIR, safe_name  # noqa: E402

INPAINT_DIR = PROCESSED / "inpainted"
RANDOM_DIR = PROCESSED / "inpainted_random"


def telea_inpaint(bgr: np.ndarray, mask: np.ndarray) -> np.ndarray:
    m = (mask > 0).astype(np.uint8)
    if m.max() == 0:
        return bgr.copy()
    return cv2.inpaint(bgr, m, inpaintRadius=3, flags=cv2.INPAINT_TELEA)


def random_mask_like(shape: tuple[int, int], area: int, rng: np.random.Generator) -> np.ndarray:
    """Place random ellipses totaling ~area pixels (control for E-b)."""
    h, w = shape
    m = np.zeros((h, w), dtype=np.uint8)
    if area <= 0:
        return m
    target = area
    tries = 0
    while np.count_nonzero(m) < target and tries < 40:
        tries += 1
        cy = int(rng.integers(0, h))
        cx = int(rng.integers(0, w))
        axes = (
            max(2, int(rng.integers(2, max(3, int(np.sqrt(area / 3)))))),
            max(2, int(rng.integers(2, max(3, int(np.sqrt(area / 3)))))),
        )
        angle = float(rng.uniform(0, 180))
        cv2.ellipse(m, (cx, cy), axes, angle, 0, 360, 255, -1)
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["markers", "random", "both"], default="both")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    manifest = load_manifest()
    if args.limit:
        manifest = manifest.head(args.limit)
    rng = np.random.default_rng(args.seed)

    if args.mode in ("markers", "both"):
        INPAINT_DIR.mkdir(parents=True, exist_ok=True)
        n = 0
        for _, r in tqdm(manifest.iterrows(), total=len(manifest), desc="inpaint-markers"):
            mp = MASK_DIR / f"{safe_name(r['case_id'])}.png"
            if not mp.exists():
                continue
            bgr = cv2.imread(str(r["image_path"]), cv2.IMREAD_COLOR)
            mask = cv2.imread(str(mp), cv2.IMREAD_GRAYSCALE)
            if bgr is None or mask is None:
                continue
            if mask.shape[:2] != bgr.shape[:2]:
                mask = cv2.resize(mask, (bgr.shape[1], bgr.shape[0]), interpolation=cv2.INTER_NEAREST)
            area_frac = float(np.count_nonzero(mask)) / (mask.shape[0] * mask.shape[1])
            # Skip near-empty / weak detections on unflagged images (avoid over-erasure).
            if area_frac < 0.0008 and not bool(r.get("annotation_flag", False)):
                cv2.imwrite(str(INPAINT_DIR / f"{safe_name(r['case_id'])}.png"), bgr)
            else:
                out = telea_inpaint(bgr, mask)
                cv2.imwrite(str(INPAINT_DIR / f"{safe_name(r['case_id'])}.png"), out)
            n += 1
        print(f"Wrote {n} marker-inpainted images → {INPAINT_DIR}")

    if args.mode in ("random", "both"):
        RANDOM_DIR.mkdir(parents=True, exist_ok=True)
        # Only clean (unflagged) images for E-b control
        clean = manifest[~manifest["annotation_flag"]]
        n = 0
        for _, r in tqdm(clean.iterrows(), total=len(clean), desc="inpaint-random"):
            mp = MASK_DIR / f"{safe_name(r['case_id'])}.png"
            bgr = cv2.imread(str(r["image_path"]), cv2.IMREAD_COLOR)
            if bgr is None:
                continue
            # Match area distribution from flagged masks when available
            area = 0
            if mp.exists():
                m0 = cv2.imread(str(mp), cv2.IMREAD_GRAYSCALE)
                if m0 is not None:
                    area = int(np.count_nonzero(m0))
            if area <= 0:
                area = int(0.005 * bgr.shape[0] * bgr.shape[1])
            rm = random_mask_like(bgr.shape[:2], area, rng)
            out = telea_inpaint(bgr, rm)
            cv2.imwrite(str(RANDOM_DIR / f"{safe_name(r['case_id'])}.png"), out)
            n += 1
        print(f"Wrote {n} random-inpainted clean images → {RANDOM_DIR}")

    meta = {
        "inpaint_dir": str(INPAINT_DIR),
        "random_dir": str(RANDOM_DIR),
        "method": "cv2.INPAINT_TELEA radius=3",
        "label": "Digitally altered — synthetic marker removal",
    }
    (PROCESSED / "inpaint_meta.json").write_text(json.dumps(meta, indent=2) + "\n")


if __name__ == "__main__":
    main()
