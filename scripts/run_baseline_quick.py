#!/usr/bin/env python3
"""Quick CPU baseline: tiny U-Net at low resolution, finishes in minutes.

Writes:
  export/quick_best.pt
  results/baseline_quick_run.json
  web/public/models/busi_unet.onnx  (overwritten later by full training if run)
"""

from __future__ import annotations

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

# Quick knobs — intentionally small for CPU minutes
MODEL_KIND = "tiny"
IMG_SIZE = 64
EPOCHS = 5
BATCH_SIZE = 8
LEARNING_RATE = 1e-3
SEG_WEIGHT = 1.0
CLS_WEIGHT = 0.3
SEED = 42
NUM_WORKERS = 0
FOLD = 0  # use fold 0 train/val; evaluate on held-out test

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def set_seed(seed: int = 42) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


@torch.no_grad()
def evaluate(model, loader) -> dict:
    model.eval()
    dice_vals, iou_vals = [], []
    cls_probs, cls_labels, cls_case = [], [], []
    seg_thresh = 0.5

    for batch in loader:
        images = batch["image"].to(DEVICE)
        masks = batch["mask"].to(DEVICE)
        seg_logits, cls_logits = model(images)
        seg_prob = torch.sigmoid(seg_logits)
        preds = (seg_prob > seg_thresh).cpu().numpy()
        gts = masks.cpu().numpy()
        for i in range(images.size(0)):
            # Skip pure-normal empty/empty from mean? Include all for honesty.
            dice_vals.append(dice_score(preds[i, 0], gts[i, 0]))
            iou_vals.append(iou_score(preds[i, 0], gts[i, 0]))
            target = float(batch["cls_target"][i])
            if target >= 0:
                cls_probs.append(float(torch.sigmoid(cls_logits[i]).cpu()))
                cls_labels.append(int(target))
                cls_case.append(batch["case_id"][i])

    d_mean, d_lo, d_hi = bootstrap_ci(np.array(dice_vals))
    i_mean, i_lo, i_hi = bootstrap_ci(np.array(iou_vals))
    out = {
        "n": len(dice_vals),
        "dice_mean": d_mean,
        "dice_ci95": [d_lo, d_hi],
        "iou_mean": i_mean,
        "iou_ci95": [i_lo, i_hi],
    }
    if cls_labels:
        from sklearn.metrics import roc_auc_score

        try:
            out["cls_auc"] = float(roc_auc_score(cls_labels, cls_probs))
        except ValueError:
            out["cls_auc"] = float("nan")
        out["n_cls"] = len(cls_labels)
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


def main() -> None:
    set_seed(SEED)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest()
    splits = load_splits()
    fold = splits["folds"][FOLD]
    train_ids, val_ids, test_ids = fold["train_ids"], fold["val_ids"], splits["test_ids"]

    train_ds = BusiDataset(manifest, train_ids, img_size=IMG_SIZE, augment=True)
    val_ds = BusiDataset(manifest, val_ids, img_size=IMG_SIZE, augment=False)
    test_ds = BusiDataset(manifest, test_ids, img_size=IMG_SIZE, augment=False)

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True, num_workers=NUM_WORKERS)
    val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=NUM_WORKERS)
    test_loader = DataLoader(test_ds, batch_size=BATCH_SIZE, shuffle=False, num_workers=NUM_WORKERS)

    model = build_model(MODEL_KIND, pretrained=False).to(DEVICE)
    opt = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)

    print(f"Device={DEVICE}  train={len(train_ds)} val={len(val_ds)} test={len(test_ds)}")
    t0 = time.time()
    history = []
    best_dice = -1.0
    best_path = EXPORT_DIR / "quick_best.pt"

    for epoch in range(1, EPOCHS + 1):
        model.train()
        losses = []
        pbar = tqdm(train_loader, desc=f"epoch {epoch}/{EPOCHS}")
        for batch in pbar:
            images = batch["image"].to(DEVICE)
            masks = batch["mask"].to(DEVICE)
            cls_t = batch["cls_target"].to(DEVICE)
            seg_logits, cls_logits = model(images)
            loss = SEG_WEIGHT * combined_seg_loss(seg_logits, masks) + CLS_WEIGHT * classification_loss(
                cls_logits, cls_t
            )
            opt.zero_grad()
            loss.backward()
            opt.step()
            losses.append(float(loss.detach().cpu()))
            pbar.set_postfix(loss=np.mean(losses[-20:]))

        val_metrics = evaluate(model, val_loader)
        row = {"epoch": epoch, "train_loss": float(np.mean(losses)), **{f"val_{k}": v for k, v in val_metrics.items()}}
        history.append(row)
        print(f"  val dice={val_metrics['dice_mean']:.3f} auc={val_metrics.get('cls_auc', float('nan')):.3f}")
        if val_metrics["dice_mean"] > best_dice:
            best_dice = val_metrics["dice_mean"]
            torch.save(
                {
                    "model_kind": MODEL_KIND,
                    "img_size": IMG_SIZE,
                    "state_dict": model.state_dict(),
                    "val_metrics": val_metrics,
                    "epoch": epoch,
                },
                best_path,
            )

    ckpt = torch.load(best_path, map_location=DEVICE, weights_only=False)
    model.load_state_dict(ckpt["state_dict"])
    test_metrics = evaluate(model, test_loader)

    onnx_path = WEB_PUBLIC / "models" / "busi_unet.onnx"
    onnx_mb = export_onnx(model, onnx_path, IMG_SIZE)
    runtime = time.time() - t0

    report = {
        "run_id": "baseline_quick",
        "note": "Tiny U-Net from scratch at 64×64 for a fast CPU baseline.",
        "hardware": {
            "device": str(DEVICE),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
        },
        "config": {
            "model_kind": MODEL_KIND,
            "img_size": IMG_SIZE,
            "epochs": EPOCHS,
            "batch_size": BATCH_SIZE,
            "learning_rate": LEARNING_RATE,
            "seg_weight": SEG_WEIGHT,
            "cls_weight": CLS_WEIGHT,
            "seed": SEED,
            "fold": FOLD,
            "pretrained": False,
        },
        "subset_sizes": {
            "train": len(train_ds),
            "val": len(val_ds),
            "test": len(test_ds),
        },
        "runtime_seconds": runtime,
        "metrics": {
            "best_val_dice": best_dice,
            "test": test_metrics,
            "history": history,
        },
        "artifacts": {
            "checkpoint": str(best_path.relative_to(REPO)),
            "onnx": str(onnx_path.relative_to(REPO)),
            "onnx_size_mb": round(onnx_mb, 3),
        },
    }
    out = RESULTS / "baseline_quick_run.json"
    out.write_text(json.dumps(report, indent=2))
    print(f"Wrote {out}")
    print(f"Test Dice={test_metrics['dice_mean']:.3f} IoU={test_metrics['iou_mean']:.3f} "
          f"AUC={test_metrics.get('cls_auc', float('nan')):.3f}  ONNX={onnx_mb:.2f} MB  {runtime:.0f}s")


if __name__ == "__main__":
    main()
