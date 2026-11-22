#!/usr/bin/env python3
"""v1.1 BUSI-only candidates vs frozen v1.0.0 under MODEL_POLICY (D3).

Same cleaned BUSI data + committed leakage-safe splits/held-out test as v1.0.0.
Tune postprocess and no-lump gate on validation only; score the frozen test once.
Does NOT promote or rewrite web/public/models/current.json.

Candidates (default):
  - ResNet-18 U-Net @ 224
  - ResNet-18 U-Net @ 256
  - ResNet-34 U-Net @ 224

Writes:
  export/v1_1/<cand_id>/{best.pt, fp32.onnx, int8.onnx}
  results/v1_1/<cand_id>.json
  results/v1_1_experiment.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
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
    bootstrap_ci,
    dice_score,
    imagenet_tensor_from_rgb,
    iou_score,
    load_manifest,
    load_splits,
    remove_small_components,
)
from model_def import (  # noqa: E402
    build_model,
    classification_loss,
    combined_seg_loss,
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
OUT_DIR = EXPORT_DIR / "v1_1"
RES_DIR = RESULTS / "v1_1"

# Frozen v1.0.0 INT8 baselines (committed). Clean Dice uses the same FP32 cleaning
# baseline published in MODEL_POLICY / Phase-4 tables for continuity.
V1_BASELINES = {
    "test_dice": 0.6972011494235116,
    "test_dice_ci95": [0.6318544128007265, 0.7656603082162292],
    "lesion_dice": 0.7643712765714284,
    "lesion_dice_ci95": [0.7049727284836597, 0.8211196389529184],
    "iou": 0.6295263549739772,
    "iou_ci95": [0.567721238896154, 0.6939308107729822],
    "auc": 0.9306878306878307,
    "clean_dice": 0.6229383436474434,
    "normal_fp": 12,
    "normal_n": 19,
    "int8_mb": 11.664,
    "img_size": 160,
    "busbra_dice": 0.7136202288207832,
    "breast_dice": 0.6265385719593876,
    "busuclm_dice": 0.386,
    "busuclm_lesion_dice": 0.679,
    "no_lump_gate_0_96_fp": 10,
}

DEFAULT_CANDIDATES = [
    {"id": "r18_224", "model": "resnet18", "img_size": 224, "batch_size": 8, "lr": 8e-4},
    {"id": "r18_256", "model": "resnet18", "img_size": 256, "batch_size": 4, "lr": 8e-4},
    {"id": "r34_224", "model": "resnet34", "img_size": 224, "batch_size": 4, "lr": 6e-4},
]


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


def bootstrap_auc(y: np.ndarray, p: np.ndarray, n_boot: int = 1000, seed: int = 42):
    rng = np.random.default_rng(seed)
    try:
        point = float(roc_auc_score(y, p))
    except ValueError:
        return None, [None, None]
    n = len(y)
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, size=n)
        yy, pp = y[idx], p[idx]
        if len(np.unique(yy)) < 2:
            continue
        try:
            vals.append(float(roc_auc_score(yy, pp)))
        except ValueError:
            continue
    if not vals:
        return point, [None, None]
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return point, [float(lo), float(hi)]


def quantize_to_int8(fp32_path: Path, int8_path: Path) -> dict:
    from onnxruntime.quantization import QuantType, quantize_dynamic

    fp32_mb = fp32_path.stat().st_size / (1024 * 1024)
    quantize_dynamic(
        model_input=str(fp32_path),
        model_output=str(int8_path),
        weight_type=QuantType.QUInt8,
    )
    int8_mb = int8_path.stat().st_size / (1024 * 1024)
    return {"fp32_mb": round(fp32_mb, 3), "int8_mb": round(int8_mb, 3)}


def train_one(cand: dict, args) -> Path:
    """Train one candidate; return checkpoint path. Skips if checkpoint exists unless --force."""
    cand_dir = OUT_DIR / cand["id"]
    cand_dir.mkdir(parents=True, exist_ok=True)
    best_path = cand_dir / "best.pt"
    if best_path.exists() and not args.force:
        print(f"[{cand['id']}] Reusing existing checkpoint {best_path}")
        return best_path

    set_seed(args.seed)
    manifest = load_manifest()
    splits = load_splits()
    fold = splits["folds"][args.fold]
    train_ids, val_ids = fold["train_ids"], fold["val_ids"]
    test_ids = splits["test_ids"]

    img_size = cand["img_size"]
    batch_size = cand["batch_size"]
    model_kind = cand["model"]
    lr = cand["lr"]

    train_ds = BusiDataset(manifest, train_ids, img_size=img_size, augment=True)
    val_ds = BusiDataset(manifest, val_ids, img_size=img_size, augment=False)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)

    model = build_model(model_kind, pretrained=True).to(DEVICE)
    if args.freeze_epochs > 0:
        set_encoder_requires_grad(model, False)
        print(f"[{cand['id']}] Encoder frozen for first {args.freeze_epochs} epochs")

    opt = torch.optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=lr,
        weight_decay=1e-4,
    )
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs, eta_min=1e-5)
    n_params = sum(p.numel() for p in model.parameters()) / 1e6
    print(
        f"[{cand['id']}] Device={DEVICE} model={model_kind} size={img_size} "
        f"params={n_params:.2f}M train={len(train_ds)} val={len(val_ds)} test={len(test_ids)}"
    )

    history = []
    best_lesion = -1.0
    stale = 0
    encoder_unfrozen = args.freeze_epochs <= 0
    t0 = time.time()

    for epoch in range(1, args.epochs + 1):
        if (not encoder_unfrozen) and epoch > args.freeze_epochs:
            set_encoder_requires_grad(model, True)
            opt = torch.optim.AdamW(model.parameters(), lr=lr * 0.5, weight_decay=1e-4)
            remaining = args.epochs - epoch + 1
            sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=remaining, eta_min=1e-5)
            encoder_unfrozen = True
            print(f"[{cand['id']}] Encoder unfrozen at epoch {epoch}; lr={lr * 0.5}")

        model.train()
        losses = []
        pbar = tqdm(train_loader, desc=f"{cand['id']} ep{epoch}/{args.epochs}")
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
            f"  [{cand['id']}] val dice={val_metrics['dice_mean']:.3f} "
            f"lesion={val_metrics['lesion_dice_mean']:.3f} auc={row['val_auc']}"
        )
        sched.step()

        if val_metrics["lesion_dice_mean"] > best_lesion:
            best_lesion = val_metrics["lesion_dice_mean"]
            stale = 0
            torch.save(
                {
                    "model_kind": model_kind,
                    "img_size": img_size,
                    "pretrained": True,
                    "state_dict": model.state_dict(),
                    "val_metrics": {k: v for k, v in val_metrics.items() if k != "per_image"},
                    "epoch": epoch,
                    "candidate_id": cand["id"],
                    "history": history,
                    "params_millions": n_params,
                    "config": {
                        **cand,
                        "epochs": args.epochs,
                        "cls_weight": args.cls_weight,
                        "seed": args.seed,
                        "fold": args.fold,
                        "freeze_epochs": args.freeze_epochs,
                        "patience": args.patience,
                    },
                },
                best_path,
            )
        else:
            stale += 1
            if stale >= args.patience:
                print(f"[{cand['id']}] Early stop at epoch {epoch}")
                break

    runtime = time.time() - t0
    meta = {"train_runtime_seconds": runtime, "best_val_lesion_dice": best_lesion}
    (cand_dir / "train_meta.json").write_text(json.dumps(meta, indent=2))
    print(f"[{cand['id']}] Training done in {runtime:.0f}s; best lesion Dice={best_lesion:.3f}")
    return best_path


def evaluate_onnx_busi(
    onnx_path: Path,
    img_size: int,
    seg_thresh: float,
    min_area: int,
    ids: list[str],
    manifest,
) -> dict:
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    man = manifest.set_index("case_id")
    seg_probs, gts, labels, cls_probs, cls_targets, case_ids, flags = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    mask_maxes = []
    for cid in tqdm(ids, desc=f"eval {onnx_path.name}"):
        row = man.loc[cid]
        img = Image.open(row["image_path"]).convert("RGB")
        x = imagenet_tensor_from_rgb(np.asarray(img), img_size)
        outs = sess.run(None, {"input": x.astype(np.float32)})
        onames = [o.name for o in sess.get_outputs()]
        seg = outs[onames.index("seg_mask")] if "seg_mask" in onames else outs[0]
        cls = outs[onames.index("cls_prob")] if "cls_prob" in onames else outs[1]
        soft = seg[0, 0].astype(np.float32)
        # Export wrapper already applies sigmoid; tolerate logits if present.
        if float(soft.min()) < 0 or float(soft.max()) > 1.1:
            soft = 1.0 / (1.0 + np.exp(-soft))
        mask_path = row["merged_mask_path"]
        gt = np.array(Image.open(mask_path).convert("L").resize((img_size, img_size), Image.NEAREST))
        gt = (gt > 127).astype(np.float32)
        seg_probs.append(soft)
        gts.append(gt)
        labels.append(str(row["label"]))
        cls_probs.append(float(np.asarray(cls).reshape(-1)[0]))
        cls_targets.append(float(row["cls_target"]))
        case_ids.append(cid)
        flags.append(bool(row["annotation_flag"]))
        mask_maxes.append(float(soft.max()))

    scored = score_predictions(
        seg_probs,
        gts,
        labels,
        cls_probs,
        cls_targets,
        case_ids,
        flags,
        seg_thresh=seg_thresh,
        min_area=min_area,
    )
    # Attach mask_max for gate analysis
    for i, r in enumerate(scored["per_image"]):
        r["mask_max"] = mask_maxes[i]

    # Clean subset
    clean = [r for r in scored["per_image"] if not r["annotation_flag"]]
    if clean:
        clean_dice, clean_lo, clean_hi = bootstrap_ci(np.array([r["dice"] for r in clean]))
        clean_ci = [clean_lo, clean_hi]
    else:
        clean_dice, clean_ci = None, [None, None]

    # AUC + bootstrap CI
    y = np.array([int(r["cls_target"]) for r in scored["per_image"] if r["cls_target"] >= 0])
    p = np.array([r["cls_prob"] for r in scored["per_image"] if r["cls_target"] >= 0])
    auc, auc_ci = bootstrap_auc(y, p)

    normals = [r for r in scored["per_image"] if r["label"] == "normal"]
    normal_fp = int(sum(1 for r in normals if r["pred_area"] > 0))

    summary = {k: v for k, v in scored.items() if k != "per_image"}
    summary["clean_dice"] = clean_dice
    summary["clean_dice_ci95"] = clean_ci
    summary["clean_n"] = len(clean)
    summary["cls_roc_auc"] = auc
    summary["cls_roc_auc_ci95"] = auc_ci
    summary["normal_false_positive_count"] = normal_fp
    summary["normal_n"] = len(normals)
    summary["per_image"] = scored["per_image"]
    return summary


def _apply_mask_max_gate(rows: list[dict], thr: float) -> list[dict]:
    out = []
    for r in rows:
        hide = r["mask_max"] < thr
        if hide:
            d = 1.0 if r["gt_area"] == 0 else 0.0
            pred_area = 0
        else:
            d = r["dice"]
            pred_area = r["pred_area"]
        out.append({**r, "gated_dice": d, "hidden": hide, "gated_pred_area": pred_area})
    return out


def tune_no_lump_on_val(val_rows: list[dict]) -> dict:
    """Re-tune display gate on validation only (same rule as tune_no_lump_gate.py)."""
    base_rows = list(val_rows)
    base_les = float(np.mean([r["dice"] for r in base_rows if r["label"] != "normal"]))
    base_fp = int(sum(1 for r in base_rows if r["label"] == "normal" and r["pred_area"] > 0))
    base_n = int(sum(1 for r in base_rows if r["label"] == "normal"))

    best = None
    for thr in np.linspace(0.5, 0.995, 100):
        gated = _apply_mask_max_gate(base_rows, float(thr))
        les = float(np.mean([r["gated_dice"] for r in gated if r["label"] != "normal"]))
        drop = base_les - les
        fp = int(
            sum(
                1
                for r in gated
                if r["label"] == "normal" and not r["hidden"] and r["gated_pred_area"] > 0
            )
        )
        cleared = base_fp - fp
        if drop <= 0.01 + 1e-12:
            cand = {
                "mask_max_thr": float(thr),
                "val_lesion_dice": les,
                "val_lesion_dice_drop": float(drop),
                "val_normal_fp": fp,
                "val_normal_n": base_n,
                "val_fp_cleared": cleared,
            }
            if best is None or cleared > best["val_fp_cleared"] or (
                cleared == best["val_fp_cleared"] and drop < best["val_lesion_dice_drop"]
            ):
                best = cand

    if best is None:
        best = {
            "mask_max_thr": 0.96,
            "val_lesion_dice": base_les,
            "val_lesion_dice_drop": 0.0,
            "val_normal_fp": base_fp,
            "val_normal_n": base_n,
            "val_fp_cleared": 0,
        }
    gated_096 = _apply_mask_max_gate(base_rows, 0.96)
    return {
        "baseline_val_lesion_dice": base_les,
        "baseline_val_normal_fp": base_fp,
        "retuned": best,
        "fixed_0_96": {
            "mask_max_thr": 0.96,
            "val_lesion_dice": float(
                np.mean([r["gated_dice"] for r in gated_096 if r["label"] != "normal"])
            ),
            "val_normal_fp": int(
                sum(
                    1
                    for r in gated_096
                    if r["label"] == "normal" and not r["hidden"] and r["gated_pred_area"] > 0
                )
            ),
        },
    }


def apply_gate_test(test_rows: list[dict], thr: float) -> dict:
    gated = []
    for r in test_rows:
        hide = r["mask_max"] < thr
        if hide:
            d = 1.0 if r["gt_area"] == 0 else 0.0
            pred_area = 0
        else:
            d = r["dice"]
            pred_area = r["pred_area"]
        gated.append({**r, "gated_dice": d, "hidden": hide, "gated_pred_area": pred_area})
    les_before = float(np.mean([r["dice"] for r in test_rows if r["label"] != "normal"]))
    les_after = float(np.mean([r["gated_dice"] for r in gated if r["label"] != "normal"]))
    fp_before = int(sum(1 for r in test_rows if r["label"] == "normal" and r["pred_area"] > 0))
    fp_after = int(
        sum(
            1
            for r in gated
            if r["label"] == "normal" and not r["hidden"] and r["gated_pred_area"] > 0
        )
    )
    return {
        "mask_max_thr": thr,
        "lesion_dice_before": les_before,
        "lesion_dice_after": les_after,
        "lesion_dice_drop": les_before - les_after,
        "normal_fp_before": fp_before,
        "normal_fp_after": fp_after,
        "normal_n": int(sum(1 for r in test_rows if r["label"] == "normal")),
    }


def measure_latency(onnx_path: Path, img_size: int, n_warmup: int = 5, n_runs: int = 30) -> dict:
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    x = np.random.randn(1, 3, img_size, img_size).astype(np.float32)
    for _ in range(n_warmup):
        sess.run(None, {"input": x})
    times = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        sess.run(None, {"input": x})
        times.append((time.perf_counter() - t0) * 1000.0)
    arr = np.array(times)
    return {
        "backend": "onnxruntime_cpu",
        "note": "CPU ORT latency proxy for in-browser WASM (browser typically slower).",
        "img_size": img_size,
        "n_runs": n_runs,
        "ms_mean": float(arr.mean()),
        "ms_std": float(arr.std()),
        "ms_p50": float(np.percentile(arr, 50)),
        "ms_p95": float(np.percentile(arr, 95)),
    }


def try_external(onnx_path: Path, img_size: int, seg_thresh: float, min_area: int) -> dict:
    """Score external sets when local data exists; skip gracefully otherwise."""
    from external.breast import build_manifest as build_breast
    from external.busbra import build_manifest as build_busbra
    from external.busuclm import build_manifest as build_busuclm
    from external.common import bootstrap_mean_ci, load_mask_binary, load_rgb

    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    builders = {"busbra": build_busbra, "breast": build_breast, "busuclm": build_busuclm}
    out = {"datasets": {}, "skipped": {}}
    for name, builder in builders.items():
        try:
            man = builder()
        except (FileNotFoundError, ImportError, OSError, ValueError) as e:
            out["skipped"][name] = f"{type(e).__name__}: {e}"
            print(f"SKIP external {name}: {e}")
            continue
        rows = []
        for _, r in tqdm(man.iterrows(), total=len(man), desc=f"ext {name}"):
            x = imagenet_tensor_from_rgb(load_rgb(r["image_path"]), img_size)
            outs = sess.run(None, {"input": x.astype(np.float32)})
            onames = [o.name for o in sess.get_outputs()]
            seg = outs[onames.index("seg_mask")] if "seg_mask" in onames else outs[0]
            soft = seg[0, 0].astype(np.float32)
            if float(soft.min()) < 0 or float(soft.max()) > 1.1:
                soft = 1.0 / (1.0 + np.exp(-soft))
            binary = soft > seg_thresh
            kept = remove_small_components(binary, min_area)
            gt = load_mask_binary(r["mask_path"] if r["mask_path"] else None, img_size)
            if r["label"] == "normal":
                gt = np.zeros_like(gt)
            rows.append(
                {
                    "label": r["label"],
                    "patient_id": str(r["patient_id"]),
                    "dice": float(dice_score(kept, gt)),
                    "iou": float(iou_score(kept, gt)),
                    "pred_area": int(kept.sum()),
                    "cls_target": (
                        1.0
                        if r["label"] == "malignant"
                        else (0.0 if r["label"] == "benign" else None)
                    ),
                    "cls_prob": float(
                        (outs[onames.index("cls_prob")] if "cls_prob" in onames else outs[1])
                        .reshape(-1)[0]
                    ),
                }
            )
        import pandas as pd

        df = pd.DataFrame(rows)
        clusters = df["patient_id"].astype(str).to_numpy()
        dice_mean, dice_ci = bootstrap_mean_ci(df["dice"].to_numpy(), clusters=clusters)
        lesion = df[df["label"].isin(["benign", "malignant"])]
        lesion_dice, lesion_ci = bootstrap_mean_ci(
            lesion["dice"].to_numpy(),
            clusters=lesion["patient_id"].astype(str).to_numpy(),
        )
        normals = df[df["label"] == "normal"]
        normal_fp = int((normals["pred_area"] > 0).sum()) if len(normals) else 0
        bm = df[df["label"].isin(["benign", "malignant"])].dropna(subset=["cls_target"])
        auc = None
        if len(bm) >= 5:
            try:
                auc = float(roc_auc_score(bm["cls_target"].to_numpy(dtype=float), bm["cls_prob"].to_numpy(dtype=float)))
            except ValueError:
                auc = None
        out["datasets"][name] = {
            "n": int(len(df)),
            "dice": dice_mean,
            "dice_ci95": dice_ci,
            "lesion_dice": lesion_dice,
            "lesion_dice_ci95": lesion_ci,
            "normal_fp": normal_fp,
            "normal_n": int(len(normals)),
            "auc": auc,
        }
    return out


def evaluate_candidate(cand: dict, args) -> dict:
    cand_dir = OUT_DIR / cand["id"]
    RES_DIR.mkdir(parents=True, exist_ok=True)
    out_json = RES_DIR / f"{cand['id']}.json"
    if out_json.exists() and not args.force_eval and (cand_dir / "int8.onnx").exists():
        print(f"[{cand['id']}] Reusing evaluation {out_json}")
        return json.loads(out_json.read_text())

    ckpt_path = train_one(cand, args)
    ckpt = torch.load(ckpt_path, map_location=DEVICE, weights_only=False)
    model = build_model(ckpt["model_kind"], pretrained=False).to(DEVICE)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    manifest = load_manifest()
    splits = load_splits()
    fold = splits["folds"][args.fold]
    img_size = int(ckpt["img_size"])

    val_ds = BusiDataset(manifest, fold["val_ids"], img_size=img_size, augment=False)
    val_loader = DataLoader(val_ds, batch_size=cand["batch_size"], shuffle=False, num_workers=0)
    print(f"[{cand['id']}] Tuning postprocess on validation…")
    raw_val = collect_raw(model, val_loader)
    best_thr, best_area, tuned_val = tune_postprocess_on_val(raw_val)
    print(
        f"[{cand['id']}] thr={best_thr} min_area={best_area} "
        f"val_lesion={tuned_val['lesion_dice_mean']:.3f}"
    )

    fp32_path = cand_dir / "fp32.onnx"
    int8_path = cand_dir / "int8.onnx"
    if not fp32_path.exists() or args.force:
        export_onnx(model, fp32_path, img_size)
    quant = quantize_to_int8(fp32_path, int8_path)
    sha = hashlib.sha256(int8_path.read_bytes()).hexdigest()

    # Score INT8 on val (for gate) and frozen test
    val_score = evaluate_onnx_busi(
        int8_path, img_size, best_thr, best_area, fold["val_ids"], manifest
    )
    test_score = evaluate_onnx_busi(
        int8_path, img_size, best_thr, best_area, splits["test_ids"], manifest
    )

    gate_tune = tune_no_lump_on_val(val_score["per_image"])
    gate_fixed = apply_gate_test(test_score["per_image"], 0.96)
    gate_retuned = apply_gate_test(test_score["per_image"], gate_tune["retuned"]["mask_max_thr"])

    latency = measure_latency(int8_path, img_size)
    # Also time v1 at 160 for comparison once
    v1_onnx = WEB_PUBLIC / "models" / "v1.0.0" / "busi_unet.onnx"
    v1_latency = measure_latency(v1_onnx, 160) if v1_onnx.exists() else None

    external = try_external(int8_path, img_size, best_thr, best_area)

    # Swap checks (BUSI-only training → full external Dice, like Phase-2 / D3)
    busbra = (external.get("datasets") or {}).get("busbra")
    breast = (external.get("datasets") or {}).get("breast")
    c_dice = test_score["dice_mean"]
    c_clean = test_score["clean_dice"]
    c_auc = test_score["cls_roc_auc"]
    busbra_dice = busbra["dice"] if busbra else None
    breast_dice = breast["dice"] if breast else None

    checks = {
        "clean_dice_ok": c_clean is not None and c_clean >= V1_BASELINES["clean_dice"] - 1e-9,
        "dice_ok": c_dice is not None and c_dice >= V1_BASELINES["test_dice"] - 1e-9,
        "auc_ok": c_auc is not None and (V1_BASELINES["auc"] - c_auc) <= 0.02 + 1e-9,
        "busbra_ok": busbra_dice is None or busbra_dice >= V1_BASELINES["busbra_dice"] - 1e-9,
        "breast_ok": breast_dice is None or breast_dice >= V1_BASELINES["breast_dice"] - 1e-9,
        "size_ok": quant["int8_mb"] <= 25.0 + 1e-9,
    }
    # Required when data available; if skipped, do not count as pass for promotion.
    if busbra_dice is None:
        checks["busbra_ok"] = False
        checks["busbra_skipped"] = True
    if breast_dice is None:
        checks["breast_ok"] = False
        checks["breast_skipped"] = True

    swap_ok = all(
        [
            checks["clean_dice_ok"],
            checks["dice_ok"],
            checks["auc_ok"],
            checks["busbra_ok"],
            checks["breast_ok"],
            checks["size_ok"],
        ]
    )
    # User-facing abbreviated rule (Dice + AUC) for the PR table; full D3 still gates swap_ok.
    abbreviated_pass = bool(checks["dice_ok"] and checks["auc_ok"])

    report = {
        "candidate_id": cand["id"],
        "label": f"candidate {cand['model']} @{cand['img_size']}² (v1.1)",
        "model_kind": cand["model"],
        "img_size": img_size,
        "params_millions": ckpt.get("params_millions"),
        "epochs_ran": ckpt.get("epoch"),
        "best_val_lesion_dice": ckpt.get("val_metrics", {}).get("lesion_dice_mean"),
        "postprocess": {
            "seg_threshold": best_thr,
            "min_component_area": best_area,
            "selected_on": "validation_lesion_dice",
            "val_lesion_dice_at_selection": tuned_val["lesion_dice_mean"],
        },
        "quantization": quant,
        "sha256_int8": sha,
        "onnx_int8": str(int8_path.relative_to(REPO)),
        "test": {k: v for k, v in test_score.items() if k != "per_image"},
        "val_summary": {k: v for k, v in val_score.items() if k != "per_image"},
        "no_lump_gate": {
            "val_tune": gate_tune,
            "test_fixed_0_96": gate_fixed,
            "test_retuned": gate_retuned,
        },
        "latency": latency,
        "v1_latency_reference": v1_latency,
        "external": external,
        "swap": {
            "rule": "D3 MODEL_POLICY: clean Dice ≥ v1, external Dice ≥ v1, AUC drop ≤ 0.02, INT8 ≤ ~25 MB",
            "abbreviated_user_rule": "Dice ≥ v1 and AUC drop ≤ 0.02",
            "v1": V1_BASELINES,
            "candidate": {
                "dice": c_dice,
                "clean_dice": c_clean,
                "auc": c_auc,
                "busbra_dice": busbra_dice,
                "breast_dice": breast_dice,
                "int8_mb": quant["int8_mb"],
            },
            "checks": checks,
            "swap_ok": swap_ok,
            "abbreviated_pass": abbreviated_pass,
            "served_unchanged": True,
        },
        "train_meta": json.loads((cand_dir / "train_meta.json").read_text())
        if (cand_dir / "train_meta.json").exists()
        else None,
    }
    # Persist per-image separately (large)
    (RES_DIR / f"{cand['id']}_per_image.json").write_text(
        json.dumps(_sanitize(test_score["per_image"]), indent=2)
    )
    out_json.write_text(json.dumps(_sanitize(report), indent=2))
    print(
        f"[{cand['id']}] Test Dice={c_dice:.3f} lesion={test_score['lesion_dice_mean']:.3f} "
        f"AUC={c_auc:.3f} clean={c_clean:.3f} INT8={quant['int8_mb']:.1f}MB "
        f"swap_ok={swap_ok} abbrev={abbreviated_pass}"
    )
    return report


def build_experiment_summary(reports: list[dict]) -> dict:
    table = [
        {
            "name": "v1.0.0 INT8 (served)",
            "role": "baseline",
            "dice": V1_BASELINES["test_dice"],
            "lesion_dice": V1_BASELINES["lesion_dice"],
            "iou": V1_BASELINES["iou"],
            "clean_dice": V1_BASELINES["clean_dice"],
            "auc": V1_BASELINES["auc"],
            "busbra_dice": V1_BASELINES["busbra_dice"],
            "breast_dice": V1_BASELINES["breast_dice"],
            "busuclm_dice": V1_BASELINES["busuclm_dice"],
            "normal_fp": V1_BASELINES["normal_fp"],
            "int8_mb": V1_BASELINES["int8_mb"],
            "img_size": 160,
            "swap_ok": None,
        }
    ]
    for r in reports:
        ext = r.get("external", {}).get("datasets", {})
        table.append(
            {
                "name": r["label"],
                "role": "candidate",
                "candidate_id": r["candidate_id"],
                "dice": r["test"]["dice_mean"],
                "dice_ci95": r["test"]["dice_ci95"],
                "lesion_dice": r["test"]["lesion_dice_mean"],
                "lesion_dice_ci95": r["test"]["lesion_dice_ci95"],
                "iou": r["test"]["iou_mean"],
                "iou_ci95": r["test"]["iou_ci95"],
                "clean_dice": r["test"]["clean_dice"],
                "auc": r["test"]["cls_roc_auc"],
                "auc_ci95": r["test"]["cls_roc_auc_ci95"],
                "busbra_dice": (ext.get("busbra") or {}).get("dice"),
                "breast_dice": (ext.get("breast") or {}).get("dice"),
                "busuclm_dice": (ext.get("busuclm") or {}).get("dice"),
                "busuclm_lesion_dice": (ext.get("busuclm") or {}).get("lesion_dice"),
                "normal_fp": r["test"]["normal_false_positive_count"],
                "normal_fp_gate_0_96": r["no_lump_gate"]["test_fixed_0_96"]["normal_fp_after"],
                "normal_fp_gate_retuned": r["no_lump_gate"]["test_retuned"]["normal_fp_after"],
                "gate_retuned_thr": r["no_lump_gate"]["test_retuned"]["mask_max_thr"],
                "int8_mb": r["quantization"]["int8_mb"],
                "img_size": r["img_size"],
                "latency_ms_p50": (r.get("latency") or {}).get("ms_p50"),
                "swap_ok": r["swap"]["swap_ok"],
                "abbreviated_pass": r["swap"]["abbreviated_pass"],
                "checks": r["swap"]["checks"],
            }
        )

    passers = [r for r in reports if r["swap"]["swap_ok"]]
    # Prefer highest clean Dice among full-rule passers; else None (do not promote).
    best = None
    if passers:
        best = max(passers, key=lambda r: r["test"]["clean_dice"] or -1)

    # Also surface best by abbreviated Dice+AUC for the UI note (still not live-swapped).
    abbrev_passers = [r for r in reports if r["swap"]["abbreviated_pass"]]
    best_abbrev = (
        max(abbrev_passers, key=lambda r: (r["test"]["dice_mean"] or -1, r["test"]["clean_dice"] or -1))
        if abbrev_passers
        else None
    )

    if best:
        decision = (
            f"Candidate {best['candidate_id']} passed the full D3 swap rule on this run, "
            "but the live served model stays v1.0.0 (no automatic swap). "
            "It is published on Results as a labelled candidate only."
        )
        mean_pass = True
    elif best_abbrev:
        decision = (
            f"No candidate passed the full D3 swap rule (clean + external Dice + AUC). "
            f"{best_abbrev['candidate_id']} passed the abbreviated Dice+AUC check only; "
            "v1.0.0 remains served. Comparison published as experiment."
        )
        mean_pass = False
    else:
        decision = (
            "No v1.1 candidate beat v1.0.0 under the swap rule; the site keeps serving v1.0.0."
        )
        mean_pass = False

    # Criteria rows vs best candidate considered (prefer full passer, else best abbrev, else first)
    focus = best or best_abbrev or (reports[0] if reports else None)
    swap_criteria = []
    if focus:
        c = focus["swap"]["candidate"]
        ch = focus["swap"]["checks"]
        swap_criteria = [
            {
                "criterion": "Clean-subset Dice (BUSI test)",
                "rule": "candidate ≥ v1",
                "v1": V1_BASELINES["clean_dice"],
                "v2": c["clean_dice"],
                "passed": bool(ch["clean_dice_ok"]),
            },
            {
                "criterion": "Held-out Dice (BUSI test)",
                "rule": "candidate ≥ v1",
                "v1": V1_BASELINES["test_dice"],
                "v2": c["dice"],
                "passed": bool(ch["dice_ok"]),
            },
            {
                "criterion": "BUS-BRA Dice (external)",
                "rule": "candidate ≥ v1",
                "v1": V1_BASELINES["busbra_dice"],
                "v2": c["busbra_dice"],
                "passed": bool(ch["busbra_ok"]),
                "note": "Skipped counts as fail for promotion."
                if ch.get("busbra_skipped")
                else "BUSI-only training → full external set.",
            },
            {
                "criterion": "BrEaST Dice (external)",
                "rule": "candidate ≥ v1",
                "v1": V1_BASELINES["breast_dice"],
                "v2": c["breast_dice"],
                "passed": bool(ch["breast_ok"]),
                "note": "Skipped counts as fail for promotion."
                if ch.get("breast_skipped")
                else None,
            },
            {
                "criterion": "AUC (B vs M)",
                "rule": "drop ≤ 0.02",
                "v1": V1_BASELINES["auc"],
                "v2": c["auc"],
                "delta": None if c["auc"] is None else c["auc"] - V1_BASELINES["auc"],
                "passed": bool(ch["auc_ok"]),
            },
            {
                "criterion": "INT8 size",
                "rule": "≤ ~25 MB",
                "v1": V1_BASELINES["int8_mb"],
                "v2": c["int8_mb"],
                "passed": bool(ch["size_ok"]),
            },
        ]

    return {
        "label": "v1.1 BUSI-only candidates vs served v1.0.0 (MODEL_POLICY D3)",
        "note": (
            "Tried larger BUSI-only U-Nets (ResNet-18 @ 224/256, ResNet-34 @ 224) on the same "
            "cleaned data and leakage-safe splits as v1.0.0. Validation-only postprocess and "
            "no-lump gate tuning; held-out test scored once. Live weights not swapped."
        ),
        "hardware": {
            "device": str(DEVICE),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch": torch.__version__,
        },
        "config": {
            "candidates": DEFAULT_CANDIDATES,
            "seed": 42,
            "fold": 0,
            "loss": "pos-weighted BCE + soft Dice (seg) + BCE (cls on B/M only)",
            "selection_metric": "val_lesion_dice",
        },
        "v1_baselines": V1_BASELINES,
        "served_unchanged": True,
        "decision_sentence": decision,
        "mean_pass": mean_pass,
        "best_candidate_id": None if not best else best["candidate_id"],
        "best_abbreviated_candidate_id": None if not best_abbrev else best_abbrev["candidate_id"],
        "promotion_rule": (
            "Full D3: clean Dice ≥ v1, external Dice ≥ v1, AUC drop ≤ 0.02, INT8 ≤ ~25 MB. "
            "Even on pass, this script never rewrites current.json — Results candidate only."
        ),
        "swap_criteria": swap_criteria,
        "table": table,
        "candidates": reports,
        "source": "results/v1_1_experiment.json",
    }


def merge_into_metrics(summary: dict) -> None:
    metrics_path = WEB_PUBLIC / "results" / "metrics.json"
    metrics = json.loads(metrics_path.read_text())
    # Slim block for the Results page (drop bulky nested per-candidate dumps)
    slim_cands = []
    for r in summary.get("candidates", []):
        slim_cands.append(
            {
                "candidate_id": r["candidate_id"],
                "label": r["label"],
                "model_kind": r["model_kind"],
                "img_size": r["img_size"],
                "int8_mb": r["quantization"]["int8_mb"],
                "test_dice": r["test"]["dice_mean"],
                "test_dice_ci95": r["test"]["dice_ci95"],
                "lesion_dice": r["test"]["lesion_dice_mean"],
                "lesion_dice_ci95": r["test"]["lesion_dice_ci95"],
                "iou": r["test"]["iou_mean"],
                "auc": r["test"]["cls_roc_auc"],
                "auc_ci95": r["test"]["cls_roc_auc_ci95"],
                "clean_dice": r["test"]["clean_dice"],
                "normal_fp": r["test"]["normal_false_positive_count"],
                "gate_0_96": r["no_lump_gate"]["test_fixed_0_96"],
                "gate_retuned": r["no_lump_gate"]["test_retuned"],
                "latency_ms_p50": (r.get("latency") or {}).get("ms_p50"),
                "external": r.get("external"),
                "swap_ok": r["swap"]["swap_ok"],
                "abbreviated_pass": r["swap"]["abbreviated_pass"],
                "checks": r["swap"]["checks"],
            }
        )
    metrics["v1_1_experiment"] = {
        "label": summary["label"],
        "note": summary["note"],
        "served_unchanged": True,
        "decision_sentence": summary["decision_sentence"],
        "promotion_rule": summary["promotion_rule"],
        "best_candidate_id": summary.get("best_candidate_id"),
        "best_abbreviated_candidate_id": summary.get("best_abbreviated_candidate_id"),
        "mean_pass": summary.get("mean_pass"),
        "swap_criteria": summary.get("swap_criteria"),
        "table": summary.get("table"),
        "candidates": slim_cands,
        "v1_baselines": summary.get("v1_baselines"),
        "source": "results/v1_1_experiment.json",
    }
    metrics_path.write_text(json.dumps(metrics, indent=2) + "\n")
    print("Updated", metrics_path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--patience", type=int, default=10)
    ap.add_argument("--freeze-epochs", type=int, default=3)
    ap.add_argument("--cls-weight", type=float, default=0.25)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--fold", type=int, default=0)
    ap.add_argument("--force", action="store_true", help="Retrain even if checkpoint exists")
    ap.add_argument("--force-eval", action="store_true", help="Re-run eval/export even if JSON exists")
    ap.add_argument(
        "--only",
        nargs="+",
        default=None,
        help="Candidate ids to run (default: all). e.g. r18_224 r34_224",
    )
    ap.add_argument("--skip-merge-metrics", action="store_true")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RES_DIR.mkdir(parents=True, exist_ok=True)

    cands = DEFAULT_CANDIDATES
    if args.only:
        wanted = set(args.only)
        cands = [c for c in DEFAULT_CANDIDATES if c["id"] in wanted]
        if not cands:
            raise SystemExit(f"No candidates matched --only {args.only}")

    reports = []
    for cand in cands:
        reports.append(evaluate_candidate(cand, args))

    summary = build_experiment_summary(reports)
    out = RESULTS / "v1_1_experiment.json"
    # Store slim summary + pointers; full per-candidate JSON lives under results/v1_1/
    slim = {k: v for k, v in summary.items() if k != "candidates"}
    slim["candidate_files"] = [f"results/v1_1/{r['candidate_id']}.json" for r in reports]
    slim["candidates_summary"] = [
        {
            "candidate_id": r["candidate_id"],
            "swap_ok": r["swap"]["swap_ok"],
            "abbreviated_pass": r["swap"]["abbreviated_pass"],
            "dice": r["test"]["dice_mean"],
            "clean_dice": r["test"]["clean_dice"],
            "auc": r["test"]["cls_roc_auc"],
            "int8_mb": r["quantization"]["int8_mb"],
        }
        for r in reports
    ]
    out.write_text(json.dumps(_sanitize(slim), indent=2))
    print("Wrote", out)
    print("Decision:", summary["decision_sentence"])

    if not args.skip_merge_metrics:
        merge_into_metrics(summary)

    # Safety: never touch current.json
    current = json.loads((WEB_PUBLIC / "models" / "current.json").read_text())
    assert current.get("version") == "1.0.0", "Refusing to leave current.json altered"
    print("Confirmed current.json still points to v1.0.0")


if __name__ == "__main__":
    main()
