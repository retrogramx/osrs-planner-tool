import os
from osrs_planner.account.bank import parse_bank_tsv, bank_value

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "sample_bank.tsv")

class FakeProvider:  # deterministic prices, no dependency on the committed snapshot
    GE = {"item:561": 120, "item:4151": 1_500_000}        # nature rune, whip (tradeable)
    HA = {"item:561": 108, "item:4151": 72_000,           # whip alchs for far less than GE
          "item:30682": 6_000}                            # Accumulation charm: HA but NO GE (untradeable)
    def ge_price(self, i): return self.GE.get(i)
    def high_alch(self, i): return self.HA.get(i)

def test_iron_realizable_vs_ge_plat_and_untradeable():
    counts = parse_bank_tsv(open(FIX, encoding="utf-8").read())
    v = bank_value(counts, FakeProvider(), "ironman")
    plat = 5000 * 1000                                     # 5000 platinum tokens @ 1000gp each
    # coins 1,000,000 + plat face; nature 5000*120 GE vs *108 HA; whip 1.5M GE vs 72k HA
    assert v["ge_value"] == 1_000_000 + plat + 5000*120 + 1*1_500_000
    assert v["iron_realizable"] == 1_000_000 + plat + 5000*108 + 1*72_000
    assert v["iron_realizable"] < v["ge_value"]            # iron can't realise GE, only HA
    assert v["headline"] == v["iron_realizable"]           # iron headline
    assert v["unpriced_count"] == 1                        # Accumulation charm (untradeable HA)

def test_untradeable_ha_not_counted_as_realizable():
    # an untradeable item with a NOMINAL high-alch must NOT inflate iron_realizable
    v = bank_value({"item:30682": 10}, FakeProvider(), "ironman")
    assert v["iron_realizable"] == 0 and v["ge_value"] == 0 and v["unpriced_count"] == 1

def test_platinum_tokens_count_as_currency():
    v = bank_value({"item:13204": 3}, FakeProvider(), "ironman")
    assert v["iron_realizable"] == 3000 and v["ge_value"] == 3000

def test_main_headline_is_ge():
    counts = parse_bank_tsv(open(FIX, encoding="utf-8").read())
    v = bank_value(counts, FakeProvider(), "main")
    assert v["headline"] == v["ge_value"]
