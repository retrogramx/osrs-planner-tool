import json, pathlib
from osrs_planner.engine.kg.model import NodeKind

ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_nodekind_facility_exists():
    assert NodeKind("facility") is NodeKind.FACILITY
    assert NodeKind.FACILITY.value == "facility"

def test_schema_facility_live_with_data_keys():
    schema = json.loads((ROOT / "kg" / "schema.json").read_text())
    fac = schema["node_kinds"]["facility"]
    assert fac["status"] == "live"
    for k in ("skills", "recipe_count", "source_url", "source_token"):
        assert k in fac["data_keys"], f"{k} missing from facility data_keys"


from kg_ingest.builders.facilities import classify_infobox

def test_classify_infobox_routing():
    assert classify_infobox(["Infobox Scenery"]) == "facility"
    assert classify_infobox(["Infobox Construction"]) == "facility"
    assert classify_infobox(["Infobox NPC"]) == "npc"
    assert classify_infobox(["Infobox Shop"]) == "shop"
    assert classify_infobox(["Infobox Activity"]) == "ambiguous"
    assert classify_infobox(["Infobox Location"]) == "ambiguous"
    assert classify_infobox([]) == "ambiguous"
    # NPC/Shop take precedence over a co-present facility infobox (defer the character/store)
    assert classify_infobox(["Infobox Scenery", "Infobox NPC"]) == "npc"
    assert classify_infobox(["Infobox Shop", "Infobox Scenery"]) == "shop"
