import dataclasses
import json
import pathlib

import pytest

from osrs_planner.engine.kg.model import (
    NodeKind, EdgeType, Op, AtomType,
    Node, ConditionAtom, ConditionGroup, Edge,
)
from osrs_planner.engine.kg.json_store import edge_to_dict, edge_from_dict


def test_node_kind_members_match_schema_taxonomy():
    assert {k.value for k in NodeKind} == {
        "skill", "item", "monster", "quest", "access", "region",
        "account_type", "gear_loadout", "activity", "diary",
        "combat_achievement", "minigame", "clog_slot", "goal",
        "recipe", "equipment_bonuses",
    }


def test_node_kind_is_str_enum():
    assert NodeKind.SKILL == "skill"
    assert isinstance(NodeKind.SKILL, str)


def test_edge_type_members_match_schema():
    assert {e.value for e in EdgeType} == {
        "requires", "grants", "drops", "located_in", "gated_by",
        "effect", "progress_towards", "supersedes", "same_entity",
        "consumes", "produces", "degrades_to", "repairs",
        "has_bonuses",
    }


def test_op_members():
    assert {o.value for o in Op} == {"and", "or", "not"}


def test_atom_type_locked_set_includes_gear_loadout_and_ca_split():
    values = {a.value for a in AtomType}
    assert values == {
        "skill_level", "skill_xp", "combat_level", "quest",
        "achievement_diary", "combat_achievement", "item",
        "is_unlocked", "gear_loadout", "kill_count", "quest_points",
        "account_type", "clue_scrolls", "combat_achievement_points",
        "count_satisfied",
    }
    # the de-overload (schema §"combat_achievement scope"): the binary
    # per-task atom and the accumulator tier-points atom are DISTINCT members.
    assert AtomType.COMBAT_ACHIEVEMENT != AtomType.COMBAT_ACHIEVEMENT_POINTS


def test_node_construction_and_data_default():
    n = Node(id="npc:7221", kind=NodeKind.MONSTER, name="Scurrius", slug="scurrius")
    assert n.id == "npc:7221"
    assert n.kind is NodeKind.MONSTER
    assert n.name == "Scurrius"
    assert n.slug == "scurrius"
    assert n.data == {}  # default_factory(dict)


def test_node_carries_data_blob():
    n = Node(
        id="gear_loadout:void", kind=NodeKind.GEAR_LOADOUT, name="Full Void",
        slug="void", data={"styles": ["melee", "ranged", "magic"]},
    )
    assert n.data["styles"] == ["melee", "ranged", "magic"]


def test_node_is_frozen():
    n = Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack")
    with pytest.raises(dataclasses.FrozenInstanceError):
        n.name = "Strength"  # type: ignore[misc]


def test_node_data_default_is_not_shared():
    a = Node(id="access:a", kind=NodeKind.ACCESS, name="A", slug="a")
    b = Node(id="access:b", kind=NodeKind.ACCESS, name="B", slug="b")
    assert a.data is not b.data  # default_factory, not a shared mutable default


def test_atom_skill_level_minimal():
    a = ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=70)
    assert a.atom_type is AtomType.SKILL_LEVEL
    assert a.ref_node == "skill:attack"
    assert a.threshold == 70
    assert a.qty is None
    assert a.data == {}


def test_atom_refless_quest_points():
    # accumulator atoms (schema: quest_points / combat_achievement_points) carry no ref_node
    a = ConditionAtom(atom_type=AtomType.QUEST_POINTS, threshold=32)
    assert a.ref_node is None
    assert a.threshold == 32


def test_atom_quest_state_in_data():
    # schema atom-semantics: quest 3-state lives in data['state'] (ORDERED enum)
    a = ConditionAtom(
        atom_type=AtomType.QUEST, ref_node="quest:dragon-slayer-i",
        data={"state": "completed"},
    )
    assert a.data["state"] == "completed"


def test_atom_account_type_value_in_data():
    a = ConditionAtom(atom_type=AtomType.ACCOUNT_TYPE, data={"value": "ironman"})
    assert a.data["value"] == "ironman"


def test_atom_clue_scrolls_set_ref_and_threshold():
    a = ConditionAtom(
        atom_type=AtomType.CLUE_SCROLLS, threshold=2,
        data={"set_ref": ["item:2677", "item:2801"]},
    )
    assert a.threshold == 2
    assert a.data["set_ref"] == ["item:2677", "item:2801"]


def test_atom_item_uses_qty():
    a = ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8839", qty=1)
    assert a.qty == 1


def test_atom_gear_loadout_refs_loadout_node():
    a = ConditionAtom(atom_type=AtomType.GEAR_LOADOUT, ref_node="gear_loadout:void")
    assert a.ref_node == "gear_loadout:void"
    assert a.threshold is None


def test_atom_is_frozen():
    a = ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=70)
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.threshold = 60  # type: ignore[misc]


def test_group_with_atom_children():
    # G_stats from the schema worked example: AND(70 Att, 70 Str)
    g = ConditionGroup(
        id=2, op=Op.AND, parent=1,
        children=[
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=70),
            ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:strength", threshold=70),
        ],
    )
    assert g.id == 2
    assert g.op is Op.AND
    assert g.parent == 1
    assert len(g.children) == 2
    assert all(isinstance(c, ConditionAtom) for c in g.children)


def test_group_children_can_mix_ids_and_atoms():
    # G_root from the worked example: OR( <group 2>, <group 3> ) — children are ints
    root = ConditionGroup(id=1, op=Op.OR, parent=None, children=[2, 3])
    assert root.parent is None  # NULL => root
    assert root.children == [2, 3]
    assert all(isinstance(c, int) for c in root.children)


def test_group_mixed_int_and_atom_children():
    mixed = ConditionGroup(
        id=99, op=Op.AND, parent=None,
        children=[10, ConditionAtom(atom_type=AtomType.QUEST_POINTS, threshold=32)],
    )
    assert mixed.children[0] == 10
    assert isinstance(mixed.children[1], ConditionAtom)


def test_group_is_frozen():
    g = ConditionGroup(id=1, op=Op.OR, parent=None, children=[2, 3])
    with pytest.raises(dataclasses.FrozenInstanceError):
        g.op = Op.AND  # type: ignore[misc]


def test_edge_plain_unconditional():
    # schema worked example: requires npc:7221 -> access:scurrius-lair (unconditional)
    e = Edge(id=9004, type=EdgeType.REQUIRES, src="npc:7221", dst="access:scurrius-lair")
    assert e.id == 9004
    assert e.type is EdgeType.REQUIRES
    assert e.src == "npc:7221"
    assert e.dst == "access:scurrius-lair"
    assert e.cond_group is None  # unconditional default


def test_edge_dst_null_pure_condition():
    # schema: requires edge whose dst IS NULL because the constraint is the cond tree
    e = Edge(id=9000, type=EdgeType.REQUIRES, src="npc:7221", dst=None, cond_group=1)
    assert e.dst is None
    assert e.cond_group == 1


def test_edge_gear_loadout_composition():
    # schema: gear_loadout:void carries its composition on a dst=NULL requires edge
    e = Edge(id=9100, type=EdgeType.REQUIRES, src="gear_loadout:void", dst=None, cond_group=10)
    assert e.src == "gear_loadout:void"
    assert e.dst is None
    assert e.cond_group == 10


def test_edge_is_frozen():
    e = Edge(id=9004, type=EdgeType.REQUIRES, src="npc:7221", dst="access:scurrius-lair")
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.dst = "region:varrock"  # type: ignore[misc]


def test_same_entity_edge_type_exists_and_roundtrips():
    assert EdgeType.SAME_ENTITY.value == "same_entity"
    e = Edge(id=1, type=EdgeType.SAME_ENTITY, src="item:1712", dst="item:amulet-of-glory",
             cond_group=None, data={"basis": "x"})
    assert edge_from_dict(edge_to_dict(e)) == e


def test_schema_declares_same_entity_live():
    with open(pathlib.Path(__file__).resolve().parents[2] / "kg" / "schema.json") as f:
        schema = json.load(f)
    assert schema["edge_kinds"]["same_entity"]["status"] == "live"
    assert "is_page" in schema["node_kinds"]["item"]["data_keys"]


def test_recipe_kind_and_consumes_produces_edges_exist():
    from osrs_planner.engine.kg.model import NodeKind, EdgeType
    assert NodeKind.RECIPE.value == "recipe"
    assert EdgeType.CONSUMES.value == "consumes"
    assert EdgeType.PRODUCES.value == "produces"


def test_schema_declares_recipe_consumes_produces_live():
    schema = json.loads((pathlib.Path(__file__).resolve().parents[2] / "kg" / "schema.json").read_text())
    assert schema["node_kinds"]["recipe"]["status"] == "live"
    assert schema["edge_kinds"]["consumes"]["status"] == "live"
    assert schema["edge_kinds"]["produces"]["status"] == "live"
    assert "charge_yield" in schema["node_kinds"]["recipe"]["data_keys"]
    assert schema["vocab"]["consumes_role"] == ["material", "subject"]


def test_degrades_to_edge_exists_and_declared_live():
    from osrs_planner.engine.kg.model import EdgeType
    assert EdgeType.DEGRADES_TO.value == "degrades_to"
    import json, pathlib
    schema = json.loads((pathlib.Path(__file__).resolve().parents[2] / "kg" / "schema.json").read_text())
    d = schema["edge_kinds"]["degrades_to"]
    assert d["status"] == "live" and d["domain"] == ["item"] and d["range"] == ["item"] and d["dst"] == "optional"
    assert d["cond_group"] == "forbidden"
    assert d["reified"] is True
    assert schema["vocab"]["degrade_terminal"] == ["destroyed", "reverts_to", "broken"]
    assert schema["vocab"]["degrade_trigger"] == ["per_use", "per_hit"]


def test_repairs_edge_exists_and_declared_live():
    from osrs_planner.engine.kg.model import EdgeType
    assert EdgeType.REPAIRS.value == "repairs"
    import json, pathlib
    schema = json.loads((pathlib.Path(__file__).resolve().parents[2] / "kg" / "schema.json").read_text())
    d = schema["edge_kinds"]["repairs"]
    assert d["status"] == "live" and d["domain"] == ["item"] and d["range"] == ["item"]
    assert d["dst"] == "required" and d["cond_group"] == "forbidden" and d["reified"] is False


def test_equipment_bonuses_and_has_bonuses_are_live():
    from osrs_planner.engine.kg.model import NodeKind, EdgeType
    assert NodeKind.EQUIPMENT_BONUSES.value == "equipment_bonuses"
    assert EdgeType.HAS_BONUSES.value == "has_bonuses"
    import json, pathlib
    schema = json.loads((pathlib.Path(__file__).resolve().parents[2] / "kg" / "schema.json").read_text())
    assert schema["node_kinds"]["equipment_bonuses"]["status"] == "live"
    hb = schema["edge_kinds"]["has_bonuses"]
    assert hb["status"] == "live" and hb["domain"] == ["item"] and hb["range"] == ["equipment_bonuses"]
    assert hb["dst"] == "required" and hb["reified"] is False
    assert hb["cond_group"] == "forbidden"
