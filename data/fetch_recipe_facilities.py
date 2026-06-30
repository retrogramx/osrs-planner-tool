#!/usr/bin/env python3
"""Fetch the Bucket:recipe projection (page_name, uses_facility, uses_skill) for the facility
taxonomy layer. Source: OSRS Wiki Bucket API (action=bucket). CC BY-NC-SA 3.0. Verbatim — no
inference. Server caps run() at 5000 rows, so paginate. Rows with empty uses_facility are
dropped (no-facility recipes). Run: ./venv/bin/python data/fetch_recipe_facilities.py
"""
import json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"
BASE = "https://oldschool.runescape.wiki/api.php"
PAGE = 5000
FIELDS = ["page_name", "uses_facility", "uses_skill"]


def run_query(query):
    url = BASE + "?action=bucket&format=json&query=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def project_rows(raw_rows):
    """Keep only the projected fields; drop rows whose uses_facility has no non-empty value.
    Sorted by (page_name, json.dumps(uses_facility)) for byte-determinism."""
    out = []
    for r in raw_rows:
        facs = r.get("uses_facility")
        facs = facs if isinstance(facs, list) else ([] if facs in (None, "") else [facs])
        if not any((f or "").strip() for f in facs):
            continue
        out.append({k: r.get(k) for k in FIELDS})
    out.sort(key=lambda r: (str(r.get("page_name") or ""), json.dumps(r.get("uses_facility"), sort_keys=True)))
    return out


def fetch_all():
    sel = ",".join(f"'{f}'" for f in FIELDS)
    rows, offset = [], 0
    while True:
        q = f"bucket('recipe').select({sel}).offset({offset}).limit({PAGE}).run()"
        d = run_query(q)
        if d.get("error"):
            raise RuntimeError(f"recipe offset={offset}: {d['error']}")
        batch = d.get("bucket", [])
        rows.extend(batch)
        print(f"  recipe: offset={offset} got {len(batch)} (total {len(rows)})")
        if len(batch) < PAGE:
            break
        offset += PAGE
        time.sleep(0.5)
    return project_rows(rows)


def main():
    os.makedirs(RAW, exist_ok=True)
    rows = fetch_all()
    out = {"_provenance": {"domain": "recipe_facility",
                           "source_url": "https://oldschool.runescape.wiki/w/Bucket:recipe",
                           "license": "CC BY-NC-SA 3.0", "extraction_method": "Bucket API action=bucket",
                           "query": f"bucket('recipe').select({','.join(FIELDS)}).run() [paginated by 5000; empty uses_facility dropped]",
                           "row_count": len(rows)},
           "bucket": rows}
    with open(os.path.join(RAW, "recipe_facility_bucket.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"DONE: {len(rows)} recipe rows with a facility")


if __name__ == "__main__":
    main()
