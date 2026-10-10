# Breast Ultrasound Lesion Segmentation: Research Write-up

Version 1.0.0 · Site-only research report  
Author: Surabhi Fadnavis (high-school senior, Georgia)

> Research demo — not for clinical use.

## Abstract
Breast ultrasound helps doctors look at breast lumps, especially when mammograms are hard to read in dense tissue. This student project builds a program that outlines those lumps on ultrasound pictures and estimates how well the program tells benign from cancerous lumps. It was trained on one public image collection and checked on three others from different hospitals. The main quality measure is an outline-overlap score (Dice), which is high when the computer outline matches the expert outline. On held-out training-collection images, the browser version reaches 0.697 overall and 0.764 on images that contain a lump. On two outside collections, outline scores stay similar (0.714 and 0.627), while telling benign from cancerous gets harder after the hospital and scanner change. On a third outside collection, empty or normal images remain difficult: false outlines pull the all-image score down to 0.386 even though the lesion-only score is 0.679. The write-up also studies near-duplicate frames, burned-in measurement marks, and whether outlines stay stable when a picture is flipped. A later mixed-collection retrain improved some outside scores but did not pass a pre-agreed replacement rule, so the site still serves the original model. This is an educational research demonstration, not a medical device, and must not be used for diagnosis or care decisions.

## Data
Annotation-flag rate 46.9% (366/780).
**BUS-UCLM** (Vallez et al., 2025; Mendeley Creative Commons Attribution 4.0) is scored for the frozen served browser model: n=640 / 38 patients (43 Doppler/combined frames excluded). All-image outline-overlap score **0.386** [0.326, 0.449]; lesion outline-overlap score **0.679** [0.593, 0.755]; area under the receiver-operating curve (AUC) **0.780**. Normal false positives dominate the all-image figure (320/413) — the same known weakness as on BUSI (12/19). Prefer the lesion outline-overlap score for cross-dataset comparison (between BrEaST and BUS-BRA).
External: BUS-BRA n=1875; BrEaST n=256 (Pawłowska et al.).

## Results highlights
Leakage Δ -0.022; E-a flagged/clean 0.764/0.628; E-c external 0.626/0.608; TTA ρ 0.613; cov80 0.778; meas diam r 0.697 (n=252), ≥20mm discordance 17.1%; v2 clean mean 0.614 (Δ -0.009).

## AI-assistance
Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (Cursor).
