#!/usr/bin/env python3
"""Assert JS morphology contract matches Python remove_small_components."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import remove_small_components  # noqa: E402


def test_synthetic_matches_reference_shape() -> None:
    # Same layout as web/src/lib/morphology.test.ts
    bin5 = np.zeros((5, 5), dtype=bool)
    bin5[1, 1] = True
    bin5[2:4, 3:5] = True
    out = remove_small_components(bin5, min_area=3)
    assert not out[1, 1]
    assert out[2:4, 3:5].all()


def test_parity_reference_exists() -> None:
    path = REPO / "tests" / "parity" / "reference.json"
    assert path.exists(), "Run scripts/parity_reference.py"
    data = json.loads(path.read_text())
    assert data["model_version"] == "1.0.0"
    assert data["seg_threshold"] == 0.4
    assert data["min_component_area"] == 40
    assert len(data["cases"]) >= 6
    assert all(c["kind"] == "gallery" for c in data["cases"])


def test_model_sha_matches_file() -> None:
    import hashlib

    cur = json.loads((REPO / "web" / "public" / "models" / "current.json").read_text())
    onnx = REPO / "web" / "public" / "models" / "v1.0.0" / "busi_unet.onnx"
    digest = hashlib.sha256(onnx.read_bytes()).hexdigest()
    assert digest == cur["sha256"]
    man = json.loads((REPO / "web" / "public" / "models" / "v1.0.0" / "model.json").read_text())
    assert man["sha256"] == digest
    assert man["postprocess"]["min_component_area"] == 40


if __name__ == "__main__":
    test_synthetic_matches_reference_shape()
    test_parity_reference_exists()
    test_model_sha_matches_file()
    print("Morphology / versioning parity checks passed.")
