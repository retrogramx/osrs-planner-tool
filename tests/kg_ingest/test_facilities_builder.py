import json, pathlib
from osrs_planner.engine.kg.model import NodeKind
from kg_ingest.builders.facilities import classify_infobox, build_facilities, facility_roster

ROOT = pathlib.Path(__file__).resolve().parents[2]

def test_nodekind_facility_exists():
    assert NodeKind("facility") is NodeKind.FACILITY
    assert NodeKind.FACILITY.value == "facility"

def test_schema_facility_live_with_data_keys():
    schema = json.loads((ROOT / "kg" / "schema.json").read_text())
    fac = schema["node_kinds"]["facility"]
    assert fac["status"] == "live"
    for k in ("skills", "recipe_count", "source_url", "source_token", "aliases"):
        assert k in fac["data_keys"], f"{k} missing from facility data_keys"


def test_classify_infobox_routing():
    assert classify_infobox(["Infobox Scenery"]) == "facility"
    assert classify_infobox(["Infobox Construction"]) == "facility"
    assert classify_infobox(["Infobox NPC"]) == "npc"
    assert classify_infobox(["Infobox Shop"]) == "shop"
    assert classify_infobox(["Infobox Activity"]) == "ambiguous"
    assert classify_infobox(["Infobox Location"]) == "ambiguous"
    assert classify_infobox([]) == "ambiguous"
    # NPC/Shop take precedence over a co-present facility infobox (defer the character/store)
    assert classify_infobox(["Infobox Scenery", "Infobox NPC"]) == "npc"
    assert classify_infobox(["Infobox Shop", "Infobox Scenery"]) == "shop"


def _ib(infoboxes, url="https://x/w/V"):
    return {"infoboxes": infoboxes, "source_url": url}

def _rows():
    return [
        {"page_name": "Bronze bar", "uses_facility": ["Furnace"], "uses_skill": ["Smithing"]},
        {"page_name": "Steel bar", "uses_facility": ["Furnace"], "uses_skill": ["Smithing"]},
        {"page_name": "Gold bracelet", "uses_facility": ["Furnace"], "uses_skill": ["Crafting"]},
        {"page_name": "Dagger", "uses_facility": ["Anvil"], "uses_skill": ["Smithing"]},
        {"page_name": "Plank", "uses_facility": ["Sawmill"], "uses_skill": [""]},   # skill-less
        {"page_name": "Battlestaff(o)", "uses_facility": ["Thormac"], "uses_skill": [""]},
        {"page_name": "Nothing", "uses_facility": None, "uses_skill": ["Magic"]},   # no facility -> ignored
    ]

def _ibs():
    return {
        "Furnace": _ib(["Infobox Scenery"], "https://x/w/Furnace"),
        "Anvil": _ib(["Infobox Scenery"], "https://x/w/Anvil"),
        "Sawmill": _ib(["Infobox Shop"]),       # defer
        "Thormac": _ib(["Infobox NPC"]),         # defer
    }

def _nmap(nodes):
    return {n.id: n for n in nodes}

def test_roster_distinct_nonempty():
    assert facility_roster(_rows()) == ["Anvil", "Furnace", "Sawmill", "Thormac"]

def test_builder_admits_facilities_defers_npc_and_shop():
    nodes, edges, groups = build_facilities(_rows(), _ibs(), {"force_facility": [], "force_exclude": []})
    ids = _nmap(nodes)
    assert edges == [] and groups == {}
    assert "facility:furnace" in ids and "facility:anvil" in ids
    assert "facility:sawmill" not in ids        # Infobox Shop -> deferred
    assert "facility:thormac" not in ids        # Infobox NPC -> deferred

def test_builder_skill_aggregation_and_count():
    nodes = _nmap(build_facilities(_rows(), _ibs(), {})[0])
    furn = nodes["facility:furnace"]
    assert furn.kind is NodeKind.FACILITY and furn.name == "Furnace"
    assert furn.data["skills"] == ["Crafting", "Smithing"]   # sorted distinct, "" dropped
    assert furn.data["recipe_count"] == 3
    assert furn.data["source_token"] == "Bucket:recipe.uses_facility=Furnace"
    assert furn.data["source_url"] == "https://x/w/Furnace"

def test_skill_less_facility_kept_without_skills_key():
    # Sawmill is deferred (shop), so use an override to admit a skill-less facility instead
    rows = [{"page_name": "Repair", "uses_facility": ["Armour stand"], "uses_skill": [""]}]
    ibs = {"Armour stand": _ib(["Infobox Scenery"], "https://x/w/Armour_stand")}
    nodes = _nmap(build_facilities(rows, ibs, {})[0])
    n = nodes["facility:armour-stand"]
    assert "skills" not in n.data            # no skill fabricated
    assert n.data["recipe_count"] == 1

def test_overrides_force_facility_and_exclude():
    rows = [
        {"page_name": "Smith X", "uses_facility": ["Blast Furnace"], "uses_skill": ["Smithing"]},
        {"page_name": "Y", "uses_facility": ["Anvil"], "uses_skill": ["Smithing"]},
    ]
    ibs = {"Blast Furnace": _ib(["Infobox Activity"], "https://x/w/Blast_Furnace"),  # ambiguous
           "Anvil": _ib(["Infobox Scenery"], "https://x/w/Anvil")}
    ov = {"force_facility": [{"value": "Blast Furnace", "source_url": "https://x/w/Blast_Furnace"}],
          "force_exclude": [{"value": "Anvil"}]}
    nodes = _nmap(build_facilities(rows, ibs, ov)[0])
    assert "facility:blast-furnace" in nodes     # ambiguous promoted by override
    assert "facility:anvil" not in nodes         # force_exclude wins

def test_per_page_name_distinctness_no_case_merge():
    rows = [
        {"page_name": "Bones", "uses_facility": ["Chaos altar"], "uses_skill": ["Prayer"]},
        {"page_name": "Runes", "uses_facility": ["Chaos Altar"], "uses_skill": ["Runecraft"]},
    ]
    ibs = {"Chaos altar": _ib(["Infobox Scenery"]), "Chaos Altar": _ib(["Infobox Scenery"])}
    nodes = _nmap(build_facilities(rows, ibs, {})[0])
    # distinct page names -> distinct facilities; slug collision guard appends -2
    assert "facility:chaos-altar" in nodes
    assert "facility:chaos-altar-2" in nodes

def test_deterministic():
    a = build_facilities(_rows(), _ibs(), {})[0]
    b = build_facilities(_rows(), _ibs(), {})[0]
    assert [n.id for n in a] == [n.id for n in b]


# ── redirect-aware canonical dedup tests ──────────────────────────────────────

def test_redirect_dedup_cooking_range_collapses_into_range():
    """Cooking range (redirect_target=Range) + Range (no redirect) -> ONE node facility:range."""
    rows = [
        {"page_name": "Lobster", "uses_facility": ["Cooking range"], "uses_skill": ["Cooking"]},
        {"page_name": "Swordfish", "uses_facility": ["Range"], "uses_skill": ["Cooking"]},
    ]
    ibs = {
        "Cooking range": {"infoboxes": ["Infobox Scenery"], "redirect_target": "Range", "source_url": "https://x/w/Range"},
        "Range": {"infoboxes": ["Infobox Scenery"], "redirect_target": None, "source_url": "https://x/w/Range"},
    }
    nodes = _nmap(build_facilities(rows, ibs, {})[0])
    assert len(nodes) == 1, f"expected 1 node, got {list(nodes)}"
    assert "facility:range" in nodes
    n = nodes["facility:range"]
    assert n.name == "Range"
    assert n.data["recipe_count"] == 2            # both rows counted
    assert n.data.get("aliases") == ["Cooking range"]


def test_redirect_dedup_underscore_space_pair():
    """Funeral pyre (Barbarian) + Funeral_pyre_(Barbarian) -> ONE node."""
    canonical = "Funeral pyre (Barbarian)"
    underscore = "Funeral_pyre_(Barbarian)"
    rows = [
        {"page_name": "Chewed bones", "uses_facility": [canonical], "uses_skill": ["Firemaking"]},
        {"page_name": "Chewed bones2", "uses_facility": [underscore], "uses_skill": ["Firemaking"]},
    ]
    ibs = {
        canonical: {"infoboxes": ["Infobox Scenery"], "redirect_target": None, "source_url": ""},
        underscore: {"infoboxes": ["Infobox Scenery"], "redirect_target": canonical, "source_url": ""},
    }
    nodes = _nmap(build_facilities(rows, ibs, {})[0])
    assert len(nodes) == 1, f"expected 1 node, got {list(nodes)}"
    n = next(iter(nodes.values()))
    assert n.name == canonical
    assert underscore in n.data.get("aliases", [])


def test_force_facility_never_collapsed():
    """Two force_facility values sharing the same redirect_target stay as TWO distinct nodes."""
    rows = [
        {"page_name": "Astral rune", "uses_facility": ["Catalytic runic altar"], "uses_skill": ["Runecraft"]},
        {"page_name": "Fire rune", "uses_facility": ["Elemental runic altar"], "uses_skill": ["Runecraft"]},
    ]
    ibs = {
        "Catalytic runic altar": {"infoboxes": [], "redirect_target": "Runic altar", "source_url": "https://x/w/Runic_altar"},
        "Elemental runic altar": {"infoboxes": [], "redirect_target": "Runic altar", "source_url": "https://x/w/Runic_altar"},
    }
    ov = {
        "force_facility": [
            {"value": "Catalytic runic altar", "source_url": "https://x/w/Runic_altar"},
            {"value": "Elemental runic altar", "source_url": "https://x/w/Runic_altar"},
        ],
        "force_exclude": [],
    }
    nodes = _nmap(build_facilities(rows, ibs, ov)[0])
    assert len(nodes) == 2, f"expected 2 nodes (no collapse), got {list(nodes)}"
    assert "facility:catalytic-runic-altar" in nodes
    assert "facility:elemental-runic-altar" in nodes
    # neither should have aliases (they are distinct, not collapsed)
    assert "aliases" not in nodes["facility:catalytic-runic-altar"].data
    assert "aliases" not in nodes["facility:elemental-runic-altar"].data
