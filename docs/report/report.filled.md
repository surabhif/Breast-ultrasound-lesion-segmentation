# Breast Ultrasound Lesion Segmentation: Research Write-up

Version 1.0.0 · Site-only research report  
Author: Surabhi Fadnavis (high-school senior, Georgia)

> Research demo — not for clinical use.

## Abstract
Served INT8 Dice 0.697, lesion Dice 0.764, AUC 0.931; BUS-BRA Dice 0.714 AUC 0.638; BrEaST Dice 0.627 AUC 0.721.

## Data
Annotation-flag rate 46.9% (366/780).
**BUS-UCLM** (Vallez et al., 2025; Mendeley CC BY 4.0) is scored for frozen v1.0.0 INT8: n=640 / 38 patients (43 Doppler/combined frames excluded). All-image Dice **0.386** [0.326, 0.449]; lesion Dice **0.679** [0.593, 0.755]; AUC **0.780**. Normal false positives dominate the all-image figure (320/413) — the same known weakness as on BUSI (12/19). Prefer lesion Dice for cross-dataset comparison (between BrEaST and BUS-BRA).
External: BUS-BRA n=1875; BrEaST n=256 (Pawłowska et al.).

## Results highlights
Leakage Δ -0.022; E-a flagged/clean 0.764/0.628; E-c external 0.626/0.608; TTA ρ 0.613; cov80 0.778; meas diam r 0.697 (n=252), ≥20mm discordance 17.1%.

## AI-assistance
Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (Cursor).
