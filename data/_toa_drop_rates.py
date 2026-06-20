# data/_toa_drop_rates.py
"""Tombs of Amascut (ToA) invocation/points deep-dive (spec §7).

WHY THIS MODULE EXISTS
----------------------
ToA unique drops do NOT have a single fixed 1/N. The per-player chance of *any*
unique is a formula of the **scaled raid level** (set by Invocations) and the
player's **total reward points**; the flat `n/24` fraction that dropsline reports
is only the *conditional* split — i.e. WHICH unique you get, GIVEN that a purple
was already rolled. So a ToA record needs an explicit disclosure that its numeric
`drop_rate` is invocation-canonical (the weighting), not the end-to-end chance.

dropsline reality (verified live 2026-06-19 against the committed full cache):
every ToA unique is a SINGLE flat row `"Dropped from": "Chest (Tombs of Amascut)"`
with `"Rarity"` already a clean fraction (Osmumten's fang / Lightbearer `7/24`,
Elidinis' ward `3/24`, Masori mask/body/chaps `2/24`, Tumeken's shadow `1/24`).
Those are already parsed to a numeric `sourced` drop_rate upstream, so apply_toa
does NOT rescue a null and does NOT overwrite the number — it ATTACHES an
invocation-scaling disclosure to `variants[]` (honest, additive). The end-to-end
points/raid-level formula itself is NOT exposed by dropsline, so it is
self-sourced here from the ToA wiki, pinned verbatim with source URLs below.

SOURCES (pinned; do not edit values from memory):
- Chest (Tombs of Amascut) — unique mechanic + weighting table (current/live):
  https://oldschool.runescape.wiki/w/Chest_(Tombs_of_Amascut)#Uniques
- Original mechanics announcement (points system, 55% cap, weightings):
  https://oldschool.runescape.wiki/w/Update:Tombs_of_Amascut_Drop_Mechanics_%26_Osmumten%27s_Fang
- Raw wikitext fetched via action=parse&prop=wikitext on 2026-06-19 (User-Agent
  per wiki API rules); fractions cross-checked against the committed dropsline cache.

PINNED FORMULA (verbatim from the Chest wikitext, "===Uniques===" section):
  "Players will have a 1% chance to receive a unique item for every
   (10,500 - 20 * RL) total reward points, where RL is a scaled raid level":

      P(any unique) = points / (10,500 - 20 * RL)          # a probability, then
      P(any unique) = min(P(any unique), 0.55)             # capped at 55%

  RL (scaled raid level) is piecewise in the chosen Invocation RaidLevel:
      RL = RaidLevel                              if RaidLevel <= 310
      RL = 310 + (RaidLevel - 310) / 3            if 310 < RaidLevel <= 430
      RL = 350 + (RaidLevel - 430) / 6            if RaidLevel > 430
  Wiki worked example: at RaidLevel 400,
      10,500 - 20 * (310 + 90/3) = 3,700  -> 1% per 3,700 points.

POINTS (same source): start 5,000; room cap 20,000; total cap 64,000 per player.
At the 64,000 total-points cap and RaidLevel 400 the chance is
64,000 / 3,700 ≈ 17.3% (then 55%-capped) — i.e. the `n/24` weighting is NOT the
chance of obtaining the item; it only selects which unique once a purple lands.

PER-UNIQUE WEIGHTING (the dropsline `n/24` fractions; the conditional split chosen
when a purple is rolled — sum = 24). Between RaidLevel 305 and 500 the wiki notes
the Fang/Lightbearer weightings shift down relative to the others; the base table:
"""
from __future__ import annotations

# The ToA chest label dropsline uses for every ToA drop (the source-resolution key).
TOA_CHEST = "Chest (Tombs of Amascut)"

# 1% unique chance per this many total reward points, at a reference RaidLevel.
# Kept as a documented reference (RaidLevel 400 -> denom 3,700) for the disclosure
# text only; NEVER written into a record's numeric drop_rate (no fabrication).
_REF_RAID_LEVEL = 400
_REF_POINTS_PER_PERCENT = 3700  # 10,500 - 20 * (310 + (400-310)/3)
UNIQUE_CHANCE_CAP = 0.55        # max P(any unique) per raid (like CoX ancient chest)

# Per-unique weighting out of 24 (the dropsline conditional split). Keyed by the
# exact collection-log / dropsline item name. Pinned from Chest(ToA)#Uniques.
TOA_UNIQUES: dict[str, dict] = {
    "Osmumten's fang":              {"weight": 7, "weight_raw": "7/24"},
    "Lightbearer":                  {"weight": 7, "weight_raw": "7/24"},
    "Elidinis' ward":               {"weight": 3, "weight_raw": "3/24"},
    "Masori mask":                  {"weight": 2, "weight_raw": "2/24"},
    "Masori body":                  {"weight": 2, "weight_raw": "2/24"},
    "Masori chaps":                 {"weight": 2, "weight_raw": "2/24"},
    "Tumeken's shadow (uncharged)": {"weight": 1, "weight_raw": "1/24"},
}

# The disclosure condition string. Contains the word "invocation" (the mechanic's
# in-game name) so consumers/tests can detect ToA scaling, and states plainly that
# the numeric n/24 is the which-unique split, not the end-to-end acquisition rate.
_DISCLOSURE_CONDITION = (
    "invocation/points scaling: dropsline n/24 is the conditional which-unique "
    "weighting once a purple rolls, NOT the acquisition chance. "
    "P(any unique) = points / (10,500 - 20*RL), capped at 55% "
    "(RL = scaled raid level; e.g. RaidLevel 400 -> 1% per 3,700 points). "
    "See https://oldschool.runescape.wiki/w/Chest_(Tombs_of_Amascut)#Uniques"
)


def _already_disclosed(record) -> bool:
    """True if the invocation disclosure is already on this record (idempotency)."""
    for v in record.get("variants", []):
        if "invocation" in str(v.get("condition", "")).lower():
            return True
    return False


def apply_toa(record: dict) -> dict:
    """ATTACH the ToA invocation-scaling disclosure to a record sourced from the
    ToA chest. No-op (returns the record unchanged) for every other source.

    For a ToA record it does NOT overwrite drop_rate / drop_rate_raw (the flat
    n/24 weighting from dropsline is a real reference number and stays); it APPENDS
    one disclosure variant whose drop_rate is None (the end-to-end chance is a
    points/raid-level formula, not a single number — emitting one would fabricate).
    Idempotent: re-running the builder does not duplicate the disclosure."""
    if record.get("source") != TOA_CHEST:
        return record
    if _already_disclosed(record):
        return record
    record = dict(record)
    record["variants"] = list(record.get("variants", [])) + [
        {"condition": _DISCLOSURE_CONDITION, "drop_rate": None, "drop_rate_raw": ""}
    ]
    return record
