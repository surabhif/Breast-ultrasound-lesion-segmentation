#!/usr/bin/env python3
"""Research experiment: how much do calipers/annotations and duplicates inflate BUSI scores?

Compares:
  1) Metrics on the full held-out test set vs clean (no annotation_flag) subset
  2) Metrics on flagged-only vs clean-only images
  3) Classifier AUC when restricting to clean B/M cases
  4) A control train on "unclean" random (non-grouped) splits to estimate leakage inflation
     from near-duplicates (short training for a relative delta, not a SotA claim)

All numbers come from actual model evaluation — nothing is fabricated.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader
from tqdm.auto import tqdm

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import (  # noqa: E402
    EXPORT_DIR,
    RESULTS,
    BusiDataset,
    bootstrap_ci,
    dice_score,
    iou_score,
    load_manifest,
    load_splits,
)
from model_def import (  # noqa: E402
    build_model,
    classification_loss,
    combined_seg_loss,
)
from train_full import evaluate_detailed  # noqa: E402

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
SEED = 42


def subset_metrics(per_image: list[dict], predicate) -> dict:
    rows = [r for r in per_image if predicate(r)]
    if not rows:
        return {"n": 0}
    dice = np.array([r["dice"] for r in rows])
    iou = np.array([r["iou"] for r in rows])
    d_m, d_lo, d_hi = bootstrap_ci(dice)
    i_m, i_lo, i_hi = bootstrap_ci(iou)
    out = {
        "n": len(rows),
        "dice_mean": d_m,
        "dice_ci95": [d_lo, d_hi],
        "iou_mean": i_m,
        "iou_ci95": [i_lo, i_hi],
    }
    cls_p = [r["cls_prob"] for r in rows if r["cls_target"] >= 0]
    cls_y = [int(r["cls_target"]) for r in rows if r["cls_target"] >= 0]
    if len(set(cls_y)) == 2:
        out["cls_auc"] = float(roc_auc_score(cls_y, cls_p))
        out["n_cls"] = len(cls_y)
    return out


def train_short(manifest, train_ids, val_ids, img_size=96, epochs=4, batch_size=8):
    train_ds = BusiDataset(manifest, train_ids, img_size=img_size, augment=True)
    val_ds = BusiDataset(manifest, val_ids, img_size=img_size, augment=False)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False, num_workers=0)
    model = build_model("tiny", pretrained=False).to(DEVICE)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    best = None
    best_dice = -1.0
    for _ in range(epochs):
        model.train()
        for batch in train_loader:
            images = batch["image"].to(DEVICE)
            masks = batch["mask"].to(DEVICE)
            cls_t = batch["cls_target"].to(DEVICE)
            seg_logits, cls_logits = model(images)
            loss = combined_seg_loss(seg_logits, masks) + 0.3 * classification_loss(cls_logits, cls_t)
            opt.zero_grad()
            loss.backward()
            opt.step()
        metrics = evaluate_detailed(model, val_loader)
        if metrics["dice_mean"] > best_dice:
            best_dice = metrics["dice_mean"]
            best = {k: v for k, v in metrics.items() if k != "per_image"}
            best["_per_image"] = metrics["per_image"]
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    return model, best


def main() -> None:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)

    manifest = load_manifest()
    splits = load_splits()
    RESULTS.mkdir(parents=True, exist_ok=True)

    # --- Part A: evaluate the full trained model on clean vs flagged ---
    ckpt_path = EXPORT_DIR / "full_best.pt"
    part_a = {"available": False}
    if ckpt_path.exists():
        ckpt = torch.load(ckpt_path, map_location=DEVICE, weights_only=False)
        model = build_model(ckpt.get("model_kind", "resnet18"), pretrained=False).to(DEVICE)
        model.load_state_dict(ckpt["state_dict"])
        img_size = int(ckpt.get("img_size", 160))
        pp_path = RESULTS / "postprocess.json"
        thr, area = 0.5, 0
        if pp_path.exists():
            import json as _json
            _pp = _json.loads(pp_path.read_text())
            thr = float(_pp.get("seg_threshold", 0.5))
            area = int(_pp.get("min_component_area", 0))
        test_ds = BusiDataset(manifest, splits["test_ids"], img_size=img_size, augment=False)
        test_loader = DataLoader(test_ds, batch_size=8, shuffle=False)
        full = evaluate_detailed(model, test_loader, seg_thresh=thr, min_area=area)
        per = full["per_image"]

        # Attach annotation flags from manifest
        flag_map = manifest.set_index("case_id")["annotation_flag"].to_dict()
        for r in per:
            r["annotation_flag"] = bool(flag_map.get(r["case_id"], False))

        all_m = subset_metrics(per, lambda r: True)
        clean_m = subset_metrics(per, lambda r: not r["annotation_flag"])
        flagged_m = subset_metrics(per, lambda r: r["annotation_flag"])
        lesion_clean = subset_metrics(
            per, lambda r: (not r["annotation_flag"]) and r["label"] != "normal"
        )
        lesion_flagged = subset_metrics(
            per, lambda r: r["annotation_flag"] and r["label"] != "normal"
        )

        part_a = {
            "available": True,
            "model": "full_best.pt",
            "img_size": img_size,
            "all_test": all_m,
            "clean_test": clean_m,
            "flagged_test": flagged_m,
            "lesion_clean": lesion_clean,
            "lesion_flagged": lesion_flagged,
            "dice_inflation_all_minus_clean": (
                None
                if clean_m.get("n", 0) == 0
                else round(all_m["dice_mean"] - clean_m["dice_mean"], 4)
            ),
            "auc_all": all_m.get("cls_auc"),
            "auc_clean": clean_m.get("cls_auc"),
            "auc_flagged": flagged_m.get("cls_auc"),
            "interpretation_hint": (
                "If flagged (caliper/text) images score higher on classification AUC than clean "
                "images, the model may be using burned-in marks as shortcuts. "
                "If overall Dice drops after removing flagged cases, reported BUSI scores may "
                "be partly driven by easier annotated frames."
            ),
        }
        print("Part A (full model clean vs flagged):")
        print(json.dumps({k: v for k, v in part_a.items() if k != "interpretation_hint"}, indent=2))
    else:
        print("No full_best.pt yet — Part A deferred until after training.")

    # --- Part B: grouped vs random-split leakage proxy (tiny model, short train) ---
    print("Part B: grouped vs random split leakage proxy (tiny U-Net)…")
    ids = manifest["case_id"].tolist()
    labels = manifest["label"].tolist()
    groups = manifest["dup_group"].tolist()

    # Grouped: use official fold 0 val as eval, train on fold 0 train (already grouped)
    fold = splits["folds"][0]
    grouped_model, grouped_val = train_short(manifest, fold["train_ids"], fold["val_ids"])
    # Evaluate grouped model on held-out test
    test_loader = DataLoader(
        BusiDataset(manifest, splits["test_ids"], img_size=96, augment=False),
        batch_size=8,
        shuffle=False,
    )
    grouped_test = evaluate_detailed(grouped_model, test_loader)
    grouped_test_s = {k: v for k, v in grouped_test.items() if k != "per_image"}

    # Random (leaky) split: ignore groups — same sizes as fold0 train/val from all non-test
    non_test = [i for i in ids if i not in set(splits["test_ids"])]
    non_test_labels = manifest.set_index("case_id").loc[non_test, "label"].tolist()
    tr, va = train_test_split(
        non_test,
        test_size=len(fold["val_ids"]) / max(len(non_test), 1),
        random_state=SEED,
        stratify=non_test_labels,
    )
    # Measure how many val images share a dup_group with train (leakage)
    gmap = manifest.set_index("case_id")["dup_group"].to_dict()
    train_groups = {gmap[c] for c in tr}
    leak_ids = [c for c in va if gmap[c] in train_groups]
    leak_frac = len(leak_ids) / max(len(va), 1)

    leaky_model, leaky_val = train_short(manifest, tr, va)
    leaky_test = evaluate_detailed(leaky_model, test_loader)
    leaky_test_s = {k: v for k, v in leaky_test.items() if k != "per_image"}

    part_b = {
        "model": "tiny_unet_short",
        "epochs": 4,
        "img_size": 96,
        "grouped_val_dice": grouped_val["dice_mean"] if grouped_val else None,
        "grouped_test_dice": grouped_test_s["dice_mean"],
        "grouped_test_auc": (grouped_test_s.get("classification") or {}).get("roc_auc"),
        "random_split_val_group_leak_fraction": round(leak_frac, 4),
        "n_val_leaky_ids": len(leak_ids),
        "leaky_val_dice": leaky_val["dice_mean"] if leaky_val else None,
        "leaky_test_dice": leaky_test_s["dice_mean"],
        "leaky_test_auc": (leaky_test_s.get("classification") or {}).get("roc_auc"),
        "val_dice_inflation_leaky_minus_grouped": (
            None
            if not grouped_val or not leaky_val
            else round(leaky_val["dice_mean"] - grouped_val["dice_mean"], 4)
        ),
        "note": (
            "Random stratified splits (ignoring near-duplicate groups) often put near-copies "
            "in both train and val, which can inflate validation Dice/AUC. The held-out test "
            "set here stays the same grouped test for both models, so test deltas mainly "
            "reflect training differences; the key leakage signal is val inflation and the "
            "reported leak fraction."
        ),
    }
    print(json.dumps(part_b, indent=2))

    report = {
        "seed": SEED,
        "audit_csv": "results/audit_calipers_duplicates.csv",
        "dataset_counts": {
            "n_total": int(len(manifest)),
            "n_annotation_flagged": int(manifest["annotation_flag"].sum()),
            "annotation_rate": float(manifest["annotation_flag"].mean()),
            "n_dup_groups": int(manifest["dup_group"].nunique()),
            "n_in_multi_member_groups": int(
                (manifest.groupby("dup_group")["case_id"].transform("count") > 1).sum()
            ),
        },
        "full_model_clean_vs_flagged": part_a,
        "duplicate_leakage_proxy": part_b,
    }

    def _sanitize(obj):
        if isinstance(obj, float):
            if np.isnan(obj) or np.isinf(obj):
                return None
            return obj
        if isinstance(obj, dict):
            return {k: _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(v) for v in obj]
        return obj

    out = RESULTS / "cleaning_experiment.json"
    out.write_text(json.dumps(_sanitize(report), indent=2))
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
