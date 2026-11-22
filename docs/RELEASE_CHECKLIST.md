# Owner checklist: publish project v1.0.1

**Audience:** repository owner only (`surabhif`).  
**Agents must not** create git tags, GitHub Releases, or Zenodo uploads.

Research demo — not for clinical use.  
**Credit (exact):** Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (Cursor).

This is a **project / docs** release. The live model stays **v1.0.0** (weights unchanged).

---

## Before you publish

- [ ] Draft PR for v1.0.1 is reviewed and merged to `main` (or you are tagging the intended merge commit)
- [ ] Footer reads **Project v1.0.1 · Model v1.0.0 (weights unchanged)**
- [ ] `CITATION.cff` / `.zenodo.json` / `web/package.json` say **1.0.1**; `date-released` is the planned publish day
- [ ] Served weights still `web/public/models/v1.0.0/` via `models/current.json`
- [ ] Release notes ready: `docs/RELEASE_NOTES_v1.0.1.md`
- [ ] CI green on the commit you will tag

---

## A. Create the GitHub Release (this is what publishes)

1. Open **Releases** → **Draft a new release**  
   `https://github.com/surabhif/Breast-ultrasound-lesion-segmentation/releases/new`
2. **Choose a tag** → type `v1.0.1` → create the tag on the freeze / merge commit (default branch)
3. **Release title:** `v1.0.1 — Project / docs release (model stays v1.0.0)`
4. Paste notes from `docs/RELEASE_NOTES_v1.0.1.md` (keep the credit line and disclaimer)
5. Click **Publish release** (not “Save draft” if you want Zenodo to fire)

Do **not** ask an agent to publish this.

---

## B. Zenodo version DOI

### If Zenodo ↔ GitHub is already On

1. Wait a few minutes after the GitHub Release publishes
2. Open the new Zenodo version for this deposit (profile → uploads, or search the repo name)
3. Copy the **new version DOI** (different from the old v1.0.0 / concept id)

### If the GitHub integration is Off or no deposit appears

1. Open the existing Zenodo record for this project (concept / all-versions page for [10.5281/zenodo.23286597](https://doi.org/10.5281/zenodo.23286597))
2. Click **New version**
3. Upload the GitHub release source zip (from the Release assets / “Source code (zip)”), or the archive Zenodo would have pulled
4. Set version metadata to **1.0.1** (title/description should note served model remains v1.0.0)
5. Publish the new version and copy the **new version DOI**

One-time GitHub toggle steps (if needed): `docs/ZENODO_STEPS.md` §A.

---

## C. Add the new version DOI afterwards

1. Edit `CITATION.cff`:
   - Keep the **concept DOI** `10.5281/zenodo.23286597` (all versions)
   - Add (or replace the preferred citation with) the **new version DOI** Zenodo just minted for 1.0.1
2. Update About → How to cite, README “How to cite”, and `.zenodo.json` related identifiers if you list the version DOI there
3. Optionally refresh the README DOI badge to the new version DOI
4. Commit/push on a normal docs PR — that commit by itself does **not** mint another DOI

---

## Explicit non-goals for agents

- [x] No agent-created tags or releases
- [x] No Zenodo API upload by agents
- [x] No change to served `v1.0.0` weights for this project release
