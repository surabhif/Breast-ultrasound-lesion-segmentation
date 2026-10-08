#!/usr/bin/env python3
"""Build web/public/report.pdf from docs/report/report.md.template + results JSON.

All numeric placeholders are filled from committed JSON — nothing hand-typed.
Also writes docs/report/report.filled.md and docs/report/numbers.json (expected map
for the drift checker).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "docs" / "report" / "report.md.template"
FILLED_MD = ROOT / "docs" / "report" / "report.filled.md"
NUMBERS_JSON = ROOT / "docs" / "report" / "numbers.json"
OUT_PDF = ROOT / "web" / "public" / "report.pdf"

HOW_BUILT = (
    "How this was built: The code, analysis scripts, and most site and report text were "
    "produced with AI coding tools (Cursor). Surabhi Fadnavis owns the research questions, "
    "interpretation, presentation choices, and final review. This is a high-school research "
    "project — not clinician-reviewed and not for clinical use."
)


def load(path: Path):
    with path.open() as f:
        return json.load(f)


def fmt(x, digits=3):
    if x is None:
        return "n/a"
    if isinstance(x, str):
        return x
    return f"{float(x):.{digits}f}"


def pct(x, digits=1):
    return f"{100.0 * float(x):.{digits}f}%"


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
    skip = load(ROOT / "results" / "external" / "busuclm_SKIPPED.json")

    fm = full["metrics"]
    ea = inp["E_a"]["original"]
    ec = inp.get("E_c") or {}
    best = ec.get("best") if isinstance(ec.get("best"), dict) else {}
    # Prefer the recorded best seed's external blocks
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
    if ec_busbra is None:
        ec_busbra = best.get("external_busbra_dice")
    if ec_breast is None:
        ec_breast = best.get("external_breast_dice")

    # Leakage delta
    runs = leak.get("runs") or []
    grouped_vals = [r["val_dice"] for r in runs if r.get("mode") == "grouped" and "val_dice" in r]
    random_vals = [r["val_dice"] for r in runs if r.get("mode") == "random" and "val_dice" in r]
    if grouped_vals and random_vals:
        leak_delta = sum(random_vals) / len(random_vals) - sum(grouped_vals) / len(grouped_vals)
    else:
        leak_delta = leak.get("summary", {}).get("delta_val_dice_random_minus_grouped")

    cov80 = None
    for row in uncert.get("risk_coverage") or []:
        if abs(float(row.get("coverage", -1)) - 0.8) < 1e-6:
            cov80 = row.get("mean_dice")
            break

    busuclm_skip = skip.get("reason") or skip.get("note") or "skipped"
    if isinstance(busuclm_skip, dict):
        busuclm_skip = busuclm_skip.get("reason") or str(busuclm_skip)

    dc = clean["dataset_counts"]
    nums = {
        "MODEL_VERSION": "1.0.0",
        "PAGES_URL": "https://surabhif.github.io/Breast-ultrasound-lesion-segmentation/",
        "GITHUB_URL": "https://github.com/surabhif/Breast-ultrasound-lesion-segmentation",
        "HOW_BUILT": HOW_BUILT,
        "SEG_THR": fmt(int8.get("seg_threshold", 0.4), 1),
        "MIN_AREA": str(int(int8.get("min_component_area", 40))),
        "MODEL_SHA8": str(int8.get("sha256", ""))[:8],
        "FP32_DICE": fmt(fm.get("test_dice")),
        "FP32_LESION_DICE": fmt(fm.get("lesion_dice")),
        "FP32_IOU": fmt(fm.get("test_iou")),
        "FP32_AUC": fmt(fm.get("cls_roc_auc")),
        "FP32_NFP": f"{fm.get('normal_false_positive_count', '?')}/{fm.get('normal_n', '?')}",
        "INT8_DICE": fmt(int8.get("dice_mean")),
        "INT8_LESION_DICE": fmt(int8.get("lesion_dice_mean")),
        "INT8_IOU": fmt(int8.get("iou_mean")),
        "INT8_AUC": "pending",
        "INT8_NFP": "pending",
        "BUSBRA_DICE": fmt(busbra.get("test_dice")),
        "BUSBRA_LESION_DICE": fmt(busbra.get("lesion_dice")),
        "BUSBRA_AUC": fmt(busbra.get("cls_roc_auc")),
        "BUSBRA_N": str(busbra.get("n")),
        "BUSBRA_NP": str(busbra.get("n_patients")),
        "BREAST_DICE": fmt(breast.get("test_dice")),
        "BREAST_LESION_DICE": fmt(breast.get("lesion_dice")),
        "BREAST_AUC": fmt(breast.get("cls_roc_auc")),
        "BREAST_N": str(breast.get("n")),
        "BREAST_NP": str(breast.get("n_patients")),
        "BUSUCLM_SKIP": str(busuclm_skip)[:120],
        "ANNOTATION_RATE": pct(dc["annotation_rate"]),
        "N_FLAGGED": str(dc["n_annotation_flagged"]),
        "N_TOTAL": str(dc["n_total"]),
        "LEAK_EPOCHS": str(leak.get("epochs")),
        "LEAK_SEEDS": ",".join(str(s) for s in leak.get("seeds", [])),
        "LEAK_DELTA": fmt(leak_delta),
        "EA_FLAGGED": fmt(ea.get("dice_flagged")),
        "EA_CLEAN": fmt(ea.get("dice_clean")),
        "EC_BUSBRA": fmt(ec_busbra),
        "EC_BREAST": fmt(ec_breast),
        "UNCERT_RHO": fmt(uncert["spearman_uncertainty_vs_error"]["rho"]),
        "UNCERT_N": str(uncert.get("n")),
        "UNCERT_COV80": fmt(cov80),
        "MEAS_DIAM_R": fmt(meas["longest_diameter_mm"]["pearson_proxy_for_icc"]),
        "MEAS_N": str(meas.get("n")),
        "MEAS_T1T2": pct(meas["longest_diameter_mm"]["t1_t2_20mm_discordance_rate"]),
    }

    nums["INT8_AUC"] = fmt(int8.get("cls_roc_auc"))
    nums["INT8_NFP"] = (
        f"{int8.get('normal_false_positive_count')}/{int8.get('normal_n')}"
    )
    for key in ("EC_BUSBRA", "EC_BREAST", "LEAK_DELTA", "UNCERT_COV80"):
        if nums[key] == "n/a":
            raise SystemExit(f"Missing required number for {{{key}}}")

    return nums


def fill_template(template: str, nums: dict[str, str]) -> str:
    out = template
    for k, v in nums.items():
        out = out.replace("{{" + k + "}}", v)
    leftover = re.findall(r"\{\{[A-Z0-9_]+\}\}", out)
    if leftover:
        raise SystemExit(f"Unfilled placeholders: {leftover}")
    return out


def md_to_pdf(md_text: str, pdf_path: Path) -> None:
    from reportlab.lib.colors import HexColor
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
        Preformatted,
        KeepTogether,
        HRFlowable,
    )

    teal = HexColor("#297373")
    ink = HexColor("#0e0e0e")
    muted = HexColor("#5c6b6b")

    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="TitleTeal",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=teal,
            spaceAfter=8,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Meta",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=muted,
            alignment=TA_CENTER,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Warn",
            parent=styles["Normal"],
            fontSize=9,
            leading=12,
            textColor=HexColor("#ffffff"),
            backColor=teal,
            borderPadding=6,
            spaceAfter=12,
            spaceBefore=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H1R",
            parent=styles["Heading1"],
            fontSize=13,
            leading=16,
            textColor=teal,
            spaceBefore=14,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H2R",
            parent=styles["Heading2"],
            fontSize=11,
            leading=14,
            textColor=ink,
            spaceBefore=10,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyR",
            parent=styles["Normal"],
            fontSize=9.5,
            leading=13,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BulletR",
            parent=styles["Normal"],
            fontSize=9.5,
            leading=13,
            leftIndent=14,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="FooterNote",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=muted,
            spaceBefore=12,
        )
    )

    def esc(s: str) -> str:
        return (
            s.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    story = []
    lines = md_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("# "):
            story.append(Paragraph(esc(line[2:].strip()), styles["TitleTeal"]))
        elif line.startswith("## "):
            story.append(Paragraph(esc(line[3:].strip()), styles["H1R"]))
        elif line.startswith("### "):
            story.append(Paragraph(esc(line[4:].strip()), styles["H2R"]))
        elif line.startswith("> "):
            # collect blockquote
            buf = [line[2:]]
            i += 1
            while i < len(lines) and lines[i].startswith("> "):
                buf.append(lines[i][2:])
                i += 1
            story.append(Paragraph(esc(" ".join(buf)), styles["BodyR"]))
            story.append(
                HRFlowable(width="100%", thickness=1, color=teal, spaceAfter=8)
            )
            continue
        elif line.startswith("|") and i + 1 < len(lines) and lines[i + 1].startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                raw = lines[i].strip()
                if re.match(r"^\|[\s|:-]+\|$", raw.replace(" ", "")) or set(
                    raw.replace("|", "").replace(":", "").replace("-", "").replace(" ", "")
                ) == set():
                    i += 1
                    continue
                cells = [c.strip() for c in raw.strip("|").split("|")]
                rows.append(cells)
                i += 1
            if rows:
                data = [[Paragraph(esc(c.replace("**", "")), styles["BodyR"]) for c in r] for r in rows]
                t = Table(data, hAlign="LEFT", colWidths=[1.6 * inch] + [1.15 * inch] * (len(rows[0]) - 1))
                t.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), HexColor("#dfeaea")),
                            ("TEXTCOLOR", (0, 0), (-1, -1), ink),
                            ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#89b2b2")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 4),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                            ("TOPPADDING", (0, 0), (-1, -1), 3),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ]
                    )
                )
                story.append(t)
                story.append(Spacer(1, 8))
            continue
        elif line.startswith("- "):
            story.append(Paragraph("• " + esc(line[2:].replace("**", "")), styles["BulletR"]))
        elif line.startswith("---"):
            story.append(HRFlowable(width="100%", thickness=0.5, color=HexColor("#c5d4d4"), spaceBefore=6, spaceAfter=6))
        elif line.strip() == "":
            story.append(Spacer(1, 4))
        elif line.startswith("*") and line.endswith("*"):
            story.append(Paragraph(esc(line.strip("*")), styles["FooterNote"]))
        else:
            # bold markdown **x**
            html = esc(line)
            html = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", html)
            html = re.sub(r"`(.+?)`", r"<font face='Courier' size='8'>\1</font>", html)
            story.append(Paragraph(html, styles["BodyR"]))
        i += 1

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title="Breast Ultrasound Lesion Segmentation — Research Write-up",
        author="Surabhi Fadnavis",
    )
    doc.build(story)


def extract_pdf_numbers(pdf_path: Path) -> str:
    """Return concatenated text of the PDF for drift checks."""
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader  # type: ignore

    reader = PdfReader(str(pdf_path))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def main() -> int:
    nums = collect_numbers()
    template = TEMPLATE.read_text()
    filled = fill_template(template, nums)
    FILLED_MD.parent.mkdir(parents=True, exist_ok=True)
    FILLED_MD.write_text(filled)
    # Persist the numeric map (values that must appear in the PDF)
    drift_keys = [
        k
        for k in nums
        if k
        not in (
            "HOW_BUILT",
            "PAGES_URL",
            "GITHUB_URL",
            "BUSUCLM_SKIP",
            "LEAK_SEEDS",
            "MODEL_SHA8",
        )
    ]
    expected = {k: nums[k] for k in drift_keys}
    NUMBERS_JSON.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n")

    md_to_pdf(filled, OUT_PDF)
    text = extract_pdf_numbers(OUT_PDF)
    missing = [f"{k}={v}" for k, v in expected.items() if v and v not in text]
    if missing:
        print("WARNING: some numbers not found in PDF text extraction:", missing[:10])
        # Still OK if PDF rendering splits numbers — check_report_pdf_drift does stricter check on filled md + pdf
    print(f"Wrote {OUT_PDF.relative_to(ROOT)} ({OUT_PDF.stat().st_size} bytes)")
    print(f"Wrote {FILLED_MD.relative_to(ROOT)}")
    print(f"Wrote {NUMBERS_JSON.relative_to(ROOT)} ({len(expected)} tracked numbers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
