#!/usr/bin/env python3
"""Structural validator for the GENERIC loot filter (design §12): balanced braces +
block comments, colours are 8-hex ARGB, IRON-gating (every rule( and every settings/
trophy apply( references IRONMAN), trophy ids resolve, module order, hide-floor default 0."""
from __future__ import annotations
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
errors = []
def check(c, m):
    if not c: errors.append(m)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--filter", default=os.path.join(REPO, "outputs", "gilded-tome-iron.rs2f"))
    ap.add_argument("--data", default=os.path.join(REPO, "data"))
    ns = ap.parse_args()
    text = open(ns.filter, encoding="utf-8").read()

    check(text.count("{") == text.count("}"), "unbalanced braces")
    check(text.count("/*") == text.count("*/"), "unbalanced block comments")
    for col in re.findall(r'"(#[0-9a-fA-F]+)"', text):
        check(len(col) == 9, f"colour not 8-hex ARGB: {col}")
    check("#define IRONMAN accountType:1" in text, "IRONMAN macro not defined")
    check(text.count("rule (IRONMAN") == text.count("rule ("), "a rule( is not IRONMAN-gated")
    check(text.count("apply (IRONMAN") == text.count("apply ("), "an apply( is not IRONMAN-gated")
    check("#define HIDE_FLOOR 0" in text, "HIDE_FLOOR default not 0 (would hide by default)")
    # every macro referenced in a condition is #defined; no empty conditions/bodies
    defined = set(re.findall(r"#define (\w+)", text))
    referenced = set()
    for c in re.findall(r"(?:rule|apply) \(([^)]*)\)", text):
        referenced |= set(re.findall(r"\b([A-Z][A-Z0-9_]{2,})\b", c))
    check(not (referenced - defined), f"macro(s) referenced but not defined: {sorted(referenced - defined)[:10]}")
    check(not re.search(r"(?:rule|apply) \(\)", text), "a rule/apply has an empty condition")
    check(not re.search(r"\)\s*\{\s*\}", text), "a rule/apply has an empty body")
    order = ["module:settings", "module:trophies", "module:categories", "module:fallback"]
    idxs = [text.find(m) for m in order]
    check(all(i >= 0 for i in idxs) and idxs == sorted(idxs), f"modules missing/out of order: {idxs}")
    idict = {r["item_id"] for r in json.load(open(os.path.join(ns.data, "item_dictionary.json"), encoding="utf-8"))["records"]}
    clog = {r["item_id"] for r in json.load(open(os.path.join(ns.data, "collection_log.json"), encoding="utf-8"))["records"]}
    for m in re.findall(r"id:\[([0-9, ]+)\]", text):
        for tok in m.split(","):
            iid = int(tok); check(iid in idict or iid in clog, f"trophy id unresolved: {iid}")
    if errors:
        print(f"LOOT-FILTER VALIDATION FAILED -- {len(errors)} violation(s):")
        for e in errors[:50]: print("  -", e)
        return 1
    print(f"LOOT-FILTER VALIDATION PASSED -- rules {text.count('rule (')}, bytes {len(text)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
