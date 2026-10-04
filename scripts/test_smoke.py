#!/usr/bin/env python3
"""Lightweight smoke tests (no full dataset required for import checks)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))


def test_model_forward():
    import torch
    from model_def import build_model

    for kind in ("tiny", "resnet18"):
        m = build_model(kind, pretrained=False)
        x = torch.randn(2, 3, 64 if kind == "tiny" else 128, 64 if kind == "tiny" else 128)
        seg, cls = m(x)
        assert seg.shape[0] == 2 and cls.shape[0] == 2


def test_metrics_json_schema():
    path = REPO / "web" / "public" / "results" / "metrics.json"
    data = json.loads(path.read_text())
    assert data["schema_version"] == 1
    assert "test_dice" in data["metrics"]
    assert data["metrics"]["test_dice"] > 0
    assert data["metrics"].get("cls_roc_auc") is not None
    assert Path(REPO / "web" / "public" / "models" / "busi_unet.onnx").exists()


def test_audit_and_splits_exist():
    assert (REPO / "results" / "audit_calipers_duplicates.csv").exists()
    splits = json.loads((REPO / "results" / "splits.json").read_text())
    assert "test_ids" in splits and len(splits["folds"]) == 5
    assert "patient" in splits["note"].lower() or "patient" in splits["note"]


def test_onnx_runs():
    import numpy as np
    import onnxruntime as ort

    path = REPO / "web" / "public" / "models" / "busi_unet.onnx"
    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    # Infer size
    shape = sess.get_inputs()[0].shape
    h = int(shape[2]) if isinstance(shape[2], int) else 128
    x = np.random.randn(1, 3, h, h).astype(np.float32)
    outs = sess.run(None, {"input": x})
    assert len(outs) == 2
    assert outs[0].shape[-2:] == (h, h)


if __name__ == "__main__":
    test_model_forward()
    test_metrics_json_schema()
    test_audit_and_splits_exist()
    test_onnx_runs()
    print("All smoke tests passed.")
