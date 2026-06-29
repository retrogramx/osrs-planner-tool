import json, os
ROOT = os.path.join(os.path.dirname(__file__), "..", "..")

def test_npc_infobox_snapshot_shape():
    d = json.load(open(os.path.join(ROOT, "data", "raw", "wiki_npc_infoboxes.json"), encoding="utf-8"))
    assert "_provenance" in d and "infoboxes" in d
    assert d["infoboxes"] == dict(sorted(d["infoboxes"].items()))
    sample = next(iter(d["infoboxes"].values()))
    assert set(sample) >= {"locations", "is_npc", "source_url"}
    assert any(v["is_npc"] for v in d["infoboxes"].values())   # some operators are real NPCs
