"""rekey() must support >1 edge per owning node without id collisions (quest-foundation Task 3)."""
from kg_ingest.assemble import rekey, stable_edge_id, stable_group_id
from osrs_planner.engine.kg.model import (
    Edge, EdgeType, Node, NodeKind, ConditionGroup, ConditionAtom, AtomType, Op,
)


def _atom_group(gid, atom):
    return ConditionGroup(id=gid, op=Op.AND, parent=None, children=[atom])


def test_single_edge_owner_is_byte_stable():
    # The existing scheme: one requires edge per owner -> ids unchanged.
    nodes = [Node(id="quest:b", kind=NodeKind.QUEST, name="B", slug="b")]
    g = {0x10000000: _atom_group(0x10000000,
            ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:a", data={"state": "completed"}))}
    e = [Edge(id=0x20000000, type=EdgeType.REQUIRES, src="quest:b", dst=None, cond_group=0x10000000)]
    _, new_edges, new_groups = rekey(nodes, e, g)
    assert new_edges[0].id == stable_edge_id("quest:b", 0)
    assert new_edges[0].cond_group == stable_group_id("quest:b", 0)
    assert set(new_groups) == {stable_group_id("quest:b", 0)}


def test_two_cond_group_edges_from_one_owner_do_not_collide():
    nodes = [Node(id="quest:x", kind=NodeKind.QUEST, name="X", slug="x")]
    g = {
        0x10000000: _atom_group(0x10000000,
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=60)),
        0x10000001: _atom_group(0x10000001,
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:ranged", threshold=50)),
    }
    e = [
        Edge(id=0x20000000, type=EdgeType.REQUIRES, src="quest:x", dst=None, cond_group=0x10000000),
        Edge(id=0x20000001, type=EdgeType.GRANTS, src="quest:x", dst="item:99",
             cond_group=0x10000001, data={"reward": "items", "qty": 1, "tradeable": False}),
    ]
    _, new_edges, new_groups = rekey(nodes, e, g)
    assert len({ne.id for ne in new_edges}) == 2          # distinct edge ids
    assert len({ne.cond_group for ne in new_edges}) == 2  # distinct group roots
    assert len(new_groups) == 2                            # no group dropped/collided
    assert new_edges[0].cond_group == stable_group_id("quest:x", 0)
    assert new_edges[1].cond_group == stable_group_id("quest:x", 1)
    # edge.data survives rekey
    assert new_edges[1].data == {"reward": "items", "qty": 1, "tradeable": False}
