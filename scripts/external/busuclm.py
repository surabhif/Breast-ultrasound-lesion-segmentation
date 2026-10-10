"""BUS-UCLM loader (Mendeley doi:10.17632/7fvgj4jsp7.3, CC BY 4.0).

Secondary dataset. If the archive is not present under data/external/busuclm/,
callers should skip evaluation and record the access failure.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from .common import EXTERNAL_ROOT, ensure_manifest

ROOT = EXTERNAL_ROOT / "busuclm"


def find_raw_root(root: Path = ROOT) -> Path | None:
    if not root.exists():
        return None
    # Accept either extracted tree or a single zip already unpacked to raw/
    candidates = [
        root / "raw",
        root,
    ]
    for c in candidates:
        if not c.exists():
            continue
        # Look for images + masks folders
        for p in c.rglob("*"):
            if p.is_dir() and p.name.lower() in {"images", "img", "benign", "malignant", "normal"}:
                return c
    zips = list(root.glob("*.zip"))
    return root if zips else None


def build_manifest(root: Path = ROOT) -> pd.DataFrame:
    """Build manifest if data is present; raise FileNotFoundError otherwise."""
    raw = find_raw_root(root)
    if raw is None:
        raise FileNotFoundError(
            "BUS-UCLM archive not found under data/external/busuclm/. "
            "Mendeley Data (doi:10.17632/7fvgj4jsp7.3) often returns HTTP 403 without interactive login. "
            "Download the zip locally, extract under data/external/busuclm/ (see docs/BUSUCLM_STEPS.md), then re-run."
        )

    # Flexible layout: CSV if present, else folder walk with RGB masks (green=benign, red=malignant).
    csvs = list(raw.rglob("*.csv"))
    rows: list[dict] = []
    if csvs:
        # Best-effort column mapping — exact schema depends on the released CSV.
        # Prefer PNG image/mask heuristics below; CSV-only trees need a configured mapper.
        _ = pd.read_csv(csvs[0])
        # Fall through to folder walk; if that also yields nothing, raise a clear skip.

    # RGB mask convention from the Sci Data paper / Antillia notes
    for img in sorted(raw.rglob("*.png")):
        name = img.name.lower()
        if "mask" in name or img.parent.name.lower() in {"masks", "mask", "gt"}:
            continue
        # Heuristic pair
        mask_cands = [
            img.parent.parent / "masks" / img.name,
            img.parent / f"{img.stem}_mask{img.suffix}",
            img.with_name(img.name.replace("image", "mask")),
        ]
        mask = next((m for m in mask_cands if m.exists()), None)
        if mask is None:
            continue
        rgb = np.asarray(Image.open(mask).convert("RGB"))
        green = (rgb[:, :, 1] > 100) & (rgb[:, :, 1] > rgb[:, :, 0]) & (rgb[:, :, 1] > rgb[:, :, 2])
        red = (rgb[:, :, 0] > 100) & (rgb[:, :, 0] > rgb[:, :, 1]) & (rgb[:, :, 0] > rgb[:, :, 2])
        if red.any() and not green.any():
            label = "malignant"
        elif green.any() and not red.any():
            label = "benign"
        elif not red.any() and not green.any():
            label = "normal"
        else:
            label = "malignant" if red.sum() >= green.sum() else "benign"
        rows.append(
            {
                "case_id": img.stem,
                "image_path": str(img),
                "mask_path": str(mask),
                "label": label,
                "patient_id": None,
                "scanner": "Siemens ACUSON S2000",
                "birads": None,
                "pixel_size_mm": None,
                "has_doppler": "doppler" in name or "color" in name,
                "dataset": "busuclm",
            }
        )
    if not rows:
        zips = list(root.glob("*.zip")) + list(root.rglob("*.zip"))
        if zips:
            raise FileNotFoundError(
                f"BUS-UCLM zip present ({zips[0].name}) but not extracted, or no image/mask pairs matched. "
                "Extract the Mendeley archive under data/external/busuclm/ (see docs/BUSUCLM_STEPS.md), then re-run."
            )
        raise FileNotFoundError(
            "BUS-UCLM files present under data/external/busuclm/ but no image/mask pairs matched heuristics. "
            "Check the extracted layout against docs/BUSUCLM_STEPS.md."
        )
    df = ensure_manifest(pd.DataFrame(rows))
    # Exclude Doppler/combined when flagged
    df = df[~df["has_doppler"].astype(bool)].reset_index(drop=True)
    return df
