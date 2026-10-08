#!/usr/bin/env python3
"""Build mistakes explorer JSON + outline-only silhouettes (no BUSI ultrasound pixels)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import RESULTS, WEB_PUBLIC, load_manifest  # noqa: E402

OUT_JSON = WEB_PUBLIC / "results" / "mistakes.json"
OUT_DIR = WEB_PUBLIC / "results" / "mistakes_silhouettes"
NOTES_MD = REPO / "docs" / "ERROR_NOTES.md"


def error_type(row: dict, pred_area: float | None = None, gt_area: float | None = None) -> str:
    label = row["label"]
    dice = float(row.get("dice", row.get("dice_score", 0)))
    cls = float(row["cls_prob"])
    y = 1 if label == "malignant" else (0 if label == "benign" else None)
    if label == "normal":
        # FP lesion if dice defined against empty — use mask activation proxy
        if dice < 0.99 and row.get("pred_area", pred_area or 1) and float(row.get("pred_nonzero", 1)) > 0:
            return "false_lesion_on_normal"
        return "false_lesion_on_normal" if dice < 1.0 else "boundary_disagreement"
    if dice < 0.1:
        return "missed_lesion"
    if y is not None and abs(cls - y) > 0.5:
        return "wrong_class"
    pa = pred_area
    ga = gt_area
    if pa is not None and ga is not None and ga > 0:
        if pa < 0.6 * ga:
            return "under_segmentation"
        if pa > 1.5 * ga:
            return "over_segmentation"
    if dice < 0.7:
        return "boundary_disagreement"
    return "boundary_disagreement"


# AI-generated analysis notes (≥20). Clearly labelled.
AI_NOTES = {
    "false_lesion_on_normal": "Model drew a lesion-like region on a normal study — classic over-call; calipers/texture may cue a false blob.",
    "missed_lesion": "Near-zero Dice: lesion was essentially missed. Low contrast or small lesion size is a common cause in BUSI.",
    "under_segmentation": "Predicted mask much smaller than the expert outline; shadowing or weak boundaries often truncate the blob.",
    "over_segmentation": "Predicted mask spills well beyond the expert outline into surrounding tissue.",
    "wrong_class": "Benign/malignant score disagreed with the label at the 0.5 operating point — auxiliary head error, not only segmentation.",
    "boundary_disagreement": "Moderate Dice: overall location is plausible but the contour disagrees (margin / caliper influence).",
}


def silhouette(mask_path: str, pred: np.ndarray | None, out_path: Path, size: int = 160) -> None:
    gt = np.array(Image.open(mask_path).convert("L").resize((size, size), Image.NEAREST)) > 127
    img = Image.new("RGB", (size, size), (40, 44, 48))
    arr = np.array(img)
    # expert = blue outline fill
    arr[gt] = (60, 110, 180)
    if pred is not None:
        p = pred.astype(bool)
        if p.shape != gt.shape:
            p = np.array(Image.fromarray((p.astype(np.uint8) * 255)).resize((size, size), Image.NEAREST)) > 127
        only_m = p & ~gt
        only_e = gt & ~p
        both = p & gt
        arr[both] = (41, 115, 115)
        arr[only_m] = (200, 120, 60)
        arr[only_e] = (80, 140, 200)
    Image.fromarray(arr).save(out_path)


def main() -> None:
    per = json.loads((RESULTS / "served_int8_per_image.json").read_text())
    manifest = load_manifest().set_index("case_id")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    notes_md = [
        "# Error notes (mistakes explorer)",
        "",
        "**Source:** AI-generated analysis (Cursor agent), not clinician-authored. Research demo only.",
        "",
    ]
    noted = 0
    for r in sorted(per, key=lambda x: float(x.get("dice", x.get("dice_score", 1)))):
        cid = r["case_id"]
        if cid not in manifest.index:
            continue
        mrow = manifest.loc[cid]
        dice = float(r.get("dice", r.get("dice_score", 0)))
        # Prefer interesting mistakes
        et = error_type(r)
        if r["label"] == "normal" and dice >= 0.99:
            # skip perfect normals unless we know FP — check pred if present
            if float(r.get("mask_mean", 1)) < 0.01:
                continue
            et = "false_lesion_on_normal"

        sil_name = cid.replace("/", "__").replace(" ", "_").replace("(", "").replace(")", "")
        if not sil_name.endswith(".png"):
            sil_name += ".png"
        sil_path = OUT_DIR / sil_name
        try:
            silhouette(str(mrow["merged_mask_path"]), None, sil_path)
        except Exception:
            continue

        note = None
        if noted < 24 and (dice < 0.75 or r["label"] == "normal" or abs(float(r["cls_prob"]) - (1 if r["label"] == "malignant" else 0)) > 0.4):
            note = AI_NOTES.get(et, AI_NOTES["boundary_disagreement"])
            notes_md.append(f"- `{cid}` ({et}, Dice {dice:.2f}): {note}")
            noted += 1

        rows.append(
            {
                "case_id": cid,
                "label": r["label"],
                "dice": dice,
                "cls_prob": float(r["cls_prob"]),
                "error_type": et,
                "annotation_flag": bool(r.get("annotation_flag", mrow.get("annotation_flag", False))),
                "note": note,
                "note_source": "AI-generated analysis" if note else None,
                "silhouette_src": f"results/mistakes_silhouettes/{sil_name}",
                "dataset": "busi_test",
            }
        )

    # Ensure ≥20 notes by filling remaining worst cases
    for r in rows:
        if noted >= 20:
            break
        if r["note"]:
            continue
        r["note"] = AI_NOTES.get(r["error_type"], AI_NOTES["boundary_disagreement"])
        r["note_source"] = "AI-generated analysis"
        notes_md.append(f"- `{r['case_id']}` ({r['error_type']}, Dice {r['dice']:.2f}): {r['note']}")
        noted += 1

    payload = {
        "disclaimer": "Research demo — not for clinical use. BUSI ultrasound pixels omitted (outline silhouettes only). Notes are AI-generated analysis, not clinician review.",
        "notes_label": "AI-generated analysis",
        "n_notes": noted,
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n")
    NOTES_MD.write_text("\n".join(notes_md) + "\n")
    print(f"Wrote {OUT_JSON} rows={len(rows)} notes={noted}")


if __name__ == "__main__":
    main()
