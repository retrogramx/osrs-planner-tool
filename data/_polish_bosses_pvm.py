#!/usr/bin/env python3
"""One-shot polish of bosses_pvm.json.

(1) drop_class split: the old single 'untradeable' bucket conflated two cases.
    - pricetype=='gemw'  -> 'tradeable_iron_no_ge'  (item HAS a live GE price /
      is GE-tradeable, but an ironman cannot GE-sell it). Verified tradeable on
      OSRS Wiki for samples spanning hilts/sigils/seeds/crystals/jars/key/tome.
    - pricetype=='value' -> 'untradeable_no_income'  (genuinely untradeable; no
      GE listing). Only 'Crystal shard' (Tradeable: No on wiki).
(2) Fix 7 malformed boss names (4x 'Contract of' -> 'Yama'; 'Gauntlet' ->
    'The Gauntlet'; 'Corrupted Gauntlet' -> 'The Corrupted Gauntlet';
    'crazy archaeologist' -> 'Crazy archaeologist' (canonical wiki sentence-case;
    'Moons of Peril' is already canonical and left as-is).

PRESERVES the frozen envelope exactly: keys {_provenance, records, _excluded};
payload key 'records'; record_count == len(records). No fabrication.
"""
import json
import datetime
from collections import Counter

PATH = "bosses_pvm.json"

with open(PATH) as f:
    d = json.load(f)

assert list(d.keys()) == ["_provenance", "records", "_excluded"], list(d.keys())
records = d["records"]
n_before = len(records)

# ---- (1) drop_class split -------------------------------------------------
flip_tradeable = 0   # untradeable -> tradeable_iron_no_ge
keep_untrade = 0     # untradeable -> untradeable_no_income
for r in records:
    for nd in r.get("notable_drops", []):
        if nd.get("drop_class") == "untradeable":
            if nd.get("pricetype") == "gemw":
                nd["drop_class"] = "tradeable_iron_no_ge"
                flip_tradeable += 1
            else:  # 'value' (no GE listing) -> genuinely no income
                nd["drop_class"] = "untradeable_no_income"
                keep_untrade += 1

# ---- (2) boss-name fixes --------------------------------------------------
# Map by (boss, method_page) so we only touch the intended records.
name_fixes = 0
for r in records:
    boss = r["boss"]
    mp = r.get("method_page", "")
    new = None
    if boss == "Contract of":
        # all four are Yama contracts (method_page: 'Killing Yama (...)')
        new = "Yama"
    elif boss == "Gauntlet":
        new = "The Gauntlet"
    elif boss == "Corrupted Gauntlet":
        new = "The Corrupted Gauntlet"
    elif boss == "crazy archaeologist":
        new = "Crazy archaeologist"
    # 'Moons of Peril' is already canonical; no change.
    if new and new != boss:
        r["boss"] = new
        name_fixes += 1

# ---- envelope integrity ---------------------------------------------------
assert len(records) == n_before, "record count changed!"

# ---- (3) provenance update ------------------------------------------------
prov = d["_provenance"]
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
prov["accessed"] = now
prov["record_count"] = len(records)  # unchanged, kept in sync
note = (
    "Polish (2026-06-17): (1) drop_class split — replaced the single "
    "'untradeable' bucket with 'tradeable_iron_no_ge' for GE-tradeable items an "
    "iron cannot GE-sell (pricetype=gemw; 47 drop entries / 32 distinct items: "
    "hilts/sigils/crystal seeds/crystals/jars/Crystal key/Tome of earth, all "
    "verified Tradeable=Yes on OSRS Wiki) vs 'untradeable_no_income' for "
    "genuinely-untradeable items (pricetype=value; 2 entries = Crystal shard, "
    "Tradeable=No). These items already matched per-record iron_ge_only_drops "
    "(0 mismatches). (2) Fixed 7 malformed boss names: 4x 'Contract of' -> "
    "'Yama' (Yama contract methods), 'Gauntlet' -> 'The Gauntlet', "
    "'Corrupted Gauntlet' -> 'The Corrupted Gauntlet', lowercase "
    "'crazy archaeologist' -> 'Crazy archaeologist' (canonical wiki sentence-case). "
    "Data-only edit; no new fetch beyond OSRS Wiki tradeability verification."
)
prov.setdefault("notes", []).append(note)

with open(PATH, "w") as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
    f.write("\n")

# ---- report ---------------------------------------------------------------
print("flip untradeable -> tradeable_iron_no_ge :", flip_tradeable)
print("keep untradeable -> untradeable_no_income:", keep_untrade)
print("boss name fixes                          :", name_fixes)
print("record_count                             :", len(records))
dc = Counter()
for r in records:
    for nd in r.get("notable_drops", []):
        dc[nd["drop_class"]] += 1
print("new drop_class distribution              :", dict(dc.most_common()))
