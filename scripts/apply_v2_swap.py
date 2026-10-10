#!/usr/bin/env python3
"""Apply MODEL_POLICY (D3) to Phase 4 v2_experiment.json.

If best candidate passes all swap checks AND INT8 ≤ ~25 MB:
  promote to web/public/models/v2.0.0/, rewrite current.json with new cache_key.
Else:
  keep v1.0.0 served; publish comparison into metrics.json for Results page.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "results"
WEB = REPO / "web" / "public"
EXP = RESULTS / "v2_experiment.json"
METRICS = WEB / "results" / "metrics.json"


def r3(x):
    return None if x is None else round(float(x), 3)


def main() -> None:
    if not EXP.exists():
        print("No results/v2_experiment.json — run scripts/train_v2.py first")
        sys.exit(1)
    exp = json.loads(EXP.read_text())
    metrics = json.loads(METRICS.read_text())
    v1 = exp.get("v1_baselines") or {}
    best = exp.get("best")
    decision = exp.get("model_policy_decision") or {}
    swap_ok = bool(decision.get("swap_ok")) and best is not None and best.get("swap_ok")

    # Size gate (also inside train_v2 checks)
    if best and best.get("onnx_int8_mb") is not None and best["onnx_int8_mb"] > 25.5:
        swap_ok = False
        decision["note"] = (
            f"INT8 {best['onnx_int8_mb']:.1f} MB exceeds ~25 MB budget — keep v1.0.0. "
            + str(decision.get("note") or "")
        )

    swap_criteria = []
    if best and best.get("metrics"):
        m = best["metrics"]
        checks = best.get("checks") or {}
        swap_criteria = [
            {
                "criterion": "Clean-subset Dice (BUSI)",
                "rule": "v2 ≥ v1",
                "v1": r3(v1.get("clean_dice")),
                "v2": r3(m.get("clean_dice")),
                "passed": bool(checks.get("clean_dice_ok")),
            },
            {
                "criterion": "External Dice (BUS-BRA held-out)",
                "rule": "v2 ≥ v1",
                "v1": r3(v1.get("busbra_dice")),
                "v2": r3(m.get("busbra_dice")),
                "passed": bool(checks.get("busbra_ok")),
            },
            {
                "criterion": "External Dice (BrEaST)",
                "rule": "v2 ≥ v1",
                "v1": r3(v1.get("breast_dice")),
                "v2": r3(m.get("breast_dice")),
                "passed": bool(checks.get("breast_ok")),
            },
            {
                "criterion": "BUSI test AUC",
                "rule": "drop ≤ 0.02",
                "v1": r3(v1.get("auc")),
                "v2": r3(m.get("auc")),
                "passed": bool(checks.get("auc_ok")),
            },
            {
                "criterion": "INT8 ONNX size",
                "rule": "≤ ~25 MB",
                "v1": r3(v1.get("int8_mb")),
                "v2": r3(m.get("int8_mb")),
                "passed": bool(checks.get("size_ok", True)),
            },
        ]

    if swap_ok and best:
        v2_dir = WEB / "models" / "v2.0.0"
        v2_dir.mkdir(parents=True, exist_ok=True)
        src = Path(best["onnx_int8"])
        dest = v2_dir / "busi_unet.onnx"
        shutil.copy2(src, dest)
        sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        model_json = {
            "version": "2.0.0",
            "sha256": sha,
            "filename": "busi_unet.onnx",
            "size_bytes": dest.stat().st_size,
            "quantization": "onnxruntime dynamic QUInt8",
            "parent": "1.0.0",
            "model_kind": best.get("model_kind"),
            "img_size": best.get("img_size"),
            "postprocess": best.get("postprocess")
            or {"seg_threshold": 0.4, "min_component_area": 40, "cls_threshold": 0.5},
            "note": "Phase 4 multi-dataset candidate that passed MODEL_POLICY swap rule",
            "metrics_note": decision.get("note"),
        }
        # Ensure cls_threshold present
        if "cls_threshold" not in model_json["postprocess"]:
            model_json["postprocess"]["cls_threshold"] = 0.5
        (v2_dir / "model.json").write_text(json.dumps(model_json, indent=2) + "\n")
        current = {
            "version": "2.0.0",
            "path": "models/v2.0.0",
            "sha256": sha,
            "cache_key": f"busi-unet-v2.0.0-{sha[:8]}",
        }
        (WEB / "models" / "current.json").write_text(json.dumps(current, indent=2) + "\n")
        # Also copy to legacy path used by some scripts
        shutil.copy2(dest, WEB / "models" / "busi_unet.onnx")
        print("PROMOTED v2.0.0", decision.get("note"))
        served_unchanged = False
        decision_sentence = "v2 met the rule, so the site serves v2.0.0."
        metrics["model_version"] = "2.0.0"
    else:
        print("KEEP v1.0.0 —", decision.get("note"))
        served_unchanged = True
        decision_sentence = "v2 did not meet the rule, so the site keeps serving v1.0.0."

    metrics["v2_experiment"] = {
        "served_unchanged": served_unchanged,
        "decision_sentence": decision_sentence,
        "swap_criteria": swap_criteria,
        "swap_note": decision.get("note"),
        "table": exp.get("table") or [],
        "config": {
            "model": (exp.get("config") or {}).get("model"),
            "img_size": (exp.get("config") or {}).get("img_size"),
            "seeds": (exp.get("config") or {}).get("seeds"),
            "inpaint": (exp.get("config") or {}).get("inpaint"),
            "loss": "Dice + focal",
        },
        "busbra_split": exp.get("busbra_split"),
        "source": "results/v2_experiment.json",
        "note": (
            "Phase 4: BUSI train + patient-grouped BUS-BRA train; held-out BUS-BRA test; "
            "BrEaST fully external. Comparison vs served v1.0.0 under MODEL_POLICY (D3)."
        ),
    }
    METRICS.write_text(json.dumps(metrics, indent=2) + "\n")
    exp["model_policy_decision"]["swap_ok"] = swap_ok
    exp["model_policy_decision"]["served_unchanged"] = served_unchanged
    EXP.write_text(json.dumps(exp, indent=2) + "\n")


if __name__ == "__main__":
    main()
