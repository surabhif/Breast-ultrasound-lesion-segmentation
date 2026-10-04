#!/usr/bin/env python3
"""Export metrics, failure gallery, and web/public/results/metrics.json from a trained checkpoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw
from torch.utils.data import DataLoader

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import (  # noqa: E402
    EXPORT_DIR,
    RESULTS,
    WEB_PUBLIC,
    BusiDataset,
    dice_score,
    load_manifest,
    load_splits,
    remove_small_components,
)
from model_def import build_model  # noqa: E402
from train_full import evaluate_detailed  # noqa: E402

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def load_postprocess() -> tuple[float, int]:
    path = RESULTS / "postprocess.json"
    if path.exists():
        pp = json.loads(path.read_text())
        return float(pp.get("seg_threshold", 0.5)), int(pp.get("min_component_area", 0))
    return 0.5, 0


def draw_overlay(image: Image.Image, gt_mask: np.ndarray, pred_mask: np.ndarray) -> Image.Image:
    """RGB overlay: GT outline in green, prediction in magenta fill+outline."""
    img = image.convert("RGBA").resize((256, 256))
    gt = Image.fromarray((gt_mask.astype(np.uint8) * 255)).resize((256, 256), Image.NEAREST)
    pr = Image.fromarray((pred_mask.astype(np.uint8) * 255)).resize((256, 256), Image.NEAREST)
    gt_arr = np.array(gt) > 127
    pr_arr = np.array(pr) > 127

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    px = overlay.load()
    for y in range(256):
        for x in range(256):
            if pr_arr[y, x]:
                px[x, y] = (200, 40, 120, 90)
    img = Image.alpha_composite(img, overlay)

    draw = ImageDraw.Draw(img)
    # Simple outline via morphological edge approx
    def edges(m: np.ndarray) -> np.ndarray:
        from scipy import ndimage

        eroded = ndimage.binary_erosion(m)
        return m & ~eroded

    try:
        gt_e = edges(gt_arr)
        pr_e = edges(pr_arr)
    except Exception:
        gt_e, pr_e = gt_arr, pr_arr

    for y in range(256):
        for x in range(256):
            if gt_e[y, x]:
                draw.point((x, y), fill=(20, 160, 90, 255))
            if pr_e[y, x]:
                draw.point((x, y), fill=(220, 50, 50, 255))
    return img.convert("RGB")


def export_failure_gallery(
    model,
    manifest,
    test_ids,
    img_size: int,
    out_dir: Path,
    top_k: int = 8,
    seg_thresh: float = 0.5,
    min_area: int = 0,
) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ds = BusiDataset(manifest, test_ids, img_size=img_size, augment=False)
    loader = DataLoader(ds, batch_size=1, shuffle=False)
    model.eval()
    scored = []

    with torch.no_grad():
        for batch in loader:
            images = batch["image"].to(DEVICE)
            masks = batch["mask"].numpy()[0, 0]
            seg_logits, cls_logits = model(images)
            pred = torch.sigmoid(seg_logits)[0, 0].cpu().numpy() > seg_thresh
            if min_area > 0:
                pred = remove_small_components(pred, min_area)
            d = dice_score(pred, masks > 0.5)
            # Prefer lesion cases for failure gallery
            if batch["label"][0] == "normal" and masks.sum() == 0 and pred.sum() == 0:
                continue
            scored.append(
                {
                    "case_id": batch["case_id"][0],
                    "label": batch["label"][0],
                    "dice": d,
                    "cls_prob": float(torch.sigmoid(cls_logits)[0].cpu()),
                    "pred": pred,
                    "gt": masks > 0.5,
                    "image_path": manifest.set_index("case_id").loc[batch["case_id"][0], "image_path"],
                }
            )

    scored.sort(key=lambda r: r["dice"])
    gallery = []
    for i, row in enumerate(scored[:top_k]):
        img = Image.open(row["image_path"]).convert("RGB")
        vis = draw_overlay(img, row["gt"], row["pred"])
        fname = f"fail_{i:02d}.png"
        vis.save(out_dir / fname)
        gallery.append(
            {
                "src": f"results/mistakes/{fname}",
                "case_id": row["case_id"],
                "label": row["label"],
                "dice": round(row["dice"], 4),
                "cls_prob": round(row["cls_prob"], 4),
                "true_label": row["label"],
                "note": "Green=GT outline, magenta/red=prediction",
            }
        )
    return gallery


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", type=Path, default=EXPORT_DIR / "full_best.pt")
    ap.add_argument("--cleaning-report", type=Path, default=RESULTS / "cleaning_experiment.json")
    args = ap.parse_args()

    if not args.checkpoint.exists():
        raise SystemExit(f"Missing checkpoint {args.checkpoint}. Train first.")

    ckpt = torch.load(args.checkpoint, map_location=DEVICE, weights_only=False)
    img_size = int(ckpt.get("img_size", 160))
    model_kind = ckpt.get("model_kind", "resnet18")
    model = build_model(model_kind, pretrained=False).to(DEVICE)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    seg_thresh, min_area = load_postprocess()
    manifest = load_manifest()
    splits = load_splits()
    test_ids = splits["test_ids"]
    fold = splits["folds"][0]

    test_ds = BusiDataset(manifest, test_ids, img_size=img_size, augment=False)
    test_loader = DataLoader(test_ds, batch_size=8, shuffle=False)
    test_metrics = evaluate_detailed(
        model, test_loader, seg_thresh=seg_thresh, min_area=min_area
    )
    test_summary = {k: v for k, v in test_metrics.items() if k != "per_image"}

    mistakes_dir = WEB_PUBLIC / "results" / "mistakes"
    gallery = export_failure_gallery(
        model,
        manifest,
        test_ids,
        img_size,
        mistakes_dir,
        seg_thresh=seg_thresh,
        min_area=min_area,
    )

    full_run = {}
    full_run_path = RESULTS / "full_run.json"
    if full_run_path.exists():
        full_run = json.loads(full_run_path.read_text())

    cleaning = None
    if args.cleaning_report.exists():
        cleaning = json.loads(args.cleaning_report.read_text())

    # Model artifact info
    onnx_path = WEB_PUBLIC / "models" / "busi_unet.onnx"
    model_artifact = None
    if onnx_path.exists():
        mb = onnx_path.stat().st_size / (1024 * 1024)
        status = (WEB_PUBLIC / "models" / "MODEL_STATUS.txt").read_text().strip() if (
            WEB_PUBLIC / "models" / "MODEL_STATUS.txt"
        ).exists() else "trained"
        quant = RESULTS / "quantization_report.json"
        q = json.loads(quant.read_text()) if quant.exists() else {}
        model_artifact = {
            "path": "models/busi_unet.onnx",
            "served_mb": round(mb, 3),
            "quantization": q.get("method", "fp32"),
            "fp32_mb": q.get("fp32_mb"),
            "status": status,
        }

    cls = test_summary.get("classification") or {}

    metrics = {
        "schema_version": 1,
        "label": "BUSI lesion segmentation — ResNet-18 U-Net",
        "disclaimer": "Research demo, not for clinical use.",
        "surabhi_prompts": [
            "Why do near-duplicate images inflate BUSI scores if they leak across splits?",
            "How could caliper marks act as a shortcut for benign vs malignant?",
            "What does a poorly calibrated probability mean for a clinician?",
            "Why isn't a high Dice on normals (empty masks) very informative?",
        ],
        "config": full_run.get("config")
        or {
            "model_kind": model_kind,
            "img_size": img_size,
            "pretrained": ckpt.get("pretrained", True),
        },
        "subset_sizes": full_run.get("subset_sizes")
        or {"train": len(fold["train_ids"]), "val": len(fold["val_ids"]), "test": len(test_ids)},
        "hardware": full_run.get("hardware"),
        "runtime_seconds": full_run.get("runtime_seconds"),
        "splits_note": splits.get("note"),
        "metrics": {
            "test_dice": test_summary["dice_mean"],
            "test_dice_bootstrap_95ci": test_summary["dice_ci95"],
            "test_iou": test_summary["iou_mean"],
            "test_iou_bootstrap_95ci": test_summary["iou_ci95"],
            "lesion_dice": test_summary["lesion_dice_mean"],
            "lesion_dice_bootstrap_95ci": test_summary["lesion_dice_ci95"],
            "by_label": test_summary.get("by_label"),
            "bootstrap_resamples": 1000,
            "seg_threshold": test_summary["seg_threshold"],
            "best_val_dice": full_run.get("metrics", {}).get("best_val_dice"),
            "cls_roc_auc": cls.get("roc_auc"),
            "cls_sensitivity": cls.get("sensitivity"),
            "cls_specificity": cls.get("specificity"),
            "cls_accuracy": cls.get("accuracy"),
            "cls_ece": cls.get("ece"),
            "decision_threshold": cls.get("decision_threshold", 0.5),
            "confusion_matrix": cls.get("confusion_matrix"),
            "cv_summary": (full_run.get("metrics") or {}).get("cv_summary"),
        },
        "roc_curve": cls.get("roc_curve"),
        "calibration": cls.get("calibration"),
        "mistakes": gallery,
        "cleaning_experiment": cleaning,
        "model_artifact": model_artifact,
    }

    def _sanitize(obj):
        if isinstance(obj, float):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return obj
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        return obj

    out_path = WEB_PUBLIC / "results" / "metrics.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(_sanitize(metrics), indent=2))
    print(f"Wrote {out_path}")
    print(f"Gallery: {len(gallery)} failure cases → {mistakes_dir}")


if __name__ == "__main__":
    main()
