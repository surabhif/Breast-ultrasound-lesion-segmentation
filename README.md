# Breast Ultrasound Lesion Segmentation

**Research demo. Not for clinical use.**

Student research project on the [BUSI](https://doi.org/10.1016/j.dib.2019.104863) breast ultrasound dataset. A network outlines lumps, estimates whether a lump looks harmless or cancerous, keeps near-identical photos together across splits, audits caliper marks, and ships a React web app that runs the trained model fully in the browser.

**Live demo:** [https://surabhif.github.io/Breast-ultrasound-lesion-segmentation/](https://surabhif.github.io/Breast-ultrasound-lesion-segmentation/)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23286597.svg)](https://doi.org/10.5281/zenodo.23286597)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/surabhif/Breast-ultrasound-lesion-segmentation/blob/main/notebooks/01_train_busi.ipynb)

**How to cite:** Fadnavis, S. (2026). Breast Ultrasound Lesion Segmentation (Version 1.0.0). Zenodo. https://doi.org/10.5281/zenodo.23286597. Also `CITATION.cff` / About → How to cite.

---

## What’s in the repo

| Path | Role |
|------|------|
| `scripts/` | Download, clean, train, evaluate, export ONNX, quantize, gallery, Colab notebook generator |
| `notebooks/01_train_busi.ipynb` | Colab end-to-end training |
| `results/` | Real run JSONs, split file, caliper/duplicate audit CSV |
| `docs/HOW_IT_WORKS.md` | Plain-language walkthrough for interviews |
| `docs/EXTERNAL_VALIDATION_PROTOCOL.md` | How outside datasets were scored, and when a new model may replace the served one |
| `docs/DECISION_LOG.md` | Project decisions log |
| `docs/LITERATURE_COMPARISON.md` | Verified literature table + split/leakage notes |
| `docs/ZENODO_STEPS.md` | How the DOI was made / release checklist |
| `docs/FREEZE_CHECKLIST.md` | Owner freeze checklist |
| `docs/SUBMISSION_GUIDE.md` | JEI vs arXiv (no auto-submit) |
| `docs/BUSUCLM_STEPS.md` | How to reproduce the BUS-UCLM test |
| `paper/` | Preprint LaTeX + `main.pdf` (numbers from metrics JSON) |
| `CHANGELOG.md` | App + model version history |
| `web/` | Vite + React + TypeScript demo (onnxruntime-web; PWA offline) |
| `.github/workflows/ci.yml` | Lint, typecheck, build, smoke, parity |
| `.github/workflows/deploy-pages.yml` | GitHub Pages deploy |

The **full BUSI archive is not committed** (redistribution license is unclear). `scripts/download_busi.py` fetches a public Hugging Face mirror.

---

## Headline results (committed run)

Numbers below are for the **served browser model (v1.0.0)**. Outline-overlap score (Dice) is high when the computer outline matches the expert outline.

| Dataset | Outline-overlap (Dice) | Lump-only Dice | Harmless vs cancerous (AUC) | Notes |
|---------|------------------------|----------------|-----------------------------|-------|
| BUSI (held-out test) | **0.697** | **0.764** | **0.931** | n=112 |
| BUS-BRA | **0.714** | 0.714 | **0.638** | Outside set |
| BrEaST | **0.627** | 0.629 | **0.721** | Outside set |
| BUS-UCLM | **0.386** | **0.679** | **0.780** | 640 images / 38 patients |

A bigger v2 model was tried; it was not better on fair tests, so v1 stays.

<details>
<summary>Technical details</summary>

CPU-trained ResNet-18 U-Net, 160×160, grouped held-out test; val-tuned threshold **0.4** + min-component area **40**. Model **v1.0.0**.

| Metric | Full-precision training | Browser model (compressed) |
|--------|-------------------------|----------------------------|
| Test Dice (all) | 0.686 [0.619–0.750] | **0.697** [0.632–0.766] |
| Lesion-only Dice | 0.751 [0.689–0.808] | **0.764** [0.706–0.820] |
| Test IoU | 0.618 | **0.629** |
| Harmless vs cancerous AUC | 0.939 | **0.931** |
| False outlines on normal (no lump) | 12/19 | **12/19** |
| Artifact size | 46.3 MB | **~11.7 MB** |

Later multi-dataset candidates were compared under a fixed swap rule (same-source held-out BUS-BRA vs BrEaST fully external; seed means). Seed-mean clean Dice failed (0.614 vs 0.623), so the site still serves v1.0.0. An earlier caliper-erase retrain also did not pass the outside-set rule. See Results on the site and `CHANGELOG.md`.

Browser scores use the same half-pixel bilinear preprocess + min-area-40 postprocess as evaluation. Sources: `results/full_run.json`, `results/served_int8_test.json`, `results/v2_experiment.json`.

Quick baseline (tiny U-Net, 64×64, ~1 min CPU): Dice ≈ 0.42, AUC ≈ 0.80 — see `results/baseline_quick_run.json`.

</details>

### Cleaning experiment

- **~47%** of images flagged for likely calipers / burned-in text (heuristic audit CSV).
- Outline-overlap (Dice) on all images minus clean images ≈ **+0.063** (flagged frames are easier; lump-only Dice flagged ≈ 0.80 vs clean ≈ 0.70).
- Ranking score is similar on flagged vs clean (~0.94) for this model. Earlier weaker runs showed a larger gap.
- Mixing near-identical photos across train and check still put ~**39%** of check images in a near-copy group also seen in train. A short proxy run did **not** show check-score inflation (≈ −0.005). Leakage risk remains; the effect is run-dependent.

True **patient-level** splits are **not possible**. BUSI has no patient IDs. We keep near-identical photo groups together.

---

## Reproduce

```bash
# Python deps
pip install -r scripts/requirements.txt

# 1) Data (no API key; Hugging Face mirror)
python scripts/download_busi.py
python scripts/prepare_dataset.py

# 2a) Quick CPU baseline (minutes)
python scripts/run_baseline_quick.py

# 2b) Full model (CPU OK; Colab GPU faster)
python scripts/train_full.py --epochs 40 --img-size 160 --batch-size 8 --patience 10 --freeze-epochs 3 --run-cv

# 3) Research export bundle
python scripts/run_cleaning_experiment.py
python scripts/export_gallery.py
python scripts/quantize_onnx.py
python scripts/export_web_results.py
```

**Colab:** open `notebooks/01_train_busi.ipynb`.

**Web locally:**

```bash
cd web && npm ci && npm run dev
```

**Pages build:**

```bash
cd web && VITE_BASE=/Breast-ultrasound-lesion-segmentation/ npm run build
```

---

## Data source used in this build

- Primary: Hugging Face dataset mirror  
  `gymprathap/Breast-Cancer-Ultrasound-Images-Dataset`  
  (`Dataset_BUSI_with_GT`, ~780 images)
- Documented alternative: Kaggle `aryashah2k/breast-ultrasound-images-dataset` (needs API key)
- Original project page: [Cairo University / Al-Dhabyani](https://scholar.cu.edu.eg/?q=afahmy/pages/dataset)

Citation: Al-Dhabyani W, Gomaa M, Khaled H, Fahmy A. Dataset of breast ultrasound images. *Data in Brief*. 2020;28:104863.

---

## Repo layout (training → web)

1. Train → `export/full_best.pt`
2. Export + quantize → `web/public/models/v1.0.0/busi_unet.onnx` (+ `current.json`)
3. `eval_served_model.py` → browser-model test metrics alongside full-precision training
4. `export_web_results.py` → `web/public/results/metrics.json` + failure gallery
5. `export_gallery.py` → ~6 BUSI test samples under `web/public/samples/`

ONNX I/O: `input` `[N,3,160,160]` → `seg_mask` `[N,1,160,160]`, `cls_prob` `[N,1]`.

---

## Limitations

- Outside checks (frozen v1.0.0): BUS-BRA Dice **0.714** / AUC **0.638**; BrEaST Dice **0.627** / AUC **0.721**; BUS-UCLM all-image Dice **0.386** / lesion Dice **0.679** / AUC **0.780** (320/413 false outlines on normal scans; internal Dice 0.697 / AUC 0.931). See Results on the site.
- No patient IDs  
- Caliper detector is a heuristic, not OCR  
- 160² resolution for CPU/browser practicality  
- **Normal-scan false outlines:** **12/19** non-empty masks on normal (no lump) images  
- **Not a medical device**

---

## Site pages

| Path | Role |
|------|------|
| `/` | Home — tour, why/what/how |
| `/demo` | Try the detector in your browser |
| `/results` | Scores, outside checks, experiments |
| `/model-errors` | Hard cases with outline-only silhouettes |
| `/bi-rads` | BI-RADS ultrasound context (a model score is not a BI-RADS category) |
| `/surgeons-view` | Size and margins research framing |
| `/portfolio` | [Surabhi Fadnavis](https://www.linkedin.com/in/surabhi-fadnavis-804065329/) · student research in oncology AI |
| `/about` | Why this project, cite, privacy, credits |
| `/model-card` | Intended use, data, limits |
| `web/public/report.pdf` | [16-page plain-language write-up](https://surabhif.github.io/Breast-ultrasound-lesion-segmentation/report.pdf) |
| `web/public/video/walkthrough.mp4` | Captioned ~1-minute site walkthrough |

Cite with `CITATION.cff` / About → How to cite ([DOI 10.5281/zenodo.23286597](https://doi.org/10.5281/zenodo.23286597)). Analytics skipped (no account); About states no cookies / browser-only inference.

## How this was built

Project by [Surabhi Fadnavis](https://www.linkedin.com/in/surabhi-fadnavis-804065329/). The code, analysis, text, and video were produced with AI tools (**Cursor**). High-school research project — **not for clinical use**.

## Credits

Project by **[Surabhi Fadnavis](https://www.linkedin.com/in/surabhi-fadnavis-804065329/)** (high-school senior, Georgia). Structure mirrors her [PatchCamelyon lymph-node demo](https://github.com/surabhif/Lymph-node-metastasis-detector). See also the [pathology report explainer](https://github.com/surabhif/Pathology-report-explainer).

MIT license for code. BUSI images remain under their original terms — only a minimal cited sample ships in `web/public/samples/`.
