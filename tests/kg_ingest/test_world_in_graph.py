import pathlib
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType
ROOT = pathlib.Path(__file__).resolve().parents[2]

def _store():
    return JsonKGStore.from_dir(str(ROOT / "kg"))

def test_continent_level_inserted_and_misthalin_reparented():
    s = _store()
    li = {(e.src, e.dst) for e in s.edges if e.type is EdgeType.LOCATED_IN}
    assert ("place:misthalin", "place:mainland") in li       # re-parented under the continent
    assert ("place:mainland", "place:gielinor") in li
    assert ("place:varrock", "place:misthalin") in li        # subtree intact

def test_content_sites_present_and_parented():
    s = _store()
    ids = {n for n in s.nodes}
    assert "place:catacombs-of-kourend" in ids               # the gap you found, now in
    assert any(e.type is EdgeType.LOCATED_IN and e.src == "place:catacombs-of-kourend" for e in s.edges)

def test_all_edge_ids_unique():
    s = _store()
    eids = [e.id for e in s.edges]
    assert len(eids) == len(set(eids))                       # seeded place-src rekey holds
