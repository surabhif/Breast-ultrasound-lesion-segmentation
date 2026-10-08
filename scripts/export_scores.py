#!/usr/bin/env python3
"""Export per-image classification scores for the Results threshold slider."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import RESULTS, WEB_PUBLIC, load_manifest, load_splits  # noqa: E402


def main() -> None:
    per = json.loads((RESULTS / "served_int8_per_image.json").read_text())
    # Also try full_test for FP32 reference
    fp32 = []
    fp32_path = RESULTS / "full_test_per_image.json"
    if fp32_path.exists():
        fp32 = json.loads(fp32_path.read_text())
    fp32_by = {r["case_id"]: r for r in fp32} if fp32 else {}

    splits = load_splits()
    test_ids = set(splits["test_ids"])
    val_ids = set(splits.get("val_ids") or [])

    rows = []
    for r in per:
        cid = r["case_id"]
        label = r["label"]
        if label not in ("benign", "malignant"):
            continue
        rows.append(
            {
                "case_id": cid,
                "split": "test" if cid in test_ids else ("val" if cid in val_ids else "other"),
                "label": label,
                "y_true": 1 if label == "malignant" else 0,
                "cls_prob": float(r["cls_prob"]),
                "dice": float(r.get("dice", r.get("dice_score", 0))),
                "annotation_flag": bool(r.get("annotation_flag", False)),
                "fp32_cls_prob": float(fp32_by[cid]["cls_prob"]) if cid in fp32_by else None,
            }
        )

    out = {
        "disclaimer": "Research only. PPV/NPV depend on prevalence; test set is not a screening population.",
        "reported_threshold": 0.5,
        "source": "results/served_int8_per_image.json",
        "n_test_bm": sum(1 for r in rows if r["split"] == "test"),
        "rows": rows,
    }
    dest = WEB_PUBLIC / "results" / "scores.json"
    dest.write_text(json.dumps(out, indent=2) + "\n")
    print(f"Wrote {dest} n={len(rows)}")


if __name__ == "__main__":
    main()
