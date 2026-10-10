#!/usr/bin/env python3
"""Build web/public/report.pdf from results JSON + generated figures.

All numeric placeholders are filled from committed JSON. Uses DejaVu fonts so
Unicode (e.g. Pawłowska) renders. Reader-facing text omits internal decision codes.
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_PDF = ROOT / "web" / "public" / "report.pdf"
FILLED_MD = ROOT / "docs" / "report" / "report.filled.md"
NUMBERS_JSON = ROOT / "docs" / "report" / "numbers.json"
FIG_DIR = ROOT / "docs" / "report" / "figures"

FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"

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

    # FP32 training checkpoint metrics are nested under metrics.test in full_run.json
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

    busuclm = (
        "BUS-UCLM was not included because its Mendeley Data download requires a login "
        "(the request returned HTTP 403)."
    )

    dc = clean["dataset_counts"]
    nums = {
        "MODEL_VERSION": "1.0.0",
        "PAGES_URL": "https://surabhif.github.io/Breast-ultrasound-lesion-segmentation/",
        "GITHUB_URL": "https://github.com/surabhif/Breast-ultrasound-lesion-segmentation",
        "HOW_BUILT": HOW_BUILT,
        "SEG_THR": fmt(int8.get("seg_threshold", 0.4), 1, label="seg_threshold"),
        "MIN_AREA": str(int(int8.get("min_component_area", 40))),
        "MODEL_SHA8": str(int8.get("sha256", ""))[:8],
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
        "BUSBRA_DICE": fmt(busbra.get("test_dice"), label="BUS-BRA dice"),
        "BUSBRA_LESION_DICE": fmt(busbra.get("lesion_dice"), label="BUS-BRA lesion dice"),
        "BUSBRA_AUC": fmt(busbra.get("cls_roc_auc"), label="BUS-BRA auc"),
        "BUSBRA_N": str(busbra.get("n")),
        "BUSBRA_NP": str(busbra.get("n_patients")),
        "BREAST_DICE": fmt(breast.get("test_dice"), label="BrEaST dice"),
        "BREAST_LESION_DICE": fmt(breast.get("lesion_dice"), label="BrEaST lesion dice"),
        "BREAST_AUC": fmt(breast.get("cls_roc_auc"), label="BrEaST auc"),
        "BREAST_N": str(breast.get("n")),
        "BREAST_NP": str(breast.get("n_patients")),
        "BUSUCLM_SENTENCE": busuclm,
        "ANNOTATION_RATE": pct(dc["annotation_rate"], label="annotation_rate"),
        "N_FLAGGED": str(dc["n_annotation_flagged"]),
        "N_TOTAL": str(dc["n_total"]),
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
    }
    if "None" in nums["INT8_NFP"] or nums["INT8_NFP"].startswith("/"):
        raise SystemExit(f"Bad INT8_NFP {nums['INT8_NFP']!r}")
    forbidden = ("n/a", "None", "TODO", "NaN", "data/external/")
    for k, v in nums.items():
        if k in ("HOW_BUILT", "PAGES_URL", "GITHUB_URL", "BUSUCLM_SENTENCE"):
            continue
        for bad in forbidden:
            if bad in v:
                raise SystemExit(f"Placeholder {bad!r} in {k}={v!r}")
    return nums


def make_figures() -> dict[str, Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}

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
    ax.set_xlabel("Dice (held-out BUSI test)")
    ax.set_ylabel("Count")
    ax.set_title("Figure 1. Served INT8 Dice distribution")
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
        ax.plot([p["fpr"] for p in roc], [p["tpr"] for p in roc], color=TEAL, lw=2, label=f"BUSI INT8 AUC={fmt(metrics.get('served_int8',{}).get('cls_roc_auc') or metrics.get('metrics',{}).get('cls_roc_auc'))}")
    # external may have roc_curve
    for name, blob, color in [
        ("BUS-BRA", busbra, "#0e0e0e"),
        ("BrEaST", breast, "#c45c26"),
    ]:
        er = blob.get("roc_curve") or []
        if er:
            ax.plot([p["fpr"] for p in er], [p["tpr"] for p in er], color=color, lw=1.6, label=f"{name} AUC={fmt(blob.get('cls_roc_auc'))}")
        else:
            # mark AUC as horizontal legend-only note
            ax.plot([], [], color=color, label=f"{name} AUC={fmt(blob.get('cls_roc_auc'))} (curve not stored)")
    ax.plot([0, 1], [0, 1], "k--", lw=0.8, alpha=0.5)
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("Figure 2. Classification ROC (internal vs external)")
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
    ax.set_title("Figure 3. Calibration (BUSI INT8)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    paths["cal"] = FIG_DIR / "fig_calibration.png"
    fig.savefig(paths["cal"])
    plt.close(fig)

    # Leakage ablation
    leak = load(ROOT / "results" / "leakage_ablation.json")
    fig, ax = plt.subplots(figsize=(5.2, 3.2), dpi=140)
    modes = {}
    for r in leak.get("runs") or []:
        modes.setdefault(r["mode"], []).append(r.get("val_dice") or r.get("test_dice"))
    labels = list(modes.keys())
    means = [sum(v) / len(v) for v in modes.values()]
    stds = [float(np.std(v)) if len(v) > 1 else 0 for v in modes.values()]
    ax.bar(labels, means, yerr=stds, color=[TEAL, "#89b2b2"][: len(labels)], edgecolor="white", capsize=4)
    ax.set_ylabel("Validation Dice")
    ax.set_title("Figure 4. Leakage ablation (grouped vs random)")
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
    fig.suptitle("Figure 5. Caliper erase demo (CC BY BrEaST; digitally altered)", fontsize=10)
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
    ax.set_xlabel("TTA disagreement")
    ax.set_ylabel("1 − Dice")
    ax.set_title(f"Figure 6. Uncertainty vs error (Spearman ρ={rho:.3f})")
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
    fig.suptitle("Figure 7. Failure-case outline silhouettes (BUSI; no ultrasound pixels)", fontsize=9)
    fig.tight_layout()
    paths["fail"] = FIG_DIR / "fig_failures.png"
    fig.savefig(paths["fail"])
    plt.close(fig)

    return paths


def build_pdf(nums: dict[str, str], figs: dict[str, Path]) -> None:
    from reportlab.lib.colors import HexColor
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
        ListFlowable,
        ListItem,
    )

    pdfmetrics.registerFont(TTFont("DejaVu", FONT_REG))
    pdfmetrics.registerFont(TTFont("DejaVu-Bold", FONT_BOLD))

    teal = HexColor("#297373")
    ink = HexColor("#0e0e0e")
    muted = HexColor("#5c6b6b")

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleTeal", fontName="DejaVu-Bold", fontSize=15, leading=19, textColor=teal, alignment=TA_CENTER, spaceAfter=8))
    styles.add(ParagraphStyle(name="Meta", fontName="DejaVu", fontSize=9, leading=12, textColor=muted, alignment=TA_CENTER, spaceAfter=4))
    styles.add(ParagraphStyle(name="H1R", fontName="DejaVu-Bold", fontSize=12, leading=15, textColor=teal, spaceBefore=12, spaceAfter=6))
    styles.add(ParagraphStyle(name="H2R", fontName="DejaVu-Bold", fontSize=10.5, leading=13, textColor=ink, spaceBefore=9, spaceAfter=4))
    styles.add(ParagraphStyle(name="BodyR", fontName="DejaVu", fontSize=9.2, leading=12.5, alignment=TA_JUSTIFY, spaceAfter=5))
    styles.add(ParagraphStyle(name="BulletR", fontName="DejaVu", fontSize=9.2, leading=12.5, leftIndent=12, spaceAfter=2))
    styles.add(ParagraphStyle(name="Cap", fontName="DejaVu", fontSize=8, leading=10, textColor=muted, alignment=TA_CENTER, spaceAfter=8, spaceBefore=2))
    styles.add(ParagraphStyle(name="Warn", fontName="DejaVu-Bold", fontSize=9, leading=12, textColor=HexColor("#ffffff"), backColor=teal, borderPadding=6, spaceAfter=10))
    styles.add(ParagraphStyle(name="Cell", fontName="DejaVu", fontSize=8.2, leading=10.5))
    styles.add(ParagraphStyle(name="CellB", fontName="DejaVu-Bold", fontSize=8.2, leading=10.5))

    def P(text: str, style="BodyR"):
        # light markdown
        html = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html)
        html = re.sub(r"`(.+?)`", r"<font face='DejaVu' size='8'>\1</font>", html)
        return Paragraph(html, styles[style])

    def table(headers, rows):
        data = [[Paragraph(h, styles["CellB"]) for h in headers]]
        for r in rows:
            data.append([Paragraph(str(c), styles["Cell"]) for c in r])
        t = Table(data, hAlign="LEFT", colWidths=[1.45 * inch] * len(headers) if len(headers) > 3 else None)
        if len(headers) <= 4:
            widths = [1.7 * inch] + [1.2 * inch] * (len(headers) - 1)
            t = Table(data, hAlign="LEFT", colWidths=widths)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), HexColor("#dfeaea")),
                    ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#89b2b2")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        return t

    def fig(key: str, width=5.6 * inch):
        path = figs[key]
        im = Image(str(path), width=width, height=width * 0.62)
        im.hAlign = "CENTER"
        return im

    story = []
    story.append(P("Breast Ultrasound Lesion Segmentation: Research Write-up", "TitleTeal"))
    story.append(P(f"Version {nums['MODEL_VERSION']} · Site-only research report (not a journal submission)", "Meta"))
    story.append(P("Author: Surabhi Fadnavis (high-school senior, Georgia)", "Meta"))
    story.append(P(f"Live demo: {nums['PAGES_URL']}", "Meta"))
    story.append(P(f"Repository: {nums['GITHUB_URL']}", "Meta"))
    story.append(Spacer(1, 6))
    story.append(P("Research demo — not for clinical use. Not clinician-reviewed. Not for diagnosis, screening, or care decisions.", "Warn"))

    story.append(P("1. Abstract", "H1R"))
    story.append(
        P(
            f"This high-school research project trains a ResNet-18 U-Net with an auxiliary "
            f"benign-vs-malignant head on the BUSI breast ultrasound dataset, exports an INT8 ONNX "
            f"model for fully in-browser inference, and reports honest internal and external metrics. "
            f"On the held-out BUSI test set the **served INT8** model reaches Dice **{nums['INT8_DICE']}** "
            f"(lesion-only **{nums['INT8_LESION_DICE']}**) and ROC-AUC **{nums['INT8_AUC']}**. "
            f"External validation on BUS-BRA and BrEaST keeps segmentation closer to internal Dice "
            f"(**{nums['BUSBRA_DICE']}** / **{nums['BREAST_DICE']}**) while classification AUC drops "
            f"(**{nums['BUSBRA_AUC']}** / **{nums['BREAST_AUC']}**). Cleaning, leakage, caliper-inpainting, "
            f"and TTA uncertainty experiments are included. This write-up is published on the project site only."
        )
    )

    story.append(P("2. Introduction", "H1R"))
    story.append(
        P(
            "Breast ultrasound helps characterize masses, especially in dense breasts. Public datasets "
            "enable student projects but hide pitfalls: near-duplicate frames, burned-in calipers, and "
            "missing patient IDs. This project asks whether a small model can outline lesions in the "
            "browser — and how honest the scores remain under those pitfalls."
        )
    )
    story.append(
        P(
            "Related educational pages on the site cover BI-RADS context (a model score is not a BI-RADS "
            "category) and a surgeon's-view framing of size and margins (imaging size is not pathologic "
            "T-stage; model outlines are not surgical margins)."
        )
    )

    story.append(P("3. Data", "H1R"))
    story.append(P("3.1 BUSI (internal)", "H2R"))
    story.append(
        P(
            f"BUSI (Al-Dhabyani et al., Data in Brief, 2020) provides ~780 PNG ultrasound images labeled "
            f"benign, malignant, or normal with masks. Multi-mask lesions are OR-merged. BUSI publishes "
            f"**no patient IDs**; we group perceptual-hash near-duplicates so groups never cross splits. "
            f"Annotation-flag rate (heuristic): **{nums['ANNOTATION_RATE']}** "
            f"({nums['N_FLAGGED']} / {nums['N_TOTAL']})."
        )
    )
    story.append(P("3.2 External sets", "H2R"))
    story.append(
        P(
            f"Primary external sets follow the pre-registered protocol in "
            f"`docs/EXTERNAL_VALIDATION_PROTOCOL.md`: **BUS-BRA** (Gómez-Flores et al., 2024; Zenodo CC BY 4.0; "
            f"n={nums['BUSBRA_N']}, patients≈{nums['BUSBRA_NP']}) and **BrEaST** (Pawłowska et al., 2024; "
            f"TCIA CC BY 4.0; n={nums['BREAST_N']}, patients={nums['BREAST_NP']})."
        )
    )
    story.append(P(nums["BUSUCLM_SENTENCE"]))

    story.append(P("4. Methods", "H1R"))
    story.append(
        P(
            f"Architecture: ResNet-18 ImageNet encoder + slim U-Net decoder (160×160) with an auxiliary "
            f"classification head. Training uses grouped stratified splits, paired augmentations, checkpointing "
            f"on lesion Dice, and val-tuned segmentation threshold **{nums['SEG_THR']}** with min-component area "
            f"**{nums['MIN_AREA']}**. The served artifact is INT8 ONNX "
            f"`models/v{nums['MODEL_VERSION']}/busi_unet.onnx` (sha256 {nums['MODEL_SHA8']}…). "
            f"The browser runs onnxruntime-web (WASM) in a Web Worker with the same morphology post-process "
            f"as the Python evaluation. Phase 2 added Telea caliper-inpaint experiments, offline TTA "
            f"uncertainty, and Demo threshold sliders."
        )
    )

    story.append(PageBreak())
    story.append(P("5. Results", "H1R"))
    story.append(P("5.1 Internal (BUSI held-out test)", "H2R"))
    story.append(
        table(
            ["Metric", "FP32 training", "Served INT8"],
            [
                ["Dice (all)", nums["FP32_DICE"], nums["INT8_DICE"]],
                ["Lesion Dice", nums["FP32_LESION_DICE"], nums["INT8_LESION_DICE"]],
                ["IoU", nums["FP32_IOU"], nums["INT8_IOU"]],
                ["ROC-AUC", nums["FP32_AUC"], nums["INT8_AUC"]],
                [
                    "Sensitivity / Specificity",
                    f"{nums['FP32_SENS']} / {nums['FP32_SPEC']}",
                    f"{nums['INT8_SENS']} / {nums['INT8_SPEC']}",
                ],
                ["ECE", nums["FP32_ECE"], nums["INT8_ECE"]],
                ["Normal FP masks", nums["FP32_NFP"], nums["INT8_NFP"]],
            ],
        )
    )
    story.append(P("Sources: results/full_run.json, results/served_int8_test.json.", "Cap"))
    story.append(fig("dice_hist"))
    story.append(P("Per-image Dice on the held-out BUSI test set for the served INT8 model.", "Cap"))

    story.append(P("5.2 External validation", "H2R"))
    story.append(
        table(
            ["Set", "Dice", "Lesion Dice", "AUC"],
            [
                ["BUSI internal", nums["INT8_DICE"], nums["INT8_LESION_DICE"], nums["INT8_AUC"]],
                ["BUS-BRA", nums["BUSBRA_DICE"], nums["BUSBRA_LESION_DICE"], nums["BUSBRA_AUC"]],
                ["BrEaST", nums["BREAST_DICE"], nums["BREAST_LESION_DICE"], nums["BREAST_AUC"]],
            ],
        )
    )
    story.append(P("Sources: results/external/busbra.json, results/external/breast.json.", "Cap"))
    story.append(fig("roc"))
    story.append(P("Classification ROC on BUSI versus external sets (when curves are stored).", "Cap"))
    story.append(fig("cal"))
    story.append(P(f"Reliability diagram for the served INT8 classifier (ECE {nums['INT8_ECE']}).", "Cap"))

    story.append(PageBreak())
    story.append(P("5.3 Leakage ablation", "H2R"))
    story.append(
        P(
            f"Short schedule ({nums['LEAK_EPOCHS']} epochs × seeds {nums['LEAK_SEEDS']}), same grouped test: "
            f"random vs grouped splits did not inflate validation Dice on this run "
            f"(mean Δ val Dice random−grouped ≈ **{nums['LEAK_DELTA']}**). Residual leakage risk remains "
            f"because patient IDs are absent. Source: results/leakage_ablation.json."
        )
    )
    story.append(fig("leak"))
    story.append(P("Grouped versus random split validation Dice under the short ablation schedule.", "Cap"))

    story.append(P("5.4 Caliper / inpaint experiment", "H2R"))
    story.append(
        P(
            f"Flagged vs clean Dice gap on the original test: flagged **{nums['EA_FLAGGED']}** vs clean "
            f"**{nums['EA_CLEAN']}**. Erasing markers (E-a) moved overall Dice from {nums['EA_ORIG_DICE']} to "
            f"{nums['EA_INP_DICE']} and did **not** collapse flagged Dice toward clean. The best E-c retrain "
            f"seed did **not** replace served v1.0.0 under the pre-registered swap rule: external Dice was "
            f"BUS-BRA {nums['EC_BUSBRA']} (vs v1 {nums['BUSBRA_DICE']}) and BrEaST {nums['EC_BREAST']} "
            f"(vs v1 {nums['BREAST_DICE']}); clean Dice {nums['EC_CLEAN']}; AUC {nums['EC_AUC']}. "
            f"Source: results/inpaint_experiment.json."
        )
    )
    story.append(fig("caliper", width=5.8 * inch))
    story.append(P("Illustrative CC BY BrEaST frame with synthetic calipers removed by Telea inpainting.", "Cap"))

    story.append(P("5.5 Uncertainty (TTA)", "H2R"))
    story.append(
        P(
            f"Spearman ρ between TTA disagreement and 1−Dice ≈ **{nums['UNCERT_RHO']}** on BUSI test "
            f"(n={nums['UNCERT_N']}). Risk–coverage at 80% keep ≈ Dice **{nums['UNCERT_COV80']}**. "
            f"Interpretation: agreement under flips — not a calibrated error probability. "
            f"Source: results/uncertainty.json."
        )
    )
    story.append(fig("uncert"))
    story.append(P("Offline TTA disagreement versus segmentation error on the BUSI test set.", "Cap"))

    story.append(PageBreak())
    story.append(P("5.6 Measurement agreement (BrEaST)", "H2R"))
    story.append(
        P(
            f"Model vs expert longest diameter (mm) Pearson proxy ≈ **{nums['MEAS_DIAM_R']}** "
            f"(n={nums['MEAS_N']}); area Pearson proxy ≈ **{nums['MEAS_AREA_R']}**; ≥20 mm threshold "
            f"discordance ≈ **{nums['MEAS_T1T2']}**. Research only — not pathologic T-stage. "
            f"Source: results/measurement_agreement.json."
        )
    )

    story.append(P("5.7 Failure cases", "H2R"))
    story.append(
        P(
            "Hard cases from the held-out test are published as outline-only silhouettes on the Model Errors "
            "explorer (BUSI ultrasound pixels withheld on new visuals). The grid below samples those outlines."
        )
    )
    story.append(fig("fail", width=5.8 * inch))
    story.append(P("Outline-only silhouettes for selected BUSI model-error cases.", "Cap"))

    story.append(P("6. Limitations", "H1R"))
    for bullet in [
        "No patient IDs → residual near-duplicate / patient leakage risk",
        "Domain shift: classification AUC drops sharply on externals",
        "Calipers / HUD may still act as shortcuts",
        f"160² resolution loses fine detail; normal-image false positives ({nums['INT8_NFP']})",
        "Not clinically validated; no clinician review on this project",
        "A model score is not a BI-RADS category; imaging size is not surgical staging",
    ]:
        story.append(P("• " + bullet, "BulletR"))

    story.append(P("7. Ethics and licensing", "H1R"))
    story.append(
        P(
            "Code is MIT. Full BUSI is not redistributed (license unclear); cite Al-Dhabyani et al. 2020. "
            "External demo imagery uses CC BY sets with attribution. Site social preview uses CC BY external "
            "pixels (not BUSI). Research demo only. This site uses no analytics or cookies; Demo images are "
            "processed in the browser only."
        )
    )

    story.append(P("8. AI-assistance statement", "H1R"))
    story.append(P(nums["HOW_BUILT"]))

    story.append(P("9. References", "H1R"))
    refs = [
        "Al-Dhabyani W, et al. Dataset of breast ultrasound images. Data in Brief. 2020;28:104863.",
        "Mendelson EB, et al. ACR BI-RADS® Ultrasound. In: ACR BI-RADS® Atlas. Reston, VA: ACR; 2013.",
        "Gómez-Flores W, et al. BUS-BRA breast ultrasound dataset. Zenodo; 2024. CC BY 4.0.",
        "Pawłowska A, et al. BrEaST — Breast Cancer Dataset. TCIA; 2024. CC BY 4.0.",
        "Moran MS, et al. SSO–ASTRO consensus guideline on margins for breast-conserving surgery. 2014.",
        f"Project repository: {nums['GITHUB_URL']}",
    ]
    for i, r in enumerate(refs, 1):
        story.append(P(f"{i}. {r}", "BulletR"))

    story.append(Spacer(1, 10))
    story.append(
        P(
            "Numbers in this PDF are auto-filled from committed results JSON by scripts/build_report_pdf.py. "
            "A CI check fails if PDF figures drift from those JSON files.",
            "Cap",
        )
    )

    # Also write a filled markdown snapshot for humans
    md = f"""# Breast Ultrasound Lesion Segmentation: Research Write-up

Version {nums['MODEL_VERSION']} · Site-only research report  
Author: Surabhi Fadnavis (high-school senior, Georgia)

> Research demo — not for clinical use.

## Abstract
Served INT8 Dice {nums['INT8_DICE']}, lesion Dice {nums['INT8_LESION_DICE']}, AUC {nums['INT8_AUC']}; BUS-BRA Dice {nums['BUSBRA_DICE']} AUC {nums['BUSBRA_AUC']}; BrEaST Dice {nums['BREAST_DICE']} AUC {nums['BREAST_AUC']}.

## Data
Annotation-flag rate {nums['ANNOTATION_RATE']} ({nums['N_FLAGGED']}/{nums['N_TOTAL']}).
{nums['BUSUCLM_SENTENCE']}
External: BUS-BRA n={nums['BUSBRA_N']}; BrEaST n={nums['BREAST_N']} (Pawłowska et al.).

## Results highlights
Leakage Δ {nums['LEAK_DELTA']}; E-a flagged/clean {nums['EA_FLAGGED']}/{nums['EA_CLEAN']}; E-c external {nums['EC_BUSBRA']}/{nums['EC_BREAST']}; TTA ρ {nums['UNCERT_RHO']}; cov80 {nums['UNCERT_COV80']}; meas diam r {nums['MEAS_DIAM_R']} (n={nums['MEAS_N']}), ≥20mm discordance {nums['MEAS_T1T2']}.

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
    # Persist drift map (values that must appear in PDF text)
    skip = {"HOW_BUILT", "PAGES_URL", "GITHUB_URL", "BUSUCLM_SENTENCE", "LEAK_SEEDS", "MODEL_SHA8"}
    expected = {k: v for k, v in nums.items() if k not in skip}
    NUMBERS_JSON.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n")
    figs = make_figures()
    build_pdf(nums, figs)

    from pypdf import PdfReader

    reader = PdfReader(str(OUT_PDF))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    # Unicode check
    if "Paw" not in text and "Pawłowska" not in text:
        # extraction may normalize; check PDF contains font and we wrote the string in filled md
        if "Pawłowska" not in FILLED_MD.read_text():
            raise SystemExit("Pawłowska missing from filled markdown")
    compact = " ".join(text.split())
    if "Mendeley Data download requires a login" not in compact:
        raise SystemExit("Reader-facing BUS-UCLM sentence missing from PDF text")
    if "data/external" in text:
        raise SystemExit("Internal data/external path leaked into PDF text")
    if "Pawłowska" not in FILLED_MD.read_text() and "Paw" not in text:
        raise SystemExit("Pawłowska / Paw missing from report")
    offenders = re.findall(r"\bD(?:1[0-2]|[1-9])\b", text)
    if offenders:
        raise SystemExit(f"Decision codes leaked into PDF text: {offenders}")
    # Reject placeholders in reader text (allow source-path captions like results/*.json)
    for bad in ("n/a", "None/None", "TODO", "NaN"):
        if bad in text:
            raise SystemExit(f"Placeholder {bad!r} found in PDF text")
    # Em dash alone as a table cell value
    if re.search(r"\n—\n", text):
        raise SystemExit("Placeholder em-dash cell found in PDF text")
    n_pages = len(reader.pages)
    print(f"Wrote {OUT_PDF} ({OUT_PDF.stat().st_size} bytes, {n_pages} pages)")
    if n_pages < 6 or n_pages > 10:
        print(f"WARNING: page count {n_pages} outside 6–10 target band")
    else:
        print(f"OK: page count {n_pages} within 6–10")
    return 0


if __name__ == "__main__":
    sys.exit(main())
