#!/usr/bin/env python3
"""Coverage gate for the farming-patch layer. REPORTS (never fails, exit 0): of the 12
Category:Farming patches members, which patch-type members yielded >=1 node; the
parented/FLAG split; and the DISCLOSED deferrals (activity + quest tail, coords,
patch_count collapse) so no gap is hidden.

REVISION: only 3 of the 12 category members carry an on-page infobox, so
`classify_member`/`classification` returns 'patch_type' for just 3 (Coral nursery
(patch)/Flower patch/Spirit tree) and 'other' for the 6 infobox-less patch pages +
Special patches. The roster completeness anchor is therefore this committed name->role
map (NOT infobox-derived) -- see the task-6 brief revision.
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "src"))
from kg_ingest.builders.farming_tables import parse_patch_tables  # noqa: E402

# The 12 Category:Farming patches members -> roster role (NOT infobox-derived; only 3 carry
# an on-page infobox). This is the completeness anchor.
MEMBER_TYPE = {
    "Allotment patch": "allotment", "Flower patch": "flower", "Herb patch": "herb",
    "Bush patch": "bush", "Hops patch": "hops", "Tree patch": "tree",
    "Fruit tree patch": "fruit_tree", "Spirit tree": "spirit_tree", "Coral nursery (patch)": "coral",
}
MEMBER_UMBRELLA = {"Special patches"}            # yields the special crops
MEMBER_EXCLUDE = {"Coral Nurseries", "Chet"}     # place / npc -> force_exclude, no node


def main() -> int:
    nodes = json.load(open(os.path.join(ROOT, "kg", "nodes.json"), encoding="utf-8"))
    edges = json.load(open(os.path.join(ROOT, "kg", "edges.json"), encoding="utf-8"))
    cat = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_farming_patch_category.json"),
                         encoding="utf-8"))["members"]
    tables = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_farming_patch_tables.json"),
                            encoding="utf-8"))["tables"]
    ov = json.load(open(os.path.join(ROOT, "data", "map", "farming_overrides.json"), encoding="utf-8"))
    rows = parse_patch_tables(tables)

    fp = [n for n in nodes if n["id"].startswith("farming_patch:")]
    located = {e["src"] for e in edges if e["type"] == "located_in" and e["src"].startswith("farming_patch:")}
    parented = [n for n in fp if n["id"] in located]
    flagged = [n for n in fp if n["id"] not in located]
    node_types = {n["data"]["patch_type"] for n in fp}
    core = list(MEMBER_TYPE.values())

    print("FARMING COVERAGE (report-not-fail):")
    print(f"  category members: {len(cat)}")
    print("  12 members = 9 patch-type + 1 umbrella + 1 place + 1 npc")
    print(f"  parsed rows: {len(rows)}  ->  farming_patch nodes: {len(fp)}")
    print(f"  parented (located_in): {len(parented)}   FLAG (unresolved place): {len(flagged)}")
    for n in sorted(flagged, key=lambda n: n["id"]):
        print(f"     - {n['id']}  (token: {n['data'].get('source_token','')!r})")

    # (a) per-type presence cross-check (the completeness probe): every MEMBER_TYPE value
    # must appear in >=1 node's patch_type.
    missing = [t for t in core if t not in node_types]
    print(f"  core types present: {len(core) - len(missing)}/{len(core)}"
          + (f"  MISSING: {missing}" if missing else ""))

    # (b) the umbrella (Special patches) must have yielded >=1 special-crop node (a
    # patch_type outside the 9-member core map).
    special_crop_types = node_types - set(core)
    print(f"  umbrella (Special patches) special-crop types yielded: {len(special_crop_types)}"
          + ("  MISSING (umbrella yielded no node)" if not special_crop_types else
             f"  {sorted(special_crop_types)}"))

    # (c) the 2 excludes are in farming_overrides.json force_exclude and produced no node.
    force_exclude = {o["value"] for o in ov.get("force_exclude", [])}
    exclude_ok = MEMBER_EXCLUDE <= force_exclude
    print(f"  excludes (place/npc, no node): {sorted(MEMBER_EXCLUDE)}  "
          f"in force_exclude: {exclude_ok}")
    if not exclude_ok:
        print(f"     MISSING FROM force_exclude: {sorted(MEMBER_EXCLUDE - force_exclude)}")

    print("  DEFERRED (disclosed): activity+quest tail (Tithe/CoX/Miscellania + 5 quest patches); "
          "coordinates (chunk-geometry layer); per-site patch_count (Grape 12->1, etc.); "
          "quest-gating-as-a-field (e.g. Locus Oasis hardwood requires a quest, recorded only in "
          "source_token prose); instance_of + patch_type nodes (P8).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
