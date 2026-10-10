#!/usr/bin/env python3
"""Fail if paper/numbers.tex disagrees with metrics.json, or main.tex hardcodes drifted digits."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from export_paper_numbers import METRICS, OUT, collect  # noqa: E402

MAIN = ROOT / "paper" / "main.tex"

# Macros that appear as primary Claims in the paper — must be referenced via \\Name
REQUIRED_MACROS = [
    "MetricServedTestDice",
    "MetricServedLesionDice",
    "MetricServedAuc",
    "MetricBusbraDice",
    "MetricBusbraAuc",
    "MetricBreastDice",
    "MetricBreastAuc",
    "MetricNormalFP",
    "MetricModelVersion",
]


def parse_tex_macros(text: str) -> dict[str, str]:
    pat = re.compile(r"\\newcommand\{\\([A-Za-z]+)\}\{([^}]*)\}")
    return {m.group(1): m.group(2) for m in pat.finditer(text)}


def main() -> int:
    if not METRICS.exists():
        print(f"FAIL: missing {METRICS}")
        return 1
    if not OUT.exists():
        print(f"FAIL: missing {OUT} — run python scripts/export_paper_numbers.py")
        return 1
    if not MAIN.exists():
        print(f"FAIL: missing {MAIN}")
        return 1

    import json

    fresh = collect(json.loads(METRICS.read_text()))
    committed = parse_tex_macros(OUT.read_text())

    mismatches = []
    for k, v in fresh.items():
        if k not in committed:
            mismatches.append(f"{k}: missing from numbers.tex")
        elif committed[k] != v:
            mismatches.append(f"{k}: numbers.tex={committed[k]!r} fresh={v!r}")

    extra = sorted(set(committed) - set(fresh))
    for k in extra:
        mismatches.append(f"{k}: extra in numbers.tex (not in exporter)")

    if mismatches:
        print("FAIL: paper/numbers.tex drifts from metrics.json:")
        for m in mismatches:
            print(" ", m)
        print("Re-run: python scripts/export_paper_numbers.py")
        return 1

    main_tex = MAIN.read_text()
    missing_refs = [name for name in REQUIRED_MACROS if f"\\{name}" not in main_tex]
    if missing_refs:
        print("FAIL: main.tex does not reference required macros:")
        for name in missing_refs:
            print(f"  \\{name}")
        return 1

    # Guard against hardcoding the primary INT8 Dice as a naked 0.xxx (allow macros only).
    # Strip comments and macro definitions via input.
    body = re.sub(r"%.*", "", main_tex)
    # Disallow literal copies of key rounded values outside commands.
    forbidden_literals = [
        fresh["MetricServedTestDice"],
        fresh["MetricServedLesionDice"],
        fresh["MetricServedAuc"],
        fresh["MetricBusbraDice"],
        fresh["MetricBreastDice"],
    ]
    # Remove known macro uses so remaining body shouldn't contain those strings.
    scrubbed = body
    for name in fresh:
        scrubbed = scrubbed.replace(f"\\{name}", "")
    found = []
    for lit in forbidden_literals:
        if lit == "n/a":
            continue
        # Match as standalone decimal token
        if re.search(rf"(?<![0-9.]){re.escape(lit)}(?![0-9])", scrubbed):
            found.append(lit)
    if found:
        print("FAIL: main.tex appears to hardcode metrics that should use macros:")
        for lit in found:
            print(f"  {lit}")
        print("Use \\MetricServedTestDice / \\MetricBusbraDice / etc. from numbers.tex")
        return 1

    print(
        f"OK: {len(fresh)} macros match metrics.json; "
        f"{len(REQUIRED_MACROS)} required refs present in main.tex"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
