"""MethodRecord/Flow/Requirements: frozen pydantic, contract field shapes."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from osrs_planner.income.methods import MethodRecord, Flow, Requirements


def _minimal_method(**over):
    base = dict(
        id="method:killing-green-dragons",
        name="Killing green dragons",
        category="Combat/Mid",
        members=True,
        audience="main",
        requires_ge=False,
        iron_eligible=True,
        realization_channel="mixed",
        outputs=[Flow(item_id="item:1753", is_coins=False, qty_per_hour=180.0)],
        inputs=[Flow(item_id="item:561", is_coins=False, qty_per_hour=105.0)],
        requirements=Requirements(skills={"skill:prayer": 25}, quests=[], items=[]),
        stage=None,
        tags={"intensity": "Moderate", "wilderness": True},
        processing_dependent=False,
        net_sign="earner",
        source="OSRS Wiki money_making_guide",
        url="https://oldschool.runescape.wiki/w/Money_making_guide/Killing_green_dragons",
        accessed_at="2026-06-18T04:06:25Z",
    )
    base.update(over)
    return MethodRecord(**base)


def test_flow_fields():
    f = Flow(item_id="item:1753", is_coins=False, qty_per_hour=180.0)
    assert f.item_id == "item:1753"
    assert f.is_coins is False
    assert f.qty_per_hour == 180.0
    c = Flow(item_id=None, is_coins=True, qty_per_hour=54.9)
    assert c.item_id is None and c.is_coins is True


def test_flow_qty_per_hour_is_nullable():
    # a null rate = "rate not modelled" -> realize surfaces unknown (never 0).
    f = Flow(item_id="item:1753", is_coins=False, qty_per_hour=None)
    assert f.qty_per_hour is None


def test_requirements_defaults_and_shape():
    r = Requirements()
    assert r.skills == {} and r.quests == [] and r.items == []
    r2 = Requirements(skills={"skill:crafting": 63}, quests=["quest:dragon-slayer-ii"], items=["item:22978"])
    assert r2.skills["skill:crafting"] == 63
    assert r2.quests == ["quest:dragon-slayer-ii"]
    assert r2.items == ["item:22978"]


def test_method_record_all_contract_fields_present():
    m = _minimal_method()
    assert m.id == "method:killing-green-dragons"
    assert m.name == "Killing green dragons"
    assert m.category == "Combat/Mid"
    assert m.members is True
    assert m.audience == "main"
    assert m.requires_ge is False
    assert m.iron_eligible is True
    assert m.realization_channel == "mixed"
    assert m.outputs[0].item_id == "item:1753"
    assert m.inputs[0].item_id == "item:561"
    assert m.requirements.skills == {"skill:prayer": 25}
    assert m.stage is None
    assert m.tags == {"intensity": "Moderate", "wilderness": True}
    assert m.processing_dependent is False
    assert m.net_sign == "earner"
    assert m.source.startswith("OSRS Wiki")
    assert m.url.startswith("https://")
    assert m.accessed_at == "2026-06-18T04:06:25Z"


def test_method_record_is_frozen():
    m = _minimal_method()
    with pytest.raises(ValidationError):
        m.name = "mutated"


def test_net_sign_must_be_earner_or_sink():
    with pytest.raises(ValidationError):
        _minimal_method(net_sign="bogus")
