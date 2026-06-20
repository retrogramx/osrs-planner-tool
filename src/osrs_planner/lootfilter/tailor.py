# src/osrs_planner/lootfilter/tailor.py
"""Account tailoring (design §9): beam the collection-log slots you still NEED, dim
the ones you HAVE, optionally hide what you bank. Consumes an already-built
AccountState (counts + clog_obtained); never calls the ingestion itself. The caller
supplies the clog id-set (generate.load_clog_ids)."""
from __future__ import annotations

from osrs_planner.lootfilter.emit import emit_module, emit_rule, IRONMAN, _id_list

_HIGH_VALUE = 100_000  # A grade -> never hide an owned item worth this much

def _ids(keys) -> set[int]:
    return {int(k.split(":")[1]) for k in keys}

def emit_tailoring(account_state, clog_ids, value_index=None) -> str:
    if account_state is None:
        return emit_module("tailoring", "Account tailoring", "")
    clog = set(clog_ids)
    obtained = _ids(account_state.clog_obtained)
    owned = _ids(account_state.counts)
    missing = sorted(clog - obtained)
    have = sorted(clog & obtained)
    value_index = value_index or {}
    hide = sorted(i for i in owned if i not in clog and value_index.get(i, 0) < _HIGH_VALUE)
    lines = ['/*@ define:input:tailoring\nlabel: Hide items already in my bank\ntype: boolean\ngroup: Tailor\n*/\n#define HIDE_OWNED false']
    if missing:
        lines.append(emit_rule(f"{IRONMAN} && {_id_list(missing)}",
            {"hidden": "false", "textColor": "#ffffffff", "backgroundColor": "#ffd8b01a", "borderColor": "#ffffd700",
             "showLootbeam": "true", "lootbeamColor": "#ffffd700", "sound": "3930", "notify": "true", "fontType": "3"}))
    if have:
        lines.append(emit_rule(f"{IRONMAN} && {_id_list(have)}",
            {"textColor": "#66d8b01a", "fontType": "1"}))   # quiet, no beam
    if hide:
        lines.append(emit_rule(f"{IRONMAN} && HIDE_OWNED && {_id_list(hide)}", {"hidden": "true"}, terminal=False))
    return emit_module("tailoring", "Account tailoring", "\n".join(lines))
