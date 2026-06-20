import os
from osrs_planner.lootfilter.generate import generate_filter, load_clog_ids
from osrs_planner.account.state import build_account_state
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_generic_modules_in_order_no_tailoring():
    f = generate_filter()
    for m in ("module:settings", "module:trophies", "module:categories", "module:fallback"):
        assert m in f
    assert "module:tailoring" not in f                        # generic omits tailoring
    assert f.index("module:settings") < f.index("module:trophies") < f.index("module:categories") < f.index("module:fallback")
    assert f.startswith("meta {") and "#define IRONMAN accountType:1" in f

def test_tailored_inserts_tailoring_above_trophies():
    st = build_account_state("ironman", bank_tsv="995\tCoins\t1\n", clog_obtained={"item:4151"})
    f = generate_filter(account_state=st)
    assert "module:tailoring" in f and f.index("module:tailoring") < f.index("module:trophies")

def test_real_clog_ids_load():
    ids = load_clog_ids(os.path.join(REPO, "data"))
    assert len(ids) > 500 and 4151 in ids

def test_clog_rarity_tiers():
    from osrs_planner.lootfilter.generate import load_clog_rarity
    rar = load_clog_rarity(os.path.join(REPO, "data"))
    assert rar.get(20997) == "ULTRA"   # Twisted bow: RAID source -> ULTRA (its 1/34 chest roll isn't its true rarity)
    assert rar.get(4151) == "COMMON"   # Abyssal whip 1/512 -> COMMON, no beam spam
    assert set(rar.values()) == {"ULTRA", "COMMON"}   # only non-default tiers stored; RARE is implicit

def test_tailored_hide_owned_spares_high_value():
    # the high-value guard must be LIVE in the real generate path (not just the unit test)
    import re
    from osrs_planner.lootfilter.generate import load_value_index
    D = os.path.join(REPO, "data")
    vi = load_value_index(D); clog = set(load_clog_ids(D))
    hv = next(i for i in sorted(vi) if vi[i] >= 1_000_000 and i not in clog)   # valuable, non-clog
    lv = next(i for i in sorted(vi) if 0 < vi[i] < 50_000 and i not in clog)   # cheap, non-clog
    st = build_account_state("ironman", bank_tsv=f"{hv}\tH\t1\n{lv}\tL\t1\n", clog_obtained=set())
    m = re.search(r"HIDE_OWNED && (id:\[[0-9, ]+\])", generate_filter(account_state=st))
    assert m, "expected a HIDE_OWNED rule for the cheap item"
    ids = set(m.group(1)[4:-1].replace(" ", "").split(","))
    assert str(lv) in ids and str(hv) not in ids   # cheap hideable; valuable spared
