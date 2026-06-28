import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_place_type_enum_has_sea_and_poi():
    place = json.loads((ROOT / "kg" / "schema.json").read_text())["node_kinds"]["place"]
    assert "sea" in place["place_type_enum"]
    assert "point_of_interest" in place["place_type_enum"]
    assert "content_kind" in place["data_keys"]
    assert "members" in place["data_keys"]
