from kg_ingest.builders.storeline import _norm, _base, index_by_shop, match_shop

KEYS = ["Varrock General Store", "Lowe's Archery Emporium", "Zaff's Superior Staffs!",
        "Ratpit bar (Varrock)", "Ratpit bar (Keldagrim)", "Aubury's Rune Shop."]

def test_exact_match():
    assert match_shop("Varrock General Store", KEYS) == "Varrock General Store"
    assert match_shop("Lowe's Archery Emporium", KEYS) == "Lowe's Archery Emporium"

def test_trailing_punctuation_match():
    assert match_shop("Zaff's Superior Staffs", KEYS) == "Zaff's Superior Staffs!"
    assert match_shop("Aubury's Rune Shop", KEYS) == "Aubury's Rune Shop."

def test_town_disambiguator_required():
    # bare base name collides across towns -> must pick the (Varrock) one, never Keldagrim
    assert match_shop("Ratpit Bar", KEYS) == "Ratpit bar (Varrock)"

def test_no_match_returns_none():
    assert match_shop("Baraek's Fur Stall", KEYS) is None
    assert match_shop("Varrock Apothecary", KEYS) is None

def test_index_by_shop_groups_rows():
    recs = [{"sold_by": "A", "sold_item": "x"}, {"sold_by": "A", "sold_item": "y"},
            {"sold_by": "B", "sold_item": "z"}]
    idx = index_by_shop(recs)
    assert sorted(r["sold_item"] for r in idx["A"]) == ["x", "y"]
    assert len(idx["B"]) == 1
