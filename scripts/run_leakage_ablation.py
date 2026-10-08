#!/usr/bin/env python3
"""Full-scale leakage ablation: random vs grouped splits (3 seeds).

Trains the same ResNet-18 U-Net recipe for a fixed short schedule on:
  - grouped splits (near-dup groups stay together)
  - random stratified splits (ignoring groups)

Both are evaluated on the *same* held-out grouped test set so test deltas
reflect training leakage, not a moving target. Writes results/leakage_ablation.json.

Does NOT overwrite export/full_best.pt or the served v1.0.0 ONNX.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.model_selection import StratifiedShuffleSplit
from torch.utils.data import DataLoader
from tqdm.auto import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import (  # noqa: E402
    RESULTS,
    BusiDataset,
    dice_score,
    load_manifest,
    load_splits,
    remove_small_components,
)
from model_def import build_model, classification_loss, combined_seg_loss  # noqa: E402
from train_full import (  # noqa: E402
    DEVICE,
    evaluate_detailed,
    set_encoder_requires_grad,
    set_seed,
)

OUT = RESULTS / "leakage_ablation.json"


def random_split_ids(manifest: pd.DataFrame, test_ids: list[str], seed: int, val_frac: float = 0.2):
    """Train/val from non-test rows with stratified random split (leakage allowed)."""
    pool = manifest[~manifest["case_id"].isin(test_ids)].reset_index(drop=True)
    y = pool["label"].to_numpy()
    sss = StratifiedShuffleSplit(n_splits=1, test_size=val_frac, random_state=seed)
    tr_idx, va_idx = next(sss.split(pool, y))
    return pool.iloc[tr_idx]["case_id"].tolist(), pool.iloc[va_idx]["case_id"].tolist()


def train_one(
    manifest: pd.DataFrame,
    train_ids: list[str],
    val_ids: list[str],
    test_ids: list[str],
    *,
    seed: int,
    epochs: int,
    img_size: int,
    batch_size: int,
    mode: str,
) -> dict:
    set_seed(seed)
    train_ds = BusiDataset(manifest, train_ids, img_size=img_size, augment=True)
    val_ds = BusiDataset(manifest, val_ids, img_size=img_size, augment=False)
    test_ds = BusiDataset(manifest, test_ids, img_size=img_size, augment=False)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False, num_workers=0)

    model = build_model("resnet18", pretrained=True).to(DEVICE)
    set_encoder_requires_grad(model, False)
    opt = torch.optim.AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=8e-4)
    best_state = None
    best_lesion = -1.0
    hist = []

    for epoch in range(epochs):
        if epoch == 2:
            set_encoder_requires_grad(model, True)
            opt = torch.optim.AdamW(model.parameters(), lr=8e-4)
        model.train()
        for batch in train_loader:
            images = batch["image"].to(DEVICE)
            masks = batch["mask"].to(DEVICE)
            cls_t = batch["cls_target"].to(DEVICE)
            opt.zero_grad(set_to_none=True)
            seg_logits, cls_logits = model(images)
            loss = combined_seg_loss(seg_logits, masks) + 0.25 * classification_loss(cls_logits, cls_t)
            loss.backward()
            opt.step()
        # quick val lesion dice
        model.eval()
        dices = []
        with torch.no_grad():
            for batch in val_loader:
                images = batch["image"].to(DEVICE)
                masks = batch["mask"].numpy()
                seg_logits, _ = model(images)
                soft = torch.sigmoid(seg_logits).cpu().numpy()
                for i in range(soft.shape[0]):
                    pred = remove_small_components(soft[i, 0] > 0.4, 40)
                    lab = batch["label"][i]
                    if lab == "normal":
                        continue
                    dices.append(dice_score(pred, masks[i, 0] > 0.5))
        lesion = float(np.mean(dices)) if dices else 0.0
        hist.append({"epoch": epoch, "val_lesion_dice": lesion})
        if lesion > best_lesion:
            best_lesion = lesion
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}

    assert best_state is not None
    model.load_state_dict(best_state)
    model.to(DEVICE)
    # Reuse evaluate_detailed if available signature matches
    try:
        val_m = evaluate_detailed(model, val_loader, seg_thresh=0.4, min_area=40)
        test_m = evaluate_detailed(model, test_loader, seg_thresh=0.4, min_area=40)
        return {
            "mode": mode,
            "seed": seed,
            "epochs": epochs,
            "best_val_lesion_dice": best_lesion,
            "val_dice": val_m.get("dice_mean"),
            "test_dice": test_m.get("dice_mean"),
            "test_lesion_dice": test_m.get("lesion_dice_mean"),
            "test_auc": test_m.get("cls_roc_auc"),
            "history": hist,
        }
    except TypeError:
        # Fallback minimal metrics
        return {"mode": mode, "seed": seed, "best_val_lesion_dice": best_lesion, "history": hist}


def group_leak_fraction(manifest: pd.DataFrame, train_ids: list[str], val_ids: list[str]) -> float:
    if "phash_group" not in manifest.columns and "group_id" not in manifest.columns:
        # try splits note from audit
        return float("nan")
    col = "phash_group" if "phash_group" in manifest.columns else "group_id"
    train_g = set(manifest[manifest["case_id"].isin(train_ids)][col])
    val = manifest[manifest["case_id"].isin(val_ids)]
    if len(val) == 0:
        return 0.0
    leak = val[col].isin(train_g).mean()
    return float(leak)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--seeds", nargs="+", type=int, default=[42, 43, 44])
    ap.add_argument("--img-size", type=int, default=160)
    ap.add_argument("--batch-size", type=int, default=8)
    args = ap.parse_args()

    manifest = load_manifest()
    splits = load_splits()
    test_ids = splits["test_ids"]
    fold0 = splits["folds"][0]
    grouped_train, grouped_val = fold0["train_ids"], fold0["val_ids"]

    # Leak fraction for a random split example
    ex_tr, ex_va = random_split_ids(manifest, test_ids, seed=0)
    # If group column exists under another name
    group_col = None
    for c in ("phash_group", "group_id", "near_dup_group"):
        if c in manifest.columns:
            group_col = c
            break
    # derive from splits file group membership if needed
    leak_frac = None
    if group_col:
        leak_frac = group_leak_fraction(manifest, ex_tr, ex_va)
    elif "groups" in splits:
        # map case->group from splits
        case_to_g = {}
        for gid, members in splits.get("groups", {}).items():
            for m in members:
                case_to_g[m] = gid
        if case_to_g:
            manifest = manifest.copy()
            manifest["phash_group"] = manifest["case_id"].map(case_to_g)
            leak_frac = group_leak_fraction(manifest, ex_tr, ex_va)

    runs = []
    t0 = time.time()
    for seed in args.seeds:
        print(f"=== seed {seed} grouped ===")
        runs.append(
            train_one(
                manifest,
                grouped_train,
                grouped_val,
                test_ids,
                seed=seed,
                epochs=args.epochs,
                img_size=args.img_size,
                batch_size=args.batch_size,
                mode="grouped",
            )
        )
        print(f"=== seed {seed} random ===")
        r_tr, r_va = random_split_ids(manifest, test_ids, seed=seed)
        runs.append(
            train_one(
                manifest,
                r_tr,
                r_va,
                test_ids,
                seed=seed,
                epochs=args.epochs,
                img_size=args.img_size,
                batch_size=args.batch_size,
                mode="random",
            )
        )

    grouped = [r for r in runs if r["mode"] == "grouped"]
    random_runs = [r for r in runs if r["mode"] == "random"]

    def mean_key(rows, key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return float(np.mean(vals)) if vals else None

    out = {
        "label": "Leakage ablation: random vs grouped splits (same grouped test)",
        "epochs": args.epochs,
        "seeds": args.seeds,
        "img_size": args.img_size,
        "random_split_val_group_leak_fraction_example": leak_frac,
        "runs": runs,
        "summary": {
            "grouped_mean_val_lesion_dice": mean_key(grouped, "best_val_lesion_dice"),
            "random_mean_val_lesion_dice": mean_key(random_runs, "best_val_lesion_dice"),
            "grouped_mean_test_dice": mean_key(grouped, "test_dice"),
            "random_mean_test_dice": mean_key(random_runs, "test_dice"),
            "val_inflation_random_minus_grouped": (
                None
                if mean_key(random_runs, "best_val_lesion_dice") is None
                else mean_key(random_runs, "best_val_lesion_dice") - mean_key(grouped, "best_val_lesion_dice")
            ),
        },
        "runtime_seconds": time.time() - t0,
        "note": "Short schedule for ablation cost; recipe matches v1 architecture. Served v1.0.0 unchanged.",
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print("Wrote", OUT)
    print(out["summary"])


if __name__ == "__main__":
    main()
