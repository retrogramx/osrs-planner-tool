import json, os
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")

def test_shop_infobox_snapshot_shape():
    d = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_shop_infoboxes.json"), encoding="utf-8"))
    assert "_provenance" in d and "infoboxes" in d
    assert d["infoboxes"] == dict(sorted(d["infoboxes"].items()))   # committed sorted (byte-deterministic)
    sample = next(iter(d["infoboxes"].values()))
    assert set(sample) >= {"locations", "members", "owner", "source_url"}
    assert isinstance(sample["locations"], list)

def test_shop_categories_snapshot_shape():
    d = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_shop_categories.json"), encoding="utf-8"))
    assert "categories" in d and d["categories"]
    assert all(isinstance(v, list) for v in d["categories"].values())
