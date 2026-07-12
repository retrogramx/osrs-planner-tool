#!/usr/bin/env python3
"""Fetch the farming-patch source (CC BY-NC-SA 3.0) into committed raw snapshots.

Two snapshots, both deterministic (sorted keys, _provenance-stamped):
  wiki_farming_patch_category.json = Category:Farming patches members + each member's
      {{Infobox X}} classification (the completeness anchor + classifier).
  wiki_farming_patch_tables.json   = raw wikitext of the /Patches location tables
      (Task 3 parses these; committed so the parse is offline-reproducible).
The category is the SOURCE OF TRUTH (a curated index page is never a census). No inference here.
"""
from __future__ import annotations
import json, re, sys, time, urllib.parse, urllib.request
from pathlib import Path

API = "https://oldschool.runescape.wiki/api.php"
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"
RAW = Path(__file__).resolve().parent / "raw"

# The location-table pages to snapshot (the transcluded /Patches subpages + the inline coral table).
# Herb & Flower have NO own subpage — Allotment/Patches is the sole source for all three (spec D6).
TABLE_PAGES = [
    "Allotment patch/Patches",
    "Bush patch/Patches",
    "Hops patch/Patches",
    "Tree patch/Patches",
    "Fruit tree patch/Patches",
    "Spirit Tree (Farming)/Patches",   # Spirit tree/Patches redirects here
    "Special patches/Patches",
    "Coral nursery (patch)",           # inline coral table (no /Patches subpage)
]

_SCENERY = {"Infobox Scenery", "Infobox Construction"}


def classify_member(infoboxes):
    """Classify a Category:Farming patches member by the {{Infobox X}} on its page."""
    s = set(infoboxes or [])
    if "Infobox NPC" in s:
        return "npc"            # Chet
    if "Infobox Location" in s:
        return "place"          # Coral Nurseries (the underwater place, not a patch)
    if s & _SCENERY:
        return "patch_type"     # Allotment/Herb/.../Coral nursery (patch)
    return "other"


def _get(params):
    params = {**params, "format": "json"}
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))


def _infoboxes_in(wikitext):
    """Sorted distinct {{Infobox X}} template names in a page's wikitext."""
    names = set(re.findall(r"\{\{\s*(Infobox [A-Za-z][A-Za-z ]*?)\s*[\|\}]", wikitext or ""))
    return sorted(names)


def _wikitext_of(titles):
    """title -> wikitext for a batch of titles (redirects resolved)."""
    out = {}
    for i in range(0, len(titles), 20):
        batch = titles[i:i + 20]
        d = _get({"action": "query", "prop": "revisions", "rvslots": "main",
                  "rvprop": "content", "redirects": "1", "titles": "|".join(batch)})
        pages = d.get("query", {}).get("pages", {})
        norm = {n["from"]: n["to"] for n in d.get("query", {}).get("normalized", [])}
        redir = {r["from"]: r["to"] for r in d.get("query", {}).get("redirects", [])}
        resolved = {t: redir.get(norm.get(t, t), norm.get(t, t)) for t in batch}
        by_title = {p["title"]: p for p in pages.values() if "title" in p}
        for t in batch:
            p = by_title.get(resolved[t])
            wt = ""
            if p and p.get("revisions"):
                wt = p["revisions"][0]["slots"]["main"]["*"]
            out[t] = wt
        time.sleep(0.2)
    return out


def fetch_category_members():
    members = []
    cont = {}
    while True:
        d = _get({"action": "query", "list": "categorymembers",
                  "cmtitle": "Category:Farming patches", "cmlimit": "500",
                  "cmtype": "page", **cont})
        members += [m["title"] for m in d["query"]["categorymembers"]]
        if "continue" in d:
            cont = d["continue"]
        else:
            break
    return sorted(members)


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    members = fetch_category_members()
    member_wt = _wikitext_of(members)
    cat = {}
    for name in members:
        ibs = _infoboxes_in(member_wt[name])
        cat[name] = {"infoboxes": ibs, "classification": classify_member(ibs),
                     "source_url": "https://oldschool.runescape.wiki/w/" +
                                   urllib.parse.quote(name.replace(" ", "_"))}
    _write(RAW / "wiki_farming_patch_category.json",
           {"_provenance": {"domain": "oldschool.runescape.wiki",
                            "source": "Category:Farming patches (action=query list=categorymembers)",
                            "license": "CC BY-NC-SA 3.0", "member_count": len(members)},
            "members": cat})

    table_wt = _wikitext_of(TABLE_PAGES)
    tables = {p: {"source_url": "https://oldschool.runescape.wiki/w/" +
                                urllib.parse.quote(p.replace(" ", "_")),
                  "wikitext": table_wt[p]} for p in TABLE_PAGES}
    _write(RAW / "wiki_farming_patch_tables.json",
           {"_provenance": {"domain": "oldschool.runescape.wiki",
                            "source": "farming /Patches subpages + inline coral table (action=query prop=revisions)",
                            "license": "CC BY-NC-SA 3.0", "pages": TABLE_PAGES},
            "tables": tables})
    print(f"wrote {len(members)} category members, {len(TABLE_PAGES)} tables")


def _write(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    sys.exit(main())
