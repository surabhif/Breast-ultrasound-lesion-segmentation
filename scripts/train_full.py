#!/usr/bin/env python3
"""Full training: ResNet-18 U-Net with ImageNet encoder + aux classification head.

Designed to finish on CPU in reasonable time (128×128, ~12–20 epochs with early stop)
while still producing honest, decent segmentation metrics.

Writes:
  export/full_best.pt
  results/full_run.json
  web/public/models/busi_unet.onnx
"""

from __future__ import annotations

import argparse
import json
import platform
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader
from tqdm.auto import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import (  # noqa: E402
    EXPORT_DIR,
    RESULTS,
    WEB_PUBLIC,
    BusiDataset,
    bootstrap_ci,
    dice_score,
    expected_calibration_error,
    iou_score,
    load_manifest,
    load_splits,
)
from model_def import (  # noqa: E402
    OnnxExportWrapper,
    build_model,
    classification_loss,
    combined_seg_loss,
)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


@torch.no_grad()
def evaluate_detailed(model, loader, seg_thresh: float = 0.5, cls_thresh: float = 0.5) -> dict:
    model.eval()
    per_image = []
    cls_probs, cls_labels = [], []

    for batch in loader:
        images = batch["image"].to(DEVICE)
        masks = batch["mask"].to(DEVICE)
        seg_logits, cls_logits = model(images)
        seg_prob = torch.sigmoid(seg_logits).cpu().numpy()
        cls_prob = torch.sigmoid(cls_logits).cpu().numpy()
        gts = masks.cpu().numpy()

        for i in range(images.size(0)):
            pred = seg_prob[i, 0] > seg_thresh
            gt = gts[i, 0] > 0.5
            label = batch["label"][i]
            d = dice_score(pred, gt)
            iou = iou_score(pred, gt)
            row = {
                "case_id": batch["case_id"][i],
                "label": label,
                "dice": d,
                "iou": iou,
                "annotation_flag": bool(batch["annotation_flag"][i]),
                "cls_target": float(batch["cls_target"][i]),
                "cls_prob": float(cls_prob[i]),
                "gt_area": float(gt.sum()),
                "pred_area": float(pred.sum()),
            }
            per_image.append(row)
            if row["cls_target"] >= 0:
                cls_probs.append(row["cls_prob"])
                cls_labels.append(int(row["cls_target"]))

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
                "iou_mean": float(np.mean([r["iou"] for r in per_image if r["label"] == lab])),
            }

    # Lesion-only Dice (exclude normals where empty/empty inflates score)
    lesion_dice = np.array([r["dice"] for r in per_image if r["label"] != "normal"])
    ld_mean, ld_lo, ld_hi = bootstrap_ci(lesion_dice) if len(lesion_dice) else (float("nan"),) * 3

    out: dict = {
        "n": len(per_image),
        "seg_threshold": seg_thresh,
        "dice_mean": d_mean,
        "dice_ci95": [d_lo, d_hi],
        "iou_mean": i_mean,
        "iou_ci95": [i_lo, i_hi],
        "lesion_dice_mean": ld_mean,
        "lesion_dice_ci95": [ld_lo, ld_hi],
        "by_label": by_label,
        "per_image": per_image,
    }

    if cls_labels:
        from sklearn.metrics import (
            accuracy_score,
            confusion_matrix,
            roc_auc_score,
            roc_curve,
        )

        y = np.array(cls_labels)
        p = np.array(cls_probs)
        try:
            auc = float(roc_auc_score(y, p))
        except ValueError:
            auc = float("nan")
        pred = (p >= cls_thresh).astype(int)
        cm = confusion_matrix(y, pred, labels=[0, 1]).tolist()
        tn, fp, fn, tp = cm[0][0], cm[0][1], cm[1][0], cm[1][1]
        sens = tp / (tp + fn) if (tp + fn) else float("nan")
        spec = tn / (tn + fp) if (tn + fp) else float("nan")
        fpr, tpr, thr = roc_curve(y, p)
        # downsample ROC
        idx = np.linspace(0, len(fpr) - 1, min(200, len(fpr))).astype(int)
        roc = [
            {
                "fpr": float(fpr[i]),
                "tpr": float(tpr[i]),
                "threshold": float(thr[i]) if i < len(thr) else None,
            }
            for i in idx
        ]
        ece, calib = expected_calibration_error(p, y, n_bins=10)
        out["classification"] = {
            "n": int(len(y)),
            "decision_threshold": cls_thresh,
            "roc_auc": auc,
            "accuracy": float(accuracy_score(y, pred)),
            "sensitivity": float(sens),
            "specificity": float(spec),
            "ece": ece,
            "confusion_matrix": {
                "labels": ["benign", "malignant"],
                "matrix": cm,
                "row_means_true": True,
            },
            "roc_curve": roc,
            "calibration": calib,
        }
    return out


def export_onnx(model, path: Path, img_size: int) -> float:
    path.parent.mkdir(parents=True, exist_ok=True)
    wrapper = OnnxExportWrapper(model).to("cpu").eval()
    dummy = torch.randn(1, 3, img_size, img_size)
    torch.onnx.export(
        wrapper,
        dummy,
        str(path),
        input_names=["input"],
        output_names=["seg_mask", "cls_prob"],
        dynamic_axes={
            "input": {0: "batch"},
            "seg_mask": {0: "batch"},
            "cls_prob": {0: "batch"},
        },
        opset_version=18,
        do_constant_folding=True,
        dynamo=False,
    )
    return path.stat().st_size / (1024 * 1024)


def run_cv_summary(manifest, splits, args) -> list[dict]:
    """Optional lightweight CV: train short epochs per fold for summary only."""
    summaries = []
    for fold in splits["folds"]:
        set_seed(args.seed + fold["fold"])
        train_ds = BusiDataset(manifest, fold["train_ids"], img_size=args.img_size, augment=True)
        val_ds = BusiDataset(manifest, fold["val_ids"], img_size=args.img_size, augment=False)
        train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=0)
        val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=0)
        model = build_model(args.model, pretrained=args.pretrained).to(DEVICE)
        opt = torch.optim.Adam(model.parameters(), lr=args.lr)
        best = -1.0
        for epoch in range(1, args.cv_epochs + 1):
            model.train()
            for batch in train_loader:
                images = batch["image"].to(DEVICE)
                masks = batch["mask"].to(DEVICE)
                cls_t = batch["cls_target"].to(DEVICE)
                seg_logits, cls_logits = model(images)
                loss = combined_seg_loss(seg_logits, masks) + args.cls_weight * classification_loss(
                    cls_logits, cls_t
                )
                opt.zero_grad()
                loss.backward()
                opt.step()
            metrics = evaluate_detailed(model, val_loader)
            best = max(best, metrics["dice_mean"])
        summaries.append(
            {
                "fold": fold["fold"],
                "val_dice": best,
                "n_train": len(train_ds),
                "n_val": len(val_ds),
            }
        )
        print(f"CV fold {fold['fold']}: best val Dice={best:.3f}")
    return summaries


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="resnet18")
    ap.add_argument("--img-size", type=int, default=128)
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--cls-weight", type=float, default=0.4)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--fold", type=int, default=0, help="Which CV fold to use for train/val")
    ap.add_argument("--patience", type=int, default=5)
    ap.add_argument("--pretrained", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--run-cv", action="store_true", help="Also run short 5-fold CV summary")
    ap.add_argument("--cv-epochs", type=int, default=4)
    ap.add_argument("--skip-onnx", action="store_true")
    args = ap.parse_args()

    set_seed(args.seed)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest()
    splits = load_splits()
    fold = splits["folds"][args.fold]
    train_ids, val_ids, test_ids = fold["train_ids"], fold["val_ids"], splits["test_ids"]

    train_ds = BusiDataset(manifest, train_ids, img_size=args.img_size, augment=True)
    val_ds = BusiDataset(manifest, val_ids, img_size=args.img_size, augment=False)
    test_ds = BusiDataset(manifest, test_ids, img_size=args.img_size, augment=False)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=args.batch_size, shuffle=False, num_workers=0)

    model = build_model(args.model, pretrained=args.pretrained).to(DEVICE)
    opt = torch.optim.Adam(model.parameters(), lr=args.lr)
    sched = torch.optim.lr_scheduler.ReduceLROnPlateau(opt, mode="max", factor=0.5, patience=2)

    print(f"Device={DEVICE} model={args.model} size={args.img_size}")
    print(f"train={len(train_ds)} val={len(val_ds)} test={len(test_ds)}")
    t0 = time.time()
    history = []
    best_dice = -1.0
    stale = 0
    best_path = EXPORT_DIR / "full_best.pt"

    for epoch in range(1, args.epochs + 1):
        model.train()
        losses = []
        pbar = tqdm(train_loader, desc=f"epoch {epoch}/{args.epochs}")
        for batch in pbar:
            images = batch["image"].to(DEVICE)
            masks = batch["mask"].to(DEVICE)
            cls_t = batch["cls_target"].to(DEVICE)
            seg_logits, cls_logits = model(images)
            loss = combined_seg_loss(seg_logits, masks) + args.cls_weight * classification_loss(
                cls_logits, cls_t
            )
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss.detach().cpu()))
            pbar.set_postfix(loss=np.mean(losses[-20:]))

        val_metrics = evaluate_detailed(model, val_loader)
        # strip per_image from history to keep JSON small
        val_summary = {k: v for k, v in val_metrics.items() if k != "per_image"}
        row = {
            "epoch": epoch,
            "train_loss": float(np.mean(losses)),
            "val_dice": val_metrics["dice_mean"],
            "val_lesion_dice": val_metrics["lesion_dice_mean"],
            "val_auc": (val_metrics.get("classification") or {}).get("roc_auc"),
        }
        history.append(row)
        print(
            f"  val dice={val_metrics['dice_mean']:.3f} "
            f"lesion_dice={val_metrics['lesion_dice_mean']:.3f} "
            f"auc={row['val_auc']}"
        )
        sched.step(val_metrics["dice_mean"])

        if val_metrics["dice_mean"] > best_dice:
            best_dice = val_metrics["dice_mean"]
            stale = 0
            torch.save(
                {
                    "model_kind": args.model,
                    "img_size": args.img_size,
                    "pretrained": args.pretrained,
                    "state_dict": model.state_dict(),
                    "val_metrics": val_summary,
                    "epoch": epoch,
                    "config": vars(args),
                },
                best_path,
            )
        else:
            stale += 1
            if stale >= args.patience:
                print(f"Early stop at epoch {epoch}")
                break

    ckpt = torch.load(best_path, map_location=DEVICE, weights_only=False)
    model.load_state_dict(ckpt["state_dict"])
    test_metrics = evaluate_detailed(model, test_loader)
    test_summary = {k: v for k, v in test_metrics.items() if k != "per_image"}

    # Persist per-image for gallery / cleaning experiment
    per_image_path = RESULTS / "full_test_per_image.json"
    per_image_path.write_text(json.dumps(test_metrics["per_image"], indent=2))

    onnx_mb = None
    onnx_path = WEB_PUBLIC / "models" / "busi_unet.onnx"
    if not args.skip_onnx:
        onnx_mb = export_onnx(model, onnx_path, args.img_size)

    cv_summary = None
    if args.run_cv:
        print("Running short 5-fold CV summary…")
        cv_summary = run_cv_summary(manifest, splits, args)

    runtime = time.time() - t0
    report = {
        "run_id": "full_resnet18_unet",
        "note": "ResNet-18 U-Net with ImageNet encoder; normal images trained with empty masks.",
        "hardware": {
            "device": str(DEVICE),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
        },
        "config": {
            "model_kind": args.model,
            "img_size": args.img_size,
            "epochs_ran": len(history),
            "epochs_max": args.epochs,
            "batch_size": args.batch_size,
            "learning_rate": args.lr,
            "cls_weight": args.cls_weight,
            "seed": args.seed,
            "fold": args.fold,
            "pretrained": args.pretrained,
            "augmentation": [
                "hflip",
                "vflip",
                "rotation15",
                "color_jitter",
            ],
            "loss": "BCE+Dice (seg) + BCE (cls on B/M only)",
            "optimizer": "Adam",
        },
        "subset_sizes": {
            "train": len(train_ds),
            "val": len(val_ds),
            "test": len(test_ds),
        },
        "runtime_seconds": runtime,
        "metrics": {
            "best_val_dice": best_dice,
            "test": test_summary,
            "history": history,
            "cv_summary": cv_summary,
        },
        "artifacts": {
            "checkpoint": str(best_path.relative_to(REPO)),
            "per_image": str(per_image_path.relative_to(REPO)),
            "onnx": None if args.skip_onnx else str(onnx_path.relative_to(REPO)),
            "onnx_size_mb": None if onnx_mb is None else round(onnx_mb, 3),
        },
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

    out = RESULTS / "full_run.json"
    out.write_text(json.dumps(_sanitize(report), indent=2))
    print(f"Wrote {out}")
    tm = test_summary
    print(
        f"Test Dice={tm['dice_mean']:.3f} [{tm['dice_ci95'][0]:.3f},{tm['dice_ci95'][1]:.3f}] "
        f"lesion_Dice={tm['lesion_dice_mean']:.3f} "
        f"AUC={(tm.get('classification') or {}).get('roc_auc')} "
        f"ONNX={onnx_mb} MB  {runtime:.0f}s"
    )


if __name__ == "__main__":
    main()
