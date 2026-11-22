# Breast Ultrasound Lesion Segmentation: Research Write-up

Project v1.0.1 · served model v1.0.0 · Site-only research report  
Author: Surabhi Fadnavis (high-school senior, Georgia)

> Research demo — not for clinical use.

## Abstract
Breast ultrasound helps doctors look at breast lumps, especially when mammograms are hard to read in dense tissue. This student project builds a program that outlines those lumps on ultrasound pictures and estimates how well it does at telling harmless from cancerous lumps. It was trained on one public image collection and checked on three others from different hospitals. The main quality measure is an outline-overlap score (Dice), which is high when the computer outline matches the expert outline. On images saved for testing, the browser version reaches 0.697 overall. On images that contain a lump, the outline match is 0.764. On two outside collections, raw outline scores stay similar (0.714 and 0.627), while telling harmless from cancerous lumps gets harder after the hospital and scanner change. A display-only “no lump” outline gate (hide when the strongest outline pixel is below 0.96) makes those outside Dice scores worse (BUS-BRA 0.714 → 0.653; BrEaST 0.627 → 0.572); the harmless-versus-cancerous ranking score stays the same. On a third outside collection, pictures without lumps remain difficult: false outlines pull the overall score down to 0.386, even though on images that contain a lump the outline match is 0.679 (not re-scored with the gate when the archive was unavailable). The write-up also studies near-identical photos, burned-in measurement marks, and whether outlines stay stable when a picture is flipped. A retrained version did better on some outside images but not consistently, so the original stays. This is an educational research demonstration, not a medical device, and must not be used for diagnosis or care decisions.

## Data
Annotation-flag rate 46.9% (366/780).
**BUS-UCLM** (Vallez et al., 2025; Mendeley Creative Commons Attribution 4.0) is scored for the frozen browser model: n=640 / 38 patients (43 Doppler/combined frames excluded). Overall outline-overlap score **0.386** [0.326, 0.449]; on images that contain a lump, **0.679** [0.593, 0.755]; area under the receiver-operating curve (AUC) **0.780**. Normal false positives dominate the overall figure (320/413) — the same known weakness as on BUSI (12/19). Prefer the score on images that contain a lump when comparing across collections (between BrEaST and BUS-BRA).
External: BUS-BRA n=1875 — raw Dice **0.714** / with no-lump gate **0.653** (worse); ranking score **0.638** unchanged. BrEaST n=256 (Pawłowska et al.) — raw Dice **0.627** / with gate **0.572** (worse); lesion **0.629 → 0.573**; IoU **0.543 → 0.502**; normal false outlines **2/4 → 2/4**; ranking score **0.721** unchanged.

## Results highlights
Leakage Δ -0.022; E-a flagged/clean 0.764/0.628; E-c external 0.626/0.608; TTA ρ 0.613; cov80 0.778; meas diam r 0.697 (n=252), ≥20mm discordance 17.1%; v2 clean mean 0.614 (Δ -0.009).

## AI-assistance
Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (Cursor).
