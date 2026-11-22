# v1.1 experiment note (plain language)

**Status:** Write-up only (owner decision). Served model stays **v1.0.0**.  
**Not on the site UI** — no Results table, no candidate ONNX under `web/public/models/`.  
**Research demo — not for clinical use.**  
**Source JSON:** `results/v1_1_experiment.json`

---

## What we asked

Can a slightly larger BUSI-only U-Net beat the served v1.0.0 model under the project’s approved swap rule, without peeking at the held-out test set while choosing settings?

## What stayed fixed (same as v1.0.0)

- Cleaned BUSI images and masks (same cleaning pipeline)
- Committed leakage-safe splits in `results/splits.json` (fold 0 train/val + frozen test of 112 images)
- Loss recipe: positive-weighted BCE + soft Dice for outlines, BCE for benign-vs-malignant on lesion cases
- Checkpoint on **validation lesion Dice**; threshold and min-area chosen on **validation only**
- Display “no-lump” gate: report both the fixed **0.96** gate and a gate re-tuned on validation only
- Outside sets scored after settings were locked — no tuning on them

## What we tried

| Candidate id | Backbone | Input size | INT8 size | Why |
|---|---|---|---|---|
| `r18_224` | ResNet-18 U-Net | 224² | 11.7 MB | Same backbone as v1, higher resolution |
| `r18_256` | ResNet-18 U-Net | 256² | 11.7 MB | Same backbone, still higher resolution |
| `r34_224` | ResNet-34 U-Net | 224² | 21.3 MB | Stronger encoder (EfficientNet-B0 was an option; ResNet-34 already in-repo) |

All INT8 models stayed under the ~25 MB browser budget. Runs were on the Cursor VM (CPU torch).

## Swap rule (pass / fail)

**Full MODEL_POLICY (D3)** — all must pass before a live swap is allowed:

1. Clean-subset Dice on BUSI test ≥ v1  
2. Outside Dice (BUS-BRA and BrEaST for this BUSI-only recipe) ≥ v1  
3. AUC drop ≤ **0.02**  
4. INT8 size ≤ ~25 MB  

**Abbreviated check** (Dice ≥ v1 and AUC drop ≤ 0.02) is also reported for the PR table.  
**This experiment never rewrote `current.json`.** Owner decision: keep docs + `results/v1_1*.json` only — do not show a candidate on Results or ship ONNX under `web/public/`.

## Held-out BUSI results (INT8)

| Setting | Dice [95% CI] | Lesion Dice | IoU | Clean Dice | AUC [95% CI] | Normal FP raw / 0.96 / retuned | ORT CPU ms (p50) |
|---|---|---|---|---|---|---|---|
| **v1.0.0 (served)** | **0.697** [0.632, 0.766] | **0.764** | **0.630** | **0.623** | **0.931** | **12** / 10* / — | ~18 |
| candidate r18 @224 | **0.703** [0.639, 0.767] | 0.772 | 0.635 | 0.629 | **0.936** [0.883, 0.976] | 12 / 8 / 8 (thr 0.97) | ~32 |
| candidate r18 @256 | 0.674 [lower] | 0.758 | 0.603 | 0.593 | 0.926 | 14 / 9 / 12 (thr 0.855) | ~24 |
| candidate r34 @224 | 0.679 | 0.775 | 0.613 | 0.646 | 0.934 | 15 / 8 / 9 (thr 0.905) | ~43 |

\*v1 0.96 gate figure from committed `results/no_lump_gate.json`.

## Outside-set scores

| Setting | BUS-BRA Dice | BrEaST Dice | BUS-UCLM |
|---|---|---|---|
| v1.0.0 | **0.714** | **0.627** | 0.386 (committed earlier; not re-scored here) |
| r18_224 | 0.696 | 0.589 | **not available** on this VM (manual Mendeley download) |
| r18_256 | 0.633 | 0.575 | skipped |
| r34_224 | 0.665 | 0.585 | skipped |

## What happened (including failures)

1. **`r18_224`** — Best overall BUSI outline + AUC story. Dice 0.703 ≥ v1 0.697 and AUC 0.936 (improved, drop within 0.02). Clean Dice also ≥ v1. **Fails full D3** because BUS-BRA (0.696 &lt; 0.714) and BrEaST (0.589 &lt; 0.627) got worse. Passes the abbreviated Dice+AUC check only. **Owner decision: write-up only** — not shown on Results and not shipped as a site candidate.
2. **`r18_256`** — Higher resolution did **not** help. Held-out Dice fell to 0.674; clean Dice 0.593. External scores also worse. **Fail.**
3. **`r34_224`** — Stronger backbone improved clean Dice (0.646) and kept AUC, but overall held-out Dice fell to 0.679 (fails abbreviated Dice rule). External still below v1. INT8 21.3 MB (under 25). **Fail.**

**Verdict:** No candidate may replace v1.0.0. Live model remains **v1.0.0**. Numbers live in `results/v1_1_experiment.json` and this note — not on the public Results page.

## How to reproduce

```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r scripts/requirements.txt
python scripts/download_busi.py
# Keep committed results/splits.json (restore from git if prepare_dataset rewrote it)
python scripts/run_v1_1_experiment.py --epochs 40 --patience 10 --freeze-epochs 3
```

Optional outside data: `python scripts/download_busbra.py`, `python scripts/download_breast.py`, and BUS-UCLM via `docs/BUSUCLM_STEPS.md`.

## Honesty

Negative and mixed results stay in the table. Latency numbers are onnxruntime **CPU** medians (browser WASM is typically slower). BUS-UCLM was not present on this VM, so that column is blank for candidates.
