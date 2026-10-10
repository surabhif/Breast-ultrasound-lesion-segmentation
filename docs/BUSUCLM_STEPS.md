# BUS-UCLM download steps (owner)

Secondary external set. The loader at `scripts/external/busuclm.py` **skips cleanly** when the archive is absent (writes `results/external/busuclm_SKIPPED.json` and records the reason in `web/public/results/metrics.json`). Do **not** invent or commit raw images.

Research evaluation only — not for clinical use.

## 1. Download the Mendeley archive

1. Open [Mendeley Data doi:10.17632/7fvgj4jsp7.3](https://doi.org/10.17632/7fvgj4jsp7.3) (Vallez et al., *Sci Data* 2025; dataset **CC BY 4.0**).
2. Sign in if the site requires interactive login (automated downloads often return **HTTP 403**).
3. Download the full dataset zip(s) from the Mendeley release page.

## 2. Place files under the repo

```text
data/external/busuclm/
  raw/          # preferred: extracted tree here
  # or unzip contents directly under data/external/busuclm/
```

Example:

```bash
mkdir -p data/external/busuclm/raw
# After download (path will vary):
unzip ~/Downloads/BUS-UCLM*.zip -d data/external/busuclm/raw
```

Expected layout after extract (names vary slightly by release):

- Image folders such as `images` / `img` / `benign` / `malignant` / `normal`
- Matching masks under a `masks` / `mask` folder, or `*_mask.png` siblings
- RGB mask convention used by the loader: **green ≈ benign**, **red ≈ malignant**

Do not commit the archive or extracted images (they stay local / gitignored).

## 3. Run external evaluation

From the repo root (after the frozen v1.0.0 ONNX and Python deps are available):

```bash
python scripts/eval_external.py --datasets busuclm
# or all external sets:
python scripts/eval_external.py
```

If the archive is missing or pairs cannot be matched, the script prints `SKIP busuclm: …` and continues. When pairs are found, metrics are written to `results/external/busuclm.json` and merged into the `external` block of `web/public/results/metrics.json`.

## 4. Citation

Vallez et al., *Sci Data* 2025;12:242 — [doi:10.1038/s41597-025-04564-2](https://doi.org/10.1038/s41597-025-04564-2). Dataset: Mendeley [doi:10.17632/7fvgj4jsp7.3](https://doi.org/10.17632/7fvgj4jsp7.3), CC BY 4.0.

See also `docs/EXTERNAL_VALIDATION_PROTOCOL.md` §5.3.
