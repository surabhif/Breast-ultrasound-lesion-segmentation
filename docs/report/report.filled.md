# Breast Ultrasound Lesion Segmentation: Research Write-up

**Version 1.0.0 · Site-only research report (not a journal submission)**  
**Author:** Surabhi Fadnavis (high-school senior, Georgia)  
**Live demo:** https://surabhif.github.io/Breast-ultrasound-lesion-segmentation/  
**Repository:** https://github.com/surabhif/Breast-ultrasound-lesion-segmentation

> Research demo — not for clinical use. Not clinician-reviewed. Not for diagnosis, screening, or care decisions.

---

## Abstract

This high-school research project trains a ResNet-18 U-Net with an auxiliary benign-vs-malignant head on the BUSI breast ultrasound dataset, exports an INT8 ONNX model for fully in-browser inference, and reports honest internal and external metrics. On the held-out BUSI test set the **served INT8** model reaches Dice **0.697** (lesion-only **0.764**) and ROC-AUC **0.931**. External validation on BUS-BRA and BrEaST keeps segmentation closer to internal Dice (**0.714** / **0.627**) while classification AUC drops (**0.638** / **0.721**). Cleaning, leakage, caliper-inpainting, and TTA uncertainty experiments are included. Venue for this write-up: **site-only** (D5).

## Introduction

Breast ultrasound helps characterize masses, especially in dense breasts. Public datasets enable student projects but hide pitfalls: near-duplicate frames, burned-in calipers, and missing patient IDs. This project asks whether a small model can outline lesions in the browser — and how honest the scores remain under those pitfalls.

Related educational pages on the site cover BI-RADS context (a model score is not a BI-RADS category) and a surgeon's-view framing of size/margins (imaging size is not pathologic T-stage; model outlines are not surgical margins).

## Data

### BUSI (internal)

BUSI (Al-Dhabyani et al., *Data in Brief*, 2020) provides ~780 PNG ultrasound images labeled benign, malignant, or normal with masks. Multi-mask lesions are OR-merged. BUSI publishes **no patient IDs**; we group perceptual-hash near-duplicates so groups never cross splits. Annotation-flag rate (heuristic): **46.9%** (366 / 780).

### External (primary)

Per pre-registered protocol (`docs/EXTERNAL_VALIDATION_PROTOCOL.md`) and owner decision D1:

- **BUS-BRA** (Gómez-Flores et al., 2024; Zenodo CC BY 4.0): n=1875, patients≈1064
- **BrEaST** (Pawłowska et al., 2024; TCIA CC BY 4.0): n=256, patients=256
- **BUS-UCLM**: skipped (BUS-UCLM archive not found under data/external/busuclm/. Mendeley Data (doi:10.17632/7fvgj4jsp7.3) returned HTTP 403 wit)

## Methods

- Architecture: ResNet-18 ImageNet encoder + slim U-Net decoder (160×160) with auxiliary classification head
- Training: grouped stratified splits; paired augmentations; checkpoint on lesion Dice; val-tuned seg threshold **0.4**, min-component area **40**
- Served artifact: INT8 ONNX `models/v1.0.0/busi_unet.onnx` (sha256 0bbf529d…)
- Browser: onnxruntime-web (WASM), Web Worker inference, same morphology post-process as Python eval
- Phase 2 extras: Telea caliper inpaint experiments, offline TTA uncertainty, Demo threshold sliders

## Results

### Internal (BUSI held-out test)

| Metric | FP32 training | Served INT8 |
|--------|---------------|-------------|
| Dice (all) | n/a | **0.697** |
| Lesion Dice | n/a | **0.764** |
| IoU | n/a | **0.630** |
| ROC-AUC | n/a | **0.931** |
| Normal FP masks | ?/? | **12/19** |

Sources: `results/full_run.json`, `results/served_int8_test.json`.

### External validation (frozen v1.0.0 INT8)

| Set | Dice | Lesion Dice | AUC |
|-----|------|-------------|-----|
| BUSI internal | 0.697 | 0.764 | 0.931 |
| BUS-BRA | 0.714 | 0.714 | 0.638 |
| BrEaST | 0.627 | 0.629 | 0.721 |

Sources: `results/external/busbra.json`, `results/external/breast.json`.

### Leakage ablation

Short schedule (6 epochs × seeds 42,43,44), same grouped test: random vs grouped splits did not inflate validation Dice on this run (mean Δ val Dice random−grouped ≈ **-0.022**). Residual leakage risk remains because patient IDs are absent. Source: `results/leakage_ablation.json`.

### Caliper / inpaint experiment

Flagged vs clean Dice gap on original test: flagged **0.764** vs clean **0.628**. Erasing markers (E-a) did not collapse flagged Dice toward clean. Best E-c retrain seed did **not** replace served v1.0.0: external Dice failed the pre-registered swap rule (BUS-BRA 0.626 vs v1 0.714; BrEaST 0.608 vs v1 0.627). Source: `results/inpaint_experiment.json`.

### Uncertainty (TTA)

Spearman(ρ) between TTA disagreement and 1−Dice ≈ **0.613** on BUSI test (n=112). Risk–coverage at 80% keep ≈ Dice **0.778**. Interpretation: agreement under flips — not a calibrated error probability. Source: `results/uncertainty.json`.

### Measurement agreement (BrEaST)

Model vs expert longest diameter (mm) Pearson proxy ≈ **0.697** (n=252); ≥20 mm threshold discordance ≈ **17.1%**. Research only — not pathologic T-stage. Source: `results/measurement_agreement.json`.

## Limitations

- No patient IDs → residual near-duplicate / patient leakage risk
- Domain shift: classification AUC drops sharply on externals
- Calipers / HUD may still act as shortcuts
- 160² resolution loses fine detail; normal-image false positives (12/19)
- Not clinically validated; no clinician review (D4 revoked)

## Ethics and licensing

Code is MIT. Full BUSI is not redistributed (license unclear); cite Al-Dhabyani et al. 2020. External demo imagery uses CC BY sets with attribution. Site social preview uses CC BY external pixels (not BUSI). Research demo only.

## AI-assistance statement

How this was built: The code, analysis scripts, and most site and report text were produced with AI coding tools (Cursor). Surabhi Fadnavis owns the research questions, interpretation, presentation choices, and final review. This is a high-school research project — not clinician-reviewed and not for clinical use.

## References

1. Al-Dhabyani W, et al. Dataset of breast ultrasound images. Data in Brief. 2020;28:104863.
2. Mendelson EB, et al. ACR BI-RADS® Ultrasound. In: ACR BI-RADS® Atlas. Reston, VA: ACR; 2013.
3. Gómez-Flores W, et al. BUS-BRA breast ultrasound dataset. Zenodo; 2024. CC BY 4.0.
4. Pawłowska A, et al. BrEaST — Breast Cancer Dataset. TCIA; 2024. CC BY 4.0.
5. Moran MS, et al. SSO–ASTRO consensus guideline on margins for breast-conserving surgery. 2014.
6. Project repository: https://github.com/surabhif/Breast-ultrasound-lesion-segmentation

---

*Numbers in this PDF are auto-filled from committed results JSON by `scripts/build_report_pdf.py`. A CI check fails if PDF figures drift from those JSON files.*
