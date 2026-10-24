#!/usr/bin/env python3
"""Tune display-only 'no lump' outline gate on BUSI validation (fold 0).

Hide the outline when peak soft-mask value < threshold.
Selection: clear as many normal false outlines as possible on validation
without dropping lesion Dice by more than 0.01. Then report held-out test.

Does not change served weights. Writes results/no_lump_gate.json and
web/public/results/no_lump_gate.json.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image
from tqdm import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import (  # noqa: E402
    RESULTS,
    WEB_PUBLIC,
    dice_score,
    imagenet_tensor_from_rgb,
    load_manifest,
    load_splits,
    remove_small_components,
)

SEG_THR = 0.4
MIN_AREA = 40
IMG = 160


def predict_rows(ids: list[str], session, manifest_by_id: dict) -> list[dict]:
    rows = []
    for case_id in tqdm(ids, desc="score"):
        item = manifest_by_id[case_id]
        rgb = np.array(Image.open(item["image_path"]).convert("RGB"))
        tensor = imagenet_tensor_from_rgb(rgb, IMG)
        seg_out, cls_out = session.run(
            ["seg_mask", "cls_prob"], {"input": tensor.astype(np.float32)}
        )
        seg = seg_out[0, 0]
        soft = (
            1.0 / (1.0 + np.exp(-seg))
            if float(seg.min()) < 0 or float(seg.max()) > 1.1
            else seg.astype(np.float32)
        ).astype(np.float32)
        binary = (soft > SEG_THR).astype(np.uint8)
        binary = remove_small_components(binary, MIN_AREA)
        mask_path = item.get("merged_mask_path") or str(item["mask_paths"]).split(";")[0]
        gt = np.array(Image.open(mask_path).convert("L"))
        gt = (
            np.array(Image.fromarray(gt).resize((IMG, IMG), Image.NEAREST)) > 127
        ).astype(np.float32)
        rows.append(
            {
                "case_id": case_id,
                "label": item["label"],
                "pred_area": int(binary.sum()),
                "mask_max": float(soft.max()),
                "cls_prob": float(cls_out[0, 0]),
                "dice": float(dice_score(binary.astype(np.float32), gt)),
                "gt_area": int(gt.sum()),
            }
        )
    return rows


def lesion_dice(rows: list[dict], key: str = "dice") -> float:
    xs = [r[key] for r in rows if r["label"] != "normal"]
    return float(np.mean(xs)) if xs else float("nan")


def apply_gate(rows: list[dict], thr: float) -> list[dict]:
    out = []
    for r in rows:
        hide = r["mask_max"] < thr
        d = (1.0 if r["gt_area"] == 0 else 0.0) if hide else r["dice"]
        out.append({**r, "gated_dice": d, "hidden": hide})
    return out


def main() -> None:
    splits = load_splits()
    fold0 = next(f for f in splits["folds"] if f["fold"] == 0)
    session = ort.InferenceSession(
        str(WEB_PUBLIC / "models" / "v1.0.0" / "busi_unet.onnx"),
        providers=["CPUExecutionProvider"],
    )
    manifest = {row["case_id"]: row for row in load_manifest().to_dict(orient="records")}

    val_rows = predict_rows(fold0["val_ids"], session, manifest)
    base_les = lesion_dice(val_rows)
    base_fp = sum(1 for r in val_rows if r["label"] == "normal" and r["pred_area"] > 0)
    base_n = sum(1 for r in val_rows if r["label"] == "normal")

    best = None
    for thr in np.linspace(0.5, 0.995, 100):
        gated = apply_gate(val_rows, float(thr))
        drop = base_les - lesion_dice(gated, "gated_dice")
        fp = sum(
            1
            for r in gated
            if r["label"] == "normal" and not r["hidden"] and r["pred_area"] > 0
        )
        cleared = base_fp - fp
        if drop <= 0.01 + 1e-12:
            cand = {
                "mask_max_thr": float(thr),
                "val_lesion_dice": lesion_dice(gated, "gated_dice"),
                "val_lesion_dice_drop": float(drop),
                "val_normal_fp": fp,
                "val_normal_n": base_n,
                "val_fp_cleared": cleared,
            }
            if best is None or cleared > best["val_fp_cleared"] or (
                cleared == best["val_fp_cleared"] and drop < best["val_lesion_dice_drop"]
            ):
                best = cand

    if best is None or best["val_fp_cleared"] <= 0:
        default_on = False
        thr = 0.96
        best = best or {
            "mask_max_thr": thr,
            "val_lesion_dice": base_les,
            "val_lesion_dice_drop": 0.0,
            "val_normal_fp": base_fp,
            "val_normal_n": base_n,
            "val_fp_cleared": 0,
        }
    else:
        thr = best["mask_max_thr"]
        default_on = True

    test_rows = predict_rows(splits["test_ids"], session, manifest)
    gated_test = apply_gate(test_rows, thr)
    t_base = lesion_dice(test_rows)
    t_gate = lesion_dice(gated_test, "gated_dice")
    drop_test = t_base - t_gate
    if drop_test > 0.01:
        default_on = False

    t_fp0 = sum(1 for r in test_rows if r["label"] == "normal" and r["pred_area"] > 0)
    t_fp1 = sum(
        1
        for r in gated_test
        if r["label"] == "normal" and not r["hidden"] and r["pred_area"] > 0
    )
    t_n = sum(1 for r in test_rows if r["label"] == "normal")

    payload = {
        "label": "Display-only no-lump outline gate (does not change served weights)",
        "disclaimer": "Research demo. Not for clinical use. Display option only.",
        "selection": {
            "split": "BUSI validation fold 0",
            "rule": (
                "Hide outline when peak soft-mask value is below a threshold. "
                "Chosen to clear the most normal false outlines on validation "
                "without dropping lesion Dice by more than 0.01."
            ),
            "seg_threshold": SEG_THR,
            "min_component_area": MIN_AREA,
            "mask_max_thr": thr,
            "default_on": default_on,
            **best,
        },
        "busi_validation": {
            "n": len(val_rows),
            "lesion_dice_before": base_les,
            "lesion_dice_after": best["val_lesion_dice"],
            "normal_fp_before": base_fp,
            "normal_fp_after": best["val_normal_fp"],
            "normal_n": base_n,
        },
        "busi_test": {
            "n": len(test_rows),
            "dice_all_before": float(np.mean([r["dice"] for r in test_rows])),
            "dice_all_after": float(np.mean([r["gated_dice"] for r in gated_test])),
            "lesion_dice_before": t_base,
            "lesion_dice_after": t_gate,
            "lesion_dice_drop": drop_test,
            "normal_fp_before": t_fp0,
            "normal_fp_after": t_fp1,
            "normal_n": t_n,
        },
        "external": {
            "busbra": {
                "note": "Outside per-image files lack soft-mask max; gate not re-applied without images."
            },
            "breast": {
                "note": "Outside per-image files lack soft-mask max; gate not re-applied without images."
            },
        },
        "busuclm_note": (
            "BUS-UCLM per-image soft masks are not in the repo, so this display gate was not "
            "re-scored there. Aggregate false outlines on normal scans remain 320/413 without "
            "applying the gate."
        ),
        "plain_summary": (
            f"Hide the outline when the model’s strongest outline pixel is below {thr:.3f} "
            f"(chosen on BUSI validation). "
            + ("Default on." if default_on else "Default off.")
        ),
    }
    out = RESULTS / "no_lump_gate.json"
    web = WEB_PUBLIC / "results" / "no_lump_gate.json"
    out.write_text(json.dumps(payload, indent=2))
    web.write_text(json.dumps(payload, indent=2))
    print("Wrote", out)
    print("default_on", default_on, "thr", thr, "test", payload["busi_test"])


if __name__ == "__main__":
    main()
