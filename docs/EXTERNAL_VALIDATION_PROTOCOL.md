# External validation protocol (pre-registration)

**Status:** Pre-registered · **Model freeze:** `v1.0.0` · **Date:** 2026-10-08  
**Evaluation:** Phase 1 scoring of frozen v1.0.0 INT8 is authorized after this protocol was committed (see git history). No tuning on external data.

---

## MODEL_POLICY — when may v2 replace served v1.0.0? (D3, 2026-10-08; fair Phase-4 amendment 2026-10-10)

Pre-registered **before** any Phase 1/2 retraining. A candidate `v2` (e.g. inpainted or multi-dataset) may **replace** the served `v1.0.0` weights on the site **before the Dec 4 freeze** only if **all** of the following hold on committed JSON:

1. **Clean-subset Dice** (BUSI held-out test images with `annotation_flag == false`) ≥ v1.0.0 clean-subset Dice.
2. **External / held-out Dice** — see Phase-4 fairness note below.
3. **AUC** (B vs M on BUSI held-out test) drops by **no more than 0.02** relative to v1.0.0.

### Phase 4 fairness amendment (2026-10-10)

When v2 is trained on **BUSI train + patient-grouped BUS-BRA train**:

- **BUS-BRA held-out is same-source for v2** (not external). Compare v2 held-out Dice to **v1.0.0 INT8 on the identical held-out case IDs** (`results/v2/v1_busbra_heldout.json`), **not** to v1’s full-set Dice (~0.714).
- **BrEaST remains the only truly external test**; require BrEaST Dice ≥ v1 BrEaST Dice.
- Report **seed mean ± SD** and a **paired bootstrap 95% CI** for each delta (v2 − v1) across seeds.
- **Promotion decision uses the 3-seed mean**: if the mean fails any rule, keep v1. Among seeds that individually pass, promote the **median-performing** seed by clean Dice (**not** the best). Also require INT8 ≤ ~25 MB.

If any criterion fails, keep **v1.0.0 served** and publish v2 only as an experiment / Results sidebar. Thresholds, min-area, and architecture operating points for the v1 external report remain frozen (§4). **Phase 1 does not retrain.**

Research demo only — not for clinical use.

---

## 1. Purpose

Report how the **frozen** BUSI-trained model transfers to independent public breast-ultrasound datasets with masks. No hyperparameter, threshold, or architecture tuning on external data for the v1 report. Any post-hoc analysis is labelled exploratory.

## 2. Frozen model

| Field | Value |
|-------|--------|
| Version | `v1.0.0` |
| Artifact | `web/public/models/v1.0.0/busi_unet.onnx` |
| sha256 | `0bbf529dcb46f1f4c01c781f11976e4c0cdca7fc5b2f2b814f028af847743570` |
| Quantization | ONNX Runtime dynamic UINT8 (weights) |
| Also report | FP32 checkpoint `export/full_best.pt` (same architecture / training run) for side-by-side comparison |

Pointer file: `web/public/models/current.json`.

## 3. Preprocessing (identical to BUSI served / browser)

1. Load image as RGB.
2. Resize to **160×160** with the shared half-pixel-center bilinear (`scripts/busi_data.py:resize_rgb_bilinear` / `web/src/lib/image.ts:resizeRgbBilinear`) — the same path used for served INT8 metrics and in-browser inference.
3. Scale to [0, 1], then ImageNet normalize: mean `(0.485, 0.456, 0.406)`, std `(0.229, 0.224, 0.225)`.
4. Masks (when used as ground truth): resize to 160×160 with **nearest** neighbour; binarize at 127. Multi-lesion masks are **OR-merged**.

## 4. Post-processing and decision thresholds (frozen from BUSI validation)

From `results/postprocess.json` / training val lesion-Dice selection — **not** re-tuned on external data:

| Parameter | Value |
|-----------|--------|
| Segmentation threshold | **0.4** |
| Min connected-component area | **40** px (4-connectivity, matching `scipy.ndimage.label` default) |
| Classification threshold (B vs M) | **0.5** |

## 5. Datasets (primary)

### 5.1 BUS-BRA

- Citation: Gómez-Flores et al., *Med Phys* 2024;51:3110–3123 ([doi:10.1002/mp.16812](https://doi.org/10.1002/mp.16812))
- Download: Zenodo [record 8231412](https://zenodo.org/records/8231412) (`BUSBRA.zip`) — **CC BY 4.0**
- ~1,875 images, 1,064 patients, biopsy-proven benign/malignant; manual masks; no normal class
- Use official patient-aware partitions where provided; otherwise keep all patients for a single external test (document which)
- Script stub: `scripts/download_busbra.py` (does not commit data)

### 5.2 BrEaST (BREAST-LESIONS-USG)

- Citation: Pawłowska et al., *Sci Data* 2024;11:148 ([doi:10.1038/s41597-024-02984-z](https://doi.org/10.1038/s41597-024-02984-z))
- Download: TCIA collection [doi:10.7937/9WKK-Q141](https://doi.org/10.7937/9WKK-Q141) — **CC BY 4.0**
- 256 images / 256 patients (benign / malignant / few normal); freehand masks
- Map only tumour masks; check clinical spreadsheet for multi-region annotations
- Script stub: `scripts/download_breast.py` (does not commit data)

### 5.3 BUS-UCLM (secondary)

- Citation: Vallez et al., *Sci Data* 2025;12:242 ([doi:10.1038/s41597-025-04564-2](https://doi.org/10.1038/s41597-025-04564-2) / [PubMed 39934113](https://pubmed.ncbi.nlm.nih.gov/39934113/))
- Download: Mendeley Data [doi:10.17632/7fvgj4jsp7.3](https://doi.org/10.17632/7fvgj4jsp7.3) — dataset **CC BY 4.0**
- Owner steps (manual download → `data/external/busuclm/`): **`docs/BUSUCLM_STEPS.md`**. Loader: `scripts/external/busuclm.py` (skips with `FileNotFoundError` when absent; `scripts/eval_external.py` records skip and merges when present).
- Many normals; exclude Doppler/combined frames when flagged in metadata; patient-cluster bootstrap (38 patients)

**Skipped:** UDIAT (institutional licence agreement); BUSIS (signed release / no redistribution). See `docs/DECISION_LOG.md` D1.

## 6. Metrics (per dataset)

Computed with the same code paths as internal test (`scripts/eval_served_model.py` / future `scripts/eval_external.py`):

- Per-image Dice and IoU: mean + 95% bootstrap CI
- Lesion-only Dice (exclude normals when present)
- Normal-image false-positive rate (non-empty predicted mask | label=normal), when normals exist
- B-vs-M ROC-AUC, sensitivity / specificity @ 0.5, ECE + reliability diagram
- Where patient IDs exist: **patient-clustered** bootstrap for CIs
- Exploratory (labelled): Dice by scanner / BI-RADS if metadata available; caliper-flag rate via existing heuristic

## 7. Analysis and reporting rules

1. Publish an internal (BUSI) vs external table and forest plot with CIs.
2. Negative or worse-than-hoped results are published unchanged.
3. CC BY attribution (credit, licence link, note of resize-to-160) on Results, About, and README.
4. **No tuning** of threshold, min-area, architecture, or training recipe on external data for the v1 report.
5. Any fine-tune / multi-dataset retrain becomes a separate model version (`v2+`); v1 external numbers remain published.

## 8. Honesty checkpoint

Git history of this file **before** the first commit that adds `results/external/*.json` is the pre-registration proof. First external scoring commit must reference model sha256 `0bbf529d…` and this protocol path.

## 9. Out of scope for this pre-registration

- Running the evaluation (Phase 1)
- Committing raw external images
- Changing v1.0.0 weights after this freeze (bugfix wrappers only; new weights → new version)
