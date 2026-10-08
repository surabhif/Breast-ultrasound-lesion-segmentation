#!/usr/bin/env python3
"""Score the *served* INT8 ONNX model on the held-out BUSI test set.

Uses the same post-processing as training metrics (seg_thresh=0.4,
min_component_area=40) and the same ImageNet-normalized 160² resize as
`busi_data.BusiDataset` / the browser pipeline.

Writes:
  results/served_int8_test.json
  results/served_int8_per_image.json
and merges a `served_int8` block into web/public/results/metrics.json.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import (  # noqa: E402
    RESULTS,
    WEB_PUBLIC,
    bootstrap_ci,
    dice_score,
    expected_calibration_error,
    imagenet_tensor_from_rgb,
    iou_score,
    load_manifest,
    load_splits,
    remove_small_components,
)


def preprocess(image_path: str, img_size: int = 160) -> np.ndarray:
    img = Image.open(image_path).convert("RGB")
    return imagenet_tensor_from_rgb(np.asarray(img), img_size)


def load_mask(mask_path: str, img_size: int = 160) -> np.ndarray:
    m = Image.open(mask_path).convert("L")
    m = m.resize((img_size, img_size), Image.NEAREST)
    return (np.asarray(m) > 127)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--onnx",
        type=Path,
        default=WEB_PUBLIC / "models" / "v1.0.0" / "busi_unet.onnx",
    )
    ap.add_argument("--img-size", type=int, default=160)
    ap.add_argument("--seg-thresh", type=float, default=None)
    ap.add_argument("--min-area", type=int, default=None)
    ap.add_argument("--cls-thresh", type=float, default=0.5)
    args = ap.parse_args()

    pp = json.loads((RESULTS / "postprocess.json").read_text())
    seg_thresh = float(args.seg_thresh if args.seg_thresh is not None else pp["seg_threshold"])
    min_area = int(args.min_area if args.min_area is not None else pp["min_component_area"])

    onnx_path = args.onnx
    sha = hashlib.sha256(onnx_path.read_bytes()).hexdigest()
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])

    manifest = load_manifest()
    splits = load_splits()
    test_ids = splits["test_ids"]
    by_id = manifest.set_index("case_id")

    per_image = []
    for case_id in tqdm(test_ids, desc="INT8 test"):
        row = by_id.loc[case_id]
        x = preprocess(row["image_path"], args.img_size)
        outs = sess.run(None, {"input": x})
        # outputs: seg_mask, cls_prob (names may vary)
        names = [o.name for o in sess.get_outputs()]
        seg = outs[names.index("seg_mask")] if "seg_mask" in names else outs[0]
        cls = outs[names.index("cls_prob")] if "cls_prob" in names else outs[1]
        seg_prob = seg[0, 0]
        cls_prob = float(cls.reshape(-1)[0])
        pred = seg_prob > seg_thresh
        if min_area > 0:
            pred = remove_small_components(pred, min_area)
        gt = load_mask(row["merged_mask_path"], args.img_size)
        label = str(row["label"])
        cls_target = float(row["cls_target"])
        d = dice_score(pred, gt)
        iou = iou_score(pred, gt)
        per_image.append(
            {
                "case_id": case_id,
                "label": label,
                "dice": float(d),
                "iou": float(iou),
                "annotation_flag": bool(row.get("annotation_flag", False)),
                "cls_target": cls_target,
                "cls_prob": cls_prob,
                "gt_area": float(gt.sum()),
                "pred_area": float(pred.sum()),
            }
        )

    dice_all = np.array([r["dice"] for r in per_image])
    iou_all = np.array([r["iou"] for r in per_image])
    d_mean, d_lo, d_hi = bootstrap_ci(dice_all)
    i_mean, i_lo, i_hi = bootstrap_ci(iou_all)

    by_label = {}
    for lab in ("benign", "malignant", "normal"):
        vals = np.array([r["dice"] for r in per_image if r["label"] == lab])
        if len(vals):
            m, lo, hi = bootstrap_ci(vals)
            by_label[lab] = {
                "n": int(len(vals)),
                "dice_mean": m,
                "dice_ci95": [lo, hi],
                "iou_mean": float(
                    np.mean([r["iou"] for r in per_image if r["label"] == lab])
                ),
            }

    lesion = np.array([r["dice"] for r in per_image if r["label"] != "normal"])
    ld_mean, ld_lo, ld_hi = bootstrap_ci(lesion)

    normals = [r for r in per_image if r["label"] == "normal"]
    normal_fp = [r for r in normals if r["pred_area"] > 0]
    normal_fp_rate = len(normal_fp) / len(normals) if normals else float("nan")

    cls_rows = [r for r in per_image if r["cls_target"] >= 0]
    y = np.array([int(r["cls_target"]) for r in cls_rows])
    p = np.array([r["cls_prob"] for r in cls_rows])
    from sklearn.metrics import confusion_matrix, roc_auc_score, roc_curve

    auc = float(roc_auc_score(y, p))
    pred_cls = (p >= args.cls_thresh).astype(int)
    cm = confusion_matrix(y, pred_cls, labels=[0, 1]).tolist()
    tn, fp, fn, tp = cm[0][0], cm[0][1], cm[1][0], cm[1][1]
    sens = tp / (tp + fn) if (tp + fn) else float("nan")
    spec = tn / (tn + fp) if (tn + fp) else float("nan")
    ece, cal = expected_calibration_error(p, y)
    fpr, tpr, thr = roc_curve(y, p)

    out = {
        "label": "Served INT8 ONNX (v1.0.0) on held-out BUSI test",
        "model_path": str(onnx_path.relative_to(REPO)),
        "sha256": sha,
        "n": len(per_image),
        "seg_threshold": seg_thresh,
        "min_component_area": min_area,
        "cls_threshold": args.cls_thresh,
        "dice_mean": d_mean,
        "dice_ci95": [d_lo, d_hi],
        "iou_mean": i_mean,
        "iou_ci95": [i_lo, i_hi],
        "lesion_dice_mean": ld_mean,
        "lesion_dice_ci95": [ld_lo, ld_hi],
        "by_label": by_label,
        "normal_false_positive_count": len(normal_fp),
        "normal_n": len(normals),
        "normal_false_positive_rate": normal_fp_rate,
        "cls_roc_auc": auc,
        "cls_sensitivity": float(sens),
        "cls_specificity": float(spec),
        "cls_ece": float(ece),
        "confusion_matrix": {"labels": ["benign", "malignant"], "matrix": cm},
        "roc_curve": [
            {"fpr": float(a), "tpr": float(b), "threshold": float(c) if i < len(thr) else None}
            for i, (a, b, c) in enumerate(
                zip(fpr, tpr, list(thr) + [None] * max(0, len(fpr) - len(thr)))
            )
        ],
        "calibration": cal,
        "compared_to_fp32": {
            "source": "results/full_run.json metrics block / web metrics.json",
            "note": "FP32 numbers come from the PyTorch checkpoint used for export; INT8 is the file served in the browser.",
        },
    }

    (RESULTS / "served_int8_test.json").write_text(json.dumps(out, indent=2))
    (RESULTS / "served_int8_per_image.json").write_text(json.dumps(per_image, indent=2))
    print(
        f"INT8 Dice={d_mean:.3f} [{d_lo:.3f},{d_hi:.3f}]  "
        f"lesion={ld_mean:.3f}  AUC={auc:.3f}  "
        f"normal FP={len(normal_fp)}/{len(normals)}"
    )

    # Merge into web metrics.json
    metrics_path = WEB_PUBLIC / "results" / "metrics.json"
    web = json.loads(metrics_path.read_text())
    fp32 = web.get("metrics", {})
    web["schema_version"] = 2
    web["model_version"] = "1.0.0"
    web["served_int8"] = {
        "label": out["label"],
        "sha256": sha,
        "seg_threshold": seg_thresh,
        "min_component_area": min_area,
        "test_dice": d_mean,
        "test_dice_bootstrap_95ci": [d_lo, d_hi],
        "test_iou": i_mean,
        "test_iou_bootstrap_95ci": [i_lo, i_hi],
        "lesion_dice": ld_mean,
        "lesion_dice_bootstrap_95ci": [ld_lo, ld_hi],
        "by_label": by_label,
        "cls_roc_auc": auc,
        "cls_sensitivity": float(sens),
        "cls_specificity": float(spec),
        "cls_ece": float(ece),
        "normal_false_positive_count": len(normal_fp),
        "normal_n": len(normals),
        "normal_false_positive_rate": normal_fp_rate,
        "delta_vs_fp32": {
            "test_dice": d_mean - float(fp32.get("test_dice", d_mean)),
            "lesion_dice": ld_mean - float(fp32.get("lesion_dice", ld_mean)),
            "cls_roc_auc": auc - float(fp32.get("cls_roc_auc", auc)),
        },
    }
    web["metrics_source"] = {
        "fp32_pytorch": "results/full_run.json (training checkpoint)",
        "int8_served": "results/served_int8_test.json (onnxruntime CPU, same postprocess)",
    }
    metrics_path.write_text(json.dumps(web, indent=2))
    print(f"Updated {metrics_path}")


if __name__ == "__main__":
    main()
