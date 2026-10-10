#!/usr/bin/env python3
"""Unit tests for external loaders (no full BUS-UCLM / BUS-BRA / BrEaST archives required)."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from external.busbra import build_manifest as build_busbra  # noqa: E402
from external.breast import build_manifest as build_breast  # noqa: E402
from external.busuclm import build_manifest as build_busuclm  # noqa: E402
from external.common import load_mask_binary  # noqa: E402


def test_load_mask_binary_grayscale_and_pure_red():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        # Binary / grayscale: white lesion on black — same as old L>127 behaviour.
        gray_arr = np.zeros((32, 32), dtype=np.uint8)
        gray_arr[8:24, 8:24] = 255
        gray_path = root / "gray.png"
        Image.fromarray(gray_arr, mode="L").save(gray_path)
        g = load_mask_binary(gray_path, img_size=32)
        assert g.dtype == bool
        assert g[16, 16]
        assert not g[0, 0]
        assert int(g.sum()) == 16 * 16

        # Pure-red malignant BUS-UCLM mask: L≈76 under convert("L"), so old rule emptied it.
        red_arr = np.zeros((32, 32, 3), dtype=np.uint8)
        red_arr[4:20, 4:20] = (255, 0, 0)
        red_path = root / "red.png"
        Image.fromarray(red_arr, mode="RGB").save(red_path)
        r = load_mask_binary(red_path, img_size=32)
        assert r[10, 10]
        assert not r[0, 0]
        assert int(r.sum()) == 16 * 16


def test_busuclm_info_csv_parse_and_doppler_filter():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        img_dir = root / "images"
        mask_dir = root / "masks"
        img_dir.mkdir()
        mask_dir.mkdir()
        # Three synthetic cases: keep two, drop one Doppler-flagged.
        rows = [
            ("ALWI_000.png", "benign", "No", "No"),
            ("ALWI_001.png", "malignant", "Yes", "No"),
            ("BETA_010.png", "normal", "No", "No"),
        ]
        for name, _label, _d, _c in rows:
            Image.new("RGB", (8, 8), (10, 10, 10)).save(img_dir / name)
            Image.new("RGB", (8, 8), (255, 0, 0)).save(mask_dir / name)
        csv_path = root / "INFO.csv"
        csv_path.write_text(
            "Image;Label;Doppler;Combined\n"
            + "\n".join(f"{n};{lab};{d};{c}" for n, lab, d, c in rows)
            + "\n"
        )
        df = build_busuclm(root)
        assert len(df) == 2, df
        assert set(df["case_id"]) == {"ALWI_000", "BETA_010"}
        assert set(df["patient_id"]) == {"ALWI", "BETA"}
        assert int(df["patient_id"].nunique()) == 2
        assert (df["dataset"] == "busuclm").all()
        assert not df["has_doppler"].astype(bool).any()


def test_busbra_breast_loaders_skip_without_archive():
    """Existing primary loaders still raise a clear skip when data is absent."""
    missing = Path("/tmp/definitely-missing-external-data-busi-demo")
    for builder, name in ((build_busbra, "BUS-BRA"), (build_breast, "BrEaST")):
        try:
            builder(missing)
            raise AssertionError(f"{name} should raise FileNotFoundError without archive")
        except FileNotFoundError as e:
            assert name.split("-")[0].lower() in str(e).lower() or "not found" in str(e).lower() or name in str(e)


if __name__ == "__main__":
    test_load_mask_binary_grayscale_and_pure_red()
    test_busuclm_info_csv_parse_and_doppler_filter()
    test_busbra_breast_loaders_skip_without_archive()
    print("All external loader tests passed.")
