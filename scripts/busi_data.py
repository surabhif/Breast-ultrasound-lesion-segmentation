"""Shared BUSI dataset + metric helpers used by training / export scripts."""

from __future__ import annotations

import json
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torchvision.transforms.functional as TF
from PIL import Image
from torch.utils.data import Dataset

from model_def import IMAGENET_MEAN, IMAGENET_STD

REPO = Path(__file__).resolve().parents[1]
PROCESSED = REPO / "data" / "processed"
RESULTS = REPO / "results"
EXPORT_DIR = REPO / "export"
WEB_PUBLIC = REPO / "web" / "public"


class BusiDataset(Dataset):
    """BUSI loader with *paired* geometric augmentations (image + mask stay aligned)."""

    def __init__(
        self,
        manifest: pd.DataFrame,
        case_ids: list[str] | None = None,
        img_size: int = 128,
        augment: bool = False,
    ) -> None:
        df = manifest.copy()
        if case_ids is not None:
            id_set = set(case_ids)
            df = df[df["case_id"].isin(id_set)].reset_index(drop=True)
        self.df = df
        self.img_size = img_size
        self.augment = augment

    def __len__(self) -> int:
        return len(self.df)

    def _paired_augment(self, img: Image.Image, mask: Image.Image) -> tuple[Image.Image, Image.Image]:
        if random.random() < 0.5:
            img = TF.hflip(img)
            mask = TF.hflip(mask)
        if random.random() < 0.5:
            img = TF.vflip(img)
            mask = TF.vflip(mask)
        angle = random.uniform(-20, 20)
        img = TF.rotate(img, angle, interpolation=TF.InterpolationMode.BILINEAR, fill=0)
        mask = TF.rotate(mask, angle, interpolation=TF.InterpolationMode.NEAREST, fill=0)
        # Mild scale/crop jitter
        if random.random() < 0.5:
            scale = random.uniform(0.85, 1.0)
            w, h = img.size
            nw, nh = int(w * scale), int(h * scale)
            top = random.randint(0, max(0, h - nh))
            left = random.randint(0, max(0, w - nw))
            img = TF.resized_crop(
                img, top, left, nh, nw, (h, w), interpolation=TF.InterpolationMode.BILINEAR
            )
            mask = TF.resized_crop(
                mask, top, left, nh, nw, (h, w), interpolation=TF.InterpolationMode.NEAREST
            )
        return img, mask

    def __getitem__(self, idx: int) -> dict:
        row = self.df.iloc[idx]
        img = Image.open(row["image_path"]).convert("RGB")
        mask = Image.open(row["merged_mask_path"]).convert("L")

        if self.augment:
            img, mask = self._paired_augment(img, mask)

        img = TF.resize(img, [self.img_size, self.img_size], interpolation=TF.InterpolationMode.BILINEAR)
        mask = TF.resize(mask, [self.img_size, self.img_size], interpolation=TF.InterpolationMode.NEAREST)

        if self.augment:
            # Color jitter on image only (after geometry is locked)
            if random.random() < 0.8:
                img = TF.adjust_brightness(img, random.uniform(0.8, 1.2))
            if random.random() < 0.8:
                img = TF.adjust_contrast(img, random.uniform(0.8, 1.25))

        x = TF.to_tensor(img)
        x = TF.normalize(x, IMAGENET_MEAN, IMAGENET_STD)
        y_seg = (TF.to_tensor(mask) > 0.5).float()
        y_cls = torch.tensor(float(row["cls_target"]), dtype=torch.float32)
        return {
            "image": x,
            "mask": y_seg,
            "cls_target": y_cls,
            "label": row["label"],
            "case_id": row["case_id"],
            "annotation_flag": bool(row.get("annotation_flag", False)),
        }


def load_manifest() -> pd.DataFrame:
    path = PROCESSED / "manifest.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}; run scripts/prepare_dataset.py")
    return pd.read_csv(path)


def load_splits() -> dict:
    path = RESULTS / "splits.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing {path}; run scripts/prepare_dataset.py")
    return json.loads(path.read_text())


def dice_score(pred: np.ndarray, gt: np.ndarray, eps: float = 1e-6) -> float:
    pred = pred.astype(bool).ravel()
    gt = gt.astype(bool).ravel()
    # Convention for empty/empty: perfect score (no false lesion)
    if pred.sum() == 0 and gt.sum() == 0:
        return 1.0
    inter = np.logical_and(pred, gt).sum()
    return float((2 * inter + eps) / (pred.sum() + gt.sum() + eps))


def iou_score(pred: np.ndarray, gt: np.ndarray, eps: float = 1e-6) -> float:
    pred = pred.astype(bool).ravel()
    gt = gt.astype(bool).ravel()
    if pred.sum() == 0 and gt.sum() == 0:
        return 1.0
    inter = np.logical_and(pred, gt).sum()
    union = np.logical_or(pred, gt).sum()
    return float((inter + eps) / (union + eps))


def bootstrap_ci(
    values: np.ndarray,
    n_boot: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float, float]:
    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    means = []
    n = len(values)
    for _ in range(n_boot):
        sample = values[rng.integers(0, n, n)]
        means.append(sample.mean())
    lo, hi = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return float(values.mean()), float(lo), float(hi)


def expected_calibration_error(
    probs: np.ndarray, labels: np.ndarray, n_bins: int = 10
) -> tuple[float, list[dict]]:
    probs = np.asarray(probs, dtype=float)
    labels = np.asarray(labels, dtype=float)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    curve = []
    n = len(probs)
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        if i == n_bins - 1:
            mask = (probs >= lo) & (probs <= hi)
        else:
            mask = (probs >= lo) & (probs < hi)
        count = int(mask.sum())
        if count == 0:
            mean_p, frac = float("nan"), float("nan")
        else:
            mean_p = float(probs[mask].mean())
            frac = float(labels[mask].mean())
            ece += (count / n) * abs(mean_p - frac)
        curve.append(
            {
                "bin_start": float(lo),
                "bin_end": float(hi),
                "center": float((lo + hi) / 2),
                "mean_predicted": None if count == 0 else mean_p,
                "fraction_positive": None if count == 0 else frac,
                "count": count,
            }
        )
    return float(ece), curve


def remove_small_components(mask: np.ndarray, min_area: int) -> np.ndarray:
    """Drop connected components smaller than min_area (val-tuned post-process)."""
    if min_area <= 0:
        return mask
    from scipy import ndimage

    labeled, n = ndimage.label(mask.astype(bool))
    if n == 0:
        return mask.astype(bool)
    out = np.zeros_like(mask, dtype=bool)
    for i in range(1, n + 1):
        comp = labeled == i
        if int(comp.sum()) >= min_area:
            out |= comp
    return out
