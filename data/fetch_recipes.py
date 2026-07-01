#!/usr/bin/env python3
"""Fetch Bucket:recipe (all rows, incl. production_json) for the recipe layer.
Source: OSRS Wiki Bucket API (action=bucket). CC BY-NC-SA 3.0. Paginate by 5000.
Run: ./venv/bin/python data/fetch_recipes.py
"""
import json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__)); RAW = os.path.join(HERE, "raw")
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"
BASE = "https://oldschool.runescape.wiki/api.php"; PAGE = 5000
FIELDS = ["page_name", "uses_skill", "uses_tool", "uses_facility", "production_json"]


def run_query(q):
    url = BASE + "?action=bucket&format=json&query=" + urllib.parse.quote(q)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=180) as r:
        return json.load(r)


def project_rows(raw_rows):
    out = [{k: r.get(k) for k in FIELDS} for r in raw_rows]
    out.sort(key=lambda r: (str(r.get("page_name") or ""), json.dumps(r.get("production_json"), sort_keys=True)))
    return out


def fetch_all():
    sel = ",".join(f"'{f}'" for f in FIELDS)
    rows, off = [], 0
    while True:
        d = run_query(f"bucket('recipe').select({sel}).offset({off}).limit({PAGE}).run()")
        if d.get("error"):
            raise RuntimeError(f"recipe offset={off}: {d['error']}")
        b = d.get("bucket", [])
        rows.extend(b)
        print(f"  recipe: offset={off} got {len(b)} (total {len(rows)})")
        if len(b) < PAGE:
            break
        off += PAGE
        time.sleep(0.5)
    return project_rows(rows)


def main():
    os.makedirs(RAW, exist_ok=True)
    rows = fetch_all()
    out = {"_provenance": {"domain": "recipe", "source_url": "https://oldschool.runescape.wiki/w/Bucket:recipe",
                           "license": "CC BY-NC-SA 3.0", "extraction_method": "Bucket API action=bucket",
                           "query": f"bucket('recipe').select({','.join(FIELDS)}).run() [paginated by 5000]",
                           "row_count": len(rows)},
           "bucket": rows}
    with open(os.path.join(RAW, "recipe_bucket.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"DONE: {len(rows)} recipe rows")


if __name__ == "__main__":
    main()
