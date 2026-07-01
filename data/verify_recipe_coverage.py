#!/usr/bin/env python3
"""Coverage report for the recipe roster (report-not-fail, exit 0). Per core skill:
Bucket rows vs recipes with a resolvable output; and disclosed residuals: unresolved
output names (recipe skipped), unresolved material/tool names (edge skipped), unresolved
facilities (no requires_facility edge). Reuses the builder helpers.
"""
from __future__ import annotations
import html, json, os, sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.recipes import CORE_SKILLS, _as_list  # noqa: E402
from kg_ingest.builders.map_varrock import make_item_resolver  # noqa: E402


def main() -> int:
    rows = json.load(open(os.path.join(ROOT, "data", "raw", "recipe_bucket.json"), encoding="utf-8"))["bucket"]
    recs = json.load(open(os.path.join(ROOT, "data", "item_dictionary.json"), encoding="utf-8"))["records"]
    nodes = json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
    fac_names = {}
    for n in nodes:
        if n["id"].startswith("facility:"):
            fac_names[n["name"]] = n["id"]
            for a in n["data"].get("aliases", []):
                fac_names[a] = n["id"]
    resolve = make_item_resolver(recs)
    def ri(name):
        return resolve(html.unescape((name or "").strip()))

    per_skill = Counter(); built = 0
    unres_out, unres_mat, unres_fac = [], set(), set()
    for r in rows:
        sk = {s for s in _as_list(r.get("uses_skill")) if s} & CORE_SKILLS
        if not sk:
            continue
        for s in sk:
            per_skill[s] += 1
        try:
            pj = json.loads(r.get("production_json") or "{}")
        except Exception:
            pj = {}
        o = pj.get("output")
        if not (isinstance(o, dict) and o.get("name")):
            continue
        if ri(o["name"]) is None:
            unres_out.append(o["name"]); continue
        built += 1
        for m in (pj.get("materials") or []):
            if m.get("name") and ri(m["name"]) is None:
                unres_mat.add(m["name"])
        for f in _as_list(r.get("uses_facility")):
            if (f or "").strip() and (f or "").strip() not in fac_names:
                unres_fac.add((f or "").strip())

    print("RECIPE COVERAGE (report-not-fail):")
    print(f"  core-skill rows: {sum(per_skill.values())}  per-skill: {dict(per_skill.most_common())}")
    print(f"  recipes built (resolvable output): {built}")
    print(f"  unresolved OUTPUT names (recipe skipped): {len(set(unres_out))}")
    for n in sorted(set(unres_out))[:20]:
        print("     -", n)
    print(f"  unresolved MATERIAL/TOOL names (edge skipped): {len(unres_mat)}")
    print(f"  unresolved FACILITIES (no requires_facility): {len(unres_fac)}")
    for f in sorted(unres_fac)[:20]:
        print("     -", f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
