#!/usr/bin/env python3
"""Unit tests for display-only no-lump gate math (no ONNX / archives required)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

spec = importlib.util.spec_from_file_location(
    "eval_external_no_lump_gate",
    REPO / "scripts" / "eval_external_no_lump_gate.py",
)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
# Avoid running main; load helpers only by executing module (imports onnxruntime).
# If onnxruntime is missing in a minimal CI, skip.
try:
    spec.loader.exec_module(mod)
except ModuleNotFoundError as e:
    print("SKIP:", e)
    raise SystemExit(0)


def test_apply_gate_hides_low_peak_and_sets_empty_pred_dice():
    rows = [
        {"case_id": "a", "mask_max": 0.95, "dice": 0.8, "iou": 0.7, "gt_area": 100, "pred_area": 90},
        {"case_id": "b", "mask_max": 0.97, "dice": 0.5, "iou": 0.4, "gt_area": 100, "pred_area": 80},
        {"case_id": "c", "mask_max": 0.50, "dice": 0.0, "iou": 0.0, "gt_area": 0, "pred_area": 12},
    ]
    gated = mod.apply_gate(rows, 0.96)
    assert gated[0]["hidden"] is True and gated[0]["gated_dice"] == 0.0 and gated[0]["gated_pred_area"] == 0
    assert gated[1]["hidden"] is False and gated[1]["gated_dice"] == 0.5
    assert gated[2]["hidden"] is True and gated[2]["gated_dice"] == 1.0  # empty vs empty


def test_gate_threshold_matches_pr19_default():
    assert abs(mod.MASK_MAX_THR_DEFAULT - 0.96) < 1e-12


if __name__ == "__main__":
    test_apply_gate_hides_low_peak_and_sets_empty_pred_dice()
    test_gate_threshold_matches_pr19_default()
    print("ok")
