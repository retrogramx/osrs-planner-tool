# src/osrs_planner/engine/state.py
"""Absence-aware account state for the Gilded Tome goal-engine.

Contract §6 (three-valued / Kleene) + ADR-0004 observability families:
state distinguishes *absent* from *zero*. Per-skill levels/XP and activity
scores (KC, clues, CA points, minigames) and account_type are
Hiscores-observable -> absence is a real zero/FALSE. Everything else
(quest, achievement_diary, combat_achievement, item, is_unlocked,
quest_points) is UNKNOWN until a plugin or manual fact supplies it.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Ordered 3-state enum, reused for both quest_state and diary_state.
QUEST_STATE_ORDER: dict[str, int] = {"not_started": 0, "in_progress": 1, "completed": 2}


@dataclass
class AccountState:
    """Player account state. Mutable (manual confirmations write back here).

    Field families map 1:1 to the condition-atom families they feed:
      levels/xp        -> skill_level / skill_xp
      counts           -> item / gear_loadout (live owned quantities)
      quest_state      -> quest        (ordered, QUEST_STATE_ORDER)
      diary_state      -> achievement_diary (ordered, QUEST_STATE_ORDER)
      done             -> is_unlocked (access:*) + per-task combat_achievement
      combat_level     -> combat_level (derived, computed once into state)
      qp               -> quest_points
      ca_points        -> combat_achievement_points
      kc               -> kill_count
      clue_counts      -> clue_scrolls
    observable_families: atom_type values whose ABSENCE is OBSERVED-as-zero
      (a real FALSE) rather than UNKNOWN. Built from ADR-0004 per source.
    """
    mode: str
    levels: dict[str, int] = field(default_factory=dict)
    xp: dict[str, int] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)  # item id -> qty
    quest_state: dict[str, str] = field(default_factory=dict)
    diary_state: dict[str, str] = field(default_factory=dict)
    done: set[str] = field(default_factory=set)  # access unlocks + per-task CAs obtained
    combat_level: int = 3
    qp: int = 0
    ca_points: int = 0
    kc: dict[str, int] = field(default_factory=dict)
    clue_counts: dict[str, int] = field(default_factory=dict)
    observable_families: set[str] = field(default_factory=set)


def family_is_observed(
    atom_family: str,
    state: AccountState,
    *,
    manually_asserted: bool,
) -> bool:
    """Decide whether an ABSENT value for ``atom_family`` is an observed zero.

    Contract §6 (absence-aware / Kleene), ADR-0004 observability families.

    Returns ``True``  -> absence is a REAL zero/not_started/not-owned (-> FALSE
                         is a legitimate verdict for an absent value).
    Returns ``False`` -> absence is genuinely unknown (-> the evaluator must
                         yield UNKNOWN, never a fabricated "locked").

    A manual assertion is trusted for ANY family (the one-tap "confirm this
    value" path, §9.3), so it overrides the observability table. Otherwise the
    family must be in ``state.observable_families`` (built per ADR-0004 from
    the account's data source) for absence to count as zero.
    """
    if manually_asserted:
        return True
    return atom_family in state.observable_families
