"""Three-valued (Kleene strong) logic for condition evaluation.

Contract §6: an absent, unobservable, not-manually-asserted atom evaluates to
UNKNOWN (not FALSE). AND/OR/NOT fold UNKNOWN and surface it ONLY when it flips
the verdict -- i.e. a FALSE dominates AND, a TRUE dominates OR.
"""

from enum import Enum
from typing import Iterable


class Tri(Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


def from_bool(b: bool) -> Tri:
    """Lift a definite Python bool into Tri (never produces UNKNOWN)."""
    return Tri.TRUE if b else Tri.FALSE


def k_not(v: Tri) -> Tri:
    """Kleene negation: TRUE<->FALSE, UNKNOWN stays UNKNOWN."""
    if v is Tri.TRUE:
        return Tri.FALSE
    if v is Tri.FALSE:
        return Tri.TRUE
    return Tri.UNKNOWN


def k_and(values: Iterable[Tri]) -> Tri:
    """Kleene conjunction: FALSE if any FALSE; else UNKNOWN if any UNKNOWN; else TRUE.

    Empty fold is TRUE (vacuous). A known-FALSE dominates, so an UNKNOWN
    sibling is absorbed and never surfaces (contract §6).
    """
    saw_unknown = False
    for v in values:
        if v is Tri.FALSE:
            return Tri.FALSE
        if v is Tri.UNKNOWN:
            saw_unknown = True
    return Tri.UNKNOWN if saw_unknown else Tri.TRUE


def k_or(values: Iterable[Tri]) -> Tri:
    """Kleene disjunction: TRUE if any TRUE; else UNKNOWN if any UNKNOWN; else FALSE.

    Empty fold is FALSE (no satisfying alternative). A known-TRUE dominates,
    so an UNKNOWN sibling is absorbed and never surfaces (contract §6).
    """
    saw_unknown = False
    for v in values:
        if v is Tri.TRUE:
            return Tri.TRUE
        if v is Tri.UNKNOWN:
            saw_unknown = True
    return Tri.UNKNOWN if saw_unknown else Tri.FALSE
