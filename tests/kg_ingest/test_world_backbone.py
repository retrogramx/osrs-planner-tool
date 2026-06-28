import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_backbone_is_a_connected_single_root_tree():
    places = json.loads((ROOT / "data" / "map" / "world.json").read_text())["places"]
    ids = {p["id"] for p in places}
    roots = [p for p in places if not p.get("located_in")]
    assert [r["id"] for r in roots] == ["place:gielinor"]          # exactly one root
    assert json.dumps(places)                                       # valid json
    # every located_in resolves within the backbone
    for p in places:
        if p["id"] != "place:gielinor":
            assert p["located_in"] in ids, f"{p['id']} -> {p['located_in']} dangling"
    # the integration anchors + the re-parent
    by = {p["id"]: p for p in places}
    assert by["place:misthalin"]["located_in"] == "place:mainland"
    assert by["place:varrock"]["located_in"] == "place:misthalin"
    # every place is wiki-sourced + has a place_type in the enum
    enum = set(json.loads((ROOT / "kg" / "schema.json").read_text())["node_kinds"]["place"]["place_type_enum"])
    for p in places:
        assert p["source_url"].startswith("https://oldschool.runescape.wiki/")
        assert p["place_type"] in enum
