#!/usr/bin/env python3
"""Source-grounding gate for the facility taxonomy layer. HARD-FAILS (exit 1) on structural
violations: a facility node whose name is not a real distinct uses_facility value; a `skills`
entry with no backing recipe row (that facility x that skill); a facility whose value does NOT
classify as 'facility' AND is not force_facility. Resolution residuals (deferred/ambiguous) are
the coverage verifier's job. Reuses the builder helpers.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.facilities import classify_infobox, facility_roster, _as_list  # noqa: E402


def main() -> int:
    errors = []
    raw = os.path.join(ROOT, "data", "raw")
    rows = json.load(open(os.path.join(raw, "recipe_facility_bucket.json"), encoding="utf-8"))["bucket"]
    ibs = json.load(open(os.path.join(raw, "wiki_facility_infoboxes.json"), encoding="utf-8"))["infoboxes"]
    ov = json.load(open(os.path.join(ROOT, "data", "map", "facility_overrides.json"), encoding="utf-8"))
    nodes = json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))

    valid_values = set(facility_roster(rows))
    force_fac = {o["value"] for o in ov.get("force_facility", [])}
    # facility -> set of backing skills, from the recipe rows
    skills_by = {}
    for r in rows:
        sks = {(s or "").strip() for s in _as_list(r.get("uses_skill"))} - {""}
        for f in _as_list(r.get("uses_facility")):
            f = (f or "").strip()
            if f:
                skills_by.setdefault(f, set()).update(sks)

    facs = [n for n in nodes if n["id"].startswith("facility:")]
    for n in facs:
        value = n["name"]
        if value not in valid_values:
            errors.append(f"[roster] {n['id']} name {value!r} is not a real uses_facility value")
            continue
        cls = classify_infobox((ibs.get(value) or {}).get("infoboxes", []))
        if cls != "facility" and value not in force_fac:
            errors.append(f"[filter] {n['id']} value {value!r} classifies {cls!r} and is not force_facility")
        for sk in n["data"].get("skills", []):
            if sk not in skills_by.get(value, set()):
                errors.append(f"[skill] {n['id']} skill {sk!r} has no backing recipe row")

    if errors:
        print(f"FACILITY VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors[:60]:
            print("  -", e)
        return 1
    print(f"FACILITY VERIFICATION PASSED — {len(facs)} facility nodes source-grounded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
