# Release notes for site / software v1.0

**Suggested tag (owner-only):** `v1.0.0`  
**Suggested title:** `v1.0.0 — Dec 4 freeze (BUSI demo + external validation)`  
**Live demo:** https://surabhif.github.io/Breast-ultrasound-lesion-segmentation/  
**Research demo — not for clinical use.**

---

## Summary

First freeze-ready release of the breast ultrasound lesion segmentation research demo: in-browser inference, BUSI metrics with honest leakage and caliper audits, outside checks on BUS-BRA, BrEaST, and BUS-UCLM, reliability experiments (served model unchanged), and context pages / portfolio polish.

**Credit:** Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (Cursor).

---

## Versioning and parity

- Served model frozen as **v1.0.0** ResNet-18 U-Net (~11.7 MB download), 160×160
- Shared half-pixel bilinear preprocess + min-component area **40** (browser ↔ Python parity)
- CI: lint, typecheck, build, smoke, morphology/parity checks
- Grouped near-duplicate splits on BUSI (no patient IDs)
- Written protocol for outside checks and when a new model may replace the served one

### Headline BUSI results (served browser model)

| Metric | Value |
|--------|-------|
| Test Dice (all) | 0.697 [0.632–0.766] |
| Lesion-only Dice | 0.764 [0.706–0.820] |
| Harmless vs cancerous AUC | 0.931 |
| False outlines on normal (no lump) | 12/19 |

(Full-precision training checkpoint reported alongside the browser model on Results / model card.)

---

## Outside checks

- Frozen **v1.0.0** scored on **BUS-BRA** and **BrEaST** (no outside tuning)
- BUS-BRA Dice **0.714** / AUC **0.638**; BrEaST Dice **0.627** / AUC **0.721**
- BUS-UCLM scored (owner local copy): all-image Dice **0.386**, lesion Dice **0.679**, AUC **0.780** (320/413 false outlines on normal scans; 43 Doppler/combined frames excluded)
- Demo: expert-vs-model compare, lesion measurements; BrEaST measurement agreement offline
- Leakage ablation (grouped vs random splits); literature comparison page

---

## Checking reliability and uncertainty

- Caliper/marker masks + Telea erase-and-retrain experiments
- Best retrain seed did **not** pass the outside-Dice swap rule → **served model remains v1.0.0**
- Offline flip-based uncertainty (Spearman ρ ≈ 0.61); Demo agreement heatmap
- Web Worker inference; self-hosted runtime; threshold sliders; Model Errors explorer

---

## Context pages and portfolio

- Pages: `/bi-rads`, `/surgeons-view`, `/portfolio`
- Auto-filled research PDF (`web/public/report.pdf`, 16-page plain-language write-up) + CI drift check
- Captioned walkthrough video; social preview; accessibility notes
- `CITATION.cff` + Zenodo DOI **10.5281/zenodo.23286597**
- No analytics / no cookies

---

## Freeze path

- Zenodo metadata (`.zenodo.json`), freeze checklist, preprint LaTeX package under `paper/`
- **DOI minted:** https://doi.org/10.5281/zenodo.23286597 (owner GitHub Release → Zenodo)
- Owner still must: choose venue, deploy Pages at freeze if not already live

---

## Known limitations (include in published notes)

- Not a medical device
- BUSI has no patient IDs; near-dup grouping ≠ true patient split
- High false-outline rate on normal (no lump) images (12/19)
- Outside ranking scores drop vs internal BUSI
- BUS-UCLM all-image Dice is pulled down by false outlines on normal scans (320/413); prefer lesion Dice for cross-dataset comparison

---

## Checklist before owner publishes a release

See `docs/FREEZE_CHECKLIST.md`.
