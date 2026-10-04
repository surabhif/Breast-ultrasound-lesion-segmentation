#!/usr/bin/env python3
"""Full training: ResNet-18 U-Net with ImageNet encoder + aux classification head.

Improvements vs first pass:
  - Paired image/mask augmentations (critical)
  - Soft Dice + pos-weighted BCE
  - Checkpoint / early-stop on *lesion* Dice (not dragged by FP on normals)
  - Longer schedule + cosine LR; brief encoder freeze then fine-tune
  - Val-only threshold + small-component post-process selection
  - Slim bilinear decoder aimed at ≤15 MB INT8 ONNX

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
    remove_small_components,
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


def set_encoder_requires_grad(model: torch.nn.Module, enabled: bool) -> None:
    if not hasattr(model, "layer4"):
        return
    for name, p in model.named_parameters():
        if name.startswith(("stem", "layer1", "layer2", "layer3", "layer4", "pool")):
            p.requires_grad = enabled


@torch.no_grad()
def predict_batch(model, images):
    seg_logits, cls_logits = model(images)
    return torch.sigmoid(seg_logits).cpu().numpy(), torch.sigmoid(cls_logits).cpu().numpy()


def score_predictions(
    seg_probs: list[np.ndarray],
    gts: list[np.ndarray],
    labels: list[str],
    cls_probs: list[float],
    cls_targets: list[float],
    case_ids: list[str],
    annotation_flags: list[bool],
    seg_thresh: float,
    min_area: int,
    cls_thresh: float = 0.5,
) -> dict:
    per_image = []
    for i in range(len(seg_probs)):
        pred = seg_probs[i] > seg_thresh
        if min_area > 0:
            pred = remove_small_components(pred, min_area)
        gt = gts[i] > 0.5
        d = dice_score(pred, gt)
        iou = iou_score(pred, gt)
        per_image.append(
            {
                "case_id": case_ids[i],
                "label": labels[i],
                "dice": d,
                "iou": iou,
                "annotation_flag": annotation_flags[i],
                "cls_target": cls_targets[i],
                "cls_prob": cls_probs[i],
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
                "iou_mean": float(np.mean([r["iou"] for r in per_image if r["label"] == lab])),
            }

    lesion_dice = np.array([r["dice"] for r in per_image if r["label"] != "normal"])
    ld_mean, ld_lo, ld_hi = bootstrap_ci(lesion_dice) if len(lesion_dice) else (float("nan"),) * 3

    out: dict = {
        "n": len(per_image),
        "seg_threshold": seg_thresh,
        "min_component_area": min_area,
        "dice_mean": d_mean,
        "dice_ci95": [d_lo, d_hi],
        "iou_mean": i_mean,
        "iou_ci95": [i_lo, i_hi],
        "lesion_dice_mean": ld_mean,
        "lesion_dice_ci95": [ld_lo, ld_hi],
        "by_label": by_label,
        "per_image": per_image,
    }

    cls_p = [r["cls_prob"] for r in per_image if r["cls_target"] >= 0]
    cls_y = [int(r["cls_target"]) for r in per_image if r["cls_target"] >= 0]
    if cls_y:
        from sklearn.metrics import (
            accuracy_score,
            confusion_matrix,
            roc_auc_score,
            roc_curve,
        )

        y = np.array(cls_y)
        p = np.array(cls_p)
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


@torch.no_grad()
def collect_raw(model, loader) -> dict:
    model.eval()
    seg_probs, gts, labels, cls_probs, cls_targets, case_ids, flags = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    for batch in loader:
        images = batch["image"].to(DEVICE)
        sp, cp = predict_batch(model, images)
        masks = batch["mask"].numpy()
        for i in range(images.size(0)):
            seg_probs.append(sp[i, 0])
            gts.append(masks[i, 0])
            labels.append(batch["label"][i])
            cls_probs.append(float(cp[i]))
            cls_targets.append(float(batch["cls_target"][i]))
            case_ids.append(batch["case_id"][i])
            flags.append(bool(batch["annotation_flag"][i]))
    return {
        "seg_probs": seg_probs,
        "gts": gts,
        "labels": labels,
        "cls_probs": cls_probs,
        "cls_targets": cls_targets,
        "case_ids": case_ids,
        "annotation_flags": flags,
    }


def evaluate_detailed(
    model, loader, seg_thresh: float = 0.5, min_area: int = 0, cls_thresh: float = 0.5
) -> dict:
    raw = collect_raw(model, loader)
    return score_predictions(
        raw["seg_probs"],
        raw["gts"],
        raw["labels"],
        raw["cls_probs"],
        raw["cls_targets"],
        raw["case_ids"],
        raw["annotation_flags"],
        seg_thresh=seg_thresh,
        min_area=min_area,
        cls_thresh=cls_thresh,
    )


def tune_postprocess_on_val(raw_val: dict) -> tuple[float, int, dict]:
    """Select seg threshold + min component area using lesion Dice on validation only."""
    best = (-1.0, 0.5, 0, {})
    for thr in [0.35, 0.40, 0.45, 0.50, 0.55, 0.60]:
        for min_area in [0, 20, 40, 80, 120]:
            metrics = score_predictions(
                raw_val["seg_probs"],
                raw_val["gts"],
                raw_val["labels"],
                raw_val["cls_probs"],
                raw_val["cls_targets"],
                raw_val["case_ids"],
                raw_val["annotation_flags"],
                seg_thresh=thr,
                min_area=min_area,
            )
            score = metrics["lesion_dice_mean"]
            if score > best[0]:
                best = (score, thr, min_area, metrics)
    return best[1], best[2], best[3]


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
    summaries = []
    for fold in splits["folds"]:
        set_seed(args.seed + fold["fold"])
        train_ds = BusiDataset(manifest, fold["train_ids"], img_size=args.img_size, augment=True)
        val_ds = BusiDataset(manifest, fold["val_ids"], img_size=args.img_size, augment=False)
        train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=0)
        val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=0)
        model = build_model(args.model, pretrained=args.pretrained).to(DEVICE)
        opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
        best = -1.0
        for _ in range(args.cv_epochs):
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
            best = max(best, metrics["lesion_dice_mean"])
        summaries.append(
            {
                "fold": fold["fold"],
                "val_lesion_dice": best,
                "n_train": len(train_ds),
                "n_val": len(val_ds),
            }
        )
        print(f"CV fold {fold['fold']}: best val lesion Dice={best:.3f}")
    return summaries


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="resnet18")
    ap.add_argument("--img-size", type=int, default=160)
    ap.add_argument("--epochs", type=int, default=35)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--lr", type=float, default=8e-4)
    ap.add_argument("--cls-weight", type=float, default=0.25)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--fold", type=int, default=0)
    ap.add_argument("--patience", type=int, default=8)
    ap.add_argument("--freeze-epochs", type=int, default=3)
    ap.add_argument("--pretrained", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--run-cv", action="store_true")
    ap.add_argument("--cv-epochs", type=int, default=5)
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
    if args.freeze_epochs > 0:
        set_encoder_requires_grad(model, False)
        print(f"Encoder frozen for first {args.freeze_epochs} epochs")

    opt = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.lr,
        weight_decay=1e-4,
    )
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs, eta_min=1e-5)

    n_params = sum(p.numel() for p in model.parameters()) / 1e6
    print(f"Device={DEVICE} model={args.model} size={args.img_size} params={n_params:.2f}M")
    print(f"train={len(train_ds)} val={len(val_ds)} test={len(test_ds)}")
    t0 = time.time()
    history = []
    best_lesion = -1.0
    stale = 0
    best_path = EXPORT_DIR / "full_best.pt"
    encoder_unfrozen = args.freeze_epochs <= 0

    for epoch in range(1, args.epochs + 1):
        if (not encoder_unfrozen) and epoch > args.freeze_epochs:
            set_encoder_requires_grad(model, True)
            opt = torch.optim.AdamW(model.parameters(), lr=args.lr * 0.5, weight_decay=1e-4)
            remaining = args.epochs - epoch + 1
            sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=remaining, eta_min=1e-5)
            encoder_unfrozen = True
            print(f"Encoder unfrozen at epoch {epoch}; lr={args.lr * 0.5}")

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
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            losses.append(float(loss.detach().cpu()))
            pbar.set_postfix(loss=np.mean(losses[-20:]), lr=opt.param_groups[0]["lr"])

        val_metrics = evaluate_detailed(model, val_loader, seg_thresh=0.5, min_area=0)
        row = {
            "epoch": epoch,
            "train_loss": float(np.mean(losses)),
            "lr": float(opt.param_groups[0]["lr"]),
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
        sched.step()

        if val_metrics["lesion_dice_mean"] > best_lesion:
            best_lesion = val_metrics["lesion_dice_mean"]
            stale = 0
            val_summary = {k: v for k, v in val_metrics.items() if k != "per_image"}
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

    print("Tuning threshold / min-area on validation (not test)…")
    raw_val = collect_raw(model, val_loader)
    best_thr, best_area, tuned_val = tune_postprocess_on_val(raw_val)
    print(
        f"  selected thr={best_thr} min_area={best_area} "
        f"val_lesion_dice={tuned_val['lesion_dice_mean']:.3f}"
    )

    raw_test = collect_raw(model, test_loader)
    test_metrics = score_predictions(
        raw_test["seg_probs"],
        raw_test["gts"],
        raw_test["labels"],
        raw_test["cls_probs"],
        raw_test["cls_targets"],
        raw_test["case_ids"],
        raw_test["annotation_flags"],
        seg_thresh=best_thr,
        min_area=best_area,
    )
    test_summary = {k: v for k, v in test_metrics.items() if k != "per_image"}

    per_image_path = RESULTS / "full_test_per_image.json"
    per_image_path.write_text(json.dumps(test_metrics["per_image"], indent=2))

    # Persist postprocess knobs for web/docs
    post = {
        "seg_threshold": best_thr,
        "min_component_area": best_area,
        "selected_on": "validation_lesion_dice",
        "val_lesion_dice_at_selection": tuned_val["lesion_dice_mean"],
    }
    (RESULTS / "postprocess.json").write_text(json.dumps(post, indent=2))

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
        "run_id": "full_resnet18_unet_v2",
        "note": (
            "ResNet-18 U-Net (slim bilinear decoder) with ImageNet encoder; "
            "paired augmentations; checkpointed on lesion Dice; val-tuned threshold/min-area."
        ),
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
            "freeze_epochs": args.freeze_epochs,
            "augmentation": [
                "paired_hflip",
                "paired_vflip",
                "paired_rotation20",
                "paired_scale_crop",
                "brightness_contrast",
            ],
            "loss": "pos-weighted BCE + soft Dice (seg) + BCE (cls on B/M only)",
            "optimizer": "AdamW + cosine",
            "selection_metric": "val_lesion_dice",
            "postprocess": post,
            "params_millions": round(n_params, 3),
        },
        "subset_sizes": {
            "train": len(train_ds),
            "val": len(val_ds),
            "test": len(test_ds),
        },
        "runtime_seconds": runtime,
        "metrics": {
            "best_val_lesion_dice": best_lesion,
            "val_after_postprocess": {
                k: v for k, v in tuned_val.items() if k != "per_image"
            },
            "test": test_summary,
            "history": history,
            "cv_summary": cv_summary,
        },
        "artifacts": {
            "checkpoint": str(best_path.relative_to(REPO)),
            "per_image": str(per_image_path.relative_to(REPO)),
            "postprocess": "results/postprocess.json",
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
