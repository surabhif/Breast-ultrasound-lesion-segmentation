#!/usr/bin/env python3
"""Download helper notes for BrEaST (TCIA BREAST-LESIONS-USG).

TCIA often requires interactive / NBIA download. This script records the
canonical DOI and optional local path; it does **not** scrape private APIs.

Licence: CC BY 4.0 — cite Pawłowska et al., Sci Data 2024.
See docs/EXTERNAL_VALIDATION_PROTOCOL.md — do not score until protocol is committed.
"""

from __future__ import annotations

import argparse
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "external" / "breast"

TCIA_DOI = "10.7937/9WKK-Q141"
TCIA_URL = "https://www.cancerimagingarchive.net/collection/breast-lesions-usg/"
PAPER_DOI = "10.1038/s41597-024-02984-z"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument(
        "--local-zip",
        type=Path,
        default=None,
        help="If you already downloaded a TCIA zip, copy/link it here.",
    )
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "SOURCE.txt").write_text(
        "dataset: BrEaST / BREAST-LESIONS-USG\n"
        f"doi_paper: {PAPER_DOI}\n"
        f"doi_data: {TCIA_DOI}\n"
        f"url: {TCIA_URL}\n"
        "licence: CC BY 4.0\n"
        "protocol: docs/EXTERNAL_VALIDATION_PROTOCOL.md\n"
        "note: Download via TCIA/NBIA Data Retriever; place archive under this folder.\n"
    )

    if args.local_zip:
        dest = args.out / args.local_zip.name
        if not args.local_zip.exists():
            raise SystemExit(f"Missing {args.local_zip}")
        if not dest.exists():
            dest.write_bytes(args.local_zip.read_bytes())
        print(f"Copied {args.local_zip} → {dest}")
    else:
        print(
            "Wrote SOURCE.txt. Download the collection from TCIA, then re-run with "
            f"--local-zip /path/to/archive.zip (output dir: {args.out})."
        )
        print(f"  {TCIA_URL}")

    print("Done. Data is gitignored; do not commit. Do not run evaluation yet.")


if __name__ == "__main__":
    main()
