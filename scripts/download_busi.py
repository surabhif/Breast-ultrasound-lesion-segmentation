#!/usr/bin/env python3
"""Download the BUSI dataset from a public Hugging Face mirror (no API key).

Primary source used by this project:
  https://huggingface.co/datasets/gymprathap/Breast-Cancer-Ultrasound-Images-Dataset

This is a public mirror of Dataset_BUSI_with_GT (Al-Dhabyani et al., 2020).
Kaggle (aryashah2k/breast-ultrasound-images-dataset) is documented as an
alternative but requires a Kaggle API key, so it is not used by default.

The original Cairo University page is:
  https://scholar.cu.edu.eg/?q=afahmy/pages/dataset

Do NOT commit the full dataset — license is not clearly stated for redistribution.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

REPO = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO / "data" / "raw"

HF_URL = (
    "https://huggingface.co/datasets/gymprathap/"
    "Breast-Cancer-Ultrasound-Images-Dataset/resolve/main/"
    "Breast-Cancer-Ultrasound-Images-Dataset.zip"
)
EXPECTED_SHA256 = None  # optional integrity check; set if pinned
ZIP_NAME = "Breast-Cancer-Ultrasound-Images-Dataset.zip"


def _progress(block_num: int, block_size: int, total_size: int) -> None:
    if total_size <= 0:
        return
    done = min(block_num * block_size, total_size)
    pct = 100.0 * done / total_size
    mb = done / 1e6
    total_mb = total_size / 1e6
    sys.stdout.write(f"\rDownloading… {mb:.1f}/{total_mb:.1f} MB ({pct:.1f}%)")
    sys.stdout.flush()


def download(out_dir: Path, force: bool = False) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / ZIP_NAME
    extract_root = out_dir / "extracted"
    marker = extract_root / "Dataset_BUSI_with_GT"

    if marker.is_dir() and not force:
        n = sum(1 for _ in marker.rglob("*.png"))
        print(f"BUSI already present at {marker} ({n} PNGs). Use --force to re-download.")
        return marker

    if force and zip_path.exists():
        zip_path.unlink()

    if not zip_path.exists():
        print(f"Fetching BUSI from Hugging Face mirror…\n  {HF_URL}")
        urlretrieve(HF_URL, zip_path, reporthook=_progress)
        print()
    else:
        print(f"Using existing zip: {zip_path}")

    if EXPECTED_SHA256:
        h = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        if h != EXPECTED_SHA256:
            raise RuntimeError(f"SHA256 mismatch: got {h}")

    if extract_root.exists() and force:
        shutil.rmtree(extract_root)
    extract_root.mkdir(parents=True, exist_ok=True)

    print(f"Extracting to {extract_root}…")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_root)

    if not marker.is_dir():
        # tolerate nested layouts
        candidates = list(extract_root.rglob("Dataset_BUSI_with_GT"))
        if not candidates:
            raise FileNotFoundError(
                f"Expected Dataset_BUSI_with_GT under {extract_root}"
            )
        marker = candidates[0]

    n = sum(1 for _ in marker.rglob("*.png"))
    print(f"Ready: {marker} ({n} PNG files)")
    print(
        "Citation: Al-Dhabyani W, Gomaa M, Khaled H, Fahmy A. "
        "Dataset of breast ultrasound images. Data in Brief. 2020;28:104863."
    )
    return marker


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    download(args.out_dir, force=args.force)


if __name__ == "__main__":
    main()
