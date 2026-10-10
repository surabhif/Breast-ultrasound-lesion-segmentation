# Breast Ultrasound Lesion Segmentation

**Research demo, not for clinical use.**

End-to-end student research project on the [BUSI](https://doi.org/10.1016/j.dib.2019.104863) breast ultrasound dataset: a U-Net that segments lesions, an auxiliary benign-vs-malignant score, grouped splits that respect near-duplicates, an audit of caliper/annotation artifacts, and a React web app that runs the trained ONNX model **fully in the browser**.

**Live demo:** [https://surabhif.github.io/Breast-ultrasound-lesion-segmentation/](https://surabhif.github.io/Breast-ultrasound-lesion-segmentation/)  
*(Requires GitHub Pages enabled for this repo — Settings → Pages → Source: GitHub Actions.)*

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/surabhif/Breast-ultrasound-lesion-segmentation/blob/main/notebooks/01_train_busi.ipynb)

---

## What’s in the repo

| Path | Role |
|------|------|
| `scripts/` | Download, clean, train, evaluate, export ONNX, quantize, gallery, Colab notebook generator |
| `notebooks/01_train_busi.ipynb` | Colab end-to-end training |
| `results/` | Real run JSONs, split file, caliper/duplicate audit CSV |
| `docs/HOW_IT_WORKS.md` | Plain-language walkthrough for interviews |
| `docs/EXTERNAL_VALIDATION_PROTOCOL.md` | Pre-registered BUS-BRA / BrEaST protocol + MODEL_POLICY (v1 scored) |
| `docs/DECISION_LOG.md` | Owner decisions (D1–D3; D4 revoked; D5–D16) |
| `docs/LITERATURE_COMPARISON.md` | Verified literature table + split/leakage notes |
| `docs/ZENODO_STEPS.md` / `FREEZE_CHECKLIST.md` | Owner DOI mint + Dec 4 freeze |
| `docs/SUBMISSION_GUIDE.md` | JEI vs arXiv (no auto-submit) |
| `docs/BUSUCLM_STEPS.md` | Optional BUS-UCLM download → external table |
| `paper/` | Preprint LaTeX + `main.pdf` (numbers from metrics JSON) |
| `CHANGELOG.md` | App + model version history |
| `web/` | Vite + React + TypeScript demo (onnxruntime-web; PWA offline) |
| `.github/workflows/ci.yml` | Lint, typecheck, build, smoke, parity |
| `.github/workflows/deploy-pages.yml` | GitHub Pages deploy |

The **full BUSI archive is not committed** (redistribution license is unclear). `scripts/download_busi.py` fetches a public Hugging Face mirror.

---

## Headline results (committed run)

**Phase 4:** multi-dataset v2 candidates under the **fair** MODEL_POLICY (BUS-BRA = same-source held-out vs v1 on the identical split; BrEaST external; seed-mean + median passer). Seed-mean clean Dice failed (0.614 vs 0.623) → **served model stays v1.0.0**. See Results → “Phase 4 model candidates vs v1” and `results/v2_experiment.json`.

**Phase 2:** inpaint-retrain did not pass the external-Dice swap rule. See Results → “What if we erase the calipers?” and CHANGELOG.


CPU-trained ResNet-18 U-Net, 160×160, grouped held-out test; val-tuned threshold **0.4** + min-component area **40**. Model **v1.0.0**.

| Metric | FP32 (training) | INT8 ONNX (**served**) |
|--------|-----------------|-------------------------|
| Test Dice (all) | 0.686 [0.619–0.750] | **0.697** [0.632–0.766] |
| Lesion-only Dice | 0.751 [0.689–0.808] | **0.764** [0.706–0.820] |
| Test IoU | 0.618 | **0.629** |
| Benign vs malignant ROC-AUC | 0.939 | **0.931** |
| Normal false-positive masks | 12/19 | **12/19** |
| Artifact size | 46.3 MB | **~11.7 MB** |

Served INT8 metrics use the same half-pixel bilinear preprocess + min-area-40 postprocess as the browser (see `CHANGELOG.md`).

The demo runs the INT8 weights; Results and the model card show both columns. Sources: `results/full_run.json`, `results/served_int8_test.json`.

Quick baseline (tiny U-Net, 64×64, ~1 min CPU): Dice ≈ 0.42, AUC ≈ 0.80 — see `results/baseline_quick_run.json`.

### Cleaning experiment (honest)

- **~47%** of images flagged for likely calipers / burned-in text (heuristic audit CSV).
- Dice(all) − Dice(clean) ≈ **+0.063** (flagged frames are easier; lesion Dice flagged ≈ 0.80 vs clean ≈ 0.70).
- Classification AUC is similar on flagged vs clean (~0.94) for this stronger model — earlier weaker runs showed a larger gap.
- Random (non-grouped) splits still put ~**39%** of val images in a near-dup group also seen in train; a short tiny-U-Net proxy on this run did **not** show val Dice inflation (≈ −0.005) — leakage risk remains, but the effect is run-dependent.

True **patient-level** splits are **not possible** — BUSI has no patient IDs. We keep perceptual-hash near-duplicate groups together.

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
3. `eval_served_model.py` → INT8 test metrics alongside FP32
4. `export_web_results.py` → `web/public/results/metrics.json` + failure gallery
5. `export_gallery.py` → ~6 BUSI test samples under `web/public/samples/`

ONNX I/O: `input` `[N,3,160,160]` → `seg_mask` `[N,1,160,160]`, `cls_prob` `[N,1]`.

---

## Limitations

- External validation (frozen v1.0.0 INT8): BUS-BRA Dice **0.714** / AUC **0.638**; BrEaST Dice **0.627** / AUC **0.721** (internal Dice 0.697 / AUC 0.931). BUS-UCLM skipped (Mendeley access). See Results and `docs/EXTERNAL_VALIDATION_PROTOCOL.md`.
- No patient IDs  
- Caliper detector is a heuristic, not OCR  
- 160² resolution for CPU/browser practicality  
- **Normal-image false positives:** **12/19** non-empty masks on normals (FP32 and served INT8)  
- **Not a medical device**

---

## Phase 3 pages

| Path | Role |
|------|------|
| `/bi-rads` | BI-RADS ultrasound context (score ≠ category) |
| `/surgeons-view` | Size/margins research framing |
| `/portfolio` | Surabhi Fadnavis · student research in oncology AI |
| `web/public/report.pdf` | Auto-filled research write-up (site-only venue) |
| `web/public/video/walkthrough.mp4` | Captioned 60–90s site walkthrough |

Cite with `CITATION.cff` / About → How to cite. A Zenodo DOI is not minted yet (needs owner login). Analytics skipped (no account); About states no cookies / browser-only inference.

## How this was built

Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (**Cursor**). High-school research project — not clinician-reviewed and **not for clinical use**.

## Credits

Project by **Surabhi Fadnavis** (high-school senior, Georgia). Structure mirrors her [PatchCamelyon lymph-node demo](https://github.com/surabhif/Lymph-node-metastasis-detector). See also the [pathology report explainer](https://github.com/surabhif/Pathology-report-explainer).

MIT license for code. BUSI images remain under their original terms — only a minimal cited sample ships in `web/public/samples/`.
