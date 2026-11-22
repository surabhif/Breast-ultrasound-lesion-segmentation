# Release notes for project / software v1.0.1

**Suggested tag (owner-only):** `v1.0.1`  
**Suggested title:** `v1.0.1 — Project / docs release (model stays v1.0.0)`  
**Live demo:** https://surabhif.github.io/Breast-ultrasound-lesion-segmentation/  
**Research demo — not for clinical use.**

Agents must **not** create the git tag, GitHub Release, or Zenodo upload. See `docs/RELEASE_CHECKLIST.md`.

---

## Summary (plain words)

This is a **project and docs** release. The live browser model is still **v1.0.0** — same weight file, same download size, same default outline settings. Nothing about the served network was retrained or swapped for this tag.

v1.0.1 locks in the site and documentation work merged after the v1.0.0 Zenodo record ([10.5281/zenodo.23286597](https://doi.org/10.5281/zenodo.23286597)): LinkedIn name links, plain-language docs cleanup, the Why page, the display-only no-lump outline gate, SEO fixes and the one-page summary PDF, the guided “Try 3 cases” tour, demo/Results UX upgrades, and a fresh outside-set score for that gate. Two later experiments are documented honestly and **were not shipped**.

**Credit:** Project by Surabhi Fadnavis. The code, analysis, text, and video were produced with AI tools (Cursor).

---

## What stayed the same (model)

- Served weights: **v1.0.0** ResNet-18 U-Net INT8 (~11.7 MB), 160×160
- Headline BUSI browser scores unchanged: Dice **0.697**, lump-only Dice **0.764**, AUC **0.931**, false outlines on normal **12/19**
- Default outline cut-off **0.4**, min-component area **40**, class cut-off **0.5**
- No-lump display gate threshold still **0.96** (hide outline when the strongest soft-mask pixel is below that)

---

## What is new in the project (since Zenodo v1.0.0)

### Site and docs

- Name links to LinkedIn across the site
- Plain-language GitHub docs and site copy cleanup
- Draft **Why I built this** page + short Home results summary
- Lighthouse SEO fixes + printable **one-page summary PDF**
- Guided **Try 3 cases** tour and accessible glossary tips
- Demo UX: example scan strip, side-by-side view, PNG download, dark mode, page-speed work (PR #22)
- Five more upgrades: struggles gallery, phone polish, Tight/Loose outline wording, print CSS, loading tips (PR #23)
- Footer now says **Project v1.0.1 · Model v1.0.0 (weights unchanged)** so the two version numbers are not confused

### No-lump outline gate (display only)

- Default-on switch on the Demo: hide the outline when the model’s strongest outline pixel is below **0.96** (chosen on BUSI validation)
- Does **not** change weights or the class (harmless vs cancerous) score
- Outside sets re-scored with the same gate (PR #24). On both available sets, overall and lump-only Dice got **worse**; AUC stayed the same:

| Set | Overall Dice (raw → gated) | Lump-only Dice | AUC |
|-----|----------------------------|----------------|-----|
| BUS-BRA | 0.714 → **0.653** (worse) | 0.714 → **0.653** | 0.638 (unchanged) |
| BrEaST | 0.627 → **0.572** (worse) | 0.629 → **0.573** | 0.721 (unchanged) |
| BUS-UCLM | raw only 0.386 / lesion 0.679 | — | 0.780 — **not re-scored** when the archive was unavailable on the eval machine |

### Experiments that did **not** ship

- **Test-time averaging** (PR #25): averaging outline + class score over flips/shifts helped a little on BUSI held-out with the gate on, but **outside Dice fell**, and browser time was about **2×**. No Fast/Steadier toggle was added to the Demo. Write-up: `docs/TTA_AVERAGING.md`.
- **v1.1 BUSI-only candidates** (PR #26): larger resolution / ResNet-34 tries. None passed the full outside-Dice swap rule. One setting (`r18@224`) matched/beat v1 on held-out Dice and AUC but failed outside. **Write-up only** — no Results table, no candidate ONNX on the site. Write-up: `docs/V1_1_EXPERIMENT.md`.

---

## Versioning and cite

- **Project / software:** 1.0.1 (`CITATION.cff`, `.zenodo.json`, `web/package.json`)
- **Served model:** 1.0.0
- **DOI for now:** concept DOI https://doi.org/10.5281/zenodo.23286597 (also the v1.0.0 version DOI). After the owner publishes this release, Zenodo should mint a **new version DOI** — add that to `CITATION.cff` / About / README (see `docs/RELEASE_CHECKLIST.md`).

---

## Known limitations (same honesty as v1.0.0)

- Not a medical device; not for diagnosis, screening, or care
- BUSI has no patient IDs; near-dup grouping ≠ true patient split
- High false-outline rate on normal (no lump) images (12/19 without the display gate)
- Outside ranking scores (AUC) drop vs internal BUSI
- The display-only no-lump gate **hurts** outside Dice on BUS-BRA and BrEaST
- BUS-UCLM all-image Dice is pulled down by false outlines on normal scans (320/413); prefer lesion Dice for cross-dataset comparison

---

## Checklist before the owner publishes

See `docs/RELEASE_CHECKLIST.md`.
