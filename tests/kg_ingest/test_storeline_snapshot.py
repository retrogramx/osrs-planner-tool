import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_storeline_snapshot_shape():
    raw = json.load(open(ROOT / "data" / "raw" / "storeline_bucket.json", encoding="utf-8"))
    rows = raw["bucket"]
    assert len(rows) >= 6000, f"expected full bucket, got {len(rows)}"
    soldby = {r["sold_by"] for r in rows}
    # exact-name shops, a trailing-punctuation shop, and a town-disambiguated shop must all be present
    assert "Varrock General Store" in soldby
    assert "Lowe's Archery Emporium" in soldby
    assert "Zaff's Superior Staffs!" in soldby
    assert "Ratpit bar (Varrock)" in soldby
    # rows are deterministically sorted
    keys = [(r.get("sold_by", ""), r.get("sold_item", "")) for r in rows]
    assert keys == sorted(keys)
