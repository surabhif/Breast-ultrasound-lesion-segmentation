#!/usr/bin/env python3
"""Export paper/numbers.tex macros from web/public/results/metrics.json.

All numeric claims in paper/main.tex must use these macros. Round Dice/AUC
to 3 decimals. Macro names are letters-only (TeX cannot embed digits in
\\newcommand names). Re-run before pdflatex; CI:
scripts/check_paper_numbers_drift.py.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS = ROOT / "web" / "public" / "results" / "metrics.json"
OUT = ROOT / "paper" / "numbers.tex"


def r3(x) -> str:
    if x is None:
        return "n/a"
    return f"{float(x):.3f}"


def r1(x) -> str:
    return f"{float(x):.1f}"


def ci_pair(lo, hi) -> tuple[str, str]:
    return r3(lo), r3(hi)


def cmd(name: str, value: str) -> str:
    if not name.isalpha():
        raise SystemExit(f"Macro name must be letters-only for TeX: {name!r}")
    safe = str(value)
    return f"\\newcommand{{\\{name}}}{{{safe}}}"


def collect(m: dict) -> dict[str, str]:
    cfg = m["config"]
    fp = m["metrics"]
    si = m["served_int8"]
    ext = m.get("external", {})
    datasets = ext.get("datasets", {})
    busbra = datasets.get("busbra", {})
    breast = datasets.get("breast", {})
    busuclm = datasets.get("busuclm", {})
    clean = m.get("cleaning_experiment", {}).get("full_model_clean_vs_flagged", {})
    uncert = m.get("uncertainty", {})
    inp = m.get("inpaint_experiment", {})
    leak = m.get("leakage_ablation", {}).get("summary", {})
    meas = m.get("measurement_agreement", {})
    art = m.get("model_artifact", {})
    sizes = m.get("subset_sizes", {})

    si_ci_lo, si_ci_hi = ci_pair(*si["test_dice_bootstrap_95ci"])
    si_ld_lo, si_ld_hi = ci_pair(*si["lesion_dice_bootstrap_95ci"])
    fp_ci_lo, fp_ci_hi = ci_pair(*fp["test_dice_bootstrap_95ci"])

    busbra_ok = "test_dice" in busbra
    breast_ok = "test_dice" in breast
    busuclm_ok = "test_dice" in busuclm
    busuclm_status = (
        busuclm.get("status")
        if "status" in busuclm
        else ("scored" if busuclm_ok else "unknown")
    )
    busuclm_nfp = int(busuclm.get("normal_false_positive_count", 0)) if busuclm_ok else 0
    busuclm_nn = int(busuclm.get("normal_n", 0)) if busuclm_ok else 0

    nfp = int(si.get("normal_false_positive_count", 12))
    nn = int(si.get("normal_n", 19))

    swap_rows = inp.get("swap_criteria", [])
    v2_clean = next((r for r in swap_rows if "Clean" in r.get("criterion", "")), {})
    v2_busbra = next((r for r in swap_rows if "BUS-BRA" in r.get("criterion", "")), {})
    v2_breast = next((r for r in swap_rows if "BrEaST" in r.get("criterion", "")), {})

    # Letters-only TeX macro names (no digits).
    out = {
        "MetricModelVersion": str(m.get("model_version", "1.0.0")),
        "MetricImgSize": str(int(cfg.get("img_size", 160))),
        "MetricSegThreshold": r1(si.get("seg_threshold", 0.4)),
        "MetricMinArea": str(int(si.get("min_component_area", 40))),
        "MetricNTrain": str(int(sizes.get("train", 0))),
        "MetricNVal": str(int(sizes.get("val", 0))),
        "MetricNTest": str(int(sizes.get("test", 0))),
        "MetricParamsM": r1(cfg.get("params_millions", 12.1)),
        "MetricOnnxMb": r1(art.get("served_mb", 11.7)),
        "MetricFpMb": r1(art.get("fp32_mb", 46.3)),
        # FP32
        "MetricFpTestDice": r3(fp["test_dice"]),
        "MetricFpTestDiceCIlo": r3(fp_ci_lo),
        "MetricFpTestDiceCIhi": r3(fp_ci_hi),
        "MetricFpLesionDice": r3(fp["lesion_dice"]),
        "MetricFpAuc": r3(fp["cls_roc_auc"]),
        "MetricFpIoU": r3(fp["test_iou"]),
        # Served INT8 (primary claims)
        "MetricServedTestDice": r3(si["test_dice"]),
        "MetricServedTestDiceCIlo": si_ci_lo,
        "MetricServedTestDiceCIhi": si_ci_hi,
        "MetricServedLesionDice": r3(si["lesion_dice"]),
        "MetricServedLesionDiceCIlo": si_ld_lo,
        "MetricServedLesionDiceCIhi": si_ld_hi,
        "MetricServedIoU": r3(si["test_iou"]),
        "MetricServedAuc": r3(si["cls_roc_auc"]),
        "MetricServedSens": r3(si["cls_sensitivity"]),
        "MetricServedSpec": r3(si["cls_specificity"]),
        "MetricServedEce": r3(si["cls_ece"]),
        "MetricNormalFP": f"{nfp}/{nn}",
        "MetricNormalFPcount": str(nfp),
        "MetricNormalN": str(nn),
        "MetricNormalFPrate": r3(si.get("normal_false_positive_rate")),
        # Cleaning
        "MetricAnnotRate": r3(
            m.get("cleaning_experiment", {}).get("dataset_counts", {}).get("annotation_rate")
        ),
        "MetricCleanDice": r3(clean.get("clean_test", {}).get("dice_mean")),
        "MetricFlaggedDice": r3(clean.get("flagged_test", {}).get("dice_mean")),
        "MetricDiceInflation": r3(clean.get("dice_inflation_all_minus_clean")),
        "MetricLesionCleanDice": r3(clean.get("lesion_clean", {}).get("dice_mean")),
        "MetricLesionFlaggedDice": r3(clean.get("lesion_flagged", {}).get("dice_mean")),
        # External
        "MetricBusbraN": str(int(busbra["n"])) if busbra_ok else "n/a",
        "MetricBusbraDice": r3(busbra["test_dice"]) if busbra_ok else "n/a",
        "MetricBusbraAuc": r3(busbra["cls_roc_auc"]) if busbra_ok else "n/a",
        "MetricBreastN": str(int(breast["n"])) if breast_ok else "n/a",
        "MetricBreastDice": r3(breast["test_dice"]) if breast_ok else "n/a",
        "MetricBreastAuc": r3(breast["cls_roc_auc"]) if breast_ok else "n/a",
        "MetricBusuclmStatus": busuclm_status,
        "MetricBusuclmN": str(int(busuclm["n"])) if busuclm_ok else "n/a",
        "MetricBusuclmPatients": str(int(busuclm.get("n_patients", 0))) if busuclm_ok else "n/a",
        "MetricBusuclmDice": r3(busuclm["test_dice"]) if busuclm_ok else "n/a",
        "MetricBusuclmLesionDice": r3(busuclm["lesion_dice"]) if busuclm_ok else "n/a",
        "MetricBusuclmAuc": r3(busuclm["cls_roc_auc"]) if busuclm_ok else "n/a",
        "MetricBusuclmNormalFP": f"{busuclm_nfp}/{busuclm_nn}" if busuclm_ok else "n/a",
        # Uncertainty / leakage / swap
        "MetricTtaSpearman": r3(uncert.get("spearman_rho")),
        "MetricDiceAtEightyCov": r3(uncert.get("dice_at_80_coverage")),
        "MetricLeakValDelta": r3(leak.get("val_inflation_random_minus_grouped")),
        "MetricVtwoCleanDice": r3(v2_clean.get("v2")),
        "MetricVoneCleanDice": r3(v2_clean.get("v1")),
        "MetricVtwoBusbraDice": r3(v2_busbra.get("v2")),
        "MetricVoneBusbraDice": r3(v2_busbra.get("v1")),
        "MetricVtwoBreastDice": r3(v2_breast.get("v2")),
        "MetricVoneBreastDice": r3(v2_breast.get("v1")),
        "MetricMeasDiamCorr": r3(
            meas.get("longest_diameter_mm", {}).get("pearson_proxy_for_icc")
        ),
        "MetricSizeDiscord": r3(
            meas.get("longest_diameter_mm", {}).get("t1_t2_20mm_discordance_rate")
        ),
    }
    return out


def write_tex(macros: dict[str, str]) -> str:
    lines = [
        "% Auto-generated by scripts/export_paper_numbers.py — do not edit by hand.",
        "% Source: web/public/results/metrics.json",
        "% Re-run: python scripts/export_paper_numbers.py",
        "",
    ]
    for name, value in macros.items():
        lines.append(cmd(name, value))
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    if not METRICS.exists():
        raise SystemExit(f"Missing {METRICS}")
    data = json.loads(METRICS.read_text())
    macros = collect(data)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = write_tex(macros)
    OUT.write_text(text)
    print(f"Wrote {OUT} ({len(macros)} macros)")
    for k in (
        "MetricServedTestDice",
        "MetricServedLesionDice",
        "MetricServedAuc",
        "MetricBusbraDice",
        "MetricBreastDice",
        "MetricNormalFP",
    ):
        print(f"  \\{k} = {macros[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
