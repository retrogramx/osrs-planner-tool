import json, pathlib
from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType

ROOT = pathlib.Path(__file__).resolve().parents[2]

def _store():
    return JsonKGStore.from_dir(str(ROOT / "kg"))

def test_lowes_stocks_storeline_items():
    store = _store()
    stock = {e.dst for e in store.edges if e.type is EdgeType.SELLS and e.src == "shop:lowes-archery-emporium"}
    assert len(stock) >= 10                                 # the 27 categories -> exact Storeline stock

def test_zaff_battlestaff_keeps_gate():
    store = _store()
    gated = [e for e in store.edges if e.type is EdgeType.SELLS
             and e.src == "shop:zaffs-superior-staffs" and e.dst == "item:1391"]
    assert gated and any(e.cond_group is not None for e in gated)   # the What-Lies-Below overlay survives

def test_dialogue_shop_keeps_owner_sell():
    store = _store()
    fur = {e.dst for e in store.edges if e.type is EdgeType.SELLS and e.src == "shop:baraeks-fur-stall"}
    assert "item:6814" in fur                               # Baraek's Fur fallback (no Storeline)

def test_no_gated_and_ungated_duplicate():
    store = _store()
    pairs = {}
    for e in store.edges:
        if e.type is EdgeType.SELLS:
            pairs.setdefault((e.src, e.dst), set()).add(e.cond_group is not None)
    assert not [k for k, v in pairs.items() if v == {True, False}]   # ownership rule holds in the graph
