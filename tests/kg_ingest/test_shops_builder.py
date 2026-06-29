from kg_ingest.builders.shops import _shop_slug, shop_roster, shop_type_for, build_shops
from osrs_planner.engine.kg.model import NodeKind

def test_shop_slug_handles_apostrophe_and_trailing_period():
    assert _shop_slug("Aemad's Adventuring Supplies.") == "shop:aemads-adventuring-supplies"
    assert _shop_slug("General Store (Canifis)") == "shop:general-store-canifis"

def test_roster_excludes_varrock_owned():
    recs = [{"sold_by": "Zaff's Superior Staffs!"}, {"sold_by": "Al Kharid General Store"},
            {"sold_by": "Aubury's Rune Shop."}]
    # Varrock owns Zaff + Aubury (matched town-aware); only Al Kharid remains
    roster = shop_roster(recs, {"Zaff's Superior Staffs", "Aubury's Rune Shop"})
    assert roster == ["Al Kharid General Store"]

def test_shop_type_from_icon():
    assert shop_type_for("[[File:Archery shop icon.png]]") == "Archery shop"
    assert shop_type_for("[[File:General store icon.png]]") == "General store"
    assert shop_type_for(None) is None
    assert shop_type_for("[[File:weird.png]]") is None        # no ' icon.png' -> None, not fabricated

def test_build_shops_emits_node_with_type_and_members():
    recs = [{"sold_by": "Al Kharid General Store", "sold_item": "Pot"}]
    ib = {"Al Kharid General Store": {"locations": ["[[Al Kharid]]"], "members": "No",
                                      "owner": [], "icon": "[[File:General store icon.png]]"}}
    nodes, edges, groups = build_shops(recs, ib, [], [], set())
    n = next(n for n in nodes if n.id == "shop:al-kharid-general-store")
    assert n.kind is NodeKind.SHOP
    assert n.data["shop_type"] == "General store"
    assert n.data["members"] is False
    assert "operator" not in n.data            # operators deferred to the NPC layer

def test_collision_guard_disambiguates_loudly(capsys):
    # two DISTINCT names that slugify identically must NOT silently merge
    recs = [{"sold_by": "Cool Shop"}, {"sold_by": "Cool  Shop"}]   # double-space -> same slug
    nodes, _, _ = build_shops(recs, {}, [], [], set())
    ids = sorted(n.id for n in nodes)
    assert len(ids) == 2 and len(set(ids)) == 2   # two distinct nodes, no merge
    assert "collision" in capsys.readouterr().out.lower()
