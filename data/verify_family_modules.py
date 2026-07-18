#!/usr/bin/env python3
"""Coverage verifier for the per-family loot-filter modules (Wave 1 restructure, design §4):
every `loot_importance` item's NAME must land in EXACTLY ONE tier `<MODULE>_<TIER>_NAMES`
`#define` default of its own family module in the GENERATED filter -- not zero (dropped by
emit_family_module), not more than one (a dedup regression).

Report-not-fail (exit 0 regardless): this checks a STRUCTURAL invariant of the generator against
its own editorial input, but per feedback_editorial_data_report_not_fail residuals are reported,
never hard-failed, so a legitimate future gap (e.g. a family split with no rows yet) doesn't force
fabrication or block an unrelated commit.

Regenerates the filter via generate_filter() (osrs_planner is an editable-installed package --
importable from any cwd, no `data/` sibling import needed here, so the tests/data package-shadow
gotcha (reference_tests_data_package_shadow) doesn't apply to this file).
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
if os.path.join(REPO, "src") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "src"))

from osrs_planner.lootfilter.generate import FAMILY_MODULES, generate_filter  # noqa: E402

_TIERS = ["SS", "S", "A", "B", "C", "D", "E"]  # GRADE_ORDER (palette.py) -- loudest first


def parse_module_tier_names(text: str, module_id: str) -> dict[str, list[str]]:
    """name -> list of tiers it appears in, read from one family module's own
    `#define <MODULE>_<TIER>_NAMES [...]` defaults (emit_family_module's NM(t))."""
    mod = module_id.upper()
    name_tiers: dict[str, list[str]] = defaultdict(list)
    for tier in _TIERS:
        m = re.search(rf"#define {re.escape(mod)}_{tier}_NAMES \[(.*?)\]", text)
        if not m:
            continue
        for raw in re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1)):
            name = raw.replace('\\"', '"').replace("\\\\", "\\")
            name_tiers[name].append(tier)
    return name_tiers


def check_family_coverage(importance: list[dict], text: str) -> tuple[list[dict], list[str]]:
    """Pure check (reused by tests): returns (per-family report rows, residual lines).
    Each report row: {family, module_id, have, total, zero (names), multi (name, tiers)}."""
    by_family: dict[str, set[str]] = defaultdict(set)
    for r in importance:
        by_family[r["family"]].add(r["name"])

    rows, residuals = [], []
    for fam, module_id, _name, _sub in FAMILY_MODULES:
        names = by_family.get(fam)
        if not names:
            continue  # no loot_importance rows for this family -> generate.py skips the module
        name_tiers = parse_module_tier_names(text, module_id)
        zero, multi, have = [], [], 0
        for n in sorted(names):
            tiers = name_tiers.get(n, [])
            if len(tiers) == 1:
                have += 1
            elif not tiers:
                zero.append(n)
            else:
                multi.append((n, tiers))
        rows.append({"family": fam, "module_id": module_id, "have": have, "total": len(names),
                     "zero": zero, "multi": multi})
        if zero:
            residuals.append(f"  {fam} ({module_id}): {len(zero)} name(s) in ZERO tiers -- {zero[:10]}")
        if multi:
            residuals.append(f"  {fam} ({module_id}): {len(multi)} name(s) in >1 tier -- {multi[:10]}")
    return rows, residuals


def main() -> int:
    importance = json.load(open(os.path.join(REPO, "data", "loot_importance.json"), encoding="utf-8"))["records"]
    text = generate_filter()  # generic build (account_state=None) -- the committed/byte-stable artifact

    rows, residuals = check_family_coverage(importance, text)

    print("FAMILY-MODULE COVERAGE (report-not-fail):")
    total_have = total_total = 0
    for row in rows:
        total_have += row["have"]
        total_total += row["total"]
        print(f"family-coverage: {row['family']:8} ({row['module_id']:8}) {row['have']}/{row['total']} covered")
    print(f"TOTAL: {total_have}/{total_total} covered across {len(rows)} family module(s)")

    if residuals:
        print(f"residuals ({len(residuals)}):")
        for line in residuals:
            print(line)
    else:
        print("residuals: none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
