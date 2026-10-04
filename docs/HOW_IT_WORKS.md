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
- **Full model:** ResNet-18 ImageNet encoder + U-Net decoder at 128×128

**Auxiliary classification head:** a small MLP on the bottleneck predicts **P(malignant)** for benign vs malignant. **Normal** images train with **empty masks** so the segmenter learns “no lesion,” and classification loss is **skipped** for normals (target = −1).

Loss = (BCE + Dice) for masks + weighted BCE for classification.

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

**Interview tip:** high Dice on **normal** images (empty vs empty) can look good without proving lesion skill. That’s why we also report **lesion-only Dice**.

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
5. Know Dice, IoU, AUC, calibration, and why shortcuts matter clinically

---

## Limitations to volunteer before you’re asked

- One public dataset; scanners/populations differ in the real world  
- Heuristic flags ≠ perfect OCR of every annotation  
- 128×128 loses fine detail  
- Demo is **not** a medical device  

Keep the disclaimer visible. Curiosity + honesty beats inflated leaderboard numbers.
