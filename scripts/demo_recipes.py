#!/usr/bin/env python3
"""Live showcase of the recipe layer over the REAL committed knowledge graph.

Nothing is mocked: every answer is traversed from kg/*.json, and the "can MY
account make it" verdict comes from the actual account-aware three-valued
evaluator (src/osrs_planner/engine). Run: ./venv/bin/python scripts/demo_recipes.py
"""
from __future__ import annotations
import pathlib, sys
from collections import Counter

from osrs_planner.engine.kg.json_store import JsonKGStore
from osrs_planner.engine.kg.model import EdgeType
from osrs_planner.engine.conditions import evaluate
from osrs_planner.engine.state import AccountState
from osrs_planner.engine.kleene import Tri

KG_DIR = str(pathlib.Path(__file__).resolve().parents[1] / "kg")
kg = JsonKGStore.from_dir(KG_DIR)
_C = sys.stdout.isatty()
def c(code, s): return f"\033[{code}m{s}\033[0m" if _C else s
def hr(t): print("\n" + "═" * 78 + f"\n  {t}\n" + "═" * 78)
def name(nid):
    n = kg.node(nid); return n.name if n else nid

# --- indexes over the committed graph ---
produces = {}        # item id -> [recipe id]
consumes = {}        # recipe id -> [(item id, qty, role)]
facility_of = {}     # recipe id -> [facility id]
skillgate = {}       # recipe id -> cond_group id (requires)
made_at = {}         # facility id -> [recipe id]
for e in kg.edges:
    if e.type is EdgeType.PRODUCES:
        produces.setdefault(e.dst, []).append(e.src)
    elif e.type is EdgeType.CONSUMES:
        consumes.setdefault(e.src, []).append((e.dst, e.data.get("qty"), e.data.get("role")))
    elif e.type is EdgeType.REQUIRES_FACILITY:
        facility_of.setdefault(e.src, []).append(e.dst)
        made_at.setdefault(e.dst, []).append(e.src)
    elif e.type is EdgeType.REQUIRES and e.src.startswith("recipe:"):
        skillgate[e.src] = e.cond_group

def item_by_name(nm):
    for n in kg.nodes.values():
        if n.id.startswith("item:") and n.name == nm:
            return n.id
    return None

def recipe_for(item_id):
    """Pick one recipe producing item_id, preferring a facility-based method."""
    rs = produces.get(item_id, [])
    rs = sorted(rs, key=lambda r: (0 if facility_of.get(r) else 1, r))
    return rs[0] if rs else None

def gate_str(rid):
    g = skillgate.get(rid)
    if not g: return ""
    parts = []
    for ch in kg.children_of(g):
        if getattr(ch, "atom_type", None) and ch.atom_type.value == "skill_level":
            parts.append(f"{name(ch.ref_node)} {ch.threshold}")
    return " + ".join(parts)


# ───────────────────────── Q1: the production chain ─────────────────────────
hr('Q1.  "How do I make a Rune platebody — from raw materials?"  (recursive bill of materials)')
def expand(item_id, mult=1, depth=0, seen=None):
    seen = seen or set()
    rid = recipe_for(item_id)
    pad = "   " * depth
    label = f"{mult}x {name(item_id)}"
    if rid is None or item_id in seen:
        return [(item_id, mult)]                       # a raw leaf (mined/bought/base)
    seen = seen | {item_id}
    fac = ", ".join(name(f) for f in facility_of.get(rid, [])) or "no facility"
    gate = gate_str(rid) or "no skill req"
    print(f"{pad}▸ {c('1',label)}   —  at {c('96',fac)}, needs {c('93',gate)}")
    leaves = []
    for (dst, qty, role) in sorted(consumes.get(rid, []), key=lambda t: t[2] or ""):
        if role == "tool":
            print(f"{pad}    · tool: {name(dst)}")
            continue
        leaves += expand(dst, mult * (qty or 1), depth + 1, seen)
    return leaves

TARGET = item_by_name("Rune platebody")
raw = Counter()
for iid, m in expand(TARGET):
    raw[iid] += m
print(f"\n  {c('92','RAW SHOPPING LIST')} for 1 Rune platebody (fully expanded):")
for iid, m in sorted(raw.items(), key=lambda t: -t[1]):
    print(f"     {m:>3}x  {name(iid)}")


# ───────────────────────── Q2: alternatives (many -> one) ─────────────────────────
hr('Q2.  "What are ALL the ways to make a Runite bar?"  (per-method-row alternatives)')
RB = item_by_name("Runite bar")
for rid in sorted(produces.get(RB, [])):
    mats = [f"{q}x {name(d)}" for (d, q, r) in consumes.get(rid, []) if r == "material"]
    fac = ", ".join(name(f) for f in facility_of.get(rid, [])) or "no facility (spell)"
    print(f"  • {c('1',name(rid))}")
    print(f"       {' + '.join(mats)}   @ {c('96',fac)}")


# ───────────────────────── Q3: what can I make here ─────────────────────────
hr('Q3.  "What can I smith at an Anvil?"  (facility -> recipes; the platebody tier ladder)')
anvil = made_at.get("facility:anvil", [])
print(f"\n  The Anvil is used by {c('92',str(len(anvil)))} recipes. The platebody ladder:")
ladder = []
for rid in anvil:
    n = kg.node(rid)
    if n and n.name.endswith("platebody"):
        xp = n.data.get("xp", {}).get("Smithing")
        g = gate_str(rid)
        ladder.append((xp or 0, n.name, g, xp))
for xp, nm, g, real_xp in sorted(ladder):
    print(f"     {nm:<22} needs {c('93',g or '—'):<16}  →  {c('92',str(real_xp))} Smithing xp")


# ───────────────────────── Q4: can MY account make it? ─────────────────────────
hr('Q4.  "Can MY account make a Rune platebody?"  (the account-aware three-valued evaluator)')
VERDICT = {Tri.TRUE: c("92", "✓ CAN MAKE"), Tri.FALSE: c("91", "✗ BLOCKED"),
           Tri.UNKNOWN: c("93", "? UNKNOWN")}
rid = recipe_for(TARGET)
gate = skillgate.get(rid)
print(f"\n  Target: Rune platebody  (recipe gate: {c('93', gate_str(rid))})\n")
accounts = {
    "Fresh account (Smithing 1, hiscores synced)":
        AccountState(mode="main", observable_families={"skill_level"}, levels={"skill:smithing": 1}),
    "Mid-game (Smithing 55)":
        AccountState(mode="main", observable_families={"skill_level"}, levels={"skill:smithing": 55}),
    "Maxed smith (Smithing 99)":
        AccountState(mode="main", observable_families={"skill_level"}, levels={"skill:smithing": 99}),
    "Unsynced account (no skills plugin yet)":
        AccountState(mode="main"),                 # nothing observable -> the planner refuses to guess
}
for label, st in accounts.items():
    v = evaluate(gate, st, kg)
    print(f"     {VERDICT[v]}   {label}")


# ───────────────────────── Q5: the graph of Gielinor so far ─────────────────────────
hr("Q5.  The graph of Gielinor — how far we've come")
kinds = Counter(n.kind.value for n in kg.nodes.values())
etypes = Counter(e.type.value for e in kg.edges)
print(f"\n  {c('92', str(len(kg.nodes)))} nodes  /  {c('92', str(len(kg.edges)))} edges committed. Node kinds:")
for k, v in kinds.most_common():
    print(f"     {v:>5}  {k}")
print("\n  A few edge types that make it a GRAPH, not a catalog:")
for t in ("sells", "located_in", "operates", "consumes", "produces", "requires", "requires_facility", "has_bonuses"):
    if t in etypes:
        print(f"     {etypes[t]:>6}  {t}")
print()
