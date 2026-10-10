#!/usr/bin/env python3
"""Build web/public/report.pdf from results JSON + generated figures.

All numeric placeholders are filled from committed JSON. Uses DejaVu fonts so
Unicode (e.g. Pawłowska) renders. Reader-facing text omits internal decision codes
and file-system paths (source captions under tables are allowed).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_PDF = ROOT / "web" / "public" / "report.pdf"
FILLED_MD = ROOT / "docs" / "report" / "report.filled.md"
NUMBERS_JSON = ROOT / "docs" / "report" / "numbers.json"
PLAIN_ABSTRACT_TS = ROOT / "web" / "src" / "lib" / "plainAbstract.ts"
FIG_DIR = ROOT / "docs" / "report" / "figures"

FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FONT_SERIF_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"

HOW_BUILT = (
    "Project by Surabhi Fadnavis. The code, analysis, text, and video were "
    "produced with AI tools (Cursor)."
)

TEAL = (41 / 255, 115 / 255, 115 / 255)


def load(path: Path):
    with path.open() as f:
        return json.load(f)


def fmt(x, digits=3, *, label: str = "value"):
    if x is None:
        raise SystemExit(f"Missing numeric {label} (refusing placeholder)")
    if isinstance(x, str):
        return x
    return f"{float(x):.{digits}f}"


def pct(x, digits=1, *, label: str = "value"):
    if x is None:
        raise SystemExit(f"Missing fraction {label} (refusing placeholder)")
    return f"{100.0 * float(x):.{digits}f}%"


def normal_fp_from_empty_mask_dice(by_label: dict) -> tuple[int, int]:
    """For empty-GT normals, per-image Dice is 0 or 1, so FP count = (1 − mean Dice) × n."""
    block = by_label["normal"]
    n = int(block["n"])
    mean_dice = float(block["dice_mean"])
    n_fp = int(round((1.0 - mean_dice) * n))
    if not (0 <= n_fp <= n):
        raise SystemExit(f"Implausible normal FP count {n_fp}/{n}")
    return n_fp, n


def plain_abstract(nums: dict[str, str]) -> str:
    """~200–250 word plain-language abstract; no unexplained acronyms."""
    return (
        f"Breast ultrasound helps doctors look at breast lumps, especially when mammograms are "
        f"hard to read in dense tissue. This student project builds a program that outlines those "
        f"lumps on ultrasound pictures and estimates how well it does at telling harmless from "
        f"cancerous lumps. It was trained on one public image collection and checked on three "
        f"others from different hospitals. "
        f"The main quality measure is an outline-overlap score (Dice), which is high when the "
        f"computer outline matches the expert outline. On images saved for testing, the browser "
        f"version reaches {nums['INT8_DICE']} overall. On images that contain a lump, the outline "
        f"match is {nums['INT8_LESION_DICE']}. On two outside collections, outline scores stay "
        f"similar ({nums['BUSBRA_DICE']} and {nums['BREAST_DICE']}), while telling harmless from "
        f"cancerous lumps gets harder after the hospital and scanner change. On a third outside "
        f"collection, pictures without lumps remain difficult: false outlines pull the overall "
        f"score down to {nums['BUSUCLM_DICE']}, even though on images that contain a lump the "
        f"outline match is {nums['BUSUCLM_LESION_DICE']}. "
        f"The write-up also studies near-identical photos, burned-in measurement marks, and whether "
        f"outlines stay stable when a picture is flipped. A retrained version did better on some "
        f"outside images but not consistently, so the original stays. This is an educational "
        f"research demonstration, not a medical device, and must not be used for diagnosis or care "
        f"decisions."
    )


def collect_numbers() -> dict[str, str]:
    full = load(ROOT / "results" / "full_run.json")
    int8 = load(ROOT / "results" / "served_int8_test.json")
    busbra = load(ROOT / "results" / "external" / "busbra.json")
    breast = load(ROOT / "results" / "external" / "breast.json")
    clean = load(ROOT / "results" / "cleaning_experiment.json")
    leak = load(ROOT / "results" / "leakage_ablation.json")
    inp = load(ROOT / "results" / "inpaint_experiment.json")
    uncert = load(ROOT / "results" / "uncertainty.json")
    meas = load(ROOT / "results" / "measurement_agreement.json")
    metrics = load(ROOT / "web" / "public" / "results" / "metrics.json")
    v2 = load(ROOT / "results" / "v2_experiment.json")
    mistakes = load(ROOT / "web" / "public" / "results" / "mistakes.json")

    fp32 = full["metrics"]["test"]
    fp32_cls = fp32["classification"]
    fp32_nfp, fp32_nn = normal_fp_from_empty_mask_dice(fp32["by_label"])

    ea = inp["E_a"]["original"]
    ec = inp.get("E_c") or {}
    best_seed_id = ec.get("best_seed")
    seed_row = None
    for row in ec.get("seeds") or []:
        if row.get("seed") == best_seed_id:
            seed_row = row
            break
    if seed_row is None and ec.get("seeds"):
        seed_row = ec["seeds"][0]
    ec_busbra = (seed_row or {}).get("external_busbra", {}).get("dice_mean")
    ec_breast = (seed_row or {}).get("external_breast", {}).get("dice_mean")

    runs = leak.get("runs") or []
    grouped_vals = [r["val_dice"] for r in runs if r.get("mode") == "grouped" and "val_dice" in r]
    random_vals = [r["val_dice"] for r in runs if r.get("mode") == "random" and "val_dice" in r]
    if not grouped_vals or not random_vals:
        raise SystemExit("Missing leakage ablation val_dice runs")
    leak_delta = sum(random_vals) / len(random_vals) - sum(grouped_vals) / len(grouped_vals)

    cov80 = None
    for row in uncert.get("risk_coverage") or []:
        if abs(float(row.get("coverage", -1)) - 0.8) < 1e-6:
            cov80 = row.get("mean_dice")
            break
    if cov80 is None:
        raise SystemExit("Missing uncertainty risk-coverage at 0.8")

    busuclm_js = load(ROOT / "results" / "external" / "busuclm.json")
    if "test_dice" in busuclm_js:
        busuclm = (
            f"**BUS-UCLM** (Vallez et al., 2025; Mendeley Creative Commons Attribution 4.0) is "
            f"scored for the frozen browser model: n={busuclm_js['n']} / "
            f"{busuclm_js['n_patients']} patients (43 Doppler/combined frames excluded). "
            f"Overall outline-overlap score **{fmt(busuclm_js['test_dice'])}** "
            f"[{fmt(busuclm_js['test_dice_bootstrap_95ci'][0])}, "
            f"{fmt(busuclm_js['test_dice_bootstrap_95ci'][1])}]; "
            f"on images that contain a lump, **{fmt(busuclm_js['lesion_dice'])}** "
            f"[{fmt(busuclm_js['lesion_dice_bootstrap_95ci'][0])}, "
            f"{fmt(busuclm_js['lesion_dice_bootstrap_95ci'][1])}]; "
            f"area under the receiver-operating curve (AUC) **{fmt(busuclm_js['cls_roc_auc'])}**. "
            f"Normal false positives dominate the overall figure "
            f"({busuclm_js['normal_false_positive_count']}/{busuclm_js['normal_n']}) — the same "
            f"known weakness as on BUSI ({int8.get('normal_false_positive_count')}/"
            f"{int8.get('normal_n')}). Prefer the score on images that contain a lump when "
            f"comparing across collections (between BrEaST and BUS-BRA)."
        )
        busuclm_dice = fmt(busuclm_js["test_dice"], label="BUS-UCLM dice")
        busuclm_lesion = fmt(busuclm_js["lesion_dice"], label="BUS-UCLM lesion dice")
        busuclm_auc = fmt(busuclm_js["cls_roc_auc"], label="BUS-UCLM auc")
        busuclm_n = str(busuclm_js["n"])
        busuclm_np = str(busuclm_js["n_patients"])
        busuclm_nfp = f"{busuclm_js['normal_false_positive_count']}/{busuclm_js['normal_n']}"
        busuclm_benign = fmt(busuclm_js["by_label"]["benign"]["dice_mean"], label="BUS-UCLM benign")
        busuclm_malig = fmt(
            busuclm_js["by_label"]["malignant"]["dice_mean"], label="BUS-UCLM malignant"
        )
    else:
        busuclm = (
            "BUS-UCLM was not included because its Mendeley Data download requires a login "
            "(the request returned HTTP 403)."
        )
        busuclm_dice = busuclm_lesion = busuclm_auc = busuclm_n = busuclm_np = busuclm_nfp = "n/a"
        busuclm_benign = busuclm_malig = "n/a"

    bl = int8["by_label"]
    art = metrics.get("model_artifact") or {}
    served_mb = art.get("served_mb")
    fp32_mb = art.get("fp32_mb")
    if served_mb is None or fp32_mb is None:
        raise SystemExit("Missing model_artifact MB sizes")

    fs = (v2.get("fair_swap") or {}).get("deltas") or {}
    ss = (v2.get("fair_swap") or {}).get("seed_summary") or {}
    if not fs or not ss:
        raise SystemExit("Missing v2 fair_swap deltas/seed_summary")

    err_counts: dict[str, int] = {}
    for row in mistakes.get("rows") or []:
        et = row.get("error_type") or "unknown"
        err_counts[et] = err_counts.get(et, 0) + 1
    n_mistakes = sum(err_counts.values())
    if n_mistakes < 1:
        raise SystemExit("Missing mistakes.json rows")

    dc = clean["dataset_counts"]
    subsets = full.get("subset_sizes") or {}
    nums = {
        "MODEL_VERSION": "1.0.0",
        "PAGES_URL": "https://surabhif.github.io/Breast-ultrasound-lesion-segmentation/",
        "GITHUB_URL": "https://github.com/surabhif/Breast-ultrasound-lesion-segmentation",
        "DOI_URL": "https://doi.org/10.5281/zenodo.23286597",
        "HOW_BUILT": HOW_BUILT,
        "SEG_THR": fmt(int8.get("seg_threshold", 0.4), 1, label="seg_threshold"),
        "MIN_AREA": str(int(int8.get("min_component_area", 40))),
        "MODEL_SHA8": str(int8.get("sha256", ""))[:8],
        "SERVED_MB": fmt(served_mb, 1, label="served_mb"),
        "FP32_MB": fmt(fp32_mb, 1, label="fp32_mb"),
        "N_TRAIN": str(subsets.get("train", "")),
        "N_VAL": str(subsets.get("val", "")),
        "N_TEST": str(subsets.get("test", "") or int8.get("n")),
        "FP32_DICE": fmt(fp32.get("dice_mean"), label="FP32 dice"),
        "FP32_LESION_DICE": fmt(fp32.get("lesion_dice_mean"), label="FP32 lesion dice"),
        "FP32_IOU": fmt(fp32.get("iou_mean"), label="FP32 iou"),
        "FP32_AUC": fmt(fp32_cls.get("roc_auc"), label="FP32 auc"),
        "FP32_SENS": fmt(fp32_cls.get("sensitivity"), label="FP32 sens"),
        "FP32_SPEC": fmt(fp32_cls.get("specificity"), label="FP32 spec"),
        "FP32_ECE": fmt(fp32_cls.get("ece"), label="FP32 ece"),
        "FP32_NFP": f"{fp32_nfp}/{fp32_nn}",
        "INT8_DICE": fmt(int8.get("dice_mean"), label="INT8 dice"),
        "INT8_LESION_DICE": fmt(int8.get("lesion_dice_mean"), label="INT8 lesion dice"),
        "INT8_IOU": fmt(int8.get("iou_mean"), label="INT8 iou"),
        "INT8_AUC": fmt(int8.get("cls_roc_auc"), label="INT8 auc"),
        "INT8_NFP": f"{int8.get('normal_false_positive_count')}/{int8.get('normal_n')}",
        "INT8_SENS": fmt(int8.get("cls_sensitivity"), label="INT8 sens"),
        "INT8_SPEC": fmt(int8.get("cls_specificity"), label="INT8 spec"),
        "INT8_ECE": fmt(int8.get("cls_ece"), label="INT8 ece"),
        "INT8_BENIGN_DICE": fmt(bl["benign"]["dice_mean"], label="INT8 benign"),
        "INT8_MALIG_DICE": fmt(bl["malignant"]["dice_mean"], label="INT8 malignant"),
        "INT8_BENIGN_N": str(bl["benign"]["n"]),
        "INT8_MALIG_N": str(bl["malignant"]["n"]),
        "INT8_NORMAL_N": str(bl["normal"]["n"]),
        "BUSBRA_DICE": fmt(busbra.get("test_dice"), label="BUS-BRA dice"),
        "BUSBRA_LESION_DICE": fmt(busbra.get("lesion_dice"), label="BUS-BRA lesion dice"),
        "BUSBRA_AUC": fmt(busbra.get("cls_roc_auc"), label="BUS-BRA auc"),
        "BUSBRA_N": str(busbra.get("n")),
        "BUSBRA_NP": str(busbra.get("n_patients")),
        "BUSBRA_BENIGN_DICE": fmt(
            busbra["by_label"]["benign"]["dice_mean"], label="BUS-BRA benign"
        ),
        "BUSBRA_MALIG_DICE": fmt(
            busbra["by_label"]["malignant"]["dice_mean"], label="BUS-BRA malignant"
        ),
        "BREAST_DICE": fmt(breast.get("test_dice"), label="BrEaST dice"),
        "BREAST_LESION_DICE": fmt(breast.get("lesion_dice"), label="BrEaST lesion dice"),
        "BREAST_AUC": fmt(breast.get("cls_roc_auc"), label="BrEaST auc"),
        "BREAST_N": str(breast.get("n")),
        "BREAST_NP": str(breast.get("n_patients")),
        "BREAST_BENIGN_DICE": fmt(
            breast["by_label"]["benign"]["dice_mean"], label="BrEaST benign"
        ),
        "BREAST_MALIG_DICE": fmt(
            breast["by_label"]["malignant"]["dice_mean"], label="BrEaST malignant"
        ),
        "BUSUCLM_SENTENCE": busuclm,
        "BUSUCLM_DICE": busuclm_dice,
        "BUSUCLM_LESION_DICE": busuclm_lesion,
        "BUSUCLM_AUC": busuclm_auc,
        "BUSUCLM_N": busuclm_n,
        "BUSUCLM_NP": busuclm_np,
        "BUSUCLM_NFP": busuclm_nfp,
        "BUSUCLM_BENIGN_DICE": busuclm_benign,
        "BUSUCLM_MALIG_DICE": busuclm_malig,
        "ANNOTATION_RATE": pct(dc["annotation_rate"], label="annotation_rate"),
        "N_FLAGGED": str(dc["n_annotation_flagged"]),
        "N_TOTAL": str(dc["n_total"]),
        "N_DUP_GROUPS": str(dc["n_dup_groups"]),
        "N_MULTI_DUP": str(dc["n_in_multi_member_groups"]),
        "LEAK_EPOCHS": str(leak.get("epochs")),
        "LEAK_SEEDS": ",".join(str(s) for s in leak.get("seeds", [])),
        "LEAK_DELTA": fmt(leak_delta, label="leak_delta"),
        "EA_FLAGGED": fmt(ea.get("dice_flagged"), label="E-a flagged"),
        "EA_CLEAN": fmt(ea.get("dice_clean"), label="E-a clean"),
        "EA_ORIG_DICE": fmt(ea.get("dice_mean"), label="E-a original"),
        "EA_INP_DICE": fmt(inp["E_a"]["inpainted"].get("dice_mean"), label="E-a inpainted"),
        "EC_BUSBRA": fmt(ec_busbra, label="E-c BUS-BRA"),
        "EC_BREAST": fmt(ec_breast, label="E-c BrEaST"),
        "EC_CLEAN": fmt(
            (seed_row or {}).get("test_clean_subset_original", {}).get("dice_mean"),
            label="E-c clean",
        ),
        "EC_AUC": fmt((seed_row or {}).get("test_original", {}).get("cls_roc_auc"), label="E-c auc"),
        "UNCERT_RHO": fmt(uncert["spearman_uncertainty_vs_error"]["rho"], label="uncert rho"),
        "UNCERT_N": str(uncert.get("n")),
        "UNCERT_COV80": fmt(cov80, label="uncert cov80"),
        "MEAS_DIAM_R": fmt(meas["longest_diameter_mm"]["pearson_proxy_for_icc"], label="meas diam"),
        "MEAS_N": str(meas.get("n")),
        "MEAS_T1T2": pct(
            meas["longest_diameter_mm"]["t1_t2_20mm_discordance_rate"], label="meas t1t2"
        ),
        "MEAS_AREA_R": fmt(meas["area_px"]["pearson_proxy_for_icc"], label="meas area"),
        "V2_CLEAN_MEAN": fmt(ss["clean_dice"]["mean"], label="v2 clean mean"),
        "V2_CLEAN_DELTA": fmt(fs["clean_dice"]["mean_delta"], label="v2 clean delta"),
        "V2_BUSBRA_MEAN": fmt(ss["busbra_heldout"]["mean"], label="v2 busbra mean"),
        "V2_BREAST_MEAN": fmt(ss["breast"]["mean"], label="v2 breast mean"),
        "V2_AUC_MEAN": fmt(ss["auc"]["mean"], label="v2 auc mean"),
        "V2_INT8_MB": fmt(ss["int8_mb"]["mean"], 1, label="v2 int8 mb"),
        "V1_CLEAN": fmt(fs["clean_dice"]["v1"], label="v1 clean"),
        "ERR_N": str(n_mistakes),
        "ERR_BOUNDARY": str(err_counts.get("boundary_disagreement", 0)),
        "ERR_FP_NORMAL": str(err_counts.get("false_lesion_on_normal", 0)),
        "ERR_WRONG_CLS": str(err_counts.get("wrong_class", 0)),
        "ERR_MISSED": str(err_counts.get("missed_lesion", 0)),
        "ERR_OVER": str(err_counts.get("over_segmentation", 0)),
        "ERR_UNDER": str(err_counts.get("under_segmentation", 0)),
    }
    if "None" in nums["INT8_NFP"] or nums["INT8_NFP"].startswith("/"):
        raise SystemExit(f"Bad INT8_NFP {nums['INT8_NFP']!r}")
    forbidden = ("n/a", "None", "TODO", "NaN", "data/external/")
    for k, v in nums.items():
        if k in ("HOW_BUILT", "PAGES_URL", "GITHUB_URL", "DOI_URL", "BUSUCLM_SENTENCE"):
            continue
        if v == "n/a":
            continue
        for bad in forbidden:
            if bad in v:
                raise SystemExit(f"Placeholder {bad!r} in {k}={v!r}")
    return nums


def write_plain_abstract_ts(nums: dict[str, str]) -> None:
    """Keep the site About/Results intro in sync with the PDF abstract."""
    text = plain_abstract(nums)
    # Escape for a TypeScript template literal
    esc = text.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
    PLAIN_ABSTRACT_TS.parent.mkdir(parents=True, exist_ok=True)
    PLAIN_ABSTRACT_TS.write_text(
        "/** Auto-synced plain-language abstract from scripts/build_report_pdf.py — do not edit by hand. */\n"
        f"export const PLAIN_ABSTRACT = `{esc}`\n"
        f"export const PLAIN_ABSTRACT_WORD_TARGET = '200-250'\n"
    )


def make_figures() -> dict[str, Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

    # Pipeline diagram
    fig, ax = plt.subplots(figsize=(7.2, 2.8), dpi=140)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3)
    ax.axis("off")
    steps = [
        (0.3, "Public\nultrasound\nimages"),
        (2.0, "Clean &\ngroup near-\nduplicates"),
        (3.8, "Train outline\n+ lump-type\nmodel"),
        (5.6, "Shrink for\nbrowser\n(download)"),
        (7.4, "Choose\noutline\nthreshold"),
        (9.0, "Score on\nown test &\noutside sets"),
    ]
    for x, label in steps:
        ax.add_patch(
            mpatches.FancyBboxPatch(
                (x - 0.55, 0.7),
                1.2,
                1.6,
                boxstyle="round,pad=0.08,rounding_size=0.15",
                facecolor=(0.87, 0.93, 0.93),
                edgecolor=TEAL,
                linewidth=1.4,
            )
        )
        ax.text(x, 1.5, label, ha="center", va="center", fontsize=7.5, color="#0e0e0e")
    for x0, x1 in [(0.85, 1.45), (2.55, 3.15), (4.35, 4.95), (6.15, 6.75), (7.95, 8.45)]:
        ax.annotate(
            "",
            xy=(x1, 1.5),
            xytext=(x0, 1.5),
            arrowprops=dict(arrowstyle="->", color=TEAL, lw=1.3),
        )
    ax.set_title("Figure 1. End-to-end pipeline (plain overview)", fontsize=10, color="#0e0e0e", pad=6)
    fig.tight_layout()
    paths["pipeline"] = FIG_DIR / "fig_pipeline.png"
    fig.savefig(paths["pipeline"], bbox_inches="tight")
    plt.close(fig)

    # Dice distribution from per-image INT8
    per = load(ROOT / "results" / "served_int8_per_image.json")
    if isinstance(per, list):
        rows = per
    else:
        rows = per.get("rows") or per.get("images") or []
    dice_vals = [float(r["dice"]) for r in rows if isinstance(r, dict) and "dice" in r]
    if not dice_vals:
        raise SystemExit("No Dice values found in served_int8_per_image.json")

    fig, ax = plt.subplots(figsize=(5.2, 3.2), dpi=140)
    ax.hist(dice_vals, bins=18, color=TEAL, edgecolor="white")
    ax.set_xlabel("Outline-overlap score (Dice) on the project's own BUSI test")
    ax.set_ylabel("Count")
    ax.set_title("Figure 2. Served browser-model Dice distribution")
    ax.axvline(np.mean(dice_vals), color="#c81e4a", linestyle="--", label=f"mean={np.mean(dice_vals):.3f}")
    ax.legend(fontsize=8)
    fig.tight_layout()
    paths["dice_hist"] = FIG_DIR / "fig_dice_hist.png"
    fig.savefig(paths["dice_hist"])
    plt.close(fig)

    # ROC internal vs external
    metrics = load(ROOT / "web" / "public" / "results" / "metrics.json")
    roc = metrics.get("roc_curve") or []
    busbra = load(ROOT / "results" / "external" / "busbra.json")
    breast = load(ROOT / "results" / "external" / "breast.json")

    fig, ax = plt.subplots(figsize=(5.2, 3.6), dpi=140)
    if roc:
        auc_lab = fmt(
            metrics.get("served_int8", {}).get("cls_roc_auc")
            or metrics.get("metrics", {}).get("cls_roc_auc")
        )
        ax.plot(
            [p["fpr"] for p in roc],
            [p["tpr"] for p in roc],
            color=TEAL,
            lw=2,
            label=f"BUSI served AUC={auc_lab}",
        )
    for name, blob, color in [
        ("BUS-BRA", busbra, "#0e0e0e"),
        ("BrEaST", breast, "#c45c26"),
    ]:
        er = blob.get("roc_curve") or []
        if er:
            ax.plot(
                [p["fpr"] for p in er],
                [p["tpr"] for p in er],
                color=color,
                lw=1.6,
                label=f"{name} AUC={fmt(blob.get('cls_roc_auc'))}",
            )
        else:
            ax.plot([], [], color=color, label=f"{name} AUC={fmt(blob.get('cls_roc_auc'))} (curve not stored)")
    ax.plot([0, 1], [0, 1], "k--", lw=0.8, alpha=0.5)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("Figure 3. Classification ROC (internal vs external)")
    ax.legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    paths["roc"] = FIG_DIR / "fig_roc.png"
    fig.savefig(paths["roc"])
    plt.close(fig)

    # Calibration
    cal = metrics.get("calibration") or []
    fig, ax = plt.subplots(figsize=(5.2, 3.4), dpi=140)
    xs = [c.get("mean_predicted") for c in cal if c.get("mean_predicted") is not None]
    ys = [c.get("fraction_positive") for c in cal if c.get("mean_predicted") is not None]
    if xs:
        ax.plot(xs, ys, "o-", color=TEAL, label="Reliability")
    ax.plot([0, 1], [0, 1], "k--", lw=0.8, alpha=0.5)
    ax.set_xlabel("Mean predicted P(malignant)")
    ax.set_ylabel("Fraction malignant")
    ax.set_title("Figure 4. Calibration (BUSI served model)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    paths["cal"] = FIG_DIR / "fig_calibration.png"
    fig.savefig(paths["cal"])
    plt.close(fig)

    # Leakage ablation
    leak = load(ROOT / "results" / "leakage_ablation.json")
    fig, ax = plt.subplots(figsize=(5.2, 3.2), dpi=140)
    modes: dict[str, list] = {}
    for r in leak.get("runs") or []:
        modes.setdefault(r["mode"], []).append(r.get("val_dice") or r.get("test_dice"))
    labels = list(modes.keys())
    means = [sum(v) / len(v) for v in modes.values()]
    stds = [float(np.std(v)) if len(v) > 1 else 0 for v in modes.values()]
    ax.bar(labels, means, yerr=stds, color=[TEAL, "#89b2b2"][: len(labels)], edgecolor="white", capsize=4)
    ax.set_ylabel("Validation outline-overlap score")
    ax.set_title("Figure 5. Leakage ablation (grouped vs random)")
    fig.tight_layout()
    paths["leak"] = FIG_DIR / "fig_leakage.png"
    fig.savefig(paths["leak"])
    plt.close(fig)

    # Caliper before/after
    before = ROOT / "web" / "public" / "samples" / "external" / "breast_03_with_synthetic_calipers.png"
    after = ROOT / "web" / "public" / "samples" / "external" / "breast_03_calipers_inpainted.png"
    fig, axes = plt.subplots(1, 2, figsize=(6.2, 3.2), dpi=140)
    axes[0].imshow(plt.imread(before), cmap="gray")
    axes[0].set_title("Before (synthetic calipers)")
    axes[0].axis("off")
    axes[1].imshow(plt.imread(after), cmap="gray")
    axes[1].set_title("After Telea inpaint")
    axes[1].axis("off")
    fig.suptitle("Figure 6. Caliper erase demo (CC BY BrEaST; digitally altered)", fontsize=10)
    fig.tight_layout()
    paths["caliper"] = FIG_DIR / "fig_caliper.png"
    fig.savefig(paths["caliper"])
    plt.close(fig)

    # TTA uncertainty vs error
    up = load(ROOT / "results" / "uncertainty_per_image.json")
    urows = up if isinstance(up, list) else up.get("rows") or up.get("images") or []
    xs, ys = [], []
    for r in urows:
        if not isinstance(r, dict):
            continue
        u = r.get("uncertainty") or r.get("disagreement") or r.get("tta_disagreement")
        d = r.get("dice")
        if u is None or d is None:
            continue
        xs.append(float(u))
        ys.append(1.0 - float(d))
    fig, ax = plt.subplots(figsize=(5.2, 3.4), dpi=140)
    if xs:
        ax.scatter(xs, ys, s=14, alpha=0.65, color=TEAL)
    uncert = load(ROOT / "results" / "uncertainty.json")
    rho = uncert["spearman_uncertainty_vs_error"]["rho"]
    ax.set_xlabel("Test-time augmentation disagreement")
    ax.set_ylabel("1 − Dice")
    ax.set_title(f"Figure 7. Uncertainty vs error (Spearman ρ={rho:.3f})")
    fig.tight_layout()
    paths["uncert"] = FIG_DIR / "fig_uncertainty.png"
    fig.savefig(paths["uncert"])
    plt.close(fig)

    # Failure silhouette grid
    sil_dir = ROOT / "web" / "public" / "results" / "mistakes_silhouettes"
    sils = sorted(sil_dir.glob("*.png"))[:12]
    fig, axes = plt.subplots(3, 4, figsize=(6.4, 4.8), dpi=140)
    for ax, p in zip(axes.ravel(), sils):
        ax.imshow(plt.imread(p))
        ax.set_title(p.stem.split("__")[0][:10], fontsize=7)
        ax.axis("off")
    for ax in axes.ravel()[len(sils) :]:
        ax.axis("off")
    fig.suptitle(
        "Figure 8. Failure-case outline silhouettes (BUSI; no ultrasound pixels)", fontsize=9
    )
    fig.tight_layout()
    paths["fail"] = FIG_DIR / "fig_failures.png"
    fig.savefig(paths["fail"])
    plt.close(fig)

    return paths


def build_pdf(nums: dict[str, str], figs: dict[str, Path]) -> None:
    from reportlab.lib.colors import HexColor, Color
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        Image,
        KeepTogether,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
        HRFlowable,
        Flowable,
    )

    pdfmetrics.registerFont(TTFont("DejaVu", FONT_REG))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", FONT_BOLD))
    if Path(FONT_SERIF).exists():
        pdfmetrics.registerFont(TTFont("DejaVuSerif", FONT_SERIF))
        title_font = "DejaVuSerif"
    else:
        title_font = "DejaVu-Bold"
    if Path(FONT_SERIF_BOLD).exists():
        pdfmetrics.registerFont(TTFont("DejaVuSerif-Bold", FONT_SERIF_BOLD))
        title_bold = "DejaVuSerif-Bold"
    else:
        title_bold = "DejaVu-Bold"

    teal = HexColor("#297373")
    ink = HexColor("#0e0e0e")
    muted = HexColor("#5c6b6b")
    box_bg = HexColor("#e8f2f2")

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="TitleTeal",
            fontName=title_bold,
            fontSize=16,
            leading=20,
            textColor=teal,
            alignment=TA_CENTER,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Meta",
            fontName="DejaVu",
            fontSize=9,
            leading=12,
            textColor=muted,
            alignment=TA_CENTER,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H1R",
            fontName="DejaVu-Bold",
            fontSize=12,
            leading=15,
            textColor=teal,
            spaceBefore=12,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H2R",
            fontName="DejaVu-Bold",
            fontSize=10.5,
            leading=13,
            textColor=ink,
            spaceBefore=9,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyR",
            fontName="DejaVu",
            fontSize=9.5,
            leading=13.2,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BulletR",
            fontName="DejaVu",
            fontSize=9.2,
            leading=12.6,
            leftIndent=12,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="KeyBullet",
            fontName="DejaVu",
            fontSize=9.0,
            leading=12.2,
            leftIndent=8,
            spaceAfter=3,
            textColor=ink,
        )
    )
    styles.add(
        ParagraphStyle(
            name="KeyTitle",
            fontName="DejaVu-Bold",
            fontSize=10.5,
            leading=13,
            textColor=teal,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Cap",
            fontName="DejaVu",
            fontSize=8,
            leading=10.5,
            textColor=muted,
            alignment=TA_CENTER,
            spaceAfter=8,
            spaceBefore=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Warn",
            fontName="DejaVu-Bold",
            fontSize=9,
            leading=12,
            textColor=HexColor("#ffffff"),
            backColor=teal,
            borderPadding=6,
            spaceAfter=10,
            alignment=TA_CENTER,
        )
    )
    styles.add(ParagraphStyle(name="Cell", fontName="DejaVu", fontSize=7.8, leading=10.2))
    styles.add(ParagraphStyle(name="CellB", fontName="DejaVu-Bold", fontSize=7.8, leading=10.2))
    styles.add(
        ParagraphStyle(
            name="GlossTerm",
            fontName="DejaVu-Bold",
            fontSize=9.2,
            leading=12,
            textColor=teal,
            spaceBefore=6,
            spaceAfter=1,
        )
    )
    styles.add(
        ParagraphStyle(
            name="GlossDef",
            fontName="DejaVu",
            fontSize=8.8,
            leading=11.8,
            alignment=TA_JUSTIFY,
            spaceAfter=2,
        )
    )
    styles.add(
        ParagraphStyle(
            name="AbstractBody",
            fontName="DejaVu",
            fontSize=9.4,
            leading=13.0,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
            firstLineIndent=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="RefR",
            fontName="DejaVu",
            fontSize=8.6,
            leading=11.4,
            leftIndent=12,
            spaceAfter=4,
        )
    )

    def P(text: str, style="BodyR"):
        html = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html)
        html = re.sub(r"`(.+?)`", r"<font face='DejaVu' size='8'>\1</font>", html)
        return Paragraph(html, styles[style])

    def table(headers, rows, col_widths=None):
        data = [[Paragraph(h, styles["CellB"]) for h in headers]]
        for r in rows:
            data.append([Paragraph(str(c), styles["Cell"]) for c in r])
        n = len(headers)
        if col_widths is None:
            if n <= 4:
                col_widths = [1.55 * inch] + [1.25 * inch] * (n - 1)
            elif n == 5:
                col_widths = [1.15 * inch] * 5
            elif n == 6:
                col_widths = [1.05 * inch] * 6
            else:
                usable = 7.1 * inch
                col_widths = [usable / n] * n
        t = Table(data, hAlign="LEFT", colWidths=col_widths)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), HexColor("#dfeaea")),
                    ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#89b2b2")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        return t

    def fig(key: str, width=6.0 * inch, aspect=0.58):
        path = figs[key]
        im = Image(str(path), width=width, height=width * aspect)
        im.hAlign = "CENTER"
        return im

    def key_findings_box():
        bullets = [
            f"On images saved for testing, the browser program’s outline-overlap score is "
            f"**{nums['INT8_DICE']}** overall. On images that contain a lump, the outline match "
            f"is **{nums['INT8_LESION_DICE']}**.",
            f"On outside hospitals, outline quality stays in a similar ballpark on BUS-BRA "
            f"(**{nums['BUSBRA_DICE']}**) and BrEaST (**{nums['BREAST_DICE']}**), but telling "
            f"harmless from cancerous lumps gets harder (**{nums['BUSBRA_AUC']}** / "
            f"**{nums['BREAST_AUC']}** vs **{nums['INT8_AUC']}** on the original test set).",
            f"On BUS-UCLM, pictures without lumps often get false outlines "
            f"({nums['BUSUCLM_NFP']}). On images that contain a lump, the outline match is "
            f"**{nums['BUSUCLM_LESION_DICE']}** — the fairer comparison.",
            f"Near-identical photos are common ({nums['N_MULTI_DUP']} images sit in "
            f"multi-member groups). Checking for near-identical photos showed they did not "
            f"inflate the scores, but patient IDs are still missing from the main training set.",
            f"Erasing measurement marks and retraining helped on some outside images, but not "
            f"consistently enough to replace the published model, so the original stays "
            f"(version {nums['MODEL_VERSION']}).",
            "This is an educational research demo only — not for diagnosis, screening, or care "
            "decisions.",
        ]
        inner = [P("Key findings in plain English", "KeyTitle")]
        for b in bullets:
            inner.append(P("• " + b, "KeyBullet"))
        box = Table([[inner]], colWidths=[6.9 * inch])
        box.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), box_bg),
                    ("BOX", (0, 0), (-1, -1), 1.5, teal),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        return box

    story = []
    story.append(P("Breast Ultrasound Lesion Segmentation: Research Write-up", "TitleTeal"))
    story.append(P(f"Version {nums['MODEL_VERSION']} · Site-only research report (not a journal submission)", "Meta"))
    story.append(P("Author: Surabhi Fadnavis (high-school senior, Georgia)", "Meta"))
    story.append(P(f"Live demo: {nums['PAGES_URL']}", "Meta"))
    story.append(P(f"Repository: {nums['GITHUB_URL']}", "Meta"))
    story.append(P(f"Software DOI: {nums['DOI_URL']}", "Meta"))
    story.append(Spacer(1, 6))
    story.append(
        P(
            "Research demo — not for clinical use. Not for diagnosis, screening, or care decisions.",
            "Warn",
        )
    )

    story.append(P("1. Abstract", "H1R"))
    abs_text = plain_abstract(nums)
    story.append(P(abs_text, "AbstractBody"))
    wc = len(abs_text.split())
    if not (190 <= wc <= 270):
        print(f"WARNING: abstract word count {wc} outside ~200–250 band")

    story.append(Spacer(1, 4))
    story.append(key_findings_box())

    story.append(PageBreak())
    story.append(P("2. Background: why outlining lumps on ultrasound matters", "H1R"))
    story.append(
        P(
            "Breast ultrasound uses high-frequency sound waves to form a live picture of breast "
            "tissue. Clinicians often add ultrasound after a mammogram or a physical exam when they "
            "need a closer look at a mass, especially in dense breasts where X-ray contrast is "
            "limited (Mendelson et al., ACR BI-RADS Ultrasound, 2013). For a patient, the practical "
            "questions are simple: Is there a lump? How large is it? Does it look more concerning or "
            "more reassuring? Those answers influence biopsy decisions and, later, surgical planning."
        )
    )
    story.append(
        P(
            "Outlining a lump — drawing its boundary on the image — is the spatial version of that "
            "conversation. A careful outline supports size estimates, shape descriptors used in "
            "Breast Imaging Reporting and Data System (BI-RADS) language, and communication among "
            "radiologists, surgeons, and patients. Automated outlining is attractive for education "
            "and research because public datasets now include expert masks. It is also easy to "
            "over-claim: a computer outline is not a surgical margin, an imaging diameter is not "
            "pathologic tumor stage, and a model score is not a BI-RADS assessment category "
            "(Moran et al., SSO–ASTRO margin guideline, 2014)."
        )
    )
    story.append(
        P(
            "This project asks a narrower, honest question suitable for a student portfolio: can a "
            "small model outline lesions in the browser, and do the published numbers survive "
            "outside the training hospital’s pictures? The site pairs the demo with BI-RADS context "
            "and a surgeon’s-view page so readers see what the numbers do not mean."
        )
    )
    story.append(
        P(
            "From a patient’s point of view, an outline is a picture of extent: how much of the "
            "frame looks abnormal, and whether the edge looks smooth or irregular. Surgeons later "
            "care about margins in tissue, not pixels, which is why this write-up repeatedly "
            "separates imaging size from pathologic stage. From a student’s point of view, the "
            "same outline is a measurable prediction that can be scored, stress-tested on outside "
            "hospitals, and shipped in a browser so anyone can see the failure modes without "
            "installing a machine-learning stack."
        )
    )

    story.append(P("3. Related work", "H1R"))
    story.append(
        P(
            "U-Net-style encoder–decoder networks remain a default for biomedical segmentation "
            "(Ronneberger et al., 2015). On the Breast Ultrasound Images (BUSI) dataset, recent "
            "papers report a wide range of scores depending on how train and test pictures are "
            "chosen, whether near-identical photos are removed, and whether pictures without lumps "
            "are included. UNeXt (Valanarasu & Patel, MICCAI 2022) reports F1 about 0.79 and "
            "intersection-over-union (IoU) about 0.67 on an 80–20 mix of harmless and cancerous BUSI "
            "frames at 256×256 — a useful context number, but not an apples-to-apples match for this "
            "project’s near-identical photo grouping and per-image outline-overlap score. Musah et "
            "al. (2025) show that BUSI scores fall after de-duplication and fall further when a "
            "BUSI-trained model is tested on BrEaST (reported Dice about 0.49 in their setting). "
            "Pawłowska et al. (2023) document roughly 235 duplicated BUSI images (~19%), which is "
            "why this project groups near-identical photos before splitting."
        )
    )
    story.append(
        P(
            f"This work’s browser model reaches outline-overlap score **{nums['INT8_DICE']}** "
            f"(on images that contain a lump, **{nums['INT8_LESION_DICE']}**) on its own test set, "
            f"and outside outline-overlap scores **{nums['BUSBRA_DICE']}** (BUS-BRA), "
            f"**{nums['BREAST_DICE']}** (BrEaST), and **{nums['BUSUCLM_LESION_DICE']}** on BUS-UCLM "
            f"images that contain a lump. Area under the curve for telling harmless from cancerous "
            f"lumps drops from **{nums['INT8_AUC']}** at home to **{nums['BUSBRA_AUC']}** / "
            f"**{nums['BREAST_AUC']}** / **{nums['BUSUCLM_AUC']}** outside — the same direction "
            f"Wang (2026) reports under dataset shift. Published tables are context, not a "
            f"leaderboard; method differences dominate small score gaps. Full row-by-row notes live "
            f"in the project’s literature-comparison document."
        )
    )
    story.append(
        P(
            "Positioning matters as much as the table. This is not a claim to beat UNeXt or "
            "nnU-Net on a public leaderboard. It is a claim that a single frozen browser artifact "
            "has internal scores, external scores, cleaning experiments, and a written rule for "
            "when the artifact may change — and that those pieces are visible next to the demo."
        )
    )
    story.append(
        table(
            ["Paper / setting", "Split & notes", "Reported figure", "How it compares here"],
            [
                [
                    "This work v1.0.0 served",
                    f"BUSI own test n={nums['N_TEST']}",
                    f"Outline-overlap {nums['INT8_DICE']}; with lump {nums['INT8_LESION_DICE']}; AUC {nums['INT8_AUC']}",
                    "Reference row",
                ],
                [
                    "This work outside hospitals",
                    "Frozen weights; no retune",
                    f"BUS-BRA {nums['BUSBRA_DICE']}; BrEaST {nums['BREAST_DICE']}; BUS-UCLM with lump {nums['BUSUCLM_LESION_DICE']}",
                    "Transfer check",
                ],
                [
                    "Valanarasu & Patel, UNeXt (2022)",
                    "BUSI B+M; 80–20 mix; 256²",
                    "F1 ≈ 0.79; IoU ≈ 0.67",
                    "Partly comparable (different split and aggregation)",
                ],
                [
                    "Musah et al. (2025)",
                    "BUSI→BrEaST OOD among other settings",
                    "BUSI→BrEaST Dice ≈ 0.49 in their setting",
                    "Same OOD direction; different model/resolution",
                ],
                [
                    "Pawłowska et al. (2023)",
                    "BUSI audit",
                    "~235 duplicates (~19%)",
                    "Motivation for near-duplicate grouping",
                ],
            ],
            col_widths=[1.55 * inch, 1.55 * inch, 1.9 * inch, 1.9 * inch],
        )
    )
    story.append(
        P(
            "Takeaway: published BUSI scores are easy to misread unless the split and metric "
            "definition match; this project optimizes for honest transfer reporting, not a "
            "leaderboard win.",
            "Cap",
        )
    )

    story.append(PageBreak())
    story.append(P("4. Data", "H1R"))
    story.append(
        P(
            f"Four public breast-ultrasound collections are used. BUSI is the training and internal "
            f"test source. BUS-BRA, BrEaST, and BUS-UCLM are external checks of the frozen served "
            f"model with no threshold retuning. BUSI provides no patient identifiers; the other three "
            f"do. Annotation marks (calipers, text overlays) were flagged heuristically on "
            f"**{nums['ANNOTATION_RATE']}** of BUSI frames ({nums['N_FLAGGED']} / {nums['N_TOTAL']}). "
            f"Perceptual near-duplicate grouping produced **{nums['N_DUP_GROUPS']}** groups, with "
            f"**{nums['N_MULTI_DUP']}** images in multi-member groups."
        )
    )
    story.append(
        table(
            ["Dataset", "Images", "Patients", "Source country", "Scanner notes", "License", "Excluded / notes"],
            [
                [
                    "BUSI (Al-Dhabyani et al., 2020)",
                    nums["N_TOTAL"],
                    "Not published",
                    "Egypt (Baheya / Cairo University collection)",
                    "Clinical ultrasound archive; device mix not standardized in the release",
                    "Citation required; full-archive redistribution rights unclear — not redistributed here",
                    "Multi-mask lesions OR-merged; near-duplicate groups kept intact across splits",
                ],
                [
                    "BUS-BRA (Gómez-Flores et al., 2024)",
                    nums["BUSBRA_N"],
                    nums["BUSBRA_NP"],
                    "Brazil",
                    "GE Logiq 5/7, Toshiba Aplio 300, U-Systems (device field in release)",
                    "Creative Commons Attribution 4.0 (Zenodo)",
                    "No normal class in this release; used as external test of frozen weights",
                ],
                [
                    "BrEaST (Pawłowska et al., 2024)",
                    nums["BREAST_N"],
                    nums["BREAST_NP"],
                    "Poland",
                    "Clinical scanners with physical pixel size in metadata",
                    "Creative Commons Attribution 4.0 (TCIA)",
                    "Freehand tumour masks; few normals; used as external test",
                ],
                [
                    "BUS-UCLM (Vallez et al., 2025)",
                    nums["BUSUCLM_N"],
                    nums["BUSUCLM_NP"],
                    "Spain (Castilla-La Mancha)",
                    "Siemens ACUSON S2000",
                    "Creative Commons Attribution 4.0 (Mendeley)",
                    "43 Doppler/combined frames excluded; images scored locally, not redistributed",
                ],
            ],
            col_widths=[1.15 * inch, 0.7 * inch, 0.75 * inch, 1.05 * inch, 1.2 * inch, 1.05 * inch, 1.2 * inch],
        )
    )
    story.append(
        P(
            "Takeaway: four public collections from different countries and scanners; only BUSI "
            "trains the published model, and BUS-UCLM drops Doppler/combined frames before scoring.",
            "Cap",
        )
    )
    story.append(
        P(
            "Sources: dataset papers cited above; counts from committed results JSON "
            "(cleaning_experiment.json; external busbra/breast/busuclm.json).",
            "Cap",
        )
    )
    story.append(P(nums["BUSUCLM_SENTENCE"]))
    story.append(
        P(
            f"Split sizes after keeping near-identical photo groups together: train "
            f"{nums['N_TRAIN']}, validation {nums['N_VAL']}, test {nums['N_TEST']}."
        )
    )

    story.append(PageBreak())
    story.append(P("5. Methods", "H1R"))
    story.append(P("5.1 Pipeline overview", "H2R"))
    story.append(
        P(
            "Figure 1 summarizes the path from public images to browser scores. Every served number "
            "on the site is produced by regenerating metrics from committed results files so the "
            "demo and the write-up cannot silently diverge."
        )
    )
    story.append(fig("pipeline", width=6.8 * inch, aspect=0.42))
    story.append(
        P(
            "Takeaway: images are cleaned and grouped, a compact model is trained, shrunk for "
            "browser download, thresholded, then scored on the project’s own test images and on "
            "outside hospitals.",
            "Cap",
        )
    )

    story.append(P("5.2 Preprocessing", "H2R"))
    story.append(
        P(
            "Each image is loaded as red–green–blue, resized to 160×160 with a shared half-pixel-"
            "center bilinear resize (identical in Python evaluation and in the browser), scaled to "
            "[0, 1], and normalized with ImageNet channel means and standard deviations. Expert "
            "masks are resized with nearest-neighbour interpolation and binarized; when a lesion has "
            "several mask files they are combined with a logical OR so any marked region counts."
        )
    )

    story.append(P("5.3 Near-duplicate grouping", "H2R"))
    story.append(
        P(
            "Because BUSI does not publish patient identifiers, near-identical frames can otherwise "
            "appear in both training and testing. Frames are grouped with a perceptual hash so that "
            "an entire near-duplicate group stays on one side of each split. That does not prove "
            "zero leakage — only that the obvious near-copies are not split apart."
        )
    )

    story.append(P("5.4 Model, explained intuitively", "H2R"))
    story.append(
        P(
            "The network is a compact encoder–decoder in the U-Net family (Ronneberger et al., 2015) "
            "with a ResNet-18 ImageNet encoder (He et al., 2016). Intuitively, the encoder compresses "
            "the ultrasound into a smaller grid of features; the decoder expands those features back "
            "to a full-size outline map. A second head reads the same compressed features and "
            "outputs a single score for benign versus malignant. Training uses paired image–mask "
            "augmentations, stratified grouped splits, and checkpoint selection on lesion "
            "outline-overlap score on the validation set."
        )
    )

    story.append(P("5.5 Shrinking the model for the browser", "H2R"))
    story.append(
        P(
            f"The full-precision training checkpoint is about **{nums['FP32_MB']}** megabytes. For "
            f"the website it is exported to the Open Neural Network Exchange (ONNX) format and "
            f"dynamically quantized to 8-bit integer weights (often called INT8), yielding a "
            f"**{nums['SERVED_MB']}** MB download. The browser runs that artifact with "
            f"onnxruntime-web (WebAssembly) inside a Web Worker so the page stays responsive. "
            f"Post-processing matches Python evaluation: probability threshold "
            f"**{nums['SEG_THR']}** and minimum connected-component area **{nums['MIN_AREA']}** "
            f"pixels."
        )
    )

    story.append(P("5.6 Threshold choice", "H2R"))
    story.append(
        P(
            f"The outline threshold **{nums['SEG_THR']}** and minimum area **{nums['MIN_AREA']}** "
            f"were chosen on BUSI validation lesion outline-overlap score and then frozen. External "
            f"sets reuse the same operating point with no retuning — an intentional honesty choice "
            f"that can look worse than a tuned baseline but answers the transfer question readers "
            f"actually care about."
        )
    )

    story.append(P("5.7 Training details in brief", "H2R"))
    story.append(
        P(
            f"Training uses the grouped BUSI split (train {nums['N_TRAIN']}, validation "
            f"{nums['N_VAL']}, test {nums['N_TEST']}). The optimization target emphasizes overlap "
            f"with expert masks; the classification head is trained jointly so the same backbone "
            f"supports both outlining and telling harmless from cancerous lumps. Checkpoints are "
            f"picked by validation outline-overlap on images that contain a lump, not by hunting "
            f"for the best final test number after the fact. The served fingerprint (sha256 prefix "
            f"{nums['MODEL_SHA8']}…) is the artifact evaluated everywhere in this write-up unless a "
            f"section explicitly names a later retrain experiment."
        )
    )
    story.append(
        P(
            "Evaluation code paths are shared: the same resize, normalization, threshold, and "
            "minimum-area filter run in Python metrics and in the browser worker. That parity is "
            "why the Results page can honestly say the site numbers are the served-model numbers, "
            "not a prettier training checkpoint left behind in a notebook."
        )
    )

    story.append(PageBreak())
    story.append(P("6. Results", "H1R"))
    story.append(P("6.1 Results on the project’s own test images", "H2R"))
    story.append(
        P(
            f"Table 2 compares the full-precision training checkpoint with the browser version on "
            f"the same test images (n={nums['N_TEST']}), kept apart from training by near-identical "
            f"photo grouping. Overall outline-overlap scores are close (**{nums['FP32_DICE']}** vs "
            f"**{nums['INT8_DICE']}**). On images that contain a lump, the scores are "
            f"**{nums['FP32_LESION_DICE']}** vs **{nums['INT8_LESION_DICE']}**. Per-class browser "
            f"scores: harmless lumps **{nums['INT8_BENIGN_DICE']}** (n={nums['INT8_BENIGN_N']}), "
            f"cancerous lumps **{nums['INT8_MALIG_DICE']}** (n={nums['INT8_MALIG_N']}). Pictures "
            f"without lumps remain hard: non-empty predicted outlines on **{nums['INT8_NFP']}** "
            f"normals."
        )
    )
    story.append(
        table(
            ["Metric", "Full-precision training", "Served browser model"],
            [
                ["Outline-overlap score (all)", nums["FP32_DICE"], nums["INT8_DICE"]],
                ["Outline-overlap (images with a lump)", nums["FP32_LESION_DICE"], nums["INT8_LESION_DICE"]],
                ["Intersection-over-union (IoU)", nums["FP32_IOU"], nums["INT8_IOU"]],
                ["AUC (telling harmless from cancerous)", nums["FP32_AUC"], nums["INT8_AUC"]],
                [
                    "Sensitivity / Specificity",
                    f"{nums['FP32_SENS']} / {nums['FP32_SPEC']}",
                    f"{nums['INT8_SENS']} / {nums['INT8_SPEC']}",
                ],
                ["Expected calibration error (ECE)", nums["FP32_ECE"], nums["INT8_ECE"]],
                ["False outlines on normals", nums["FP32_NFP"], nums["INT8_NFP"]],
            ],
        )
    )
    story.append(
        P(
            "Takeaway: shrinking the model for the browser barely changes outline quality on the "
            "project’s own test images; empty/normal pictures are still the weak spot.",
            "Cap",
        )
    )
    story.append(P("Sources: results/full_run.json, results/served_int8_test.json.", "Cap"))
    story.append(fig("dice_hist"))
    story.append(
        P(
            "Takeaway: most of the project’s own test cases land at high outline-overlap scores, "
            "with a long left tail of hard misses and false outlines on normals.",
            "Cap",
        )
    )

    story.append(P("6.2 Results on outside hospitals", "H2R"))
    story.append(
        P(
            f"The same frozen browser model was scored without retuning on BUS-BRA "
            f"(n={nums['BUSBRA_N']}, {nums['BUSBRA_NP']} patients), BrEaST (n={nums['BREAST_N']}, "
            f"{nums['BREAST_NP']} patients), and BUS-UCLM (n={nums['BUSUCLM_N']}, "
            f"{nums['BUSUCLM_NP']} patients). Per-class outline-overlap scores: BUS-BRA harmless "
            f"**{nums['BUSBRA_BENIGN_DICE']}** / cancerous **{nums['BUSBRA_MALIG_DICE']}**; BrEaST "
            f"harmless **{nums['BREAST_BENIGN_DICE']}** / cancerous **{nums['BREAST_MALIG_DICE']}**; "
            f"BUS-UCLM harmless **{nums['BUSUCLM_BENIGN_DICE']}** / cancerous "
            f"**{nums['BUSUCLM_MALIG_DICE']}**."
        )
    )
    story.append(
        table(
            ["Set", "Outline-overlap", "Images with a lump", "AUC"],
            [
                ["BUSI (own test)", nums["INT8_DICE"], nums["INT8_LESION_DICE"], nums["INT8_AUC"]],
                ["BUS-BRA", nums["BUSBRA_DICE"], nums["BUSBRA_LESION_DICE"], nums["BUSBRA_AUC"]],
                ["BrEaST", nums["BREAST_DICE"], nums["BREAST_LESION_DICE"], nums["BREAST_AUC"]],
                ["BUS-UCLM", nums["BUSUCLM_DICE"], nums["BUSUCLM_LESION_DICE"], nums["BUSUCLM_AUC"]],
            ],
        )
    )
    story.append(
        P(
            "Takeaway: outlines travel better than telling harmless from cancerous lumps; "
            f"BUS-UCLM’s overall figure is dragged down by false outlines on normals "
            f"({nums['BUSUCLM_NFP']}).",
            "Cap",
        )
    )
    story.append(
        P(
            "Sources: results/external/busbra.json, breast.json, busuclm.json.",
            "Cap",
        )
    )
    story.append(fig("roc"))
    story.append(
        P(
            "Takeaway: the curve that separates benign from malignant looks strong on BUSI and "
            "weaker once the hospital and scanner change.",
            "Cap",
        )
    )
    story.append(fig("cal"))
    story.append(
        P(
            f"Takeaway: predicted cancer probabilities are only roughly aligned with observed rates "
            f"(ECE {nums['INT8_ECE']}) — confidence should be read cautiously.",
            "Cap",
        )
    )

    story.append(PageBreak())
    story.append(P("6.3 Checking for near-identical photos", "H2R"))
    story.append(
        P(
            f"A short training schedule ({nums['LEAK_EPOCHS']} epochs × seeds {nums['LEAK_SEEDS']}) "
            f"compared keeping near-identical photos together versus mixing them across train and "
            f"check sets, then scored both on the same careful test set. Checking for near-identical "
            f"photos showed they did not inflate the scores (difference about "
            f"**{nums['LEAK_DELTA']}**). Risk remains because patient identifiers are absent and "
            f"near-copies are documented in the literature."
        )
    )
    story.append(fig("leak"))
    story.append(
        P(
            "Takeaway: on this short check, mixing near-identical photos did not inflate check-set "
            "scores — but missing patient IDs are still a reason for caution.",
            "Cap",
        )
    )
    story.append(P("Source: results/leakage_ablation.json.", "Cap"))

    story.append(P("6.4 Measurement-mark experiments", "H2R"))
    story.append(
        P(
            f"Images with burned-in measurement marks often look easier: marked-frame "
            f"outline-overlap score **{nums['EA_FLAGGED']}** versus unmarked **{nums['EA_CLEAN']}**. "
            f"Erasing markers on the original test moved overall score from "
            f"{nums['EA_ORIG_DICE']} to {nums['EA_INP_DICE']} and did **not** close that gap. "
            f"Retraining with erased marks produced outside scores BUS-BRA {nums['EC_BUSBRA']} and "
            f"BrEaST {nums['EC_BREAST']}, with unmarked-image score {nums['EC_CLEAN']} and AUC "
            f"{nums['EC_AUC']} — not enough to replace served v{nums['MODEL_VERSION']} under the "
            f"written replacement criteria."
        )
    )
    story.append(fig("caliper", width=5.8 * inch, aspect=0.52))
    story.append(
        P(
            "Takeaway: measurement marks can act as shortcuts; simply erasing them on test images "
            "does not automatically make hard unmarked cases easy.",
            "Cap",
        )
    )

    story.append(P("6.5 When the outline stays stable under flips", "H2R"))
    story.append(
        P(
            f"Test-time augmentation (TTA) flips and mild transforms are run offline; disagreement "
            f"across those views is treated as an uncertainty signal. Spearman correlation between "
            f"disagreement and 1−Dice is **{nums['UNCERT_RHO']}** on the BUSI test "
            f"(n={nums['UNCERT_N']}). Keeping the most certain 80% of cases raises mean "
            f"outline-overlap score to **{nums['UNCERT_COV80']}**. Interpretation: agreement under "
            f"flips — not a calibrated probability of being wrong."
        )
    )
    story.append(fig("uncert"))
    story.append(
        P(
            "Takeaway: when the outline stays stable under flips, errors are less common — useful "
            "as a research triage signal, not as a clinical confidence meter.",
            "Cap",
        )
    )

    story.append(P("6.6 Size agreement with experts (BrEaST)", "H2R"))
    story.append(
        P(
            f"On BrEaST, model versus expert longest diameter (mm) shows Pearson correlation proxy "
            f"**{nums['MEAS_DIAM_R']}** (n={nums['MEAS_N']}); area correlation proxy "
            f"**{nums['MEAS_AREA_R']}**; disagreement at a 20 mm threshold occurs on about "
            f"**{nums['MEAS_T1T2']}** of cases. Research only — imaging size is not pathologic "
            f"T-stage."
        )
    )

    story.append(PageBreak())
    story.append(P("6.7 A later retrain, and why the original stayed", "H2R"))
    story.append(
        P(
            f"A later candidate trained on BUSI plus BUS-BRA (larger backbone, 256×256, stronger "
            f"augmentation) was compared with served v{nums['MODEL_VERSION']} under written "
            f"replacement criteria set beforehand. Average outline-overlap on unmarked test images "
            f"was **{nums['V2_CLEAN_MEAN']}** versus v1 **{nums['V1_CLEAN']}** (difference "
            f"**{nums['V2_CLEAN_DELTA']}**). BUS-BRA images from the same source rose to "
            f"**{nums['V2_BUSBRA_MEAN']}**, and truly outside BrEaST to **{nums['V2_BREAST_MEAN']}**, "
            f"with AUC **{nums['V2_AUC_MEAN']}** and packaged size about **{nums['V2_INT8_MB']}** MB. "
            f"A retrained version did better on some outside images but not consistently, so the "
            f"original stays (v{nums['MODEL_VERSION']}); the comparison is published as an experiment."
        )
    )
    story.append(
        P(
            "Takeaway: a flashier chart on one check set is not enough; the published model only "
            "changes when every pre-agreed gate passes on the average across training seeds.",
            "Cap",
        )
    )
    story.append(P("Source: results/v2_experiment.json.", "Cap"))

    story.append(P("7. Where the model goes wrong", "H1R"))
    story.append(
        P(
            f"The Model Errors explorer on the site lists **{nums['ERR_N']}** hard test cases from "
            f"the project’s own collection as outline-only silhouettes (BUSI ultrasound pixels "
            f"withheld because redistribution rights are unclear). Category counts: boundary "
            f"disagreement **{nums['ERR_BOUNDARY']}**, false lump on a normal picture "
            f"**{nums['ERR_FP_NORMAL']}**, wrong class **{nums['ERR_WRONG_CLS']}**, missed lump "
            f"**{nums['ERR_MISSED']}**, over-segmentation **{nums['ERR_OVER']}**, under-segmentation "
            f"**{nums['ERR_UNDER']}**. Boundary disagreements dominate; false outlines on normals "
            f"remain the most intuitive failure mode for a triage-style demo."
        )
    )
    story.append(fig("fail", width=5.8 * inch, aspect=0.70))
    story.append(
        P(
            "Takeaway: silhouette cards make misses visible without redistributing BUSI pixels — "
            "most hard cases are boundary fights, not total collapses.",
            "Cap",
        )
    )

    story.append(P("8. Discussion: what the numbers mean in practice", "H1R"))
    story.append(
        P(
            f"An outline-overlap score near **{nums['INT8_DICE']}** on the project’s own test images "
            f"means that, on average, the computer outline and the expert outline share most of "
            f"their area — useful for a demo and for learning what these scores feel like, not for "
            f"claiming radiologist parity. Outside outline scores in the 0.63–0.71 range suggest "
            f"drawing the boundary travels better than telling harmless from cancerous lumps, which "
            f"falls when scanners and labeling habits change. That pattern matches the broader "
            f"literature on dataset shift."
        )
    )
    story.append(
        P(
            f"Normal false positives ({nums['INT8_NFP']} on BUSI; {nums['BUSUCLM_NFP']} on BUS-UCLM) "
            f"are the practical warning label: a browser demo that “finds” a lump on a healthy-looking "
            f"frame can mislead a casual reader faster than a slightly jagged outline on a true mass. "
            f"Calibration (ECE {nums['INT8_ECE']}) is imperfect, so verbal confidence cues are "
            f"intentionally subdued on the site."
        )
    )
    story.append(
        P(
            f"Readers comparing this project with published BUSI leaderboards should weight method "
            f"first. Many papers mix near-identical photos across train and test; this project keeps "
            f"those groups together, reports the browser download ({nums['SERVED_MB']} MB), and "
            f"publishes outside-hospital numbers without retuning. A higher home-set score under a "
            f"leakier setup is not a stronger scientific claim than a slightly lower score under a "
            f"stricter one."
        )
    )
    story.append(
        P(
            f"Keeping the original model is part of the result, not something to hide. BUS-BRA "
            f"scores on the same-source check set rose to about {nums['V2_BUSBRA_MEAN']}, and "
            f"BrEaST to about {nums['V2_BREAST_MEAN']}, yet the unmarked-image average "
            f"({nums['V2_CLEAN_MEAN']} vs v1 {nums['V1_CLEAN']}) did not clear the bar written "
            f"beforehand. Setting that bar before seeing the average is how a student project stays "
            f"honest when a larger model looks tempting on a chart."
        )
    )
    story.append(
        P(
            "For admissions readers and scientifically literate parents, the portfolio claim is "
            "process honesty: careful train/test grouping, frozen outside tests, written "
            "replacement criteria that refused a flashy upgrade, and a downloadable write-up whose "
            "figures are locked to committed JSON."
        )
    )

    story.append(P("9. Limitations", "H1R"))
    story.append(
        P(
            "Several constraints bound how far these numbers should travel outside a research demo:"
        )
    )
    for bullet in [
        "No patient identifiers on BUSI → residual risk from near-identical photos despite perceptual grouping.",
        f"Domain shift: classification AUC drops from {nums['INT8_AUC']} internally to as low as {nums['BUSBRA_AUC']} on BUS-BRA.",
        "Calipers and on-screen text may still act as shortcuts on annotated frames.",
        f"160×160 resolution loses fine boundary detail; normal-image false positives remain ({nums['INT8_NFP']}).",
        "Single-author student project without clinical validation; not a medical device.",
        "A model score is not a BI-RADS category; imaging size is not surgical staging.",
        "External BUS-UCLM images were scored locally and are not redistributed with the site.",
    ]:
        story.append(P("• " + bullet, "BulletR"))

    story.append(P("10. Ethics and responsible use", "H1R"))
    story.append(
        P(
            "Code is released under the MIT license. The full BUSI archive is not redistributed "
            "(redistribution rights are unclear); users must obtain it themselves and cite "
            "Al-Dhabyani et al. (2020). External demo imagery uses Creative Commons Attribution "
            "collections with credit. The site uses no analytics or cookies; Demo images are "
            "processed in the browser only and are not uploaded to a server. This write-up and the "
            "live demo are educational research materials. They must not be used for diagnosis, "
            "triage, screening, or any care decision. No clinician reviewed this project for "
            "clinical deployment, and none is claimed."
        )
    )

    story.append(P("11. Future work", "H1R"))
    story.append(
        P(
            "Natural next steps, if pursued, include stronger normal-vs-lesion rejection, "
            "patient-level collections with clearer licenses, higher-resolution models that still "
            "fit a browser budget, and uncertainty displays that a non-specialist can interpret "
            "without over-trust. Any promoted weight file would need a new version number and a "
            "fresh pass of the written replacement criteria."
        )
    )
    story.append(
        P(
            "A second thread of future work is communication: shorter silhouette cards that teach "
            "error types, clearer captions for parents who are not engineers, and printable "
            "one-pagers that keep the same locked numbers as this PDF. None of those changes "
            "should quietly retune thresholds on external data."
        )
    )

    story.append(P("12. Reproducibility", "H1R"))
    story.append(
        P(
            f"Software version {nums['MODEL_VERSION']} is archived with DOI {nums['DOI_URL']}. "
            f"To regenerate this PDF: install Python dependencies (reportlab, pypdf, matplotlib), "
            f"run the report builder script from the repository root, then run the drift check so "
            f"every locked number still appears in the PDF text. Paper metrics are exported from the "
            f"same results JSON into LaTeX macros. Served artifact fingerprint (sha256 prefix): "
            f"{nums['MODEL_SHA8']}… · packaged size {nums['SERVED_MB']} MB. Typical software stack "
            f"for regeneration: Python 3.10+, Node.js 20+ for the web app, onnxruntime / "
            f"onnxruntime-web for model execution. Exact pinned versions live in the repository "
            f"lockfiles on the tagged release."
        )
    )

    story.append(P("13. AI-use disclosure", "H1R"))
    story.append(P(nums["HOW_BUILT"]))

    story.append(PageBreak())
    story.append(P("14. Glossary", "H1R"))
    glossary = [
        (
            "Outline-overlap score (Dice)",
            "A number from 0 to 1 describing how much the computer outline and the expert outline "
            "overlap. Twice the shared area divided by the sum of both areas; 1 is a perfect match.",
        ),
        (
            "Intersection-over-union (IoU)",
            "Shared outline area divided by the area of either outline. Related to Dice; usually a "
            "little lower than Dice for the same pair of outlines.",
        ),
        (
            "Area under the curve (AUC)",
            "A summary of how well a score ranks cancerous cases above benign ones across all "
            "thresholds. 0.5 is chance; 1.0 is perfect ranking.",
        ),
        (
            "Sensitivity / Specificity",
            "Sensitivity is the share of truly cancerous cases the score catches at a chosen "
            "threshold; specificity is the share of truly benign cases it correctly leaves below "
            "that threshold.",
        ),
        (
            "Calibration / expected calibration error (ECE)",
            "Whether a predicted probability (for example “70% malignant”) matches how often such "
            "cases are actually malignant. ECE summarizes the mismatch across probability bins.",
        ),
        (
            "BI-RADS",
            "Breast Imaging Reporting and Data System — a standard lexicon and assessment "
            "categories radiologists use. A model score is not a BI-RADS category.",
        ),
        (
            "U-Net",
            "A widely used neural-network shape for image outlining: a compressing path, an "
            "expanding path, and skip connections that preserve spatial detail.",
        ),
        (
            "ONNX",
            "Open Neural Network Exchange — a portable file format for trained models so the same "
            "weights can run in Python and in the browser.",
        ),
        (
            "Quantization (INT8)",
            "Storing weights with 8-bit integers instead of 32-bit floats to shrink download size "
            "and speed inference, with small metric changes when done carefully.",
        ),
        (
            "Test-time augmentation (TTA)",
            "Running the model on flipped or lightly altered copies of the same image and "
            "measuring how much the outlines disagree — used here as an uncertainty signal.",
        ),
        (
            "External validation",
            "Scoring a frozen model on data from other hospitals or collections without retuning, "
            "to test whether results were specific to the training source.",
        ),
        (
            "Data leakage",
            "Accidental overlap between training and test information (for example near-duplicate "
            "frames on both sides) that makes scores look better than true generalization.",
        ),
    ]
    for term, defn in glossary:
        story.append(KeepTogether([P(term, "GlossTerm"), P(defn, "GlossDef"), Spacer(1, 4)]))

    story.append(PageBreak())
    story.append(P("15. References", "H1R"))
    story.append(
        P(
            "Citations below support the clinical framing, datasets, model family, and "
            "software archive. Prefer the dataset papers when quoting collection size or license."
        )
    )
    refs = [
        "Al-Dhabyani W, Gomaa M, Khaled H, Fahmy A. Dataset of breast ultrasound images. Data in Brief. 2020;28:104863.",
        "Mendelson EB, Böhm-Vélez M, Berg WA, et al. ACR BI-RADS® Ultrasound. In: ACR BI-RADS® Atlas. Reston, VA: American College of Radiology; 2013.",
        "Ronneberger O, Fischer P, Brox T. U-Net: Convolutional networks for biomedical image segmentation. MICCAI. 2015.",
        "He K, Zhang X, Ren S, Sun J. Deep residual learning for image recognition. CVPR. 2016.",
        "Gómez-Flores W, et al. BUS-BRA: A breast ultrasound dataset for assessing computer-aided diagnosis systems. Medical Physics. 2024;51:3110–3123. Zenodo CC BY 4.0.",
        "Pawłowska A, et al. A curated benchmark dataset for ultrasound-based breast lesion analysis (BrEaST). Scientific Data. 2024;11:148. TCIA CC BY 4.0.",
        "Pawłowska A, et al. Letter commenting on BUSI quality issues and duplicates. Data in Brief / related commentary. 2023.",
        "Vallez N, et al. BUS-UCLM: Breast ultrasound dataset from the University of Castilla-La Mancha. Scientific Data. 2025;12:242. Mendeley CC BY 4.0.",
        "Valanarasu JMJ, Patel VM. UNeXt: MLP-based rapid medical image segmentation network. MICCAI. 2022.",
        "Musah et al. On de-duplication and out-of-distribution breast ultrasound segmentation. arXiv:2508.17768. 2025.",
        "Wang L. Classification performance under dataset shift in breast ultrasound. Diagnostics. 2026;16(10):1537.",
        "Moran MS, et al. Society of Surgical Oncology–American Society for Radiation Oncology consensus guideline on margins for breast-conserving surgery. 2014.",
        f"Fadnavis S. Breast Ultrasound Lesion Segmentation (Version {nums['MODEL_VERSION']}). Zenodo; 2026. {nums['DOI_URL']}",
        f"Project repository: {nums['GITHUB_URL']}",
    ]
    for i, r in enumerate(refs, 1):
        story.append(P(f"{i}. {r}", "RefR"))

    story.append(Spacer(1, 10))
    story.append(
        P(
            "Numbers in this PDF are auto-filled from committed results JSON by the report builder. "
            "A continuous-integration check fails if PDF figures drift from those JSON files.",
            "Cap",
        )
    )

    md = f"""# Breast Ultrasound Lesion Segmentation: Research Write-up

Version {nums['MODEL_VERSION']} · Site-only research report  
Author: Surabhi Fadnavis (high-school senior, Georgia)

> Research demo — not for clinical use.

## Abstract
{plain_abstract(nums)}

## Data
Annotation-flag rate {nums['ANNOTATION_RATE']} ({nums['N_FLAGGED']}/{nums['N_TOTAL']}).
{nums['BUSUCLM_SENTENCE']}
External: BUS-BRA n={nums['BUSBRA_N']}; BrEaST n={nums['BREAST_N']} (Pawłowska et al.).

## Results highlights
Leakage Δ {nums['LEAK_DELTA']}; E-a flagged/clean {nums['EA_FLAGGED']}/{nums['EA_CLEAN']}; E-c external {nums['EC_BUSBRA']}/{nums['EC_BREAST']}; TTA ρ {nums['UNCERT_RHO']}; cov80 {nums['UNCERT_COV80']}; meas diam r {nums['MEAS_DIAM_R']} (n={nums['MEAS_N']}), ≥20mm discordance {nums['MEAS_T1T2']}; v2 clean mean {nums['V2_CLEAN_MEAN']} (Δ {nums['V2_CLEAN_DELTA']}).

## AI-assistance
{nums['HOW_BUILT']}
"""
    FILLED_MD.parent.mkdir(parents=True, exist_ok=True)
    FILLED_MD.write_text(md)

    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT_PDF),
        pagesize=letter,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.65 * inch,
        bottomMargin=0.65 * inch,
        title="Breast Ultrasound Lesion Segmentation — Research Write-up",
        author="Surabhi Fadnavis",
    )
    doc.build(story)


def main() -> int:
    nums = collect_numbers()
    skip = {
        "HOW_BUILT",
        "PAGES_URL",
        "GITHUB_URL",
        "BUSUCLM_SENTENCE",
        "LEAK_SEEDS",
        "MODEL_SHA8",
    }
    expected = {k: v for k, v in nums.items() if k not in skip}
    NUMBERS_JSON.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n")
    write_plain_abstract_ts(nums)
    figs = make_figures()
    build_pdf(nums, figs)

    from pypdf import PdfReader

    reader = PdfReader(str(OUT_PDF))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    if "Paw" not in text and "Pawłowska" not in text:
        if "Pawłowska" not in FILLED_MD.read_text():
            raise SystemExit("Pawłowska missing from filled markdown")
    compact = " ".join(text.split())
    if "BUS-UCLM" not in compact or (
        "requires a login" not in compact
        and "Normal false positives dominate" not in compact
        and "normal false positives dominate" not in compact.lower()
    ):
        # Accept either legacy phrasing or the plain-language sentence
        if "BUS-UCLM" not in compact:
            raise SystemExit("Reader-facing BUS-UCLM sentence missing from PDF text")
        if "lesion outline-overlap score" not in compact.lower() and "requires a login" not in compact:
            raise SystemExit("Reader-facing BUS-UCLM sentence missing from PDF text")
    if "data/external" in text:
        raise SystemExit("Internal data/external path leaked into PDF text")
    if "Pawłowska" not in FILLED_MD.read_text() and "Paw" not in text:
        raise SystemExit("Pawłowska / Paw missing from report")
    offenders = re.findall(r"\bD(?:1[0-7]|[1-9])\b", text)
    if offenders:
        raise SystemExit(f"Decision codes leaked into PDF text: {offenders}")
    for bad in ("n/a", "None/None", "TODO", "NaN"):
        if bad in text:
            raise SystemExit(f"Placeholder {bad!r} found in PDF text")
    if re.search(r"\n—\n", text):
        raise SystemExit("Placeholder em-dash cell found in PDF text")
    if "Key findings in plain English" not in text and "Key findings in plain English" not in compact:
        raise SystemExit("Key findings box missing from PDF")
    if "Glossary" not in text:
        raise SystemExit("Glossary section missing from PDF")
    # Page-1 jargon guard: abstract + key findings
    page1 = text
    if "1. Abstract" in text and "2. Background" in text:
        page1 = text.split("1. Abstract", 1)[1].split("2. Background", 1)[0]
    for banned in (
        "INT8",
        "ONNX",
        "TTA",
        "ECE",
        "pHash",
        "ResNet",
        "U-Net",
        "AUC",
        "swap rule",
        "clean-subset",
        "leakage check",
        "random splits",
        "lesion-only",
        "held-out training-collection",
        "Δ",
    ):
        if banned in page1:
            raise SystemExit(f"Banned jargon {banned!r} found on page-1 abstract/key-findings")
    n_pages = len(reader.pages)
    print(f"Wrote {OUT_PDF} ({OUT_PDF.stat().st_size} bytes, {n_pages} pages)")
    if n_pages < 15 or n_pages > 20:
        raise SystemExit(f"Page count {n_pages} outside 15–20 target band")
    print(f"OK: page count {n_pages} within 15–20")
    abs_wc = len(plain_abstract(nums).split())
    print(f"OK: abstract word count {abs_wc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
