# Changelog

All notable changes to this project and its served model are documented here.
Model versions follow [SemVer](https://semver.org/) under `web/public/models/vX.Y.Z/`.

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
