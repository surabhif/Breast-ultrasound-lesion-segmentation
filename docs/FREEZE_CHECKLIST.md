# Dec 4 freeze checklist

**Target freeze:** 4 December (D12).  
**Agents must not create git tags or GitHub Releases.** Owner completes the owner-only rows.

Research demo — not for clinical use. No clinician outreach (D4 revoked).

---

## Model & metrics

- [ ] **Served model decision locked:** keep **v1.0.0** *or* document a v2 that passed MODEL_POLICY (clean Dice ≥ v1, external Dice ≥ v1 on BUS-BRA and BrEaST, AUC drop ≤ 0.02). Current site decision: **v1.0.0** (inpaint E-c failed external Dice).
- [ ] Served artifact path matches `web/public/models/current.json` → `v1.0.0/busi_unet.onnx`
- [ ] SHA-256 of served ONNX matches committed metrics (`0bbf529d…` for v1.0.0 as of Phase 1–3)
- [ ] **`web/public/results/metrics.json` locked** (no further metric rewrites without a new decision-log entry)
- [ ] `results/served_int8_test.json`, `results/external/*.json`, inpaint / uncertainty / leakage JSONs consistent with the site
- [ ] Postprocess frozen: seg threshold **0.4**, min-component area **40**, cls threshold **0.5**
- [ ] Browser ↔ Python parity / CI still green on freeze commit

## BUS-UCLM (optional secondary)

- [ ] If available: owner downloads BUS-UCLM (Mendeley), places under `data/external/busuclm/`, re-runs external eval, commits JSON
- [ ] If still unavailable: leave skipped status + reason in metrics / protocol (current state)

## Citation / DOI

- [ ] Zenodo ↔ GitHub connected (toggle **On**) — `docs/ZENODO_STEPS.md`
- [ ] **DOI minted** via owner-created GitHub Release (not by agent)
- [ ] `CITATION.cff` and README updated with DOI after mint
- [ ] `.zenodo.json` present on tagged commit

## Preprint / write-up

- [ ] `paper/main.pdf` rebuilt from current `paper/numbers.tex` (`python scripts/export_paper_numbers.py` + `pdflatex` ×2)
- [ ] `python scripts/check_paper_numbers_drift.py` passes
- [ ] Venue chosen per `docs/SUBMISSION_GUIDE.md` (JEI vs arXiv vs site-only) — **do not submit from agents**
- [ ] Preprint **submitted or staged** (PDF + source ready; endorsement / mentor arranged if needed)
- [ ] AI-use disclosure included exactly as decided (D6)

## Site / deploy

- [ ] GitHub Pages deploy green for freeze commit (`deploy-pages` workflow)
- [ ] Live demo URL loads Demo, Results, About, BI-RADS, Surgeons’ view, Portfolio
- [ ] `web/public/report.pdf` and walkthrough video present
- [ ] axe / accessibility CI green (`docs/ACCESSIBILITY.md` / workflow)
- [ ] No analytics, no clinician outreach, no `/review` page

## Changelog & tags (owner-only)

- [ ] `CHANGELOG.md` updated for freeze / Unreleased → v1.0.0 section
- [ ] Draft release notes promoted from `docs/RELEASE_NOTES_v1.0_DRAFT.md` (remove DRAFT banner)
- [ ] Owner creates tag + GitHub Release **only after** checklist items above are satisfied
- [ ] Decision log entry noting freeze date, served model version, DOI (when minted)

## Explicit non-goals at freeze

- [x] No clinician review / outreach / acknowledgements
- [x] No agent-created tags or releases
- [x] No journal/preprint submission by agents
