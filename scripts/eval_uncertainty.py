#!/usr/bin/env python3
"""Offline TTA uncertainty evaluation (Spearman vs Dice; risk–coverage)."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image
from scipy.stats import spearmanr
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import (  # noqa: E402
    RESULTS,
    WEB_PUBLIC,
    dice_score,
    imagenet_tensor_from_rgb,
    load_manifest,
    load_splits,
    remove_small_components,
)

SEG_THRESH = 0.4
MIN_AREA = 40


def tta_masks(sess, rgb: np.ndarray, img_size: int = 160) -> tuple[float, float]:
    """Return (agreement, cls_std) for simple flip TTA."""
    names = [o.name for o in sess.get_outputs()]
    variants = [rgb, np.flip(rgb, 1), np.flip(rgb, 0), np.flip(np.flip(rgb, 0), 1)]
    masks = []
    probs = []
    for v in variants:
        x = imagenet_tensor_from_rgb(v.copy(), img_size)
        outs = sess.run(None, {"input": x})
        seg = outs[names.index("seg_mask")] if "seg_mask" in names else outs[0]
        cls = outs[names.index("cls_prob")] if "cls_prob" in names else outs[1]
        soft = seg[0, 0]
        # invert geometric flips applied to input
        if v is variants[1]:
            soft = np.flip(soft, 1)
        elif v is variants[2]:
            soft = np.flip(soft, 0)
        elif v is variants[3]:
            soft = np.flip(np.flip(soft, 0), 1)
        masks.append(remove_small_components(soft > SEG_THRESH, MIN_AREA))
        probs.append(float(cls.reshape(-1)[0]))
    # pairwise Dice agreement
    pair = []
    for i in range(len(masks)):
        for j in range(i + 1, len(masks)):
            pair.append(dice_score(masks[i], masks[j]))
    agreement = float(np.mean(pair)) if pair else 1.0
    cls_std = float(np.std(probs))
    return agreement, cls_std


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--onnx", type=Path, default=WEB_PUBLIC / "models" / "v1.0.0" / "busi_unet.onnx")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    sess = ort.InferenceSession(str(args.onnx), providers=["CPUExecutionProvider"])
    sha = hashlib.sha256(args.onnx.read_bytes()).hexdigest()
    manifest = load_manifest().set_index("case_id")
    test_ids = load_splits()["test_ids"]
    if args.limit:
        test_ids = test_ids[: args.limit]

    rows = []
    for cid in tqdm(test_ids, desc="TTA uncertainty"):
        row = manifest.loc[cid]
        rgb = np.asarray(Image.open(row["image_path"]).convert("RGB"))
        agreement, cls_std = tta_masks(sess, rgb)
        # single-pass dice for reference
        x = imagenet_tensor_from_rgb(rgb, 160)
        outs = sess.run(None, {"input": x})
        names = [o.name for o in sess.get_outputs()]
        seg = outs[names.index("seg_mask")] if "seg_mask" in names else outs[0]
        pred = remove_small_components(seg[0, 0] > SEG_THRESH, MIN_AREA)
        gt = np.array(Image.open(row["merged_mask_path"]).convert("L").resize((160, 160), Image.NEAREST)) > 127
        d = float(dice_score(pred, gt))
        uncertainty = 1.0 - agreement
        rows.append(
            {
                "case_id": cid,
                "label": row["label"],
                "dice": d,
                "agreement": agreement,
                "uncertainty": uncertainty,
                "cls_std": cls_std,
                "annotation_flag": bool(row["annotation_flag"]),
            }
        )

    dice = np.array([r["dice"] for r in rows])
    unc = np.array([r["uncertainty"] for r in rows])
    rho, pval = spearmanr(unc, 1.0 - dice)

    # Risk–coverage: abstain on top-k uncertain
    order = np.argsort(-unc)
    coverage_curve = []
    for keep_frac in [1.0, 0.9, 0.8, 0.7, 0.5]:
        k = max(1, int(round(len(rows) * keep_frac)))
        keep = order[-k:]  # least uncertain
        coverage_curve.append(
            {
                "coverage": keep_frac,
                "mean_dice": float(dice[keep].mean()),
                "n": int(k),
            }
        )

    normals = [r for r in rows if r["label"] == "normal"]
    normal_fp = [r for r in normals if r["dice"] < 0.99]
    out = {
        "model_sha256": sha,
        "n": len(rows),
        "spearman_uncertainty_vs_error": {"rho": float(rho), "pvalue": float(pval)},
        "interpretation": (
            "Positive rho means higher TTA disagreement tends to co-occur with lower Dice. "
            "This is agreement under flips — not a calibrated error probability."
        ),
        "risk_coverage": coverage_curve,
        "normal_fp": {
            "n_normal": len(normals),
            "n_fp_proxy": len(normal_fp),
            "mean_uncertainty_fp": float(np.mean([r["uncertainty"] for r in normal_fp])) if normal_fp else None,
            "mean_uncertainty_all_normal": float(np.mean([r["uncertainty"] for r in normals])) if normals else None,
        },
        "per_image_path": "results/uncertainty_per_image.json",
    }
    (RESULTS / "uncertainty.json").write_text(json.dumps(out, indent=2) + "\n")
    (RESULTS / "uncertainty_per_image.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(json.dumps({k: out[k] for k in out if k != "per_image_path"}, indent=2))


if __name__ == "__main__":
    main()
