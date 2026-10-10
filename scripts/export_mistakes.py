#!/usr/bin/env python3
"""Build mistakes explorer JSON + outline silhouettes (expert + model; no BUSI pixels)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from busi_data import (  # noqa: E402
    RESULTS,
    WEB_PUBLIC,
    imagenet_tensor_from_rgb,
    load_manifest,
    remove_small_components,
)

OUT_JSON = WEB_PUBLIC / "results" / "mistakes.json"
OUT_DIR = WEB_PUBLIC / "results" / "mistakes_silhouettes"
NOTES_MD = REPO / "docs" / "ERROR_NOTES.md"
ONNX = WEB_PUBLIC / "models" / "v1.0.0" / "busi_unet.onnx"
SEG_THRESH = 0.4
MIN_AREA = 40


def error_type(row: dict, pred_area: float, gt_area: float) -> str:
    label = row["label"]
    dice = float(row.get("dice", row.get("dice_score", 0)))
    cls = float(row["cls_prob"])
    y = 1 if label == "malignant" else (0 if label == "benign" else None)
    if label == "normal":
        return "false_lesion_on_normal" if pred_area > 0 else "boundary_disagreement"
    if dice < 0.1:
        return "missed_lesion"
    if y is not None and abs(cls - y) > 0.5:
        return "wrong_class"
    if gt_area > 0:
        if pred_area < 0.6 * gt_area:
            return "under_segmentation"
        if pred_area > 1.5 * gt_area:
            return "over_segmentation"
    if dice < 0.7:
        return "boundary_disagreement"
    return "boundary_disagreement"


AI_NOTES = {
    "false_lesion_on_normal": "Model drew a lesion-like region on a normal study — classic over-call; calipers/texture may cue a false blob.",
    "missed_lesion": "Near-zero Dice: lesion was essentially missed. Low contrast or small lesion size is a common cause in BUSI.",
    "under_segmentation": "Predicted mask much smaller than the expert outline; shadowing or weak boundaries often truncate the blob.",
    "over_segmentation": "Predicted mask spills well beyond the expert outline into surrounding tissue.",
    "wrong_class": "Benign/malignant score disagreed with the label at the 0.5 operating point — auxiliary head error, not only segmentation.",
    "boundary_disagreement": "Moderate Dice: overall location is plausible but the contour disagrees (margin / caliper influence).",
}


def _outline(mask: np.ndarray) -> np.ndarray:
    """4-neighbour boundary pixels of a boolean mask."""
    m = mask.astype(bool)
    if not m.any():
        return m
    up = np.zeros_like(m)
    down = np.zeros_like(m)
    left = np.zeros_like(m)
    right = np.zeros_like(m)
    up[1:] = m[:-1]
    down[:-1] = m[1:]
    left[:, 1:] = m[:, :-1]
    right[:, :-1] = m[:, 1:]
    return m & ~(up & down & left & right)


def silhouette(gt: np.ndarray, pred: np.ndarray, out_path: Path, size: int = 160) -> None:
    """Gray background; teal fill = agreement; blue = expert-only; orange = model-only; outlines bold."""
    if gt.shape != (size, size):
        gt = (
            np.array(Image.fromarray((gt.astype(np.uint8) * 255)).resize((size, size), Image.NEAREST))
            > 127
        )
    if pred.shape != (size, size):
        pred = (
            np.array(
                Image.fromarray((pred.astype(np.uint8) * 255)).resize((size, size), Image.NEAREST)
            )
            > 127
        )
    arr = np.full((size, size, 3), 48, dtype=np.uint8)
    both = gt & pred
    only_e = gt & ~pred
    only_m = pred & ~gt
    arr[both] = (41, 115, 115)
    arr[only_e] = (70, 120, 190)
    arr[only_m] = (210, 130, 55)
    # Distinct outlines on top
    e_edge = _outline(gt)
    m_edge = _outline(pred)
    arr[e_edge] = (90, 160, 255)
    arr[m_edge] = (255, 170, 60)
    Image.fromarray(arr).save(out_path)


def predict_mask(sess: ort.InferenceSession, image_path: str, size: int = 160) -> np.ndarray:
    rgb = np.asarray(Image.open(image_path).convert("RGB"))
    x = imagenet_tensor_from_rgb(rgb, size)
    outs = sess.run(None, {"input": x})
    names = [o.name for o in sess.get_outputs()]
    seg = outs[names.index("seg_mask")] if "seg_mask" in names else outs[0]
    return remove_small_components(seg[0, 0] > SEG_THRESH, MIN_AREA)


def main() -> None:
    per = json.loads((RESULTS / "served_int8_per_image.json").read_text())
    manifest = load_manifest().set_index("case_id")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sess = ort.InferenceSession(str(ONNX), providers=["CPUExecutionProvider"])

    rows = []
    notes_md = [
        "# Error notes (Model Errors explorer)",
        "",
        "**Source:** AI-generated analysis (Cursor agent). Research demo only.",
        "",
    ]
    noted = 0
    for r in sorted(per, key=lambda x: float(x.get("dice", x.get("dice_score", 1)))):
        cid = r["case_id"]
        if cid not in manifest.index:
            continue
        mrow = manifest.loc[cid]
        dice = float(r.get("dice", r.get("dice_score", 0)))
        pred_area = float(r.get("pred_area", 0))
        gt_area = float(r.get("gt_area", 0))
        et = error_type(r, pred_area, gt_area)
        if r["label"] == "normal" and dice >= 0.99 and pred_area <= 0:
            continue

        sil_name = cid.replace("/", "__").replace(" ", "_").replace("(", "").replace(")", "")
        if not sil_name.endswith(".png"):
            sil_name += ".png"
        sil_path = OUT_DIR / sil_name

        gt = np.array(Image.open(mrow["merged_mask_path"]).convert("L").resize((160, 160), Image.NEAREST)) > 127
        try:
            pred = predict_mask(sess, str(mrow["image_path"]))
        except Exception as e:
            print("predict failed", cid, e)
            continue
        silhouette(gt, pred, sil_path)

        note = None
        if noted < 24 and (
            dice < 0.75
            or r["label"] == "normal"
            or abs(float(r["cls_prob"]) - (1 if r["label"] == "malignant" else 0)) > 0.4
        ):
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
        "disclaimer": "Research demo — not for clinical use. BUSI ultrasound pixels omitted (outline silhouettes only). Notes are AI-generated analysis.",
        "notes_label": "AI-generated analysis",
        "legend": {
            "expert": "Expert outline (blue)",
            "model": "Model outline (orange)",
            "overlap": "Agreement fill (teal)",
        },
        "n_notes": noted,
        "rows": rows,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2) + "\n")
    NOTES_MD.write_text("\n".join(notes_md) + "\n")
    print(f"Wrote {OUT_JSON} rows={len(rows)} notes={noted}")


if __name__ == "__main__":
    main()
