#!/usr/bin/env python3
"""Score served v1.0.0 INT8 on the Phase 4 patient-grouped BUS-BRA held-out split.

Fair baseline for v2 swap: v2 trains on BUS-BRA train, so full-set 0.714 is not
comparable. Writes results/v2/v1_busbra_heldout.json.
"""

from __future__ import annotations

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
    bootstrap_ci,
    dice_score,
    imagenet_tensor_from_rgb,
    iou_score,
    remove_small_components,
)
from external.busbra import build_manifest as build_busbra  # noqa: E402
from external.common import load_mask_binary, load_rgb  # noqa: E402

V2_RESULTS = RESULTS / "v2"
SPLIT = V2_RESULTS / "busbra_patient_split.json"
OUT = V2_RESULTS / "v1_busbra_heldout.json"


def main() -> None:
    if not SPLIT.exists():
        raise SystemExit(f"Missing {SPLIT}; run train_v2.py first (writes the split).")
    split = json.loads(SPLIT.read_text())
    test_ids = set(split["test_ids"])
    man = build_busbra()
    held = man[man["case_id"].isin(test_ids)].reset_index(drop=True)
    if len(held) == 0:
        raise SystemExit("Held-out BUS-BRA IDs matched 0 rows")

    pp = json.loads((RESULTS / "postprocess.json").read_text())
    seg_thresh = float(pp["seg_threshold"])
    min_area = int(pp["min_component_area"])

    onnx = WEB_PUBLIC / "models" / "v1.0.0" / "busi_unet.onnx"
    sha = hashlib.sha256(onnx.read_bytes()).hexdigest()
    sess = ort.InferenceSession(str(onnx), providers=["CPUExecutionProvider"])
    img_size = 160  # v1 contract

    rows = []
    for _, r in tqdm(held.iterrows(), total=len(held), desc="v1@BUS-BRA held-out"):
        x = imagenet_tensor_from_rgb(load_rgb(r["image_path"]), img_size)
        outs = sess.run(None, {"input": x})
        onames = [o.name for o in sess.get_outputs()]
        seg = outs[onames.index("seg_mask")] if "seg_mask" in onames else outs[0]
        cls = outs[onames.index("cls_prob")] if "cls_prob" in onames else outs[1]
        soft = seg[0, 0].astype(np.float32)
        pred = soft > seg_thresh
        if min_area > 0:
            pred = remove_small_components(pred, min_area)
        gt = load_mask_binary(r["mask_path"], img_size)
        d = dice_score(pred, gt)
        rows.append(
            {
                "case_id": r["case_id"],
                "patient_id": r["patient_id"],
                "label": r["label"],
                "dice": d,
                "iou": iou_score(pred, gt),
                "cls_prob": float(cls.reshape(-1)[0]),
            }
        )

    df = pd.DataFrame(rows)
    d_mean, d_lo, d_hi = bootstrap_ci(df["dice"].to_numpy())
    lesion = df[df["label"].isin(["benign", "malignant"])]
    ld_mean, ld_lo, ld_hi = bootstrap_ci(lesion["dice"].to_numpy())
    auc = None
    try:
        from sklearn.metrics import roc_auc_score

        y = (df["label"] == "malignant").astype(float).to_numpy()
        p = df["cls_prob"].to_numpy()
        auc = float(roc_auc_score(y, p))
    except Exception:  # noqa: BLE001
        auc = None

    out = {
        "label": "v1.0.0 INT8 on Phase-4 patient-grouped BUS-BRA held-out split",
        "note": (
            "Fair baseline for v2: same held-out case IDs as results/v2/busbra_patient_split.json. "
            "Not comparable to full-set BUS-BRA Dice 0.714 (v1 never trained on BUS-BRA; v2 does)."
        ),
        "role": "same_source_heldout_baseline",
        "model_version": "1.0.0",
        "model_sha256": sha,
        "img_size": img_size,
        "seg_threshold": seg_thresh,
        "min_component_area": min_area,
        "n": int(len(df)),
        "n_patients": int(df["patient_id"].nunique()),
        "dice_mean": d_mean,
        "dice_ci95": [d_lo, d_hi],
        "lesion_dice_mean": ld_mean,
        "lesion_dice_ci95": [ld_lo, ld_hi],
        "cls_roc_auc": auc,
        "split_seed": split.get("split_seed"),
        "test_frac": split.get("test_frac"),
        "source_split": "results/v2/busbra_patient_split.json",
    }
    V2_RESULTS.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(
        f"Wrote {OUT}: Dice={d_mean:.3f} [{d_lo:.3f},{d_hi:.3f}] "
        f"lesion={ld_mean:.3f} AUC={auc} n={len(df)}"
    )


if __name__ == "__main__":
    main()
