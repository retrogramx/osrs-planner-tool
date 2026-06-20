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

def test_no_account_state_empty():
    assert emit_tailoring(None, clog_ids={1, 2}).strip().endswith("*/")  # just the module header

def test_high_value_owned_not_hidden():
    st = build_account_state("ironman", bank_tsv="400\tY\t1\n", clog_obtained=set())
    out = emit_tailoring(st, clog_ids=set(), value_index={400: 5_000_000})
    assert "id:[400]" not in out                              # valuable owned item never hidden
