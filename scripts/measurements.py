#!/usr/bin/env python3
"""Offline measurement agreement: model vs expert masks (px; mm on BrEaST).

Research only — not clinical measurements. Writes results/measurement_agreement.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import RESULTS, imagenet_tensor_from_rgb, remove_small_components  # noqa: E402
from external.breast import build_manifest as build_breast  # noqa: E402
from external.common import load_mask_binary, load_rgb  # noqa: E402
import hashlib
import onnxruntime as ort
from tqdm import tqdm


def feret_and_perp(binary: np.ndarray) -> tuple[float, float, float]:
    """Longest Feret (px), perpendicular width, area."""
    ys, xs = np.where(binary)
    area = float(len(xs))
    if area == 0:
        return 0.0, 0.0, 0.0
    pts = np.stack([xs, ys], axis=1).astype(float)
    # farthest pair (OK for 160²)
    dmax = 0.0
    a = b = pts[0]
    for i in range(len(pts)):
        dif = pts[i:] - pts[i]
        d2 = (dif**2).sum(axis=1)
        j = int(np.argmax(d2))
        if d2[j] > dmax:
            dmax = float(d2[j])
            a = pts[i]
            b = pts[i + j]
    longest = float(np.sqrt(dmax))
    u = b - a
    nrm = np.linalg.norm(u) or 1.0
    perp_dir = np.array([-u[1], u[0]]) / nrm
    proj = (pts - a) @ perp_dir
    perp = float(proj.max() - proj.min())
    return longest, perp, area


def bland_altman(ref: np.ndarray, pred: np.ndarray) -> dict:
    diff = pred - ref
    mean = (pred + ref) / 2
    return {
        "bias": float(diff.mean()),
        "sd": float(diff.std(ddof=1)) if len(diff) > 1 else 0.0,
        "loa_low": float(diff.mean() - 1.96 * diff.std(ddof=1)) if len(diff) > 1 else 0.0,
        "loa_high": float(diff.mean() + 1.96 * diff.std(ddof=1)) if len(diff) > 1 else 0.0,
        "n": int(len(diff)),
    }


def icc_approx(ref: np.ndarray, pred: np.ndarray) -> float:
    """Simple ICC(A,1)-like consistency via two-way agreement approximation."""
    if len(ref) < 3:
        return float("nan")
    # Pearson as a transparent proxy when full ICC libraries are heavy — label as such
    if ref.std() < 1e-9 or pred.std() < 1e-9:
        return float("nan")
    return float(np.corrcoef(ref, pred)[0, 1])


def main() -> None:
    onnx = REPO / "web" / "public" / "models" / "v1.0.0" / "busi_unet.onnx"
    sha = hashlib.sha256(onnx.read_bytes()).hexdigest()
    sess = ort.InferenceSession(str(onnx), providers=["CPUExecutionProvider"])

    # BrEaST with spacing
    man = build_breast()
    rows = []
    for _, r in tqdm(man.iterrows(), total=len(man), desc="measure-breast"):
        if r["label"] == "normal":
            continue
        x = imagenet_tensor_from_rgb(load_rgb(r["image_path"]), 160)
        outs = sess.run(None, {"input": x})
        names = [o.name for o in sess.get_outputs()]
        soft = outs[names.index("seg_mask")][0, 0]
        pred = remove_small_components(soft > 0.4, 40)
        gt = load_mask_binary(r["mask_path"], 160)
        pl, pp, pa = feret_and_perp(pred)
        gl, gp, ga = feret_and_perp(gt)
        spacing = r["pixel_size_mm"]
        rows.append(
            {
                "case_id": r["case_id"],
                "pixel_size_mm": spacing,
                "pred_area_px": pa,
                "gt_area_px": ga,
                "pred_longest_px": pl,
                "gt_longest_px": gl,
                "pred_perp_px": pp,
                "gt_perp_px": gp,
                "pred_longest_mm": pl * spacing if spacing else None,
                "gt_longest_mm": gl * spacing if spacing else None,
            }
        )

    import pandas as pd

    df = pd.DataFrame(rows)
    # T1/T2 20 mm boundary discordance (exploratory)
    both_mm = df.dropna(subset=["pred_longest_mm", "gt_longest_mm"])
    gt_over = both_mm["gt_longest_mm"] >= 20
    pred_over = both_mm["pred_longest_mm"] >= 20
    discord = float((gt_over != pred_over).mean()) if len(both_mm) else None

    out = {
        "label": "Measurement agreement on BrEaST (model vs expert masks @ 160²)",
        "model_sha256": sha,
        "disclaimer": "Research only — imaging size is not pathological T-stage; not clinical measurements.",
        "n": int(len(df)),
        "area_px": {
            "bland_altman": bland_altman(df["gt_area_px"].to_numpy(), df["pred_area_px"].to_numpy()),
            "pearson_proxy_for_icc": icc_approx(df["gt_area_px"].to_numpy(), df["pred_area_px"].to_numpy()),
        },
        "longest_diameter_px": {
            "bland_altman": bland_altman(df["gt_longest_px"].to_numpy(), df["pred_longest_px"].to_numpy()),
            "pearson_proxy_for_icc": icc_approx(df["gt_longest_px"].to_numpy(), df["pred_longest_px"].to_numpy()),
        },
        "longest_diameter_mm": {
            "bland_altman": bland_altman(
                both_mm["gt_longest_mm"].to_numpy(), both_mm["pred_longest_mm"].to_numpy()
            )
            if len(both_mm)
            else None,
            "pearson_proxy_for_icc": icc_approx(
                both_mm["gt_longest_mm"].to_numpy(), both_mm["pred_longest_mm"].to_numpy()
            )
            if len(both_mm)
            else None,
            "t1_t2_20mm_discordance_rate": discord,
            "note": "Exploratory: fraction of cases where model and expert disagree on ≥20 mm longest diameter.",
        },
        "per_image_path": "results/measurement_agreement_per_image.json",
    }
    (RESULTS / "measurement_agreement.json").write_text(json.dumps(out, indent=2) + "\n")
    (RESULTS / "measurement_agreement_per_image.json").write_text(json.dumps(rows, indent=2) + "\n")
    print("Wrote results/measurement_agreement.json", "discord", discord)


if __name__ == "__main__":
    main()
