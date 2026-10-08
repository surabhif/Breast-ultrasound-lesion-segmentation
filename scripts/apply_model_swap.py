#!/usr/bin/env python3
"""Apply pre-registered MODEL_POLICY: maybe promote best E-c seed to v2.0.0.

Criteria vs served v1.0.0 INT8:
  1) clean-subset Dice >= v1 clean-subset Dice
  2) external Dice on BUS-BRA and BrEaST >= v1
  3) BUSI AUC drops by no more than 0.02

If fail: keep v1 served; write experiment block into metrics.json.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
WEB = REPO / "web" / "public"
INPAINT = RESULTS / "inpaint_experiment.json"
METRICS = WEB / "results" / "metrics.json"
V1 = WEB / "models" / "v1.0.0"


def main() -> None:
    if not INPAINT.exists():
        print("No inpaint_experiment.json yet")
        sys.exit(1)
    exp = json.loads(INPAINT.read_text())
    metrics = json.loads(METRICS.read_text())

    v1_clean = None
    # From cleaning experiment / served per-image
    clean_block = (metrics.get("cleaning_experiment") or {}).get("full_model_clean_vs_flagged") or {}
    v1_clean = (clean_block.get("clean_test") or {}).get("dice_mean")
    if v1_clean is None:
        # fallback: E-a clean_original
        v1_clean = ((exp.get("E_a") or {}).get("clean_original") or {}).get("dice_mean")

    v1_busbra = ((metrics.get("external") or {}).get("datasets") or {}).get("busbra", {}).get("test_dice")
    v1_breast = ((metrics.get("external") or {}).get("datasets") or {}).get("breast", {}).get("test_dice")
    v1_auc = ((metrics.get("external") or {}).get("internal_busi_int8") or {}).get("cls_roc_auc")
    if v1_auc is None:
        v1_auc = (metrics.get("served_int8") or {}).get("cls_roc_auc")

    best = (exp.get("E_c") or {}).get("best")
    table = [
        {
            "name": "v1 original test",
            "dice": (exp.get("E_a") or {}).get("original", {}).get("dice_mean"),
            "lesion_dice": (exp.get("E_a") or {}).get("original", {}).get("lesion_dice_mean"),
            "auc": (exp.get("E_a") or {}).get("original", {}).get("cls_roc_auc"),
        },
        {
            "name": "v1 on inpainted test (E-a)",
            "dice": (exp.get("E_a") or {}).get("inpainted", {}).get("dice_mean"),
            "lesion_dice": (exp.get("E_a") or {}).get("inpainted", {}).get("lesion_dice_mean"),
            "auc": (exp.get("E_a") or {}).get("inpainted", {}).get("cls_roc_auc"),
        },
        {
            "name": "E-b random inpaint (clean)",
            "dice": (exp.get("E_b") or {}).get("clean_random_inpaint", {}).get("dice_mean"),
            "lesion_dice": (exp.get("E_b") or {}).get("clean_random_inpaint", {}).get("lesion_dice_mean"),
            "auc": (exp.get("E_b") or {}).get("clean_random_inpaint", {}).get("cls_roc_auc"),
        },
    ]

    swap_ok = False
    swap_note = "E-c not finished"
    if best:
        c_clean = (best.get("test_clean_subset_original") or {}).get("dice_mean")
        c_auc = (best.get("test_original") or {}).get("cls_roc_auc")
        c_busbra = (best.get("external_busbra") or {}).get("dice_mean")
        c_breast = (best.get("external_breast") or {}).get("dice_mean")
        checks = {
            "clean_dice_ok": c_clean is not None and v1_clean is not None and c_clean >= v1_clean - 1e-9,
            "busbra_ok": c_busbra is not None and v1_busbra is not None and c_busbra >= v1_busbra - 1e-9,
            "breast_ok": c_breast is not None and v1_breast is not None and c_breast >= v1_breast - 1e-9,
            "auc_ok": c_auc is not None and v1_auc is not None and (v1_auc - c_auc) <= 0.02 + 1e-9,
        }
        swap_ok = all(checks.values())
        swap_note = (
            f"seed {best['seed']}: clean {c_clean:.3f} vs v1 {v1_clean:.3f}; "
            f"BUS-BRA {c_busbra} vs {v1_busbra}; BrEaST {c_breast} vs {v1_breast}; "
            f"AUC {c_auc} vs {v1_auc}; checks={checks}"
        )
        table.append(
            {
                "name": f"E-c best seed {best['seed']} (original test)",
                "dice": (best.get("test_original") or {}).get("dice_mean"),
                "lesion_dice": (best.get("test_original") or {}).get("lesion_dice_mean"),
                "auc": c_auc,
            }
        )

    if swap_ok and best:
        v2_dir = WEB / "models" / "v2.0.0"
        v2_dir.mkdir(parents=True, exist_ok=True)
        src = Path(best["onnx"])
        dest = v2_dir / "busi_unet.onnx"
        shutil.copy2(src, dest)
        sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        model_json = {
            "version": "2.0.0",
            "sha256": sha,
            "filename": "busi_unet.onnx",
            "parent": "1.0.0",
            "note": "Inpaint-retrained candidate that passed MODEL_POLICY swap rule",
            "swap_note": swap_note,
        }
        (v2_dir / "model.json").write_text(json.dumps(model_json, indent=2) + "\n")
        current = {
            "version": "2.0.0",
            "path": "models/v2.0.0/busi_unet.onnx",
            "sha256": sha,
            "cache_key": f"busi-unet-v2.0.0-{sha[:8]}",
        }
        (WEB / "models" / "current.json").write_text(json.dumps(current, indent=2) + "\n")
        print("PROMOTED v2.0.0", swap_note)
        served_unchanged = False
    else:
        print("KEEP v1.0.0 —", swap_note)
        served_unchanged = True

    metrics["inpaint_experiment"] = {
        "served_unchanged": served_unchanged,
        "swap_note": swap_note,
        "table": table,
        "before_after_note": "Demo before/after uses CC BY BrEaST sample with synthetic calipers (digitally altered), not BUSI pixels.",
        "source": "results/inpaint_experiment.json",
    }
    METRICS.write_text(json.dumps(metrics, indent=2) + "\n")
    exp["model_policy_decision"] = {
        "swap_ok": swap_ok,
        "served_unchanged": served_unchanged,
        "note": swap_note,
    }
    INPAINT.write_text(json.dumps(exp, indent=2) + "\n")


if __name__ == "__main__":
    main()
