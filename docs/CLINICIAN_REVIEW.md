# Clinician review protocol

**Status:** Ready for outreach (family sends emails) · **Do not contact clinicians from automated agents.**  
**Decision:** D4 (2026-10-08) — see `docs/DECISION_LOG.md`.

Research demo, not for clinical use.

---

## Purpose

Ask 3–4 clinicians for informal feedback on **outline quality** and **wording clarity** on a small set of **CC BY external** ultrasound images (BrEaST). Reviewers are **acknowledged by default**, not listed as co-authors.

Suggested mix:

- ≥1 breast radiologist or sonographer
- ≥1 breast or surgical oncologist

Also ask the **school counselor / teacher** whether any school review or IRB-like process applies to talking with clinicians for a student research project.

---

## Review tool (static, private)

- URL pattern: `/review?k=<token>` (not linked in the site nav).
- Default token for local / draft use: `busi-review-2026` (change before sharing widely).
- Answers stored in **browser `localStorage` only**; **CSV export** button; **no server, no analytics**.
- Review set: CC BY BrEaST samples under `web/public/samples/external/` (attribution on page).

What reviewers score (per image):

1. Outline usefulness (1–5)
2. Would this outline help or hurt a teaching discussion? (help / neutral / hurt)
3. Free-text note (optional)

Plus overall comments on disclaimers and Results wording.

---

## Outreach email template (family may send)

Subject: Informal review request — high-school breast ultrasound AI demo (research only)

Dear Dr. [Name],

I'm writing on behalf of Surabhi Fadnavis, a high-school senior working on an educational research demo for breast ultrasound lesion segmentation (not a medical device; not for clinical use). She trained a small model on the public BUSI dataset and evaluated it on independent CC BY datasets (BUS-BRA, BrEaST).

Would you be willing to spend ~20–30 minutes reviewing ~6 public ultrasound images with model outlines on a private static page, and sharing brief comments on outline quality and how clearly the site states its limitations? Reviewers are acknowledged by name only with consent; the default is acknowledgement, not co-authorship.

Page: [paste review URL with token]  
Project: https://surabhif.github.io/Breast-ultrasound-lesion-segmentation/

Thank you for considering this educational request.

Best regards,  
[Parent/guardian name]

---

## Consent & acknowledgement

- Written consent required before listing a name publicly.
- Default wording: “Reviewed informally by [Name], [role], who provided feedback on outline clarity; they did not validate clinical performance.”
- Never say “clinically validated.”

---

## Images

Only **CC BY** external samples (BrEaST). BUSI ultrasound pixels are not used on the review page (decision D2).
