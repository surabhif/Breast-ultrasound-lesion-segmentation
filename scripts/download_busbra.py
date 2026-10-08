#!/usr/bin/env python3
"""Download BUS-BRA (Zenodo) for external validation.

Does **not** commit data. Writes under data/external/busbra/ (gitignored).
Licence: CC BY 4.0 — cite Gómez-Flores et al., Med Phys 2024.

See docs/EXTERNAL_VALIDATION_PROTOCOL.md — do not score until protocol is committed.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "data" / "external" / "busbra"

# Zenodo record 8231412 — BUSBRA.zip
ZENODO_URL = "https://zenodo.org/records/8231412/files/BUSBRA.zip?download=1"
# Fill after first successful download if you want a pin:
EXPECTED_SHA256: str | None = None


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--skip-extract", action="store_true")
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    zip_path = args.out / "BUSBRA.zip"
    meta = args.out / "SOURCE.txt"
    meta.write_text(
        "dataset: BUS-BRA\n"
        "doi_paper: 10.1002/mp.16812\n"
        "zenodo: https://zenodo.org/records/8231412\n"
        f"url: {ZENODO_URL}\n"
        "licence: CC BY 4.0\n"
        "protocol: docs/EXTERNAL_VALIDATION_PROTOCOL.md\n"
    )

    if not zip_path.exists():
        print(f"Downloading {ZENODO_URL} → {zip_path} …")
        urlretrieve(ZENODO_URL, zip_path)
    else:
        print(f"Using existing {zip_path}")

    digest = sha256_file(zip_path)
    print(f"sha256={digest}")
    (args.out / "BUSBRA.zip.sha256").write_text(digest + "\n")
    if EXPECTED_SHA256 and digest != EXPECTED_SHA256:
        print("ERROR: checksum mismatch", file=sys.stderr)
        sys.exit(1)

    if not args.skip_extract:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(args.out / "raw")
        print(f"Extracted under {args.out / 'raw'}")

    print("Done. Data is gitignored; do not commit.")


if __name__ == "__main__":
    main()
