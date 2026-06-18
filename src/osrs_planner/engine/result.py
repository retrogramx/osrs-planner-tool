"""The Result envelope — every Engine function returns one of these (contract §4).

Result[T] =
  | Ok[T]    : a card payload + the nodes it makes claims about
  | Empty    : a SUCCESS terminal ("already done", "no frontier", "no result")
  | Problem  : a structured failure from the closed ProblemKind taxonomy

`Refs` is the grounding leash (contract §5.1, §7.4): every node the Advisor may
name must live in `nodes` (the plan) or `mentions` (incidental HOW context).
These are engine-internal frozen dataclasses; the pydantic card layer projects
them to the JSON/tool-schema shapes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Generic, Literal, TypeVar

T = TypeVar("T")


class ProblemKind(str, Enum):
    """Closed failure taxonomy (contract §4, error contract §10).

    Trimmed to what the Engine can actually return under the merged schema:
    `unsupported_mode` is dropped (I12 scope grammar prevents it) and a
    `requires_dag` cycle is dropped (I1 FAILs the build before swap).
    `UNSATISFIABLE_CYCLE` is retained only for the I15-excluded acquisition walk.
    """

    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"
    INVALID_TARGET = "invalid_target"
    IMPOSSIBLE_FOR_ACCOUNT = "impossible_for_account"
    MISSING_STATE = "missing_state"
    UNSATISFIABLE_CYCLE = "unsatisfiable_cycle"


class TerminalReason(str, Enum):
    """Why an `Empty` (a SUCCESS state, not a failure) terminated."""

    ALREADY_SATISFIED = "already_satisfied"
    NO_FRONTIER = "no_frontier"
    EMPTY_RESULT = "empty_result"


@dataclass(frozen=True)
class NodeRef:
    """A reference to one KG node, carried in `Refs` for the grounding check."""

    id: str
    kind: str
    name: str


@dataclass(frozen=True)
class Refs:
    """The grounding leash: nodes a card claims about + incidentally mentions.

    `nodes`    — the prereq/closure/claim nodes the card makes claims about.
    `mentions` — nodes referenced incidentally by a step's method/advisory slot.
    Each defaults to its OWN empty dict (default_factory — no shared-mutable bug).
    """

    nodes: dict[str, NodeRef] = field(default_factory=dict)
    mentions: dict[str, NodeRef] = field(default_factory=dict)


@dataclass(frozen=True)
class Ok(Generic[T]):
    """Success carrying a card payload of type T plus its grounding refs."""

    card: T
    refs: Refs


@dataclass(frozen=True)
class Empty:
    """A SUCCESS terminal: a valid empty answer the Advisor must narrate.

    Distinct from `Problem`: "you're already done" / "no frontier" / "no result"
    are correct answers, not errors. `status` is fixed to "ok".
    """

    refs: Refs
    reason: TerminalReason
    status: Literal["ok"] = "ok"


@dataclass(frozen=True)
class Problem:
    """A structured failure. No function raises to the transport (contract §4);
    FastAPI maps this to a 4xx body and the tool-schema surfaces the same shape."""

    kind: ProblemKind
    refs: Refs
    message: str


# The envelope every Engine function returns. Consumers branch on the variant.
type Result[T] = Ok[T] | Empty | Problem
