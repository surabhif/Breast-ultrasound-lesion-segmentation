# Preprint / journal submission guide (JEI vs arXiv)

**Status:** guidance only. **Do not submit** from agents or automated runners. Owner decides venue and submits (or keeps site-only per earlier D5).

**As-of date for URLs/policies checked in this doc:** **2026-10-10**. Re-check JEI and arXiv pages before submitting — policies change.

Related: `paper/main.tex`, `paper/main.pdf`, `docs/ZENODO_STEPS.md`, `docs/FREEZE_CHECKLIST.md`.

**Mandatory disclosure wording (D6):**  
> Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (Cursor).

---

## Side-by-side recommendation

| Criterion | Journal of Emerging Investigators (JEI) | arXiv |
|-----------|-------------------------------------------|-------|
| Audience | Middle/high-school journal with mentoring review | Open preprint server for scientific community |
| Fit for **this** repo | **Poor fit** given JEI’s strict AI policy vs our disclosed AI-assisted code/analysis/text | **Better fit** if endorsement can be obtained; allows AI disclosure |
| Mentor / adult | **Required** senior mentor as last author; adult must submit | No mentor role; endorsement required for new submitters |
| Cost | **\$49** submission fee (scholarship possible) | Free |
| Peer review | Yes (student-focused editorial process) | No (moderation only) |
| Preprint conflict | JEI: manuscript must not be submitted to venues lacking clear public copyright/permissions; check their permissions page before dual-tracking | Publishing on arXiv first may conflict with JEI — read JEI permissions before dual use |
| Speed to citable ID | Weeks+ through review | Days after acceptance/announcement (if endorsed) |
| Categories | N/A (JEI journal) | Suggest primary **eess.IV** (Image and Video Processing) and/or **cs.CV** |
| Recommendation for this project | Prefer **not** JEI unless the owner rewrites without prohibited AI use **and** finds an eligible mentor — current disclosure conflicts with JEI AI rules | Prefer **arXiv** *or* remain **site-only** (PDF on Pages) if endorsement is hard |

**Practical recommendation:** Keep the GitHub Pages PDF + `paper/main.pdf` as the default citable write-up; mint a **Zenodo DOI** on freeze release for the software. Pursue **arXiv** only if a suitable endorser (e.g. mentor/teacher with arXiv endorsement rights in eess/cs) agrees. Treat **JEI as unlikely** under current AI policy given this project’s build process.

---

## A. Journal of Emerging Investigators (JEI)

**Home:** https://emerginginvestigators.org/  
**Submission guide hub:** https://emerginginvestigators.org/submissions/guidelines  
**Author eligibility:** https://emerginginvestigators.org/submissions/author-eligibility  
**Academic honesty & AI:** https://emerginginvestigators.org/submissions/academic-honesty-and-ai  
**Pay & submit overview:** https://emerginginvestigators.org/submissions/pay-and-submit  
**Manuscript template:** https://emerginginvestigators.org/documents/author_manuscript_template  

### Eligibility (owner must satisfy)

- Middle- or high-school student authors aged **13+**; **initial submission before university enrollment**
- At least **two authors**: student(s) + **senior mentor as last author** (teacher, professor, postdoc, senior grad student; parent only if research at home). Undergraduates cannot be senior author
- **Student must never submit** their own manuscript. An **adult** (parent/guardian/mentor) submits; JEI notes parent/legal guardian must submit via Editorial Manager for minors
- One manuscript per student at a time

### AI policy (critical for this repo) — checked 2026-10-10

JEI states they **cannot ethically publish** manuscripts that use AI for, among other things:

- Reading/summarizing/analyzing prior studies  
- Writing text or making revisions (exception: minor spelling/grammar proofreading **after** the author writes)  
- Creating images  
- Statistical analysis / modeling / calculations  
- Data mining without a hypothesis  
- Citing / building reference lists  

Our project explicitly discloses AI use for **code, analysis, text, and video**. That conflicts with JEI’s published AI rules. Do **not** submit to JEI without the owner independently confirming compliance (likely requires a non-AI-written manuscript and non-AI analysis path JEI would accept). Agents must not “sanitize” disclosure to squeeze through review.

### Click-by-click submission path (owner + adult)

1. Read https://emerginginvestigators.org/submissions/guidelines end-to-end  
2. Confirm eligibility + AI honesty pages above  
3. Download/write on the official **Word template** (JEI does not accept arbitrary LaTeX uploads as the primary manuscript format)  
4. Complete https://emerginginvestigators.org/submissions/pay-and-submit  
5. **Step 1 — Pay:** open https://emerginginvestigators.org/submissions/pay-and-submit/pay → pay **\$49** via Stripe (or apply for scholarship: https://emerginginvestigators.org/submissions/scholarships/new)  
6. **Step 2 — Code:** wait for JEI email with **10-character submission fee confirmation code** (not the Stripe receipt ID) — https://emerginginvestigators.org/submissions/pay-and-submit/code  
7. **Step 3 — Submit:** the fee email contains the **link to JEI’s submission platform** (Editorial Manager) and an instructional PDF — https://emerginginvestigators.org/submissions/pay-and-submit/submit  
8. Adult corresponding author: create/login account on the emailed portal → enter fee code → enter authors (student + senior mentor email) → upload Word manuscript + figures/ethics docs → review generated PDF → approve → submit  
9. Wait **≥2–3 weeks** for pre-review; JEI asks waiting **≥4 weeks** before status inquiries  

**Note:** The public site does not hard-code a permanent Editorial Manager URL on the pay/submit pages; the portal link arrives in the post-payment email. Re-check JEI FAQ if the flow changes: https://emerginginvestigators.org/submissions/faq  

---

## B. arXiv

**Home:** https://arxiv.org/  
**Submit help:** https://info.arxiv.org/help/submit/index.html  
**Endorsement:** https://info.arxiv.org/help/endorsement.html  
**Endorsement policy update (2026-01-21):** https://blog.arxiv.org/2026/01/21/attention-authors-updated-endorsement-policy/  
**Category taxonomy:** https://arxiv.org/category_taxonomy  
**TeX submit help:** https://info.arxiv.org/help/submit_tex.html  

### Suggested categories for this work

- Primary: **eess.IV** — Image and Video Processing (medical imaging fits here)  
- Cross-list / alternate: **cs.CV** — Computer Vision and Pattern Recognition  

### Endorsement (new submitters — as of Jan 2026 policy)

arXiv no longer treats institutional email alone as sufficient. Paths:

1. **Automatic-style path:** institutional/research email **and** claimed ownership of a prior arXiv paper in the endorsement domain — unlikely for a first-time high-school sole author  
2. **Personal endorsement:** an established arXiv author with endorsement rights in the domain endorses you  

Personal endorsement click path (from arXiv help):

1. Create/login account: follow https://info.arxiv.org/help/registerhelp.html  
2. Start a new submission and select category (**eess.IV** or **cs.CV**)  
3. Check email for an **endorsement request** message (contains a link/code for endorsers)  
4. Find endorsers via related abstracts → “Which authors of this paper are endorsers?”  
5. Contact endorsers you know (advisor/teacher with arXiv history); send the endorsement code — do not mass-email strangers  
6. After ≥1 positive endorsement for the category, continue submission  

### Click-by-click upload (after endorsement)

1. https://arxiv.org/user → **Start new submission**  
2. Metadata: title, author (Surabhi Fadnavis), abstract (from `paper/main.tex`), comments (e.g. “Research demo; not for clinical use”), license  
3. Select primary category **eess.IV** (optional cross-list **cs.CV**)  
4. Upload LaTeX sources: `paper/main.tex`, `paper/numbers.tex`, and generated `paper/main.pdf` as needed per arXiv TeX guidelines (prefer source over PDF-only)  
5. Include AI-use disclosure in the PDF (already in § AI-use disclosure)  
6. Process / compile on arXiv → preview → **Submit**  
7. Wait for moderation/announcement; note the arXiv ID  

**Minors / school email:** arXiv identity policies evolve; a parent/mentor may need to help with account/endorsement logistics. Read https://info.arxiv.org/help/policies/identity_and_affiliation.html before registering.

---

## C. Owner decision checklist (still: do not submit from agents)

- [ ] Read JEI AI policy; confirm JEI is or is not viable  
- [ ] If arXiv: identify endorser; obtain endorsement for eess.IV or cs.CV  
- [ ] Rebuild `paper/main.pdf`; pass `scripts/check_paper_numbers_drift.py`  
- [x] Zenodo DOI minted: [10.5281/zenodo.23286597](https://doi.org/10.5281/zenodo.23286597) (`docs/ZENODO_STEPS.md`)  
- [ ] Update `docs/DECISION_LOG.md` with venue choice when decided  
- [ ] **Submit only from the owner’s (or mentor’s) account**
