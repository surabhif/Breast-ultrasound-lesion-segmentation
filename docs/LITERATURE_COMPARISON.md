# Literature comparison (BUSI & external sets)

**Rule:** every numeric row was read from the cited paper (or marked **[UNVERIFIED]**).  
Research demo — not for clinical use. Updated 2026-10-08 (Phase 1).

## How to read this table

Published BUSI numbers often use **random** train/test splits on a dataset with known near-duplicates (~19% per Pawłowska et al. 2023). This project uses **grouped** near-duplicate splits and reports **served INT8** metrics with bootstrap CIs. Differences in metric definition (per-image mean Dice vs global F1), resolution, and whether normals are included make many rows only partly comparable.

| Paper | Model / setting | Data & split | Reported | Comparable to ours? |
|---|---|---|---|---|
| **This work (v1.0.0 INT8)** | ResNet-18 U-Net 160² | BUSI grouped held-out test n=112 | Dice 0.697; lesion Dice 0.764; AUC 0.931 | Reference |
| **This work (external)** | same frozen INT8 | BUS-BRA n=1875 (patient-cluster CI) | Dice 0.714; AUC 0.638 | External transfer |
| **This work (external)** | same frozen INT8 | BrEaST n=256 | Dice 0.627; lesion 0.629; AUC 0.721 | External transfer |
| Valanarasu & Patel, UNeXt, MICCAI 2022 ([arXiv:2203.04967](https://arxiv.org/abs/2203.04967)) | UNeXt (+ U-Net baselines) | BUSI 647 B+M; **80–20 random** ×3; 256² | UNeXt F1 79.37±0.57, IoU 66.95±1.22 | Partly — random split; F1 aggregation may differ from per-image Dice |
| Musah et al., arXiv:2508.17768 (2025) | nnU-Net ResEnc | BUSI-Full vs de-duplicated; also train BUSI→test BrEaST | Full Dice 0.7514 vs dedup ~0.71–0.72; **BUSI→BrEaST Dice 0.4855** | Yes for OOD logic; different model/resolution |
| Pawłowska et al., *Data in Brief* 2023 ([PMC10293973](https://pmc.ncbi.nlm.nih.gov/articles/PMC10293973/)) | data audit | BUSI | 235 duplicates (~19%); axilla/needle issues; usable counts in letter table | Basis for leakage/dup discussion |
| Gómez-Flores et al., *Med Phys* 2024 ([doi:10.1002/mp.16812](https://doi.org/10.1002/mp.16812)) | CAD benchmarks on BUS-BRA | BUS-BRA official folds | Paper reports multiple CAD metrics — cite paper tables when quoting exact numbers | Dataset paper for our BUS-BRA eval |
| Pawłowska et al., *Sci Data* 2024 ([doi:10.1038/s41597-024-02984-z](https://doi.org/10.1038/s41597-024-02984-z)) | dataset release | BrEaST 256 pts | Dataset description; physical pixel size available | Dataset paper for our BrEaST eval |
| Wang L., *Diagnostics* 16(10):1537 ([doi:10.3390/diagnostics16101537](https://doi.org/10.3390/diagnostics16101537)) | classification AUROC under shift | BUSI + external sets, patient-level | Mean AUROC internal ~0.801 → external ~0.719 | Classification context for our AUC drop |
| Aumente-Maestro et al., *CMPB* 2025 ([doi:10.1016/j.cmpb.2024.108540](https://doi.org/10.1016/j.cmpb.2024.108540)) | multi-task on curated BUSI | Curated BUSI (~450) | Metric values **[UNVERIFIED]** — read before quoting | Likely yes after verification |
| Chen et al., AAU-Net, IEEE TMI 2022 | attention U-Net | BUSI | **[UNVERIFIED]** | Fill only after reading |

## Leakage / duplicates

- Pawłowska 2023 documents **235** duplicated BUSI images and related quality issues.
- This project's pHash cleaning (`results/cleaning_experiment.json`) grouped **601** near-dup clusters; **322** images sit in multi-member groups. Image-level precision/recall vs Pawłowska's Appendix B list is **not computed here** (list not machine-ingested in this repo); treat the 235 figure as the published reference and our pHash groups as an independent operational definition.
- **Leakage ablation** (`results/leakage_ablation.json`): ResNet-18 U-Net, 6 epochs × 3 seeds, train under **grouped** vs **random** splits, evaluate on the **same grouped held-out test**. Mean val lesion-Dice: grouped **0.701** vs random **0.683** (Δ random−grouped ≈ **−0.018**). Mean test Dice: grouped **0.575** vs random **0.545**. On this short schedule, random splits did **not** inflate validation Dice relative to grouped splits — consistent with the earlier tiny-U-Net proxy in `cleaning_experiment.json`. Leakage risk remains (near-dups exist); the inflation effect is run- and schedule-dependent.

## Takeaway for visitors

A high in-domain Dice under random splits is not the same claim as **grouped-split** Dice or **external** Dice. Our external Dice stays in a similar ballpark to internal Dice on BUS-BRA, but **AUC falls sharply** under dataset shift — consistent with the direction reported by Musah et al. (segmentation OOD) and Wang (classification OOD).
