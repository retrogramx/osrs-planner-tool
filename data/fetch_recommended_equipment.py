"""Fetch the OSRS-wiki `recommended_equipment` Bucket (written by Module:Recommended equipment)
into data/raw/. Same action=bucket API as fetch_recipes.py. Run: python data/fetch_recommended_equipment.py"""
import json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__)); RAW = os.path.join(HERE, "raw")
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"
BASE = "https://oldschool.runescape.wiki/api.php"; PAGE = 5000
FIELDS = ["page_name", "json"]

def run_query(q):
    url = BASE + "?action=bucket&format=json&query=" + urllib.parse.quote(q)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=180) as r:
        return json.load(r)

def fetch_all():
    sel = ",".join(f"'{f}'" for f in FIELDS)
    rows, off = [], 0
    while True:
        d = run_query(f"bucket('recommended_equipment').select({sel}).offset({off}).limit({PAGE}).run()")
        if d.get("error"):
            raise RuntimeError(f"recommended_equipment offset={off}: {d['error']}")
        b = d.get("bucket", [])
        rows.extend(b)
        print(f"  recommended_equipment: offset={off} got {len(b)} (total {len(rows)})")
        if len(b) < PAGE:
            break
        off += PAGE; time.sleep(0.5)
    rows.sort(key=lambda r: (str(r.get("page_name") or ""), str(r.get("json") or "")))
    return rows

def main():
    os.makedirs(RAW, exist_ok=True)
    rows = fetch_all()
    out = {"_provenance": {"domain": "recommended_equipment",
                           "source_url": "https://oldschool.runescape.wiki/w/Module:Recommended_equipment",
                           "license": "CC BY-NC-SA 3.0", "extraction_method": "Bucket API action=bucket",
                           "query": "bucket('recommended_equipment').select('page_name','json').run() [paginated]",
                           "row_count": len(rows)},
           "bucket": rows}
    with open(os.path.join(RAW, "recommended_equipment_bucket.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(rows)} rows -> data/raw/recommended_equipment_bucket.json")

if __name__ == "__main__":
    main()
