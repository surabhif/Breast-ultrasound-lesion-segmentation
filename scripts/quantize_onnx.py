#!/usr/bin/env python3
"""Optionally quantize the ONNX model to shrink the browser download.

Uses onnxruntime dynamic quantization (QUInt8 weights on MatMul/Gemm/Conv when available).
Adopts INT8 into web/public/models/ if size drops meaningfully and outputs stay close.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import RESULTS, WEB_PUBLIC, load_manifest, load_splits  # noqa: E402

ONNX_PATH = WEB_PUBLIC / "models" / "busi_unet.onnx"
FP32_BACKUP = WEB_PUBLIC / "models" / "busi_unet_fp32.onnx"


def main() -> None:
    if not ONNX_PATH.exists():
        raise SystemExit(f"Missing {ONNX_PATH}")

    import onnx
    from onnxruntime.quantization import QuantType, quantize_dynamic

    fp32_mb = ONNX_PATH.stat().st_size / (1024 * 1024)
    shutil.copy2(ONNX_PATH, FP32_BACKUP)
    int8_path = WEB_PUBLIC / "models" / "busi_unet_int8.onnx"

    print(f"FP32 size: {fp32_mb:.2f} MB")
    quantize_dynamic(
        model_input=str(FP32_BACKUP),
        model_output=str(int8_path),
        weight_type=QuantType.QUInt8,
    )
    int8_mb = int8_path.stat().st_size / (1024 * 1024)
    print(f"INT8 size: {int8_mb:.2f} MB")

    # Compare on a few test images
    import onnxruntime as ort
    from PIL import Image
    from torchvision import transforms

    from model_def import IMAGENET_MEAN, IMAGENET_STD

    manifest = load_manifest().set_index("case_id")
    splits = load_splits()
    # Infer input size from model
    sess_fp32 = ort.InferenceSession(str(FP32_BACKUP), providers=["CPUExecutionProvider"])
    shape = sess_fp32.get_inputs()[0].shape
    img_size = int(shape[2]) if isinstance(shape[2], int) else 128
    sess_int8 = ort.InferenceSession(str(int8_path), providers=["CPUExecutionProvider"])

    tf = transforms.Compose(
        [
            transforms.Resize((img_size, img_size)),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )

    deltas_cls = []
    deltas_seg = []
    for cid in splits["test_ids"][:24]:
        img = Image.open(manifest.loc[cid, "image_path"]).convert("RGB")
        x = tf(img).unsqueeze(0).numpy()
        out_f = sess_fp32.run(None, {"input": x})
        out_i = sess_int8.run(None, {"input": x})
        # outputs: seg_mask, cls_prob
        deltas_seg.append(float(np.mean(np.abs(out_f[0] - out_i[0]))))
        deltas_cls.append(float(np.abs(out_f[1] - out_i[1]).mean()))

    mean_seg = float(np.mean(deltas_seg))
    max_seg = float(np.max(deltas_seg))
    mean_cls = float(np.mean(deltas_cls))
    max_cls = float(np.max(deltas_cls))

    # Adopt if smaller and deltas are acceptable; also prefer INT8 when FP32 > 15MB
    size_ok = int8_mb < 0.95 * fp32_mb
    delta_ok = max_cls < 0.08 and mean_seg < 0.05
    prefer = fp32_mb > 15 and int8_mb <= 15 and max_cls < 0.12
    adopted = bool((size_ok and delta_ok) or prefer)

    if adopted:
        shutil.copy2(int8_path, ONNX_PATH)
        (WEB_PUBLIC / "models" / "MODEL_STATUS.txt").write_text(
            "trained_int8_dynamic\n"
            f"fp32_mb={fp32_mb:.3f}\nint8_mb={int8_mb:.3f}\n"
            f"max_cls_delta={max_cls:.4f}\nmean_seg_delta={mean_seg:.4f}\n"
        )
        method = "dynamic_uint8"
        served = int8_mb
    else:
        shutil.copy2(FP32_BACKUP, ONNX_PATH)
        (WEB_PUBLIC / "models" / "MODEL_STATUS.txt").write_text(
            "trained_fp32\n"
            f"fp32_mb={fp32_mb:.3f}\nint8_mb={int8_mb:.3f}\n"
            f"adopted=false reason=delta_or_size\n"
        )
        method = "fp32"
        served = fp32_mb

    report = {
        "fp32_mb": round(fp32_mb, 3),
        "int8_mb": round(int8_mb, 3),
        "served_mb": round(served, 3),
        "method": method,
        "adopted_for_web": adopted,
        "gallery_mean_abs_delta_cls": mean_cls,
        "gallery_max_abs_delta_cls": max_cls,
        "gallery_mean_abs_delta_seg": mean_seg,
        "gallery_max_abs_delta_seg": max_seg,
        "n_compared": len(deltas_cls),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    out = RESULTS / "quantization_report.json"
    out.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    # Keep fp32 backup for reference but don't require committing both if huge
    print(f"Served model: {ONNX_PATH} ({served:.2f} MB, {method})")


if __name__ == "__main__":
    main()
