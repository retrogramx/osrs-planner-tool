#!/usr/bin/env python3
"""Iron-gate validator — the durable guard for account-type economic correctness.

Exits non-zero if any invariant is violated, so it can run in CI / pre-commit to
stop the two leak classes PR #3's review caught from ever regressing:

  Leak 1 (money_making): a GE buy-process-sell / flipping method must never be
          presented as iron-eligible. Detected GENERALLY (not via a skill
          allow-list): a processing/conversion method (incl. Magic, and
          skillcategory=None resolved via the skill requirement) that buys a
          GE-priced material is GE-arbitrage.
  Leak 2 (bosses_pvm): an EQUIPPABLE tradeable item (joined against
          items_equipment.json) that is GE-priced must never be counted as
          iron-realizable income — an iron cannot GE-sell worn gear.

Plus a structural check: the four account-gate fields
{audience, pricing_basis, realization_channel, requires_ge} are present on every
record across the five money/economy domains.

Usage:  python3 data/validate_iron_gate.py
"""
import json
import os
import re
import sys

DATA = os.path.dirname(os.path.abspath(__file__))
errors = []


def load(name):
    with open(os.path.join(DATA, name)) as f:
        return json.load(f)


def check(cond, msg):
    if not cond:
        errors.append(msg)


GATE_FIELDS = ("audience", "pricing_basis", "realization_channel", "requires_ge")
# mirror data/build_money_making.py
PROC_SKILLS = {"Crafting", "Fletching", "Cooking", "Smithing", "Herblore", "Firemaking", "Magic"}
GATHER_SKILLS = {"Mining", "Fishing", "Woodcutting", "Hunter", "Thieving",
                 "Runecraft", "Agility", "Farming", "Sailing", "Slayer"}
PROCESSING_CATS = {"Processing", "Processing (Sapling)", "Cooking (Brewing)"}


def has_gemw_input(j):
    return any(
        i.get("pricetype") == "gemw" and (i.get("name", "").lower() != "coins")
        and float(i.get("value") or 0) > 0
        for i in (j.get("inputs") or [])
    )


def is_processing_method(j):
    if j.get("category") != "Skilling":
        return False
    sc = j.get("skillcategory")
    if sc in PROC_SKILLS:
        return True
    if sc is None:
        req = set(re.findall(r'data-skill="([^"]+)"', str(j.get("skill") or "")))
        return bool(req & PROC_SKILLS) and not (req & GATHER_SKILLS)
    return False


def requires_ge(j, page=""):
    act = (j.get("activity") or "").lower()
    if "flip" in act or "flipping" in (page or "").lower():
        return True
    if j.get("category") in PROCESSING_CATS:
        return True
    return bool(is_processing_method(j) and has_gemw_input(j))


# --- Leak 1: money_making ---------------------------------------------------
mm = load("money_making.json")
for r in mm["records"]:
    name = r.get("name", "?")
    check(r.get("requires_ge") is False, f"[money_making] record requires_ge!=False: {name}")
    check(r.get("iron_eligible") is True, f"[money_making] record not iron_eligible: {name}")
    # general GE-arbitrage detection (re-derive from raw_json; catches Magic/None-skill escapes)
    if requires_ge(r.get("raw_json") or {}, r.get("page_name", "")):
        check(False, f"[money_making] GE buy-process-sell method leaked as iron-eligible: {name}")
for r in mm["_excluded"]:
    check(r.get("requires_ge") is True, f"[money_making] _excluded entry without requires_ge=True: {r.get('name')}")

# --- Leak 2: bosses_pvm (join against items_equipment) ----------------------
try:
    ie = load("items_equipment.json")
    EQUIPPABLE = {(r.get("item") or "").strip().lower() for r in ie.get("records", []) if r.get("item")}
except (OSError, ValueError):
    EQUIPPABLE = set()
check(len(EQUIPPABLE) > 1000, f"[bosses_pvm] items_equipment join set too small ({len(EQUIPPABLE)}) — cannot validate Leak 2")
GEAR_HINT = re.compile(r"\b(ring|amulet|necklace|bracelet)\b|whip|tentacle|\bfangs?\b|\bclaws?\b|seercull", re.I)

bp = load("bosses_pvm.json")
for r in bp["records"]:
    boss = r.get("boss", "?")
    for nd in r.get("notable_drops", []):
        nm = nd.get("name", "")
        is_gear = nm.strip().lower() in EQUIPPABLE or bool(GEAR_HINT.search(nm))
        if is_gear and nd.get("pricetype") == "gemw":
            check(nd.get("iron_realizable") is False,
                  f"[bosses_pvm] equippable GE-priced gear counted as iron income: {boss}/{nm} (={nd.get('value_each')})")
hi = {"Berserker ring", "Archers ring", "Seers ring"}
leak = [(r["boss"], nd["name"]) for r in bp["records"] for nd in r.get("notable_drops", [])
        if nd.get("name") in hi and nd.get("iron_realizable")]
check(not leak, f"[bosses_pvm] expensive rings counted as iron income: {leak}")

# --- Structural: gate fields present across the 5 money/economy domains ------
for dom in ("money_making", "bosses_pvm", "ironman_money_making", "account_cost_split", "skills_training"):
    d = load(dom + ".json")
    for f in GATE_FIELDS:
        n_missing = sum(1 for r in d["records"] if f not in r)
        check(n_missing == 0, f"[{dom}] {n_missing} record(s) missing gate field '{f}'")

# --- report -----------------------------------------------------------------
if errors:
    print(f"IRON-GATE VALIDATION FAILED — {len(errors)} violation(s):")
    for e in errors[:50]:
        print("  -", e)
    if len(errors) > 50:
        print(f"  ... and {len(errors) - 50} more")
    sys.exit(1)
print("IRON-GATE VALIDATION PASSED — all account-type economic invariants hold.")
print(f"  money_making: {len(mm['records'])} iron-eligible records, {len(mm['_excluded'])} GE-gated")
print(f"  bosses_pvm:   {sum(len(r['notable_drops']) for r in bp['records'])} drops across {len(bp['records'])} methods")
print(f"  items_equipment join: {len(EQUIPPABLE)} equippable names")
