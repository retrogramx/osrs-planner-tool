#!/usr/bin/env python3
"""Fetch each location page's infobox `location` parameter (verbatim wikitext) from the
OSRS Wiki, for parenting the world skeleton's residual. Deterministic + sorted. Verbatim —
no inference. Source: OSRS Wiki (CC BY-NC-SA). Run: ./venv/bin/python data/fetch_world_infoboxes.py
"""
import json, os, re, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"
API = "https://oldschool.runescape.wiki/api.php"
WIKI = "https://oldschool.runescape.wiki/w/"

# Isolate the {{Infobox Location ...}} block first, then extract |location= from it.
# This avoids capturing {{Relativelocation|location = <own page title>}} which appears later.
INFOBOX_BLOCK_RE = re.compile(r"\{\{Infobox Location(.*?)\}\}", re.IGNORECASE | re.DOTALL)
LOC_PARAM_RE = re.compile(r"\|\s*location\s*=\s*(.+?)(?=\n\s*\||\n\s*\}\})", re.IGNORECASE | re.DOTALL)


def _api(params):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
        return json.load(r)


def _location_param(wikitext):
    """Extract |location = ... from inside the {{Infobox Location}} block (not Relativelocation)."""
    block = INFOBOX_BLOCK_RE.search(wikitext or "")
    if not block:
        return ""
    m = LOC_PARAM_RE.search(block.group(1))
    return m.group(1).strip() if m else ""


def main():
    snap = json.load(open(os.path.join(RAW, "wiki_location_categories.json"), encoding="utf-8"))
    titles = sorted({t for lst in snap["categories"].values() for t in lst})
    out = {}
    for i in range(0, len(titles), 20):
        batch = titles[i:i + 20]
        d = _api({"action": "query", "titles": "|".join(batch), "prop": "revisions",
                  "rvprop": "content", "rvslots": "main"})
        for pg in d.get("query", {}).get("pages", {}).values():
            title = pg["title"]
            revs = pg.get("revisions", [])
            wt = revs[0]["slots"]["main"]["*"] if revs else ""
            out[title] = {"location": _location_param(wt), "source_url": WIKI + title.replace(" ", "_")}
        time.sleep(0.1)
    payload = {"_provenance": {"domain": "wiki_location_infoboxes", "source": "OSRS Wiki revisions API",
                               "license": "CC BY-NC-SA 3.0", "param": "Infobox Location|location="},
               "infoboxes": dict(sorted(out.items()))}
    with open(os.path.join(RAW, "wiki_location_infoboxes.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
    print("DONE:", len(out), "pages;", sum(1 for v in out.values() if v["location"]), "with a location param")


if __name__ == "__main__":
    main()
