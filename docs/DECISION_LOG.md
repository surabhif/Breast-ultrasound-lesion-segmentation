# Project decisions log

Dated owner decisions for this research demo. Older entries keep their labels so history stays searchable; new writing should prefer plain names over short codes.

Research demo, not for clinical use.

**Credit (site-facing wording):** Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (Cursor).

**DOI status:** Done. Concept DOI (all versions) **10.5281/zenodo.23286596**. Version DOIs: v1.0.1 **10.5281/zenodo.24433044**; v1.0.0 **10.5281/zenodo.23286597**. Older prep notes that said “DOI placeholders” are historical.

---

## 2026-11-21 — v1.1 BUSI-only candidates (write-up only; no live swap)

**Decided:** Train up to three larger BUSI-only candidates (ResNet-18 @ 224/256, ResNet-34 @ 224) on the same cleaned data and committed `results/splits.json` as v1.0.0. Tune postprocess and no-lump gate on validation only. Score frozen test + outside sets. Apply MODEL_POLICY D3 for any live swap; also report the abbreviated Dice+AUC check. **Do not** rewrite `current.json`.

**Outcome:** No candidate passed full D3 (outside Dice dropped on BUS-BRA/BrEaST). `r18_224` passed abbreviated Dice+AUC (Dice 0.703 ≥ 0.697, AUC 0.936 ≥ 0.931−0.02). **Owner follow-up:** keep the write-up (`docs/V1_1_EXPERIMENT.md`, `results/v1_1*.json`, scripts, CHANGELOG) only — **do not** show a candidate on Results or ship candidate ONNX under `web/public/`. Served model remains **v1.0.0**.

## 2026-11-21 — Test-time averaging (no ship)

**Decided:** Do **not** enable soft-mask / class-score averaging in the demo (no Fast/Steadier toggle). On the published BUSI held-out split with the 0.96 no-lump gate, flip averaging did not improve lesion Dice; BUS-BRA and BrEaST outline Dice fell; browser time was ~2.0× for two views. Served weights stay **v1.0.0**. Write-up only: `docs/TTA_AVERAGING.md`, `results/tta_averaging.json`. Avoid editing the Results no-lump section (parallel gate re-score branch).

---

## 2026-10-10 — Citation / preprint prep

Prep only — **no tags, releases, or submissions** by agents.

### Zenodo / CITATION freeze path

**Decided (prep):** Ship `.zenodo.json` (MIT, software, open) + enhanced `CITATION.cff` with preferred-citation. Owner follows `docs/ZENODO_STEPS.md` (how the DOI was made / release checklist) to connect Zenodo and mint a DOI from a GitHub Release at freeze. **Update:** DOI is minted (see top of this file).

### D14 — Preprint package

**Decided (prep):** Add LaTeX manuscript under `paper/` with numbers imported from `web/public/results/metrics.json` via `scripts/export_paper_numbers.py` and drift check `scripts/check_paper_numbers_drift.py`. Venue comparison in `docs/SUBMISSION_GUIDE.md` (JEI vs arXiv). **Do not submit** in this phase; owner chooses later. Note: JEI’s published AI policy (as of 2026-10-10) conflicts with this project’s AI-assisted build — arXiv or site-only are the realistic defaults unless the owner changes approach.

### D15 — Dec 4 freeze checklist

**Decided (prep):** Owner uses `docs/FREEZE_CHECKLIST.md` and `docs/RELEASE_NOTES_v1.0.md` for the freeze release. Served model remains **v1.0.0** unless the written swap rule is newly satisfied.

### D16 — Phase 4 v2 training attempt

**Decided:** Train multi-dataset v2 candidates (BUSI train + patient-grouped BUS-BRA train; held-out BUS-BRA test; BrEaST fully external) with ResNet-34 @ 256², stronger augmentation, Dice+focal, optional Telea caliper inpaint, ~3 seeds. Promote to served **v2.0.0** only if MODEL_POLICY passes **and** INT8 ONNX ≤ ~25 MB with reasonable in-browser latency. Otherwise keep **v1.0.0** and publish the comparison on Results. No clinician outreach.

### D17 — Fair Phase-4 swap comparison (2026-10-10)

**Decided:** Because v2 trains on BUS-BRA, BUS-BRA held-out is **same-source**, not external. Score v1.0.0 INT8 on the **exact same held-out IDs** and compare against that. Label accordingly on Results, report, and paper. **BrEaST** is the only truly external test. Report seed mean ± SD and paired-bootstrap 95% CIs for deltas. Promote only if the **seed mean** passes all rules; among passing seeds take the **median** by clean Dice (not the best). No merge until owner review.

---

## 2026-10-08 — Phase 3 decisions (plan numbering D5–D12)

Applied at Phase 3 (draft PR; owner merges). Numbering follows the enhancement plan.

### D5 — Write-up venue

**Decided:** **Site-only** for now (PDF on the GitHub Pages site + repo). Not submitted to a journal or preprint server in this phase.

### D6 — Credit / “How this was built”

**Decided:** Use consistently on the site, README, report, video end card, and portfolio:

> Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (Cursor).

Do not claim specific tasks Surabhi personally drafted or recorded.

### D7 — Personal info on the site

**Decided:** Publish **name** and **“high-school senior, Georgia”** only. No school name, photo, email, or personal contact.

### D8 — Zenodo DOI

**Decided (updated):** **Minted.** Owner published a GitHub Release; Zenodo assigned v1.0.0 version DOI **10.5281/zenodo.23286597** and concept DOI **10.5281/zenodo.23286596**. Later v1.0.1 version DOI **10.5281/zenodo.24433044**. Main citation / badge should use the **concept** DOI. Agents still must not create tags or releases unless the owner asks.

### D9 — Walkthrough video

**Decided:** AI-made captioned walkthrough (no voiceover, no person on camera), self-hosted under `web/public/video/`. Target 60–90 s.

### D10 — Compute / storage

**Decided:** Keep training and artifacts within the existing repo / CPU-friendly workflow already used for v1.0.0 (no new paid compute tier required for Phase 3 polish).

### D11 — Analytics

**Decided:** **None.** No analytics account. About page states the site uses no analytics or cookies and processes images in the browser only.

### D12 — Model freeze date

**Decided:** Target freeze is **4 December** (Dec 4). **Do not** create the freeze tag or GitHub release yet; served model stays **v1.0.0** until the owner tags it.

### Portfolio hosting (separate note — not a D-number)

**Decided 2026-10-08:** The plan’s separate `surabhif.github.io` portfolio repo needs the owner to create it. For Phase 3, ship an in-site **`/portfolio`** page instead. Do not modify sibling repositories.

### Clinician involvement (extends D4 revocation)

**Decided:** **None.** Skip plan item **C3** entirely. Do not add reviewer or acknowledgement sections. (See D4 revoked below.)

---

## 2026-10-08 — D4 revoked (no clinician review)

**Decided:** The earlier Phase 1 decision **D4 (clinician review / outreach)** is **revoked**. This project will **not** involve clinician review, outreach emails, reviewer acknowledgements, or a private `/review` page. Related docs and UI were removed in Phase 2. Reaffirmed for Phase 3 (skip C3).

---

## 2026-10-08 — Phase 1 go-ahead (D1–D4)

**Context:** Phase 0 (model v1.0.0, CI, parity, external-validation pre-registration) is merged. Owner approved decisions D1–D4 exactly as recommended in the enhancement plan §9 and authorized Phase 1. **D4 was later revoked the same day** (see entry above).

### D1 — External datasets

**Decided:** Use **BUS-BRA** and **BrEaST** as primary external sets; **BUS-UCLM** as secondary. Skip **UDIAT** and **BUSIS** (licence / institutional-access friction). Verify CC BY 4.0 (or equivalent) and access route before scoring. Cite each dataset; do not commit raw images except small CC BY samples on the site with attribution.

**Update (2026-10-10):** Owner downloaded BUS-UCLM and scored frozen v1.0.0 INT8 locally (sha matched `current.json`; seg 0.4 / min area 40 / cls 0.5; patient bootstrap 1000, seed 42). Committed `results/external/busuclm.json` (n=640, 38 patients; 43 Doppler/combined excluded). All-image Dice 0.386 is dominated by 320/413 normal FPs; lesion Dice 0.679 is the fairer cross-dataset figure. Images stay local / not redistributed.

### D2 — BUSI imagery on the site

**Decided:** Keep BUSI pixels limited to the samples and failure cases already shipped. New visuals (explorer, social preview) use **CC BY external** images. Elsewhere, BUSI rows may show metrics plus **outline-only silhouettes** (no ultrasound pixels).

### D3 — Model-swap rule (pre-registered)

**Decided:** A retrained `v2` may replace served `v1.0.0` before the Dec 4 freeze **only if** it matches or beats v1 on (a) clean-subset Dice and (b) external Dice, and AUC drops by **no more than 0.02**. Otherwise keep v1 served and publish v2 as an experiment. Written into `docs/EXTERNAL_VALIDATION_PROTOCOL.md` (§ MODEL_POLICY).

### D4 — Clinician review (REVOKED)

~~Build a static private review page…~~ **Revoked 2026-10-08** — see entry above.

---

## Earlier (Phase 0, 2026-10-08)

- Freeze served INT8 as **v1.0.0**; publish INT8 test metrics beside FP32; browser min-area-40 parity; CI; pre-register external protocol before scoring.
