# Changelog

All notable changes to this project and its served model are documented here.
Model versions follow [SemVer](https://semver.org/) under `web/public/models/vX.Y.Z/`.

## [Unreleased] — Phase 4 (2026-10-10)

### Added

- **v2 training pipeline** (`scripts/train_v2.py`, `scripts/apply_v2_swap.py`): BUSI train + patient-grouped BUS-BRA train; held-out BUS-BRA test; BrEaST external; ResNet-34 @ 256²; Dice+focal; stronger aug; optional Telea inpaint; ~3 seeds. Results comparison table on `/results` (`v2_experiment`). Swap only under MODEL_POLICY (D3) + INT8 ≤ ~25 MB.
- Citation / freeze pack: `.zenodo.json`, enhanced `CITATION.cff`, `docs/ZENODO_STEPS.md`, `docs/RELEASE_NOTES_v1.0_DRAFT.md`, `docs/FREEZE_CHECKLIST.md` (no tags/releases by agents).
- Preprint pack: `paper/` LaTeX (6–8 pp) with auto-pulled numbers + drift check; `docs/SUBMISSION_GUIDE.md` (JEI vs arXiv). No submissions.
- BUS-UCLM: hardened loader + `docs/BUSUCLM_STEPS.md`; eval skips cleanly when archive absent.
- Demo: drag-and-drop / upload (browser-only + privacy note), client-side one-page result PDF, mobile camera capture, PWA/offline (shell + model cached by `current.json` cache_key).

### Model

- Served weights remain **v1.0.0**. Fair Phase-4 swap (D17): seed-mean clean Dice **0.614 ± 0.012** vs v1 **0.623** (Δ −0.009, paired bootstrap 95% CI [−0.022, +0.002]) — **mean fails**, so no promotion. Only seed 42 individually passed; seeds 43/44 failed clean and/or AUC. BUS-BRA same-source held-out improved a lot (v2 mean **0.894** vs v1-on-same-split **0.713**); BrEaST external mean **0.672** vs v1 **0.627**. INT8 ~21.3 MB. See Results → Phase 4 comparison and `results/v2_experiment.json`.

## [Phase 3] — 2026-10-08

### Added

- `/bi-rads` — plain-language BI-RADS ultrasound context (score ≠ category); verified ACR / review citations.
- `/surgeons-view` — size/margins research framing; BrEaST CC BY examples + BUSI outline silhouettes.
- `web/public/report.pdf` — 6–10 page research write-up auto-filled from results JSON with figures; CI drift check.
- `CITATION.cff` + About “How to cite” (Zenodo DOI deferred — needs owner login).
- Captioned walkthrough `web/public/video/walkthrough.mp4` + poster + VTT; storyboard in `docs/VIDEO_SCRIPT.md`.
- `/portfolio` — Surabhi Fadnavis: student research in oncology AI (verified sibling links; no invented metrics).
- Social preview from CC BY BrEaST imagery; privacy note (no analytics/cookies).
- Grouped primary nav (Learn / About menus); accessibility notes in `docs/ACCESSIBILITY.md`.
- Decision log D5–D12 (plan numbering); credit: “Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (Cursor).”

### Skipped

- Clinician review / acknowledgements (revoked; C3 skipped).
- Analytics (none).
- Separate `surabhif.github.io` portfolio repo — in-site `/portfolio` instead (dated note, not a D-number).
- Model **v1.0.0** unchanged; Dec 4 freeze not tagged yet.

## [Phase 2] — 2026-10-08

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
