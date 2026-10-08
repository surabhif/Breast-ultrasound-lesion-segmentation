# Decision log

Dated owner decisions for this research demo. Implementation assistance from an AI coding agent (Cursor); Surabhi owns the research questions, interpretation, and presentation.

Research demo, not for clinical use.

---

## 2026-10-08 — D4 revoked (no clinician review)

**Decided:** The earlier Phase 1 decision **D4 (clinician review / outreach)** is **revoked**. This project will **not** involve clinician review, outreach emails, reviewer acknowledgements, or a private `/review` page. Related docs and UI were removed in Phase 2.

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

~~Build a static private review page…~~ **Revoked 2026-10-08** — see entry at top of this file.

---

## Earlier (Phase 0, 2026-10-08)

- Freeze served INT8 as **v1.0.0**; publish INT8 test metrics beside FP32; browser min-area-40 parity; CI; pre-register external protocol before scoring.
