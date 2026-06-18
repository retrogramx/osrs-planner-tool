"""Gilded Tome goal-engine: deterministic KG traversal + Kleene evaluation.

Public surface (built across this plan):
    result.py      — Ok / Empty / Problem envelope (contract §4)
    kleene.py      — three-valued logic (contract §6)
    state.py       — AccountState + absence-aware UNKNOWN rule (contract §6)
    kg/model.py    — Node / Edge / ConditionGroup / ConditionAtom (KG schema v1)
    kg/store.py    — KGStore interface + InMemoryKGStore + requires_dag projection
    conditions.py  — recursive evaluate() / atom_satisfied() folding via kleene
    cards.py       — pydantic projection (UnlockCard / PlanCard / Step / ...)
    engine.py      — Engine.is_unlocked / prereqs_for / next_steps

Runs on a hand-authored KG fixture; the real KG (data/*.json) arrives with feat/kg-ingest.
"""
