# src/osrs_planner/income/methods.py
"""Normalized money-making method model (income design §3).

One ``MethodRecord`` (frozen pydantic) unifies the two source datasets
(data/money_making.json: 377 main, HTML requirements; data/ironman_money_making.json:
49 iron, native structured requirements). gp/hr is COMPUTED at query time from
``outputs x PriceProvider`` (realize.py) -- the stored ``gp_hr`` is NOT trusted.

IDs are KG-style strings: methods ``method:<slug>``, items ``item:<n>``,
quests ``quest:<slug>``, skills ``skill:<name>``.
"""
from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Flow(BaseModel):
    """One output or input stream of a method, per hour.

    ``item_id`` is a KG-style ``"item:<n>"`` string, or ``None`` for a pure
    coins flow (``is_coins=True``). A non-coin flow with ``item_id=None`` is an
    un-resolvable / aggregate stream (e.g. the "Gem drop table" pseudo-output)
    that realize.py treats as unpriceable. ``qty_per_hour`` is ``None`` when the
    rate is not modelled (realize.py surfaces that as ``unknown``, never 0).
    """

    item_id: Optional[str] = None
    is_coins: bool = False
    qty_per_hour: Optional[float] = None


class Requirements(BaseModel):
    """Structured requirements feeding the engine condition-evaluator (filter.py).

    ``skills`` maps a KG ``"skill:<name>"`` id to a required level; ``quests``
    is a list of ``"quest:<slug>"`` ids; ``items`` is a list of ``"item:<n>"``
    ids (item gates stay UNKNOWN until bank data -- absence != zero).
    """

    skills: dict[str, int] = Field(default_factory=dict)
    quests: list[str] = Field(default_factory=list)
    items: list[str] = Field(default_factory=list)


class MethodRecord(BaseModel, frozen=True):
    """A single money-making method, normalized across both datasets (§3).

    Frozen: loaded once and shared across requests (like the KG static value
    types). ``stage`` is a SOFT hint only -- the requirement check (filter.py),
    not this tag, decides doability. ``processing_dependent`` flags methods whose
    iron income needs a processing chain not yet covered, so v1 marks them
    ``gp_hr_status=unknown`` rather than under-counting.
    """

    id: str
    name: str
    category: str
    members: bool
    audience: str
    requires_ge: bool
    iron_eligible: bool
    realization_channel: str
    outputs: list[Flow] = Field(default_factory=list)
    inputs: list[Flow] = Field(default_factory=list)
    requirements: Requirements = Field(default_factory=Requirements)
    stage: Optional[str] = None
    tags: dict = Field(default_factory=dict)
    processing_dependent: bool = False
    net_sign: Literal["earner", "sink"]
    source: str
    url: str
    accessed_at: str


# Pseudo-"skills" in skill_requirements_html that are NOT KG skill nodes
# (combat level is derived; quest points handled by the engine elsewhere).
_NON_SKILL_PSEUDO = frozenset({"combat level", "quest points"})


def _slug(name: str) -> str:
    """A wiki page name -> a KG slug fragment.

    Lowercase; apostrophes dropped; every run of non-alphanumerics -> a single
    hyphen; trim leading/trailing hyphens. "Fairytale II - Cure a Queen" ->
    "fairytale-ii-cure-a-queen".
    """
    s = name.strip().lower().replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
# data-skill, then OPTIONALLY a data-level somewhere later in the same tag.
_SCP_SPAN = re.compile(r'data-skill="([^"]+)"(?:[^>]*?data-level="([^"]+)")?')


def parse_requirements_html(skill_html, quest_html=None) -> Requirements:
    """Parse the main dataset's prose requirement fields into Requirements.

    ``skill_html`` = a money_making.json ``skill_requirements_html`` value.
    Each span with a numeric ``data-level`` becomes a ``skill:<name>`` gate
    (trailing ``+`` stripped; pseudo-skills combat-level/quest-points dropped; a
    span with no level is a recommendation, dropped). ``quest_html`` = the
    ``quest`` prose field; EVERY ``[[Quest]]`` wikilink becomes a ``quest:<slug>``
    gate (v1 is conservative -- a "recommended" quest over-gates to future_gated,
    which is safe; under-gating is not, spec §11).
    """
    skills: dict[str, int] = {}
    if skill_html:
        for m in _SCP_SPAN.finditer(skill_html):
            raw_skill = m.group(1).strip()
            raw_level = m.group(2)
            if raw_skill.lower() in _NON_SKILL_PSEUDO:
                continue
            if not raw_level:
                continue  # no numeric gate -> recommendation, not a requirement
            level = int(raw_level.rstrip("+ ").strip())
            skills[f"skill:{_slug(raw_skill)}"] = level

    quests: list[str] = []
    if quest_html and quest_html.strip().lower() != "none":
        seen: set[str] = set()
        for m in _WIKILINK.finditer(quest_html):
            qid = f"quest:{_slug(m.group(1))}"
            if qid not in seen:
                seen.add(qid)
                quests.append(qid)

    return Requirements(skills=skills, quests=quests, items=[])
