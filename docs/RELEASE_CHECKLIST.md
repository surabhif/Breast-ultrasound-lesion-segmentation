# Owner checklist: publish project v1.0.1

**Audience:** repository owner only (`surabhif`).  
**Agents must not** create git tags, GitHub Releases, or Zenodo uploads unless the owner explicitly asks.

Research demo — not for clinical use.  
**Credit (exact):** Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (Cursor).

This is a **project / docs** release. The live model stays **v1.0.0** (weights unchanged).

---

## Zenodo DOIs (verified)

| Role | DOI |
|------|-----|
| Concept (all versions) — use for the main citation / badge | [10.5281/zenodo.23286596](https://doi.org/10.5281/zenodo.23286596) |
| Version DOI for **v1.0.1** (published 2026-11-22) | [10.5281/zenodo.24433044](https://doi.org/10.5281/zenodo.24433044) |
| Version DOI for **v1.0.0** | [10.5281/zenodo.23286597](https://doi.org/10.5281/zenodo.23286597) |

Do **not** call `23286597` the concept DOI — that number is the **v1.0.0 version** record.

---

## Before you publish

- [x] Draft PR for v1.0.1 reviewed and merged to `main`
- [x] Footer reads **Project v1.0.1 · Model v1.0.0 (weights unchanged)**
- [x] `CITATION.cff` / `.zenodo.json` / `web/package.json` say **1.0.1**
- [x] Served weights still `web/public/models/v1.0.0/` via `models/current.json`
- [x] Release notes: `docs/RELEASE_NOTES_v1.0.1.md`
- [x] GitHub Release `v1.0.1` published; Zenodo minted version DOI **10.5281/zenodo.24433044**

---

## A. Create the GitHub Release (done for v1.0.1)

1. Open **Releases** → **Draft a new release**
2. Tag `v1.0.1` on the freeze / merge commit
3. Title: `v1.0.1`
4. Paste notes from `docs/RELEASE_NOTES_v1.0.1.md`
5. Publish (not draft) so Zenodo can fire if the GitHub integration is On

---

## B. Zenodo version DOI (done for v1.0.1)

### If Zenodo ↔ GitHub is already On

Zenodo creates a new version automatically after the GitHub Release. Copy the **version DOI** from the new deposit.

### If the GitHub integration is Off or no deposit appears

1. Open the concept / all-versions page: [10.5281/zenodo.23286596](https://doi.org/10.5281/zenodo.23286596)
2. Click **New version**
3. Upload the GitHub release source zip
4. Set version metadata to **1.0.1** (note served model remains v1.0.0)
5. Publish and copy the new version DOI

One-time GitHub toggle steps: `docs/ZENODO_STEPS.md` §A.

---

## C. Keep citation files accurate after mint

1. Main citation / README badge → **concept DOI** `10.5281/zenodo.23286596`
2. List version DOIs in `CITATION.cff`, About → How to cite, and `.zenodo.json`:
   - v1.0.1 → `10.5281/zenodo.24433044`
   - v1.0.0 → `10.5281/zenodo.23286597`
3. A docs-only PR that only updates DOI text does **not** mint another DOI by itself

---

## Explicit non-goals for agents (unless the owner asks)

- [x] No agent-created tags or releases without an explicit owner ask
- [x] No Zenodo API upload by agents
- [x] No change to served `v1.0.0` weights for this project release
