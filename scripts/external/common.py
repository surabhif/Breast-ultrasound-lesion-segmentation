"""Shared helpers for external-dataset manifests and metrics."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
EXTERNAL_ROOT = REPO / "data" / "external"
RESULTS_EXTERNAL = REPO / "results" / "external"

MANIFEST_COLUMNS = [
    "case_id",
    "image_path",
    "mask_path",
    "label",
    "patient_id",
    "scanner",
    "birads",
    "pixel_size_mm",
    "has_doppler",
    "dataset",
]


def ensure_manifest(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in MANIFEST_COLUMNS:
        if c not in out.columns:
            out[c] = None
    return out[MANIFEST_COLUMNS]


def load_rgb(path: str | Path) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"))


def load_mask_binary(path: str | Path | None, img_size: int = 160) -> np.ndarray:
    if path is None or (isinstance(path, float) and np.isnan(path)) or not path:
        return np.zeros((img_size, img_size), dtype=bool)
    p = Path(str(path))
    if not p.exists():
        return np.zeros((img_size, img_size), dtype=bool)
    m = Image.open(p).convert("L")
    m = m.resize((img_size, img_size), Image.NEAREST)
    return np.asarray(m) > 127


def or_merge_masks(paths: list[str | Path], img_size: int = 160) -> np.ndarray:
    acc = np.zeros((img_size, img_size), dtype=bool)
    for p in paths:
        if not p or (isinstance(p, float) and np.isnan(p)):
            continue
        acc |= load_mask_binary(p, img_size)
    return acc


def bootstrap_mean_ci(
    values: np.ndarray,
    n_boot: int = 1000,
    seed: int = 42,
    clusters: np.ndarray | None = None,
) -> tuple[float, list[float]]:
    """Mean + 95% CI. If clusters provided, resample clusters (patient-level)."""
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return float("nan"), [float("nan"), float("nan")]
    rng = np.random.default_rng(seed)
    if clusters is None:
        boots = []
        for _ in range(n_boot):
            idx = rng.integers(0, len(values), len(values))
            boots.append(values[idx].mean())
    else:
        clusters = np.asarray(clusters)
        uniq = np.unique(clusters)
        boots = []
        for _ in range(n_boot):
            draw = rng.choice(uniq, size=len(uniq), replace=True)
            parts = [values[clusters == c] for c in draw]
            boots.append(np.concatenate(parts).mean() if parts else float("nan"))
    boots = np.asarray(boots, dtype=float)
    return float(values.mean()), [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + "\n")
