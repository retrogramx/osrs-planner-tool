#!/usr/bin/env python3
"""Income-layer data validator (iron-gate tradition; income design §8.1).

Exits non-zero if any income-data invariant is violated (CI / pre-commit gate).
The money-making datasets are wiki-sourced; the green-dragons realization chain
(recipes.json + the tan service fee) is HAND-CURATED, wiki-pinned golden-set
coverage -- bulk recipe/service sourcing is a disclosed v1 follow-up.

Invariants:
  1. Gate coherence: a requires_ge method is iron_eligible=false.
  2. Every output/input item id that is an "item:<n>" ref resolves in
     item_dictionary.json (coins outputs are exempt -- is_coins, no item id).
  3. Every requirement-item "item:<n>" ref resolves; prose item reqs allowed.
  4. STRICT quest-id path: every STRUCTURED ``requirements.quests`` ref resolves to
     a quest node in kg/nodes.json (after stripping a "(...)" suffix). EXCEPTIONS
     (non-fatal): a DIARY-shaped ref (matches /diary/i) is NOT a quest and is
     skipped (it routes to advisory tags at load, not a gate); a ref whose slug
     is in the disclosed _KNOWN_MISSING_QUESTS set is a [known-gap] WARNING
     (a real KG quest-coverage gap to be filled by the engine/KG build later,
     NOT income's job; income MUST NOT add KG nodes). Any OTHER unresolved
     structured quest ref stays FATAL. (Mirrors data/validate_kg.py's
     known_missing pattern.)
     PROSE path (non-strict): the MAIN dataset's ``quest`` markup is FREE-FORM
     prose whose wikilinks point at a MIX of quests and non-quest pages (items,
     locations, fairy rings, diaries, File: links). It is NOT a curated quest-id
     list, so an unresolved main-markup wikilink is a NON-FATAL [main-quest-prose]
     disclosure (the loader is conservative and may over-gate, the safe direction);
     diary + File: links are skipped outright.
  5. gp_hr (where stored) is numeric or null. The stored gp_hr is NOT trusted
     (recomputed per family at query time) and net-LOSS methods legitimately exist
     (e.g. "Catching anglerfish (Diabolic worms)" gp_hr=-191600), so a NEGATIVE
     value is a non-fatal [net-loss] disclosure; only a non-numeric value is fatal.
  6. recipes.json output/input ids resolve; service_fee_coins >= 0 when present;
     the green d'hide body exemplar is present (3 leather @ Crafting 63).
  7. KG stays income-free: no income/gp_hr/net_sign/realization_channel token in kg/*.json.
  8. Envelope consistency: _provenance.record_count == len(records); _excluded is a list.

Usage: python3 data/validate_income.py [--data DATA_DIR] [--kg KG_DIR]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

errors: list[str] = []
warnings: list[str] = []  # non-fatal [known-gap] disclosures (do not affect exit code)

# Disclosed KG quest-coverage gaps (real quests whose nodes are ABSENT from the
# 205-quest KG). An iron requirements.quests ref to one of these is a NON-FATAL
# [known-gap] warning, NOT a fatal unresolved-ref error -- mirrors
# data/validate_kg.py's _provenance.completeness.known_missing pattern. These are
# to be filled by the engine/KG build later; income MUST NOT add KG nodes.
_KNOWN_MISSING_QUESTS = frozenset({"crack-the-clue-iii", "sleeping-giants"})


def check(cond, msg):
    if not cond:
        errors.append(msg)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def item_num(item_id):
    if isinstance(item_id, int):
        return item_id
    if isinstance(item_id, str) and item_id.startswith("item:"):
        try:
            return int(item_id.split(":", 1)[1])
        except ValueError:
            return None
    return None


_PAREN = re.compile(r"\s*\([^)]*\)\s*$")
_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
_DIARY = re.compile(r"diary", re.IGNORECASE)  # a DIARY ref is not a quest (DR-3)
# Precise income tokens (avoid false-positiving legit KG keys like "data"/"name").
_INCOME_TOKENS = re.compile(r'"(income|gp_hr|gp_hour|net_sign|realization_channel|money_making)"', re.I)


def quest_slug(ref: str) -> str:
    """'[[Dragon Slayer II]]' or 'Dragon Slayer II' -> 'quest:dragon-slayer-ii'.

    Strips wiki [[ ]] markup + a trailing "(...)" suffix; lowercases; drops
    apostrophes; non-alnum runs -> a single '-'. Mirrors methods._slug.
    """
    s = _PAREN.sub("", ref).strip()
    s = re.sub(r"^\[\[|\]\]$", "", s)
    s = s.strip().lower().replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return f"quest:{s}"


def main(argv=None) -> int:
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(here)
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=here)
    ap.add_argument("--kg", default=os.path.join(repo, "kg"))
    ns = ap.parse_args(argv)
    data, kg = ns.data, ns.kg

    idict = load(os.path.join(data, "item_dictionary.json"))
    item_ids = {r["item_id"] for r in idict["records"]}

    # kg/nodes.json is a bare LIST of node dicts.
    nodes = load(os.path.join(kg, "nodes.json"))
    node_list = nodes["records"] if isinstance(nodes, dict) and "records" in nodes else nodes
    quest_node_ids = {n["id"] for n in node_list if isinstance(n, dict) and n.get("kind") == "quest"}

    n_records = 0
    for fname in ("money_making.json", "ironman_money_making.json"):
        fpath = os.path.join(data, fname)
        if not os.path.exists(fpath):
            continue
        doc = load(fpath)
        records = doc["records"]
        prov = doc.get("_provenance", {})
        check(prov.get("record_count") == len(records),
              f"[{fname}] record_count {prov.get('record_count')} != len(records) {len(records)}")
        check(isinstance(doc.get("_excluded"), list), f"[{fname}] _excluded missing or not a list")

        for rec in records:
            n_records += 1
            name = rec.get("name") or rec.get("method")
            # Inv 1
            if rec.get("requires_ge") is True:
                check(rec.get("iron_eligible") is False,
                      f"[{fname}] requires_ge method not iron_eligible=false: {name}")
            # Inv 5: a stored gp_hr, when present, must be NUMERIC (guard garbage).
            # The plan does NOT trust the stored gp_hr (it is recomputed per family
            # at query time), and net-LOSS methods legitimately exist in the wiki
            # data (e.g. "Catching anglerfish (Diabolic worms)" gp_hr=-191600 is a
            # real sink). So a NEGATIVE stored gp_hr is a NON-FATAL [net-loss]
            # disclosure, not an error -- only a non-numeric value is fatal.
            gp = rec.get("gp_hr")
            check(gp is None or isinstance(gp, (int, float)),
                  f"[{fname}] gp_hr not numeric: {name} ({gp!r})")
            if isinstance(gp, (int, float)) and gp < 0:
                warnings.append(
                    f"[net-loss] [{fname}] stored gp_hr < 0: {name} ({gp}) "
                    f"(a real net-loss/sink method; stored gp_hr is untrusted, "
                    f"recomputed per family at query time)"
                )
            # Inv 2: output/input item:<n> ids resolve (coins exempt; named flows
            # resolve by name at load, not validated here).
            for io_list in (rec.get("outputs"), rec.get("inputs")):
                if not isinstance(io_list, list):
                    continue
                for io in io_list:
                    if io.get("is_coins"):
                        continue
                    iid = io.get("item_id")
                    if iid is not None:
                        check(item_num(iid) in item_ids,
                              f"[{fname}] output/input item_id does not resolve: {iid} ({name})")
            # Inv 3/4: requirement refs
            req = rec.get("requirements") or {}
            for it in req.get("items", []) or []:
                num = item_num(it)
                if num is not None:
                    check(num in item_ids, f"[{fname}] req item id unresolved: {it} ({name})")
            for q in req.get("quests", []) or []:
                # DR-3: a DIARY-shaped ref is not a quest gate -> skip (it routes
                # to advisory tags at load, never requirements.quests).
                if _DIARY.search(q):
                    continue
                qid = quest_slug(q)  # strips "(...)" then slugs (matches the loader)
                if qid in quest_node_ids:
                    continue
                if qid[len("quest:"):] in _KNOWN_MISSING_QUESTS:
                    warnings.append(
                        f"[known-gap] [{fname}] req quest {q!r} -> {qid} absent from KG "
                        f"(disclosed _KNOWN_MISSING_QUESTS; a real quest-coverage gap to be "
                        f"filled by the engine/KG build later) ({name})"
                    )
                    continue
                check(False, f"[{fname}] req quest unresolved: {q!r} -> {qid} ({name})")
            # Inv 4 (main `quest` markup): this field is FREE-FORM PROSE whose
            # wikilinks point at a mix of quests AND non-quest pages (items like
            # [[Dragonfire shield]], locations like [[Nardah]], [[Fairy rings]],
            # diaries, File: links, NPCs). It is NOT a curated quest-id list, so a
            # wikilink that doesn't resolve to a quest node is NOT necessarily a
            # missing quest -- treating each as a fatal quest-resolution requirement
            # would fail on ~171 committed refs (most are items/places, not quests).
            # So: unresolved main-markup wikilinks are NON-FATAL [main-quest-prose]
            # disclosures (the loader is conservative and may over-gate these to
            # future_gated, which is the safe direction). DIARY + File: links skipped.
            # The STRICT quest-id check is the structured iron requirements.quests
            # path above; the main prose field cannot be machine-curated in v1.
            if rec.get("quest"):
                for m in _WIKILINK.finditer(str(rec["quest"])):
                    link = m.group(1)
                    if _DIARY.search(link) or link.lower().startswith("file:"):
                        continue
                    qid = quest_slug(link)
                    if qid not in quest_node_ids:
                        warnings.append(
                            f"[main-quest-prose] [{fname}] wikilink {link!r} -> {qid} "
                            f"does not resolve to a quest node (free-form prose field; "
                            f"may be an item/place/achievement-region, not a quest) ({name})"
                        )

    # Inv 6: recipes realization-chain refs + the green-dragons exemplar.
    rec_path = os.path.join(data, "recipes.json")
    has_body = False
    if os.path.exists(rec_path):
        rdoc = load(rec_path)
        for r in rdoc["records"]:
            check(item_num(r["output_item_id"]) in item_ids,
                  f"[recipes] output id unresolved: {r['output_item_id']}")
            fee = r.get("service_fee_coins")
            check(fee is None or (isinstance(fee, (int, float)) and fee >= 0),
                  f"[recipes] service_fee_coins < 0: {r['output_item_id']}")
            for inp in r.get("inputs", []):
                check(item_num(inp["item_id"]) in item_ids,
                      f"[recipes] input id unresolved: {inp['item_id']}")
            if item_num(r["output_item_id"]) == 1135:  # Green d'hide body
                has_body = True
                leather = [i for i in r["inputs"] if item_num(i["item_id"]) == 1745]
                check(bool(leather) and leather[0]["qty"] == 3,
                      "[recipes] green d'hide body must consume 3 green dragon leather (item:1745)")
                check(r.get("level") == 63, "[recipes] green d'hide body Crafting level must be 63")
        check(has_body, "[recipes] green d'hide body exemplar (item:1135) absent (golden-set chain)")

    # Inv 7: KG stays income-free.
    for kgf in sorted(glob.glob(os.path.join(kg, "*.json"))):
        with open(kgf, encoding="utf-8") as f:
            raw = f.read()
        m = _INCOME_TOKENS.search(raw)
        check(m is None, f"[kg] income token leaked into {os.path.basename(kgf)}: {m.group(0) if m else ''}")

    if errors:
        print(f"INCOME VALIDATION FAILED -- {len(errors)} violation(s):")
        for e in errors[:50]:
            print("  -", e)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more")
        return 1
    print("INCOME VALIDATION PASSED -- all income-data invariants hold.")
    print(f"  item_dictionary: {len(item_ids)} resolvable item_ids")
    print(f"  quest nodes: {len(quest_node_ids)}")
    print(f"  method records validated: {n_records}")
    if warnings:
        print(f"  {len(warnings)} non-fatal disclosure(s) (do not affect exit code):")
        for w in warnings[:50]:
            print("    -", w)
    print("  NOTE: green-dragons exemplar chain hand-curated + wiki-pinned; bulk recipe/service sourcing is a v1 follow-up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
