# Zenodo DOI — owner click-by-click steps

**Audience:** repository owner only (`surabhif`).  
**Agents / cloud runners must NOT create Git tags, GitHub Releases, or Zenodo deposits.**

Goal: mint a citable DOI for this software via Zenodo’s GitHub integration when you publish a GitHub Release. Metadata for that deposit lives in `.zenodo.json` at the repo root (MIT license, matching `LICENSE` / `CITATION.cff`).

Sources checked for this guide (as of **2026-10-10**):

- [GitHub Docs: Referencing and citing content (Zenodo)](https://docs.github.com/en/repositories/archiving-a-github-repository/referencing-and-citing-content)
- [Zenodo login](https://zenodo.org/login) · [Zenodo GitHub settings](https://zenodo.org/account/settings/github/)

---

## Prerequisites

1. Repo is **public**: `https://github.com/surabhif/Breast-ultrasound-lesion-segmentation`
2. You are logged into GitHub as the owner account that can create releases.
3. A `LICENSE` file is present (MIT — already in repo).
4. `.zenodo.json` is on the default branch (or on the commit you will tag) so Zenodo picks up title, creators, keywords, license.
5. Decide the release tag name (suggested: `v1.0.0` for the Dec 4 freeze). Do **not** create it until freeze checklist items are ready — see `docs/FREEZE_CHECKLIST.md` and draft notes in `docs/RELEASE_NOTES_v1.0_DRAFT.md`.

---

## A. Connect Zenodo to GitHub (one-time)

1. Open **https://zenodo.org/login**
2. Click **Log in with GitHub**
3. If prompted, review OAuth permissions and click **Authorize zenodo** (or **Authorize application**)
4. After login, open **https://zenodo.org/account/settings/github/**
5. If GitHub shows an organization approval screen for Zenodo and the repo is under an org, the org owner must approve the Zenodo OAuth app first (personal account repos usually do not need this)
6. On the Zenodo GitHub page, find **`surabhif/Breast-ultrasound-lesion-segmentation`** in the repository list  
   - If missing: click **Sync now** / refresh; confirm the GitHub account linked to Zenodo is the owner account
7. To the **right** of that repository name, flip the toggle from **Off** → **On**
8. Leave the page with the switch **On**. Zenodo will now watch for new GitHub Releases on that repo

---

## B. Create a GitHub Release (owner only — this mints the DOI)

Zenodo archives the repository and issues a **new DOI each time you create a new GitHub Release**.

1. On GitHub, open the repo → **Releases** (right sidebar) → **Draft a new release**  
   Direct path pattern: `https://github.com/surabhif/Breast-ultrasound-lesion-segmentation/releases/new`
2. Click **Choose a tag** → type a new tag (e.g. `v1.0.0`) → **Create new tag on publish** (target: default branch / freeze commit)
3. Set **Release title** (e.g. `v1.0.0 — Dec 4 freeze`)
4. Paste release notes (start from `docs/RELEASE_NOTES_v1.0_DRAFT.md`; remove the DRAFT banner before publishing)
5. Optionally attach binaries (usually unnecessary — Zenodo archives the source tarball from the tag)
6. Click **Publish release**  
   - **Do not** have an agent publish this release
7. Wait a few minutes. Zenodo hooks the release, creates a deposit, and assigns a DOI of the form `10.5281/zenodo.<id>`

### Find the DOI after the release

1. Open **https://zenodo.org/** → your profile / deposits, **or** search Zenodo for the repo name
2. Open the new deposit for this release
3. Copy the DOI shown on the record page (also often emailed)
4. Concept DOI (all versions) vs version DOI: Zenodo shows both; for `CITATION.cff` prefer the **version** DOI that matches this release unless you intentionally cite “all versions”

---

## C. Update citation files with the DOI (after mint)

1. Edit `CITATION.cff`:
   - Uncomment / fill `identifiers` with `type: doi` and `value: "10.5281/zenodo.<id>"`
   - Uncomment / fill `preferred-citation.doi`
2. Edit README “How to cite” / About page cite blurb to include the DOI badge or plain `https://doi.org/10.5281/zenodo.<id>`
3. Optionally add a DOI badge to README:  
   `[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.<id>.svg)](https://doi.org/10.5281/zenodo.<id>)`
4. Commit and push those doc updates on a normal PR (this does **not** mint a new DOI by itself; only a new GitHub Release does)

---

## D. Troubleshooting

| Symptom | What to check |
|---------|----------------|
| Repo missing on Zenodo GitHub page | Wrong GitHub account linked; sync; OAuth revoked |
| Toggle On but no DOI after release | Wait 5–15 min; check Zenodo deposit “Failed” state; ensure release is a full published Release (not draft) |
| Metadata wrong | Fix `.zenodo.json` on the tagged commit; create a **new** release for a corrected deposit, or edit the Zenodo record metadata in the Zenodo UI |
| Private repo | Zenodo GitHub integration needs a **public** repo |

---

## What agents must not do

- Create or push git tags
- Create GitHub Releases (draft or published)
- Upload deposits via Zenodo API
- Claim a DOI before the owner completes steps A–B
