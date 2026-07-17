"""Build data/recommended_equipment.json from the committed raw Bucket snapshot.
Clean item names come from the [[File:...|link=NAME]] targets in each rendered cell.
Run: python data/parse_recommended_equipment.py"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__)); RAW = os.path.join(HERE, "raw")
LINK_RE = re.compile(r"\[\[File:[^\]]*?\|link=([^\]|]+)\]\]")
SRC_BASE = "https://oldschool.runescape.wiki/w/"

def _slot_items_from_obj(obj):
    """[(slot, item_name), ...] from an already-parsed Bucket `json` object; dedup within a
    (slot) preserving order."""
    eq = obj.get("Recommended Equipment") or {}
    out, seen = [], set()
    for slot, cells in eq.items():
        for cell in (cells if isinstance(cells, list) else [cells]):
            for name in LINK_RE.findall(cell):
                key = (slot, name)
                if key not in seen:
                    seen.add(key); out.append((slot, name))
    return out

def extract_slot_items(json_str):
    """[(slot, item_name), ...] from a Bucket `json` string; dedup within a (slot) preserving order."""
    return _slot_items_from_obj(json.loads(json_str))

def normalize_link_name(name):
    """Normalize a raw [[File:...|link=NAME]] target for dictionary lookup: strip whitespace,
    drop any #anchor, underscores->spaces, and first-letter-case-fold (wiki page names are
    first-letter-case-insensitive). The ORIGINAL name is only used if resolution fails."""
    name = name.strip()
    name = name.split("#", 1)[0]
    name = name.replace("_", " ")
    name = name.strip()
    if name:
        name = name[0].upper() + name[1:]
    return name

def _best_record(name, candidates):
    """Apply the disambiguation precedence to a group of dict records sharing `name`:
    (a) prefer page_name == name (exact page match), (b) else prefer is_canonical, (c) else
    the lowest item_id."""
    exact = [r for r in candidates if r["page_name"] == name]
    pool = exact or candidates
    canonical = [r for r in pool if r.get("is_canonical")]
    pool = canonical or pool
    return min(pool, key=lambda r: r["item_id"])

def resolve_item_id(linkname, dict_recs):
    """Resolve a (normalized) link-target name to the best-matching item_id among dict_recs
    whose name == linkname, using the (a) exact-page / (b) canonical / (c) lowest-id
    precedence. Returns None if no dict record has this name at all."""
    candidates = [r for r in dict_recs if r["name"] == linkname]
    if not candidates:
        return None
    return _best_record(linkname, candidates)["item_id"]

def build_name_index(dict_recs):
    """{name: best_item_id} built once over the whole dictionary, same precedence as
    resolve_item_id — avoids an O(names * dict_recs) rescan per lookup in build_records."""
    groups = {}
    for r in dict_recs:
        groups.setdefault(r["name"], []).append(r)
    return {name: _best_record(name, recs)["item_id"] for name, recs in groups.items()}

def build_records(bucket_rows, dict_recs):
    index = build_name_index(dict_recs)
    records, unresolved = [], {}
    seen, malformed = set(), 0
    for row in bucket_rows:
        page = row.get("page_name") or ""
        try:
            obj = json.loads(row["json"])
        except Exception:
            malformed += 1
            continue
        style = obj.get("style") or ""
        for slot, raw_name in _slot_items_from_obj(obj):
            name = normalize_link_name(raw_name)
            iid = index.get(name)
            if iid is None:
                unresolved[name] = unresolved.get(name, 0) + 1
                continue
            key = (iid, page, slot, style)
            if key in seen:
                continue
            seen.add(key)
            records.append({"item_name": name, "item_id": iid, "page_name": page, "style": style,
                            "slot": slot, "source_url": SRC_BASE + page.replace(" ", "_"),
                            "source_token": page})
    records.sort(key=lambda r: (r["item_id"], r["page_name"], r["slot"]))
    return records, unresolved, malformed

def main():
    raw = json.load(open(os.path.join(RAW, "recommended_equipment_bucket.json"), encoding="utf-8"))["bucket"]
    dict_recs = json.load(open(os.path.join(HERE, "item_dictionary.json"), encoding="utf-8"))["records"]
    records, unresolved, malformed = build_records(raw, dict_recs)
    distinct = sorted({r["item_id"] for r in records})
    envelope = {"_provenance": {"domain": "recommended_equipment",
                    "source_url": "https://oldschool.runescape.wiki/w/Module:Recommended_equipment",
                    "license": "CC BY-NC-SA 3.0", "record_count": len(records),
                    "distinct_items": len(distinct), "unresolved_names": len(unresolved),
                    "malformed_rows": malformed,
                    "note": "one record per (item, page, slot, style); item names from [[File:|link=]] targets"},
                "records": records, "_unresolved": sorted(unresolved)}
    with open(os.path.join(HERE, "recommended_equipment.json"), "w", encoding="utf-8") as f:
        json.dump(envelope, f, ensure_ascii=False, indent=2)
    print(f"wrote {len(records)} records / {len(distinct)} distinct items; "
          f"{len(unresolved)} unresolved names; {malformed} malformed rows")

if __name__ == "__main__":
    main()
