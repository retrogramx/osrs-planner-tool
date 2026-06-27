#!/usr/bin/env python3
"""Fetch the OSRS Wiki Bucket:Storeline (every shop's inventory) in full.

Source: OSRS Wiki Bucket API (action=bucket). Content licensed CC BY-NC-SA 3.0.
Verbatim — no inference. The server caps run() at 5000 rows, so paginate by offset.
Rows are sorted by (sold_by, sold_item) so the committed snapshot is byte-deterministic.
"""
import json, os, time, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"
BASE = "https://oldschool.runescape.wiki/api.php"
PAGE = 5000
FIELDS = ["sold_by", "sold_item", "store_currency", "store_buy_price",
          "store_sell_price", "store_stock", "store_delta", "restock_time"]


def run_query(query):
    url = BASE + "?action=bucket&format=json&query=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def fetch_all():
    sel = ",".join(f"'{f}'" for f in FIELDS)
    rows, offset = [], 0
    while True:
        q = f"bucket('storeline').select({sel}).offset({offset}).limit({PAGE}).run()"
        d = run_query(q)
        if d.get("error"):
            raise RuntimeError(f"storeline offset={offset}: {d['error']}")
        batch = d.get("bucket", [])
        rows.extend(batch)
        print(f"  storeline: offset={offset} got {len(batch)} (total {len(rows)})")
        if len(batch) < PAGE:
            break
        offset += PAGE
        time.sleep(0.5)
    rows.sort(key=lambda r: (r.get("sold_by", ""), r.get("sold_item", "")))
    return rows


def main():
    os.makedirs(RAW, exist_ok=True)
    rows = fetch_all()
    out = {"_provenance": {"domain": "storeline",
                           "source_url": "https://oldschool.runescape.wiki/w/Bucket:Storeline",
                           "license": "CC BY-NC-SA 3.0", "extraction_method": "Bucket API action=bucket",
                           "query": f"bucket('storeline').select({','.join(FIELDS)}).run() [paginated by 5000]",
                           "row_count": len(rows)},
           "bucket": rows}
    with open(os.path.join(RAW, "storeline_bucket.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"DONE: {len(rows)} storeline rows")


if __name__ == "__main__":
    main()
