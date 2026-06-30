#!/usr/bin/env python3
"""Source-grounding gate for the facility taxonomy layer. HARD-FAILS (exit 1) on structural
violations: every member (name + aliases) must be a real uses_facility roster value; a `skills`
entry must be backed by at least one member's recipe rows; the display name must classify as
'facility' OR be force_facility (aliases are non-force redirects, so they classify facility too).
Resolution residuals (deferred/ambiguous) are the coverage verifier's job. Reuses the builder helpers.
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
    # per-value set of backing skills, from the recipe rows
    skills_by = {}
    for r in rows:
        sks = {(s or "").strip() for s in _as_list(r.get("uses_skill"))} - {""}
        for f in _as_list(r.get("uses_facility")):
            f = (f or "").strip()
            if f:
                skills_by.setdefault(f, set()).update(sks)

    facs = [n for n in nodes if n["id"].startswith("facility:")]
    for n in facs:
        display = n["name"]
        aliases = n["data"].get("aliases", [])
        members = [display] + aliases

        # every member (display name + aliases) must be a real roster value
        for m in members:
            if m not in valid_values:
                errors.append(f"[roster] {n['id']} member {m!r} is not a real uses_facility value")

        # display name must classify as facility OR be force_facility
        cls = classify_infobox((ibs.get(display) or {}).get("infoboxes", []))
        if cls != "facility" and display not in force_fac:
            errors.append(f"[filter] {n['id']} value {display!r} classifies {cls!r} and is not force_facility")

        # each skills entry must be backed by at least one member
        member_skills: set[str] = set()
        for m in members:
            member_skills |= skills_by.get(m, set())
        for sk in n["data"].get("skills", []):
            if sk not in member_skills:
                errors.append(f"[skill] {n['id']} skill {sk!r} has no backing recipe row across any member")

    if errors:
        print(f"FACILITY VERIFICATION FAILED — {len(errors)} violation(s):")
        for e in errors[:60]:
            print("  -", e)
        return 1
    print(f"FACILITY VERIFICATION PASSED — {len(facs)} facility nodes source-grounded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
