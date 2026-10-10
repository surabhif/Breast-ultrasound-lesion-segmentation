# Decision log

Dated owner decisions for this research demo.

Research demo, not for clinical use.

**Credit (site-facing wording):** Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (Cursor).

---

## 2026-10-10 — Phase 4 citation / preprint prep (D13–D15)

Prep only — **no tags, releases, or submissions** by agents.

### D13 — Zenodo / CITATION freeze path

**Decided (prep):** Ship `.zenodo.json` (MIT, software, open) + enhanced `CITATION.cff` with preferred-citation and DOI placeholders. Owner follows `docs/ZENODO_STEPS.md` to connect Zenodo and mint a DOI from a GitHub Release at freeze. Agents must not create tags/releases.

### D14 — Preprint package

**Decided (prep):** Add LaTeX manuscript under `paper/` with numbers imported from `web/public/results/metrics.json` via `scripts/export_paper_numbers.py` and drift check `scripts/check_paper_numbers_drift.py`. Venue comparison in `docs/SUBMISSION_GUIDE.md` (JEI vs arXiv). **Do not submit** in this phase; owner chooses later. Note: JEI’s published AI policy (as of 2026-10-10) conflicts with this project’s AI-assisted build — arXiv or site-only are the realistic defaults unless the owner changes approach.

### D15 — Dec 4 freeze checklist

**Decided (prep):** Owner uses `docs/FREEZE_CHECKLIST.md` and draft `docs/RELEASE_NOTES_v1.0_DRAFT.md` for the freeze release. Served model remains **v1.0.0** unless MODEL_POLICY is newly satisfied. No clinician outreach.

### D16 — Phase 4 v2 training attempt (swap rule unchanged)

**Decided:** Train multi-dataset v2 candidates (BUSI train + patient-grouped BUS-BRA train; held-out BUS-BRA test; BrEaST fully external) with ResNet-34 @ 256², stronger augmentation, Dice+focal, optional Telea caliper inpaint, ~3 seeds. Promote to served **v2.0.0** only if MODEL_POLICY (D3) passes **and** INT8 ONNX ≤ ~25 MB with reasonable in-browser latency. Otherwise keep **v1.0.0** and publish the comparison on Results. No clinician outreach.

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

**Decided:** **Deferred.** Minting a DOI needs the owner’s Zenodo login. Note the deferral in cite docs / `CITATION.cff` only — agents cannot complete it.

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

### D2 — BUSI imagery on the site

**Decided:** Keep BUSI pixels limited to the samples and failure cases already shipped. New visuals (explorer, social preview) use **CC BY external** images. Elsewhere, BUSI rows may show metrics plus **outline-only silhouettes** (no ultrasound pixels).

### D3 — Model-swap rule (pre-registered)

**Decided:** A retrained `v2` may replace served `v1.0.0` before the Dec 4 freeze **only if** it matches or beats v1 on (a) clean-subset Dice and (b) external Dice, and AUC drops by **no more than 0.02**. Otherwise keep v1 served and publish v2 as an experiment. Written into `docs/EXTERNAL_VALIDATION_PROTOCOL.md` (§ MODEL_POLICY).

### D4 — Clinician review (REVOKED)

~~Build a static private review page…~~ **Revoked 2026-10-08** — see entry above.

---

## Earlier (Phase 0, 2026-10-08)

- Freeze served INT8 as **v1.0.0**; publish INT8 test metrics beside FP32; browser min-area-40 parity; CI; pre-register external protocol before scoring.
