import json, pathlib
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType

ROOT = pathlib.Path(__file__).resolve().parents[2]
KG = str(ROOT / "kg")

def _members(store, target):
    return {e.src for e in store.edges if e.type is EdgeType.SAME_ENTITY and e.dst == target}

def _family(store, target):
    out = set()
    for anchor in _members(store, target):          # family -> member pages/variants
        out.add(anchor)
        out |= _members(store, anchor)              # member page -> its variants
    return out

def _recipe_materials(store, target):
    return {e.dst for e in store.edges
            if e.type is EdgeType.CONSUMES and e.src == target and (e.data or {}).get("role") == "material"}

def _is_destroyed(store, target):
    # variants of the page (same_entity in-edges) that have an outgoing degrades_to with dst=None
    variants = {e.src for e in store.edges if e.type is EdgeType.SAME_ENTITY and e.dst == target}
    return {e.src for e in store.edges
            if e.type is EdgeType.DEGRADES_TO and e.dst is None and e.src in variants}


def _is_repairable(store, target):
    # the repaired-item set reachable from the broken target via a repairs edge
    return {e.dst for e in store.edges if e.type is EdgeType.REPAIRS and e.src == target}


def _equipment_bonus(store, target, stat):
    for e in store.edges:
        if e.type is EdgeType.HAS_BONUSES and e.src == target:
            return store.node(e.dst).data["stats"].get(stat)
    return None


def _sold_by(store, target):
    # the set of shops with a sells edge to the target item
    return {e.src for e in store.edges if e.type is EdgeType.SELLS and e.dst == target}


def test_all_competency_questions_pass():
    store = JsonKGStore.from_dir(KG)
    with open(ROOT / "kg" / "competency_questions.json") as f:
        cqs = json.load(f)["records"]
    assert cqs
    for cq in cqs:
        if cq["method"] == "same_entity_members":
            answer = _members(store, cq["target"])
        elif cq["method"] == "same_entity_family":
            answer = _family(store, cq["target"])
        elif cq["method"] == "recipe_materials":
            answer = _recipe_materials(store, cq["target"])
        elif cq["method"] == "is_destroyed":
            answer = _is_destroyed(store, cq["target"])
        elif cq["method"] == "is_repairable":
            answer = _is_repairable(store, cq["target"])
        elif cq["method"] == "equipment_bonus":
            answer = _equipment_bonus(store, cq["target"], cq["stat"])
            assert answer == cq["expect"], f"{cq['id']}: {cq['stat']}={answer!r} != {cq['expect']!r}"
            continue
        elif cq["method"] == "sold_by":
            answer = _sold_by(store, cq["target"])
        else:
            raise AssertionError(f"unknown method {cq['method']!r}")
        assert len(answer) >= cq["expect_min"], f"{cq['id']}: got {len(answer)} < {cq['expect_min']}"
