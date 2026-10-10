#!/usr/bin/env python3
"""CI check: fail if report.pdf numeric figures drift from results JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_report_pdf import (  # noqa: E402
    NUMBERS_JSON,
    OUT_PDF,
    collect_numbers,
)

SKIP_IN_PDF = {
    "HOW_BUILT",
    "PAGES_URL",
    "GITHUB_URL",
    "BUSUCLM_SENTENCE",
    "BUSUCLM_SKIP",
    "LEAK_SEEDS",
    "MODEL_SHA8",
}


def extract_pdf_numbers(pdf_path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def main() -> int:
    if not OUT_PDF.exists():
        print(f"FAIL: missing {OUT_PDF}")
        return 1
    if not NUMBERS_JSON.exists():
        print(f"FAIL: missing {NUMBERS_JSON} — run scripts/build_report_pdf.py")
        return 1

    committed = json.loads(NUMBERS_JSON.read_text())
    fresh = collect_numbers()
    drift_keys = [k for k in committed if k not in SKIP_IN_PDF]

    mismatches = []
    for k in drift_keys:
        if k not in fresh:
            mismatches.append(f"{k}: missing from fresh collect")
            continue
        if committed[k] != fresh[k]:
            mismatches.append(f"{k}: committed={committed[k]!r} fresh={fresh[k]!r}")

    if mismatches:
        print("FAIL: numbers.json drifts from results JSON:")
        for m in mismatches:
            print(" ", m)
        print("Re-run: python scripts/build_report_pdf.py")
        return 1

    pdf_text = extract_pdf_numbers(OUT_PDF)
    compact = " ".join(pdf_text.split())
    missing_in_pdf = []
    for k in drift_keys:
        val = committed[k]
        if not val or val == "n/a":
            continue
        if val not in pdf_text and val not in compact:
            missing_in_pdf.append(f"{k}={val}")

    if missing_in_pdf:
        print("FAIL: PDF text missing expected numbers:")
        for m in missing_in_pdf:
            print(" ", m)
        return 1

    if "HTTP 403 wit)" in pdf_text:
        print("FAIL: BUS-UCLM sentence truncated")
        return 1
    if "BUS-UCLM" not in pdf_text and "BUS-UCLM" not in compact:
        print("FAIL: BUS-UCLM missing from PDF text")
        return 1

    print(f"OK: {len(drift_keys)} numbers match results JSON and appear in {OUT_PDF.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
