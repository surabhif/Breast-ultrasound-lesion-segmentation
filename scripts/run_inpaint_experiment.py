#!/usr/bin/env python3
"""Inpainting experiments E-a, E-b, E-c (plan S2).

E-a: frozen v1 INT8 on original vs marker-inpainted test images.
E-b: control — random-region inpaint on clean images.
E-c: retrain on marker-inpainted training data (3 seeds), evaluate on
     original test, inpainted test, clean subset, BUS-BRA, BrEaST.

Writes results/inpaint_experiment.json. Does not overwrite served v1 unless
MODEL_POLICY swap criteria are met (handled by scripts/apply_model_swap.py).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
import pandas as pd
import torch
from PIL import Image
from sklearn.metrics import roc_auc_score
from torch.utils.data import DataLoader
from tqdm.auto import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import (  # noqa: E402
    EXPORT_DIR,
    RESULTS,
    WEB_PUBLIC,
    BusiDataset,
    dice_score,
    imagenet_tensor_from_rgb,
    load_manifest,
    load_splits,
    remove_small_components,
)
from caliper_masks import safe_name  # noqa: E402
from inpaint_calipers import INPAINT_DIR, RANDOM_DIR  # noqa: E402
from model_def import (  # noqa: E402
    OnnxExportWrapper,
    build_model,
    classification_loss,
    combined_seg_loss,
)
from train_full import (  # noqa: E402
    DEVICE,
    evaluate_detailed,
    set_encoder_requires_grad,
    set_seed,
)

V1_ONNX = WEB_PUBLIC / "models" / "v1.0.0" / "busi_unet.onnx"
OUT = RESULTS / "inpaint_experiment.json"
SEG_THRESH = 0.4
MIN_AREA = 40


def remap_manifest(manifest: pd.DataFrame, image_dir: Path) -> pd.DataFrame:
    df = manifest.copy()
    paths = []
    for cid, orig in zip(df["case_id"], df["image_path"]):
        alt = image_dir / f"{safe_name(cid)}.png"
        paths.append(str(alt) if alt.exists() else orig)
    df["image_path"] = paths
    return df


def score_onnx_on_ids(
    sess: ort.InferenceSession,
    manifest: pd.DataFrame,
    case_ids: list[str],
    *,
    img_size: int = 160,
) -> dict:
    by_id = manifest.set_index("case_id")
    names = [o.name for o in sess.get_outputs()]
    dices, lesion_dices, probs, targets, flags = [], [], [], [], []
    for cid in case_ids:
        row = by_id.loc[cid]
        img = Image.open(row["image_path"]).convert("RGB")
        x = imagenet_tensor_from_rgb(np.asarray(img), img_size)
        outs = sess.run(None, {"input": x})
        seg = outs[names.index("seg_mask")] if "seg_mask" in names else outs[0]
        cls = outs[names.index("cls_prob")] if "cls_prob" in names else outs[1]
        pred = remove_small_components(seg[0, 0] > SEG_THRESH, MIN_AREA)
        gt = np.array(Image.open(row["merged_mask_path"]).convert("L").resize((img_size, img_size), Image.NEAREST)) > 127
        d = float(dice_score(pred, gt))
        dices.append(d)
        if str(row["label"]) != "normal":
            lesion_dices.append(d)
        if str(row["label"]) in ("benign", "malignant"):
            probs.append(float(cls.reshape(-1)[0]))
            targets.append(float(row["cls_target"]))
        flags.append(bool(row["annotation_flag"]))
    auc = None
    if len(set(targets)) > 1:
        auc = float(roc_auc_score(targets, probs))
    flagged = [d for d, f in zip(dices, flags) if f]
    clean = [d for d, f in zip(dices, flags) if not f]
    return {
        "n": len(dices),
        "dice_mean": float(np.mean(dices)) if dices else None,
        "lesion_dice_mean": float(np.mean(lesion_dices)) if lesion_dices else None,
        "dice_flagged": float(np.mean(flagged)) if flagged else None,
        "dice_clean": float(np.mean(clean)) if clean else None,
        "cls_roc_auc": auc,
    }


def train_one_seed(
    seed: int,
    train_manifest: pd.DataFrame,
    *,
    epochs: int,
    img_size: int,
    batch_size: int,
) -> dict:
    """Train ResNet-18 U-Net on (possibly remapped) manifest; return metrics + onnx path."""
    set_seed(seed)
    splits = load_splits()
    fold = splits["folds"][0]
    train_ids, val_ids = fold["train_ids"], fold["val_ids"]
    # Training uses remapped (inpainted) paths; eval also needs original for comparison
    orig = load_manifest()
    train_ds = BusiDataset(train_manifest, train_ids, img_size=img_size, augment=True)
    val_ds = BusiDataset(train_manifest, val_ids, img_size=img_size, augment=False)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)

    model = build_model("resnet18", pretrained=True).to(DEVICE)
    set_encoder_requires_grad(model, False)
    opt = torch.optim.AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=1e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs, eta_min=1e-5)
    best_path = EXPORT_DIR / f"inpaint_seed{seed}_best.pt"
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    best_lesion, stale, patience = -1.0, 0, 6
    freeze_epochs = 2
    encoder_unfrozen = False

    for epoch in range(1, epochs + 1):
        if (not encoder_unfrozen) and epoch > freeze_epochs:
            set_encoder_requires_grad(model, True)
            opt = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
            sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs - epoch + 1, eta_min=1e-5)
            encoder_unfrozen = True
        model.train()
        for batch in train_loader:
            images = batch["image"].to(DEVICE)
            masks = batch["mask"].to(DEVICE)
            cls_t = batch["cls_target"].to(DEVICE)
            seg_logits, cls_logits = model(images)
            loss = combined_seg_loss(seg_logits, masks) + 0.3 * classification_loss(cls_logits, cls_t)
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
        sched.step()
        val = evaluate_detailed(model, val_loader, seg_thresh=0.5, min_area=0)
        print(f"  seed {seed} ep {epoch}: val lesion Dice {val['lesion_dice_mean']:.3f}")
        if val["lesion_dice_mean"] > best_lesion:
            best_lesion = val["lesion_dice_mean"]
            stale = 0
            torch.save({"state_dict": model.state_dict(), "seed": seed, "epoch": epoch}, best_path)
        else:
            stale += 1
            if stale >= patience:
                print(f"  early stop seed {seed} at epoch {epoch}")
                break

    ckpt = torch.load(best_path, map_location=DEVICE, weights_only=False)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    # Export ONNX for this seed
    onnx_path = EXPORT_DIR / f"inpaint_seed{seed}.onnx"
    wrapper = OnnxExportWrapper(model)
    wrapper.eval()
    dummy = torch.randn(1, 3, img_size, img_size, device=DEVICE)
    torch.onnx.export(
        wrapper,
        dummy,
        str(onnx_path),
        input_names=["input"],
        output_names=["seg_mask", "cls_prob"],
        dynamic_axes={"input": {0: "batch"}, "seg_mask": {0: "batch"}, "cls_prob": {0: "batch"}},
        opset_version=17,
    )

    # Quantize dynamically like v1
    try:
        from onnxruntime.quantization import QuantType, quantize_dynamic

        qpath = EXPORT_DIR / f"inpaint_seed{seed}_int8.onnx"
        quantize_dynamic(str(onnx_path), str(qpath), weight_type=QuantType.QUInt8)
        onnx_eval = qpath
    except Exception as e:
        print("quantization failed, using FP32 ONNX:", e)
        onnx_eval = onnx_path

    sess = ort.InferenceSession(str(onnx_eval), providers=["CPUExecutionProvider"])
    orig_m = orig
    inp_m = remap_manifest(orig, INPAINT_DIR)
    test_ids = splits["test_ids"]
    clean_ids = [c for c in test_ids if not bool(orig.set_index("case_id").loc[c]["annotation_flag"])]
    metrics = {
        "seed": seed,
        "best_val_lesion_dice": float(best_lesion),
        "onnx": str(onnx_eval),
        "sha256": hashlib.sha256(onnx_eval.read_bytes()).hexdigest(),
        "test_original": score_onnx_on_ids(sess, orig_m, test_ids),
        "test_inpainted": score_onnx_on_ids(sess, inp_m, test_ids),
        "test_clean_subset_original": score_onnx_on_ids(sess, orig_m, clean_ids),
    }
    return metrics


def eval_external_quick(sess: ort.InferenceSession, dataset: str) -> dict | None:
    """Score ONNX on an external set via existing loaders (subset OK if slow)."""
    try:
        if dataset == "busbra":
            from external.busbra import build_manifest as build
        elif dataset == "breast":
            from external.breast import build_manifest as build
        else:
            return None
        man = build()
    except Exception as e:
        return {"skipped": True, "reason": str(e)}

    from external.common import load_mask_binary, load_rgb

    names = [o.name for o in sess.get_outputs()]
    dices, lesion, probs, targets = [], [], [], []
    for _, r in man.iterrows():
        if r["label"] == "normal" and not r.get("mask_path"):
            continue
        x = imagenet_tensor_from_rgb(load_rgb(r["image_path"]), 160)
        outs = sess.run(None, {"input": x})
        seg = outs[names.index("seg_mask")] if "seg_mask" in names else outs[0]
        cls = outs[names.index("cls_prob")] if "cls_prob" in names else outs[1]
        pred = remove_small_components(seg[0, 0] > SEG_THRESH, MIN_AREA)
        gt = load_mask_binary(r["mask_path"], 160)
        d = float(dice_score(pred, gt))
        dices.append(d)
        if r["label"] != "normal":
            lesion.append(d)
        if r["label"] in ("benign", "malignant"):
            probs.append(float(cls.reshape(-1)[0]))
            targets.append(1.0 if r["label"] == "malignant" else 0.0)
    auc = float(roc_auc_score(targets, probs)) if len(set(targets)) > 1 else None
    return {
        "n": len(dices),
        "dice_mean": float(np.mean(dices)) if dices else None,
        "lesion_dice_mean": float(np.mean(lesion)) if lesion else None,
        "cls_roc_auc": auc,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-train", action="store_true", help="Only E-a/E-b (no E-c retrain)")
    ap.add_argument("--epochs", type=int, default=25)
    ap.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--img-size", type=int, default=160)
    args = ap.parse_args()

    t0 = time.time()
    splits = load_splits()
    test_ids = splits["test_ids"]
    orig = load_manifest()
    clean_ids = [c for c in test_ids if not bool(orig.set_index("case_id").loc[c]["annotation_flag"])]
    flagged_ids = [c for c in test_ids if bool(orig.set_index("case_id").loc[c]["annotation_flag"])]

    v1_sha = hashlib.sha256(V1_ONNX.read_bytes()).hexdigest()
    sess_v1 = ort.InferenceSession(str(V1_ONNX), providers=["CPUExecutionProvider"])

    print("=== E-a: v1 on original vs marker-inpainted test ===")
    ea_orig = score_onnx_on_ids(sess_v1, orig, test_ids)
    ea_inp = score_onnx_on_ids(sess_v1, remap_manifest(orig, INPAINT_DIR), test_ids)
    ea_flag_orig = score_onnx_on_ids(sess_v1, orig, flagged_ids)
    ea_flag_inp = score_onnx_on_ids(sess_v1, remap_manifest(orig, INPAINT_DIR), flagged_ids)
    ea_clean = score_onnx_on_ids(sess_v1, orig, clean_ids)

    print("=== E-b: random inpaint control on clean test ===")
    clean_only = [c for c in clean_ids]
    eb_orig = score_onnx_on_ids(sess_v1, orig, clean_only)
    eb_rand = score_onnx_on_ids(sess_v1, remap_manifest(orig, RANDOM_DIR), clean_only)

    result: dict = {
        "label": "Caliper inpainting experiments E-a / E-b / E-c",
        "v1_onnx_sha256": v1_sha,
        "seg_threshold": SEG_THRESH,
        "min_component_area": MIN_AREA,
        "E_a": {
            "description": "Frozen v1 INT8 on original vs Telea marker-inpainted test images",
            "original": ea_orig,
            "inpainted": ea_inp,
            "flagged_original": ea_flag_orig,
            "flagged_inpainted": ea_flag_inp,
            "clean_original": ea_clean,
            "delta_dice_inpainted_minus_original": (
                None
                if ea_orig["dice_mean"] is None or ea_inp["dice_mean"] is None
                else ea_inp["dice_mean"] - ea_orig["dice_mean"]
            ),
        },
        "E_b": {
            "description": "Control: random-region Telea inpaint on clean (unflagged) test images",
            "clean_original": eb_orig,
            "clean_random_inpaint": eb_rand,
            "delta_dice_random_minus_original": (
                None
                if eb_orig["dice_mean"] is None or eb_rand["dice_mean"] is None
                else eb_rand["dice_mean"] - eb_orig["dice_mean"]
            ),
        },
        "E_c": {"seeds": [], "note": "Retrain on marker-inpainted train/val; evaluate INT8"},
    }
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print("E-a/E-b checkpoint written")

    if not args.skip_train:
        print("=== E-c: retrain on inpainted data ===")
        train_man = remap_manifest(orig, INPAINT_DIR)
        seed_runs = []
        for seed in args.seeds:
            print(f"--- training seed {seed} ---")
            m = train_one_seed(
                seed,
                train_man,
                epochs=args.epochs,
                img_size=args.img_size,
                batch_size=args.batch_size,
            )
            # External eval for this seed
            sess = ort.InferenceSession(m["onnx"], providers=["CPUExecutionProvider"])
            m["external_busbra"] = eval_external_quick(sess, "busbra")
            m["external_breast"] = eval_external_quick(sess, "breast")
            seed_runs.append(m)
            # Persist incremental
            result["E_c"]["seeds"] = seed_runs
            OUT.write_text(json.dumps(result, indent=2) + "\n")

        # Aggregate best seed by clean-subset Dice (MODEL_POLICY primary lever)
        best = max(seed_runs, key=lambda r: r["test_clean_subset_original"]["dice_mean"] or -1)
        result["E_c"]["best_seed"] = best["seed"]
        result["E_c"]["best"] = best
        result["E_c"]["mean_test_dice_original"] = float(
            np.mean([r["test_original"]["dice_mean"] for r in seed_runs])
        )
        result["E_c"]["mean_clean_dice"] = float(
            np.mean([r["test_clean_subset_original"]["dice_mean"] for r in seed_runs])
        )

    result["runtime_seconds"] = time.time() - t0
    OUT.write_text(json.dumps(result, indent=2) + "\n")
    print("Wrote", OUT)


if __name__ == "__main__":
    main()
