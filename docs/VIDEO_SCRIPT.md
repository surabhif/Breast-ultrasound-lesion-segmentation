# Walkthrough video — storyboard & script

**File:** `web/public/video/walkthrough.mp4`  
**Poster:** `web/public/video/walkthrough-poster.jpg`  
**Captions:** `web/public/video/walkthrough.vtt` (also burned into the MP4)  
**Length target:** 60–90 seconds · **no voiceover · no person on camera**  
**Generator:** `scripts/record_walkthrough.py` (Playwright screenshots + ffmpeg)

Research demo — not for clinical use.

**Credit:** Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (Cursor).

---

## Scenes

| t (approx) | Scene | Caption |
|------------|-------|---------|
| 0–4s | Title card | Research demo · not for clinical use · Surabhi Fadnavis |
| 4–10s | Home | Home — educational tour and in-browser lesion segmentation |
| 10–17s | Demo gallery | Demo gallery — BUSI samples and CC BY BrEaST images |
| 17–29s | Demo overlay | Mask overlay and benign vs malignant score — fully in the browser |
| 29–37s | Demo controls | Expert compare, threshold sliders, and research measurements |
| 37–45s | Results charts | Results — Dice, ROC, and calibration from committed JSON |
| 45–52s | External table | External validation on BUS-BRA and BrEaST |
| 52–58s | Model Errors | Model Errors explorer — outline-only silhouettes for hard cases |
| 58–64s | BI-RADS | BI-RADS context — a model score is not a BI-RADS category |
| 64–70s | Surgeon’s view | Surgeon's view — imaging size is not pathologic T-stage |
| 70–75s | Portfolio | Portfolio — related oncology-AI student research demos |
| 75–82s | End card | Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (Cursor). |

## Production notes

- Wait for `networkidle` **and** a visible element on each route.
- Demo scenes wait until the model loads and `.score-card` / `canvas` are visible.
- Prefer local `vite preview` with matching `base`.
- Keep file under ~15 MB (H.264, 1280×720).
- Before commit: extract one frame every 5 s; reject blank whites; save contact sheet as `phase3b-video-contact.png`.
- Poster labels the **actual** duration (not “60–90s”).
