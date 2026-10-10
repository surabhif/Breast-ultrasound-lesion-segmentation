# How this project works (plain-language guide)

This note is for **Surabhi Fadnavis** — so you can explain every design choice confidently in interviews. It is not a clinical guide. **Research demo, not for clinical use.**

---

## The clinical question (research framing)

Breast ultrasound helps characterize masses. Two related research questions show up again and again:

1. **Where is the lesion?** → segmentation (draw a mask)
2. **Does it look more benign or malignant?** → classification (a score)

Public datasets let students train models quickly, but they also hide traps: duplicate frames, burned-in calipers, and missing patient IDs. This project builds a working demo **and** measures those traps.

---

## Dataset: BUSI

**BUSI** (Al-Dhabyani et al., *Data in Brief*, 2020) has ~780 breast ultrasound PNGs in three folders: benign, malignant, normal. Each image usually has a `*_mask.png` ground truth; some lesions have extra masks (`_mask_1`, …). We **OR-merge** those masks so one image has one lesion map.

**Important honesty:** BUSI does **not** publish patient IDs. You cannot claim patient-level separation. Say instead: *“We grouped near-duplicate images with perceptual hashing so the same (or nearly the same) frame never appears on both sides of a split.”*

We do **not** commit the full dataset (license for redistribution is unclear). A script downloads a public Hugging Face mirror. Kaggle is documented as an alternative that needs an API key.

---

## Why cleaning matters

### Near-duplicates

Ultrasound exams often save similar frames. If one copy is in training and another in test, the model can “cheat” by memorizing appearance. We compute a **perceptual hash (pHash)** and cluster images within a Hamming distance. Those **groups** stay entirely in train, val, *or* test.

### Caliper marks and burned-in text

Calipers (measurement crosses) and on-screen labels are common. A classifier might learn “marks present ⇒ malignant” instead of real tissue patterns. We run a **heuristic** (bright thin lines / cross shapes, glyph-like blobs, bright borders) and write an audit CSV. Then we compare metrics on **flagged vs clean** test images. Whatever the numbers show, report them honestly — even if the shortcut effect is small.

---

## Splits

- Hold out ~15% test (grouped + stratified)
- Remaining data → **5-fold cross-validation** (grouped + stratified)
- Document clearly: **not** patient-level

If someone asks why you didn’t use random 80/20: explain leakage risk from duplicates.

---

## Model: U-Net + auxiliary head

**U-Net** is an encoder–decoder with skip connections. The encoder compresses the image into features; the decoder upsamples back to a full-resolution mask. Skips help keep edges sharp.

We use:

- **Quick baseline:** tiny U-Net from scratch at 64×64 — trains on CPU in minutes
- **Full model:** ResNet-18 ImageNet encoder + slim bilinear U-Net decoder at 160×160

**Auxiliary classification head:** a small linear head on the bottleneck predicts **P(malignant)** for benign vs malignant. **Normal** images train with **empty masks** so the segmenter learns “no lesion,” and classification loss is **skipped** for normals (target = −1).

Loss = (pos-weighted BCE + soft Dice) for masks + weighted BCE for classification.

**Training details that matter:** geometric augmentations are applied to image and mask *together* (otherwise the mask no longer matches the image). We checkpoint on **lesion Dice** (not overall Dice dragged by false positives on normals). Threshold and tiny-blob removal are chosen on **validation only**, then frozen for the test report.

---

## Metrics you should be able to define

| Metric | Meaning |
|--------|---------|
| **Dice** | \(2|P∩G| / (|P|+|G|)\) — overlap; 1 is perfect |
| **IoU** | \(|P∩G| / |P∪G|\) — stricter cousin of Dice |
| **Bootstrap 95% CI** | Resample test images many times; report the middle 95% of mean Dice |
| **ROC-AUC** | Ranking quality for benign vs malignant scores |
| **Sensitivity / specificity** | TPR / TNR at a chosen threshold (we state 0.5) |
| **Calibration / ECE** | Do 0.8 scores really mean ~80% malignant in that bin? ECE summarizes the gap |

**Interview tip:** for empty ground-truth masks, predicting nothing should score as perfect (Dice = 1). If the model paints a false lesion on a normal image, Dice collapses toward 0 — so “normal Dice” is really a false-positive check. That’s why we also report **lesion-only Dice**.

---

## In-browser demo

We export the network to **ONNX** and run it with **onnxruntime-web** in WASM. Your ultrasound never needs to leave the laptop. The UI draws a soft mask overlay + outline and shows P(malignant) with uncertainty wording when the mask is empty or the score is near 0.5.

---

## What “done” means for you in an interview

You can say:

1. Built an end-to-end BUSI segmentation + aux classification pipeline
2. Prevented near-duplicate leakage with grouped splits (and said patient IDs are missing)
3. Audited calipers/text and measured whether scores inflate on flagged images
4. Shipped a GitHub Pages demo with real ONNX weights and real metrics
5. Know Dice, IoU, AUC, calibration, and why annotation shortcuts matter for honest scores

---

## External validation (Phase 1)

The frozen served model (`v1.0.0` INT8) was also scored on **BUS-BRA**, **BrEaST**, and **BUS-UCLM** with the pre-registered protocol (no tuning). Dice stayed in a similar ballpark to BUSI on BUS-BRA, but **benign-vs-malignant AUC dropped a lot** under shift. On BUS-UCLM, all-image Dice is low (~0.386) mainly because of **normal false positives** (320/413); lesion-only Dice (~0.679) is the fairer comparison. Honest headline: segmentation transfers better than the auxiliary classifier when lesions are present, but normals remain a known weakness.

## Phase 2 (robustness & uncertainty)

- **Caliper inpainting:** detect marker pixels, erase them with Telea inpainting, and retrain (E-a/E-b/E-c). A new model only becomes the served version if it beats the pre-registered swap rule.
- **TTA uncertainty:** run the model several times with small flips/brightness changes; show an agreement chip and optional heatmap. This is *not* a probability of being wrong.
- **Web Worker:** inference (and TTA) leave the UI thread so the page stays responsive; WASM files are self-hosted.
- **Threshold sliders:** change mask and class cut-offs live on the Demo; on Results, explore sensitivity/specificity trade-offs from saved scores.
- **Model Errors explorer:** filter hard cases with outline-only silhouettes and clearly labelled AI-generated notes.

This project does **not** include expert medical review or outreach.

## Phase 3 (clinical context & polish)

- **BI-RADS page:** plain-language ultrasound categories/descriptors; a model score is **not** a BI-RADS assessment.
- **Surgeon’s-view page:** why size/margins matter clinically, and why demo measurements are research-only (BrEaST CC BY examples + BUSI outline silhouettes).
- **Write-up PDF:** `web/public/report.pdf` auto-filled from results JSON; CI fails on number drift.
- **Cite / portfolio / video / OG / a11y / privacy:** CITATION.cff, in-site portfolio (sibling repos verified), captioned walkthrough, social preview from CC BY imagery, accessibility fixes, no analytics.
- **Served model stays v1.0.0.** No Dec 4 freeze tag yet. C3 clinician review skipped.

## How this was built

Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (Cursor). Not clinician-reviewed. Not for clinical use.

## Limitations to volunteer before you’re asked

- Domain shift: AUC falls externally even when Dice looks OK  
- Heuristic flags ≠ perfect OCR of every annotation  
- 160×160 loses fine detail  
- Demo is **not** a medical device  

Keep the disclaimer visible. Curiosity + honesty beats inflated leaderboard numbers.
