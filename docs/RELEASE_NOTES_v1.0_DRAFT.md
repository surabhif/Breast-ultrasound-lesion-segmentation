# DRAFT — Release notes for site / software v1.0

> **STATUS: DRAFT ONLY.** Do **not** publish a GitHub Release or create tags from this file until the owner completes `docs/FREEZE_CHECKLIST.md`. Agents must not create releases.

**Suggested tag (owner-only, later):** `v1.0.0`  
**Suggested title:** `v1.0.0 — Dec 4 freeze (BUSI demo + external validation)`  
**Live demo:** https://surabhif.github.io/Breast-ultrasound-lesion-segmentation/  
**Research demo — not for clinical use.**

---

## Summary

First freeze-ready release of the breast ultrasound lesion segmentation research demo: in-browser ONNX inference, BUSI metrics with honest leakage/caliper audits, external validation on BUS-BRA and BrEaST, Phase 2 robustness experiments (served model unchanged), and Phase 3 clinical-context / portfolio polish.

**Credit:** Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (Cursor).

---

## Phase 0 — Parity & versioning

- Served model frozen as **v1.0.0** ResNet-18 U-Net, **INT8** ONNX (~11.7 MB), 160×160
- Shared half-pixel bilinear preprocess + min-component area **40** (browser ↔ Python parity)
- CI: lint, typecheck, build, smoke, morphology/parity checks
- Grouped near-duplicate splits on BUSI (no patient IDs)
- Pre-registered external validation protocol + MODEL_POLICY swap rule

### Headline BUSI results (served INT8)

| Metric | Value |
|--------|-------|
| Test Dice (all) | 0.697 [0.632–0.766] |
| Lesion-only Dice | 0.764 [0.706–0.820] |
| B vs M ROC-AUC | 0.931 |
| Normal false-positive masks | 12/19 |

(FP32 training checkpoint reported alongside INT8 on Results / model card.)

---

## Phase 1 — External validation

- Frozen **v1.0.0 INT8** scored on **BUS-BRA** and **BrEaST** (no external tuning)
- BUS-BRA Dice **0.714** / AUC **0.638**; BrEaST Dice **0.627** / AUC **0.721**
- BUS-UCLM skipped (Mendeley login / HTTP 403 from non-interactive download)
- Demo: expert-vs-model compare, lesion measurements; BrEaST measurement agreement offline
- Leakage ablation (grouped vs random splits); literature comparison page
- Decision log D1–D3; **D4 clinician review later revoked**

---

## Phase 2 — Robustness & uncertainty

- Caliper/marker masks + Telea inpaint experiments (E-a / E-b / E-c)
- **MODEL_POLICY:** best E-c seed did **not** pass external-Dice swap → **served model remains v1.0.0**
- Offline TTA uncertainty (Spearman ρ ≈ 0.61); Demo agreement heatmap
- Web Worker inference; self-hosted ORT WASM; threshold sliders; Model Errors explorer
- Clinician outreach / `/review` removed (D4 revoked)

---

## Phase 3 — Clinical polish & portfolio

- Pages: `/bi-rads`, `/surgeons-view`, `/portfolio`
- Auto-filled research PDF (`web/public/report.pdf`) + CI drift check
- Captioned walkthrough video; social preview; accessibility notes
- `CITATION.cff` (Zenodo DOI deferred to owner login)
- No analytics / no cookies; no clinician acknowledgements

---

## Phase 4 prep (this PR / freeze path — not a release yet)

- Zenodo metadata (`.zenodo.json`), freeze checklist, preprint LaTeX package under `paper/`
- Owner still must: mint DOI via release, choose venue, deploy Pages at freeze

---

## Known limitations (include in published notes)

- Not a medical device; not clinician-reviewed
- BUSI has no patient IDs; near-dup grouping ≠ true patient split
- High normal false-positive rate (12/19)
- External classification AUC drops vs internal BUSI
- BUS-UCLM not scored unless owner downloads and re-runs

---

## Checklist before owner clicks “Publish release”

See `docs/FREEZE_CHECKLIST.md`. Remove this DRAFT banner from the GitHub Release body when publishing.
