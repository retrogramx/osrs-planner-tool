# tests/engine/conftest.py
"""Auto-discovered pytest fixtures for the engine test suite.

Wraps the plain importable builders in tests/engine/fixtures/kg_fixture.py so
Tasks 10-13 can request `scurrius_kg` / `fresh_main` / `iron_75atk_60str`
by fixture name (pytest scans conftest.py for fixtures; it does NOT scan the
kg_fixture module). The store is the kg-schema-v1 worked example rooted at
npc:7221 with requires-tree OR( AND(70 Attack, 70 Strength), gear_loadout:void ).
"""

from __future__ import annotations

import pytest

from osrs_planner.engine.kg.store import InMemoryKGStore
from osrs_planner.engine.state import AccountState
from tests.engine.fixtures.kg_fixture import (
    build_store,
    fresh_main as _fresh_main,
    iron_75atk_60str_novoid as _iron_75atk_60str_novoid,
)


@pytest.fixture
def scurrius_kg() -> InMemoryKGStore:
    """The worked (70 Att AND 70 Str) OR full-Void Scurrius KG (npc:7221)."""
    return build_store()


@pytest.fixture
def fresh_main() -> AccountState:
    """A brand-new NORMAL account (no observable families set)."""
    return _fresh_main()


@pytest.fixture
def iron_75atk_60str() -> AccountState:
    """The flagship counter-example: ironman 75 Atk / 60 Str, no Void."""
    return _iron_75atk_60str_novoid()
