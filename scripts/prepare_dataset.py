#!/usr/bin/env python3
"""Prepare BUSI for training: merge multi-masks, hash near-duplicates, flag
caliper/annotation artifacts, and build grouped stratified splits.

Outputs (committed where noted):
  data/processed/manifest.csv          — one row per image (local; gitignored data/)
  data/processed/merged_masks/         — merged binary masks
  results/audit_calipers_duplicates.csv — committed audit report
  results/splits.json                  — grouped 5-fold CV + held-out test
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

import cv2
import imagehash
import numpy as np
import pandas as pd
from PIL import Image
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold, train_test_split

REPO = Path(__file__).resolve().parents[1]
DEFAULT_RAW = REPO / "data" / "raw" / "extracted" / "Dataset_BUSI_with_GT"
PROCESSED = REPO / "data" / "processed"
RESULTS = REPO / "results"

CLASSES = ("benign", "malignant", "normal")
CLASS_TO_ID = {"benign": 0, "malignant": 1, "normal": 2}
# Classification head target: benign=0, malignant=1; normal ignored (-1)
CLS_TARGET = {"benign": 0, "malignant": 1, "normal": -1}

PHASH_THRESHOLD = 8  # Hamming distance for near-duplicates
SEED = 42
TEST_FRACTION = 0.15
N_FOLDS = 5


def discover_cases(raw_root: Path) -> list[dict]:
    """Pair each ultrasound image with all of its mask files."""
    cases: list[dict] = []
    for cls in CLASSES:
        folder = raw_root / cls
        if not folder.is_dir():
            raise FileNotFoundError(folder)
        images = sorted(
            f for f in folder.glob("*.png") if "_mask" not in f.name
        )
        for img_path in images:
            stem = img_path.stem  # e.g. "benign (1)"
            masks = sorted(folder.glob(f"{stem}_mask*.png"))
            # Prefer exact _mask.png plus any _mask_N.png
            cases.append(
                {
                    "case_id": f"{cls}/{img_path.name}",
                    "label": cls,
                    "label_id": CLASS_TO_ID[cls],
                    "cls_target": CLS_TARGET[cls],
                    "image_path": str(img_path.resolve()),
                    "mask_paths": [str(m.resolve()) for m in masks],
                    "n_masks": len(masks),
                }
            )
    return cases


def merge_masks(mask_paths: list[str], out_path: Path) -> tuple[int, int]:
    """OR-merge all lesion masks for one image. Empty mask for normals / missing."""
    if not mask_paths:
        # Write empty placeholder; size filled later from image
        return 0, 0

    arrays = []
    for p in mask_paths:
        arr = np.array(Image.open(p).convert("L"))
        arrays.append(arr > 127)
    merged = np.any(np.stack(arrays, axis=0), axis=0).astype(np.uint8) * 255
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(merged).save(out_path)
    return int(merged.sum() // 255), int(merged.size)


def ensure_empty_mask(image_path: str, out_path: Path) -> None:
    img = Image.open(image_path)
    empty = np.zeros((img.height, img.width), dtype=np.uint8)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(empty).save(out_path)


def perceptual_hash(image_path: str) -> str:
    img = Image.open(image_path).convert("RGB")
    return str(imagehash.phash(img))


def group_near_duplicates(hashes: list[str], threshold: int = PHASH_THRESHOLD) -> list[int]:
    """Union-find grouping by Hamming distance on phash hex strings."""
    n = len(hashes)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    parsed = [imagehash.hex_to_hash(h) for h in hashes]
    for i in range(n):
        for j in range(i + 1, n):
            if parsed[i] - parsed[j] <= threshold:
                union(i, j)

    roots = [find(i) for i in range(n)]
    root_to_gid: dict[int, int] = {}
    groups: list[int] = []
    next_gid = 0
    for r in roots:
        if r not in root_to_gid:
            root_to_gid[r] = next_gid
            next_gid += 1
        groups.append(root_to_gid[r])
    return groups


def detect_calipers_annotations(image_path: str) -> dict:
    """Heuristic flags for burned-in calipers / text / measurement marks.

    BUSI images frequently contain bright caliper crosses and on-screen text.
    We combine several cheap signals (no OCR dependency):
      - bright thin-line / cross-like structures (calipers)
      - high-contrast small components resembling characters
      - elevated edge energy in image borders (HUD overlays)
    """
    bgr = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if bgr is None:
        return {
            "caliper_flag": False,
            "text_flag": False,
            "annotation_flag": False,
            "caliper_score": 0.0,
            "text_score": 0.0,
            "reasons": "unreadable",
        }
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    reasons: list[str] = []

    # --- Caliper / bright cross detection ---
    bright = (gray > 220).astype(np.uint8) * 255
    # Morphological top-hat to emphasize thin bright marks
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    tophat = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)
    thin_bright = ((tophat > 40) & (gray > 180)).astype(np.uint8) * 255

    # Look for plus-shaped local patterns via horizontal+vertical line hits
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 9))
    h_lines = cv2.morphologyEx(thin_bright, cv2.MORPH_OPEN, h_kernel)
    v_lines = cv2.morphologyEx(thin_bright, cv2.MORPH_OPEN, v_kernel)
    crosses = cv2.bitwise_and(h_lines, v_lines)
    cross_frac = float(np.count_nonzero(crosses)) / (h * w)
    bright_frac = float(np.count_nonzero(bright)) / (h * w)
    thin_frac = float(np.count_nonzero(thin_bright)) / (h * w)

    caliper_score = min(1.0, cross_frac * 800 + thin_frac * 15)
    caliper_flag = bool(cross_frac > 0.00015 or (thin_frac > 0.012 and bright_frac > 0.01))
    if caliper_flag:
        reasons.append(f"bright_thin_marks(cross={cross_frac:.5f},thin={thin_frac:.4f})")

    # --- Text / HUD heuristic ---
    # Border strips often hold burned-in labels
    border = 24
    borders = np.concatenate(
        [
            gray[:border, :].ravel(),
            gray[-border:, :].ravel(),
            gray[:, :border].ravel(),
            gray[:, -border:].ravel(),
        ]
    )
    border_bright = float(np.mean(borders > 200))
    # Connected components of bright small blobs (glyph-like)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        (gray > 200).astype(np.uint8), connectivity=8
    )
    glyph_like = 0
    for i in range(1, num_labels):
        x, y, bw, bh, area = stats[i]
        if 8 <= area <= 400 and 2 <= bw <= 40 and 5 <= bh <= 40:
            aspect = bw / max(bh, 1)
            if 0.15 <= aspect <= 2.5:
                glyph_like += 1
    text_score = min(1.0, glyph_like / 40.0 + border_bright)
    text_flag = bool(glyph_like >= 12 or (glyph_like >= 6 and border_bright > 0.08))
    if text_flag:
        reasons.append(f"textlike_blobs(n={glyph_like},border_bright={border_bright:.3f})")

    annotation_flag = caliper_flag or text_flag
    return {
        "caliper_flag": caliper_flag,
        "text_flag": text_flag,
        "annotation_flag": annotation_flag,
        "caliper_score": round(caliper_score, 4),
        "text_score": round(text_score, 4),
        "reasons": ";".join(reasons) if reasons else "",
    }


def build_splits(df: pd.DataFrame, seed: int = SEED) -> dict:
    """Grouped stratified held-out test + 5-fold CV on the remainder.

    BUSI has no patient IDs. Near-duplicate groups (via perceptual hash) are
    kept entirely within one split so identical/near-identical frames never
    leak across train/val/test. True patient-level splits are not possible.
    """
    # Stratify by label for held-out test using groups
    groups = df["dup_group"].values
    labels = df["label"].values
    indices = np.arange(len(df))

    # StratifiedGroupKFold with 1/TEST ~ folds for held-out approx
    n_test_folds = max(2, int(round(1 / TEST_FRACTION)))
    sgkf = StratifiedGroupKFold(n_splits=n_test_folds, shuffle=True, random_state=seed)
    trainval_idx, test_idx = next(sgkf.split(indices, labels, groups))

    test_ids = df.iloc[test_idx]["case_id"].tolist()
    trainval = df.iloc[trainval_idx].reset_index(drop=True)

    folds = []
    # Prefer StratifiedGroupKFold; fall back if a class is too rare in groups
    try:
        cv = StratifiedGroupKFold(n_splits=N_FOLDS, shuffle=True, random_state=seed)
        splits_iter = cv.split(np.arange(len(trainval)), trainval["label"], trainval["dup_group"])
    except ValueError:
        cv = GroupKFold(n_splits=N_FOLDS)
        splits_iter = cv.split(np.arange(len(trainval)), trainval["label"], trainval["dup_group"])

    for fold_i, (tr, va) in enumerate(splits_iter):
        folds.append(
            {
                "fold": fold_i,
                "train_ids": trainval.iloc[tr]["case_id"].tolist(),
                "val_ids": trainval.iloc[va]["case_id"].tolist(),
            }
        )

    # Sanity: no group overlap
    def groups_of(ids: list[str]) -> set[int]:
        return set(df.set_index("case_id").loc[ids, "dup_group"].tolist())

    test_groups = groups_of(test_ids)
    for fold in folds:
        tr_g = groups_of(fold["train_ids"])
        va_g = groups_of(fold["val_ids"])
        assert tr_g.isdisjoint(va_g), "train/val group leak"
        assert tr_g.isdisjoint(test_groups), "train/test group leak"
        assert va_g.isdisjoint(test_groups), "val/test group leak"

    return {
        "seed": seed,
        "test_fraction_target": TEST_FRACTION,
        "n_folds": N_FOLDS,
        "note": (
            "BUSI provides no patient IDs. Splits are grouped by perceptual-hash "
            "near-duplicate clusters so near-identical images never cross splits. "
            "This is NOT a true patient-level split."
        ),
        "counts": {
            "total": int(len(df)),
            "test": int(len(test_ids)),
            "trainval": int(len(trainval)),
            "by_label_total": df["label"].value_counts().to_dict(),
            "by_label_test": df.iloc[test_idx]["label"].value_counts().to_dict(),
            "n_dup_groups": int(df["dup_group"].nunique()),
            "n_annotation_flagged": int(df["annotation_flag"].sum()),
        },
        "test_ids": test_ids,
        "folds": folds,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raw-root", type=Path, default=DEFAULT_RAW)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    if not args.raw_root.is_dir():
        raise SystemExit(
            f"Raw BUSI not found at {args.raw_root}. Run scripts/download_busi.py first."
        )

    PROCESSED.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    mask_dir = PROCESSED / "merged_masks"
    mask_dir.mkdir(parents=True, exist_ok=True)

    print("Discovering cases…")
    cases = discover_cases(args.raw_root)
    print(f"  {len(cases)} images")

    rows = []
    print("Merging masks, hashing, flagging annotations…")
    for i, case in enumerate(cases):
        safe_name = case["case_id"].replace("/", "__").replace(" ", "_")
        merged_path = mask_dir / f"{safe_name}"
        if not merged_path.suffix:
            merged_path = merged_path.with_suffix(".png")

        if case["mask_paths"]:
            area, total = merge_masks(case["mask_paths"], merged_path)
        else:
            ensure_empty_mask(case["image_path"], merged_path)
            area, total = 0, 0

        # Normals should be empty even if a mask file exists (BUSI normals have empty masks)
        if case["label"] == "normal":
            ensure_empty_mask(case["image_path"], merged_path)
            area = 0

        ph = perceptual_hash(case["image_path"])
        flags = detect_calipers_annotations(case["image_path"])
        rows.append(
            {
                **case,
                "mask_paths": "|".join(case["mask_paths"]),
                "merged_mask_path": str(merged_path.resolve()),
                "mask_area_px": area,
                "phash": ph,
                **flags,
            }
        )
        if (i + 1) % 100 == 0:
            print(f"  processed {i + 1}/{len(cases)}")

    df = pd.DataFrame(rows)
    print("Grouping near-duplicates…")
    df["dup_group"] = group_near_duplicates(df["phash"].tolist(), PHASH_THRESHOLD)

    # Exact duplicate hash clusters
    exact = df.groupby("phash").size()
    df["exact_dup"] = df["phash"].map(exact) > 1

    manifest_path = PROCESSED / "manifest.csv"
    df.to_csv(manifest_path, index=False)
    print(f"Wrote {manifest_path}")

    # Committed audit report (subset of columns)
    audit_cols = [
        "case_id",
        "label",
        "n_masks",
        "mask_area_px",
        "phash",
        "dup_group",
        "exact_dup",
        "caliper_flag",
        "text_flag",
        "annotation_flag",
        "caliper_score",
        "text_score",
        "reasons",
    ]
    audit_path = RESULTS / "audit_calipers_duplicates.csv"
    df[audit_cols].to_csv(audit_path, index=False)
    print(f"Wrote audit report {audit_path}")

    print("Building grouped splits…")
    splits = build_splits(df, seed=args.seed)
    splits_path = RESULTS / "splits.json"
    splits_path.write_text(json.dumps(splits, indent=2))
    print(f"Wrote {splits_path}")
    print(json.dumps(splits["counts"], indent=2))
    print(
        f"Flagged annotations: {int(df['annotation_flag'].sum())} / {len(df)} "
        f"({100 * df['annotation_flag'].mean():.1f}%)"
    )
    print(
        f"Near-dup groups: {df['dup_group'].nunique()} "
        f"(images in multi-member groups: {int((df.groupby('dup_group').transform('size') > 1).sum())})"
    )


if __name__ == "__main__":
    main()
