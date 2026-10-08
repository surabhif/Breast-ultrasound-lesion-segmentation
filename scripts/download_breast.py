#!/usr/bin/env python3
"""Download BrEaST (TCIA BREAST-LESIONS-USG), CC BY 4.0.

Direct zip + clinical XLSX from cancerimagingarchive.net (no NBIA required).
Does not commit data. See docs/EXTERNAL_VALIDATION_PROTOCOL.md.
"""
from __future__ import annotations
import argparse, hashlib, zipfile
from pathlib import Path
from urllib.request import urlretrieve

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "external" / "breast"
ZIP_URL = "https://www.cancerimagingarchive.net/wp-content/uploads/BrEaST-Lesions_USG-images_and_masks-Dec-15-2023.zip"
XLSX_URL = "https://www.cancerimagingarchive.net/wp-content/uploads/BrEaST-Lesions-USG-clinical-data-Dec-15-2023.xlsx"

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "SOURCE.txt").write_text(
        "dataset: BrEaST / BREAST-LESIONS-USG\n"
        "doi_paper: 10.1038/s41597-024-02984-z\n"
        "doi_data: 10.7937/9WKK-Q141\n"
        f"zip: {ZIP_URL}\n"
        f"clinical: {XLSX_URL}\n"
        "licence: CC BY 4.0\n"
    )
    zpath = args.out / "BrEaST-Lesions_USG-images_and_masks.zip"
    if not zpath.exists():
        print("Downloading images zip…")
        urlretrieve(ZIP_URL, zpath)
    xlsx = args.out / "BrEaST-Lesions-USG-clinical-data.xlsx"
    if not xlsx.exists():
        print("Downloading clinical XLSX…")
        urlretrieve(XLSX_URL, xlsx)
    digest = sha256_file(zpath)
    (args.out / "BrEaST.zip.sha256").write_text(digest + "\n")
    print("sha256", digest)
    with zipfile.ZipFile(zpath) as zf:
        zf.extractall(args.out / "raw")
    print("Done. Data is gitignored.")

if __name__ == "__main__":
    main()
