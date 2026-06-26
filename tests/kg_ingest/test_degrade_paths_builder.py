from kg_ingest.builders.degrade_paths import build_degrade_paths
from osrs_planner.engine.kg.model import EdgeType

DESTROYED = [{"slug": "ring-of-dueling-degrade", "page": "Ring of dueling", "trigger": "per_use",
              "sequence": [2552, 2554, 2566], "terminal": "destroyed"}]
REVERTS = [{"slug": "scythe-of-vitur-degrade", "page": "Scythe of vitur", "trigger": "per_hit",
            "sequence": [22325], "terminal": "reverts_to", "terminal_item": 22486}]
BROKEN = [{"slug": "dharoks-helm-degrade", "page": "Dharok's helm", "trigger": "per_hit",
           "sequence": [4716, 4883], "terminal": "broken", "terminal_item": 4884}]

def test_destroyed_chain_ends_in_dst_none():
    nodes, edges, groups = build_degrade_paths(DESTROYED)
    assert nodes == [] and groups == {}
    chain = [(e.src, e.dst) for e in edges if e.type is EdgeType.DEGRADES_TO]
    assert ("item:2552", "item:2554") in chain          # step edge
    assert ("item:2554", "item:2566") in chain          # step edge
    term = [e for e in edges if e.src == "item:2566"]
    assert len(term) == 1 and term[0].dst is None and term[0].data == {"trigger": "per_use", "terminal": "destroyed"}
    assert all(e.data["trigger"] == "per_use" for e in edges)

def test_reverts_to_terminal_points_to_uncharged_node():
    _, edges, _ = build_degrade_paths(REVERTS)
    assert len(edges) == 1
    e = edges[0]
    assert e.src == "item:22325" and e.dst == "item:22486" and e.data["terminal"] == "reverts_to"

def test_broken_terminal_points_to_broken_node():
    _, edges, _ = build_degrade_paths(BROKEN)
    term = [e for e in edges if e.src == "item:4883"]
    assert len(term) == 1 and term[0].dst == "item:4884" and term[0].data["terminal"] == "broken"
    assert ("item:4716", "item:4883") in {(e.src, e.dst) for e in edges}
