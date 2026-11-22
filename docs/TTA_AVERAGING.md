# Test-time averaging experiment (v1.0.0)

**Research demo. Not for clinical use.**

**Credit:** Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (Cursor).

**Decision:** Do **not** turn averaging on in the demo. Keep single-view inference as the default. Served weights stay **v1.0.0** (unchanged).

---

## What we tried

At test time only (no retraining), we ran the same frozen browser model several times on slightly changed views of each image, then **averaged**:

- the soft outline map (after putting each view back to the original pose)
- the harmless vs cancerous score

Views tried:

| Preset | Views |
|---|---|
| `single` | original only |
| `hflip2` | original + left–right flip |
| `hflip_scale` | those two + mild zoom in/out (0.95 / 1.05) |
| `hflip_shift` | those two + four 4-pixel shifts |

The live-site **0.96 “hide outline if likely no lump”** display gate was applied the same way when scoring outlines (peak soft-mask value below 0.96 → empty outline). Script: `scripts/eval_tta_averaging.py`. Numbers: `results/tta_averaging.json`.

---

## Keep rule

Keep averaging in the app only if:

1. Outline accuracy improves (lesion Dice up, or all-image Dice up without hurting lesion Dice)
2. AUC is not hurt (drop ≤ about 0.005)
3. In-browser time stays under about **2×** single-view

---

## BUSI held-out test (same published split)

Gate on. 95% bootstrap CIs. Offline ONNX ms on this VM.

| Setting | Dice | Lesion Dice | IoU | AUC | False outlines on normal | ONNX ms | × |
|---|---|---|---|---|---|---|---|
| Single | 0.710 [0.644, 0.777] | 0.758 [0.696, 0.816] | 0.645 [0.581, 0.708] | 0.929 | 10 / 19 | ~12 | 1.00 |
| Flip average (2) | 0.718 [0.653, 0.784] | 0.757 [0.692, 0.817] | 0.657 [0.593, 0.718] | 0.933 | 9 / 19 | ~24 | 1.96 |
| + mild zoom (4) | 0.728 [0.662, 0.792] | 0.747 [0.682, 0.808] | 0.667 [0.603, 0.730] | 0.942 | 7 / 19 | ~47 | 3.90 |
| + shifts (6) | 0.717 [0.651, 0.783] | 0.756 [0.693, 0.815] | 0.655 [0.591, 0.716] | 0.935 | 9 / 19 | ~71 | 5.82 |

**Reading the table:** Flip averaging nudged all-image Dice up a little and cleared one more false outline on a normal scan, and AUC was fine. But **lesion Dice did not improve** (slightly down). Extra zooms/shifts cost more time and still did not help lesion outlines.

---

## Outside sets (when present on the VM)

Same gate. Absolute Dice here is lower than the older *ungated* published outside numbers, because the 0.96 gate can clear weak lesion outlines — another branch may re-score the gated baseline separately. What matters for this experiment is **single vs averaged under the same gate**.

| Dataset | Single Dice | Flip-avg Dice | Single AUC | Flip-avg AUC | Notes |
|---|---|---|---|---|---|
| BUS-BRA | 0.653 | 0.636 | 0.639 | 0.639 | Outline Dice **down** with averaging |
| BrEaST | 0.578 | 0.566 | 0.720 | 0.736 | Outline Dice **down**; AUC a bit up |
| BUS-UCLM | — | — | — | — | Archive not on this VM (see `docs/BUSUCLM_STEPS.md`) |

Ungated single-view BUS-BRA Dice matched the published ~0.714 check, so the loader/model path is fine.

---

## In-browser time

Chromium via `vite preview` on this VM (model already warm). Soft-mask average of original + horizontal flip on six gallery samples:

| | Mean ms / image |
|---|---|
| Single | ~151 |
| Flip average (2) | ~305 |
| Ratio | **~2.03×** |

So time sits right at the “about 2×” ceiling even for the smallest useful set.

Reproduce: `cd web && npm run build && cd .. && node scripts/measure_tta_browser_time.mjs`

---

## Why the app was not changed

Averaging did **not** earn a default (or even an optional “Steadier”) path:

- Lesion outline accuracy on BUSI did not improve
- Outside outline Dice got worse on BUS-BRA and BrEaST
- Browser cost was already ~2× for two views

The demo still has the older optional “Estimate uncertainty (8 flips)” path for agreement heatmaps — that is a different feature (uncertainty), not this averaging ship decision.

---

## Overlap with the no-lump gate re-score branch

Another agent is re-scoring outside sets with the no-lump gate on a separate branch. This write-up only adds:

- `results/tta_averaging.json` / `results/tta_averaging_per_image.json`
- `docs/TTA_AVERAGING.md`
- `scripts/eval_tta_averaging.py` / `scripts/measure_tta_browser_time.mjs`

It does **not** edit `results/no_lump_gate.json` or the Results page no-lump section, to avoid merge fights on the same prose.

---

## How to re-run

```bash
# BUSI processed data + ONNX already present
python3 scripts/eval_tta_averaging.py

# Optional browser timing after web build
cd web && npm run build && cd .. && node scripts/measure_tta_browser_time.mjs
```

Dark mode, credit line, and disclaimer on the site are unchanged — the demo UI was not modified for this experiment.
