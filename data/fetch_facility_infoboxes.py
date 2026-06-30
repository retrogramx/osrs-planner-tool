#!/usr/bin/env python3
"""Fetch each distinct Bucket:recipe.uses_facility value's wiki infobox(es) — the roster FILTER
for the facility taxonomy layer (the wiki's own {{Infobox X}} is the classifier). Redirect-
resolved (Cooking range/Bank are redirects). Verbatim — no inference. CC BY-NC-SA 3.0.
Run: ./venv/bin/python data/fetch_facility_infoboxes.py
"""
import json, os, re, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"
API = "https://oldschool.runescape.wiki/api.php"
WIKI = "https://oldschool.runescape.wiki/w/"

_IB_RE = re.compile(r"\{\{\s*(Infobox [A-Za-z][A-Za-z ]*?)\s*[\|\}]")


def infoboxes_in(wikitext):
    """Sorted distinct {{Infobox X}} template names in the wikitext."""
    return sorted({m.strip() for m in _IB_RE.findall(wikitext or "")})


def _api(params):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
        return json.load(r)


def distinct_facility_values():
    rows = json.load(open(os.path.join(RAW, "recipe_facility_bucket.json"), encoding="utf-8"))["bucket"]
    vals = set()
    for r in rows:
        facs = r.get("uses_facility") or []
        for f in (facs if isinstance(facs, list) else [facs]):
            f = (f or "").strip()
            if f:
                vals.add(f)
    return sorted(vals)


def main():
    os.makedirs(RAW, exist_ok=True)
    titles = distinct_facility_values()
    out = {}
    for i in range(0, len(titles), 20):
        batch = titles[i:i + 20]
        d = _api({"action": "query", "titles": "|".join(batch), "prop": "revisions",
                  "rvprop": "content", "rvslots": "main", "redirects": 1})
        q = d.get("query", {})
        # map each queried title -> final (normalized + redirect-resolved) title
        final = {t: t for t in batch}
        for n in q.get("normalized", []):
            final[n["from"]] = n["to"]
        red = {r["from"]: r["to"] for r in q.get("redirects", [])}
        for src, dst in list(final.items()):
            final[src] = red.get(dst, dst)
        pages = {pg["title"]: pg for pg in q.get("pages", {}).values()}
        for value in batch:
            tgt = final[value]
            pg = pages.get(tgt, {})
            revs = pg.get("revisions", [])
            wt = revs[0]["slots"]["main"]["*"] if revs else ""
            out[value] = {"infoboxes": infoboxes_in(wt),
                          "redirect_target": (tgt if tgt != value else None),
                          "source_url": WIKI + tgt.replace(" ", "_")}
        time.sleep(0.1)
    with open(os.path.join(RAW, "wiki_facility_infoboxes.json"), "w", encoding="utf-8") as f:
        json.dump({"_provenance": {"domain": "wiki_facility_infoboxes",
                                   "source": "OSRS Wiki revisions API (redirects resolved)",
                                   "license": "CC BY-NC-SA 3.0", "param": "{{Infobox X}} presence"},
                   "infoboxes": dict(sorted(out.items()))}, f, ensure_ascii=False, indent=1)
    from collections import Counter
    c = Counter()
    # local import to avoid a hard dependency at module import time
    import sys; sys.path.insert(0, os.path.dirname(HERE))
    from kg_ingest.builders.facilities import classify_infobox
    for v in out.values():
        c[classify_infobox(v["infoboxes"])] += 1
    print(f"DONE: {len(titles)} values -> {dict(c)}")


if __name__ == "__main__":
    main()
