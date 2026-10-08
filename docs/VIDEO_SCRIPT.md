# Walkthrough video — storyboard & script

**File:** `web/public/video/walkthrough.mp4`  
**Poster:** `web/public/video/walkthrough-poster.jpg`  
**Captions:** `web/public/video/walkthrough.vtt` (also burned into the MP4)  
**Length target:** 60–90 seconds · **no voiceover · no person on camera**  
**Generator:** `scripts/record_walkthrough.py` (Playwright screenshots + ffmpeg)

Research demo — not for clinical use.

---

## Title card (0–4s)

**On-screen:** Breast Ultrasound Lesion Segmentation  
**Caption:** Research demo · not for clinical use · Surabhi Fadnavis

## Home (4–14s)

**Action:** Open Home; show hero + disclaimer.  
**Caption:** Educational tour and in-browser lesion segmentation on BUSI

## Demo (14–34s)

**Action:** Navigate to Demo; select a BrEaST CC BY sample; wait for mask overlay.  
**Caption:** Try the detector — mask overlay and benign vs malignant score in your browser

## Measurements (34–44s)

**Action:** Show measurement card / diameter lines if visible.  
**Caption:** Research-only size estimates — not pathologic T-stage or surgical margins

## Results (44–56s)

**Action:** Open Results; scroll to external validation headline.  
**Caption:** Internal and external metrics from committed results JSON

## BI-RADS + surgeon’s view (56–68s)

**Action:** Brief view of BI-RADS page, then surgeon’s-view examples.  
**Caption:** A model score is not a BI-RADS category · imaging size is not staging

## Portfolio + About (68–78s)

**Action:** Portfolio cards, then About cite / privacy.  
**Caption:** Related oncology-AI student projects · no analytics · cite the repo

## End card (78–88s)

**On-screen:** How this was built  
**Caption:** Code, analysis, and text produced with AI tools (Cursor). Surabhi owns the research questions and review. Not for clinical use.

---

## Production notes

- Prefer live Pages or local `vite preview` with `VITE_BASE`.
- Keep file under ~15 MB (H.264, 1280×720, CRF ~28).
- Burn captions with ffmpeg `drawtext` / `subtitles` filter; also ship WebVTT for the HTML `<track>`.
- Imagery in the recording may show CC BY BrEaST samples and BUSI outline silhouettes only for new failure visuals (D2).
