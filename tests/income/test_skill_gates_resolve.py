"""Real-data regression: every parsed skill gate is a real KG skill node.

Guards against pseudo-"skills" in money_making.json's ``data-skill`` spans
leaking through ``parse_requirements_html`` as bogus ``skill:<x>`` gates that the
can-do-now filter would permanently mis-gate as hard-FALSE (an account can never
hold a non-KG skill). The valid skill-node set is derived from ``kg/nodes.json``
(authoritative) so this test catches ANY future pseudo-skill -- e.g. the
previously-leaking ``skill:sailing`` (unreleased skill, no KG node) and
``skill:skills`` (a Total-level pseudo-gate) would fail here if they reappeared.
"""
from __future__ import annotations

import json
import os

from osrs_planner.income.methods import load_methods

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(_ROOT, "data")
KG_NODES = os.path.join(_ROOT, "kg", "nodes.json")


def _kg_skill_ids() -> set[str]:
    """Authoritative valid skill-gate ids: KG nodes with kind == 'skill'."""
    with open(KG_NODES, encoding="utf-8") as f:
        nodes = json.load(f)
    ids = {
        n["id"]
        for n in nodes
        if n.get("kind") == "skill" and str(n.get("id", "")).startswith("skill:")
    }
    assert ids, "no kind=='skill' nodes found in kg/nodes.json"
    return ids


def _parsed_skill_ids() -> set[str]:
    keys: set[str] = set()
    for m in load_methods(DATA_DIR):
        keys |= set(m.requirements.skills)
    return keys


def test_every_parsed_skill_gate_is_a_real_kg_skill_node():
    parsed = _parsed_skill_ids()
    valid = _kg_skill_ids()
    bogus = parsed - valid
    assert not bogus, f"parsed skill gates that are NOT KG skill nodes: {sorted(bogus)}"


def test_no_sailing_or_total_level_pseudo_skill_leaks():
    # The two pseudo-"skills" this regression locks out specifically: Sailing
    # (unreleased, no KG node) and "Skills" (a Total-level pseudo-gate).
    parsed = _parsed_skill_ids()
    assert "skill:sailing" not in parsed
    assert "skill:skills" not in parsed
