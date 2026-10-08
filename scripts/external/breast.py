"""BrEaST / BREAST-LESIONS-USG loader (TCIA, CC BY 4.0)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from PIL import Image

from .common import EXTERNAL_ROOT, ensure_manifest

ROOT = EXTERNAL_ROOT / "breast" / "raw" / "BrEaST-Lesions_USG-images_and_masks"
CLINICAL = EXTERNAL_ROOT / "breast" / "BrEaST-Lesions-USG-clinical-data.xlsx"


def build_manifest(root: Path = ROOT, clinical: Path = CLINICAL) -> pd.DataFrame:
    if not root.exists():
        raise FileNotFoundError(f"BrEaST images not found at {root}")
    if not clinical.exists():
        raise FileNotFoundError(f"BrEaST clinical XLSX not found at {clinical}")
    meta = pd.read_excel(clinical)
    rows = []
    for _, r in meta.iterrows():
        img_name = str(r["Image_filename"])
        tumor = r.get("Mask_tumor_filename")
        other = r.get("Mask_other_filename")
        # Protocol: map only tumour masks for GT (ignore "other" abnormal areas for Dice).
        mask_name = None if pd.isna(tumor) else str(tumor).split("&")[0].strip()
        img = root / img_name
        mask = root / mask_name if mask_name else None
        if not img.exists():
            continue
        if mask is not None and not mask.exists():
            mask = None
        label = str(r["Classification"]).strip().lower()
        if label not in {"benign", "malignant", "normal"}:
            continue
        # Sci Data 2024: Pixel_size is "width and height of pixel in cm".
        px_cm = float(r["Pixel_size"]) if not pd.isna(r["Pixel_size"]) else None
        with Image.open(img) as im:
            ow, oh = im.size
        # Normals may lack tumor masks — empty GT.
        rows.append(
            {
                "case_id": f"breast-{int(r['CaseID']):03d}",
                "image_path": str(img),
                "mask_path": str(mask) if mask else "",
                "label": label,
                "patient_id": str(int(r["CaseID"])),
                "scanner": None,
                "birads": str(r["BIRADS"]) if not pd.isna(r["BIRADS"]) else None,
                "pixel_size_mm": (px_cm * 10.0) if px_cm is not None else None,
                "orig_width": ow,
                "orig_height": oh,
                "has_doppler": False,
                "dataset": "breast",
                "_other_masks": str(other) if not pd.isna(other) else "",
            }
        )
    df = pd.DataFrame(rows)
    return ensure_manifest(df)


if __name__ == "__main__":
    m = build_manifest()
    print(m["label"].value_counts())
    print("n", len(m), "with spacing", m["pixel_size_mm"].notna().sum())
