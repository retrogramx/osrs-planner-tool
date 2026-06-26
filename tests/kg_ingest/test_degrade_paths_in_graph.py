import pathlib
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType

KG = str(pathlib.Path(__file__).resolve().parents[2] / "kg")

def test_degrade_terminals_and_dharoks_autoimport():
    s = JsonKGStore.from_dir(KG)
    # destroyed: Ring of dueling (1) -> None
    t = [e for e in s.edges if e.type is EdgeType.DEGRADES_TO and e.src == "item:2566"]
    assert len(t) == 1 and t[0].dst is None and t[0].data["terminal"] == "destroyed"
    # reverts_to: Scythe charged -> uncharged
    sc = [e for e in s.edges if e.type is EdgeType.DEGRADES_TO and e.src == "item:22325"]
    assert len(sc) == 1 and sc[0].dst == "item:22486" and sc[0].data["terminal"] == "reverts_to"
    # broken: Dharok's variants auto-imported + terminal to the broken (0) node
    assert s.node("item:4880") is not None and s.node("item:4884") is not None
    dh = [e for e in s.edges if e.type is EdgeType.DEGRADES_TO and e.src == "item:4883"]
    assert len(dh) == 1 and dh[0].dst == "item:4884" and dh[0].data["terminal"] == "broken"

def test_shared_rekey_gives_distinct_ids_for_same_entity_and_degrades_to():
    # Ring of dueling (8) item:2552 is the SRC of both a same_entity edge (slice 1)
    # and a degrades_to edge (this slice). The shared rekey must give them distinct ids.
    s = JsonKGStore.from_dir(KG)
    se = [e for e in s.edges if e.type is EdgeType.SAME_ENTITY and e.src == "item:2552"]
    dg = [e for e in s.edges if e.type is EdgeType.DEGRADES_TO and e.src == "item:2552"]
    assert len(se) == 1 and len(dg) == 1
    assert se[0].id != dg[0].id, "shared rekey collision: same_entity and degrades_to got the same edge id"
