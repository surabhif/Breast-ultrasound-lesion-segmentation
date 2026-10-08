# Breast Ultrasound Lesion Segmentation: Research Write-up

Version 1.0.0 · Site-only research report  
Author: Surabhi Fadnavis (high-school senior, Georgia)

> Research demo — not for clinical use.

## Abstract
Served INT8 Dice 0.697, lesion Dice 0.764, AUC 0.931; BUS-BRA Dice 0.714 AUC 0.638; BrEaST Dice 0.627 AUC 0.721.

## Data
Annotation-flag rate 46.9% (366/780).
BUS-UCLM was not included because its Mendeley Data download requires a login (the request returned HTTP 403).
External: BUS-BRA n=1875; BrEaST n=256 (Pawłowska et al.).

## Results highlights
Leakage Δ -0.022; E-a flagged/clean 0.764/0.628; E-c external 0.626/0.608; TTA ρ 0.613; cov80 0.778; meas diam r 0.697 (n=252), ≥20mm discordance 17.1%.

## AI-assistance
Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (Cursor).
