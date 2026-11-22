#!/usr/bin/env python3
"""Test-time averaging (soft-mask + class score) for frozen v1.0.0 — no retraining.

Averages predictions over a small set of views (identity + horizontal flip;
optional mild shifts / scales). Geometric transforms are undone before averaging.
Applies the live-site 0.96 no-lump display gate when scoring outlines.

Writes:
  results/tta_averaging.json
  results/tta_averaging_per_image.json
  docs/TTA_AVERAGING.md  (plain-language write-up; caller may also update)

Does not change model weights.
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
from PIL import Image
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

# Avoid importing busi_data (pulls torch). Inline the shared helpers we need.
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
RESULTS = REPO / "results"
WEB_PUBLIC = REPO / "web" / "public"
PROCESSED = REPO / "data" / "processed"

SEG_THRESH = 0.4
MIN_AREA = 40
CLS_THRESH = 0.5
NO_LUMP_MASK_MAX_THR = 0.96
IMG_SIZE = 160


def resize_rgb_bilinear(arr: np.ndarray, out_size: int) -> np.ndarray:
    if arr.ndim != 3 or arr.shape[2] < 3:
        raise ValueError(f"expected HWC RGB array, got {arr.shape}")
    src = arr.astype(np.float64)
    sh, sw = src.shape[0], src.shape[1]
    dh = dw = int(out_size)
    ys = (np.arange(dh) + 0.5) * sh / dh - 0.5
    xs = (np.arange(dw) + 0.5) * sw / dw - 0.5
    ys = np.clip(ys, 0.0, sh - 1.0)
    xs = np.clip(xs, 0.0, sw - 1.0)
    y0 = np.floor(ys).astype(np.int64)
    x0 = np.floor(xs).astype(np.int64)
    y1 = np.minimum(y0 + 1, sh - 1)
    x1 = np.minimum(x0 + 1, sw - 1)
    fy = (ys - y0).reshape(dh, 1, 1)
    fx = (xs - x0).reshape(1, dw, 1)
    Ia = src[y0][:, x0]
    Ib = src[y0][:, x1]
    Ic = src[y1][:, x0]
    Id = src[y1][:, x1]
    wa = (1 - fx) * (1 - fy)
    wb = fx * (1 - fy)
    wc = (1 - fx) * fy
    wd = fx * fy
    return wa * Ia + wb * Ib + wc * Ic + wd * Id


def imagenet_tensor_from_rgb(arr_hwc: np.ndarray, img_size: int = 160) -> np.ndarray:
    resized = resize_rgb_bilinear(arr_hwc, img_size)
    arr = (resized / 255.0).astype(np.float32)
    mean = np.array(IMAGENET_MEAN, dtype=np.float32).reshape(1, 1, 3)
    std = np.array(IMAGENET_STD, dtype=np.float32).reshape(1, 1, 3)
    arr = (arr - mean) / std
    return np.transpose(arr, (2, 0, 1))[None, ...].astype(np.float32)


def dice_score(pred: np.ndarray, gt: np.ndarray, eps: float = 1e-6) -> float:
    pred = pred.astype(bool).ravel()
    gt = gt.astype(bool).ravel()
    if pred.sum() == 0 and gt.sum() == 0:
        return 1.0
    inter = np.logical_and(pred, gt).sum()
    return float((2 * inter + eps) / (pred.sum() + gt.sum() + eps))


def iou_score(pred: np.ndarray, gt: np.ndarray, eps: float = 1e-6) -> float:
    pred = pred.astype(bool).ravel()
    gt = gt.astype(bool).ravel()
    if pred.sum() == 0 and gt.sum() == 0:
        return 1.0
    inter = np.logical_and(pred, gt).sum()
    union = np.logical_or(pred, gt).sum()
    return float((inter + eps) / (union + eps))


def bootstrap_ci(
    values: np.ndarray,
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float, float]:
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    means = []
    n = len(values)
    for _ in range(n_boot):
        sample = values[rng.integers(0, n, n)]
        means.append(sample.mean())
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return float(values.mean()), float(lo), float(hi)


def remove_small_components(mask: np.ndarray, min_area: int) -> np.ndarray:
    if min_area <= 0:
        return mask
    from scipy import ndimage

    labeled, n = ndimage.label(mask.astype(bool))
    if n == 0:
        return mask.astype(bool)
    out = np.zeros_like(mask, dtype=bool)
    for i in range(1, n + 1):
        comp = labeled == i
        if int(comp.sum()) >= min_area:
            out |= comp
    return out


def load_mask(path: str, img_size: int = 160) -> np.ndarray:
    m = Image.open(path).convert("L")
    m = m.resize((img_size, img_size), Image.NEAREST)
    return np.asarray(m) > 127


# --- geometric views (applied at model resolution after bilinear resize) -------------

def shift2d(arr: np.ndarray, dy: int, dx: int) -> np.ndarray:
    """Translate HxW or HxWxC; fill with edge values."""
    h, w = arr.shape[:2]
    ys = np.clip(np.arange(h) - dy, 0, h - 1)
    xs = np.clip(np.arange(w) - dx, 0, w - 1)
    return arr[ys][:, xs].copy()


def scale2d(arr: np.ndarray, scale: float) -> np.ndarray:
    """Mild center zoom on HxW or HxWxC float/uint8, then back to original size."""
    if abs(scale - 1.0) < 1e-6:
        return arr
    h, w = arr.shape[:2]
    nh, nw = max(1, int(round(h * scale))), max(1, int(round(w * scale)))
    # Use PIL; promote single-channel to L / multi to RGB
    if arr.ndim == 2:
        mode = "F" if np.issubdtype(arr.dtype, np.floating) else "L"
        pil = Image.fromarray(arr.astype(np.float32 if mode == "F" else np.uint8), mode=mode)
        resized = pil.resize((nw, nh), Image.BILINEAR)
        if scale >= 1.0:
            cl, ct = (nw - w) // 2, (nh - h) // 2
            out = resized.crop((cl, ct, cl + w, ct + h))
            return np.asarray(out, dtype=np.float32)
        canvas = Image.new(mode, (w, h), 0)
        canvas.paste(resized, ((w - nw) // 2, (h - nh) // 2))
        return np.asarray(canvas, dtype=np.float32)
    # HWC
    if arr.dtype != np.uint8:
        arr_u8 = np.clip(arr, 0, 255).astype(np.uint8)
    else:
        arr_u8 = arr
    pil = Image.fromarray(arr_u8, mode="RGB")
    resized = pil.resize((nw, nh), Image.BILINEAR)
    if scale >= 1.0:
        cl, ct = (nw - w) // 2, (nh - h) // 2
        return np.asarray(resized.crop((cl, ct, cl + w, ct + h)))
    canvas = Image.new("RGB", (w, h), (0, 0, 0))
    canvas.paste(resized, ((w - nw) // 2, (h - nh) // 2))
    return np.asarray(canvas)


def build_views(preset: str) -> list[dict]:
    """Return list of view specs: {id, hflip, dy, dx, scale}."""
    if preset == "single":
        return [{"id": "id", "hflip": False, "dy": 0, "dx": 0, "scale": 1.0}]
    if preset == "hflip2":
        return [
            {"id": "id", "hflip": False, "dy": 0, "dx": 0, "scale": 1.0},
            {"id": "h", "hflip": True, "dy": 0, "dx": 0, "scale": 1.0},
        ]
    if preset == "hflip_shift":
        return [
            {"id": "id", "hflip": False, "dy": 0, "dx": 0, "scale": 1.0},
            {"id": "h", "hflip": True, "dy": 0, "dx": 0, "scale": 1.0},
            {"id": "u4", "hflip": False, "dy": -4, "dx": 0, "scale": 1.0},
            {"id": "d4", "hflip": False, "dy": 4, "dx": 0, "scale": 1.0},
            {"id": "l4", "hflip": False, "dy": 0, "dx": -4, "scale": 1.0},
            {"id": "r4", "hflip": False, "dy": 0, "dx": 4, "scale": 1.0},
        ]
    if preset == "hflip_scale":
        return [
            {"id": "id", "hflip": False, "dy": 0, "dx": 0, "scale": 1.0},
            {"id": "h", "hflip": True, "dy": 0, "dx": 0, "scale": 1.0},
            {"id": "s095", "hflip": False, "dy": 0, "dx": 0, "scale": 0.95},
            {"id": "s105", "hflip": False, "dy": 0, "dx": 0, "scale": 1.05},
        ]
    raise ValueError(f"unknown preset: {preset}")


def apply_view_resized(rgb160: np.ndarray, spec: dict) -> np.ndarray:
    """Apply geometry on already-resized HxWx3 uint8 canvas."""
    out = rgb160
    if abs(spec["scale"] - 1.0) > 1e-6:
        out = scale2d(out, spec["scale"])
    if spec["dy"] or spec["dx"]:
        out = shift2d(out, spec["dy"], spec["dx"])
    if spec["hflip"]:
        out = np.flip(out, axis=1).copy()
    return out


def undo_view_soft(soft: np.ndarray, spec: dict) -> np.ndarray:
    """Undo geometry on soft mask (reverse order of apply)."""
    out = soft.astype(np.float32)
    if spec["hflip"]:
        out = np.flip(out, axis=1).copy()
    if spec["dy"] or spec["dx"]:
        out = shift2d(out, -spec["dy"], -spec["dx"])
    if abs(spec["scale"] - 1.0) > 1e-6:
        out = scale2d(out, 1.0 / spec["scale"])
    return out.astype(np.float32)


def tensor_from_resized_rgb(rgb160: np.ndarray) -> np.ndarray:
    arr = (rgb160.astype(np.float32) / 255.0)
    mean = np.array(IMAGENET_MEAN, dtype=np.float32).reshape(1, 1, 3)
    std = np.array(IMAGENET_STD, dtype=np.float32).reshape(1, 1, 3)
    arr = (arr - mean) / std
    return np.transpose(arr, (2, 0, 1))[None, ...].astype(np.float32)


def run_views(
    sess: ort.InferenceSession,
    rgb: np.ndarray,
    views: list[dict],
    img_size: int = IMG_SIZE,
) -> tuple[np.ndarray, float, float, list[float]]:
    """Return mean_soft, mean_cls, soft_max, per-view ms."""
    names = [o.name for o in sess.get_outputs()]
    rgb160 = np.clip(resize_rgb_bilinear(rgb, img_size), 0, 255).astype(np.uint8)
    masks = []
    probs = []
    times = []
    for spec in views:
        view_rgb = apply_view_resized(rgb160, spec)
        x = tensor_from_resized_rgb(view_rgb)
        t0 = time.perf_counter()
        outs = sess.run(None, {"input": x})
        times.append((time.perf_counter() - t0) * 1000.0)
        seg = outs[names.index("seg_mask")] if "seg_mask" in names else outs[0]
        cls = outs[names.index("cls_prob")] if "cls_prob" in names else outs[1]
        soft = seg[0, 0].astype(np.float32)
        soft = undo_view_soft(soft, spec)
        masks.append(soft)
        probs.append(float(cls.reshape(-1)[0]))
    mean_soft = np.mean(np.stack(masks, axis=0), axis=0).astype(np.float32)
    mean_cls = float(np.mean(probs))
    return mean_soft, mean_cls, float(mean_soft.max()), times


def postprocess(soft: np.ndarray, apply_gate: bool) -> tuple[np.ndarray, float, bool]:
    """Binary mask after morphology; optionally zero out under no-lump gate."""
    soft_max = float(soft.max())
    gated = bool(apply_gate and soft_max < NO_LUMP_MASK_MAX_THR)
    if gated:
        return np.zeros_like(soft, dtype=bool), soft_max, True
    binary = soft > SEG_THRESH
    kept = remove_small_components(binary, MIN_AREA)
    return kept, soft_max, False


def summarize_rows(rows: list[dict], clusters: np.ndarray | None = None) -> dict:
    from sklearn.metrics import roc_auc_score

    dice = np.array([r["dice"] for r in rows], dtype=float)
    iou = np.array([r["iou"] for r in rows], dtype=float)
    d_m, d_lo, d_hi = bootstrap_ci(dice)
    i_m, i_lo, i_hi = bootstrap_ci(iou)

    lesion = [r for r in rows if r["label"] != "normal"]
    lesion_dice = np.array([r["dice"] for r in lesion], dtype=float)
    ld_m, ld_lo, ld_hi = bootstrap_ci(lesion_dice)

    # Patient-cluster bootstrap override when provided (external sets)
    if clusters is not None:
        from external.common import bootstrap_mean_ci

        d_m, d_ci = bootstrap_mean_ci(dice, clusters=clusters)
        d_lo, d_hi = d_ci[0], d_ci[1]
        i_m, i_ci = bootstrap_mean_ci(iou, clusters=clusters)
        i_lo, i_hi = i_ci[0], i_ci[1]
        lesion_idx = [i for i, r in enumerate(rows) if r["label"] != "normal"]
        if lesion_idx:
            ld_m, ld_ci = bootstrap_mean_ci(
                lesion_dice, clusters=clusters[lesion_idx]
            )
            ld_lo, ld_hi = ld_ci[0], ld_ci[1]

    normals = [r for r in rows if r["label"] == "normal"]
    normal_fp = [r for r in normals if r["pred_area"] > 0]

    cls_rows = [r for r in rows if r.get("cls_target") is not None and r["cls_target"] >= 0]
    auc = None
    if len(cls_rows) >= 5:
        y = np.array([int(r["cls_target"]) for r in cls_rows])
        p = np.array([r["cls_prob"] for r in cls_rows])
        if len(np.unique(y)) == 2:
            auc = float(roc_auc_score(y, p))

    ms = np.array([r["ms_total"] for r in rows], dtype=float)
    return {
        "n": len(rows),
        "dice_mean": d_m,
        "dice_ci95": [d_lo, d_hi],
        "iou_mean": i_m,
        "iou_ci95": [i_lo, i_hi],
        "lesion_dice_mean": ld_m,
        "lesion_dice_ci95": [ld_lo, ld_hi],
        "lesion_n": len(lesion),
        "cls_roc_auc": auc,
        "normal_n": len(normals),
        "normal_false_positive_count": len(normal_fp),
        "normal_false_positive_rate": (len(normal_fp) / len(normals)) if normals else None,
        "ms_mean": float(ms.mean()) if len(ms) else None,
        "ms_median": float(np.median(ms)) if len(ms) else None,
        "gated_count": int(sum(1 for r in rows if r["gated"])),
    }


def score_case(
    sess: ort.InferenceSession,
    rgb: np.ndarray,
    gt: np.ndarray,
    label: str,
    cls_target: float | None,
    views: list[dict],
    apply_gate: bool,
) -> dict:
    soft, cls_prob, soft_max, times = run_views(sess, rgb, views)
    pred, soft_max2, gated = postprocess(soft, apply_gate)
    soft_max = soft_max2
    d = dice_score(pred, gt)
    i = iou_score(pred, gt)
    return {
        "label": label,
        "cls_target": cls_target,
        "cls_prob": cls_prob,
        "soft_max": soft_max,
        "gated": gated,
        "dice": d,
        "iou": i,
        "gt_area": int(gt.sum()),
        "pred_area": int(pred.sum()),
        "ms_total": float(sum(times)),
        "ms_per_view": [float(t) for t in times],
        "n_views": len(views),
    }


def eval_busi(sess: ort.InferenceSession, presets: list[str], apply_gate: bool, limit: int) -> dict:
    manifest = pd.read_csv(PROCESSED / "manifest.csv").set_index("case_id")
    splits = json.loads((RESULTS / "splits.json").read_text())
    test_ids = list(splits["test_ids"])
    if limit:
        test_ids = test_ids[:limit]

    out_presets = {}
    all_rows = {}
    for preset in presets:
        views = build_views(preset)
        rows = []
        for cid in tqdm(test_ids, desc=f"BUSI/{preset}"):
            row = manifest.loc[cid]
            rgb = np.asarray(Image.open(row["image_path"]).convert("RGB"))
            gt = load_mask(row["merged_mask_path"], IMG_SIZE)
            if str(row["label"]) == "normal":
                gt = np.zeros_like(gt)
            cls_t = float(row["cls_target"])
            r = score_case(sess, rgb, gt, str(row["label"]), cls_t, views, apply_gate)
            r["case_id"] = cid
            r["dataset"] = "busi_test"
            r["preset"] = preset
            rows.append(r)
        out_presets[preset] = summarize_rows(rows)
        out_presets[preset]["n_views"] = len(views)
        out_presets[preset]["view_ids"] = [v["id"] for v in views]
        all_rows[preset] = rows
    return {"summary": out_presets, "rows": all_rows}


def eval_external(
    sess: ort.InferenceSession,
    name: str,
    presets: list[str],
    apply_gate: bool,
    limit: int,
) -> dict | None:
    try:
        if name == "busbra":
            from external.busbra import build_manifest
        elif name == "breast":
            from external.breast import build_manifest
        elif name == "busuclm":
            from external.busuclm import build_manifest
        else:
            raise ValueError(name)
        manifest = build_manifest()
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": str(exc)}

    if manifest is None or len(manifest) == 0:
        return {"available": False, "error": "empty manifest"}

    from external.common import load_mask_binary, load_rgb

    if limit:
        manifest = manifest.head(limit)

    out_presets = {}
    all_rows = {}
    for preset in presets:
        views = build_views(preset)
        rows = []
        for _, r in tqdm(manifest.iterrows(), total=len(manifest), desc=f"{name}/{preset}"):
            rgb = load_rgb(r["image_path"])
            gt = load_mask_binary(r["mask_path"] if r["mask_path"] else None, IMG_SIZE)
            if r["label"] == "normal":
                gt = np.zeros_like(gt)
            cls_t = (
                1.0
                if r["label"] == "malignant"
                else (0.0 if r["label"] == "benign" else None)
            )
            scored = score_case(sess, rgb, gt, str(r["label"]), cls_t, views, apply_gate)
            scored["case_id"] = r["case_id"]
            scored["patient_id"] = r["patient_id"]
            scored["dataset"] = name
            scored["preset"] = preset
            rows.append(scored)
        clusters = np.array([str(r["patient_id"]) for r in rows])
        out_presets[preset] = summarize_rows(rows, clusters=clusters)
        out_presets[preset]["n_views"] = len(views)
        out_presets[preset]["view_ids"] = [v["id"] for v in views]
        all_rows[preset] = rows

    return {"available": True, "summary": out_presets, "rows": all_rows}


def decide(busi_summary: dict) -> dict:
    """Recommend keep only if outline improves, AUC not hurt, time ≲ 2×.

    Compares best multi-view preset against single. Primary candidate: hflip2.
    """
    single = busi_summary["single"]
    candidates = []
    for name in ("hflip2", "hflip_scale", "hflip_shift"):
        if name not in busi_summary:
            continue
        s = busi_summary[name]
        dice_delta = s["dice_mean"] - single["dice_mean"]
        lesion_delta = s["lesion_dice_mean"] - single["lesion_dice_mean"]
        auc_delta = None
        if s["cls_roc_auc"] is not None and single["cls_roc_auc"] is not None:
            auc_delta = s["cls_roc_auc"] - single["cls_roc_auc"]
        time_ratio = (
            s["ms_mean"] / single["ms_mean"]
            if single["ms_mean"] and s["ms_mean"]
            else None
        )
        # "Improves outline": lesion Dice up (or all-image Dice up with lesion not down)
        outline_better = lesion_delta > 0.001 or (
            dice_delta > 0.001 and lesion_delta >= -0.001
        )
        auc_ok = auc_delta is None or auc_delta >= -0.005
        time_ok = time_ratio is None or time_ratio <= 2.15  # small slack over 2×
        fp_delta = None
        if s["normal_false_positive_count"] is not None and single[
            "normal_false_positive_count"
        ] is not None:
            fp_delta = (
                s["normal_false_positive_count"] - single["normal_false_positive_count"]
            )
        keep = bool(outline_better and auc_ok and time_ok)
        candidates.append(
            {
                "preset": name,
                "keep": keep,
                "dice_delta": dice_delta,
                "lesion_dice_delta": lesion_delta,
                "auc_delta": auc_delta,
                "time_ratio": time_ratio,
                "normal_fp_delta": fp_delta,
                "outline_better": outline_better,
                "auc_ok": auc_ok,
                "time_ok": time_ok,
            }
        )

    # Prefer hflip2 if it qualifies; else any qualifying; else none
    chosen = None
    for c in candidates:
        if c["preset"] == "hflip2" and c["keep"]:
            chosen = c
            break
    if chosen is None:
        for c in candidates:
            if c["keep"]:
                chosen = c
                break

    return {
        "recommend_ship": chosen is not None,
        "chosen_preset": chosen["preset"] if chosen else None,
        "candidates": candidates,
        "rule": (
            "Ship only if lesion/all Dice improves (>0.001), AUC drop ≤ 0.005, "
            "and offline ONNX time ratio ≤ ~2.15× (proxy for browser ~2×)."
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--onnx",
        type=Path,
        default=WEB_PUBLIC / "models" / "v1.0.0" / "busi_unet.onnx",
    )
    ap.add_argument(
        "--presets",
        nargs="+",
        default=["single", "hflip2", "hflip_scale", "hflip_shift"],
    )
    ap.add_argument("--no-gate", action="store_true", help="Disable 0.96 no-lump gate")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--skip-external", action="store_true")
    args = ap.parse_args()

    apply_gate = not args.no_gate
    sha = hashlib.sha256(args.onnx.read_bytes()).hexdigest()
    sess = ort.InferenceSession(str(args.onnx), providers=["CPUExecutionProvider"])

    # Warmup
    _ = sess.run(None, {"input": np.zeros((1, 3, IMG_SIZE, IMG_SIZE), dtype=np.float32)})

    busi = eval_busi(sess, args.presets, apply_gate, args.limit)
    decision = decide(busi["summary"])

    external = {}
    if not args.skip_external:
        for name in ("busbra", "breast", "busuclm"):
            external[name] = eval_external(
                sess, name, args.presets, apply_gate, args.limit
            )

    # Flatten a compact per-image dump (single + chosen/hflip2 only to keep size sane)
    keep_presets = {"single", "hflip2"}
    if decision["chosen_preset"]:
        keep_presets.add(decision["chosen_preset"])
    per_image = []
    for preset, rows in busi["rows"].items():
        if preset in keep_presets:
            per_image.extend(rows)
    for ds, block in external.items():
        if not block or not block.get("available"):
            continue
        for preset, rows in block.get("rows", {}).items():
            if preset in keep_presets:
                # Drop bulky timing lists for external to keep file smaller
                for r in rows:
                    r2 = {k: v for k, v in r.items() if k != "ms_per_view"}
                    per_image.append(r2)

    # Strip full external rows from summary payload
    external_summary = {}
    for ds, block in external.items():
        if not block:
            continue
        if not block.get("available"):
            external_summary[ds] = {"available": False, "error": block.get("error")}
        else:
            external_summary[ds] = {
                "available": True,
                "summary": block["summary"],
            }

    out = {
        "label": "Test-time averaging (soft mask + class score) for v1.0.0 — no retraining",
        "disclaimer": "Research demo. Not for clinical use. Display / inference option only.",
        "model_path": str(args.onnx.relative_to(REPO)),
        "model_sha256": sha,
        "seg_threshold": SEG_THRESH,
        "min_component_area": MIN_AREA,
        "no_lump_mask_max_thr": NO_LUMP_MASK_MAX_THR if apply_gate else None,
        "gate_applied": apply_gate,
        "presets": {
            p: [v["id"] for v in build_views(p)] for p in args.presets
        },
        "busi_test": busi["summary"],
        "external": external_summary,
        "decision": decision,
        "plain_summary": (
            "Tried averaging the outline and the harmless/cancerous score over a few "
            "slightly changed views of the same image (flip, optional small shift/zoom), "
            "then put each view back before averaging. Same served model weights."
        ),
    }

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "tta_averaging.json").write_text(json.dumps(out, indent=2) + "\n")
    (RESULTS / "tta_averaging_per_image.json").write_text(
        json.dumps(per_image, indent=2) + "\n"
    )

    # Compact console table
    print("\n=== BUSI held-out test (gate={}) ===".format(apply_gate))
    hdr = f"{'preset':<14} {'Dice':>8} {'Lesion':>8} {'IoU':>8} {'AUC':>8} {'N-FP':>6} {'ms':>8} {'×':>5}"
    print(hdr)
    base_ms = busi["summary"]["single"]["ms_mean"] or 1.0
    for p in args.presets:
        s = busi["summary"][p]
        ratio = (s["ms_mean"] / base_ms) if s["ms_mean"] else float("nan")
        auc = s["cls_roc_auc"]
        print(
            f"{p:<14} {s['dice_mean']:8.4f} {s['lesion_dice_mean']:8.4f} "
            f"{s['iou_mean']:8.4f} {auc if auc is not None else float('nan'):8.4f} "
            f"{s['normal_false_positive_count'] or 0:6d} {s['ms_mean']:8.1f} {ratio:5.2f}"
        )
    print("\nDecision:", json.dumps(decision, indent=2))
    print("Wrote", RESULTS / "tta_averaging.json")


if __name__ == "__main__":
    main()
