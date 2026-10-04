#!/usr/bin/env python3
"""Generate notebooks/01_train_busi.ipynb for Colab end-to-end training."""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "notebooks" / "01_train_busi.ipynb"


def md(source: str) -> dict:
    lines = source.strip("\n").split("\n")
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": [ln + "\n" for ln in lines[:-1]] + ([lines[-1] + "\n"] if lines else []),
    }


def code(source: str) -> dict:
    lines = source.strip("\n").split("\n")
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": [ln + "\n" for ln in lines[:-1]] + ([lines[-1] + "\n"] if lines else []),
    }


cells = [
    md(
        """# BUSI lesion segmentation — Colab training notebook

**Research demo, not for clinical use.**

This notebook trains a U-Net (ResNet-18 encoder) with an auxiliary benign-vs-malignant head
on the BUSI dataset, evaluates Dice/IoU/AUC, and exports ONNX for the web demo.

Repo: https://github.com/surabhif/Breast-ultrasound-lesion-segmentation
"""
    ),
    md("## 1. Setup"),
    code(
        """!pip -q install torch torchvision pillow scikit-learn scikit-image imagehash opencv-python-headless onnx onnxruntime tqdm pandas matplotlib scipy
import torch
print('CUDA:', torch.cuda.is_available(), 'Torch', torch.__version__)"""
    ),
    md("## 2. Clone repo & download BUSI"),
    code(
        """import os
from pathlib import Path
if not Path('scripts/download_busi.py').exists():
    !git clone --depth 1 https://github.com/surabhif/Breast-ultrasound-lesion-segmentation.git repo
    %cd repo
else:
    print('Already in repo root')
!python scripts/download_busi.py
!python scripts/prepare_dataset.py"""
    ),
    md(
        """## 3. Quick baseline (CPU-friendly)

Tiny U-Net at 64×64 — useful smoke test. Skip if you only want the full model.
"""
    ),
    code("""!python scripts/run_baseline_quick.py"""),
    md(
        """## 4. Full training (GPU recommended)

ResNet-18 U-Net at 160×160. On Colab GPU this is much faster than CPU.
"""
    ),
    code(
        """!python scripts/train_full.py --epochs 40 --img-size 160 --batch-size 16 --patience 10 --freeze-epochs 3 --run-cv --cv-epochs 4"""
    ),
    md("## 5. Cleaning experiment, gallery, metrics, quantize"),
    code(
        """!python scripts/run_cleaning_experiment.py
!python scripts/export_gallery.py
!python scripts/quantize_onnx.py
!python scripts/export_web_results.py
print('Artifacts ready under web/public/ and results/')"""
    ),
    md(
        """## 6. Download weights for GitHub Pages

Download `web/public/models/busi_unet.onnx` and `web/public/results/metrics.json` (plus mistakes gallery)
and commit them to the repo, or open a PR from Colab via GitHub.
"""
    ),
    code(
        """from google.colab import files
from pathlib import Path
for p in [
    Path('web/public/models/busi_unet.onnx'),
    Path('web/public/results/metrics.json'),
    Path('results/full_run.json'),
    Path('results/cleaning_experiment.json'),
]:
    if p.exists():
        print('download', p)
        files.download(str(p))
    else:
        print('missing', p)"""
    ),
]

nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "pygments_lexer": "ipython3"},
        "colab": {"provenance": [], "gpuType": "T4"},
    },
    "cells": cells,
}

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(nb, indent=1))
print(f"Wrote {OUT}")


if __name__ == "__main__":
    pass
