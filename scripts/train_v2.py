#!/usr/bin/env python3
"""Phase 4 v2 candidates under MODEL_POLICY (D3).

Train on BUSI train + patient-grouped BUS-BRA train; hold out BUS-BRA test;
leave BrEaST fully external. Try ResNet-34 @ 256, stronger aug, Dice+focal,
optional caliper Telea inpaint on flagged BUSI frames. ~3 seeds.

Writes results/v2_experiment.json (honest table + swap checks). Does NOT
promote weights — use scripts/apply_v2_swap.py after quantization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torchvision.transforms.functional as TF
from PIL import Image
from sklearn.model_selection import GroupShuffleSplit
from torch.utils.data import DataLoader, Dataset
from tqdm.auto import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import (  # noqa: E402
    EXPORT_DIR,
    PROCESSED,
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
    resize_rgb_bilinear,
)
from external.breast import build_manifest as build_breast  # noqa: E402
from external.busbra import build_manifest as build_busbra  # noqa: E402
from external.common import load_mask_binary, load_rgb  # noqa: E402
from inpaint_calipers import telea_inpaint  # noqa: E402
from caliper_masks import MASK_DIR, safe_name  # noqa: E402
from model_def import (  # noqa: E402
    OnnxExportWrapper,
    build_model,
    classification_loss,
    dice_focal_seg_loss,
)
from train_full import (  # noqa: E402
    collect_raw,
    evaluate_detailed,
    export_onnx,
    score_predictions,
    set_encoder_requires_grad,
    set_seed,
    tune_postprocess_on_val,
)

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
V2_DIR = EXPORT_DIR / "v2"
V2_RESULTS = RESULTS / "v2"


class MultiSegDataset(Dataset):
    """Unified BUSI + BUS-BRA rows with stronger paired augmentation."""

    def __init__(
        self,
        rows: pd.DataFrame,
        img_size: int = 256,
        augment: bool = False,
        use_inpaint: bool = False,
    ) -> None:
        self.df = rows.reset_index(drop=True)
        self.img_size = img_size
        self.augment = augment
        self.use_inpaint = use_inpaint

    def __len__(self) -> int:
        return len(self.df)

    def _load_image(self, row) -> Image.Image:
        path = Path(row["image_path"])
        if self.use_inpaint and bool(row.get("annotation_flag", False)):
            # Prefer precomputed Telea inpaint; fall back to on-the-fly.
            inpainted = PROCESSED / "inpainted" / f"{safe_name(row['case_id'])}.png"
            if inpainted.exists():
                return Image.open(inpainted).convert("RGB")
            cal = MASK_DIR / f"{safe_name(row['case_id'])}.png"
            if cal.exists():
                bgr = np.array(Image.open(path).convert("RGB"))[:, :, ::-1]
                m = np.array(Image.open(cal).convert("L"))
                if m.shape[:2] != bgr.shape[:2]:
                    m = np.array(
                        Image.fromarray(m).resize((bgr.shape[1], bgr.shape[0]), Image.NEAREST)
                    )
                out = telea_inpaint(bgr, m)[:, :, ::-1]
                return Image.fromarray(out)
        return Image.open(path).convert("RGB")

    def _load_mask(self, row) -> Image.Image:
        mp = row.get("merged_mask_path") or row.get("mask_path")
        if not mp or (isinstance(mp, float) and np.isnan(mp)):
            # Empty mask sized later from image
            return Image.new("L", (self.img_size, self.img_size), 0)
        return Image.open(mp).convert("L")

    def _strong_augment(self, img: Image.Image, mask: Image.Image) -> tuple[Image.Image, Image.Image]:
        if random.random() < 0.5:
            img, mask = TF.hflip(img), TF.hflip(mask)
        if random.random() < 0.5:
            img, mask = TF.vflip(img), TF.vflip(mask)
        angle = random.uniform(-30, 30)
        img = TF.rotate(img, angle, interpolation=TF.InterpolationMode.BILINEAR, fill=0)
        mask = TF.rotate(mask, angle, interpolation=TF.InterpolationMode.NEAREST, fill=0)
        if random.random() < 0.7:
            scale = random.uniform(0.75, 1.05)
            w, h = img.size
            nw, nh = max(8, int(w * scale)), max(8, int(h * scale))
            top = random.randint(0, max(0, h - nh)) if h >= nh else 0
            left = random.randint(0, max(0, w - nw)) if w >= nw else 0
            # If zoomed out, pad then crop center-ish
            if nh > h or nw > w:
                pad_h, pad_w = max(0, nh - h), max(0, nw - w)
                img = TF.pad(img, [pad_w // 2, pad_h // 2, pad_w - pad_w // 2, pad_h - pad_h // 2])
                mask = TF.pad(mask, [pad_w // 2, pad_h // 2, pad_w - pad_w // 2, pad_h - pad_h // 2])
                w, h = img.size
                top = random.randint(0, max(0, h - self.img_size)) if h > self.img_size else 0
                left = random.randint(0, max(0, w - self.img_size)) if w > self.img_size else 0
                img = TF.resized_crop(
                    img, top, left, min(h, self.img_size), min(w, self.img_size),
                    (self.img_size, self.img_size), interpolation=TF.InterpolationMode.BILINEAR,
                )
                mask = TF.resized_crop(
                    mask, top, left, min(h, self.img_size), min(w, self.img_size),
                    (self.img_size, self.img_size), interpolation=TF.InterpolationMode.NEAREST,
                )
                return img, mask
            img = TF.resized_crop(
                img, top, left, nh, nw, (h, w), interpolation=TF.InterpolationMode.BILINEAR
            )
            mask = TF.resized_crop(
                mask, top, left, nh, nw, (h, w), interpolation=TF.InterpolationMode.NEAREST
            )
        if random.random() < 0.3:
            # Elastic-ish: small affine shear
            shear = random.uniform(-8, 8)
            img = TF.affine(
                img, angle=0, translate=(0, 0), scale=1.0, shear=[shear, 0],
                interpolation=TF.InterpolationMode.BILINEAR, fill=0,
            )
            mask = TF.affine(
                mask, angle=0, translate=(0, 0), scale=1.0, shear=[shear, 0],
                interpolation=TF.InterpolationMode.NEAREST, fill=0,
            )
        return img, mask

    def __getitem__(self, idx: int) -> dict:
        row = self.df.iloc[idx]
        img = self._load_image(row)
        mask = self._load_mask(row)
        if mask.size != img.size:
            mask = mask.resize(img.size, Image.NEAREST)

        if self.augment:
            img, mask = self._strong_augment(img, mask)

        img = TF.resize(img, [self.img_size, self.img_size], interpolation=TF.InterpolationMode.BILINEAR)
        mask = TF.resize(mask, [self.img_size, self.img_size], interpolation=TF.InterpolationMode.NEAREST)

        if self.augment:
            if random.random() < 0.9:
                img = TF.adjust_brightness(img, random.uniform(0.7, 1.3))
            if random.random() < 0.9:
                img = TF.adjust_contrast(img, random.uniform(0.7, 1.35))
            if random.random() < 0.5:
                img = TF.adjust_gamma(img, random.uniform(0.8, 1.25))

        from model_def import IMAGENET_MEAN, IMAGENET_STD

        x = TF.normalize(TF.to_tensor(img), IMAGENET_MEAN, IMAGENET_STD)
        y_seg = (TF.to_tensor(mask) > 0.5).float()
        y_cls = torch.tensor(float(row["cls_target"]), dtype=torch.float32)
        return {
            "image": x,
            "mask": y_seg,
            "cls_target": y_cls,
            "label": row["label"],
            "case_id": str(row["case_id"]),
            "annotation_flag": bool(row.get("annotation_flag", False)),
        }


def busi_rows(manifest: pd.DataFrame, ids: list[str]) -> pd.DataFrame:
    id_set = set(ids)
    df = manifest[manifest["case_id"].isin(id_set)].copy()
    df["dataset"] = "busi"
    df["merged_mask_path"] = df["merged_mask_path"]
    return df


def busbra_patient_split(seed: int = 42, test_frac: float = 0.25) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Patient-grouped BUS-BRA train / held-out test (BrEaST stays external)."""
    man = build_busbra()
    man = man.copy()
    man["cls_target"] = man["label"].map({"benign": 0.0, "malignant": 1.0}).fillna(-1.0)
    man["annotation_flag"] = False
    man["merged_mask_path"] = man["mask_path"]
    gss = GroupShuffleSplit(n_splits=1, test_size=test_frac, random_state=seed)
    idx = np.arange(len(man))
    tr, te = next(gss.split(idx, man["label"], groups=man["patient_id"]))
    train_df = man.iloc[tr].reset_index(drop=True)
    test_df = man.iloc[te].reset_index(drop=True)
    return train_df, test_df


@torch.no_grad()
def eval_external_pt(
    model,
    manifest: pd.DataFrame,
    img_size: int,
    seg_thresh: float,
    min_area: int,
) -> dict:
    model.eval()
    per = []
    for _, r in tqdm(manifest.iterrows(), total=len(manifest), desc="ext"):
        rgb = load_rgb(r["image_path"])
        x = imagenet_tensor_from_rgb(rgb, img_size)
        t = torch.from_numpy(x).to(DEVICE)
        seg_logits, cls_logits = model(t)
        soft = torch.sigmoid(seg_logits)[0, 0].cpu().numpy()
        cls_prob = float(torch.sigmoid(cls_logits).reshape(-1)[0].cpu())
        pred = soft > seg_thresh
        if min_area > 0:
            pred = remove_small_components(pred, min_area)
        gt = load_mask_binary(r["mask_path"] if r.get("mask_path") else None, img_size)
        if r["label"] == "normal":
            gt = np.zeros_like(gt)
        d = dice_score(pred, gt)
        per.append(
            {
                "case_id": r["case_id"],
                "label": r["label"],
                "patient_id": r.get("patient_id"),
                "dice": d,
                "iou": iou_score(pred, gt),
                "cls_prob": cls_prob,
                "cls_target": 1.0 if r["label"] == "malignant" else (0.0 if r["label"] == "benign" else None),
            }
        )
    df = pd.DataFrame(per)
    d_mean, d_lo, d_hi = bootstrap_ci(df["dice"].to_numpy())
    lesion = df[df["label"].isin(["benign", "malignant"])]
    ld_mean, ld_lo, ld_hi = bootstrap_ci(lesion["dice"].to_numpy()) if len(lesion) else (float("nan"),) * 3
    auc = None
    bm = df[df["label"].isin(["benign", "malignant"])].dropna(subset=["cls_target"])
    if len(bm) >= 5:
        from sklearn.metrics import roc_auc_score

        try:
            auc = float(roc_auc_score(bm["cls_target"].to_numpy(dtype=float), bm["cls_prob"].to_numpy(dtype=float)))
        except ValueError:
            auc = None
    return {
        "n": int(len(df)),
        "n_patients": int(df["patient_id"].nunique()) if "patient_id" in df else None,
        "dice_mean": d_mean,
        "dice_ci95": [d_lo, d_hi],
        "lesion_dice_mean": ld_mean,
        "lesion_dice_ci95": [ld_lo, ld_hi],
        "cls_roc_auc": auc,
    }


def quantize_onnx(fp32: Path, int8: Path) -> float:
    from onnxruntime.quantization import QuantType, quantize_dynamic

    quantize_dynamic(model_input=str(fp32), model_output=str(int8), weight_type=QuantType.QUInt8)
    return int8.stat().st_size / (1024 * 1024)


def train_one_seed(args, seed: int, busi_man, busi_splits, busbra_train, busbra_test, breast_man) -> dict:
    set_seed(seed)
    fold = busi_splits["folds"][0]
    busi_train = busi_rows(busi_man, fold["train_ids"])
    busi_val = busi_rows(busi_man, fold["val_ids"])
    busi_test = busi_rows(busi_man, busi_splits["test_ids"])

    train_df = pd.concat([busi_train, busbra_train], ignore_index=True)
    val_df = busi_val  # BUSI val only for early-stop / postprocess (no BUS-BRA leakage into knobs)

    train_ds = MultiSegDataset(
        train_df, img_size=args.img_size, augment=True, use_inpaint=args.inpaint
    )
    val_ds = MultiSegDataset(val_df, img_size=args.img_size, augment=False, use_inpaint=False)
    test_ds = MultiSegDataset(busi_test, img_size=args.img_size, augment=False, use_inpaint=False)

    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=args.batch_size, shuffle=False, num_workers=0)

    model = build_model(args.model, pretrained=True).to(DEVICE)
    if args.freeze_epochs > 0:
        set_encoder_requires_grad(model, False)

    opt = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=args.lr,
        weight_decay=1e-4,
    )
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs, eta_min=1e-5)
    n_params = sum(p.numel() for p in model.parameters()) / 1e6
    print(
        f"[seed {seed}] device={DEVICE} model={args.model} size={args.img_size} "
        f"params={n_params:.2f}M train={len(train_ds)} (BUSI {len(busi_train)}+"
        f"BUSBRA {len(busbra_train)}) val={len(val_ds)} test={len(test_ds)}"
    )

    best_lesion = -1.0
    stale = 0
    history = []
    ckpt_path = V2_DIR / f"seed{seed}_best.pt"
    encoder_unfrozen = args.freeze_epochs <= 0
    t0 = time.time()

    for epoch in range(1, args.epochs + 1):
        if (not encoder_unfrozen) and epoch > args.freeze_epochs:
            set_encoder_requires_grad(model, True)
            opt = torch.optim.AdamW(model.parameters(), lr=args.lr * 0.5, weight_decay=1e-4)
            remaining = args.epochs - epoch + 1
            sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=remaining, eta_min=1e-5)
            encoder_unfrozen = True
            print(f"[seed {seed}] encoder unfrozen @ epoch {epoch}")

        model.train()
        losses = []
        pbar = tqdm(train_loader, desc=f"seed{seed} ep{epoch}/{args.epochs}")
        for batch in pbar:
            images = batch["image"].to(DEVICE)
            masks = batch["mask"].to(DEVICE)
            cls_t = batch["cls_target"].to(DEVICE)
            seg_logits, cls_logits = model(images)
            loss = dice_focal_seg_loss(seg_logits, masks) + args.cls_weight * classification_loss(
                cls_logits, cls_t
            )
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            losses.append(float(loss.detach().cpu()))
            pbar.set_postfix(loss=np.mean(losses[-20:]))

        val_metrics = evaluate_detailed(model, val_loader, seg_thresh=0.5, min_area=0)
        history.append(
            {
                "epoch": epoch,
                "train_loss": float(np.mean(losses)),
                "val_dice": val_metrics["dice_mean"],
                "val_lesion_dice": val_metrics["lesion_dice_mean"],
                "val_auc": (val_metrics.get("classification") or {}).get("roc_auc"),
            }
        )
        print(
            f"  [seed {seed}] val lesion_dice={val_metrics['lesion_dice_mean']:.3f} "
            f"dice={val_metrics['dice_mean']:.3f}"
        )
        sched.step()

        if val_metrics["lesion_dice_mean"] > best_lesion:
            best_lesion = val_metrics["lesion_dice_mean"]
            stale = 0
            torch.save(
                {
                    "model_kind": args.model,
                    "img_size": args.img_size,
                    "state_dict": model.state_dict(),
                    "epoch": epoch,
                    "seed": seed,
                    "val_lesion_dice": best_lesion,
                },
                ckpt_path,
            )
        else:
            stale += 1
            if stale >= args.patience:
                print(f"[seed {seed}] early stop @ epoch {epoch}")
                break

    ckpt = torch.load(ckpt_path, map_location=DEVICE, weights_only=False)
    model.load_state_dict(ckpt["state_dict"])

    raw_val = collect_raw(model, val_loader)
    best_thr, best_area, tuned_val = tune_postprocess_on_val(raw_val)

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
    # Clean-subset Dice (annotation_flag == false)
    clean_idx = [i for i, f in enumerate(raw_test["annotation_flags"]) if not f]
    clean_metrics = score_predictions(
        [raw_test["seg_probs"][i] for i in clean_idx],
        [raw_test["gts"][i] for i in clean_idx],
        [raw_test["labels"][i] for i in clean_idx],
        [raw_test["cls_probs"][i] for i in clean_idx],
        [raw_test["cls_targets"][i] for i in clean_idx],
        [raw_test["case_ids"][i] for i in clean_idx],
        [False] * len(clean_idx),
        seg_thresh=best_thr,
        min_area=best_area,
    )

    busbra_metrics = eval_external_pt(model, busbra_test, args.img_size, best_thr, best_area)
    breast_metrics = eval_external_pt(model, breast_man, args.img_size, best_thr, best_area)

    fp32_onnx = V2_DIR / f"seed{seed}_fp32.onnx"
    int8_onnx = V2_DIR / f"seed{seed}_int8.onnx"
    fp32_mb = export_onnx(model, fp32_onnx, args.img_size)
    int8_mb = quantize_onnx(fp32_onnx, int8_onnx)
    sha = hashlib.sha256(int8_onnx.read_bytes()).hexdigest()

    runtime = time.time() - t0
    test_summary = {k: v for k, v in test_metrics.items() if k != "per_image"}
    clean_summary = {k: v for k, v in clean_metrics.items() if k != "per_image"}
    out = {
        "seed": seed,
        "model_kind": args.model,
        "img_size": args.img_size,
        "params_millions": round(n_params, 3),
        "epochs_ran": len(history),
        "runtime_seconds": runtime,
        "postprocess": {"seg_threshold": best_thr, "min_component_area": best_area},
        "best_val_lesion_dice": best_lesion,
        "test_original": test_summary,
        "test_clean_subset": clean_summary,
        "external_busbra_heldout": busbra_metrics,
        "external_breast": breast_metrics,
        "onnx_fp32_mb": round(fp32_mb, 3),
        "onnx_int8_mb": round(int8_mb, 3),
        "onnx_int8": str(int8_onnx),
        "onnx_sha256": sha,
        "history": history,
        "subset_sizes": {
            "train_total": len(train_ds),
            "train_busi": len(busi_train),
            "train_busbra": len(busbra_train),
            "val_busi": len(val_ds),
            "test_busi": len(test_ds),
            "test_busbra_heldout": len(busbra_test),
            "breast_external": len(breast_man),
        },
        "failures": [],
    }
    if int8_mb > 25.5:
        out["failures"].append(f"INT8 ONNX {int8_mb:.1f} MB exceeds ~25 MB budget")
    print(
        f"[seed {seed}] DONE test_dice={test_summary['dice_mean']:.3f} "
        f"clean={clean_summary['dice_mean']:.3f} "
        f"BUS-BRA={busbra_metrics['dice_mean']:.3f} BrEaST={breast_metrics['dice_mean']:.3f} "
        f"AUC={(test_summary.get('classification') or {}).get('roc_auc')} "
        f"INT8={int8_mb:.1f}MB {runtime:.0f}s"
    )
    return out


def load_v1_baselines() -> dict:
    metrics = json.loads((WEB_PUBLIC / "results" / "metrics.json").read_text())
    clean = (
        (metrics.get("cleaning_experiment") or {})
        .get("full_model_clean_vs_flagged", {})
        .get("clean_test", {})
        .get("dice_mean")
    )
    # Prefer served INT8 external numbers (protocol freeze)
    ext = metrics.get("external") or {}
    datasets = ext.get("datasets") or {}
    busbra = (datasets.get("busbra") or {}).get("test_dice")
    breast = (datasets.get("breast") or {}).get("test_dice")
    auc = (ext.get("internal_busi_int8") or {}).get("cls_roc_auc")
    if auc is None:
        auc = (metrics.get("served_int8") or {}).get("cls_roc_auc")
    served = metrics.get("served_int8") or metrics.get("metrics") or {}
    return {
        "clean_dice": clean,
        "busbra_dice": busbra,
        "breast_dice": breast,
        "auc": auc,
        "test_dice": served.get("test_dice"),
        "lesion_dice": served.get("lesion_dice"),
        "int8_mb": 12.0,  # approx; overwritten from model file if present
    }


def apply_swap_checks(candidate: dict, v1: dict) -> dict:
    c_clean = (candidate.get("test_clean_subset") or {}).get("dice_mean")
    c_auc = (candidate.get("test_original") or {}).get("classification", {}) or {}
    if isinstance(c_auc, dict):
        c_auc = c_auc.get("roc_auc")
    c_busbra = (candidate.get("external_busbra_heldout") or {}).get("dice_mean")
    c_breast = (candidate.get("external_breast") or {}).get("dice_mean")
    int8_mb = candidate.get("onnx_int8_mb")
    checks = {
        "clean_dice_ok": c_clean is not None and v1["clean_dice"] is not None and c_clean >= v1["clean_dice"] - 1e-9,
        "busbra_ok": c_busbra is not None and v1["busbra_dice"] is not None and c_busbra >= v1["busbra_dice"] - 1e-9,
        "breast_ok": c_breast is not None and v1["breast_dice"] is not None and c_breast >= v1["breast_dice"] - 1e-9,
        "auc_ok": c_auc is not None and v1["auc"] is not None and (v1["auc"] - c_auc) <= 0.02 + 1e-9,
        "size_ok": int8_mb is not None and int8_mb <= 25.5,
    }
    return {
        "checks": checks,
        "swap_ok": all(checks.values()),
        "v2": {
            "clean_dice": c_clean,
            "busbra_dice": c_busbra,
            "breast_dice": c_breast,
            "auc": c_auc,
            "int8_mb": int8_mb,
            "test_dice": (candidate.get("test_original") or {}).get("dice_mean"),
            "lesion_dice": (candidate.get("test_original") or {}).get("lesion_dice_mean"),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="resnet34")
    ap.add_argument("--img-size", type=int, default=256)
    ap.add_argument("--epochs", type=int, default=14)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--lr", type=float, default=6e-4)
    ap.add_argument("--cls-weight", type=float, default=0.25)
    ap.add_argument("--patience", type=int, default=5)
    ap.add_argument("--freeze-epochs", type=int, default=2)
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    ap.add_argument("--inpaint", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--busbra-test-frac", type=float, default=0.25)
    ap.add_argument("--split-seed", type=int, default=42)
    args = ap.parse_args()

    V2_DIR.mkdir(parents=True, exist_ok=True)
    V2_RESULTS.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Ensure Telea inpaints exist for flagged BUSI if requested
    if args.inpaint:
        inpainted = PROCESSED / "inpainted"
        if not inpainted.exists() or not any(inpainted.glob("*.png")):
            print("Generating Telea caliper inpaints for flagged BUSI…")
            from subprocess import check_call

            check_call([sys.executable, str(REPO / "scripts" / "inpaint_calipers.py"), "--mode", "markers"])

    busi_man = load_manifest()
    busi_splits = load_splits()
    busbra_train, busbra_test = busbra_patient_split(seed=args.split_seed, test_frac=args.busbra_test_frac)
    # Persist split for audit
    split_meta = {
        "split_seed": args.split_seed,
        "test_frac": args.busbra_test_frac,
        "train_n": len(busbra_train),
        "test_n": len(busbra_test),
        "train_patients": int(busbra_train["patient_id"].nunique()),
        "test_patients": int(busbra_test["patient_id"].nunique()),
        "train_ids": busbra_train["case_id"].tolist(),
        "test_ids": busbra_test["case_id"].tolist(),
    }
    (V2_RESULTS / "busbra_patient_split.json").write_text(json.dumps(split_meta, indent=2) + "\n")
    breast_man = build_breast()
    breast_man = breast_man.copy()
    breast_man["cls_target"] = breast_man["label"].map({"benign": 0.0, "malignant": 1.0, "normal": -1.0}).fillna(-1.0)

    v1 = load_v1_baselines()
    onnx_v1 = WEB_PUBLIC / "models" / "v1.0.0" / "busi_unet.onnx"
    if onnx_v1.exists():
        v1["int8_mb"] = round(onnx_v1.stat().st_size / (1024 * 1024), 3)

    seeds_out = []
    for seed in args.seeds:
        try:
            row = train_one_seed(args, seed, busi_man, busi_splits, busbra_train, busbra_test, breast_man)
            row["swap"] = apply_swap_checks(row, v1)
            seeds_out.append(row)
            (V2_RESULTS / f"seed{seed}.json").write_text(json.dumps(row, indent=2, default=float) + "\n")
        except Exception as e:  # noqa: BLE001 — honest failure logging
            fail = {
                "seed": seed,
                "failed": True,
                "error": repr(e),
                "failures": [repr(e)],
            }
            seeds_out.append(fail)
            (V2_RESULTS / f"seed{seed}_FAILED.json").write_text(json.dumps(fail, indent=2) + "\n")
            print(f"[seed {seed}] FAILED: {e}")

    ok_seeds = [s for s in seeds_out if s.get("swap", {}).get("swap_ok")]
    # Prefer best clean Dice among swap-ok; else best clean among finished
    finished = [s for s in seeds_out if "test_clean_subset" in s]
    best = None
    if ok_seeds:
        best = max(ok_seeds, key=lambda s: s["test_clean_subset"]["dice_mean"])
    elif finished:
        best = max(finished, key=lambda s: s["test_clean_subset"]["dice_mean"])

    table = [
        {
            "name": "v1.0.0 served INT8 (160² ResNet-18)",
            "dice": v1.get("test_dice"),
            "lesion_dice": v1.get("lesion_dice"),
            "clean_dice": v1.get("clean_dice"),
            "busbra_dice": v1.get("busbra_dice"),
            "breast_dice": v1.get("breast_dice"),
            "auc": v1.get("auc"),
            "int8_mb": v1.get("int8_mb"),
        }
    ]
    for s in finished:
        sw = s.get("swap", {})
        table.append(
            {
                "name": f"v2 candidate seed {s['seed']} ({args.model} {args.img_size}²)",
                "dice": (s.get("test_original") or {}).get("dice_mean"),
                "lesion_dice": (s.get("test_original") or {}).get("lesion_dice_mean"),
                "clean_dice": (s.get("test_clean_subset") or {}).get("dice_mean"),
                "busbra_dice": (s.get("external_busbra_heldout") or {}).get("dice_mean"),
                "breast_dice": (s.get("external_breast") or {}).get("dice_mean"),
                "auc": ((s.get("test_original") or {}).get("classification") or {}).get("roc_auc"),
                "int8_mb": s.get("onnx_int8_mb"),
                "swap_ok": sw.get("swap_ok"),
                "checks": sw.get("checks"),
                "failures": s.get("failures"),
            }
        )

    swap_ok = bool(best and best.get("swap", {}).get("swap_ok"))
    report = {
        "label": "Phase 4 v2 multi-dataset candidates (MODEL_POLICY D3)",
        "note": (
            "Trained on BUSI train + patient-grouped BUS-BRA train; held-out BUS-BRA test; "
            "BrEaST fully external. ResNet-34 @ 256, strong aug, Dice+focal"
            + (", Telea caliper inpaint on flagged BUSI" if args.inpaint else "")
            + ". Honest reporting including failures."
        ),
        "hardware": {
            "device": str(DEVICE),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
        },
        "config": vars(args),
        "v1_baselines": v1,
        "busbra_split": {
            "train_n": len(busbra_train),
            "test_n": len(busbra_test),
            "train_patients": int(busbra_train["patient_id"].nunique()),
            "test_patients": int(busbra_test["patient_id"].nunique()),
        },
        "seeds": seeds_out,
        "best": None
        if best is None
        else {
            "seed": best["seed"],
            "swap_ok": best.get("swap", {}).get("swap_ok"),
            "checks": best.get("swap", {}).get("checks"),
            "onnx_int8": best.get("onnx_int8"),
            "onnx_sha256": best.get("onnx_sha256"),
            "onnx_int8_mb": best.get("onnx_int8_mb"),
            "metrics": best.get("swap", {}).get("v2"),
            "postprocess": best.get("postprocess"),
            "img_size": best.get("img_size"),
            "model_kind": best.get("model_kind"),
        },
        "table": table,
        "model_policy_decision": {
            "swap_ok": swap_ok,
            "served_unchanged": not swap_ok,
            "note": (
                f"Best seed {best['seed']} passed MODEL_POLICY + size"
                if swap_ok
                else (
                    f"No seed passed MODEL_POLICY + ≤25MB INT8"
                    + (f"; best incomplete seed {best['seed']}" if best else "")
                    + " — keep v1.0.0 served"
                )
            ),
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
        if isinstance(obj, (np.floating, np.integer)):
            return obj.item()
        return obj

    out_path = RESULTS / "v2_experiment.json"
    out_path.write_text(json.dumps(_sanitize(report), indent=2) + "\n")
    print("Wrote", out_path)
    print("DECISION:", report["model_policy_decision"]["note"])


if __name__ == "__main__":
    main()
