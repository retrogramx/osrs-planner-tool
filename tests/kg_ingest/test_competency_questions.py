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
        else:
            raise AssertionError(f"unknown method {cq['method']!r}")
        assert len(answer) >= cq["expect_min"], f"{cq['id']}: got {len(answer)} < {cq['expect_min']}"
