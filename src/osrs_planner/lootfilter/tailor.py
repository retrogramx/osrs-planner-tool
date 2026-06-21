# src/osrs_planner/lootfilter/tailor.py
"""Account tailoring (design §9): beam the collection-log slots you still NEED, dim
the ones you HAVE, optionally hide what you bank. Consumes an already-built
AccountState (counts + clog_obtained); never calls the ingestion itself. The caller
supplies the clog id-set (generate.load_clog_ids)."""
from __future__ import annotations

from osrs_planner.lootfilter.emit import emit_module, emit_rule, emit_style_input, IRONMAN, _id_list

_HIGH_VALUE = 100_000  # A grade -> never hide an owned item worth this much
# Collection-log purple ("a purple!") -- the OSRS rare-unique colour. Distinct from coin gold so a
# new clog slot reads as the special moment it is, not a coin pile.
_CLOG = "#ffc23cf0"

def _ids(keys) -> set[int]:
    return {int(k.split(":")[1]) for k in keys}

def _missing_style(border: str, font: str, beam: bool) -> dict:
    """A purple missing-clog panel; ULTRA/RARE add the loot beam + sound + notify, COMMON is panel-only."""
    s = {"hidden": "false", "textColor": "#fff5f5f5", "backgroundColor": _CLOG, "borderColor": border,
         "fontType": font, "textAccent": "3", "icon": "CurrentItem()"}
    if beam:
        s.update({"showLootbeam": "true", "lootbeamColor": _CLOG, "sound": "3930", "notify": "true"})
    return s

def emit_tailoring(account_state, clog_ids, value_index=None, rarity_index=None) -> str:
    if account_state is None:
        return emit_module("tailoring", "Account tailoring", "")
    clog = set(clog_ids)
    obtained = _ids(account_state.clog_obtained)
    owned = _ids(account_state.counts)
    missing = clog - obtained
    have = sorted(clog & obtained)
    value_index = value_index or {}
    rarity_index = rarity_index or {}
    hide = sorted(i for i in owned if i not in clog and value_index.get(i, 0) < _HIGH_VALUE)
    # split missing slots by rarity so common ones don't beam-spam (ULTRA/RARE beam, COMMON panels)
    ultra = sorted(i for i in missing if rarity_index.get(i) == "ULTRA")
    common = sorted(i for i in missing if rarity_index.get(i) == "COMMON")
    rare = sorted(i for i in missing if rarity_index.get(i, "RARE") not in ("ULTRA", "COMMON"))
    lines = ['/*@ define:input:tailoring\nlabel: Hide items already in my bank\ntype: boolean\ngroup: Tailor\n*/\n#define HIDE_OWNED false']
    # Clog signature = purple panel + a GOLD border (no category/coin ever has a gold border, so the
    # combo is unmistakably clog); ULTRA keeps a RED border so the rarest still pops hardest.
    if ultra:   # rarest slots: bold + RED-bordered purple + beam + sound + notify (editable picker)
        lines.append(emit_style_input("tailoring", "Missing clog -- ULTRA (rarest)", "Collection log", "CLOG_ULTRA",
            f"{IRONMAN} && {_id_list(ultra)}", _missing_style("#ffff2b2b", "3", True)))
    if rare:    # rare / clue / pet / minigame slots: gold-bordered purple + beam + sound + notify
        lines.append(emit_style_input("tailoring", "Missing clog -- rare", "Collection log", "CLOG_RARE",
            f"{IRONMAN} && {_id_list(rare)}", _missing_style("#ffffd700", "2", True)))
    if common:  # common slots: gold-bordered purple PANEL only, no beam/sound (cuts the spam)
        lines.append(emit_style_input("tailoring", "Missing clog -- common", "Collection log", "CLOG_COMMON",
            f"{IRONMAN} && {_id_list(common)}", _missing_style("#ffffd700", "1", False)))
    if have:    # obtained clog: a quiet bronze "collection" panel (still clearly visible) -- NO beam
        lines.append(emit_style_input("tailoring", "Obtained clog", "Collection log", "CLOG_HAVE",
            f"{IRONMAN} && {_id_list(have)}",
            {"backgroundColor": "#ffbc6025", "borderColor": "#ff7a3f18", "textColor": "#fff5f5f5",
             "fontType": "1", "textAccent": "3", "icon": "CurrentItem()"}))
    if hide:
        lines.append(emit_rule(f"{IRONMAN} && HIDE_OWNED && {_id_list(hide)}", {"hidden": "true"}, terminal=False))
    return emit_module("tailoring", "Account tailoring", "\n".join(lines), "Beam missing slots, dim owned")
