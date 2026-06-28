import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_snapshot_shape():
    d = json.loads((ROOT / "data" / "raw" / "wiki_location_categories.json").read_text())
    cats = d["categories"]
    assert len(cats["Dungeons"]) >= 150          # exhaustive dungeon list
    assert "Catacombs of Kourend" in cats["Dungeons"]
    assert len(cats["Settlements"]) >= 80
    assert d["members"] and d["free_to_play"]      # F2P/Members membership pulled
    assert "page_categories" in d                  # per-page categories for parentage
    # deterministic ordering
    for lst in cats.values():
        assert lst == sorted(lst)
