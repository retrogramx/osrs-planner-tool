import re

from osrs_planner.lootfilter.emit import emit_notable

def test_notable_module_layers():
    out = emit_notable(recommended_ids=[10, 11], rare_ids=[20])
    assert "define:module:notable" in out
    assert "id:[10, 11]" in out          # recommended list
    assert "id:[20]" in out              # rare list beams
    assert "value:>=500000" in out       # value safety-net beam

    # Ordering (whole-branch-review fix B): rules are terminal/first-match-wins, so the BEAM
    # rules (rare, value) must be emitted BEFORE the no-beam recommended rule -- else a
    # recommended∩rare item would hit the recommended rule first and never beam.
    rare_pos = out.index("id:[20]")
    value_pos = out.index("value:>=500000")
    recommended_pos = out.index("id:[10, 11]")
    assert rare_pos < recommended_pos, "rare beam rule must be emitted before the recommended rule"
    assert value_pos < recommended_pos, "value beam rule must be emitted before the recommended rule"

    # Isolate each rule's own self-contained block: emit_style_input emits `decl \n #define \n
    # rule`, and showLootbeam lives in the #define (referenced by the rule via the macro name),
    # so a block runs from its "/*@ define:input:notable" decl up to the NEXT such decl (or the
    # end of the module). Split on that marker to check each rule's own beam policy precisely,
    # not just count occurrences anywhere in the module.
    starts = [m.start() for m in re.finditer(r"/\*@ define:input:notable", out)] + [len(out)]
    def block_at(pos: int) -> str:
        start = max(s for s in starts if s <= pos)
        end = min(s for s in starts if s > pos)
        return out[start:end]

    recommended_block = block_at(recommended_pos)
    rare_block = block_at(rare_pos)
    value_block = block_at(value_pos)

    assert "showLootbeam" not in recommended_block, "the recommended rule must carry NO beam"
    assert "showLootbeam = true" in rare_block, "the rare rule must beam"
    assert "showLootbeam = true" in value_block, "the value safety-net rule must beam"
