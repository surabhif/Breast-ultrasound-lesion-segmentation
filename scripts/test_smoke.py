#!/usr/bin/env python3
"""Lightweight smoke tests (no full dataset required for import checks)."""

from __future__ import annotations

import hashlib
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
    assert data["schema_version"] == 2
    assert "test_dice" in data["metrics"]
    assert data["metrics"]["test_dice"] > 0
    assert data["metrics"].get("cls_roc_auc") is not None
    assert data.get("model_version") == "1.0.0"
    served = data.get("served_int8")
    assert served is not None, "served_int8 block required in schema v2"
    assert served["test_dice"] > 0
    assert served["normal_false_positive_count"] >= 0
    assert (REPO / "web" / "public" / "models" / "v1.0.0" / "busi_unet.onnx").exists()
    assert (REPO / "web" / "public" / "models" / "current.json").exists()


def test_audit_and_splits_exist():
    assert (REPO / "results" / "audit_calipers_duplicates.csv").exists()
    splits = json.loads((REPO / "results" / "splits.json").read_text())
    assert "test_ids" in splits and len(splits["folds"]) == 5
    assert "patient" in splits["note"].lower() or "patient" in splits["note"]


def test_onnx_runs():
    import numpy as np
    import onnxruntime as ort

    path = REPO / "web" / "public" / "models" / "v1.0.0" / "busi_unet.onnx"
    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    shape = sess.get_inputs()[0].shape
    h = int(shape[2]) if isinstance(shape[2], int) else 160
    x = np.random.randn(1, 3, h, h).astype(np.float32)
    outs = sess.run(None, {"input": x})
    assert len(outs) == 2
    assert outs[0].shape[-2:] == (h, h)

    cur = json.loads((REPO / "web" / "public" / "models" / "current.json").read_text())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    assert digest == cur["sha256"]


def test_external_protocol_preregistered():
    path = REPO / "docs" / "EXTERNAL_VALIDATION_PROTOCOL.md"
    assert path.exists()
    text = path.read_text()
    assert "v1.0.0" in text
    assert "0bbf529d" in text
    assert "BUS-BRA" in text and "BrEaST" in text
    assert "MODEL_POLICY" in text
    assert "no more than 0.02" in text or "no more than **0.02**" in text


def test_external_results_or_skip_documented():
    ext = REPO / "results" / "external"
    assert (REPO / "docs" / "DECISION_LOG.md").exists()
    decision = (REPO / "docs" / "DECISION_LOG.md").read_text()
    assert "D4 revoked" in decision or "REVOKED" in decision
    assert not (REPO / "docs" / "CLINICIAN_REVIEW.md").exists()
    assert not (REPO / "web" / "src" / "pages" / "ReviewPage.tsx").exists()
    assert (REPO / "docs" / "LITERATURE_COMPARISON.md").exists()
    # At least one primary external result, or an explicit skip file
    has_busbra = (ext / "busbra.json").exists()
    has_breast = (ext / "breast.json").exists()
    assert has_busbra and has_breast, "Phase 1 expects BUS-BRA and BrEaST results"
    metrics = json.loads((REPO / "web" / "public" / "results" / "metrics.json").read_text())
    assert "external" in metrics and "datasets" in metrics["external"]
    assert "busbra" in metrics["external"]["datasets"]
    assert "breast" in metrics["external"]["datasets"]


if __name__ == "__main__":
    test_model_forward()
    test_metrics_json_schema()
    test_audit_and_splits_exist()
    test_onnx_runs()
    test_external_protocol_preregistered()
    test_external_results_or_skip_documented()
    print("All smoke tests passed.")
