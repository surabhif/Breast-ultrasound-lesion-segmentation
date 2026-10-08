# Changelog

All notable changes to this project and its served model are documented here.
Model versions follow [SemVer](https://semver.org/) under `web/public/models/vX.Y.Z/`.

## [Unreleased] — Phase 2 (2026-10-08)

### Removed

- Clinician review / outreach (`/review`, `docs/CLINICIAN_REVIEW.md`, related tokens). **D4 revoked** (see `docs/DECISION_LOG.md`).

### Added

- Caliper/marker pixel masks + agent QA (≥60 flagged + 20 clean); Telea inpaint E-a/E-b/E-c (3 seeds).
- Offline TTA uncertainty (`results/uncertainty.json`) + Demo agreement/heatmap.
- Web Worker inference + self-hosted ORT WASM under `web/public/ort/`.
- Demo mask/class threshold sliders; Results operating-point explorer; `/mistakes` explorer (≥20 AI notes).
- CC BY BrEaST before/after (synthetic calipers) on Results.

### Changed

- **Served model remains v1.0.0.** MODEL_POLICY swap failed: best E-c seed improved clean Dice slightly and kept AUC, but **external Dice dropped** (BUS-BRA 0.626 vs v1 0.714; BrEaST 0.608 vs 0.627). Published as experiment only.

### Inpaint experiment (honest)

| Setting | Dice | Lesion Dice | AUC |
|---|---|---|---|
| v1 original test | 0.697 | 0.764 | 0.931 |
| v1 on inpainted test (E-a) | 0.702 | 0.760 | 0.918 |
| E-b random inpaint (clean) | 0.626 | — | — |
| E-c best seed 44 (original test) | 0.671 | 0.776 | 0.945 |

E-a: erasing markers did **not** drop flagged Dice toward clean (flagged Dice stayed ~0.76–0.77). E-b control Δ≈−0.002.

### TTA

- Spearman(uncertainty, 1−Dice) ρ ≈ 0.61 on BUSI test; risk–coverage at 80% keep ≈ Dice 0.78.

## [Phase 1] — 2026-10-08

### Added

- External validation of frozen **v1.0.0 INT8** on **BUS-BRA** and **BrEaST** (`results/external/*`); BUS-UCLM skipped (Mendeley HTTP 403 without interactive login).
- Results sections: External validation + Comparison with published work; `docs/LITERATURE_COMPARISON.md`.
- Demo: expert-vs-model compare modes + per-image Dice; lesion measurements (px / mm on BrEaST).
- Offline measurement agreement on BrEaST (`results/measurement_agreement.json`).
- Full-scale leakage ablation (`scripts/run_leakage_ablation.py` → `results/leakage_ablation.json`): 6 ep × 3 seeds; random splits did not inflate val Dice vs grouped on this schedule (Δ ≈ −0.018).
- `docs/DECISION_LOG.md` (D1–D3; D4 later revoked); model-swap rule in `EXTERNAL_VALIDATION_PROTOCOL.md`.
- Small CC BY BrEaST samples under `web/public/samples/external/` with attribution.

### Changed

- Model card / README limitations updated with external Dice/AUC (honest AUC drop).
- Served model remains **v1.0.0** (unchanged).

### External metrics (v1.0.0 INT8)

| Set | Dice | Lesion Dice | AUC |
|---|---|---|---|
| BUSI internal | 0.697 | 0.764 | 0.931 |
| BUS-BRA | 0.714 | 0.714 | 0.638 |
| BrEaST | 0.627 | 0.629 | 0.721 |

## [model-v1.0.0] — 2026-10-08

### Added

- Semantic model version **v1.0.0** for the served INT8 ONNX (`models/v1.0.0/busi_unet.onnx` + `model.json`).
- `models/current.json` pointer with versioned Cache API key (`busi-unet-v1.0.0-<sha8>`); stale `busi-unet-*` caches are deleted on load.
- Full held-out **INT8 test metrics** (`results/served_int8_test.json`) published next to FP32 training metrics.
- Browser post-processing parity: min-component area **40** (4-connected), matching Python eval.
- Python↔browser parity suite (`tests/parity/reference.json`, Playwright + Vitest morphology tests).
- GitHub Actions **CI** (lint/typecheck/build, Python smoke, parity) on PRs and `main`.
- Pre-registered external validation protocol: `docs/EXTERNAL_VALIDATION_PROTOCOL.md` (BUS-BRA, BrEaST; no evaluation run yet).
- Optional download stubs: `scripts/download_busbra.py`, `scripts/download_breast.py` (data not committed).

### Changed

- Results page and model card label **served INT8** vs **FP32 training** metrics; footer shows model version.
- Metrics schema bumped to `schema_version: 2` with a `served_int8` block.

### Metrics (held-out BUSI test, n=112)

| | FP32 PyTorch (training preprocess) | INT8 ONNX (served preprocess) |
|---|---|---|
| Test Dice | 0.686 [0.619–0.750] | 0.697 [0.632–0.766] |
| Lesion Dice | 0.751 [0.689–0.808] | 0.764 [0.706–0.820] |
| Cls AUC | 0.939 | 0.931 |
| Normal FP masks | 12/19 | 12/19 |

Served numbers use shared half-pixel bilinear resize (`busi_data.resize_rgb_bilinear` / `image.resizeRgbBilinear`) so the browser matches the evaluated INT8 path. FP32 training still used torchvision/PIL resize.

sha256 `0bbf529dcb46f1f4c01c781f11976e4c0cdca7fc5b2f2b814f028af847743570`
