import pathlib
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType

KG = str(pathlib.Path(__file__).resolve().parents[2] / "kg")

def test_committed_graph_has_item_pages_families_and_bridges():
    s = JsonKGStore.from_dir(KG)
    assert s.node("item:amulet-of-glory") is not None         # L1 page node
    assert s.node("item:amulet-of-glory").data.get("is_page") is True
    assert s.node("item:scythe-of-vitur-family") is not None  # L2 family node
    assert s.node("item:scythe-of-vitur-family").data.get("is_family") is True
    se = [e for e in s.edges if e.type is EdgeType.SAME_ENTITY]
    pairs = {(e.src, e.dst) for e in se}
    assert ("item:1712", "item:amulet-of-glory") in pairs            # variant -> page (L1)
    assert ("item:scythe-of-vitur", "item:scythe-of-vitur-family") in pairs  # page -> family (L2)
    # Dragon scimitar still resolves with its goal-owned name (no handoff conflict)
    assert s.node("item:4587").name == "Dragon scimitar"
