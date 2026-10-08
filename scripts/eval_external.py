#!/usr/bin/env python3
"""Evaluate frozen v1.0.0 INT8 ONNX on external datasets (pre-registered protocol).

No threshold / architecture tuning. Writes results/external/<dataset>.json and
per-image JSON; merges an `external` block into web/public/results/metrics.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import (  # noqa: E402
    RESULTS,
    WEB_PUBLIC,
    dice_score,
    expected_calibration_error,
    imagenet_tensor_from_rgb,
    iou_score,
    remove_small_components,
)
from external.breast import build_manifest as build_breast  # noqa: E402
from external.busbra import build_manifest as build_busbra  # noqa: E402
from external.busuclm import build_manifest as build_busuclm  # noqa: E402
from external.common import RESULTS_EXTERNAL, bootstrap_mean_ci, load_mask_binary, load_rgb, write_json  # noqa: E402

try:
    from sklearn.metrics import roc_auc_score, roc_curve
except ImportError:
    roc_auc_score = None  # type: ignore
    roc_curve = None  # type: ignore


def score_manifest(name: str, manifest, sess, seg_thresh: float, min_area: int, cls_thresh: float, sha: str):
    rows = []
    for _, r in tqdm(manifest.iterrows(), total=len(manifest), desc=name):
        x = imagenet_tensor_from_rgb(load_rgb(r["image_path"]), 160)
        outs = sess.run(None, {"input": x})
        onames = [o.name for o in sess.get_outputs()]
        seg = outs[onames.index("seg_mask")] if "seg_mask" in onames else outs[0]
        cls = outs[onames.index("cls_prob")] if "cls_prob" in onames else outs[1]
        soft = seg[0, 0].astype(np.float32)
        cls_prob = float(cls.reshape(-1)[0])
        binary = soft > seg_thresh
        kept = remove_small_components(binary, min_area)
        gt = load_mask_binary(r["mask_path"] if r["mask_path"] else None, 160)
        if r["label"] == "normal":
            gt = np.zeros_like(gt)
        d = dice_score(kept, gt)
        i = iou_score(kept, gt)
        rows.append(
            {
                "case_id": r["case_id"],
                "label": r["label"],
                "patient_id": r["patient_id"],
                "scanner": r["scanner"],
                "birads": r["birads"],
                "pixel_size_mm": r["pixel_size_mm"],
                "dice": d,
                "iou": i,
                "cls_prob": cls_prob,
                "gt_area": int(gt.sum()),
                "pred_area": int(kept.sum()),
                "cls_target": 1.0 if r["label"] == "malignant" else (0.0 if r["label"] == "benign" else None),
            }
        )

    import pandas as pd

    df = pd.DataFrame(rows)
    clusters = df["patient_id"].astype(str).to_numpy()
    dice_mean, dice_ci = bootstrap_mean_ci(df["dice"].to_numpy(), clusters=clusters)
    iou_mean, iou_ci = bootstrap_mean_ci(df["iou"].to_numpy(), clusters=clusters)
    lesion = df[df["label"].isin(["benign", "malignant"])]
    lesion_dice, lesion_ci = bootstrap_mean_ci(lesion["dice"].to_numpy(), clusters=lesion["patient_id"].astype(str).to_numpy())

    by_label = {}
    for lab, g in df.groupby("label"):
        m, ci = bootstrap_mean_ci(g["dice"].to_numpy(), clusters=g["patient_id"].astype(str).to_numpy())
        by_label[lab] = {"n": int(len(g)), "dice_mean": m, "dice_ci95": ci}

    normals = df[df["label"] == "normal"]
    normal_fp = int((normals["pred_area"] > 0).sum()) if len(normals) else None

    bm = df[df["label"].isin(["benign", "malignant"])].dropna(subset=["cls_target"])
    cls_auc = sens = spec = ece = None
    cm = None
    if len(bm) >= 5 and roc_auc_score is not None:
        y = bm["cls_target"].to_numpy(dtype=float)
        p = bm["cls_prob"].to_numpy(dtype=float)
        try:
            cls_auc = float(roc_auc_score(y, p))
        except ValueError:
            cls_auc = None
        pred = (p >= cls_thresh).astype(int)
        tp = int(((pred == 1) & (y == 1)).sum())
        tn = int(((pred == 0) & (y == 0)).sum())
        fp = int(((pred == 1) & (y == 0)).sum())
        fn = int(((pred == 0) & (y == 1)).sum())
        sens = tp / (tp + fn) if (tp + fn) else None
        spec = tn / (tn + fp) if (tn + fp) else None
        ece_raw = expected_calibration_error(p, y)
        ece = float(ece_raw[0] if isinstance(ece_raw, (tuple, list)) else ece_raw)
        cm = {"labels": ["benign", "malignant"], "matrix": [[tn, fp], [fn, tp]]}

    subgroups = {}
    if df["birads"].notna().any():
        subgroups["by_birads"] = {}
        for b, g in df.dropna(subset=["birads"]).groupby("birads"):
            m, ci = bootstrap_mean_ci(g["dice"].to_numpy(), clusters=g["patient_id"].astype(str).to_numpy())
            subgroups["by_birads"][str(b)] = {"n": int(len(g)), "dice_mean": m, "dice_ci95": ci}
    if df["scanner"].notna().any():
        subgroups["by_scanner"] = {}
        for s, g in df.dropna(subset=["scanner"]).groupby("scanner"):
            m, ci = bootstrap_mean_ci(g["dice"].to_numpy(), clusters=g["patient_id"].astype(str).to_numpy())
            subgroups["by_scanner"][str(s)] = {"n": int(len(g)), "dice_mean": m, "dice_ci95": ci}

    summary = {
        "dataset": name,
        "model_version": "1.0.0",
        "model_sha256": sha,
        "protocol": "docs/EXTERNAL_VALIDATION_PROTOCOL.md",
        "n": int(len(df)),
        "n_patients": int(df["patient_id"].nunique()),
        "seg_threshold": seg_thresh,
        "min_component_area": min_area,
        "cls_threshold": cls_thresh,
        "test_dice": dice_mean,
        "test_dice_bootstrap_95ci": dice_ci,
        "test_iou": iou_mean,
        "test_iou_bootstrap_95ci": iou_ci,
        "lesion_dice": lesion_dice,
        "lesion_dice_bootstrap_95ci": lesion_ci,
        "by_label": by_label,
        "normal_false_positive_count": normal_fp,
        "normal_n": int(len(normals)) if len(normals) else 0,
        "cls_roc_auc": cls_auc,
        "cls_sensitivity": sens,
        "cls_specificity": spec,
        "cls_ece": ece,
        "confusion_matrix": cm,
        "subgroups": subgroups,
        "attribution": {
            "busbra": "Gómez-Flores et al., Med Phys 2024; Zenodo 8231412; CC BY 4.0",
            "breast": "Pawłowska et al., Sci Data 2024; TCIA Breast-Lesions-USG; CC BY 4.0",
            "busuclm": "Vallez et al., Sci Data 2025; Mendeley 7fvgj4jsp7; CC BY 4.0",
        }.get(name),
        "note": "Frozen v1.0.0 INT8; no tuning on external data. Images resized to 160² (shared bilinear).",
    }
    write_json(RESULTS_EXTERNAL / f"{name}.json", summary)
    write_json(RESULTS_EXTERNAL / f"{name}_per_image.json", rows)
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", nargs="+", default=["busbra", "breast", "busuclm"])
    args = ap.parse_args()

    pp = json.loads((RESULTS / "postprocess.json").read_text())
    seg_thresh = float(pp["seg_threshold"])
    min_area = int(pp["min_component_area"])
    cls_thresh = 0.5

    onnx = WEB_PUBLIC / "models" / "v1.0.0" / "busi_unet.onnx"
    sha = hashlib.sha256(onnx.read_bytes()).hexdigest()
    assert sha.startswith("0bbf529d"), f"Model sha mismatch: {sha}"
    sess = ort.InferenceSession(str(onnx), providers=["CPUExecutionProvider"])

    builders = {
        "busbra": build_busbra,
        "breast": build_breast,
        "busuclm": build_busuclm,
    }
    skipped = {}
    summaries = {}
    for name in args.datasets:
        try:
            man = builders[name]()
        except FileNotFoundError as e:
            skipped[name] = str(e)
            write_json(RESULTS_EXTERNAL / f"{name}_SKIPPED.json", {"dataset": name, "reason": str(e)})
            print(f"SKIP {name}: {e}")
            continue
        summaries[name] = score_manifest(name, man, sess, seg_thresh, min_area, cls_thresh, sha)
        print(
            f"{name}: Dice={summaries[name]['test_dice']:.3f} "
            f"lesion={summaries[name]['lesion_dice']:.3f} AUC={summaries[name]['cls_roc_auc']}"
        )

    # Merge into metrics.json
    metrics_path = WEB_PUBLIC / "results" / "metrics.json"
    metrics = json.loads(metrics_path.read_text())
    internal = metrics.get("served_int8", metrics["metrics"])
    metrics["external"] = {
        "protocol": "docs/EXTERNAL_VALIDATION_PROTOCOL.md",
        "model_version": "1.0.0",
        "model_sha256": sha,
        "internal_busi_int8": {
            "test_dice": internal.get("test_dice"),
            "lesion_dice": internal.get("lesion_dice"),
            "cls_roc_auc": internal.get("cls_roc_auc"),
            "n": 112,
        },
        "datasets": summaries,
        "skipped": skipped,
    }
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n")
    print("Updated", metrics_path)
    if skipped:
        print("Skipped:", skipped)


if __name__ == "__main__":
    main()
