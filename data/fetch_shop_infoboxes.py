#!/usr/bin/env python3
"""Fetch each shop page's {{Infobox Shop}} location/members/owner (verbatim) + the
Category:Shops type-subcategory membership, for the all-shops layer. Deterministic +
sorted. Verbatim — no inference. Source: OSRS Wiki (CC BY-NC-SA).
Run: ./venv/bin/python data/fetch_shop_infoboxes.py
"""
import json, os, re, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"
API = "https://oldschool.runescape.wiki/api.php"
WIKI = "https://oldschool.runescape.wiki/w/"


def extract_infobox_block(wikitext):
    """Return the {{Infobox Shop ...}} block (brace-depth counted so nested {{...}}
    are kept), or '' if absent. Robust to nested templates (naive non-greedy regex
    would truncate at the first nested }})."""
    m = re.search(r"\{\{Infobox Shop\b", wikitext or "", re.IGNORECASE)
    if not m:
        return ""
    i, depth = m.start(), 0
    while i < len(wikitext):
        if wikitext[i:i + 2] == "{{":
            depth += 1; i += 2; continue
        if wikitext[i:i + 2] == "}}":
            depth -= 1; i += 2
            if depth == 0:
                return wikitext[m.start():i]
            continue
        i += 1
    return wikitext[m.start():]          # unbalanced -> take the tail (verbatim, no inference)


def split_top_level_params(block):
    """Split an infobox block into {param: value} on '|' at brace/bracket depth 0
    (so nested {{...}} and [[...]] pipes do NOT split). First '=' splits key/value."""
    inner = block
    if inner.startswith("{{"):
        inner = inner[2:]
    if inner.endswith("}}"):
        inner = inner[:-2]
    parts, buf, depth = [], [], 0
    i = 0
    while i < len(inner):
        two = inner[i:i + 2]
        if two in ("{{", "[["):
            depth += 1; buf.append(two); i += 2; continue
        if two in ("}}", "]]"):
            depth = max(0, depth - 1); buf.append(two); i += 2; continue
        c = inner[i]
        if c == "|" and depth == 0:
            parts.append("".join(buf)); buf = []
        else:
            buf.append(c)
        i += 1
    parts.append("".join(buf))
    out = {}
    for seg in parts[1:]:                # parts[0] is the template name
        if "=" in seg:
            k, v = seg.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def shop_locations(params):
    """Ordered, non-empty location values: |location=, else |location1..N= (verbatim)."""
    out = []
    if params.get("location"):
        out.append(params["location"])
    for i in range(1, 21):
        v = params.get(f"location{i}")
        if v:
            out.append(v)
    return out


def shop_members(params):
    v = params.get("members")
    return v if v else None


def shop_owners(params):
    out = []
    if params.get("owner"):
        out.append(params["owner"])
    for i in range(1, 21):
        v = params.get(f"owner{i}")
        if v:
            out.append(v)
    return out


def _api(params):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
        return json.load(r)


def _members(category, cmtype):
    out, cont = [], {}
    while True:
        d = _api({"action": "query", "list": "categorymembers", "cmtitle": category,
                  "cmlimit": "500", "cmtype": cmtype, **cont})
        out += [m["title"] for m in d.get("query", {}).get("categorymembers", [])]
        if "continue" in d:
            cont = d["continue"]
        else:
            break
    return out


def main():
    os.makedirs(RAW, exist_ok=True)
    # 1) Category:Shops subcategories -> {subcat: [pages]} ; subcat title sans 'Category:' = shop_type source
    subcats = _members("Category:Shops", "subcat")
    categories = {}
    for sc in sorted(subcats):
        pages = _members(sc, "page")
        categories[sc.replace("Category:", "")] = sorted(pages)
        time.sleep(0.1)
    all_pages = sorted({p for pages in categories.values() for p in pages})
    # 2) {{Infobox Shop}} per page
    infoboxes = {}
    for i in range(0, len(all_pages), 20):
        batch = all_pages[i:i + 20]
        d = _api({"action": "query", "titles": "|".join(batch), "prop": "revisions",
                  "rvprop": "content", "rvslots": "main"})
        for pg in d.get("query", {}).get("pages", {}).values():
            title = pg["title"]
            revs = pg.get("revisions", [])
            wt = revs[0]["slots"]["main"]["*"] if revs else ""
            params = split_top_level_params(extract_infobox_block(wt))
            infoboxes[title] = {"locations": shop_locations(params), "members": shop_members(params),
                                "owner": shop_owners(params), "icon": params.get("icon"),
                                "source_url": WIKI + title.replace(" ", "_")}
        time.sleep(0.1)
    with open(os.path.join(RAW, "wiki_shop_categories.json"), "w", encoding="utf-8") as f:
        json.dump({"_provenance": {"domain": "wiki_shop_categories", "source": "OSRS Wiki category API",
                                   "license": "CC BY-NC-SA 3.0", "root": "Category:Shops"},
                   "categories": dict(sorted(categories.items()))}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(RAW, "wiki_shop_infoboxes.json"), "w", encoding="utf-8") as f:
        json.dump({"_provenance": {"domain": "wiki_shop_infoboxes", "source": "OSRS Wiki revisions API",
                                   "license": "CC BY-NC-SA 3.0", "param": "Infobox Shop|location/members/owner"},
                   "infoboxes": dict(sorted(infoboxes.items()))}, f, ensure_ascii=False, indent=1)
    print(f"DONE: {len(categories)} shop-type categories, {len(all_pages)} pages, "
          f"{sum(1 for v in infoboxes.values() if v['locations'])} with a location")


if __name__ == "__main__":
    main()
