#!/usr/bin/env python3
"""Apply fair Phase-4 MODEL_POLICY to results/v2_experiment.json.

Fairness rules (owner 2026-10-10):
  1) BUS-BRA is same-source held-out for v2 (v2 trains on BUS-BRA train).
     Compare v2 held-out Dice to v1.0.0 INT8 on the *same* held-out IDs
     (results/v2/v1_busbra_heldout.json), NOT v1's full-set 0.714.
     BrEaST remains the only truly external test.
  2) Report mean ± SD across seeds and paired-bootstrap 95% CI for each delta.
  3) Promotion on the 3-seed result: if the seed-*mean* fails any rule, keep v1.
     Among seeds that pass, promote the *median-performing* seed (by clean Dice),
     not the best. Say so in the decision sentence.

Also requires INT8 ≤ ~25 MB.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
WEB = REPO / "web" / "public"
EXP = RESULTS / "v2_experiment.json"
V2_DIR = RESULTS / "v2"
V1_HELD = V2_DIR / "v1_busbra_heldout.json"
METRICS = WEB / "results" / "metrics.json"


def r3(x):
    return None if x is None else round(float(x), 3)


def r4(x):
    return None if x is None else round(float(x), 4)


def paired_bootstrap_ci(deltas: list[float], n_boot: int = 5000, seed: int = 42) -> list[float]:
    """Percentile CI for mean delta via paired/seed-level bootstrap."""
    arr = np.asarray(deltas, dtype=float)
    if len(arr) == 0:
        return [None, None]  # type: ignore[list-item]
    if len(arr) == 1:
        return [float(arr[0]), float(arr[0])]
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(n_boot):
        sample = rng.choice(arr, size=len(arr), replace=True)
        means.append(float(sample.mean()))
    lo, hi = np.percentile(means, [2.5, 97.5])
    return [float(lo), float(hi)]


def seed_metrics(s: dict) -> dict | None:
    if "test_clean_subset" not in s:
        return None
    return {
        "seed": s["seed"],
        "clean_dice": (s.get("test_clean_subset") or {}).get("dice_mean"),
        "test_dice": (s.get("test_original") or {}).get("dice_mean"),
        "lesion_dice": (s.get("test_original") or {}).get("lesion_dice_mean"),
        "busbra_heldout": (s.get("external_busbra_heldout") or {}).get("dice_mean"),
        "breast": (s.get("external_breast") or {}).get("dice_mean"),
        "auc": ((s.get("test_original") or {}).get("classification") or {}).get("roc_auc"),
        "int8_mb": s.get("onnx_int8_mb"),
        "onnx_int8": s.get("onnx_int8"),
        "onnx_sha256": s.get("onnx_sha256"),
        "postprocess": s.get("postprocess"),
        "img_size": s.get("img_size"),
        "model_kind": s.get("model_kind"),
        "normal_note": (
            ((s.get("test_original") or {}).get("by_label") or {}).get("normal") or {}
        ).get("dice_mean"),
    }


def checks_for(m: dict, v1: dict) -> dict:
    c_clean, c_auc = m["clean_dice"], m["auc"]
    c_busbra, c_breast = m["busbra_heldout"], m["breast"]
    int8_mb = m["int8_mb"]
    return {
        "clean_dice_ok": c_clean is not None and v1["clean_dice"] is not None and c_clean >= v1["clean_dice"] - 1e-9,
        "busbra_heldout_ok": (
            c_busbra is not None
            and v1["busbra_heldout_dice"] is not None
            and c_busbra >= v1["busbra_heldout_dice"] - 1e-9
        ),
        "breast_ok": c_breast is not None and v1["breast_dice"] is not None and c_breast >= v1["breast_dice"] - 1e-9,
        "auc_ok": c_auc is not None and v1["auc"] is not None and (v1["auc"] - c_auc) <= 0.02 + 1e-9,
        "size_ok": int8_mb is not None and int8_mb <= 25.5,
    }


def mean_sd(vals: list[float]) -> dict:
    a = np.asarray(vals, dtype=float)
    return {
        "mean": float(a.mean()),
        "sd": float(a.std(ddof=1)) if len(a) > 1 else 0.0,
        "n": int(len(a)),
        "values": [float(x) for x in a],
    }


def main() -> None:
    if not EXP.exists():
        # Assemble experiment from per-seed JSONs if train_v2 still writing final file
        seeds = sorted(V2_DIR.glob("seed*.json"))
        if not seeds:
            print("No results/v2_experiment.json or per-seed JSON — run train_v2.py first")
            sys.exit(1)
        print("Assembling v2_experiment.json from per-seed files…")
        # Minimal shell; train_v2 should write the full file when done
        metrics_web = json.loads(METRICS.read_text())
        clean = (
            (metrics_web.get("cleaning_experiment") or {})
            .get("full_model_clean_vs_flagged", {})
            .get("clean_test", {})
            .get("dice_mean")
        )
        ext = metrics_web.get("external") or {}
        datasets = ext.get("datasets") or {}
        v1_base = {
            "clean_dice": clean,
            "busbra_dice_fullset": (datasets.get("busbra") or {}).get("test_dice"),
            "breast_dice": (datasets.get("breast") or {}).get("test_dice"),
            "auc": (ext.get("internal_busi_int8") or {}).get("cls_roc_auc")
            or (metrics_web.get("served_int8") or {}).get("cls_roc_auc"),
            "test_dice": (metrics_web.get("served_int8") or {}).get("test_dice"),
            "lesion_dice": (metrics_web.get("served_int8") or {}).get("lesion_dice"),
            "int8_mb": round((WEB / "models" / "v1.0.0" / "busi_unet.onnx").stat().st_size / (1024 * 1024), 3),
        }
        seed_objs = [json.loads(p.read_text()) for p in seeds]
        exp = {
            "label": "Phase 4 v2 multi-dataset candidates (MODEL_POLICY D3, fair held-out)",
            "v1_baselines": v1_base,
            "seeds": seed_objs,
            "config": {"model": "resnet34", "img_size": 256, "seeds": [s.get("seed") for s in seed_objs]},
            "busbra_split": json.loads((V2_DIR / "busbra_patient_split.json").read_text())
            if (V2_DIR / "busbra_patient_split.json").exists()
            else {},
        }
    else:
        exp = json.loads(EXP.read_text())

    if not V1_HELD.exists():
        print(f"Missing {V1_HELD} — run scripts/eval_v1_busbra_heldout.py first")
        sys.exit(1)
    v1_held = json.loads(V1_HELD.read_text())

    v1 = dict(exp.get("v1_baselines") or {})
    v1["busbra_heldout_dice"] = v1_held.get("dice_mean")
    v1["busbra_heldout_meta"] = {
        "n": v1_held.get("n"),
        "dice_ci95": v1_held.get("dice_ci95"),
        "source": "results/v2/v1_busbra_heldout.json",
        "role": "same_source_heldout_baseline",
    }
    # Keep full-set number for display only (not used for swap)
    if "busbra_dice" in v1 and "busbra_dice_fullset" not in v1:
        v1["busbra_dice_fullset"] = v1.get("busbra_dice")

    finished = [seed_metrics(s) for s in exp.get("seeds") or []]
    finished = [m for m in finished if m is not None]
    if len(finished) < 1:
        print("No finished seeds")
        sys.exit(1)

    # Per-seed checks (fair BUS-BRA held-out)
    for m in finished:
        m["checks"] = checks_for(m, v1)
        m["pass"] = all(m["checks"].values())

    # Seed-mean metrics + checks
    def col(key: str) -> list[float]:
        return [float(m[key]) for m in finished if m.get(key) is not None]

    summary = {
        "clean_dice": mean_sd(col("clean_dice")),
        "test_dice": mean_sd(col("test_dice")),
        "lesion_dice": mean_sd(col("lesion_dice")),
        "busbra_heldout": mean_sd(col("busbra_heldout")),
        "breast": mean_sd(col("breast")),
        "auc": mean_sd(col("auc")),
        "int8_mb": mean_sd(col("int8_mb")),
    }

    # Deltas vs v1 + paired bootstrap CI across seeds
    def deltas(key: str, v1_key: str) -> dict:
        v1v = v1.get(v1_key)
        vals = col(key)
        if v1v is None or not vals:
            return {"v1": v1v, "mean_delta": None, "sd_delta": None, "ci95": [None, None]}
        d = [v - float(v1v) for v in vals]
        ms = mean_sd(d)
        return {
            "v1": float(v1v),
            "v2_mean": summary[key]["mean"] if key in summary else None,
            "v2_sd": summary[key]["sd"] if key in summary else None,
            "mean_delta": ms["mean"],
            "sd_delta": ms["sd"],
            "ci95_paired_bootstrap": paired_bootstrap_ci(d),
            "per_seed_delta": d,
        }

    deltas_block = {
        "clean_dice": deltas("clean_dice", "clean_dice"),
        "busbra_heldout": deltas("busbra_heldout", "busbra_heldout_dice"),
        "breast": deltas("breast", "breast_dice"),
        "auc": deltas("auc", "auc"),
        "test_dice": deltas("test_dice", "test_dice"),
        "lesion_dice": deltas("lesion_dice", "lesion_dice"),
    }

    mean_row = {
        "clean_dice": summary["clean_dice"]["mean"],
        "busbra_heldout": summary["busbra_heldout"]["mean"],
        "breast": summary["breast"]["mean"],
        "auc": summary["auc"]["mean"],
        "int8_mb": summary["int8_mb"]["mean"],
    }
    mean_checks = checks_for(
        {
            "clean_dice": mean_row["clean_dice"],
            "busbra_heldout": mean_row["busbra_heldout"],
            "breast": mean_row["breast"],
            "auc": mean_row["auc"],
            "int8_mb": mean_row["int8_mb"],
        },
        v1,
    )
    mean_pass = all(mean_checks.values())

    passing = [m for m in finished if m["pass"]]
    # Median-performing among passers by clean Dice (not the best)
    promote = None
    if mean_pass and passing:
        ordered = sorted(passing, key=lambda m: m["clean_dice"])
        promote = ordered[len(ordered) // 2]

    swap_ok = promote is not None and mean_pass

    # Criteria table for Results (uses seed-mean vs v1 fair baselines)
    swap_criteria = [
        {
            "criterion": "Clean-subset Dice (BUSI) — seed mean",
            "rule": "mean ≥ v1",
            "v1": r3(v1.get("clean_dice")),
            "v2": r3(mean_row["clean_dice"]),
            "v2_sd": r3(summary["clean_dice"]["sd"]),
            "delta": r4(deltas_block["clean_dice"]["mean_delta"]),
            "delta_ci95": [r4(x) for x in deltas_block["clean_dice"]["ci95_paired_bootstrap"]],
            "passed": bool(mean_checks["clean_dice_ok"]),
        },
        {
            "criterion": "BUS-BRA same-source held-out Dice — seed mean",
            "rule": "mean ≥ v1 on same held-out split",
            "v1": r3(v1.get("busbra_heldout_dice")),
            "v2": r3(mean_row["busbra_heldout"]),
            "v2_sd": r3(summary["busbra_heldout"]["sd"]),
            "delta": r4(deltas_block["busbra_heldout"]["mean_delta"]),
            "delta_ci95": [r4(x) for x in deltas_block["busbra_heldout"]["ci95_paired_bootstrap"]],
            "passed": bool(mean_checks["busbra_heldout_ok"]),
            "note": "Not external for v2; v1 baseline is INT8 on the identical held-out IDs.",
        },
        {
            "criterion": "External Dice (BrEaST) — seed mean",
            "rule": "mean ≥ v1",
            "v1": r3(v1.get("breast_dice")),
            "v2": r3(mean_row["breast"]),
            "v2_sd": r3(summary["breast"]["sd"]),
            "delta": r4(deltas_block["breast"]["mean_delta"]),
            "delta_ci95": [r4(x) for x in deltas_block["breast"]["ci95_paired_bootstrap"]],
            "passed": bool(mean_checks["breast_ok"]),
            "note": "Only truly external test for v2.",
        },
        {
            "criterion": "BUSI test AUC — seed mean",
            "rule": "mean drop ≤ 0.02",
            "v1": r3(v1.get("auc")),
            "v2": r3(mean_row["auc"]),
            "v2_sd": r3(summary["auc"]["sd"]),
            "delta": r4(deltas_block["auc"]["mean_delta"]),
            "delta_ci95": [r4(x) for x in deltas_block["auc"]["ci95_paired_bootstrap"]],
            "passed": bool(mean_checks["auc_ok"]),
        },
        {
            "criterion": "INT8 ONNX size — seed mean",
            "rule": "≤ ~25 MB",
            "v1": r3(v1.get("int8_mb")),
            "v2": r3(mean_row["int8_mb"]),
            "v2_sd": r3(summary["int8_mb"]["sd"]),
            "passed": bool(mean_checks["size_ok"]),
        },
    ]

    table = [
        {
            "name": "v1.0.0 served INT8 (160² ResNet-18)",
            "dice": v1.get("test_dice"),
            "lesion_dice": v1.get("lesion_dice"),
            "clean_dice": v1.get("clean_dice"),
            "busbra_dice": v1.get("busbra_heldout_dice"),
            "busbra_label": "same-source held-out (v1 INT8 on v2 split)",
            "breast_dice": v1.get("breast_dice"),
            "auc": v1.get("auc"),
            "int8_mb": v1.get("int8_mb"),
            "busbra_fullset_ref_only": v1.get("busbra_dice_fullset") or v1.get("busbra_dice"),
        }
    ]
    for m in finished:
        table.append(
            {
                "name": f"v2 seed {m['seed']} (resnet34 256²)",
                "dice": m["test_dice"],
                "lesion_dice": m["lesion_dice"],
                "clean_dice": m["clean_dice"],
                "busbra_dice": m["busbra_heldout"],
                "busbra_label": "same-source held-out",
                "breast_dice": m["breast"],
                "auc": m["auc"],
                "int8_mb": m["int8_mb"],
                "swap_ok": m["pass"],
                "checks": m["checks"],
            }
        )
    table.append(
        {
            "name": f"v2 seed mean ± SD (n={len(finished)})",
            "dice": summary["test_dice"]["mean"],
            "dice_sd": summary["test_dice"]["sd"],
            "lesion_dice": summary["lesion_dice"]["mean"],
            "lesion_dice_sd": summary["lesion_dice"]["sd"],
            "clean_dice": summary["clean_dice"]["mean"],
            "clean_dice_sd": summary["clean_dice"]["sd"],
            "busbra_dice": summary["busbra_heldout"]["mean"],
            "busbra_dice_sd": summary["busbra_heldout"]["sd"],
            "busbra_label": "same-source held-out",
            "breast_dice": summary["breast"]["mean"],
            "breast_dice_sd": summary["breast"]["sd"],
            "auc": summary["auc"]["mean"],
            "auc_sd": summary["auc"]["sd"],
            "int8_mb": summary["int8_mb"]["mean"],
            "swap_ok": mean_pass,
            "checks": mean_checks,
        }
    )

    if swap_ok and promote is not None:
        decision_sentence = (
            f"Seed-mean passed the fair swap rule; promoting the median-performing passing seed "
            f"{promote['seed']} (by clean Dice) to v2.0.0 — not the best seed."
        )
        note = decision_sentence
    elif not mean_pass:
        decision_sentence = (
            "Seed-mean failed at least one fair swap criterion, so the site keeps serving v1.0.0."
        )
        note = decision_sentence + f" mean_checks={mean_checks}"
    elif not passing:
        decision_sentence = (
            "No individual seed passed all fair criteria, so the site keeps serving v1.0.0."
        )
        note = decision_sentence
    else:
        decision_sentence = "v2 did not meet the fair promotion rule; keep v1.0.0."
        note = decision_sentence

    # Promote or keep
    metrics = json.loads(METRICS.read_text())
    if swap_ok and promote is not None:
        v2_web = WEB / "models" / "v2.0.0"
        v2_web.mkdir(parents=True, exist_ok=True)
        src = Path(promote["onnx_int8"])
        dest = v2_web / "busi_unet.onnx"
        shutil.copy2(src, dest)
        sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        pp = promote.get("postprocess") or {}
        model_json = {
            "version": "2.0.0",
            "sha256": sha,
            "filename": "busi_unet.onnx",
            "size_bytes": dest.stat().st_size,
            "quantization": "onnxruntime dynamic QUInt8",
            "parent": "1.0.0",
            "model_kind": promote.get("model_kind"),
            "img_size": promote.get("img_size") or 256,
            "postprocess": {
                "seg_threshold": pp.get("seg_threshold", 0.4),
                "min_component_area": pp.get("min_component_area", 40),
                "cls_threshold": 0.5,
            },
            "note": (
                "Phase 4 multi-dataset v2; median passing seed under fair held-out BUS-BRA rule"
            ),
            "metrics_note": note,
            "promoted_seed": promote["seed"],
            "promotion_rule": "median_passing_seed_by_clean_dice_if_seed_mean_passes",
        }
        (v2_web / "model.json").write_text(json.dumps(model_json, indent=2) + "\n")
        current = {
            "version": "2.0.0",
            "path": "models/v2.0.0",
            "sha256": sha,
            "cache_key": f"busi-unet-v2.0.0-{sha[:8]}",
        }
        (WEB / "models" / "current.json").write_text(json.dumps(current, indent=2) + "\n")
        shutil.copy2(dest, WEB / "models" / "busi_unet.onnx")
        print("PROMOTED v2.0.0 seed", promote["seed"], note)
        served_unchanged = False
        metrics["model_version"] = "2.0.0"
    else:
        print("KEEP v1.0.0 —", note)
        served_unchanged = True

    metrics["v2_experiment"] = {
        "served_unchanged": served_unchanged,
        "decision_sentence": decision_sentence,
        "swap_criteria": swap_criteria,
        "swap_note": note,
        "table": table,
        "seed_summary": summary,
        "deltas": deltas_block,
        "mean_checks": mean_checks,
        "mean_pass": mean_pass,
        "promoted_seed": None if promote is None else promote["seed"],
        "promotion_rule": (
            "Promote median-performing passing seed by clean Dice only if seed-mean passes "
            "all fair criteria. BUS-BRA is same-source held-out (v1 baseline on identical split). "
            "BrEaST is the only truly external test."
        ),
        "busbra_label": "same-source held-out",
        "breast_label": "external",
        "v1_busbra_heldout": v1.get("busbra_heldout_meta"),
        "config": exp.get("config"),
        "busbra_split": exp.get("busbra_split"),
        "source": "results/v2_experiment.json",
        "note": (
            "Phase 4 fair comparison: BUSI train + patient-grouped BUS-BRA train; "
            "BUS-BRA held-out is same-source (not external for v2); BrEaST fully external."
        ),
    }
    METRICS.write_text(json.dumps(metrics, indent=2) + "\n")

    exp["v1_baselines"] = v1
    exp["fair_swap"] = {
        "seed_summary": summary,
        "deltas": deltas_block,
        "mean_checks": mean_checks,
        "mean_pass": mean_pass,
        "promoted_seed": None if promote is None else promote["seed"],
        "swap_ok": swap_ok,
    }
    exp["model_policy_decision"] = {
        "swap_ok": swap_ok,
        "served_unchanged": served_unchanged,
        "note": note,
        "fair_busbra": True,
        "promotion_rule": "median_passing_seed_if_mean_passes",
    }
    exp["best"] = None
    if promote is not None:
        exp["best"] = {
            "seed": promote["seed"],
            "role": "median_passing_seed",
            "swap_ok": True,
            "checks": promote["checks"],
            "onnx_int8": promote["onnx_int8"],
            "onnx_sha256": promote["onnx_sha256"],
            "onnx_int8_mb": promote["int8_mb"],
            "metrics": {
                "clean_dice": promote["clean_dice"],
                "busbra_dice": promote["busbra_heldout"],
                "breast_dice": promote["breast"],
                "auc": promote["auc"],
                "int8_mb": promote["int8_mb"],
                "test_dice": promote["test_dice"],
                "lesion_dice": promote["lesion_dice"],
            },
            "postprocess": promote["postprocess"],
            "img_size": promote["img_size"],
            "model_kind": promote["model_kind"],
        }
    # refresh table in experiment file
    exp["table"] = table
    EXP.write_text(json.dumps(exp, indent=2, default=float) + "\n")
    print("Updated", METRICS, "and", EXP)


if __name__ == "__main__":
    main()
