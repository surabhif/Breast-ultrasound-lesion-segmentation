#!/usr/bin/env python3
"""Export a small set of real BUSI test-set samples for the web demo gallery."""

from __future__ import annotations

import argparse
import json
import random
import shutil
import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import WEB_PUBLIC, load_manifest, load_splits  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--per-class", type=int, default=2)
    args = ap.parse_args()

    manifest = load_manifest().set_index("case_id")
    splits = load_splits()
    test_ids = splits["test_ids"]

    by_label: dict[str, list[str]] = {"benign": [], "malignant": [], "normal": []}
    for cid in test_ids:
        lab = manifest.loc[cid, "label"]
        by_label[lab].append(cid)

    rng = random.Random(args.seed)
    chosen = []
    for lab, ids in by_label.items():
        rng.shuffle(ids)
        chosen.extend(ids[: args.per_class])

    samples_dir = WEB_PUBLIC / "samples"
    samples_dir.mkdir(parents=True, exist_ok=True)
    # clear old sample pngs
    for p in samples_dir.glob("*.png"):
        p.unlink()

    samples = []
    for i, cid in enumerate(chosen):
        row = manifest.loc[cid]
        src = Path(row["image_path"])
        # Resize for web weight while keeping aspect
        img = Image.open(src).convert("RGB")
        img.thumbnail((384, 384), Image.Resampling.LANCZOS)
        safe = f"sample_{i:02d}_{row['label']}.png"
        img.save(samples_dir / safe, optimize=True)
        # also copy mask thumbnail for reference (optional, not shown in UI by default)
        mask = Image.open(row["merged_mask_path"]).convert("L")
        mask.thumbnail((384, 384), Image.Resampling.NEAREST)
        mask.save(samples_dir / f"sample_{i:02d}_{row['label']}_mask.png")

        samples.append(
            {
                "id": f"busi-test-{i:02d}",
                "src": f"samples/{safe}",
                "mask_src": f"samples/sample_{i:02d}_{row['label']}_mask.png",
                "label": row["label"],
                "groundTruthMalignant": True if row["label"] == "malignant" else (
                    False if row["label"] == "benign" else None
                ),
                "hasLesion": row["label"] != "normal",
                "case_id": cid,
                "kind": "ultrasound",
                "annotation_flag": bool(row.get("annotation_flag", False)),
                "note": "Held-out BUSI test image (grouped split).",
            }
        )

    readme = samples_dir / "README.txt"
    readme.write_text(
        "Minimal BUSI test-set sample images for the in-browser demo.\n"
        "Source: Breast Ultrasound Images Dataset (BUSI), Al-Dhabyani et al., Data in Brief 2020.\n"
        "License for redistribution of the full dataset is not clearly stated; only a tiny\n"
        "cited sample subset is included here for research demonstration.\n"
        "Citation: Al-Dhabyani W, Gomaa M, Khaled H, Fahmy A. Dataset of breast ultrasound\n"
        "images. Data in Brief. 2020;28:104863. https://doi.org/10.1016/j.dib.2019.104863\n"
    )

    manifest_json = {
        "disclaimer": (
            "Research samples from the BUSI held-out test split. Not for clinical use. "
            "Cite Al-Dhabyani et al., Data in Brief 2020."
        ),
        "seed": args.seed,
        "source": "BUSI Dataset_BUSI_with_GT (Al-Dhabyani et al. 2020)",
        "samples": samples,
    }
    out = REPO / "web" / "src" / "data" / "samples.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest_json, indent=2))
    print(f"Exported {len(samples)} samples → {samples_dir}")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
