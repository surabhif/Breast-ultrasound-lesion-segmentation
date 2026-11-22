#!/usr/bin/env python3
"""Re-score external sets with the display-only no-lump gate (mask_max < 0.96).

Uses the same frozen v1.0.0 INT8 ONNX, splits/manifests, preprocessing, and
post-process thresholds as scripts/eval_external.py. Does **not** change the
served model or the gate threshold (fixed from results/no_lump_gate.json /
PR #19). Does **not** rewrite BUSI held-out numbers.

Writes:
  results/external/no_lump_gate_external.json
  updates external block in results/no_lump_gate.json
  + web/public/results/no_lump_gate.json

If a dataset archive is missing, records the skip reason and continues.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
import pandas as pd
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import (  # noqa: E402
    RESULTS,
    WEB_PUBLIC,
    dice_score,
    imagenet_tensor_from_rgb,
    iou_score,
    remove_small_components,
)
from external.breast import build_manifest as build_breast  # noqa: E402
from external.busbra import build_manifest as build_busbra  # noqa: E402
from external.busuclm import build_manifest as build_busuclm  # noqa: E402
from external.common import (  # noqa: E402
    RESULTS_EXTERNAL,
    bootstrap_mean_ci,
    load_mask_binary,
    load_rgb,
    write_json,
)

try:
    from sklearn.metrics import roc_auc_score
except ImportError:
    roc_auc_score = None  # type: ignore


MASK_MAX_THR_DEFAULT = 0.96


def soft_mask(seg: np.ndarray) -> np.ndarray:
    """Match eval_external / browser: served INT8 outputs probabilities in [0, 1]."""
    soft = seg.astype(np.float32)
    if float(soft.min()) < 0 or float(soft.max()) > 1.1:
        soft = 1.0 / (1.0 + np.exp(-soft))
    return soft.astype(np.float32)


def score_rows(name: str, manifest: pd.DataFrame, sess, seg_thresh: float, min_area: int) -> list[dict]:
    rows: list[dict] = []
    onames = [o.name for o in sess.get_outputs()]
    for _, r in tqdm(manifest.iterrows(), total=len(manifest), desc=name):
        x = imagenet_tensor_from_rgb(load_rgb(r["image_path"]), 160)
        outs = sess.run(None, {"input": x})
        seg = outs[onames.index("seg_mask")] if "seg_mask" in onames else outs[0]
        cls = outs[onames.index("cls_prob")] if "cls_prob" in onames else outs[1]
        soft = soft_mask(seg[0, 0])
        cls_prob = float(cls.reshape(-1)[0])
        binary = soft > seg_thresh
        kept = remove_small_components(binary, min_area)
        gt = load_mask_binary(r["mask_path"] if r["mask_path"] else None, 160)
        if r["label"] == "normal":
            gt = np.zeros_like(gt)
        pred = kept.astype(bool)
        d = dice_score(pred, gt)
        i = iou_score(pred, gt)
        rows.append(
            {
                "case_id": r["case_id"],
                "label": r["label"],
                "patient_id": str(r["patient_id"]),
                "dice": float(d),
                "iou": float(i),
                "cls_prob": cls_prob,
                "gt_area": int(gt.sum()),
                "pred_area": int(kept.sum()),
                "mask_max": float(soft.max()),
                "cls_target": 1.0
                if r["label"] == "malignant"
                else (0.0 if r["label"] == "benign" else None),
            }
        )
    return rows


def apply_gate(rows: list[dict], thr: float) -> list[dict]:
    out = []
    for r in rows:
        hide = r["mask_max"] < thr
        if hide:
            # Empty prediction (display hide)
            gated_dice = 1.0 if r["gt_area"] == 0 else 0.0
            gated_iou = 1.0 if r["gt_area"] == 0 else 0.0
            gated_pred_area = 0
        else:
            gated_dice = r["dice"]
            gated_iou = r["iou"]
            gated_pred_area = r["pred_area"]
        out.append(
            {
                **r,
                "hidden": hide,
                "gated_dice": float(gated_dice),
                "gated_iou": float(gated_iou),
                "gated_pred_area": int(gated_pred_area),
            }
        )
    return out


def metric_block(values: np.ndarray, clusters: np.ndarray) -> dict:
    mean, ci = bootstrap_mean_ci(values, clusters=clusters)
    return {"mean": mean, "bootstrap_95ci": ci}


def summarize(name: str, rows_raw: list[dict], thr: float, sha: str, seg_thresh: float, min_area: int) -> dict:
    gated = apply_gate(rows_raw, thr)
    df = pd.DataFrame(gated)
    clusters = df["patient_id"].astype(str).to_numpy()

    lesion = df[df["label"].isin(["benign", "malignant"])]
    lesion_c = lesion["patient_id"].astype(str).to_numpy()
    normals = df[df["label"] == "normal"]
    n_normal = int(len(normals))

    fp_before = int((normals["pred_area"] > 0).sum()) if n_normal else None
    fp_after = (
        int(((~normals["hidden"]) & (normals["pred_area"] > 0)).sum()) if n_normal else None
    )

    # AUC from classification head — display gate does not change it
    bm = df[df["label"].isin(["benign", "malignant"])].dropna(subset=["cls_target"])
    cls_auc = None
    if len(bm) >= 5 and roc_auc_score is not None:
        try:
            cls_auc = float(roc_auc_score(bm["cls_target"].to_numpy(dtype=float), bm["cls_prob"].to_numpy(dtype=float)))
        except ValueError:
            cls_auc = None

    dice_before = metric_block(df["dice"].to_numpy(), clusters)
    dice_after = metric_block(df["gated_dice"].to_numpy(), clusters)
    iou_before = metric_block(df["iou"].to_numpy(), clusters)
    iou_after = metric_block(df["gated_iou"].to_numpy(), clusters)
    lesion_before = metric_block(lesion["dice"].to_numpy(), lesion_c)
    lesion_after = metric_block(lesion["gated_dice"].to_numpy(), lesion_c)

    n_hidden = int(df["hidden"].sum())
    n_hidden_lesion = int(lesion["hidden"].sum()) if len(lesion) else 0

    plain_bits = []
    d_drop = lesion_before["mean"] - lesion_after["mean"]
    if d_drop > 0.02:
        plain_bits.append(
            f"Lump-only Dice got worse ({lesion_before['mean']:.3f} → {lesion_after['mean']:.3f}; drop {d_drop:.3f})."
        )
    elif d_drop > 1e-6:
        plain_bits.append(
            f"Lump-only Dice got slightly worse ({lesion_before['mean']:.3f} → {lesion_after['mean']:.3f})."
        )
    elif d_drop < -0.02:
        plain_bits.append(
            f"Lump-only Dice got better ({lesion_before['mean']:.3f} → {lesion_after['mean']:.3f})."
        )
    elif d_drop < -1e-6:
        plain_bits.append(
            f"Lump-only Dice got slightly better ({lesion_before['mean']:.3f} → {lesion_after['mean']:.3f})."
        )
    else:
        plain_bits.append("Lump-only Dice stayed the same.")

    if n_normal:
        plain_bits.append(
            f"False outlines on normal scans: {fp_before}/{n_normal} → {fp_after}/{n_normal}."
        )
    else:
        plain_bits.append("This set has no normal (no-lump) scans, so false-outline rate does not apply.")

    plain_bits.append("AUC is unchanged (the display gate does not touch the class score).")

    return {
        "dataset": name,
        "model_version": "1.0.0",
        "model_sha256": sha,
        "protocol": "docs/EXTERNAL_VALIDATION_PROTOCOL.md",
        "gate": {
            "rule": "Hide outline when peak soft-mask value is below threshold (display only).",
            "mask_max_thr": thr,
            "source": "results/no_lump_gate.json (PR #19; chosen on BUSI validation fold 0)",
            "seg_threshold": seg_thresh,
            "min_component_area": min_area,
        },
        "n": int(len(df)),
        "n_patients": int(df["patient_id"].nunique()),
        "n_normal": n_normal,
        "n_hidden": n_hidden,
        "n_hidden_lesion": n_hidden_lesion,
        "raw": {
            "test_dice": dice_before["mean"],
            "test_dice_bootstrap_95ci": dice_before["bootstrap_95ci"],
            "lesion_dice": lesion_before["mean"],
            "lesion_dice_bootstrap_95ci": lesion_before["bootstrap_95ci"],
            "test_iou": iou_before["mean"],
            "test_iou_bootstrap_95ci": iou_before["bootstrap_95ci"],
            "cls_roc_auc": cls_auc,
            "normal_false_positive_count": fp_before,
            "normal_n": n_normal,
        },
        "with_no_lump_gate": {
            "test_dice": dice_after["mean"],
            "test_dice_bootstrap_95ci": dice_after["bootstrap_95ci"],
            "lesion_dice": lesion_after["mean"],
            "lesion_dice_bootstrap_95ci": lesion_after["bootstrap_95ci"],
            "test_iou": iou_after["mean"],
            "test_iou_bootstrap_95ci": iou_after["bootstrap_95ci"],
            "cls_roc_auc": cls_auc,
            "normal_false_positive_count": fp_after,
            "normal_n": n_normal,
            "lesion_dice_drop": float(d_drop),
        },
        "plain_summary": " ".join(plain_bits),
    }


def update_no_lump_gate_json(payload_external: dict, skipped: dict, thr: float) -> None:
    paths = [RESULTS / "no_lump_gate.json", WEB_PUBLIC / "results" / "no_lump_gate.json"]
    base = json.loads(paths[0].read_text())
    # Keep BUSI held-out / validation numbers untouched.
    external_out: dict = {}
    for name, summary in payload_external.items():
        raw = summary["raw"]
        gated = summary["with_no_lump_gate"]
        external_out[name] = {
            "n": summary["n"],
            "n_normal": summary["n_normal"],
            "mask_max_thr": thr,
            "scored": True,
            "raw": {
                "test_dice": raw["test_dice"],
                "test_dice_bootstrap_95ci": raw["test_dice_bootstrap_95ci"],
                "lesion_dice": raw["lesion_dice"],
                "lesion_dice_bootstrap_95ci": raw["lesion_dice_bootstrap_95ci"],
                "test_iou": raw["test_iou"],
                "test_iou_bootstrap_95ci": raw["test_iou_bootstrap_95ci"],
                "cls_roc_auc": raw["cls_roc_auc"],
                "normal_false_positive_count": raw["normal_false_positive_count"],
                "normal_n": raw["normal_n"],
            },
            "with_no_lump_gate": {
                "test_dice": gated["test_dice"],
                "test_dice_bootstrap_95ci": gated["test_dice_bootstrap_95ci"],
                "lesion_dice": gated["lesion_dice"],
                "lesion_dice_bootstrap_95ci": gated["lesion_dice_bootstrap_95ci"],
                "test_iou": gated["test_iou"],
                "test_iou_bootstrap_95ci": gated["test_iou_bootstrap_95ci"],
                "cls_roc_auc": gated["cls_roc_auc"],
                "normal_false_positive_count": gated["normal_false_positive_count"],
                "normal_n": gated["normal_n"],
                "lesion_dice_drop": gated["lesion_dice_drop"],
            },
            # Back-compat fields used by older copy
            "lesion_dice_before": raw["lesion_dice"],
            "lesion_dice_after": gated["lesion_dice"],
            "normal_fp_before": raw["normal_false_positive_count"],
            "normal_fp_after": gated["normal_false_positive_count"],
            "plain_summary": summary["plain_summary"],
        }

    for name, reason in skipped.items():
        external_out[name] = {
            "scored": False,
            "note": reason,
            "unavailable_on_vm": True,
        }

    base["external"] = external_out
    if "busuclm" in skipped:
        base["busuclm_note"] = (
            "BUS-UCLM was not re-scored with the no-lump gate on this VM: the Mendeley archive "
            "is not available here (download returned HTTP 403 without interactive login; see "
            "docs/BUSUCLM_STEPS.md). Published raw numbers stay as-is in results/external/busuclm.json "
            "(overall Dice 0.386, lesion Dice 0.679, AUC 0.780, false outlines on normal 320/413). "
            "No gated before/after numbers are claimed for BUS-UCLM."
        )
    elif "busuclm" in payload_external:
        base["busuclm_note"] = payload_external["busuclm"]["plain_summary"]

    base["plain_summary_external"] = (
        "Outside sets re-scored with the same display-only gate (peak soft-mask < "
        f"{thr:.2f}). Raw = without gate; with no-lump gate = outline hidden when peak is low. "
        "AUC unchanged. BUSI held-out numbers were not changed."
    )
    text = json.dumps(base, indent=2) + "\n"
    for p in paths:
        p.write_text(text)
        print("Updated", p)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--datasets", nargs="+", default=["busbra", "breast", "busuclm"])
    ap.add_argument(
        "--mask-max-thr",
        type=float,
        default=None,
        help="Override gate threshold (default: value from results/no_lump_gate.json, else 0.96)",
    )
    args = ap.parse_args()

    gate_path = RESULTS / "no_lump_gate.json"
    gate_doc = json.loads(gate_path.read_text())
    thr = float(
        args.mask_max_thr
        if args.mask_max_thr is not None
        else gate_doc.get("selection", {}).get("mask_max_thr", MASK_MAX_THR_DEFAULT)
    )
    # Do not retune — pin to published PR #19 value.
    if abs(thr - MASK_MAX_THR_DEFAULT) > 1e-9 and args.mask_max_thr is None:
        # Keep whatever is in JSON if someone changed it, but warn.
        print(f"Using mask_max_thr={thr} from {gate_path}")

    pp = json.loads((RESULTS / "postprocess.json").read_text())
    seg_thresh = float(pp["seg_threshold"])
    min_area = int(pp["min_component_area"])

    onnx = WEB_PUBLIC / "models" / "v1.0.0" / "busi_unet.onnx"
    sha = hashlib.sha256(onnx.read_bytes()).hexdigest()
    assert sha.startswith("0bbf529d"), f"Model sha mismatch: {sha}"
    sess = ort.InferenceSession(str(onnx), providers=["CPUExecutionProvider"])

    builders = {
        "busbra": build_busbra,
        "breast": build_breast,
        "busuclm": build_busuclm,
    }

    summaries: dict = {}
    skipped: dict = {}
    per_image_dir = RESULTS_EXTERNAL / "no_lump_gate_per_image"
    per_image_dir.mkdir(parents=True, exist_ok=True)

    for name in args.datasets:
        try:
            man = builders[name]()
        except FileNotFoundError as e:
            skipped[name] = str(e)
            print(f"SKIP {name}: {e}")
            continue
        rows = score_rows(name, man, sess, seg_thresh, min_area)
        summary = summarize(name, rows, thr, sha, seg_thresh, min_area)
        summaries[name] = summary
        write_json(per_image_dir / f"{name}.json", rows)
        print(
            f"{name}: raw Dice={summary['raw']['test_dice']:.3f} "
            f"gated={summary['with_no_lump_gate']['test_dice']:.3f} "
            f"lesion {summary['raw']['lesion_dice']:.3f}→"
            f"{summary['with_no_lump_gate']['lesion_dice']:.3f} "
            f"AUC={summary['raw']['cls_roc_auc']}"
        )

    payload = {
        "label": "Outside-set re-score with display-only no-lump gate",
        "disclaimer": "Research demo. Not for clinical use. Display option only. Model weights unchanged.",
        "mask_max_thr": thr,
        "model_version": "1.0.0",
        "model_sha256": sha,
        "datasets": summaries,
        "skipped": skipped,
    }
    write_json(RESULTS_EXTERNAL / "no_lump_gate_external.json", payload)
    update_no_lump_gate_json(summaries, skipped, thr)
    if skipped:
        print("Skipped:", skipped)


if __name__ == "__main__":
    main()
