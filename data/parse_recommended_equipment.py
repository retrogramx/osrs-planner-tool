"""Build data/recommended_equipment.json from the committed raw Bucket snapshot.
Clean item names come from the [[File:...|link=NAME]] targets in each rendered cell.
Run: python data/parse_recommended_equipment.py"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__)); RAW = os.path.join(HERE, "raw")
LINK_RE = re.compile(r"\[\[File:[^\]]*?\|link=([^\]|]+)\]\]")
SRC_BASE = "https://oldschool.runescape.wiki/w/"

def extract_slot_items(json_str):
    """[(slot, item_name), ...] from a Bucket `json` string; dedup within a (slot) preserving order."""
    obj = json.loads(json_str)
    eq = obj.get("Recommended Equipment") or {}
    out, seen = [], set()
    for slot, cells in eq.items():
        for cell in (cells if isinstance(cells, list) else [cells]):
            for name in LINK_RE.findall(cell):
                key = (slot, name)
                if key not in seen:
                    seen.add(key); out.append((slot, name))
    return out

def build_records(bucket_rows, dict_recs):
    by_name = {}
    for r in dict_recs:
        by_name.setdefault(r["name"], r["item_id"])
    records, unresolved = [], {}
    for row in bucket_rows:
        page = row.get("page_name") or ""
        try:
            style = (json.loads(row["json"]).get("style") or "")
        except Exception:
            style = ""
        for slot, name in extract_slot_items(row["json"]):
            iid = by_name.get(name)
            if iid is None:
                unresolved[name] = unresolved.get(name, 0) + 1
                continue
            records.append({"item_name": name, "item_id": iid, "page_name": page, "style": style,
                            "slot": slot, "source_url": SRC_BASE + page.replace(" ", "_"),
                            "source_token": page})
    records.sort(key=lambda r: (r["item_id"], r["page_name"], r["slot"]))
    return records, unresolved

def main():
    raw = json.load(open(os.path.join(RAW, "recommended_equipment_bucket.json"), encoding="utf-8"))["bucket"]
    dict_recs = json.load(open(os.path.join(HERE, "item_dictionary.json"), encoding="utf-8"))["records"]
    records, unresolved = build_records(raw, dict_recs)
    distinct = sorted({r["item_id"] for r in records})
    envelope = {"_provenance": {"domain": "recommended_equipment",
                    "source_url": "https://oldschool.runescape.wiki/w/Module:Recommended_equipment",
                    "license": "CC BY-NC-SA 3.0", "record_count": len(records),
                    "distinct_items": len(distinct), "unresolved_names": len(unresolved),
                    "note": "one record per (item, page, slot); item names from [[File:|link=]] targets"},
                "records": records, "_unresolved": sorted(unresolved)}
    with open(os.path.join(HERE, "recommended_equipment.json"), "w", encoding="utf-8") as f:
        json.dump(envelope, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(records)} records / {len(distinct)} distinct items; {len(unresolved)} unresolved names")

if __name__ == "__main__":
    main()
