#!/usr/bin/env python3
"""Build parity reference JSON by running the served INT8 ONNX on fixed images.

Uses gallery samples (always present in the repo) plus optional held-out test
paths when `data/processed/manifest.csv` exists.

Output: tests/parity/reference.json
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import (  # noqa: E402
    RESULTS,
    WEB_PUBLIC,
    imagenet_tensor_from_rgb,
    remove_small_components,
)

IMG_SIZE = 160
SEG_THRESH = 0.4
MIN_AREA = 40


def run_one(sess: ort.InferenceSession, image_path: Path) -> dict:
    img = Image.open(image_path).convert("RGB")
    x = imagenet_tensor_from_rgb(np.asarray(img), IMG_SIZE)
    outs = sess.run(None, {"input": x})
    names = [o.name for o in sess.get_outputs()]
    seg = outs[names.index("seg_mask")] if "seg_mask" in names else outs[0]
    cls = outs[names.index("cls_prob")] if "cls_prob" in names else outs[1]
    soft = seg[0, 0].astype(np.float32)
    cls_prob = float(cls.reshape(-1)[0])
    binary = soft > SEG_THRESH
    kept = remove_small_components(binary, MIN_AREA)
    post = soft.copy()
    post[~kept] = 0.0
    # Compact mask fingerprint
    bits = kept.astype(np.uint8).tobytes()
    return {
        "cls_prob": cls_prob,
        "mask_mean": float(post.mean()),
        "pred_area": int(kept.sum()),
        "mask_sha256": hashlib.sha256(bits).hexdigest(),
        "mask_downsample": kept[::10, ::10].astype(int).tolist(),
    }


def main() -> None:
    onnx = WEB_PUBLIC / "models" / "v1.0.0" / "busi_unet.onnx"
    sess = ort.InferenceSession(str(onnx), providers=["CPUExecutionProvider"])
    sha = hashlib.sha256(onnx.read_bytes()).hexdigest()

    samples = json.loads((WEB_PUBLIC.parent / "src" / "data" / "samples.json").read_text())
    cases = []
    for s in samples["samples"]:
        path = WEB_PUBLIC / s["src"]
        if not path.exists():
            # samples live under public/
            path = REPO / "web" / "public" / s["src"]
        ref = run_one(sess, path)
        cases.append({"id": s["id"], "src": s["src"], "kind": "gallery", **ref})

    # Optional held-out cases (not written into the committed gallery reference by default).
    # Pass --include-test when data/processed is available locally.
    include_test = "--include-test" in sys.argv
    manifest_path = REPO / "data" / "processed" / "manifest.csv"
    splits_path = RESULTS / "splits.json"
    if include_test and manifest_path.exists() and splits_path.exists():
        import pandas as pd

        man = pd.read_csv(manifest_path).set_index("case_id")
        test_ids = json.loads(splits_path.read_text())["test_ids"][:8]
        for cid in test_ids:
            row = man.loc[cid]
            ref = run_one(sess, Path(row["image_path"]))
            cases.append({"id": cid, "src": row["image_path"], "kind": "test", **ref})

    out = {
        "model_version": "1.0.0",
        "model_sha256": sha,
        "img_size": IMG_SIZE,
        "seg_threshold": SEG_THRESH,
        "min_component_area": MIN_AREA,
        "tolerances": {
            "cls_prob_abs": 0.02,
            "pred_area_abs": 8,
            "mask_sha_must_match": False,
            "note": "Canvas bilinear resize can differ slightly from PIL; area tolerance absorbs that.",
        },
        "cases": cases,
    }
    dest = REPO / "tests" / "parity" / "reference.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2))
    print(f"Wrote {dest} ({len(cases)} cases)")


if __name__ == "__main__":
    main()
