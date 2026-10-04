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
| `web/` | Vite + React + TypeScript demo (onnxruntime-web) |
| `.github/workflows/deploy-pages.yml` | GitHub Pages deploy |

The **full BUSI archive is not committed** (redistribution license is unclear). `scripts/download_busi.py` fetches a public Hugging Face mirror.

---

## Headline results (committed run)

From `results/full_run.json` / `web/public/results/metrics.json` (CPU-trained ResNet-18 U-Net, 160×160, grouped held-out test; val-tuned threshold 0.4 + min-component area 40):

| Metric | Value |
|--------|-------|
| Test Dice (all) | **0.686** (95% CI 0.619–0.750) |
| Lesion-only Dice | **0.751** (95% CI 0.689–0.808) |
| Test IoU | **0.618** |
| Benign vs malignant ROC-AUC | **0.939** |
| Served ONNX | **~11.7 MB** dynamic INT8 |

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
2. Export ONNX → `web/public/models/busi_unet.onnx`
3. Quantize if helpful (INT8 adopted here)
4. `export_web_results.py` → `web/public/results/metrics.json` + failure gallery
5. `export_gallery.py` → ~6 BUSI test samples under `web/public/samples/`

ONNX I/O: `input` `[N,3,160,160]` → `seg_mask` `[N,1,160,160]`, `cls_prob` `[N,1]`.

---

## Limitations

- Single public dataset; domain shift untested  
- No patient IDs  
- Caliper detector is a heuristic, not OCR  
- 160² resolution for CPU/browser practicality  
- **Not a medical device**

---

## Credits

Project by **Surabhi Fadnavis** (high-school senior, aspiring surgical oncologist). Structure mirrors her [PatchCamelyon lymph-node demo](https://github.com/surabhif/Lymph-node-metastasis-detector). Substantial implementation assistance from an AI coding agent (Cursor); Surabhi owns the research questions, interpretation, and presentation.

MIT license for code. BUSI images remain under their original terms — only a minimal cited sample ships in `web/public/samples/`.
