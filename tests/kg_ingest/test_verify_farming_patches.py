"""Tests for data/verify_farming_patches.py — farming-patch structural source-grounding gate.

Exercises find_violations() directly against synthetic rows/nodes/edges so the reject paths
(Frankenstein pairing, fabricated type, dangling located_in) are covered without mutating
kg/nodes.json.
"""
import importlib.util
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_PATH = os.path.join(_ROOT, "data", "verify_farming_patches.py")
_spec = importlib.util.spec_from_file_location("verify_farming_patches", _PATH)
vfp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vfp)


# A herb row and a coral row — two distinct (patch_type, location_raw) rows to pair against.
_ROWS = [
    {"patch_type": "herb", "location_raw": "North of [[Falador]]", "place_link": "Falador",
     "gardeners": [], "source_page": "Herb patch/Patches", "source_url": "https://x/herb", "row_index": 0},
    {"patch_type": "coral", "location_raw": "[[Coral Nurseries]] underwater",
     "place_link": "Fossil Island", "gardeners": [], "source_page": "Coral nursery (patch)",
     "source_url": "https://x/coral", "row_index": 1},
]

_PLACE_IDS = {"place:falador", "place:fossil-island"}


def _node(nid, patch_type, source_token, **data_over):
    data = {"patch_type": patch_type, "source_token": source_token, "source_url": "https://x/y"}
    data.update(data_over)
    return {"id": nid, "data": data}


def _edge(src, dst):
    return {"type": "located_in", "src": src, "dst": dst}


def test_clean_node_matching_a_real_row_pair_has_no_violations():
    node = _node("farming_patch:herb-falador", "herb", "North of [[Falador]]")
    violations = vfp.find_violations([node], [_edge(node["id"], "place:falador")], _ROWS, _PLACE_IDS)
    assert violations == []


def test_frankenstein_node_real_type_wrong_token_is_flagged():
    # patch_type "coral" is real, but source_token is copied from the HERB row's location_raw.
    node = _node("farming_patch:coral-fossil-island", "coral", "North of [[Falador]]")
    violations = vfp.find_violations([node], [], _ROWS, _PLACE_IDS)
    assert any("grounding" in v and node["id"] in v for v in violations)


def test_fabricated_patch_type_is_flagged():
    node = _node("farming_patch:fakecrop-falador", "fakecrop", "North of [[Falador]]")
    violations = vfp.find_violations([node], [], _ROWS, _PLACE_IDS)
    assert any("grounding" in v and node["id"] in v for v in violations)


def test_located_in_edge_to_nonexistent_place_is_flagged():
    node = _node("farming_patch:herb-falador", "herb", "North of [[Falador]]")
    violations = vfp.find_violations(
        [node], [_edge(node["id"], "place:does-not-exist")], _ROWS, _PLACE_IDS)
    assert any("[place]" in v and "place:does-not-exist" in v for v in violations)


def test_committed_graph_verifies_clean():
    assert vfp.main() == 0
