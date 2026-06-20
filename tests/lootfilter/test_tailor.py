from osrs_planner.lootfilter.tailor import emit_tailoring
from osrs_planner.account.state import build_account_state

def test_missing_beam_obtained_dim_and_hide_owned():
    # clog universe {100,200,300}; obtained {200}; bank {200, 400}
    st = build_account_state("ironman", bank_tsv="200\tX\t1\n400\tY\t1\n", clog_obtained={"item:200"})
    out = emit_tailoring(st, clog_ids={100, 200, 300})
    assert "module:tailoring" in out
    assert "id:[100, 300]" in out and "showLootbeam = true;" in out and "notify = true;" in out  # missing beam
    assert "id:[200]" in out                                  # obtained dim
    assert "#define HIDE_OWNED false" in out
    assert "HIDE_OWNED && id:[400]" in out                    # hide-owned excludes ALL clog (200 is clog, kept)

def test_rarity_splits_missing_beams():
    # rarity_index buckets missing slots: ULTRA = red border + beam, RARE = beam, COMMON = panel only
    st = build_account_state("ironman", bank_tsv="", clog_obtained=set())
    out = emit_tailoring(st, clog_ids={11, 22, 33}, rarity_index={11: "ULTRA", 33: "COMMON"})  # 22 -> RARE default
    lines = out.splitlines()
    ultra = next(l for l in lines if "id:[11]" in l)
    rare = next(l for l in lines if "id:[22]" in l)
    common = next(l for l in lines if "id:[33]" in l)
    assert "#ffff2b2b" in ultra and "showLootbeam = true;" in ultra   # rarest: red border + beam
    assert "showLootbeam = true;" in rare                             # rare: beam
    assert "showLootbeam" not in common                              # common: gold PANEL only, NO beam

def test_clog_purple_gold_signature():
    # clog signature = purple panel + (gold border on RARE/COMMON, red on ULTRA) -- unique to clog
    from osrs_planner.lootfilter.tailor import _CLOG
    assert _CLOG == "#ffc23cf0"
    st = build_account_state("ironman", bank_tsv="", clog_obtained=set())
    out = emit_tailoring(st, clog_ids={11, 22}, rarity_index={11: "ULTRA"})  # 22 -> RARE default
    ultra = next(l for l in out.splitlines() if "id:[11]" in l)
    rare = next(l for l in out.splitlines() if "id:[22]" in l)
    assert "#ffc23cf0" in ultra and "#ffff2b2b" in ultra   # purple panel + RED border
    assert "#ffc23cf0" in rare and "#ffffd700" in rare     # purple panel + GOLD border

def test_no_account_state_empty():
    assert emit_tailoring(None, clog_ids={1, 2}).strip().endswith("*/")  # just the module header

def test_high_value_owned_not_hidden():
    st = build_account_state("ironman", bank_tsv="400\tY\t1\n", clog_obtained=set())
    out = emit_tailoring(st, clog_ids=set(), value_index={400: 5_000_000})
    assert "id:[400]" not in out                              # valuable owned item never hidden
