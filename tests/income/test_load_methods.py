"""load_methods: normalize BOTH datasets into MethodRecord over real data."""
from __future__ import annotations

import os

from osrs_planner.income.methods import load_methods, build_method_index, MethodRecord

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "data",
)


def _by_name(methods, name):
    hits = [m for m in methods if m.name == name]
    assert hits, f"{name!r} not loaded"
    return hits[0]


def test_counts_are_sane():
    methods = load_methods(DATA_DIR)
    # Corrected dedupe (plan defect found in execution): mains key by full slug
    # (all 377 distinct -- gear/mode variants stay separate); iron records merge
    # onto the canonical base-main sharing the looser activity key, else add
    # iron-only. Deterministic measured total = 377 main + 36 iron-only = 413
    # (the other 13 iron records merge onto a canonical main). This replaces the
    # original unreachable 415-426 window the over-collapsing key produced.
    assert len(methods) == 413, len(methods)
    assert all(isinstance(m, MethodRecord) for m in methods)
    assert all(m.id.startswith("method:") for m in methods)
    # mains stay distinct: every full slug present (no main-vs-main collapse)
    assert len([m for m in methods if m.audience == "main"]) == 377


def test_green_dragons_normalized_outputs_and_requirements():
    methods = load_methods(DATA_DIR)
    gd = _by_name(methods, "Killing green dragons")
    assert gd.id == "method:killing-green-dragons"
    assert gd.audience == "main"
    assert gd.requires_ge is False
    assert gd.iron_eligible is True
    hide = [o for o in gd.outputs if o.item_id == "item:1753"]
    assert hide, "green dragonhide (item:1753) output missing"
    assert hide[0].qty_per_hour == 180.0  # qty 1 * kph 180 (isperkill)
    coins = [o for o in gd.outputs if o.is_coins]
    assert coins and coins[0].item_id is None
    # aggregate / unresolvable output (Gem drop table) -> item_id None, not coins
    assert any(o.item_id is None and not o.is_coins for o in gd.outputs)
    # DR-1: the dedupe MERGE with the iron "Green dragons (...)" records UNIONs
    # requirements -- the main's HTML-parsed skills are KEPT (never overwritten):
    assert gd.requirements.skills.get("skill:prayer") == 25
    assert gd.requirements.skills.get("skill:ranged") == 60
    assert "skill:combat" not in gd.requirements.skills
    # DR-1 + DR-4: AND the iron quest gate is now present, with the parenthetical
    # stripped ("A Kingdom Divided (for thralls)" -> quest:a-kingdom-divided).
    assert "quest:a-kingdom-divided" in gd.requirements.quests
    assert "quest:a-kingdom-divided-for-thralls" not in gd.requirements.quests


def test_iron_native_method_loaded_with_structured_requirements():
    methods = load_methods(DATA_DIR)
    ruby = _by_name(methods, "Picking up ruby rings (Varrock west bank) and high-alching")
    assert ruby.audience == "ironman"
    assert ruby.stage == "mid"
    assert ruby.requirements.skills.get("skill:magic") == 55
    # "Crack the Clue III" is a real quest (KG node absent -> a disclosed known-gap,
    # validated as a [known-gap] warning in T9); it IS still a quest gate (not a diary).
    assert ruby.requirements.quests == ["quest:crack-the-clue-iii"]
    # prose item ("fire/nature runes ...") is NOT emitted as an item:<n> gate
    assert ruby.requirements.items == []
    assert "iron_item_notes" in ruby.tags


def test_iron_diary_shaped_req_is_not_a_quest_gate():
    # DR-3: a DIARY-shaped requirement string ("Ardougne Diary medium tasks" on
    # "Pickpocketing Knights of Ardougne") must NOT become a quest gate -- it routes
    # to advisory tags instead. (Diaries are NOT quests; income must not add KG nodes.)
    methods = load_methods(DATA_DIR)
    knights = _by_name(methods, "Pickpocketing Knights of Ardougne")
    assert all("ardougne-diary" not in q for q in knights.requirements.quests)
    assert not any("diary" in q.lower() for q in knights.requirements.quests)
    advisory = knights.tags.get("advisory_reqs") or []
    assert any("diary" in a.lower() for a in advisory), (
        "diary-shaped req should be routed to tags['advisory_reqs']"
    )


def test_iron_green_dragons_quest_gate_resolves_with_paren_stripped():
    # DR-4: the iron green-dragons quest ref "A Kingdom Divided (for thralls)" must
    # slug to quest:a-kingdom-divided (the PRESENT node) -- the parenthetical stripped
    # BEFORE slugging, so loader and validator agree and the gate resolves.
    methods = load_methods(DATA_DIR)
    gd = _by_name(methods, "Killing green dragons")  # merged record (DR-1 union)
    assert "quest:a-kingdom-divided" in gd.requirements.quests
    assert "quest:a-kingdom-divided-for-thralls" not in gd.requirements.quests


def test_dedupe_merges_rune_dragons_with_structured_reqs():
    methods = load_methods(DATA_DIR)
    rd = [m for m in methods if "rune dragons" in m.name.lower()]
    # exactly one merged record for the rune-dragons activity key
    assert len(rd) == 1
    merged = rd[0]
    # the merged record carries structured (iron) requirements
    assert merged.requirements.quests == ["quest:dragon-slayer-ii"]


def test_main_only_method_marked_main():
    methods = load_methods(DATA_DIR)
    grimy = [m for m in methods if "ranarr" in m.name.lower() and m.audience == "main"]
    assert grimy, "expected a main-audience ranarr method"


def test_build_method_index_round_trips():
    methods = load_methods(DATA_DIR)
    idx = build_method_index(methods)
    ids = [m.id for m in (idx.values() if isinstance(idx, dict) else idx)]
    assert len(ids) == len(set(ids)) == len(methods)


def test_net_sign_in_allowed_set():
    methods = load_methods(DATA_DIR)
    assert all(m.net_sign in ("earner", "sink") for m in methods)
