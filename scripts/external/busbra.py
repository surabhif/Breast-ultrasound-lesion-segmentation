"""BUS-BRA loader (Zenodo 8231412, CC BY 4.0)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .common import EXTERNAL_ROOT, ensure_manifest

ROOT = EXTERNAL_ROOT / "busbra" / "raw" / "BUSBRA"


def build_manifest(root: Path = ROOT) -> pd.DataFrame:
    if not root.exists():
        raise FileNotFoundError(f"BUS-BRA not found at {root}; run scripts/download_busbra.py")
    meta = pd.read_csv(root / "bus_data.csv")
    rows = []
    for _, r in meta.iterrows():
        rid = str(r["ID"])
        # bus_0001-l → mask_0001-l.png
        mask_name = "mask_" + rid.split("_", 1)[1] + ".png"
        img = root / "Images" / f"{rid}.png"
        mask = root / "Masks" / mask_name
        if not img.exists() or not mask.exists():
            continue
        rows.append(
            {
                "case_id": rid,
                "image_path": str(img),
                "mask_path": str(mask),
                "label": str(r["Pathology"]).lower(),
                "patient_id": str(r["Case"]),
                "scanner": str(r["Device"]),
                "birads": str(r["BIRADS"]),
                "pixel_size_mm": None,
                "has_doppler": False,
                "dataset": "busbra",
            }
        )
    return ensure_manifest(pd.DataFrame(rows))


if __name__ == "__main__":
    m = build_manifest()
    print(m["label"].value_counts())
    print("n", len(m), "patients", m["patient_id"].nunique())
