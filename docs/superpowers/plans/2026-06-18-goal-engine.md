# Goal-Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the deterministic goal-engine — the "careful librarian" that reads a knowledge graph + an account's state and answers *can you do X / what's needed / what's next*, never guessing — proven against a hand-authored KG fixture.

**Architecture:** A pure-Python `networkx` engine over the KG (`Node/Edge/ConditionGroup/ConditionAtom`) + an absence-aware `AccountState`. Every function returns a `Result[T] = Ok | Empty | Problem` envelope; conditions evaluate in three-valued (Kleene) logic so unobservable state yields `indeterminate`/`cant_verify`, never a false "locked." Built TDD against a fixture encoding the contract's worked examples; the real KG arrives later via the separate `feat/kg-ingest` brick.

**Tech Stack:** Python 3.12+, networkx (new dep), pydantic (public cards), pytest.

**Scope (this plan):** the deterministic core + `is_unlocked` / `prereqs_for` / `next_steps`. **Out of scope (follow-up plan):** `expand_for_account` (account-type buy-vs-gather acquisition), `compare_goals`, `suggest_goals`, `resolve_goal`, mutations, and the LLM advisor projection — these are the functions that emit the `AMBIGUOUS` / `INVALID_TARGET` / `IMPOSSIBLE_FOR_ACCOUNT` / `EMPTY_RESULT` results, which is why this plan defines those taxonomy members but does not emit them. The real KG ingest (`data/*.json` → graph) is the separate `feat/kg-ingest` brick.

**Source design:** engine↔advisor contract (`docs/superpowers/specs/2026-06-15-engine-advisor-contract-design.md`), KG schema v1 (`research/kg-schema-v1.md`), observability table (`decisions/2026-06-13-0004-public-multi-account.md`).

---

## File structure

| File | Responsibility |
|---|---|
| `src/osrs_planner/engine/result.py` | `Result[T] = Ok \| Empty \| Problem` envelope + `ProblemKind`/`TerminalReason` (contract §4) |
| `src/osrs_planner/engine/kleene.py` | three-valued `Tri{TRUE,FALSE,UNKNOWN}` + AND/OR/NOT folding (contract §6) |
| `src/osrs_planner/engine/kg/model.py` | KG types `Node/Edge/ConditionGroup/ConditionAtom` + `NodeKind/EdgeType/AtomType/Op` |
| `src/osrs_planner/engine/kg/store.py` | `KGStore` interface + `InMemoryKGStore`; `requires_dag()` projection (grant-flip + cond-leaf); `descendants`/`topo_order`/`find_cycles` |
| `src/osrs_planner/engine/state.py` | `AccountState` (absence-aware) + `QUEST_STATE_ORDER` |
| `src/osrs_planner/engine/conditions.py` | `evaluate(group_id, state, kg) -> Tri` + `atom_satisfied(atom, state, kg) -> Tri` for every locked atom |
| `src/osrs_planner/engine/cards.py` | pydantic return payloads: `NodeRef/ReferencedAtom/Step/UnlockCard/PlanCard` |
| `src/osrs_planner/engine/engine.py` | the `Engine` — `is_unlocked` / `prereqs_for` / `next_steps` |
| `tests/engine/fixtures/kg_fixture.py` | hand-authored KG (Scurrius goal, `(70 Att AND 70 Str) OR full-Void`, quests/diary) + sample `AccountState`s |

---

## Resolved design decisions (these OVERRIDE any task text that conflicts)

These were settled during plan review (the parallel task-drafts had a few inconsistencies). Apply them everywhere:

- **D1 — Ordering is prereqs-first.** `KGStore.topo_order(goal)` returns `reversed(list(nx.topological_sort(dag)))` where edge `a→b` means "a requires b" (KG schema v1 line 291). So prerequisites come **before** the goal. All ordering tests assert prereqs-first.
- **D2 — `ConditionGroup.children`** is a `list` whose elements are either an `int` (a child group id, looked up in `kg.groups`) **or** a `ConditionAtom` object (inline leaf). `evaluate(group_id)` looks the group up and dispatches on element type.
- **D3 — `gear_loadout` is ref-bearing for the DAG, AND dynamic for evaluation.** In `requires_dag`, a `gear_loadout` atom projects a `cond_dep` edge to its `gear_loadout:*` node (whose `dst=NULL` composition edge pulls the item leaves into the closure). In `atom_satisfied`, it is evaluated by recursing into that composition against **current** counts (never cached `done`). Both are true; they are not in conflict. `_REF_BEARING_ATOMS = {item, is_unlocked, gear_loadout, quest, achievement_diary, combat_achievement, kill_count}`.
- **D4 — `MISSING_STATE` only for a wholly-absent account** (`state is None`). A fresh real account (mode set, empty progress, `combat_level==3`) is **valid**, not missing.
- **D5 — `is_unlocked` folds ALL of a node's `requires` edges as an AND.** A node may have multiple `requires` edges (the fixture's Scurrius has two); the node is unlocked iff every requires edge is satisfied — each edge satisfied iff its `cond_group` (if any) is TRUE **and** its `dst` node (if non-NULL) is itself unlocked (recursive).
- **D6 — manual assertion = value present in `AccountState`.** `atom_satisfied` treats a ref whose value is present in the relevant state dict as *known* (whether synced or manually confirmed); absent + family not in `observable_families` → `UNKNOWN`.
- **D7 — `NOT_FOUND` carries an empty `Refs`** (an unknown id is not a node, so it cannot be a `NodeRef`); the id is named in `Problem.message`. Consistent across `is_unlocked`/`prereqs_for`/`next_steps`.
- **D8 — `next_steps` reuses `prereqs_for`'s `Step` instances** (filters that step list to the actionable frontier) so the two reads can never drift.

---

### Task 1: SPEC.md reconciliation + engine scaffold

Fold the research track (engine↔advisor contract, KG schema v1, data foundation) into `SPEC.md` as the DESIGN+DATA backing the `feat/goal-engine` brick, split ingest into its own brick, then scaffold the engine package (`src/osrs_planner/engine/` + `engine/kg/` + `tests/engine/`) and add `networkx` to dependencies. Part (a) is a DOC edit shown as before/after snippets (no TDD). Part (b) is the package skeleton + the `pyproject.toml` diff, ending in a commit and a verify run.

**Files:**
- `SPEC.md` (edit — header date, bricks table, ADR-adjacent roadmap note)
- `src/osrs_planner/engine/__init__.py` (new)
- `src/osrs_planner/engine/kg/__init__.py` (new)
- `tests/engine/__init__.py` (new)
- `pyproject.toml` (edit — add `networkx`)

---

#### Part (a) — SPEC.md reconciliation (DOC, no TDD)

- [ ] **Bump the status/date header.** In `SPEC.md`, line 5 currently reads:

  **Before:**
  ```markdown
  **Status:** Active · `feat/web-foundation` shipped → PR #1 · updated 2026-06-13
  ```

  **After:**
  ```markdown
  **Status:** Active · `feat/web-foundation` shipped → PR #1 · `feat/goal-engine` design+data locked (the engine↔advisor contract, KG schema v1, data foundation) · updated 2026-06-18
  ```

  Apply this with the Edit tool (exact replace of the single line).

- [ ] **Replace the combined goal row in the bricks table and split out ingest.** In `SPEC.md` §6 (Roadmap), the bricks table currently has one row combining the tracker and engine, and a `feat/runelite-plugin` row that conflates sync with ingest. Replace the goal row and add an explicit ingest brick.

  **Before** (the single combined row, line 73):
  ```markdown
  | `feat/goal-tracker` · `feat/goal-engine` | The differentiator — account-type-aware goal-DAG | todo | — |
  ```

  **After** (two rows — engine carries the design+data backing; tracker stays the STATE/DDL brick):
  ```markdown
  | `feat/goal-engine` | The differentiator's brain — deterministic engine over a hand-authored KG fixture (Result envelope + Kleene + cards). **Design:** engine↔advisor contract (`docs/superpowers/specs/2026-06-15-engine-advisor-contract-design.md`) + KG schema v1 (`research/kg-schema-v1.md`). **Data:** the source datasets in `data/*.json` (the engine runs on a KG fixture for now, not these directly). | in progress | (this plan) |
  | `feat/goal-tracker` | Per-account STATE layer: the goal-DAG DDL (§9 of the contract — `goal`/`account_progress`, two-writer rule) + tracker UI. Inherits the engine's `Result`/card shapes. | todo | — |
  ```

- [ ] **Add the ingest brick as a separate row.** Immediately below the `feat/goal-tracker` row added above, the existing `feat/runelite-plugin` row (line 74) currently reads:

  **Before:**
  ```markdown
  | `feat/runelite-plugin` | Java sync → `/sync`: deep-data shipper **+ account claim/auth** | todo | — |
  ```

  **After** (note ingest is its own brick that the engine does NOT depend on for `feat/goal-engine`):
  ```markdown
  | `feat/kg-ingest` | **Separate brick:** the data pipeline that builds the real KG (`data/*.json` → `node`/`edge`/`condition_*` per KG schema v1) which the engine's `KGStore` loads. `feat/goal-engine` ships first on a hand-authored fixture and does NOT block on this. | todo | — |
  | `feat/runelite-plugin` | Java sync → `/sync`: deep-data shipper **+ account claim/auth** | todo | — |
  ```

- [ ] **Update §4 (Goal model) to point the prereq logic at the engine brick.** In `SPEC.md` §4, the final sentence (line 55) currently reads:

  **Before:**
  ```markdown
  Detailed schema is specified in the `feat/goal-tracker` plan when that brick is built.
  ```

  **After:**
  ```markdown
  Detailed schema is specified in the `feat/goal-tracker` plan; the prerequisite-graph **evaluation** (Kleene three-valued unlock/prereq/next-step logic over the KG) is the `feat/goal-engine` brick, designed in the engine↔advisor contract and KG schema v1 and built on a hand-authored KG fixture before ingest exists.
  ```

- [ ] **Resolve the matching open decision.** In `SPEC.md` §9 (Open decisions), the first bullet (line 100) currently reads:

  **Before:**
  ```markdown
  - Prerequisite graph: curated/opinionated path vs neutral graph the user orders.
  ```

  **After:**
  ```markdown
  - ~~Prerequisite graph: curated/opinionated path vs neutral graph the user orders.~~ **Resolved** (KG schema v1 + contract §13.1): a **neutral facts graph** is the source of truth; the engine never auto-picks a route — it returns all branches as choices, with a crude `fewest_unmet_leaves` efficiency hint. Curated orderings are an optional opinion overlay that must be a valid topo order of the facts graph.
  ```

- [ ] **Commit the doc reconciliation.**
  ```bash
  cd /Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool && git add SPEC.md && git commit -m "docs(spec): fold engine/KG/data research into feat/goal-engine; split ingest brick"
  ```
  Expected output: one commit created, `1 file changed`.

---

#### Part (b) — Engine package scaffold (TDD-shaped: create dirs, add dependency, verify)

- [ ] **Create the engine package marker.** Write `src/osrs_planner/engine/__init__.py`:
  ```python
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
  ```

- [ ] **Create the KG sub-package marker.** Write `src/osrs_planner/engine/kg/__init__.py`:
  ```python
  """Knowledge-graph model + store for the goal-engine (KG schema v1)."""
  ```

- [ ] **Create the engine test package marker.** Write `tests/engine/__init__.py`:
  ```python
  """Tests for osrs_planner.engine (pytest)."""
  ```

- [ ] **Add `networkx` to dependencies.** Edit `pyproject.toml` — the `dependencies` list.

  **Before:**
  ```toml
  dependencies = [
      "pydantic",
      "pytest",
      "httpx",
      "fastapi",
      "uvicorn",
  ]
  ```

  **After:**
  ```toml
  dependencies = [
      "pydantic",
      "pytest",
      "httpx",
      "fastapi",
      "uvicorn",
      "networkx",
  ]
  ```

- [ ] **Install the new dependency into the project venv.**
  ```bash
  cd /Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool && ./venv/bin/python -m pip install -e . -q
  ```
  Expected: pip resolves and installs `networkx` (plus the already-present deps), exit code 0. If `pip install -e .` is too heavy, the minimal equivalent is `./venv/bin/python -m pip install networkx -q`.

- [ ] **Verify networkx imports.**
  ```bash
  cd /Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool && ./venv/bin/python -c "import networkx; print('networkx', networkx.__version__)"
  ```
  Expected output (version may differ): `networkx 3.x`. Exit code 0.

- [ ] **Verify the engine packages import cleanly.**
  ```bash
  cd /Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool && ./venv/bin/python -c "import osrs_planner.engine, osrs_planner.engine.kg; print('engine packages OK')"
  ```
  Expected output: `engine packages OK`. Exit code 0.

- [ ] **Verify pytest discovers the new test package with zero engine tests (no errors).**
  ```bash
  cd /Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool && ./venv/bin/python -m pytest tests/engine/ -q
  ```
  Expected output: `no tests ran` (collected 0 items), exit code 5 (pytest's "no tests collected") — importantly **no collection errors**. The full suite still passes:
  ```bash
  cd /Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool && ./venv/bin/python -m pytest -q
  ```
  Expected: the pre-existing `tests/test_planner.py` / `tests/test_xp.py` still pass (e.g. `N passed`), exit code 0.

- [ ] **Commit the scaffold.**
  ```bash
  cd /Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool && git add src/osrs_planner/engine/ tests/engine/ pyproject.toml && git commit -m "feat(engine): scaffold engine package + add networkx dependency"
  ```
  Expected output: one commit created, `4 files changed` (three new `__init__.py` files + `pyproject.toml`).

---

**Notes for the plan author / next tasks:**
- The fixed type-spine maps onto these scaffolded paths exactly: `engine/result.py`, `engine/kleene.py`, `engine/state.py`, `engine/conditions.py`, `engine/cards.py`, `engine/engine.py`, `engine/kg/model.py`, `engine/kg/store.py`. Task 2 onward fills them in (suggested order: `kleene.py` → `result.py` → `kg/model.py` → `state.py` → `kg/store.py` (requires_dag, I1 cycle check) → `conditions.py` → `cards.py` → `engine.py`), each as its own TDD task under `tests/engine/`.
- The project venv interpreter is `./venv/bin/python` (Python 3.12+ per `requires-python`); the installed test runner is invoked as `./venv/bin/python -m pytest` to avoid any global pytest. Bare `pytest -q` also works if the venv is activated, but the absolute-interpreter form is reproducible across the agent's reset cwd.
- No source files (`data/*.json`) are touched — the engine runs on a hand-authored KG fixture (built with `InMemoryKGStore` in a later task), per the contract's "engine ships first on a fixture, ingest is a separate brick" split.

Relevant absolute paths: `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/SPEC.md`, `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/pyproject.toml`, `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/src/osrs_planner/engine/`, `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/tests/engine/`.

---

### Task 2: The Result envelope (`engine/result.py`)

Build the standard answer envelope every Engine function returns: `Ok` / `Empty` / `Problem`, plus the closed `ProblemKind` / `TerminalReason` taxonomies and the `NodeRef` / `Refs` grounding carriers. This is the "single highest-leverage refinement" of the contract (§4) — nothing else in the engine can be written until functions have a shape to return. Pure stdlib (`dataclasses`, `enum`, `typing`); no third-party deps.

Reference: contract §4 (the `Result[T] = Ok | Empty | Problem` shape, the trimmed `ProblemKind`, `TerminalReason`, "`Empty` is a success state"), §5.1 (`Refs` is the grounding leash), §10 (error contract — which `ProblemKind` maps to which situation), §7.4 (every `Result` carries `refs`).

> Note on the spine vs. the prose contract: the type-spine fixes `Refs` as two `dict[str, NodeRef]` maps named `nodes` and `mentions` (engine-internal frozen dataclasses), and `TerminalReason` to the three engine-emittable terminals `ALREADY_SATISFIED` / `NO_FRONTIER` / `EMPTY_RESULT`. The §5.1 `about`/`mentions` *list* form and the §4 longer `TerminalReason` glosses are the JSON-projection wording (Task: cards); this task builds the internal spine exactly as named. `ProblemKind` matches §4's trimmed set verbatim.

**Files:**
- `src/osrs_planner/engine/__init__.py` (new — package marker)
- `src/osrs_planner/engine/result.py` (new — the envelope)
- `tests/engine/__init__.py` (new — test package marker)
- `tests/engine/test_result.py` (new — the failing-then-passing tests)

Run commands assume the repo venv (the project is editable-installed there; `pytest 9.0.2`, Python 3.14). All commands are run from the repo root `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool`.

- [ ] **Step 2.1 — Create the engine + test packages (scaffolding only, no logic).**
  Create the package markers so `osrs_planner.engine.result` and `tests/engine/` resolve. No test yet — this is a one-shot setup before the first red.

  `src/osrs_planner/engine/__init__.py`:
  ```python
  """Deterministic Gilded Tome goal-engine (Result envelope, Kleene, KG, conditions, cards)."""
  ```

  `tests/engine/__init__.py`:
  ```python
  ```
  (empty file — package marker so `tests/engine/test_*.py` import as a package)

  Verify both exist and the engine package imports:
  ```
  venv/bin/python -c "import osrs_planner.engine; print('engine pkg ok')"
  ```
  Expected output:
  ```
  engine pkg ok
  ```

- [ ] **Step 2.2 — RED: write `test_result.py` covering enums, NodeRef/Refs defaults, and Ok/Empty/Problem fields.**
  Write the full test module against the not-yet-existing `result.py`. Every assertion below is real (no stubs).

  `tests/engine/test_result.py`:
  ```python
  from dataclasses import FrozenInstanceError

  import pytest

  from osrs_planner.engine.result import (
      Empty,
      NodeRef,
      Ok,
      Problem,
      ProblemKind,
      Refs,
      Result,
      TerminalReason,
  )


  # --- ProblemKind: the closed failure taxonomy (contract §4, §10) ---

  def test_problemkind_members_exact():
      assert {k.value for k in ProblemKind} == {
          "not_found",
          "ambiguous",
          "invalid_target",
          "impossible_for_account",
          "missing_state",
          "unsatisfiable_cycle",
      }

  def test_problemkind_is_str_enum():
      # str-mixin: the value compares/serializes as the bare string
      assert ProblemKind.NOT_FOUND == "not_found"
      assert ProblemKind.NOT_FOUND.value == "not_found"


  # --- TerminalReason: Empty's "this is a success" reasons (contract §4) ---

  def test_terminalreason_members_exact():
      assert {r.value for r in TerminalReason} == {
          "already_satisfied",
          "no_frontier",
          "empty_result",
      }

  def test_terminalreason_is_str_enum():
      assert TerminalReason.ALREADY_SATISFIED == "already_satisfied"


  # --- NodeRef: the grounding atom ---

  def test_noderef_fields():
      ref = NodeRef(id="npc:7221", kind="monster", name="Scurrius")
      assert ref.id == "npc:7221"
      assert ref.kind == "monster"
      assert ref.name == "Scurrius"

  def test_noderef_frozen():
      ref = NodeRef(id="npc:7221", kind="monster", name="Scurrius")
      with pytest.raises(FrozenInstanceError):
          ref.id = "npc:0"  # type: ignore[misc]


  # --- Refs: two maps, each defaulting to an independent empty dict ---

  def test_refs_defaults_empty():
      refs = Refs()
      assert refs.nodes == {}
      assert refs.mentions == {}

  def test_refs_default_factory_not_shared():
      # default_factory must give each instance its OWN dict (no mutable-default bug)
      a = Refs()
      b = Refs()
      assert a.nodes is not b.nodes
      assert a.mentions is not b.mentions

  def test_refs_carries_node_and_mention_maps():
      n = NodeRef(id="skill:attack", kind="skill", name="Attack")
      m = NodeRef(id="activity:fight-caves", kind="activity", name="Fight Caves")
      refs = Refs(nodes={n.id: n}, mentions={m.id: m})
      assert refs.nodes["skill:attack"] is n
      assert refs.mentions["activity:fight-caves"] is m

  def test_refs_frozen():
      refs = Refs()
      with pytest.raises(FrozenInstanceError):
          refs.nodes = {}  # type: ignore[misc]


  # --- Ok[T]: carries the card + refs (contract §4) ---

  def test_ok_carries_card_and_refs():
      refs = Refs(nodes={"npc:7221": NodeRef("npc:7221", "monster", "Scurrius")})
      ok = Ok(card="any-card-payload", refs=refs)
      assert ok.card == "any-card-payload"
      assert ok.refs is refs

  def test_ok_is_generic_over_card_type():
      # Generic[T]: the payload may be any type; a list works as well as a str
      ok = Ok(card=[1, 2, 3], refs=Refs())
      assert ok.card == [1, 2, 3]

  def test_ok_frozen():
      ok = Ok(card=1, refs=Refs())
      with pytest.raises(FrozenInstanceError):
          ok.card = 2  # type: ignore[misc]


  # --- Empty: a SUCCESS state (status defaults to "ok"), with a TerminalReason ---

  def test_empty_is_success_with_reason():
      refs = Refs(nodes={"npc:7221": NodeRef("npc:7221", "monster", "Scurrius")})
      empty = Empty(refs=refs, reason=TerminalReason.ALREADY_SATISFIED)
      assert empty.status == "ok"        # Empty is NOT a failure
      assert empty.reason is TerminalReason.ALREADY_SATISFIED
      assert empty.refs is refs

  def test_empty_status_default_is_ok():
      empty = Empty(refs=Refs(), reason=TerminalReason.NO_FRONTIER)
      assert empty.status == "ok"

  def test_empty_frozen():
      empty = Empty(refs=Refs(), reason=TerminalReason.EMPTY_RESULT)
      with pytest.raises(FrozenInstanceError):
          empty.reason = TerminalReason.NO_FRONTIER  # type: ignore[misc]


  # --- Problem: the failure carrier (kind + refs + message) ---

  def test_problem_carries_kind_refs_message():
      refs = Refs(nodes={"npc:0": NodeRef("npc:0", "monster", "?")})
      prob = Problem(
          kind=ProblemKind.NOT_FOUND,
          refs=refs,
          message="no node 'npc:0'",
      )
      assert prob.kind is ProblemKind.NOT_FOUND
      assert prob.refs is refs
      assert prob.message == "no node 'npc:0'"

  def test_problem_frozen():
      prob = Problem(kind=ProblemKind.MISSING_STATE, refs=Refs(), message="x")
      with pytest.raises(FrozenInstanceError):
          prob.message = "y"  # type: ignore[misc]


  # --- Result alias: usable as a type annotation over all three variants ---

  def test_result_alias_admits_all_three_variants():
      values: list[Result] = [
          Ok(card="c", refs=Refs()),
          Empty(refs=Refs(), reason=TerminalReason.ALREADY_SATISFIED),
          Problem(kind=ProblemKind.AMBIGUOUS, refs=Refs(), message="2 candidates"),
      ]
      # the consumer pattern both projections use: branch on the concrete variant
      kinds = [type(v).__name__ for v in values]
      assert kinds == ["Ok", "Empty", "Problem"]
  ```

  Run (expect collection/import failure — `result.py` does not exist yet):
  ```
  venv/bin/python -m pytest tests/engine/test_result.py -q
  ```
  Expected output (abridged — the key line is the import error and zero passed):
  ```
   E   ModuleNotFoundError: No module named 'osrs_planner.engine.result'
  ...
  !!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
  1 error in 0.0Xs
  ```

- [ ] **Step 2.3 — GREEN: implement `engine/result.py` (the complete envelope).**
  Write the real module. `Ok` is generic over the card type `T`; `Refs` uses `default_factory` so each instance gets its own dicts; every dataclass is frozen; `Result` is a `Union` type alias.

  `src/osrs_planner/engine/result.py`:
  ```python
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
  from typing import Generic, TypeVar, Union

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
      status: str = "ok"


  @dataclass(frozen=True)
  class Problem:
      """A structured failure. No function raises to the transport (contract §4);
      FastAPI maps this to a 4xx body and the tool-schema surfaces the same shape."""

      kind: ProblemKind
      refs: Refs
      message: str


  # The envelope every Engine function returns. Consumers branch on the variant.
  Result = Union[Ok[T], Empty, Problem]
  ```

  Run (expect all green):
  ```
  venv/bin/python -m pytest tests/engine/test_result.py -q
  ```
  Expected output:
  ```
  ......................                                                   [100%]
  22 passed in 0.0Xs
  ```

- [ ] **Step 2.4 — Guard: full suite stays green (no regression in the existing planner/xp tests).**
  Confirm the new package didn't disturb collection of the legacy suite.
  ```
  venv/bin/python -m pytest -q
  ```
  Expected output (existing 6 + new 22; the trailing count is what matters):
  ```
  28 passed in 0.0Xs
  ```

- [ ] **Step 2.5 — Commit.**
  ```
  git add src/osrs_planner/engine/__init__.py src/osrs_planner/engine/result.py tests/engine/__init__.py tests/engine/test_result.py
  git commit -m "feat: Result envelope (Ok/Empty/Problem) for the goal-engine

  Adds engine/result.py per the engine-advisor contract §4: the Ok[T]/Empty/
  Problem envelope, the trimmed ProblemKind and TerminalReason taxonomies, and
  the NodeRef/Refs grounding carriers. Empty is a success terminal, not a
  failure. Pure stdlib; no new deps. Covered by tests/engine/test_result.py."
  ```

---

Notes for the plan author (paths are absolute):

- The contract §4 lives at `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/docs/superpowers/specs/2026-06-15-engine-advisor-contract-design.md`; the condition-atom/Refs semantics at `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/research/kg-schema-v1.md`.
- Run commands use the repo venv at `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/venv/bin/python -m pytest` (confirmed `pytest 9.0.2`, Python 3.14.2; `osrs_planner` is editable-installed there; the existing suite is 6 tests). networkx is NOT required for this task — it's introduced by the KG-store task; do not add it here.
- One deliberate deviation from the §4/§5.1 prose, flagged inline in the task: the spine fixes `Refs` as `nodes`/`mentions` **dicts** and `TerminalReason` to three engine-internal values, whereas §5.1 shows `about`/`mentions` **lists** and §4 lists four longer-glossed terminals. The task builds the spine names verbatim (as required) and documents that the §5.1/§4 wording is the pydantic-card JSON projection (a later "cards" task), so the two are not in conflict.

---

### Task 3: Three-valued Kleene logic (`engine/kleene.py`)

The engine's condition evaluator (Task 6) folds atom verdicts with three-valued (Kleene strong) logic so that *absent, unobservable* account data surfaces as `indeterminate` instead of a confident-but-wrong `locked` (contract §6, §6.4). This task TDD's the pure logic kernel: the `Tri` enum and the `k_and` / `k_or` / `k_not` / `from_bool` folds. The load-bearing rule from contract §6 — *"AND/OR/NOT fold UNKNOWN and surface it only when it flips the verdict"* — is exactly the dominance behavior: a `FALSE` dominates AND (so `k_and([FALSE, UNKNOWN]) == FALSE`), a `TRUE` dominates OR (so `k_or([TRUE, UNKNOWN]) == TRUE`), and `UNKNOWN` only escapes when no dominating value is present. This task has no dependencies on the rest of the spine and builds the bedrock the worked `(70 Att AND 70 Str) OR full-Void` example (kg-schema-v1.md §"Worked condition") relies on.

This task also bootstraps the `engine` package directory and the `tests/engine` directory, since this is the first engine brick.

**Files:**
- `src/osrs_planner/engine/__init__.py` (new — package marker)
- `src/osrs_planner/engine/kleene.py` (new — the `Tri` enum + folds)
- `tests/engine/__init__.py` (new — test package marker)
- `tests/engine/test_kleene.py` (new — exhaustive truth-table tests)

All commands are run from the repo root `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool`. Tests run with the project's venv pytest (`venv/bin/pytest`), which resolves imports as `from osrs_planner.engine... import ...` (matching the existing `tests/test_xp.py` convention).

---

- [ ] **Step 3.1 — Create the engine + test package skeletons.** These empty markers must exist before pytest can import `osrs_planner.engine.kleene` and `tests/engine/test_kleene.py`. Run:

  ```bash
  mkdir -p src/osrs_planner/engine tests/engine
  ```

  Then create both `__init__.py` files.

  `src/osrs_planner/engine/__init__.py`:
  ```python
  """Gilded Tome deterministic goal-engine (contract: docs/superpowers/specs/2026-06-15-engine-advisor-contract-design.md)."""
  ```

  `tests/engine/__init__.py`:
  ```python
  ```
  (empty file — just the marker)

  Verify the directories and markers exist:
  ```bash
  ls -la src/osrs_planner/engine/__init__.py tests/engine/__init__.py
  ```
  Expected output (both files listed, no error):
  ```
  -rw-r--r--  ... src/osrs_planner/engine/__init__.py
  -rw-r--r--  ... tests/engine/__init__.py
  ```

- [ ] **Step 3.2 — Failing test: the `Tri` enum members exist.** Write the first test asserting the three-valued enum and its three members. `Tri` is a plain `Enum` (per the spine — *not* a `str` enum), so members compare by identity.

  Create `tests/engine/test_kleene.py`:
  ```python
  from osrs_planner.engine.kleene import Tri, k_and, k_or, k_not, from_bool


  class TestTriEnum:
      def test_has_three_members(self):
          assert {m.name for m in Tri} == {"TRUE", "FALSE", "UNKNOWN"}

      def test_members_are_distinct(self):
          assert Tri.TRUE is not Tri.FALSE
          assert Tri.TRUE is not Tri.UNKNOWN
          assert Tri.FALSE is not Tri.UNKNOWN
  ```

  Run:
  ```bash
  venv/bin/pytest tests/engine/test_kleene.py -q
  ```
  Expected: collection/import error — the module does not exist yet:
  ```
  ModuleNotFoundError: No module named 'osrs_planner.engine.kleene'
  ```

- [ ] **Step 3.3 — Minimal impl: the `Tri` enum.** Create `src/osrs_planner/engine/kleene.py` with just the enum (folds added next so the import resolves and the first tests pass):

  ```python
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
  ```

  Run:
  ```bash
  venv/bin/pytest tests/engine/test_kleene.py -q
  ```
  Expected: the two `TestTriEnum` tests pass (the `from ... import k_and, k_or, k_not, from_bool` line still resolves because they are referenced only inside test bodies not yet written — the import will fail). To keep the import clean, the names must exist; add the import-only failure check by running and confirming:
  ```
  ImportError: cannot import name 'k_and' from 'osrs_planner.engine.kleene'
  ```
  This is the expected FAIL that drives Step 3.4 (the test module's top-level import of all four functions cannot resolve until they exist). Proceed to add the functions.

- [ ] **Step 3.4 — Failing tests: `from_bool` and `k_not` truth tables.** Append to `tests/engine/test_kleene.py`:

  ```python
  class TestFromBool:
      def test_true(self):
          assert from_bool(True) is Tri.TRUE

      def test_false(self):
          assert from_bool(False) is Tri.FALSE


  class TestKNot:
      def test_not_true_is_false(self):
          assert k_not(Tri.TRUE) is Tri.FALSE

      def test_not_false_is_true(self):
          assert k_not(Tri.FALSE) is Tri.TRUE

      def test_not_unknown_is_unknown(self):
          # UNKNOWN never flips -- negation can't resolve it.
          assert k_not(Tri.UNKNOWN) is Tri.UNKNOWN
  ```

  Run:
  ```bash
  venv/bin/pytest tests/engine/test_kleene.py -q
  ```
  Expected FAIL (import of `from_bool`/`k_not` still unresolved at module load):
  ```
  ImportError: cannot import name 'from_bool' from 'osrs_planner.engine.kleene'
  ```

- [ ] **Step 3.5 — Minimal impl: `from_bool` and `k_not`.** Append to `src/osrs_planner/engine/kleene.py`:

  ```python
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
  ```

  Run:
  ```bash
  venv/bin/pytest tests/engine/test_kleene.py::TestFromBool tests/engine/test_kleene.py::TestKNot tests/engine/test_kleene.py::TestTriEnum -q
  ```
  Expected: the `Tri`, `from_bool`, and `k_not` tests pass (the `k_and`/`k_or` import names are still unresolved at module top, so the whole-file run still errors — that's expected and drives the next step). Confirm the targeted classes report:
  ```
  7 passed
  ```
  (If pytest still reports the module-level ImportError even for targeted classes, that is the import of `k_and`/`k_or` failing at collection; proceed to Step 3.6 — those are added next.)

- [ ] **Step 3.6 — Failing tests: `k_and` full truth table + dominance/flip cases.** Append to `tests/engine/test_kleene.py`. This covers all 9 two-element pairings plus the empty-fold identity and the variadic-iterable contract, with explicit comments on where UNKNOWN is absorbed vs. surfaced:

  ```python
  class TestKAnd:
      # --- all-definite (classical) ---
      def test_true_true(self):
          assert k_and([Tri.TRUE, Tri.TRUE]) is Tri.TRUE

      def test_true_false(self):
          assert k_and([Tri.TRUE, Tri.FALSE]) is Tri.FALSE

      def test_false_false(self):
          assert k_and([Tri.FALSE, Tri.FALSE]) is Tri.FALSE

      # --- FALSE dominates: UNKNOWN is ABSORBED (does not flip the verdict) ---
      def test_false_unknown_is_false(self):
          # §6: a known-FALSE clause locks AND to FALSE; UNKNOWN can't rescue it.
          assert k_and([Tri.FALSE, Tri.UNKNOWN]) is Tri.FALSE

      def test_unknown_false_is_false(self):
          assert k_and([Tri.UNKNOWN, Tri.FALSE]) is Tri.FALSE

      # --- no FALSE present: UNKNOWN SURFACES (it flips a would-be TRUE) ---
      def test_true_unknown_is_unknown(self):
          # All others TRUE, one UNKNOWN -> can't claim TRUE -> UNKNOWN.
          assert k_and([Tri.TRUE, Tri.UNKNOWN]) is Tri.UNKNOWN

      def test_unknown_unknown_is_unknown(self):
          assert k_and([Tri.UNKNOWN, Tri.UNKNOWN]) is Tri.UNKNOWN

      # --- variadic / fold shape ---
      def test_all_true_three(self):
          assert k_and([Tri.TRUE, Tri.TRUE, Tri.TRUE]) is Tri.TRUE

      def test_false_anywhere_dominates(self):
          assert k_and([Tri.TRUE, Tri.UNKNOWN, Tri.FALSE, Tri.TRUE]) is Tri.FALSE

      def test_empty_is_true(self):
          # Empty conjunction = identity TRUE (vacuously satisfied).
          assert k_and([]) is Tri.TRUE

      def test_accepts_generator(self):
          # Signature is Iterable[Tri], not list -- must consume any iterable.
          assert k_and(t for t in (Tri.TRUE, Tri.FALSE)) is Tri.FALSE
  ```

  Run:
  ```bash
  venv/bin/pytest tests/engine/test_kleene.py -q
  ```
  Expected FAIL — `k_and` is not importable yet:
  ```
  ImportError: cannot import name 'k_and' from 'osrs_planner.engine.kleene'
  ```

- [ ] **Step 3.7 — Minimal impl: `k_and`.** Append to `src/osrs_planner/engine/kleene.py`. One pass over the iterable: any `FALSE` short-circuits to `FALSE` (dominance); otherwise track whether any `UNKNOWN` was seen; absent both, the conjunction is `TRUE`:

  ```python
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
  ```

  Run:
  ```bash
  venv/bin/pytest tests/engine/test_kleene.py -q
  ```
  Expected: all `TestKAnd` tests now pass; `k_or` import names are still unresolved so the full-file run errors at collection. Run the `k_and` class directly to confirm:
  ```bash
  venv/bin/pytest tests/engine/test_kleene.py::TestKAnd -q
  ```
  Expected:
  ```
  11 passed
  ```

- [ ] **Step 3.8 — Failing tests: `k_or` full truth table + dominance/flip cases.** Append to `tests/engine/test_kleene.py`. Symmetric to `k_and`: `TRUE` dominates, empty-fold identity is `FALSE`:

  ```python
  class TestKOr:
      # --- all-definite (classical) ---
      def test_true_true(self):
          assert k_or([Tri.TRUE, Tri.TRUE]) is Tri.TRUE

      def test_true_false(self):
          assert k_or([Tri.TRUE, Tri.FALSE]) is Tri.TRUE

      def test_false_false(self):
          assert k_or([Tri.FALSE, Tri.FALSE]) is Tri.FALSE

      # --- TRUE dominates: UNKNOWN is ABSORBED (does not flip the verdict) ---
      def test_true_unknown_is_true(self):
          # §6: a known-TRUE alternative satisfies OR; UNKNOWN is irrelevant.
          # This is the worked-example shape: OR(known-true, can't-verify) == TRUE.
          assert k_or([Tri.TRUE, Tri.UNKNOWN]) is Tri.TRUE

      def test_unknown_true_is_true(self):
          assert k_or([Tri.UNKNOWN, Tri.TRUE]) is Tri.TRUE

      # --- no TRUE present: UNKNOWN SURFACES (it flips a would-be FALSE) ---
      def test_false_unknown_is_unknown(self):
          # No satisfied alternative, but one we can't rule out -> UNKNOWN.
          assert k_or([Tri.FALSE, Tri.UNKNOWN]) is Tri.UNKNOWN

      def test_unknown_unknown_is_unknown(self):
          assert k_or([Tri.UNKNOWN, Tri.UNKNOWN]) is Tri.UNKNOWN

      # --- variadic / fold shape ---
      def test_all_false_three(self):
          assert k_or([Tri.FALSE, Tri.FALSE, Tri.FALSE]) is Tri.FALSE

      def test_true_anywhere_dominates(self):
          assert k_or([Tri.FALSE, Tri.UNKNOWN, Tri.TRUE, Tri.FALSE]) is Tri.TRUE

      def test_empty_is_false(self):
          # Empty disjunction = identity FALSE (no alternative satisfies it).
          assert k_or([]) is Tri.FALSE

      def test_accepts_generator(self):
          assert k_or(t for t in (Tri.FALSE, Tri.TRUE)) is Tri.TRUE
  ```

  Run:
  ```bash
  venv/bin/pytest tests/engine/test_kleene.py -q
  ```
  Expected FAIL — `k_or` not importable yet:
  ```
  ImportError: cannot import name 'k_or' from 'osrs_planner.engine.kleene'
  ```

- [ ] **Step 3.9 — Minimal impl: `k_or`.** Append to `src/osrs_planner/engine/kleene.py`:

  ```python
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
  ```

  Run the full file — every test should now pass:
  ```bash
  venv/bin/pytest tests/engine/test_kleene.py -q
  ```
  Expected:
  ```
  37 passed
  ```

- [ ] **Step 3.10 — Regression + duality sanity check.** Confirm the new module didn't break the existing suite and that De Morgan duality holds across the kernel (a cheap structural check that `k_and`/`k_or`/`k_not` are mutually consistent). Append one parametrized test to `tests/engine/test_kleene.py`:

  ```python
  import itertools
  import pytest


  @pytest.mark.parametrize("a,b", itertools.product(list(Tri), repeat=2))
  def test_de_morgan_duality(a, b):
      # NOT(a AND b) == (NOT a) OR (NOT b), and dually -- must hold for all 9 pairs.
      assert k_not(k_and([a, b])) is k_or([k_not(a), k_not(b)])
      assert k_not(k_or([a, b])) is k_and([k_not(a), k_not(b)])
  ```

  Run the whole project suite:
  ```bash
  venv/bin/pytest -q
  ```
  Expected: all previously-passing tests plus the new engine tests pass (the `test_de_morgan_duality` parametrization adds 9 cases). The engine file count is `37 + 9 = 46` engine tests, with the pre-existing `tests/test_xp.py` / `tests/test_planner.py` still green:
  ```
  ... passed
  ```
  (No failures, no errors.)

- [ ] **Step 3.11 — Commit.** Stage the new engine package, the test package, and run:

  ```bash
  git add src/osrs_planner/engine/__init__.py src/osrs_planner/engine/kleene.py tests/engine/__init__.py tests/engine/test_kleene.py
  git commit -m "feat(engine): three-valued Kleene logic kernel (Tri, k_and/k_or/k_not/from_bool)

Implements contract §6 three-valued evaluation primitives: FALSE dominates
AND, TRUE dominates OR, UNKNOWN surfaces only when it flips the verdict.
Exhaustive truth-table + De Morgan duality tests under tests/engine/.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
  ```

  Verify the commit landed and the tree is clean for these paths:
  ```bash
  git log --oneline -1 && git status --short src/osrs_planner/engine tests/engine
  ```
  Expected: the new commit at HEAD; no unstaged/untracked changes under those two paths (clean).

---

Notes for the plan author / implementer:
- Relevant absolute paths: code `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/src/osrs_planner/engine/kleene.py`; tests `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/tests/engine/test_kleene.py`.
- `Tri` is a plain `Enum` (members compared with `is`), per the type-spine — deliberately *not* a `str`-mixin enum like the other engine enums, because it is never serialized across the contract boundary (it's an internal eval value; cards carry the projected `status` strings instead).
- The dominance semantics here are the exact mechanism behind contract §6's "surface UNKNOWN only when it flips the verdict" and the kg-schema worked example's `OR( AND(75≥70=T, 60≥70=F)=F, gear_loadout(void)=F ) = False` (all-definite path) — when a Void piece is *unobservable* instead, that leaf becomes `UNKNOWN` and `k_or` will surface `indeterminate` rather than a false `locked`. Task 6 (`conditions.evaluate`) consumes this kernel; Task 5/state supplies the per-leaf `Tri`.
- Empty-fold identities (`k_and([])==TRUE`, `k_or([])==FALSE`) match I5's grammar guarantee that `AND`/`OR` groups carry ≥1 child in practice, but are defined for safety and tested explicitly.
- Per-step pytest run notes: because `test_kleene.py` imports all four functions at module top, intermediate steps (3.3–3.8) will report a collection-time `ImportError` until the named function exists — this is the intended red state of each TDD step; the "expected output" lines above call this out at each step.

---

### Task 4: KG data model — Node / Edge / ConditionGroup / ConditionAtom + the locked enums

The static knowledge-graph is the engine's spine. This task builds the frozen, immutable Python value types that mirror `kg-schema-v1.md`'s node/edge/condition tables, plus the four closed enums (`NodeKind`, `EdgeType`, `Op`, `AtomType`). Nothing here traverses or evaluates — it is the data shape that Task 5 (`KGStore`) loads and Task 7 (`conditions.evaluate`) reads. The locked atom set is the load-bearing detail: it must include `GEAR_LOADOUT`, the 3-state quest/diary semantics carried in `ConditionAtom.data['state']`, and the deliberate split between the **binary** `COMBAT_ACHIEVEMENT` (per-task done/not, schema §"`combat_achievement` scope") and the **accumulator** `COMBAT_ACHIEVEMENT_POINTS` (tier reached via a point total). Frozen-ness matters: the KG is global static data shared across all accounts/requests (schema principle (c)), so these instances must be hashable and tamper-proof.

All enums subclass `str` (except `Op`/`NodeKind`/etc. per spine: `NodeKind`, `EdgeType`, `AtomType` are `str`-enums; `Op` is `str`-enum too) so values serialize directly to JSON/SQL `TEXT` and compare equal to their raw string. `ConditionGroup.children` holds a heterogeneous list of child-group **ids** (`int`) and `ConditionAtom` **objects** — this is the exact shape `conditions.evaluate` folds over in a later task.

**Files:**
- `src/osrs_planner/engine/__init__.py` (new, empty package marker)
- `src/osrs_planner/engine/kg/__init__.py` (new, empty package marker)
- `src/osrs_planner/engine/kg/model.py` (new — the enums + four frozen dataclasses)
- `tests/engine/__init__.py` (new, empty package marker)
- `tests/engine/test_kg_model.py` (new — the failing-then-passing tests)

Run commands assume the repo venv (`./venv/bin/python -m pytest`, which is how the existing suite runs); all paths are relative to the repo root `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool`.

---

- [ ] **Step 1 — Create the engine package skeleton.** These empty `__init__.py` files make `osrs_planner.engine`, `osrs_planner.engine.kg`, and the `tests.engine` test package importable. Create all four:

  `src/osrs_planner/engine/__init__.py`:
  ```python
  ```
  `src/osrs_planner/engine/kg/__init__.py`:
  ```python
  ```
  `tests/engine/__init__.py`:
  ```python
  ```
  (Each file is intentionally empty — a zero-byte package marker.)

  Run (expect: collected, the test dir exists but has no tests yet → "no tests ran"):
  ```
  ./venv/bin/python -m pytest tests/engine/ -q
  ```
  Expected output (substring): `no tests ran`

- [ ] **Step 2 — Write the failing test for the four closed enums.** This pins the EXACT locked member sets from `kg-schema-v1.md` (node taxonomy table + edge-type table + `condition_group.op` CHECK + `condition_atom.atom_type` CHECK). Note `COMBAT_ACHIEVEMENT` (binary task) and `COMBAT_ACHIEVEMENT_POINTS` (accumulator) are BOTH present and distinct — the de-overload fix. Each enum is a `str` subclass so `NodeKind.SKILL == "skill"`.

  Create `tests/engine/test_kg_model.py`:
  ```python
  from osrs_planner.engine.kg.model import (
      NodeKind, EdgeType, Op, AtomType,
      Node, ConditionAtom, ConditionGroup, Edge,
  )


  def test_node_kind_members_match_schema_taxonomy():
      assert {k.value for k in NodeKind} == {
          "skill", "item", "monster", "quest", "access", "region",
          "account_type", "gear_loadout", "activity", "diary",
          "combat_achievement", "minigame", "clog_slot",
      }


  def test_node_kind_is_str_enum():
      assert NodeKind.SKILL == "skill"
      assert isinstance(NodeKind.SKILL, str)


  def test_edge_type_members_match_schema():
      assert {e.value for e in EdgeType} == {
          "requires", "grants", "drops", "located_in", "gated_by",
      }


  def test_op_members():
      assert {o.value for o in Op} == {"and", "or", "not"}


  def test_atom_type_locked_set_includes_gear_loadout_and_ca_split():
      values = {a.value for a in AtomType}
      assert values == {
          "skill_level", "skill_xp", "combat_level", "quest",
          "achievement_diary", "combat_achievement", "item",
          "is_unlocked", "gear_loadout", "kill_count", "quest_points",
          "account_type", "clue_scrolls", "combat_achievement_points",
      }
      # the de-overload (schema §"combat_achievement scope"): the binary
      # per-task atom and the accumulator tier-points atom are DISTINCT members.
      assert AtomType.COMBAT_ACHIEVEMENT != AtomType.COMBAT_ACHIEVEMENT_POINTS
  ```

  Run (expect: FAIL — `model.py` does not exist yet → ModuleNotFoundError at collection):
  ```
  ./venv/bin/python -m pytest tests/engine/test_kg_model.py -q
  ```
  Expected output (substring): `ModuleNotFoundError: No module named 'osrs_planner.engine.kg.model'`

- [ ] **Step 3 — Implement the four enums (minimal, to green Step 2).** Member NAMES are upper-snake of the value; the value is the schema's `TEXT` string. `Op` values are lowercase (`"and"`/`"or"`/`"not"`) to match the test; the SQL CHECK stores them uppercase, but the in-memory enum value is the engine's contract — keep it consistent with the test above.

  Create `src/osrs_planner/engine/kg/model.py`:
  ```python
  """KG static value types — frozen, hashable, JSON/SQL-serializable.

  Mirrors the node/edge/condition tables of research/kg-schema-v1.md. These
  instances are GLOBAL static game-data shared across all accounts and requests
  (schema principle (c)), so every type is a frozen dataclass and every enum is
  a str-subclass (its .value is the SQL TEXT column verbatim).
  """
  from __future__ import annotations

  from dataclasses import dataclass, field
  from enum import Enum
  from typing import Optional


  class NodeKind(str, Enum):
      """node.kind closed enum (schema: type taxonomy). v1-CORE + id-reserved kinds."""
      SKILL = "skill"
      ITEM = "item"
      MONSTER = "monster"
      QUEST = "quest"
      ACCESS = "access"
      REGION = "region"
      ACCOUNT_TYPE = "account_type"
      GEAR_LOADOUT = "gear_loadout"
      ACTIVITY = "activity"
      DIARY = "diary"
      COMBAT_ACHIEVEMENT = "combat_achievement"
      MINIGAME = "minigame"
      CLOG_SLOT = "clog_slot"


  class EdgeType(str, Enum):
      """The 5 FACT edge types (schema: fact edge-type table). Opinion edges
      (recommended_for / recommended_method) are out of the engine's fact spine."""
      REQUIRES = "requires"
      GRANTS = "grants"
      DROPS = "drops"
      LOCATED_IN = "located_in"
      GATED_BY = "gated_by"


  class Op(str, Enum):
      """condition_group.op (schema: CHECK op IN AND/OR/NOT). NOT => exactly one child."""
      AND = "and"
      OR = "or"
      NOT = "not"


  class AtomType(str, Enum):
      """condition_atom.atom_type closed enum (schema: condition_atom CHECK +
      atom-semantics list). COMBAT_ACHIEVEMENT (binary per-task) and
      COMBAT_ACHIEVEMENT_POINTS (accumulator tier total) are deliberately split."""
      SKILL_LEVEL = "skill_level"
      SKILL_XP = "skill_xp"
      COMBAT_LEVEL = "combat_level"
      QUEST = "quest"
      ACHIEVEMENT_DIARY = "achievement_diary"
      COMBAT_ACHIEVEMENT = "combat_achievement"
      ITEM = "item"
      IS_UNLOCKED = "is_unlocked"
      GEAR_LOADOUT = "gear_loadout"
      KILL_COUNT = "kill_count"
      QUEST_POINTS = "quest_points"
      ACCOUNT_TYPE = "account_type"
      CLUE_SCROLLS = "clue_scrolls"
      COMBAT_ACHIEVEMENT_POINTS = "combat_achievement_points"
  ```

  Run (expect: PASS — the 5 enum tests green):
  ```
  ./venv/bin/python -m pytest tests/engine/test_kg_model.py -q
  ```
  Expected output (substring): `5 passed`

- [ ] **Step 4 — Write the failing test for `Node` (the spine row).** `Node` mirrors the `node` table: `id`, `kind` (a `NodeKind`), `name`, `slug`, and a `data` JSON-blob dict that defaults to empty. It must be frozen (hashable, immutable) since it is shared static data.

  Append to `tests/engine/test_kg_model.py`:
  ```python


  import dataclasses
  import pytest


  def test_node_construction_and_data_default():
      n = Node(id="npc:7221", kind=NodeKind.MONSTER, name="Scurrius", slug="scurrius")
      assert n.id == "npc:7221"
      assert n.kind is NodeKind.MONSTER
      assert n.name == "Scurrius"
      assert n.slug == "scurrius"
      assert n.data == {}  # default_factory(dict)


  def test_node_carries_data_blob():
      n = Node(
          id="gear_loadout:void", kind=NodeKind.GEAR_LOADOUT, name="Full Void",
          slug="void", data={"styles": ["melee", "ranged", "magic"]},
      )
      assert n.data["styles"] == ["melee", "ranged", "magic"]


  def test_node_is_frozen():
      n = Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack")
      with pytest.raises(dataclasses.FrozenInstanceError):
          n.name = "Strength"  # type: ignore[misc]


  def test_node_data_default_is_not_shared():
      a = Node(id="access:a", kind=NodeKind.ACCESS, name="A", slug="a")
      b = Node(id="access:b", kind=NodeKind.ACCESS, name="B", slug="b")
      assert a.data is not b.data  # default_factory, not a shared mutable default
  ```

  Run (expect: FAIL — `Node` not yet defined → ImportError, OR `TypeError`/`NameError` on construction):
  ```
  ./venv/bin/python -m pytest tests/engine/test_kg_model.py -q
  ```
  Expected output (substring): `ImportError: cannot import name 'Node'`

- [ ] **Step 5 — Implement `Node`.** Append to `src/osrs_planner/engine/kg/model.py`:
  ```python


  @dataclass(frozen=True)
  class Node:
      """A row of the `node` spine (schema: Node model). One row per game entity.
      `data` is the kind-specific JSON blob the engine does NOT hot-filter
      (e.g. account_type {'must_self_acquire','can_ge'}, diary {'region','tier'})."""
      id: str
      kind: NodeKind
      name: str
      slug: str
      data: dict = field(default_factory=dict)
  ```

  Run (expect: PASS — the 4 new Node tests + 5 enum tests):
  ```
  ./venv/bin/python -m pytest tests/engine/test_kg_model.py -q
  ```
  Expected output (substring): `9 passed`

- [ ] **Step 6 — Write the failing test for `ConditionAtom` (the leaf predicate).** `ConditionAtom` mirrors `condition_atom`: an `atom_type` plus the optional fields different atom families use. Per the schema's atom-semantics list, `data` carries the non-scalar payloads: quest/diary `state`, `account_type` `value`, `clue_scrolls` `set_ref`. `ref_node`, `threshold`, `qty` are all optional (ref-less atoms like `quest_points`/`combat_level`/`clue_scrolls` carry no `ref_node`). Frozen.

  Append to `tests/engine/test_kg_model.py`:
  ```python


  def test_atom_skill_level_minimal():
      a = ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=70)
      assert a.atom_type is AtomType.SKILL_LEVEL
      assert a.ref_node == "skill:attack"
      assert a.threshold == 70
      assert a.qty is None
      assert a.data == {}


  def test_atom_refless_quest_points():
      # accumulator atoms (schema: quest_points / combat_achievement_points) carry no ref_node
      a = ConditionAtom(atom_type=AtomType.QUEST_POINTS, threshold=32)
      assert a.ref_node is None
      assert a.threshold == 32


  def test_atom_quest_state_in_data():
      # schema atom-semantics: quest 3-state lives in data['state'] (ORDERED enum)
      a = ConditionAtom(
          atom_type=AtomType.QUEST, ref_node="quest:dragon-slayer-i",
          data={"state": "completed"},
      )
      assert a.data["state"] == "completed"


  def test_atom_account_type_value_in_data():
      a = ConditionAtom(atom_type=AtomType.ACCOUNT_TYPE, data={"value": "ironman"})
      assert a.data["value"] == "ironman"


  def test_atom_clue_scrolls_set_ref_and_threshold():
      a = ConditionAtom(
          atom_type=AtomType.CLUE_SCROLLS, threshold=2,
          data={"set_ref": ["item:2677", "item:2801"]},
      )
      assert a.threshold == 2
      assert a.data["set_ref"] == ["item:2677", "item:2801"]


  def test_atom_item_uses_qty():
      a = ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8839", qty=1)
      assert a.qty == 1


  def test_atom_gear_loadout_refs_loadout_node():
      a = ConditionAtom(atom_type=AtomType.GEAR_LOADOUT, ref_node="gear_loadout:void")
      assert a.ref_node == "gear_loadout:void"
      assert a.threshold is None


  def test_atom_is_frozen():
      a = ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=70)
      with pytest.raises(dataclasses.FrozenInstanceError):
          a.threshold = 60  # type: ignore[misc]
  ```

  Run (expect: FAIL — `ConditionAtom` not yet defined → ImportError):
  ```
  ./venv/bin/python -m pytest tests/engine/test_kg_model.py -q
  ```
  Expected output (substring): `ImportError: cannot import name 'ConditionAtom'`

- [ ] **Step 7 — Implement `ConditionAtom`.** All fields after `atom_type` are optional; `data` is a default-factory dict. Append to `src/osrs_planner/engine/kg/model.py`:
  ```python


  @dataclass(frozen=True)
  class ConditionAtom:
      """A leaf of a condition tree (schema: condition_atom). One testable
      predicate. `data` carries non-scalar payloads per the atom-semantics list:
      quest/diary 'state' (3-state ORDERED enum), account_type 'value',
      clue_scrolls 'set_ref' (list of node ids). ref_node/threshold/qty are
      optional because ref-less atoms (quest_points, combat_level, clue_scrolls,
      combat_achievement_points) carry none of them."""
      atom_type: AtomType
      ref_node: Optional[str] = None
      threshold: Optional[int] = None
      qty: Optional[int] = None
      data: dict = field(default_factory=dict)
  ```

  Run (expect: PASS — the 8 new atom tests + 9 prior):
  ```
  ./venv/bin/python -m pytest tests/engine/test_kg_model.py -q
  ```
  Expected output (substring): `17 passed`

- [ ] **Step 8 — Write the failing test for `ConditionGroup` (the boolean tree node).** `ConditionGroup` mirrors `condition_group`: an integer `id`, an `Op`, an optional `parent` id (NULL ⇒ root), and `children` — a heterogeneous list of child-group **ids** (`int`) AND `ConditionAtom` objects. This mixed-list shape is exactly what `conditions.evaluate` will fold (Task 7), so the test encodes the flagship `(70 Att AND 70 Str) OR full-Void` structure from the schema's worked example: a root OR group whose children are two child-group ids (the AND-of-stats and the AND-of-void), demonstrating int children; and a leaf group holding `ConditionAtom`s. Frozen.

  Append to `tests/engine/test_kg_model.py`:
  ```python


  def test_group_with_atom_children():
      # G_stats from the schema worked example: AND(70 Att, 70 Str)
      g = ConditionGroup(
          id=2, op=Op.AND, parent=1,
          children=[
              ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=70),
              ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:strength", threshold=70),
          ],
      )
      assert g.id == 2
      assert g.op is Op.AND
      assert g.parent == 1
      assert len(g.children) == 2
      assert all(isinstance(c, ConditionAtom) for c in g.children)


  def test_group_children_can_mix_ids_and_atoms():
      # G_root from the worked example: OR( <group 2>, <group 3> ) — children are ints
      root = ConditionGroup(id=1, op=Op.OR, parent=None, children=[2, 3])
      assert root.parent is None  # NULL => root
      assert root.children == [2, 3]
      assert all(isinstance(c, int) for c in root.children)


  def test_group_mixed_int_and_atom_children():
      mixed = ConditionGroup(
          id=99, op=Op.AND, parent=None,
          children=[10, ConditionAtom(atom_type=AtomType.QUEST_POINTS, threshold=32)],
      )
      assert mixed.children[0] == 10
      assert isinstance(mixed.children[1], ConditionAtom)


  def test_group_is_frozen():
      g = ConditionGroup(id=1, op=Op.OR, parent=None, children=[2, 3])
      with pytest.raises(dataclasses.FrozenInstanceError):
          g.op = Op.AND  # type: ignore[misc]
  ```

  Run (expect: FAIL — `ConditionGroup` not yet defined → ImportError):
  ```
  ./venv/bin/python -m pytest tests/engine/test_kg_model.py -q
  ```
  Expected output (substring): `ImportError: cannot import name 'ConditionGroup'`

- [ ] **Step 9 — Implement `ConditionGroup`.** `children` has no default (every group is constructed with its child list). Append to `src/osrs_planner/engine/kg/model.py`:
  ```python


  @dataclass(frozen=True)
  class ConditionGroup:
      """An internal node of a condition tree (schema: condition_group).
      `children` is a heterogeneous list of child-group ids (int) and/or
      ConditionAtom objects — the exact shape conditions.evaluate folds over.
      parent is None for the root. NOT => exactly one child (enforced by load-time
      QA invariant I5, not here)."""
      id: int
      op: Op
      parent: Optional[int]
      children: list
  ```

  Run (expect: PASS — the 4 new group tests + 17 prior):
  ```
  ./venv/bin/python -m pytest tests/engine/test_kg_model.py -q
  ```
  Expected output (substring): `21 passed`

- [ ] **Step 10 — Write the failing test for `Edge` (the fact edge row).** `Edge` mirrors the `edge` table reduced to the engine's fact spine: integer `id`, an `EdgeType`, `src` node id, an OPTIONAL `dst` (NULL when the constraint IS the condition tree — e.g. the `(70 Att AND 70 Str) OR full-Void` requires edge and gear_loadout compositions), and an optional `cond_group` id (NULL ⇒ unconditional). Frozen. The test encodes both a plain unconditional edge and the dst=NULL pure-condition edge from the schema.

  Append to `tests/engine/test_kg_model.py`:
  ```python


  def test_edge_plain_unconditional():
      # schema worked example: requires npc:7221 -> access:scurrius-lair (unconditional)
      e = Edge(id=9004, type=EdgeType.REQUIRES, src="npc:7221", dst="access:scurrius-lair")
      assert e.id == 9004
      assert e.type is EdgeType.REQUIRES
      assert e.src == "npc:7221"
      assert e.dst == "access:scurrius-lair"
      assert e.cond_group is None  # unconditional default


  def test_edge_dst_null_pure_condition():
      # schema: requires edge whose dst IS NULL because the constraint is the cond tree
      e = Edge(id=9000, type=EdgeType.REQUIRES, src="npc:7221", dst=None, cond_group=1)
      assert e.dst is None
      assert e.cond_group == 1


  def test_edge_gear_loadout_composition():
      # schema: gear_loadout:void carries its composition on a dst=NULL requires edge
      e = Edge(id=9100, type=EdgeType.REQUIRES, src="gear_loadout:void", dst=None, cond_group=10)
      assert e.src == "gear_loadout:void"
      assert e.dst is None
      assert e.cond_group == 10


  def test_edge_is_frozen():
      e = Edge(id=9004, type=EdgeType.REQUIRES, src="npc:7221", dst="access:scurrius-lair")
      with pytest.raises(dataclasses.FrozenInstanceError):
          e.dst = "region:varrock"  # type: ignore[misc]
  ```

  Run (expect: FAIL — `Edge` not yet defined → ImportError):
  ```
  ./venv/bin/python -m pytest tests/engine/test_kg_model.py -q
  ```
  Expected output (substring): `ImportError: cannot import name 'Edge'`

- [ ] **Step 11 — Implement `Edge`.** `dst` and `cond_group` are optional. Append to `src/osrs_planner/engine/kg/model.py`:
  ```python


  @dataclass(frozen=True)
  class Edge:
      """A FACT edge (schema: edge table, fact subset). Direction: requires reads
      `src needs dst`; producer edges read `src -> produced`. `dst` is None for a
      pure-condition edge (the constraint IS the cond_group tree, e.g. the
      `(70 Att AND 70 Str) OR full-Void` requires edge and gear_loadout
      compositions). `cond_group` None => unconditional; multiple requires
      edges out of one src are implicitly AND-ed (D5: is_unlocked folds ALL
      requires edges)."""
      id: int
      type: EdgeType
      src: str
      dst: Optional[str] = None
      cond_group: Optional[int] = None
  ```

  Run (expect: PASS — the full file green):
  ```
  ./venv/bin/python -m pytest tests/engine/test_kg_model.py -q
  ```
  Expected output (substring): `25 passed`

- [ ] **Step 12 — Full-suite regression check.** Confirm the new engine model did not break the existing curriculum-era suite and that everything collects under the venv:
  ```
  ./venv/bin/python -m pytest -q
  ```
  Expected: all tests pass (the prior `tests/test_xp.py` + `tests/test_planner.py` plus the new `25 passed` in `tests/engine/`), no errors, no collection failures.

- [ ] **Step 13 — Commit.** Stage the new engine package, the model module, and the test package:
  ```
  git add src/osrs_planner/engine/__init__.py src/osrs_planner/engine/kg/__init__.py src/osrs_planner/engine/kg/model.py tests/engine/__init__.py tests/engine/test_kg_model.py
  git commit -m "feat: KG static value types (Node/Edge/ConditionGroup/ConditionAtom + locked enums)"
  ```
  Expected output (substring): `5 files changed` and the commit hash printed.

---

Notes for the plan author / implementer:
- **Run command:** the repo has no global `pytest`; the venv at `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/venv` runs the existing suite. All run lines use `./venv/bin/python -m pytest …` from the repo root. If the plan standardizes on a different invocation (e.g. `pytest` once the venv is activated), apply it uniformly across all engine tasks.
- **No new dependencies in this task.** `model.py` is pure stdlib (`dataclasses`, `enum`, `typing`). `networkx` (the new dependency named in the spine) is introduced by the later `store.py`/`requires_dag` task, and `pydantic` (already in `pyproject.toml`, present in the venv as 2.12.5) by the later `cards.py` task — neither is needed here.
- **`Op` value casing:** the in-memory enum values are lowercase (`"and"/"or"/"not"`) per the tests; the schema's SQL `CHECK` stores them uppercase (`AND/OR/NOT`). The loader (Task 5, `InMemoryKGStore`/future ingest) is responsible for normalizing SQL `TEXT` → `Op`; this task fixes the in-memory contract only. If a later task standardizes on uppercase enum values, the spine signature (`Op(str, Enum)`) is unchanged — only the member value strings and these four `Op` assertions move.
- **Why frozen:** I1/I5/I6/I18 and the global-static-data principle (schema (c)) require these instances to be immutable and hashable so a single loaded KG can be safely shared across all account overlays without defensive copying.

---

### Task 5: KG store + graph projection (`engine/kg/store.py`)

Builds the `KGStore` interface and its `InMemoryKGStore` implementation: holds nodes/edges/groups; `node()` / `children_of()` / `composition_of()` lookups; the `requires_dag()` NetworkX projection (`requires` edges + grant-flip cycle-only synthetics + ref-bearing cond-leaf `cond_dep` edges, direction `a→b` = "a requires b"); `descendants()` / `topo_order()`; and `find_cycles()` (invariant **I1**). All test graphs are tiny inline fixtures (2–3 nodes, one `requires` edge, one cond-leaf) — they do **not** depend on the large hand-authored KG fixture (that is Task 8).

Prereqs: Tasks 1–2 created `src/osrs_planner/engine/__init__.py`, `src/osrs_planner/engine/kg/__init__.py`, and `src/osrs_planner/engine/kg/model.py` (the `Node`, `Edge`, `ConditionGroup`, `ConditionAtom`, `NodeKind`, `EdgeType`, `Op`, `AtomType` types). `networkx` is a **new dependency**.

**Files:**
- `pyproject.toml` (edit — add `networkx` dependency)
- `src/osrs_planner/engine/kg/store.py` (new)
- `tests/engine/__init__.py` (new, if not already present from an earlier task — empty)
- `tests/engine/test_kg_store.py` (new)

Reference: `research/kg-schema-v1.md` → "The acyclic REQUIRES projection" (`requires_dag` pseudocode + the three MUST-FIX gaps), the "Direction is fixed" paragraph (`a→b` = "a requires b"; closure = `nx.descendants(dag, goal)`; order = `reversed(topological_sort)`), the "NetworkX load sketch" (`MultiDiGraph`, edge attrs `etype`/`cond_group`/`qty`), and invariant **I1** (cycle check on the grant-flip-augmented graph).

---

- [ ] **Step 5.0 — Add the `networkx` dependency.** Open `pyproject.toml`, find the `[project]` `dependencies = [...]` array, and add `networkx`. (If a `dependencies` array does not yet exist under `[project]`, add one.) Example edit — add the line:

  ```toml
      "networkx>=3.0",
  ```

  Then install it into the active environment:

  ```
  python3 -m pip install 'networkx>=3.0'
  ```

  Expected output (tail): `Successfully installed networkx-3.x.x` (or `Requirement already satisfied`). Verify:

  ```
  python3 -c "import networkx as nx; print(nx.__version__)"
  ```

  Expected output: a version string like `3.4.2` printed with no traceback.

- [ ] **Step 5.1 — Failing test: `InMemoryKGStore` holds and looks up nodes/edges/groups.** Create `tests/engine/__init__.py` as an empty file (skip if it already exists). Then create `tests/engine/test_kg_store.py` with the imports + a tiny inline graph builder + the first test:

  ```python
  import networkx as nx
  import pytest

  from osrs_planner.engine.kg.model import (
      AtomType,
      ConditionAtom,
      ConditionGroup,
      Edge,
      EdgeType,
      Node,
      NodeKind,
      Op,
  )
  from osrs_planner.engine.kg.store import InMemoryKGStore, KGStore


  def _tiny_store() -> InMemoryKGStore:
      """A 3-node graph: a boss requires an access (hard requires edge),
      and the access is gated by a dst=NULL requires edge whose cond tree
      has one ref-bearing leaf (a quest) -> a cond_dep edge in the DAG."""
      nodes = [
          Node(id="npc:1", kind=NodeKind.MONSTER, name="Boss", slug="boss"),
          Node(id="access:a", kind=NodeKind.ACCESS, name="A Access", slug="a"),
          Node(id="quest:q", kind=NodeKind.QUEST, name="A Quest", slug="q"),
      ]
      # group 1: AND( quest(quest:q, completed) ) — the access's pure-condition tree
      groups = {
          1: ConditionGroup(
              id=1,
              op=Op.AND,
              parent=None,
              children=[
                  ConditionAtom(
                      atom_type=AtomType.QUEST,
                      ref_node="quest:q",
                      data={"state": "completed"},
                  )
              ],
          ),
      }
      edges = [
          # boss --requires--> access  (hard prerequisite)
          Edge(id=1, type=EdgeType.REQUIRES, src="npc:1", dst="access:a"),
          # access --requires--> NULL, constraint IS the cond tree (group 1)
          Edge(id=2, type=EdgeType.REQUIRES, src="access:a", dst=None, cond_group=1),
      ]
      return InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)


  def test_inmemory_store_holds_collections_and_node_lookup():
      kg = _tiny_store()
      assert isinstance(kg, KGStore)
      assert set(kg.nodes.keys()) == {"npc:1", "access:a", "quest:q"}
      assert len(kg.edges) == 2
      assert set(kg.groups.keys()) == {1}
      assert kg.node("npc:1").name == "Boss"
      assert kg.node("nope") is None
  ```

  Run:

  ```
  python3 -m pytest tests/engine/test_kg_store.py -q
  ```

  Expected: **FAIL** — `ModuleNotFoundError: No module named 'osrs_planner.engine.kg.store'` (the module does not exist yet).

- [ ] **Step 5.2 — Minimal impl: `KGStore` interface + `InMemoryKGStore` with `node()`.** Create `src/osrs_planner/engine/kg/store.py`:

  ```python
  """KG store interface + in-memory implementation.

  KGStore is the read interface the future ingest brick will implement; the engine
  only ever depends on this surface. InMemoryKGStore is built from plain lists of
  Node/Edge/ConditionGroup (used by tests and the hand-authored fixture).
  """

  from __future__ import annotations

  from typing import Optional

  import networkx as nx

  from osrs_planner.engine.kg.model import (
      AtomType,
      ConditionAtom,
      ConditionGroup,
      Edge,
      EdgeType,
      Node,
  )

  # atom_types whose ref_node is a real node FK -> projected as 'cond_dep' closure
  # edges (kg-schema-v1.md: the requires_dag ref-leaf projection, MUST-FIX gap 1).
  # D3: gear_loadout is ref-bearing HERE (it projects a cond_dep to its
  # gear_loadout:* node so the loadout's item leaves enter the closure) AND is
  # dynamically evaluated in atom_satisfied (recursed against current counts).
  # Both are true — they are not in conflict.
  _REF_BEARING_ATOMS: frozenset[AtomType] = frozenset(
      {
          AtomType.ITEM,
          AtomType.IS_UNLOCKED,
          AtomType.QUEST,
          AtomType.ACHIEVEMENT_DIARY,
          AtomType.COMBAT_ACHIEVEMENT,
          AtomType.KILL_COUNT,
          AtomType.GEAR_LOADOUT,
      }
  )


  class KGStore:
      """Read interface over the knowledge graph."""

      nodes: dict[str, Node]
      edges: list[Edge]
      groups: dict[int, ConditionGroup]

      def node(self, node_id: str) -> Optional[Node]:
          raise NotImplementedError

      def children_of(self, group_id: int) -> list:
          raise NotImplementedError

      def composition_of(self, loadout_node_id: str) -> int:
          raise NotImplementedError

      def requires_dag(self) -> nx.MultiDiGraph:
          raise NotImplementedError

      def descendants(self, goal_id: str) -> set[str]:
          raise NotImplementedError

      def topo_order(self, goal_id: str) -> list[str]:
          raise NotImplementedError

      def find_cycles(self) -> list[list[str]]:
          raise NotImplementedError


  class InMemoryKGStore(KGStore):
      def __init__(
          self,
          nodes: list[Node],
          edges: list[Edge],
          groups: dict[int, ConditionGroup],
      ) -> None:
          self.nodes = {n.id: n for n in nodes}
          self.edges = list(edges)
          self.groups = dict(groups)

      def node(self, node_id: str) -> Optional[Node]:
          return self.nodes.get(node_id)
  ```

  Run:

  ```
  python3 -m pytest tests/engine/test_kg_store.py -q
  ```

  Expected: **PASS** — `1 passed`.

- [ ] **Step 5.3 — Commit.**

  ```
  git add pyproject.toml src/osrs_planner/engine/kg/store.py tests/engine/__init__.py tests/engine/test_kg_store.py
  git commit -m "feat: KGStore interface + InMemoryKGStore node lookup"
  ```

  Expected output: a commit summary line listing the staged files (e.g. `4 files changed`).

- [ ] **Step 5.4 — Failing test: `children_of()` and `composition_of()`.** `children_of` returns a group's `children` list verbatim (sub-group ids and/or `ConditionAtom` objects); `composition_of` returns the `cond_group` id of a `gear_loadout` node's `dst=NULL` `requires` edge. Append to `tests/engine/test_kg_store.py`:

  ```python
  def test_children_of_returns_group_children():
      kg = _tiny_store()
      children = kg.children_of(1)
      assert len(children) == 1
      atom = children[0]
      assert isinstance(atom, ConditionAtom)
      assert atom.atom_type == AtomType.QUEST
      assert atom.ref_node == "quest:q"


  def _loadout_store() -> InMemoryKGStore:
      """A gear_loadout node carrying its composition on a dst=NULL requires edge."""
      nodes = [
          Node(id="gear_loadout:void", kind=NodeKind.GEAR_LOADOUT, name="Void", slug="void"),
          Node(id="item:8839", kind=NodeKind.ITEM, name="Void top", slug="void-top"),
      ]
      groups = {
          10: ConditionGroup(
              id=10,
              op=Op.AND,
              parent=None,
              children=[ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8839")],
          ),
      }
      edges = [
          Edge(id=1, type=EdgeType.REQUIRES, src="gear_loadout:void", dst=None, cond_group=10),
      ]
      return InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)


  def test_composition_of_returns_loadout_cond_group_id():
      kg = _loadout_store()
      assert kg.composition_of("gear_loadout:void") == 10
  ```

  Run:

  ```
  python3 -m pytest tests/engine/test_kg_store.py -q
  ```

  Expected: **FAIL** — `NotImplementedError` raised from `children_of` / `composition_of` (the base-class stubs).

- [ ] **Step 5.5 — Minimal impl: `children_of()` + `composition_of()`.** Add to `InMemoryKGStore` (after `node`):

  ```python
      def children_of(self, group_id: int) -> list:
          return list(self.groups[group_id].children)

      def composition_of(self, loadout_node_id: str) -> int:
          for e in self.edges:
              if (
                  e.type is EdgeType.REQUIRES
                  and e.src == loadout_node_id
                  and e.dst is None
                  and e.cond_group is not None
              ):
                  return e.cond_group
          raise KeyError(f"no composition cond_group for loadout {loadout_node_id!r}")
  ```

  Run:

  ```
  python3 -m pytest tests/engine/test_kg_store.py -q
  ```

  Expected: **PASS** — `3 passed`.

- [ ] **Step 5.6 — Commit.**

  ```
  git add src/osrs_planner/engine/kg/store.py tests/engine/test_kg_store.py
  git commit -m "feat: KGStore children_of + composition_of"
  ```

  Expected output: a commit summary line (`2 files changed`).

- [ ] **Step 5.7 — Failing test: `requires_dag()` projects hard requires + ref-bearing cond-leaves.** The DAG is a `MultiDiGraph`; edge `a→b` = "a requires b". A hard `requires` edge with a non-NULL `dst` becomes a `kind="requires"` edge; every ref-bearing atom (here the `quest:q` leaf under `access:a`'s `dst=NULL` tree) becomes a `kind="cond_dep"` edge from the edge's `src` to the atom's `ref_node`. Append:

  ```python
  def test_requires_dag_has_requires_edge_and_cond_dep_edge():
      kg = _tiny_store()
      dag = kg.requires_dag()
      assert isinstance(dag, nx.MultiDiGraph)
      assert set(dag.nodes) == {"npc:1", "access:a", "quest:q"}

      # hard requires: npc:1 -> access:a (a->b = a requires b)
      req = [d for _, _, d in dag.out_edges("npc:1", data=True)]
      assert any(d.get("kind") == "requires" for d in req)
      assert dag.has_edge("npc:1", "access:a")

      # ref-bearing cond leaf: access:a (dst=NULL requires, group 1) -> quest:q
      assert dag.has_edge("access:a", "quest:q")
      cond = [d for _, _, d in dag.out_edges("access:a", data=True)]
      assert any(d.get("kind") == "cond_dep" for d in cond)


  def test_requires_dag_preserves_parallel_edges():
      # two parallel requires edges with distinct cond_groups must both survive
      nodes = [
          Node(id="a", kind=NodeKind.ACTIVITY, name="A", slug="a"),
          Node(id="b", kind=NodeKind.SKILL, name="B", slug="b"),
      ]
      groups = {
          1: ConditionGroup(id=1, op=Op.AND, parent=None, children=[]),
          2: ConditionGroup(id=2, op=Op.AND, parent=None, children=[]),
      }
      edges = [
          Edge(id=1, type=EdgeType.REQUIRES, src="a", dst="b", cond_group=1),
          Edge(id=2, type=EdgeType.REQUIRES, src="a", dst="b", cond_group=2),
      ]
      kg = InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)
      dag = kg.requires_dag()
      assert dag.number_of_edges("a", "b") == 2
  ```

  Run:

  ```
  python3 -m pytest tests/engine/test_kg_store.py -q
  ```

  Expected: **FAIL** — `NotImplementedError` from `requires_dag`.

- [ ] **Step 5.8 — Minimal impl: `requires_dag()` (requires + cond_dep, parallels preserved).** Add a private leaf-walker and `requires_dag` to `InMemoryKGStore`:

  ```python
      def _iter_ref_leaves(self):
          """Yield (owner_src, ref_node, group_id) for every ref-bearing atom in any
          cond tree reachable from a requires edge. Walks groups recursively so atoms
          nested under sub-groups are projected too. (kg-schema-v1.md iter_ref_leaves.)"""
          # map each cond_group id -> the requires-edge src that owns its tree
          owner_of_group: dict[int, str] = {}
          for e in self.edges:
              if e.type is EdgeType.REQUIRES and e.cond_group is not None:
                  owner_of_group.setdefault(e.cond_group, e.src)

          def walk(group_id: int, owner: str):
              for child in self.groups[group_id].children:
                  if isinstance(child, ConditionAtom):
                      if child.atom_type in _REF_BEARING_ATOMS and child.ref_node is not None:
                          yield owner, child.ref_node, group_id
                  else:  # a sub-group id (int)
                      yield from walk(int(child), owner)

          for gid, owner in owner_of_group.items():
              yield from walk(gid, owner)

      def requires_dag(self) -> nx.MultiDiGraph:
          dag = nx.MultiDiGraph()
          dag.add_nodes_from(self.nodes.keys())
          # 1) hard prerequisite edges (a->b = a requires b); keep parallels + conditions
          for e in self.edges:
              if e.type is EdgeType.REQUIRES and e.dst is not None:
                  dag.add_edge(e.src, e.dst, kind="requires", cond_group=e.cond_group, qty=e.qty)
          # 1b) ref-bearing condition leaves -> 'cond_dep' closure edges
          for owner, ref_node, gid in self._iter_ref_leaves():
              dag.add_edge(owner, ref_node, kind="cond_dep", cond_group=gid)
          return dag
  ```

  Run:

  ```
  python3 -m pytest tests/engine/test_kg_store.py -q
  ```

  Expected: **PASS** — `5 passed`.

- [ ] **Step 5.9 — Commit.**

  ```
  git add src/osrs_planner/engine/kg/store.py tests/engine/test_kg_store.py
  git commit -m "feat: requires_dag projection (requires + cond_dep, parallels kept)"
  ```

  Expected output: a commit summary line (`2 files changed`).

- [ ] **Step 5.10 — Failing test: `descendants()` and `topo_order()`.** `descendants(goal)` = the full prereq closure (`nx.descendants` over the DAG, incl. `cond_dep` reach); `topo_order(goal)` = a valid completion order = `reversed(topological_sort)` of the closure subgraph (**prereqs-first**, per D1: edge `a→b` = "a requires b", so `b` must be completed before `a` — the goal comes LAST). Append:

  ```python
  def test_descendants_is_full_prereq_closure():
      kg = _tiny_store()
      # npc:1 -> access:a -> quest:q  => closure of npc:1 is {access:a, quest:q}
      assert kg.descendants("npc:1") == {"access:a", "quest:q"}
      assert kg.descendants("access:a") == {"quest:q"}
      assert kg.descendants("quest:q") == set()


  def test_topo_order_lists_prereqs_before_goal():
      kg = _tiny_store()
      order = kg.topo_order("npc:1")
      assert set(order) == {"npc:1", "access:a", "quest:q"}
      # D1: a->b means a requires b, so b (the prereq) must come BEFORE a in
      # completion order. reversed(topological_sort) yields prereqs first, goal last.
      assert order.index("quest:q") < order.index("access:a")
      assert order.index("access:a") < order.index("npc:1")
  ```

  Run:

  ```
  python3 -m pytest tests/engine/test_kg_store.py -q
  ```

  Expected: **FAIL** — `NotImplementedError` from `descendants`.

- [ ] **Step 5.11 — Minimal impl: `descendants()` + `topo_order()`.** Add to `InMemoryKGStore`:

  ```python
      def descendants(self, goal_id: str) -> set[str]:
          return set(nx.descendants(self.requires_dag(), goal_id))

      def topo_order(self, goal_id: str) -> list[str]:
          dag = self.requires_dag()
          closure = {goal_id} | set(nx.descendants(dag, goal_id))
          sub = dag.subgraph(closure)
          return list(reversed(list(nx.topological_sort(sub))))
  ```

  Run:

  ```
  python3 -m pytest tests/engine/test_kg_store.py -q
  ```

  Expected: **PASS** — `7 passed`.

- [ ] **Step 5.12 — Commit.**

  ```
  git add src/osrs_planner/engine/kg/store.py tests/engine/test_kg_store.py
  git commit -m "feat: KGStore descendants + topo_order over requires closure"
  ```

  Expected output: a commit summary line (`2 files changed`).

- [ ] **Step 5.13 — Failing test: `find_cycles()` (invariant I1).** The cycle check (I1) runs on a grant-flip-augmented copy of the DAG: for every `grants` edge `src→dst`, add a cycle-only synthetic `dst→src` (granted depends-on granter), then report all simple cycles. An acyclic graph returns `[]`; a `requires`/`grants` tangle returns the cycle node lists. Append:

  ```python
  def test_find_cycles_empty_for_acyclic_graph():
      kg = _tiny_store()
      assert kg.find_cycles() == []


  def test_find_cycles_detects_requires_loop():
      nodes = [
          Node(id="x", kind=NodeKind.ACCESS, name="X", slug="x"),
          Node(id="y", kind=NodeKind.ACCESS, name="Y", slug="y"),
      ]
      edges = [
          Edge(id=1, type=EdgeType.REQUIRES, src="x", dst="y"),
          Edge(id=2, type=EdgeType.REQUIRES, src="y", dst="x"),
      ]
      kg = InMemoryKGStore(nodes=nodes, edges=edges, groups={})
      cycles = kg.find_cycles()
      assert cycles  # non-empty
      assert {"x", "y"} <= set().union(*[set(c) for c in cycles])


  def test_find_cycles_detects_grant_flip_tangle():
      # access:g granted by quest:p, but quest:p requires access:g -> a cycle
      # ONLY through the grant-flip synthetic (I1's reason to augment the graph).
      nodes = [
          Node(id="access:g", kind=NodeKind.ACCESS, name="G", slug="g"),
          Node(id="quest:p", kind=NodeKind.QUEST, name="P", slug="p"),
      ]
      edges = [
          Edge(id=1, type=EdgeType.GRANTS, src="quest:p", dst="access:g"),
          Edge(id=2, type=EdgeType.REQUIRES, src="quest:p", dst="access:g"),
      ]
      kg = InMemoryKGStore(nodes=nodes, edges=edges, groups={})
      # requires alone is acyclic (quest:p -> access:g); the grant flip
      # (access:g -> quest:p) closes the loop, which I1 must catch.
      cycles = kg.find_cycles()
      assert cycles
  ```

  Run:

  ```
  python3 -m pytest tests/engine/test_kg_store.py -q
  ```

  Expected: **FAIL** — `NotImplementedError` from `find_cycles`.

- [ ] **Step 5.14 — Minimal impl: `find_cycles()` with grant-flip synthetics (I1).** Add to `InMemoryKGStore`:

  ```python
      def find_cycles(self) -> list[list[str]]:
          """Invariant I1: report all simple cycles of the requires_dag augmented with
          grant-flip synthetics. A 'grants' edge src->dst becomes a cycle-only synthetic
          dst->src (granted depends-on granter). cond_dep edges are already in the dag,
          so a tangle through a grant OR any ref-bearing atom is caught."""
          cyc = self.requires_dag().copy()
          for e in self.edges:
              if e.type is EdgeType.GRANTS and e.dst is not None:
                  cyc.add_edge(e.dst, e.src, kind="grant_synthetic")
          return [list(c) for c in nx.simple_cycles(cyc)]
  ```

  Run:

  ```
  python3 -m pytest tests/engine/test_kg_store.py -q
  ```

  Expected: **PASS** — `10 passed`.

- [ ] **Step 5.15 — Commit.**

  ```
  git add src/osrs_planner/engine/kg/store.py tests/engine/test_kg_store.py
  git commit -m "feat: KGStore find_cycles with grant-flip synthetics (I1)"
  ```

  Expected output: a commit summary line (`2 files changed`).

---

Notes for the implementer / consistency with the spine:
- `requires_dag()` returns a `networkx.MultiDiGraph`; `nx.simple_cycles` works on MultiDiGraphs in networkx ≥ 3. The `find_cycles` augmented copy is **only** for the I1 cycle check — the returned `requires_dag` itself never carries grant synthetics (so the planner traversing `descendants`/`topo_order` sees only hard `requires` + `cond_dep`, per the schema's "Direction is fixed" paragraph).
- `_iter_ref_leaves` walks sub-groups recursively (`children` may hold `ConditionGroup` ids as ints alongside `ConditionAtom` objects, per the `ConditionGroup.children` spine type), so a ref-bearing atom nested under an OR/AND sub-group still projects a `cond_dep` edge — keeping `descendants()` a complete closure even for `dst=NULL` pure-condition edges (the MUST-FIX gap-1 fix).
- The `_REF_BEARING_ATOMS` set matches the schema's projection list (`item`, `is_unlocked`, `quest`, `achievement_diary`, `combat_achievement`, `kill_count`) plus `gear_loadout` (its composition resolves to ref-bearing item leaves); non-ref atoms (`quest_points`, `combat_achievement_points`, `account_type`, `combat_level`, `clue_scrolls`) are intentionally skipped.

Relevant absolute paths: spec `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/docs/superpowers/specs/2026-06-15-engine-advisor-contract-design.md`; schema `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/research/kg-schema-v1.md`; target module `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/src/osrs_planner/engine/kg/store.py`; test `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/tests/engine/test_kg_store.py`.

---

### Task 6: AccountState — the absence-aware account model (`engine/state.py`)

**Files:**
- `src/osrs_planner/engine/state.py` (new) — `QUEST_STATE_ORDER`, `AccountState`, the `family_is_observed` absence-aware helper
- `tests/engine/test_state.py` (new) — TDD coverage for construction, state ordering, and the observed-zero-vs-UNKNOWN decision

This task builds the *state* layer only. It deliberately does **not** import `kleene` or evaluate atoms — `conditions.py` (a later task) consumes the helper this task exposes. The helper here returns a plain `bool` ("is this family's absence a real observed-zero?"); the Kleene `Tri` mapping happens in the evaluator task, against the contract §6 rule: *absent + not-observed + not-manually-asserted → UNKNOWN; absent + observed-family → real FALSE/zero.*

- [ ] **Step 6.1 — Failing test: `QUEST_STATE_ORDER` is a 3-state ordered enum (reused for diaries).**
  Per kg-schema-v1 (`quest`/`achievement_diary` are ordered `>=` over `{not_started, in_progress, completed}`) and contract §6. Create `tests/engine/__init__.py` if it does not exist, then write `tests/engine/test_state.py`:

  ```python
  # tests/engine/test_state.py
  from osrs_planner.engine.state import QUEST_STATE_ORDER, AccountState, family_is_observed


  def test_quest_state_order_is_ordered_three_state():
      assert QUEST_STATE_ORDER == {"not_started": 0, "in_progress": 1, "completed": 2}
      # ordered: a 'completed' requirement is met only by completed;
      # an 'in_progress' requirement is met by in_progress or completed.
      assert QUEST_STATE_ORDER["completed"] > QUEST_STATE_ORDER["in_progress"]
      assert QUEST_STATE_ORDER["in_progress"] > QUEST_STATE_ORDER["not_started"]
      # diary states reuse the same ordering map
      assert QUEST_STATE_ORDER["completed"] >= QUEST_STATE_ORDER["in_progress"]
  ```

  Run command and expected output (collection/import error — module does not exist yet):
  ```
  $ python -m pytest tests/engine/test_state.py -q
  E   ModuleNotFoundError: No module named 'osrs_planner.engine.state'
  ... 1 error in 0.0Ns
  ```

- [ ] **Step 6.2 — Minimal impl: the ordering map + module skeleton.**
  Create `src/osrs_planner/engine/state.py` (assume `src/osrs_planner/engine/__init__.py` already exists from the result.py/kleene.py tasks; if missing, create an empty one):

  ```python
  # src/osrs_planner/engine/state.py
  """Absence-aware account state for the Gilded Tome goal-engine.

  Contract §6 (three-valued / Kleene) + ADR-0004 observability families:
  state distinguishes *absent* from *zero*. Per-skill levels/XP and activity
  scores (KC, clues, CA points, minigames), the clog COUNT, and account_type
  are Hiscores-observable -> absence is a real zero/FALSE. Everything else
  (quest, achievement_diary, combat_achievement, item, is_unlocked, clog_slot,
  quest_points) is UNKNOWN until a plugin or manual fact supplies it.
  """
  from __future__ import annotations

  from dataclasses import dataclass, field

  # Ordered 3-state enum, reused for both quest_state and diary_state.
  QUEST_STATE_ORDER: dict[str, int] = {"not_started": 0, "in_progress": 1, "completed": 2}
  ```

  Run command and expected output (the order test now passes; the unwritten symbols still fail to import — so run only the one test for now):
  ```
  $ python -m pytest tests/engine/test_state.py::test_quest_state_order_is_ordered_three_state -q
  E   ImportError: cannot import name 'AccountState' from 'osrs_planner.engine.state'
  ... 1 error in 0.0Ns
  ```
  (The import line pulls all three names; `AccountState`/`family_is_observed` don't exist yet, so this still errors. That's the expected RED for the next step — do not treat it as a failure of 6.2's code.)

- [ ] **Step 6.3 — Failing test: construct `AccountState` with full defaults.**
  Append to `tests/engine/test_state.py`:

  ```python
  def test_account_state_constructs_with_defaults():
      st = AccountState(mode="ironman")
      assert st.mode == "ironman"
      # every collection field defaults to an independent empty container
      assert st.levels == {}
      assert st.xp == {}
      assert st.counts == {}
      assert st.quest_state == {}
      assert st.diary_state == {}
      assert st.done == set()
      assert st.kc == {}
      assert st.clue_counts == {}
      assert st.observable_families == set()
      # scalar derived defaults
      assert st.combat_level == 3
      assert st.qp == 0
      assert st.ca_points == 0


  def test_account_state_default_containers_are_not_shared():
      a = AccountState(mode="normal")
      b = AccountState(mode="normal")
      a.levels["attack"] = 70
      a.done.add("access:lumbridge")
      # mutable defaults must be per-instance (field(default_factory=...))
      assert b.levels == {}
      assert b.done == set()
  ```

  Run command and expected output:
  ```
  $ python -m pytest tests/engine/test_state.py -q
  E   ImportError: cannot import name 'AccountState' from 'osrs_planner.engine.state'
  ... 1 error in 0.0Ns
  ```

- [ ] **Step 6.4 — Minimal impl: the `AccountState` dataclass (exact spine).**
  Append to `src/osrs_planner/engine/state.py`:

  ```python
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
  ```

  Run command and expected output (construction tests pass; `family_is_observed` still missing so suite import still errors — run just the two construction tests):
  ```
  $ python -m pytest tests/engine/test_state.py::test_account_state_constructs_with_defaults tests/engine/test_state.py::test_account_state_default_containers_are_not_shared -q
  E   ImportError: cannot import name 'family_is_observed' from 'osrs_planner.engine.state'
  ```
  (Still RED because the module-level `import` pulls `family_is_observed`. Expected — the helper lands next. To see the two construction tests GREEN in isolation, temporarily they share the file's import; the clean GREEN comes after 6.6.)

- [ ] **Step 6.5 — Failing test: the absence-aware `family_is_observed` helper.**
  This is the heart of the task: it answers contract §6's "absent ≠ zero" question for a single atom family, given the account's `observable_families` and whether a manual assertion exists. Append to `tests/engine/test_state.py`:

  ```python
  def test_observed_family_with_absent_value_is_a_real_zero():
      # skill_level IS Hiscores-observable: absence == observed zero (eligible FALSE)
      st = AccountState(mode="normal", observable_families={"skill_level", "kill_count"})
      assert family_is_observed("skill_level", st, manually_asserted=False) is True
      assert family_is_observed("kill_count", st, manually_asserted=False) is True


  def test_unobserved_family_absent_and_not_asserted_is_unknown():
      # quest is NOT a Hiscores field -> absence is UNKNOWN, not FALSE
      st = AccountState(mode="normal", observable_families={"skill_level"})
      assert family_is_observed("quest", st, manually_asserted=False) is False
      assert family_is_observed("achievement_diary", st, manually_asserted=False) is False
      assert family_is_observed("combat_achievement", st, manually_asserted=False) is False
      assert family_is_observed("item", st, manually_asserted=False) is False
      assert family_is_observed("is_unlocked", st, manually_asserted=False) is False


  def test_manual_assertion_makes_any_family_observed():
      # a one-tap "confirm this value" manual fact is trusted (contract §6 / §9.3):
      # even an unobservable family becomes a known value once manually asserted.
      st = AccountState(mode="normal", observable_families=set())
      assert family_is_observed("quest", st, manually_asserted=True) is True
      assert family_is_observed("item", st, manually_asserted=True) is True


  def test_observable_families_membership_drives_the_decision():
      # the SAME family flips purely on whether it's in observable_families
      observed = AccountState(mode="normal", observable_families={"kill_count"})
      not_observed = AccountState(mode="normal", observable_families=set())
      assert family_is_observed("kill_count", observed, manually_asserted=False) is True
      assert family_is_observed("kill_count", not_observed, manually_asserted=False) is False
  ```

  Run command and expected output:
  ```
  $ python -m pytest tests/engine/test_state.py -q
  E   ImportError: cannot import name 'family_is_observed' from 'osrs_planner.engine.state'
  ... 1 error in 0.0Ns
  ```

- [ ] **Step 6.6 — Minimal impl: `family_is_observed`.**
  This helper is pure and side-effect-free; it encodes only the §6 decision rule (observed-family OR manually-asserted ⇒ known/real-zero; otherwise the absence is UNKNOWN). It does **not** look at the actual value or return a `Tri` — that mapping belongs to `conditions.py`. Append to `src/osrs_planner/engine/state.py`:

  ```python
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
  ```

  Run command and expected output (full suite GREEN):
  ```
  $ python -m pytest tests/engine/test_state.py -q
  .........                                                        [100%]
  9 passed in 0.0Ns
  ```

- [ ] **Step 6.7 — Commit.**
  ```
  $ git add src/osrs_planner/engine/state.py tests/engine/test_state.py tests/engine/__init__.py
  $ git commit -m "feat: absence-aware AccountState + observed-zero-vs-unknown helper (engine/state.py)"
  ```
  Expected output: one commit recorded, e.g. `2 files changed` (or 3 if `tests/engine/__init__.py` was newly created), listing `src/osrs_planner/engine/state.py` and `tests/engine/test_state.py`.

---

Notes for the plan author / parent agent (not part of the task body):
- I kept this task **state-only** — it does not import `kleene.Tri`. The spine description folds the absence rule into `conditions.atom_satisfied`, so the `bool`→`Tri` step (`UNKNOWN` when `not family_is_observed(...)` and value absent and not asserted; else map the comparison) is drafted in the conditions task, consuming `family_is_observed` from here. If the parent prefers the helper to return `Tri` directly, that is the one design fork in this task.
- Family-string source of truth: the helper compares against `AtomType` *values* (e.g. `"skill_level"`, `"kill_count"`, `"quest"`) per the spine's `AtomType(str)` enum, so callers can pass `atom.atom_type.value`. Observable set per ADR-0004 / contract §6.4: `{skill_level, skill_xp, kill_count, clue_scrolls, combat_achievement_points, account_type}` are Hiscores-observable; `combat_level`/`quest_points`/`access` are `derived` (inherit UNKNOWN); `quest`/`achievement_diary`/`combat_achievement`/`item`/`is_unlocked`/`clog_slot` need plugin/manual.

Relevant file paths:
- Task target (new): `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/src/osrs_planner/engine/state.py`
- Task target (new): `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/tests/engine/test_state.py`
- Contract source read: `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/docs/superpowers/specs/2026-06-15-engine-advisor-contract-design.md` (§6, §6.4)
- KG schema source read: `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/research/kg-schema-v1.md` (atom semantics, QUEST_STATE_ORDER)

---

### Task 7: Condition evaluation — `atom_satisfied` (every atom type) + recursive `evaluate` folding via Kleene, with the absence-aware UNKNOWN rule

This task implements `src/osrs_planner/engine/conditions.py` against the type-spine. It depends on the modules built in Tasks 1–6: `engine/kleene.py` (`Tri`, `k_and`, `k_or`, `k_not`, `from_bool`), `engine/kg/model.py` (`NodeKind`, `AtomType`, `Op`, `Node`, `ConditionAtom`, `ConditionGroup`, `Edge`, `EdgeType`), `engine/state.py` (`AccountState`, `QUEST_STATE_ORDER`), and `engine/kg/store.py` (`KGStore`, `InMemoryKGStore`, with `children_of(group_id)` and `composition_of(loadout_node_id)`).

The two functions (exact spine signatures, do not rename):
- `evaluate(group_id: int, state: AccountState, kg: KGStore) -> Tri` — recursive; hydrates `kg.children_of(group_id)` (a mixed list of child `ConditionGroup` *ids* (int) and `ConditionAtom` objects), recurses into ints via `evaluate`, evaluates atoms via `atom_satisfied`, and folds with `k_and` / `k_or` / `k_not` keyed on the group's `op`.
- `atom_satisfied(atom: ConditionAtom, state: AccountState, kg: KGStore) -> Tri` — one branch per `AtomType`, each honoring the absence-aware UNKNOWN rule (kg-schema §"Atom semantics"; contract §6).

Behavioral anchors from the source docs (do not re-derive):
- **Absence-aware rule (state.py spine + contract §6):** for a *ref-bearing* atom whose value is absent and **not** manually asserted, if the atom's observable-family is **not** in `state.observable_families` → `Tri.UNKNOWN` (never FALSE). If the family **is** observable, absence means the real zero / `not_started` / not-owned value → a real FALSE.
- **`gear_loadout` is DYNAMIC** (kg-schema §gear-loadout, §worked Void example): evaluate `kg.composition_of(atom.ref_node)` against current `state.counts`; gear is never read from `done`. The Void composition is `AND( OR(helm a/b/c), top, robe, gloves )`, so 3/4 pieces → FALSE, full set → TRUE. Item families are observable (banked/owned), so absence → 0 → FALSE.
- **`quest` / `achievement_diary` are 3-state ordered** (`QUEST_STATE_ORDER`): satisfied iff `order[state] >= order[required]`, so an `in_progress` requirement is met by a `completed` account state. These families are unobservable on Hiscores → absence → UNKNOWN.
- **`combat_achievement`** is binary: `ref_node in state.done` (per-task; never "in progress"). Unobservable → absence is UNKNOWN.
- **`is_unlocked`**: `ref_node in state.done` (permanent access). `access:*` is engine-derived/unobservable → absence is UNKNOWN.
- **`combat_level`, `quest_points`, `combat_achievement_points`, `account_type`** are ref-less. `combat_level` and the two point totals read engine-computed scalars (`state.combat_level`, `state.qp`, `state.ca_points`) that always exist → numeric `>=` → never UNKNOWN. `account_type` reads `state.mode == data['value']` → always known.
- **`skill_level` / `skill_xp`**: numeric `>=` against `state.levels` / `state.xp`; skill levels/XP are observable for any tracked account (contract §6.4) → absent skill defaults to level 1 / xp 0 → real FALSE, never UNKNOWN.
- **`item`**: `state.counts.get(ref_node,0) >= (qty or 1)`; items observable (bank feed) → absent → 0 → FALSE.
- **`kill_count`**: `state.kc.get(ref_node,0) >= threshold`; KC is the canonical *absence ≠ zero* case (contract §6.4 cardinal rule) → unobservable absence → UNKNOWN.
- **`clue_scrolls`**: cardinality — `count(m in data['set_ref'] if m satisfied) >= threshold`, where a member `m` (a clue-tier node id) is "satisfied" iff `state.clue_counts.get(m,0) >= 1`. Clue tiers are an *absence ≠ zero* family → if a member is absent-and-unobservable it contributes UNKNOWN, and the cardinality fold uses Kleene so the verdict is UNKNOWN only when it can flip.

**Files:**
- `src/osrs_planner/engine/conditions.py` (new)
- `tests/engine/test_conditions.py` (new)

> Helper used by several steps to keep `AccountState` construction terse. Adjust only the fields each test asserts on; everything else defaults via the spine dataclass.

---

- [ ] **Step 7.1 — RED: `skill_level` numeric `>=` (TRUE/FALSE), absence → FALSE (observable family).**

  Create the test file with the first atom test.

  Write `tests/engine/test_conditions.py`:
  ```python
  from osrs_planner.engine.kleene import Tri
  from osrs_planner.engine.state import AccountState
  from osrs_planner.engine.kg.model import (
      AtomType, Op, NodeKind, Node, ConditionAtom, ConditionGroup, Edge, EdgeType,
  )
  from osrs_planner.engine.kg.store import InMemoryKGStore
  from osrs_planner.engine.conditions import evaluate, atom_satisfied


  def _store(nodes=None, edges=None, groups=None):
      # Task 5's InMemoryKGStore expects groups as a dict[int, ConditionGroup];
      # callers pass a list[ConditionGroup], so index it by id here.
      return InMemoryKGStore(
          nodes=list(nodes or []),
          edges=list(edges or []),
          groups={g.id: g for g in (groups or [])},
      )


  def test_skill_level_atom_true_false_and_absent_is_false():
      kg = _store(nodes=[Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack")])
      atom = ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=70)

      met = AccountState(mode="normal", levels={"skill:attack": 70})
      under = AccountState(mode="normal", levels={"skill:attack": 69})
      absent = AccountState(mode="normal")  # skill levels are observable -> absent means level 1 -> FALSE

      assert atom_satisfied(atom, met, kg) is Tri.TRUE
      assert atom_satisfied(atom, under, kg) is Tri.FALSE
      assert atom_satisfied(atom, absent, kg) is Tri.FALSE
  ```

  Run:
  ```
  python -m pytest tests/engine/test_conditions.py -q
  ```
  Expected: **FAIL** — `ModuleNotFoundError: No module named 'osrs_planner.engine.conditions'` (or `ImportError` for `evaluate`/`atom_satisfied`).

- [ ] **Step 7.2 — GREEN: create `conditions.py` with the `skill_level` branch.**

  Write `src/osrs_planner/engine/conditions.py`:
  ```python
  """Recursive three-valued (Kleene) condition evaluation over the KG.

  evaluate(group_id, state, kg) folds a condition_group tree via kleene.
  atom_satisfied(atom, state, kg) tests one leaf, honoring the absence-aware
  UNKNOWN rule (kg-schema-v1 atom semantics; engine-advisor-contract section 6).
  """
  from __future__ import annotations

  from osrs_planner.engine.kleene import Tri, k_and, k_or, k_not, from_bool
  from osrs_planner.engine.kg.model import AtomType, Op, ConditionAtom
  from osrs_planner.engine.kg.store import KGStore
  from osrs_planner.engine.state import AccountState, QUEST_STATE_ORDER, family_is_observed


  def atom_satisfied(atom: ConditionAtom, state: AccountState, kg: KGStore) -> Tri:
      at = atom.atom_type

      if at is AtomType.SKILL_LEVEL:
          # skill levels are observable for any tracked account -> absent = level 1 = real FALSE
          return from_bool(state.levels.get(atom.ref_node, 1) >= (atom.threshold or 0))

      raise NotImplementedError(f"atom_satisfied: {at!r} not implemented")
  ```

  Run:
  ```
  python -m pytest tests/engine/test_conditions.py -q
  ```
  Expected: **PASS** (1 passed).

- [ ] **Step 7.3 — commit.**
  ```
  git add src/osrs_planner/engine/conditions.py tests/engine/test_conditions.py
  git commit -m "feat: condition atom_satisfied for skill_level (numeric >=, observable absence=FALSE)"
  ```

- [ ] **Step 7.4 — RED: `skill_xp`, `combat_level`, `quest_points`, `combat_achievement_points` (numeric scalars, never UNKNOWN).**

  Append to `tests/engine/test_conditions.py`:
  ```python
  def test_skill_xp_atom():
      kg = _store(nodes=[Node(id="skill:slayer", kind=NodeKind.SKILL, name="Slayer", slug="slayer")])
      atom = ConditionAtom(atom_type=AtomType.SKILL_XP, ref_node="skill:slayer", threshold=100_000)
      assert atom_satisfied(atom, AccountState(mode="normal", xp={"skill:slayer": 100_000}), kg) is Tri.TRUE
      assert atom_satisfied(atom, AccountState(mode="normal", xp={"skill:slayer": 99_999}), kg) is Tri.FALSE
      assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.FALSE  # absent xp = 0


  def test_combat_level_atom_reads_derived_scalar():
      kg = _store()
      atom = ConditionAtom(atom_type=AtomType.COMBAT_LEVEL, threshold=100)
      assert atom_satisfied(atom, AccountState(mode="normal", combat_level=100), kg) is Tri.TRUE
      assert atom_satisfied(atom, AccountState(mode="normal", combat_level=99), kg) is Tri.FALSE
      # default combat_level=3 always exists -> never UNKNOWN
      assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.FALSE


  def test_quest_points_and_ca_points_atoms():
      kg = _store()
      qp = ConditionAtom(atom_type=AtomType.QUEST_POINTS, threshold=32)
      cap = ConditionAtom(atom_type=AtomType.COMBAT_ACHIEVEMENT_POINTS, threshold=500)
      assert atom_satisfied(qp, AccountState(mode="normal", qp=32), kg) is Tri.TRUE
      assert atom_satisfied(qp, AccountState(mode="normal", qp=31), kg) is Tri.FALSE
      assert atom_satisfied(cap, AccountState(mode="normal", ca_points=500), kg) is Tri.TRUE
      assert atom_satisfied(cap, AccountState(mode="normal", ca_points=499), kg) is Tri.FALSE
  ```

  Run:
  ```
  python -m pytest tests/engine/test_conditions.py -q
  ```
  Expected: **FAIL** — `NotImplementedError: atom_satisfied: <AtomType.SKILL_XP: 'skill_xp'> not implemented`.

- [ ] **Step 7.5 — GREEN: add the four scalar branches.**

  In `src/osrs_planner/engine/conditions.py`, replace the `skill_level` block + `raise` with:
  ```python
      if at is AtomType.SKILL_LEVEL:
          # skill levels are observable for any tracked account -> absent = level 1 = real FALSE
          return from_bool(state.levels.get(atom.ref_node, 1) >= (atom.threshold or 0))

      if at is AtomType.SKILL_XP:
          return from_bool(state.xp.get(atom.ref_node, 0) >= (atom.threshold or 0))

      if at is AtomType.COMBAT_LEVEL:
          # engine-derived scalar, always present (defaults to 3) -> never UNKNOWN
          return from_bool(state.combat_level >= (atom.threshold or 0))

      if at is AtomType.QUEST_POINTS:
          return from_bool(state.qp >= (atom.threshold or 0))

      if at is AtomType.COMBAT_ACHIEVEMENT_POINTS:
          return from_bool(state.ca_points >= (atom.threshold or 0))

      raise NotImplementedError(f"atom_satisfied: {at!r} not implemented")
  ```

  Run:
  ```
  python -m pytest tests/engine/test_conditions.py -q
  ```
  Expected: **PASS** (4 passed).

- [ ] **Step 7.6 — commit.**
  ```
  git add src/osrs_planner/engine/conditions.py tests/engine/test_conditions.py
  git commit -m "feat: condition atoms for skill_xp, combat_level, quest_points, ca_points (engine scalars)"
  ```

- [ ] **Step 7.7 — RED: `item` (qty) + `account_type` (mode match).**

  Append to `tests/engine/test_conditions.py`:
  ```python
  def test_item_atom_qty_observable_absent_is_false():
      kg = _store(nodes=[Node(id="item:8839", kind=NodeKind.ITEM, name="Void top", slug="void-top")])
      atom = ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8839", qty=2)
      assert atom_satisfied(atom, AccountState(mode="normal", counts={"item:8839": 2}), kg) is Tri.TRUE
      assert atom_satisfied(atom, AccountState(mode="normal", counts={"item:8839": 1}), kg) is Tri.FALSE
      # items are observable (bank feed) -> absent = 0 owned = FALSE
      assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.FALSE


  def test_item_atom_qty_defaults_to_one():
      kg = _store(nodes=[Node(id="item:8842", kind=NodeKind.ITEM, name="Void gloves", slug="void-gloves")])
      atom = ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8842")  # qty None -> 1
      assert atom_satisfied(atom, AccountState(mode="normal", counts={"item:8842": 1}), kg) is Tri.TRUE
      assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.FALSE


  def test_account_type_atom_matches_mode():
      kg = _store()
      atom = ConditionAtom(atom_type=AtomType.ACCOUNT_TYPE, data={"value": "ironman"})
      assert atom_satisfied(atom, AccountState(mode="ironman"), kg) is Tri.TRUE
      assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.FALSE
  ```

  Run:
  ```
  python -m pytest tests/engine/test_conditions.py -q
  ```
  Expected: **FAIL** — `NotImplementedError: atom_satisfied: <AtomType.ITEM: 'item'> not implemented`.

- [ ] **Step 7.8 — GREEN: add `item` + `account_type` branches.**

  In `conditions.py`, insert above the final `raise`:
  ```python
      if at is AtomType.ITEM:
          # items observable via the bank feed -> absent = 0 owned = real FALSE
          return from_bool(state.counts.get(atom.ref_node, 0) >= (atom.qty or 1))

      if at is AtomType.ACCOUNT_TYPE:
          # mode is always known for a loaded account -> never UNKNOWN
          return from_bool(state.mode == atom.data.get("value"))

  ```

  Run:
  ```
  python -m pytest tests/engine/test_conditions.py -q
  ```
  Expected: **PASS** (6 passed).

- [ ] **Step 7.9 — commit.**
  ```
  git add src/osrs_planner/engine/conditions.py tests/engine/test_conditions.py
  git commit -m "feat: condition atoms for item (qty, observable) and account_type (mode match)"
  ```

- [ ] **Step 7.10 — RED: `is_unlocked` + `combat_achievement` (both `in state.done`; unobservable absence → UNKNOWN).**

  Append to `tests/engine/test_conditions.py`:
  ```python
  def test_is_unlocked_atom_done_membership_and_unobservable_absent_is_unknown():
      kg = _store(nodes=[Node(id="access:fairy-rings", kind=NodeKind.ACCESS,
                              name="Fairy rings", slug="fairy-rings")])
      atom = ConditionAtom(atom_type=AtomType.IS_UNLOCKED, ref_node="access:fairy-rings")

      has = AccountState(mode="normal", done={"access:fairy-rings"})
      # access is engine-derived/unobservable; absent + not asserted -> UNKNOWN (not a false locked)
      absent = AccountState(mode="normal")
      # but if the family IS observed, absence is a real FALSE
      observed = AccountState(mode="normal", observable_families={"is_unlocked"})

      assert atom_satisfied(atom, has, kg) is Tri.TRUE
      assert atom_satisfied(atom, absent, kg) is Tri.UNKNOWN
      assert atom_satisfied(atom, observed, kg) is Tri.FALSE


  def test_combat_achievement_atom_binary_in_done():
      kg = _store(nodes=[Node(id="ca:scurrius:smashing-the-rat", kind=NodeKind.COMBAT_ACHIEVEMENT,
                              name="Smashing the Rat", slug="scurrius:smashing-the-rat")])
      atom = ConditionAtom(atom_type=AtomType.COMBAT_ACHIEVEMENT, ref_node="ca:scurrius:smashing-the-rat")
      done = AccountState(mode="normal", done={"ca:scurrius:smashing-the-rat"})
      absent = AccountState(mode="normal")  # per-task CAs unobservable on Hiscores -> UNKNOWN
      observed = AccountState(mode="normal", observable_families={"combat_achievement"})
      assert atom_satisfied(atom, done, kg) is Tri.TRUE
      assert atom_satisfied(atom, absent, kg) is Tri.UNKNOWN
      assert atom_satisfied(atom, observed, kg) is Tri.FALSE
  ```

  Run:
  ```
  python -m pytest tests/engine/test_conditions.py -q
  ```
  Expected: **FAIL** — `NotImplementedError: atom_satisfied: <AtomType.IS_UNLOCKED: 'is_unlocked'> not implemented`.

- [ ] **Step 7.11 — GREEN: add a `_done_membership` absence-aware helper + the two branches.**

  In `conditions.py`, add this helper just below the imports (above `atom_satisfied`):
  ```python
  def _done_membership(family: str, ref_node: str, state: AccountState) -> Tri:
      """Binary 'ref_node in state.done', honoring the absence-aware UNKNOWN rule.

      D6: presence of the value in the relevant state dict is 'known'; the
      observed-vs-UNKNOWN decision for an ABSENT value routes through
      family_is_observed (the single source of the §6 rule).

      Present in done  -> TRUE (a manually-confirmed value is present here too).
      Absent + family observed -> real FALSE (we'd have seen it if it were done).
      Absent + family unobservable -> UNKNOWN (can't tell; never a false 'locked').
      """
      if ref_node in state.done:
          return Tri.TRUE
      if family_is_observed(family, state, manually_asserted=False):
          return Tri.FALSE
      return Tri.UNKNOWN
  ```

  Then insert above the final `raise`:
  ```python
      if at is AtomType.IS_UNLOCKED:
          return _done_membership("is_unlocked", atom.ref_node, state)

      if at is AtomType.COMBAT_ACHIEVEMENT:
          return _done_membership("combat_achievement", atom.ref_node, state)

  ```

  Run:
  ```
  python -m pytest tests/engine/test_conditions.py -q
  ```
  Expected: **PASS** (8 passed).

- [ ] **Step 7.12 — commit.**
  ```
  git add src/osrs_planner/engine/conditions.py tests/engine/test_conditions.py
  git commit -m "feat: is_unlocked + combat_achievement atoms (done-membership, absence-aware UNKNOWN)"
  ```

- [ ] **Step 7.13 — RED: `quest` + `achievement_diary` (3-state ordered; in_progress req met by completed; unobservable absence → UNKNOWN).**

  Append to `tests/engine/test_conditions.py`:
  ```python
  def test_quest_atom_ordered_state_in_progress_req_met_by_completed():
      kg = _store(nodes=[Node(id="quest:dragon-slayer-i", kind=NodeKind.QUEST,
                              name="Dragon Slayer I", slug="dragon-slayer-i")])
      needs_completed = ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:dragon-slayer-i",
                                      data={"state": "completed"})
      needs_in_progress = ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:dragon-slayer-i",
                                        data={"state": "in_progress"})

      completed = AccountState(mode="normal", quest_state={"quest:dragon-slayer-i": "completed"})
      in_progress = AccountState(mode="normal", quest_state={"quest:dragon-slayer-i": "in_progress"})

      # completed satisfies a 'completed' requirement
      assert atom_satisfied(needs_completed, completed, kg) is Tri.TRUE
      # in_progress does NOT satisfy a 'completed' requirement (ordered <)
      assert atom_satisfied(needs_completed, in_progress, kg) is Tri.FALSE
      # an 'in_progress' requirement is met by BOTH in_progress and completed (ordered >=)
      assert atom_satisfied(needs_in_progress, in_progress, kg) is Tri.TRUE
      assert atom_satisfied(needs_in_progress, completed, kg) is Tri.TRUE


  def test_quest_atom_unobservable_absent_is_unknown():
      kg = _store(nodes=[Node(id="quest:cooks-assistant", kind=NodeKind.QUEST,
                              name="Cook's Assistant", slug="cooks-assistant")])
      atom = ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:cooks-assistant",
                           data={"state": "completed"})
      # quests are NOT on the Hiscores -> absent + unobservable -> UNKNOWN
      assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.UNKNOWN
      # when observed (plugin), absence resolves to not_started -> real FALSE
      observed = AccountState(mode="normal", observable_families={"quest"})
      assert atom_satisfied(atom, observed, kg) is Tri.FALSE


  def test_achievement_diary_atom_ordered_and_unobservable():
      kg = _store(nodes=[Node(id="diary:varrock:hard", kind=NodeKind.DIARY,
                              name="Varrock Hard Diary", slug="varrock:hard")])
      atom = ConditionAtom(atom_type=AtomType.ACHIEVEMENT_DIARY, ref_node="diary:varrock:hard",
                           data={"state": "completed"})
      done = AccountState(mode="normal", diary_state={"diary:varrock:hard": "completed"})
      partial = AccountState(mode="normal", diary_state={"diary:varrock:hard": "in_progress"})
      assert atom_satisfied(atom, done, kg) is Tri.TRUE
      assert atom_satisfied(atom, partial, kg) is Tri.FALSE
      assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.UNKNOWN  # not on Hiscores
  ```

  Run:
  ```
  python -m pytest tests/engine/test_conditions.py -q
  ```
  Expected: **FAIL** — `NotImplementedError: atom_satisfied: <AtomType.QUEST: 'quest'> not implemented`.

- [ ] **Step 7.14 — GREEN: add a `_ordered_state` absence-aware helper + the two branches.**

  In `conditions.py`, add below `_done_membership`:
  ```python
  def _ordered_state(family: str, ref_node: str, required: str,
                     observed: dict, state: AccountState) -> Tri:
      """3-state ordered comparison via QUEST_STATE_ORDER (reused for quest + diary).

      Satisfied iff order[current] >= order[required]. Absent value:
        family observable -> treat as 'not_started' (order 0) = real comparison;
        family unobservable -> UNKNOWN.
      """
      have = observed.get(ref_node)
      if have is None:
          # D6: an absent value is a real not_started only if the family is observed
          # (or manually asserted); otherwise it is genuinely UNKNOWN.
          if family_is_observed(family, state, manually_asserted=False):
              have = "not_started"
          else:
              return Tri.UNKNOWN
      return from_bool(QUEST_STATE_ORDER[have] >= QUEST_STATE_ORDER[required])
  ```

  Then insert above the final `raise`:
  ```python
      if at is AtomType.QUEST:
          return _ordered_state("quest", atom.ref_node, atom.data["state"],
                                state.quest_state, state)

      if at is AtomType.ACHIEVEMENT_DIARY:
          return _ordered_state("achievement_diary", atom.ref_node, atom.data["state"],
                                state.diary_state, state)

  ```
  > Note: the unobservable family key for the diary branch is `"achievement_diary"` (the `AtomType` value), matching what `observable_families` carries; the `quest` test asserts `{"quest"}`, the diary test relies on quests/diaries being unobservable by default (empty set).

  Run:
  ```
  python -m pytest tests/engine/test_conditions.py -q
  ```
  Expected: **PASS** (11 passed).

- [ ] **Step 7.15 — commit.**
  ```
  git add src/osrs_planner/engine/conditions.py tests/engine/test_conditions.py
  git commit -m "feat: quest + achievement_diary atoms (3-state ordered, absence-aware UNKNOWN)"
  ```

- [ ] **Step 7.16 — RED: `kill_count` (absence ≠ zero → UNKNOWN unless observed).**

  Append to `tests/engine/test_conditions.py`:
  ```python
  def test_kill_count_atom_absence_is_unknown_not_zero():
      kg = _store(nodes=[Node(id="npc:7221", kind=NodeKind.MONSTER, name="Scurrius", slug="scurrius")])
      atom = ConditionAtom(atom_type=AtomType.KILL_COUNT, ref_node="npc:7221", threshold=100)
      assert atom_satisfied(atom, AccountState(mode="normal", kc={"npc:7221": 100}), kg) is Tri.TRUE
      assert atom_satisfied(atom, AccountState(mode="normal", kc={"npc:7221": 99}), kg) is Tri.FALSE
      # cardinal rule: absent KC may be below the Hiscores cutoff, NOT zero -> UNKNOWN
      assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.UNKNOWN
      # when observed (plugin), absence is a real 0 -> FALSE
      observed = AccountState(mode="normal", observable_families={"kill_count"})
      assert atom_satisfied(atom, observed, kg) is Tri.FALSE
  ```

  Run:
  ```
  python -m pytest tests/engine/test_conditions.py -q
  ```
  Expected: **FAIL** — `NotImplementedError: atom_satisfied: <AtomType.KILL_COUNT: 'kill_count'> not implemented`.

- [ ] **Step 7.17 — GREEN: add the `kill_count` branch (numeric, absence-aware).**

  In `conditions.py`, insert above the final `raise`:
  ```python
      if at is AtomType.KILL_COUNT:
          if atom.ref_node in state.kc:
              return from_bool(state.kc[atom.ref_node] >= (atom.threshold or 0))
          # absence != zero (could be below the Hiscores tracking cutoff); D6 routes
          # the observed-vs-UNKNOWN decision through family_is_observed.
          if family_is_observed("kill_count", state, manually_asserted=False):
              return from_bool(0 >= (atom.threshold or 0))
          return Tri.UNKNOWN

  ```

  Run:
  ```
  python -m pytest tests/engine/test_conditions.py -q
  ```
  Expected: **PASS** (12 passed).

- [ ] **Step 7.18 — commit.**
  ```
  git add src/osrs_planner/engine/conditions.py tests/engine/test_conditions.py
  git commit -m "feat: kill_count atom (absence != zero -> UNKNOWN per contract 6.4)"
  ```

- [ ] **Step 7.19 — RED: `evaluate` folds AND/OR/NOT via kleene over a nested tree.**

  This first uses `evaluate` against a real `InMemoryKGStore` tree. Append to `tests/engine/test_conditions.py`:
  ```python
  def test_evaluate_and_or_not_fold_via_kleene():
      # group 1 = OR( group 2 = AND(att>=70, str>=70), NOT(group 3 = AND(qp>=99)) )
      nodes = [
          Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack"),
          Node(id="skill:strength", kind=NodeKind.SKILL, name="Strength", slug="strength"),
      ]
      groups = [
          ConditionGroup(id=1, op=Op.OR, parent=None, children=[
              2,
              ConditionGroup(id=4, op=Op.NOT, parent=1, children=[3]),  # see store children_of contract
          ]),
          ConditionGroup(id=2, op=Op.AND, parent=1, children=[
              ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=70),
              ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:strength", threshold=70),
          ]),
          ConditionGroup(id=3, op=Op.AND, parent=4, children=[
              ConditionAtom(atom_type=AtomType.QUEST_POINTS, threshold=99),
          ]),
          ConditionGroup(id=4, op=Op.NOT, parent=1, children=[3]),
      ]
      kg = _store(nodes=nodes, groups=groups)

      # AND branch TRUE -> whole OR TRUE
      both = AccountState(mode="normal", levels={"skill:attack": 70, "skill:strength": 70})
      assert evaluate(1, both, kg) is Tri.TRUE

      # AND branch FALSE (str 60), but NOT(qp>=99) = NOT(FALSE) = TRUE -> OR TRUE
      low_str = AccountState(mode="normal", levels={"skill:attack": 70, "skill:strength": 60}, qp=0)
      assert evaluate(1, low_str, kg) is Tri.TRUE

      # AND branch FALSE AND NOT(qp>=99)=NOT(TRUE)=FALSE -> OR FALSE
      low_str_high_qp = AccountState(mode="normal",
                                     levels={"skill:attack": 70, "skill:strength": 60}, qp=99)
      assert evaluate(1, low_str_high_qp, kg) is Tri.FALSE
  ```
  > `children_of(group_id)` returns a list of child `ConditionGroup` *ids* (int) and/or `ConditionAtom` objects per the store contract; `_store` passes `groups` straight through to `InMemoryKGStore`. The nested literal above mirrors how Task 6's store resolves children — `children_of(1)` yields `[2, 4]` (ints), `children_of(2)` yields the two atoms, etc. The duplicate `id=4` group entry is the canonical row the store indexes; the inline one inside group 1's `children` is ignored by `children_of` (which reads by id). If Task 6's `InMemoryKGStore` instead expects `children` to contain only `int` ids + `ConditionAtom`s (no inline groups), simplify group 1 to `children=[2, 4]`.

  Run:
  ```
  python -m pytest tests/engine/test_conditions.py -q
  ```
  Expected: **FAIL** — `NameError`/`AttributeError` because `evaluate` is imported but not yet defined (only `atom_satisfied` exists).

- [ ] **Step 7.20 — GREEN: implement `evaluate`.**

  In `conditions.py`, add at the bottom of the file:
  ```python
  def evaluate(group_id: int, state: AccountState, kg: KGStore) -> Tri:
      """Recursively evaluate a condition_group, folding children via Kleene."""
      group = kg.groups[group_id]
      values: list[Tri] = []
      for child in kg.children_of(group_id):
          if isinstance(child, ConditionAtom):
              values.append(atom_satisfied(child, state, kg))
          else:  # a child condition_group id (int)
              values.append(evaluate(child, state, kg))

      if group.op is Op.AND:
          return k_and(values)
      if group.op is Op.OR:
          return k_or(values)
      # NOT -> exactly one child (enforced by schema invariant I5)
      return k_not(values[0])
  ```

  Run:
  ```
  python -m pytest tests/engine/test_conditions.py -q
  ```
  Expected: **PASS** (13 passed).

- [ ] **Step 7.21 — commit.**
  ```
  git add src/osrs_planner/engine/conditions.py tests/engine/test_conditions.py
  git commit -m "feat: evaluate() folds condition tree AND/OR/NOT via kleene"
  ```

- [ ] **Step 7.22 — RED: `gear_loadout` is DYNAMIC — evaluate composition vs current counts (3/4 → FALSE, full set → TRUE).**

  This is the flagship Void case. The `gear_loadout` atom delegates to `evaluate(kg.composition_of(ref_node), ...)`. Append to `tests/engine/test_conditions.py`:
  ```python
  def test_gear_loadout_atom_dynamic_partial_false_full_true():
      # Void composition (kg-schema worked example): AND( OR(helm a/b/c), top, robe, gloves )
      nodes = [
          Node(id="gear_loadout:void", kind=NodeKind.GEAR_LOADOUT, name="Full Void", slug="void"),
          Node(id="item:11663", kind=NodeKind.ITEM, name="Void mage helm", slug="void-mage-helm"),
          Node(id="item:11664", kind=NodeKind.ITEM, name="Void ranger helm", slug="void-ranger-helm"),
          Node(id="item:11665", kind=NodeKind.ITEM, name="Void melee helm", slug="void-melee-helm"),
          Node(id="item:8839", kind=NodeKind.ITEM, name="Void top", slug="void-top"),
          Node(id="item:8840", kind=NodeKind.ITEM, name="Void robe", slug="void-robe"),
          Node(id="item:8842", kind=NodeKind.ITEM, name="Void gloves", slug="void-gloves"),
      ]
      # composition cond_group 10 lives on gear_loadout:void's dst=NULL requires edge
      groups = [
          ConditionGroup(id=10, op=Op.AND, parent=None, children=[
              11,  # the helm-OR subgroup
              ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8839"),
              ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8840"),
              ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8842"),
          ]),
          ConditionGroup(id=11, op=Op.OR, parent=10, children=[
              ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:11663"),
              ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:11664"),
              ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:11665"),
          ]),
      ]
      edges = [
          Edge(id=9100, type=EdgeType.REQUIRES, src="gear_loadout:void", dst=None, cond_group=10),
      ]
      kg = _store(nodes=nodes, edges=edges, groups=groups)
      atom = ConditionAtom(atom_type=AtomType.GEAR_LOADOUT, ref_node="gear_loadout:void")

      # full set (melee helm + top + robe + gloves) -> TRUE
      full = AccountState(mode="normal", counts={
          "item:11665": 1, "item:8839": 1, "item:8840": 1, "item:8842": 1,
      })
      assert atom_satisfied(atom, full, kg) is Tri.TRUE

      # 3/4 pieces (missing gloves) -> FALSE (the false-single-piece-OR guard)
      three = AccountState(mode="normal", counts={
          "item:11665": 1, "item:8839": 1, "item:8840": 1,
      })
      assert atom_satisfied(atom, three, kg) is Tri.FALSE

      # only one piece (a helm) -> FALSE (would be a false TRUE without the AND-of-slots tree)
      one = AccountState(mode="normal", counts={"item:11665": 1})
      assert atom_satisfied(atom, one, kg) is Tri.FALSE
  ```
  > `composition_of(loadout_node_id)` (Task 6 store) returns the `cond_group` id of the loadout's `dst=NULL` `requires` edge — here `10`. The `gear_loadout` atom branch must call `evaluate(kg.composition_of(atom.ref_node), state, kg)`.

  Run:
  ```
  python -m pytest tests/engine/test_conditions.py -q
  ```
  Expected: **FAIL** — `NotImplementedError: atom_satisfied: <AtomType.GEAR_LOADOUT: 'gear_loadout'> not implemented`.

- [ ] **Step 7.23 — GREEN: add the `gear_loadout` branch (delegates to `evaluate` on the composition).**

  In `conditions.py`, insert above the final `raise` in `atom_satisfied`:
  ```python
      if at is AtomType.GEAR_LOADOUT:
          # DYNAMIC: re-evaluate the loadout's item-composition tree against CURRENT counts
          # (never read from done -- gear is ownable/losable). kg-schema-v1 worked Void example.
          return evaluate(kg.composition_of(atom.ref_node), state, kg)

  ```
  > `evaluate` is defined later in the same module; because `atom_satisfied` calls it only at runtime (not import time), the forward reference resolves fine within the module namespace.

  Run:
  ```
  python -m pytest tests/engine/test_conditions.py -q
  ```
  Expected: **PASS** (14 passed).

- [ ] **Step 7.24 — commit.**
  ```
  git add src/osrs_planner/engine/conditions.py tests/engine/test_conditions.py
  git commit -m "feat: gear_loadout atom (DYNAMIC composition vs current counts; 3/4=FALSE, full=TRUE)"
  ```

- [ ] **Step 7.25 — RED: `clue_scrolls` cardinality (>= n members satisfied; UNKNOWN folds via Kleene only when it can flip).**

  Append to `tests/engine/test_conditions.py`:
  ```python
  def test_clue_scrolls_cardinality_atom():
      nodes = [
          Node(id="clue:easy", kind=NodeKind.ACTIVITY, name="Easy clue", slug="easy-clue"),
          Node(id="clue:medium", kind=NodeKind.ACTIVITY, name="Medium clue", slug="medium-clue"),
          Node(id="clue:hard", kind=NodeKind.ACTIVITY, name="Hard clue", slug="hard-clue"),
      ]
      kg = _store(nodes=nodes)
      # need >= 2 of the 3 clue tiers completed at least once
      atom = ConditionAtom(atom_type=AtomType.CLUE_SCROLLS, threshold=2,
                           data={"set_ref": ["clue:easy", "clue:medium", "clue:hard"]})

      # 2 satisfied (easy + hard) -> TRUE  (observed family so absent members are real 0)
      obs2 = AccountState(mode="normal",
                          clue_counts={"clue:easy": 4, "clue:hard": 1},
                          observable_families={"clue_scrolls"})
      assert atom_satisfied(atom, obs2, kg) is Tri.TRUE

      # only 1 satisfied, family observed -> the other two are real FALSE -> 1 < 2 -> FALSE
      obs1 = AccountState(mode="normal", clue_counts={"clue:easy": 4},
                          observable_families={"clue_scrolls"})
      assert atom_satisfied(atom, obs1, kg) is Tri.FALSE

      # 1 known-satisfied + 2 UNKNOWN (unobservable): could still reach 2 -> verdict UNKNOWN
      unk = AccountState(mode="normal", clue_counts={"clue:easy": 4})
      assert atom_satisfied(atom, unk, kg) is Tri.UNKNOWN

      # 2 already known-satisfied + 1 UNKNOWN: TRUE regardless of the unknown (k_or short-circuit)
      enough = AccountState(mode="normal", clue_counts={"clue:easy": 4, "clue:medium": 1})
      assert atom_satisfied(atom, enough, kg) is Tri.TRUE
  ```
  > Cardinality folds with Kleene: a member's per-member satisfaction is itself a `Tri` (TRUE if count>=1, FALSE if observed-absent, UNKNOWN if unobservable-absent). The atom is TRUE once `>= threshold` members are TRUE; FALSE once it is impossible to reach the threshold even if every UNKNOWN turned TRUE; otherwise UNKNOWN.

  Run:
  ```
  python -m pytest tests/engine/test_conditions.py -q
  ```
  Expected: **FAIL** — `NotImplementedError: atom_satisfied: <AtomType.CLUE_SCROLLS: 'clue_scrolls'> not implemented`.

- [ ] **Step 7.26 — GREEN: add the `clue_scrolls` Kleene-cardinality branch.**

  In `conditions.py`, insert above the final `raise`:
  ```python
      if at is AtomType.CLUE_SCROLLS:
          members = atom.data.get("set_ref", [])
          threshold = atom.threshold or 0
          per_member: list[Tri] = []
          for m in members:
              if state.clue_counts.get(m, 0) >= 1:
                  per_member.append(Tri.TRUE)
              elif family_is_observed("clue_scrolls", state, manually_asserted=False):
                  per_member.append(Tri.FALSE)  # observed absence = a real 0 (D6)
              else:
                  per_member.append(Tri.UNKNOWN)  # absence != zero
          n_true = sum(1 for t in per_member if t is Tri.TRUE)
          n_unknown = sum(1 for t in per_member if t is Tri.UNKNOWN)
          if n_true >= threshold:
              return Tri.TRUE                      # already enough, unknowns can't undo it
          if n_true + n_unknown < threshold:
              return Tri.FALSE                     # can't reach threshold even if all unknowns flip
          return Tri.UNKNOWN                        # might or might not reach it

  ```

  Run:
  ```
  python -m pytest tests/engine/test_conditions.py -q
  ```
  Expected: **PASS** (15 passed).

- [ ] **Step 7.27 — commit.**
  ```
  git add src/osrs_planner/engine/conditions.py tests/engine/test_conditions.py
  git commit -m "feat: clue_scrolls cardinality atom (Kleene fold over set_ref members)"
  ```

- [ ] **Step 7.28 — RED: `evaluate` surfaces UNKNOWN only when it flips the verdict (the launch-common absence case).**

  This is the §6 contract guarantee at the tree level. Append to `tests/engine/test_conditions.py`:
  ```python
  def test_evaluate_unknown_surfaces_only_when_it_flips_the_verdict():
      # G1 = OR( quest:x completed [UNKNOWN when absent], skill:attack >= 70 )
      nodes = [
          Node(id="quest:x", kind=NodeKind.QUEST, name="Quest X", slug="quest-x"),
          Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack"),
      ]
      groups = [
          ConditionGroup(id=1, op=Op.OR, parent=None, children=[
              ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:x", data={"state": "completed"}),
              ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=70),
          ]),
      ]
      kg = _store(nodes=nodes, groups=groups)

      # quest unknown, but attack>=70 TRUE -> OR is TRUE (k_or short-circuits the UNKNOWN)
      high_att = AccountState(mode="normal", levels={"skill:attack": 70})
      assert evaluate(1, high_att, kg) is Tri.TRUE

      # quest unknown AND attack 60 FALSE -> OR is UNKNOWN (the unknown now flips it)
      low_att = AccountState(mode="normal", levels={"skill:attack": 60})
      assert evaluate(1, low_att, kg) is Tri.UNKNOWN


  def test_evaluate_and_with_one_false_is_false_despite_unknown():
      # G1 = AND( skill:attack >= 70 [FALSE], quest:x [UNKNOWN] ) -> FALSE
      nodes = [
          Node(id="quest:x", kind=NodeKind.QUEST, name="Quest X", slug="quest-x"),
          Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack"),
      ]
      groups = [
          ConditionGroup(id=1, op=Op.AND, parent=None, children=[
              ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=70),
              ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:x", data={"state": "completed"}),
          ]),
      ]
      kg = _store(nodes=nodes, groups=groups)
      st = AccountState(mode="normal", levels={"skill:attack": 60})  # quest absent -> UNKNOWN
      assert evaluate(1, st, kg) is Tri.FALSE  # any FALSE in AND wins over UNKNOWN
  ```

  Run:
  ```
  python -m pytest tests/engine/test_conditions.py -q
  ```
  Expected: **PASS** (17 passed) — no new production code; this proves the fold semantics from Steps 7.20/7.13/7.5 compose correctly. If either assertion fails, it pinpoints a Kleene-fold bug to fix before continuing.

- [ ] **Step 7.29 — commit.**
  ```
  git add tests/engine/test_conditions.py
  git commit -m "test: evaluate surfaces UNKNOWN only when it flips the verdict (contract section 6)"
  ```

- [ ] **Step 7.30 — Full-file run + final commit (whole engine suite green).**

  Run the entire engine test package to confirm Task 7 integrates with the spine modules from Tasks 1–6:
  ```
  python -m pytest tests/engine/ -q
  ```
  Expected: all tests pass, including the 17 in `test_conditions.py` (exit code 0, `17 passed` for this file within the suite total).

  If everything is green and not already committed:
  ```
  git add -A
  git commit -m "test: full engine suite green after conditions.py (Task 7 complete)"
  ```

---

**Notes for the implementer / plan reviewer:**
- `conditions.py` ends up with `atom_satisfied` covering all 14 `AtomType` members and `evaluate` folding the tree; the final `raise NotImplementedError` is unreachable once every branch is added but is kept as a defensive guard against a future `AtomType` addition.
- The absence-aware split is encoded per-atom by family-string membership in `state.observable_families` (e.g. `"quest"`, `"kill_count"`, `"is_unlocked"`, `"clue_scrolls"`). These strings are the `AtomType` *values*; keep them consistent with however Task 4 (`state.py`) / ADR-0004's observability table populates `observable_families`.
- The `gear_loadout` branch is the one place an atom recurses back into `evaluate` (via `composition_of`) — this is the spine's DYNAMIC-vs-`done` distinction (kg-schema §gear-loadout) and is exercised by Step 7.22's 3/4-vs-full assertions.
- Two store-contract assumptions inherited from Task 6: `kg.groups[group_id]` indexes `ConditionGroup` by id, and `kg.children_of(group_id)` returns the mixed `int | ConditionAtom` child list. If Task 6 shipped a different `children_of` return convention, only Step 7.20's `isinstance` dispatch and the Step 7.19/7.22 fixture literals need adjusting — the atom branches are independent of it.

Relevant file paths: `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/src/osrs_planner/engine/conditions.py` (to be created) and `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/tests/engine/test_conditions.py` (to be created).

---

### Task 8: Hand-authored KG fixture (`InMemoryKGStore`) + smoke test

This task is **test infrastructure**, not TDD — it builds the shared fixture that every later engine test loads. It encodes the `kg-schema-v1.md` worked examples (Scurrius access tree, the `(70 Att AND 70 Str) OR full-Void` tree, `gear_loadout:void` composition, two quests incl. an `in_progress` prereq, one diary tier) as an `InMemoryKGStore`, plus a few sample `AccountState`s. There is **one** red→green smoke test (`test_fixture_smoke.py`) that proves the fixture loads and self-checks against the spine. All ids/atoms are cross-checked against the spine + the kg-schema Scurrius worked example.

> **Depends on:** the type-spine modules from earlier tasks must already exist and import cleanly: `engine/result.py`, `engine/kleene.py`, `engine/kg/model.py`, `engine/state.py`, `engine/kg/store.py` (incl. `InMemoryKGStore`), `engine/conditions.py`. The fixture imports `Node, Edge, ConditionGroup, ConditionAtom, NodeKind, EdgeType, Op, AtomType` from `engine.kg.model`, `AccountState` from `engine.state`, `InMemoryKGStore` from `engine.kg.store`, and `evaluate` from `engine.conditions`. `networkx` is installed (added as a dependency in the `store.py` task).

**Files:**
- `tests/engine/__init__.py` (created earlier; create here if absent)
- `tests/engine/fixtures/__init__.py` (new — makes `fixtures` an importable package)
- `tests/engine/fixtures/kg_fixture.py` (new — the hand-authored store builder + sample states + pytest fixtures)
- `tests/engine/conftest.py` (new — pytest-auto-discovered fixtures `scurrius_kg`, `fresh_main`, `iron_75atk_60str` that Tasks 10–13 resolve by name)
- `tests/engine/test_fixture_smoke.py` (new — the single red→green smoke test)

---

- [ ] **Step 1 — make `fixtures` a package.** Create the empty package marker so `from tests.engine.fixtures.kg_fixture import ...` resolves (and so a bare `kg_fixture` import works under rootdir-on-path). Run from repo root:

```bash
mkdir -p tests/engine/fixtures && touch tests/engine/__init__.py && \
  printf '' > tests/engine/fixtures/__init__.py && ls tests/engine/fixtures/
```

Expected output (order may vary):
```
__init__.py
```

- [ ] **Step 2 — write the fixture module (full code, no placeholders).** Create `tests/engine/fixtures/kg_fixture.py` with the complete hand-authored store and sample states. Every id and atom is cross-checked against `kg-schema-v1.md` (Scurrius worked example) and the type-spine signatures.

```python
# tests/engine/fixtures/kg_fixture.py
"""Hand-authored KG fixture for the goal-engine tests.

Encodes the kg-schema-v1 worked examples as an InMemoryKGStore:
  - Scurrius (npc:7221) access tree: located_in -> region:scurrius-lair,
    region gated_by access:scurrius-lair, region:varrock-sewers GRANTS that access,
    and npc:7221 REQUIRES access:scurrius-lair (+ the flagship combat condition).
  - The flagship requires condition on npc:7221:
        OR( AND(70 Attack, 70 Strength), gear_loadout:void )
  - gear_loadout:void composition (dst=NULL requires edge, "the constraint IS the tree"):
        AND( OR(item:11663, item:11664, item:11665),  # any one Void helm (mage/ranger/melee)
             item:8839,  # Void top
             item:8840,  # Void robe
             item:8842 ) # Void gloves
  - Two quests: quest:cooks-assistant (no reqs) and quest:rag-and-bone-man-ii whose
    requires tree carries an IN_PROGRESS quest prereq (kg-schema scale-gap G1 worked case).
  - One diary tier: diary:varrock:hard, requiring quest:cooks-assistant COMPLETED.

IDs/atoms cross-checked against research/kg-schema-v1.md "Worked example — Scurrius"
and the flagship "(70 Attack AND 70 Strength) OR full Void" condition.

This is TEST INFRA: a builder function + a pytest fixture + sample AccountStates.
"""

from __future__ import annotations

import pytest

from osrs_planner.engine.kg.model import (
    AtomType,
    ConditionAtom,
    ConditionGroup,
    Edge,
    EdgeType,
    Node,
    NodeKind,
    Op,
)
from osrs_planner.engine.kg.store import InMemoryKGStore
from osrs_planner.engine.state import AccountState

# ---------------------------------------------------------------------------
# condition_group ids (match the kg-schema worked example where it pins them):
#   1 = OR root on npc:7221 ; 2 = AND(70 Att, 70 Str) ; 3 = AND(gear_loadout:void)
#   10 = gear_loadout:void composition root ; 11 = OR of the three Void helms
#   20 = AND on diary:varrock:hard ; 30 = AND on quest:rag-and-bone-man-ii
# ---------------------------------------------------------------------------
G_SCURRIUS_OR = 1
G_STATS_AND = 2
G_VOID_BRANCH = 3
G_VOID_SET = 10
G_VOID_HELM = 11
G_DIARY_AND = 20
G_RAGII_AND = 30


def build_nodes() -> list[Node]:
    """Every node the fixture's edges/atoms reference (spine + worked example)."""
    return [
        # --- Scurrius reach subgraph ---
        Node(id="npc:7221", kind=NodeKind.MONSTER, name="Scurrius", slug="scurrius",
             data={"is_boss": True, "combat_level": 250}),
        Node(id="region:scurrius-lair", kind=NodeKind.REGION,
             name="Scurrius's Lair (instance)", slug="scurrius-lair",
             data={"instanced": True}),
        Node(id="region:varrock-sewers", kind=NodeKind.REGION, name="Varrock Sewers",
             slug="varrock-sewers", data={}),
        Node(id="access:scurrius-lair", kind=NodeKind.ACCESS, name="Scurrius Lair Access",
             slug="scurrius-lair",
             data={"note": "ability to enter the Scurrius fight instance"}),
        # --- skills referenced by the flagship stats branch ---
        Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack", data={}),
        Node(id="skill:strength", kind=NodeKind.SKILL, name="Strength", slug="strength", data={}),
        Node(id="skill:cooking", kind=NodeKind.SKILL, name="Cooking", slug="cooking", data={}),
        # --- full Void loadout + its piece items ---
        Node(id="gear_loadout:void", kind=NodeKind.GEAR_LOADOUT, name="Full Void Knight",
             slug="void", data={"styles": ["melee", "ranged", "magic"]}),
        Node(id="item:11663", kind=NodeKind.ITEM, name="Void mage helm", slug="void-mage-helm",
             data={"slot": "head"}),
        Node(id="item:11664", kind=NodeKind.ITEM, name="Void ranger helm", slug="void-ranger-helm",
             data={"slot": "head"}),
        Node(id="item:11665", kind=NodeKind.ITEM, name="Void melee helm", slug="void-melee-helm",
             data={"slot": "head"}),
        Node(id="item:8839", kind=NodeKind.ITEM, name="Void knight top", slug="void-knight-top",
             data={"slot": "body"}),
        Node(id="item:8840", kind=NodeKind.ITEM, name="Void knight robe", slug="void-knight-robe",
             data={"slot": "legs"}),
        Node(id="item:8842", kind=NodeKind.ITEM, name="Void knight gloves", slug="void-knight-gloves",
             data={"slot": "hands"}),
        # --- account types (mode-conditional branches read account:* data) ---
        Node(id="account:normal", kind=NodeKind.ACCOUNT_TYPE, name="Normal", slug="normal",
             data={"must_self_acquire": False, "can_ge": True}),
        Node(id="account:ironman", kind=NodeKind.ACCOUNT_TYPE, name="Ironman", slug="ironman",
             data={"must_self_acquire": True, "can_ge": False}),
        # --- quests (one no-req, one with an in_progress prereq: scale-gap G1) ---
        Node(id="quest:cooks-assistant", kind=NodeKind.QUEST, name="Cook's Assistant",
             slug="cooks-assistant", data={"no_requirements": True}),
        Node(id="quest:rag-and-bone-man-ii", kind=NodeKind.QUEST, name="Rag and Bone Man II",
             slug="rag-and-bone-man-ii", data={}),
        # --- one diary tier (task-based 3-state) ---
        Node(id="diary:varrock:hard", kind=NodeKind.DIARY, name="Varrock Diary (Hard)",
             slug="varrock:hard", data={"region": "varrock", "tier": "hard"}),
    ]


def build_groups() -> dict[int, ConditionGroup]:
    """Condition trees. children = list of (sub-group ids) and/or ConditionAtom objects."""
    return {
        # npc:7221 flagship: OR( AND(70 Att, 70 Str), gear_loadout:void )
        G_SCURRIUS_OR: ConditionGroup(
            id=G_SCURRIUS_OR, op=Op.OR, parent=None,
            children=[G_STATS_AND, G_VOID_BRANCH]),
        G_STATS_AND: ConditionGroup(
            id=G_STATS_AND, op=Op.AND, parent=G_SCURRIUS_OR,
            children=[
                ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack",
                              threshold=70),
                ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:strength",
                              threshold=70),
            ]),
        G_VOID_BRANCH: ConditionGroup(
            id=G_VOID_BRANCH, op=Op.AND, parent=G_SCURRIUS_OR,
            children=[
                ConditionAtom(atom_type=AtomType.GEAR_LOADOUT, ref_node="gear_loadout:void"),
            ]),
        # gear_loadout:void composition: AND( OR(3 helms), top, robe, gloves )
        G_VOID_SET: ConditionGroup(
            id=G_VOID_SET, op=Op.AND, parent=None,
            children=[
                G_VOID_HELM,
                ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8839", qty=1),
                ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8840", qty=1),
                ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:8842", qty=1),
            ]),
        G_VOID_HELM: ConditionGroup(
            id=G_VOID_HELM, op=Op.OR, parent=G_VOID_SET,
            children=[
                ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:11663", qty=1),
                ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:11664", qty=1),
                ConditionAtom(atom_type=AtomType.ITEM, ref_node="item:11665", qty=1),
            ]),
        # diary:varrock:hard requires quest:cooks-assistant COMPLETED
        G_DIARY_AND: ConditionGroup(
            id=G_DIARY_AND, op=Op.AND, parent=None,
            children=[
                ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:cooks-assistant",
                              data={"state": "completed"}),
            ]),
        # quest:rag-and-bone-man-ii requires quest:cooks-assistant only IN_PROGRESS (G1)
        G_RAGII_AND: ConditionGroup(
            id=G_RAGII_AND, op=Op.AND, parent=None,
            children=[
                ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:cooks-assistant",
                              data={"state": "in_progress"}),
            ]),
    }


def build_edges() -> list[Edge]:
    """Fact edges. requires reads dependent->prerequisite; grants reads producer->produced."""
    return [
        # Scurrius reach (kg-schema edge ids 9001-9004)
        Edge(id=9001, type=EdgeType.LOCATED_IN, src="npc:7221",
             dst="region:scurrius-lair", cond_group=None),
        Edge(id=9002, type=EdgeType.GATED_BY, src="region:scurrius-lair",
             dst="access:scurrius-lair", cond_group=None),
        Edge(id=9003, type=EdgeType.GRANTS, src="region:varrock-sewers",
             dst="access:scurrius-lair", cond_group=None),
        Edge(id=9004, type=EdgeType.REQUIRES, src="npc:7221",
             dst="access:scurrius-lair", cond_group=None),
        # npc:7221 flagship condition (dst=NULL: the constraint IS the tree)
        Edge(id=9005, type=EdgeType.REQUIRES, src="npc:7221",
             dst=None, cond_group=G_SCURRIUS_OR),
        # gear_loadout:void composition (dst=NULL requires edge, kg-schema edge 9100)
        Edge(id=9100, type=EdgeType.REQUIRES, src="gear_loadout:void",
             dst=None, cond_group=G_VOID_SET),
        # diary tier requires (dst=NULL: the constraint IS the tree)
        Edge(id=9200, type=EdgeType.REQUIRES, src="diary:varrock:hard",
             dst=None, cond_group=G_DIARY_AND),
        # rag-and-bone-man-ii requires an in_progress quest (dst=NULL)
        Edge(id=9300, type=EdgeType.REQUIRES, src="quest:rag-and-bone-man-ii",
             dst=None, cond_group=G_RAGII_AND),
    ]


def build_store() -> InMemoryKGStore:
    """Assemble the hand-authored store from the three lists/dicts above."""
    return InMemoryKGStore(
        nodes=build_nodes(),
        edges=build_edges(),
        groups=build_groups(),
    )


# ---------------------------------------------------------------------------
# Sample account states
# ---------------------------------------------------------------------------
def fresh_main() -> AccountState:
    """A brand-new NORMAL account: combat level 3, nothing trained, nothing done."""
    return AccountState(mode="normal")


def iron_75atk_60str_novoid() -> AccountState:
    """The kg-schema flagship counter-example: ironman, 75 Atk / 60 Str, no Void.
    OR( AND(75>=70=T, 60>=70=F)=F, gear_loadout:void=F ) -> FALSE."""
    return AccountState(
        mode="ironman",
        levels={"skill:attack": 75, "skill:strength": 60},
        # observable_families lets the absent void items read as a real FALSE (owned-count 0),
        # not UNKNOWN, so this counter-example evaluates deterministically.
        observable_families={"skill_level", "item", "quest", "achievement_diary"},
    )


def main_70atk_70str() -> AccountState:
    """A NORMAL account that satisfies the stats branch (70/70) of the flagship OR."""
    return AccountState(
        mode="normal",
        levels={"skill:attack": 70, "skill:strength": 70},
        observable_families={"skill_level", "item", "quest", "achievement_diary"},
    )


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def kg() -> InMemoryKGStore:
    """The shared hand-authored KG store."""
    return build_store()


@pytest.fixture
def states() -> dict[str, AccountState]:
    """Named sample account states for engine tests."""
    return {
        "fresh_main": fresh_main(),
        "iron_75atk_60str_novoid": iron_75atk_60str_novoid(),
        "main_70atk_70str": main_70atk_70str(),
    }
```

> **Builder vs fixture (so the conftest can reuse it).** `build_store()` is a plain importable function (NOT a pytest fixture); the `kg()` fixture is just a thin wrapper around it. The conftest in Step 2b imports `build_store` directly. Keep `build_store` importable.

- [ ] **Step 2b — write the pytest conftest (auto-discovered fixtures).** Create `tests/engine/conftest.py`. pytest auto-discovers `conftest.py` for every test module under `tests/engine/`, so a fixture defined here resolves by name in Tasks 10–13 without an explicit import (unlike `kg_fixture.py`, which is a plain module pytest does NOT scan for fixtures). It re-exports the worked `(70 Att AND 70 Str) OR full-Void` Scurrius store (rooted at `npc:7221`) as `scurrius_kg`, plus two sample `AccountState`s, all built from the importable `kg_fixture` builders.

```python
# tests/engine/conftest.py
"""Auto-discovered pytest fixtures for the engine test suite.

Wraps the plain importable builders in tests/engine/fixtures/kg_fixture.py so
Tasks 10–13 can request `scurrius_kg` / `fresh_main` / `iron_75atk_60str`
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
```

> **Fixture-name reconciliation (Tasks 10–13).** Task 10's seven tests request `scurrius_kg` (provided here). Tasks 11/12 use their own module-local `_fixture_kg()`/`_two_layer_kg()` helpers and construct `AccountState` inline, so they need nothing from conftest. Task 13 defines its OWN module-local `kg` and `ironman` fixtures (a module-local fixture shadows conftest, so there is no clash); it does not consume `scurrius_kg`. The conftest deliberately does NOT export a bare `kg` fixture to avoid shadowing Task 13's local one. The sample states `fresh_main`/`iron_75atk_60str` are available to any task that wants them by fixture name.

- [ ] **Step 3 — write the smoke test (the one red→green step).** Create `tests/engine/test_fixture_smoke.py`. It is the failing test (the fixture module/import surface doesn't exist yet at this point in the plan if you author the test before the module — but since Step 2 already wrote the module, run it now and watch it go green; if you prefer strict red-first, write this test file BEFORE Step 2's module and observe the collection error). The asserts pin the worked-example structure and exercise the spine evaluator end-to-end.

```python
# tests/engine/test_fixture_smoke.py
"""Smoke test: the hand-authored KG fixture loads and matches the worked examples."""

from osrs_planner.engine.conditions import evaluate
from osrs_planner.engine.kg.model import EdgeType, NodeKind
from osrs_planner.engine.kleene import Tri
from tests.engine.fixtures.kg_fixture import (
    G_SCURRIUS_OR,
    G_VOID_SET,
    build_store,
    fresh_main,
    iron_75atk_60str_novoid,
    main_70atk_70str,
)


def test_store_loads_core_nodes():
    kg = build_store()
    scurrius = kg.node("npc:7221")
    assert scurrius is not None
    assert scurrius.kind is NodeKind.MONSTER
    assert scurrius.name == "Scurrius"
    # the four void slots + three helms + skills + access all present
    for nid in ("access:scurrius-lair", "gear_loadout:void", "item:8839",
                "item:8840", "item:8842", "item:11663", "skill:attack"):
        assert kg.node(nid) is not None, nid


def test_scurrius_requires_access_and_flagship_condition():
    kg = build_store()
    req_edges = [e for e in kg.edges
                 if e.type is EdgeType.REQUIRES and e.src == "npc:7221"]
    # one hard access prereq (dst set) + one dst=NULL flagship condition edge
    assert any(e.dst == "access:scurrius-lair" for e in req_edges)
    assert any(e.dst is None and e.cond_group == G_SCURRIUS_OR for e in req_edges)


def test_void_composition_resolves_via_store():
    kg = build_store()
    # composition_of resolves the gear_loadout's dst=NULL requires edge to its cond_group
    assert kg.composition_of("gear_loadout:void") == G_VOID_SET


def test_flagship_false_for_iron_75_60_no_void():
    # OR( AND(75>=70=T, 60>=70=F)=F, gear_loadout:void=F ) -> FALSE  (kg-schema worked result)
    kg = build_store()
    assert evaluate(G_SCURRIUS_OR, iron_75atk_60str_novoid(), kg) is Tri.FALSE


def test_flagship_true_for_main_70_70():
    # the stats branch satisfies the OR -> TRUE
    kg = build_store()
    assert evaluate(G_SCURRIUS_OR, main_70atk_70str(), kg) is Tri.TRUE


def test_fresh_main_flagship_is_false_when_skills_observable():
    # fresh_main has no observable_families set -> absent skills are UNKNOWN, not FALSE;
    # the OR cannot be proven, so the verdict is UNKNOWN (Kleene), never a false locked.
    kg = build_store()
    assert evaluate(G_SCURRIUS_OR, fresh_main(), kg) is Tri.UNKNOWN
```

- [ ] **Step 4 — run the smoke test (expect PASS).** From the repo root:

```bash
./venv/bin/python -m pytest tests/engine/test_fixture_smoke.py -q
```

Expected output (last lines):
```
......                                                                     [100%]
6 passed in 0.0Xs
```

If instead you authored the test before the module (strict red-first), the same command first fails at collection with:
```
E   ModuleNotFoundError: No module named 'tests.engine.fixtures.kg_fixture'
```
— then add Step 2's module and re-run to reach the `6 passed` green.

- [ ] **Step 5 — sanity-check the full engine suite still collects.** Confirm the new fixture file is importable alongside the rest of the engine tests (no name clashes, no import cycles):

```bash
./venv/bin/python -m pytest tests/engine -q
```

Expected: all engine tests pass, including the 6 new smoke tests (exact count grows as later tasks add tests):
```
... 6 passed ...
```
(If earlier-task engine tests already exist, the total is `<prior> + 6 passed`.)

- [ ] **Step 6 — commit.**

```bash
git add tests/engine/__init__.py tests/engine/fixtures/__init__.py \
        tests/engine/fixtures/kg_fixture.py tests/engine/conftest.py \
        tests/engine/test_fixture_smoke.py && \
git commit -m "test: hand-authored KG fixture + conftest + smoke test for goal-engine

Encodes the kg-schema-v1 worked examples (Scurrius access tree, the
'(70 Att AND 70 Str) OR full-Void' condition, gear_loadout:void
composition, two quests incl. an in_progress prereq, one diary tier)
as an InMemoryKGStore, with sample AccountStates (fresh main, the
iron 75-Atk/60-Str/no-Void counter-example, a 70/70 main).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

Expected: one commit created listing the four files.

---

**Cross-check notes (ids/atoms verified against the spine + kg-schema worked example):**
- Scurrius `npc:7221` (combat 250, is_boss); reach edges `9001` located_in → `region:scurrius-lair`, `9002` gated_by → `access:scurrius-lair`, `9003` `region:varrock-sewers` GRANTS the access, `9004` `npc:7221` REQUIRES the access — all match kg-schema "Fact prerequisites to fight Scurrius."
- Flagship condition group `1 = OR(2,3)`, `2 = AND(70 Attack, 70 Strength)`, `3 = AND(gear_loadout:void)` — matches the "(70 Attack AND 70 Strength) OR full Void" tree (groups 1/2/3).
- Void composition group `10 = AND(OR(item:11663, item:11664, item:11665), item:8839, item:8840, item:8842)` with helm-OR group `11` — matches kg-schema `cond_group 10` / the worked Void set (mage/ranger/melee helm ids, top/robe/gloves ids).
- `account:normal` / `account:ironman` data flags (`must_self_acquire`, `can_ge`) match the worked nodes.
- The `quest` atom carries `data={"state": ...}` per the spine (`QUEST_STATE_ORDER`, ordered `>=`); the `in_progress` prereq on `quest:rag-and-bone-man-ii` exercises scale-gap **G1**. `diary:varrock:hard` uses the `quest` atom with `state="completed"`.
- The fixture relies on the spine's **absence-aware Kleene rule**: `fresh_main()` has empty `observable_families`, so absent skill levels read as `UNKNOWN` → the flagship OR is `UNKNOWN` (the contract §6 "can't-tell, never a false locked"); the iron counter-example sets `observable_families` so absent Void items read as a real `FALSE`, reproducing the kg-schema `... = False` result deterministically.

**Caveats for the plan author / executor:**
- This task assumes earlier tasks already created `tests/engine/__init__.py` and the full type-spine; if `tests/engine/__init__.py` is missing, Step 1's `touch` creates it.
- `InMemoryKGStore(nodes=..., edges=..., groups=...)` is invoked with `nodes`/`edges` as `list[Node]`/`list[Edge]` and `groups` as a `dict[int, ConditionGroup]` here — matching Task 5's constructor signature (`groups: dict[int, ConditionGroup]`). `build_groups()` returns that dict directly; do NOT change it to a list. Every `InMemoryKGStore(...)` call in the plan must pass `groups` as a `dict[int, ConditionGroup]` (Task 7's `_store` helper indexes its list arg by `g.id` for exactly this reason).
- Relevant absolute paths: `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/tests/engine/fixtures/kg_fixture.py` and `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/tests/engine/test_fixture_smoke.py`.

---

### Task 9: Return cards — `engine/cards.py` (pydantic projection types)

This task builds the public, JSON-serializable card types the Engine returns inside the `Ok.card` slot of the Result envelope. They are pydantic `BaseModel`s (per the convention: internal KG/state/eval are `@dataclass`; public cards are pydantic) so they project cleanly to tool-schema/JSON. We verify construction, defaults, and `model_dump()` serialization, including the `is_partial` flag from contract §5.6 (a `quest` required-state `< completed` is a partial check).

**Files:**
- `tests/engine/__init__.py` (new — package marker, only created if absent)
- `tests/engine/test_cards.py` (new — tests)
- `src/osrs_planner/engine/__init__.py` (new — package marker, only created if absent)
- `src/osrs_planner/engine/cards.py` (new — implementation)

> Run all commands from the repo root `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool`, using the project venv interpreter `./venv/bin/python`. (`pydantic 2.12.5` / `pytest 9.0.2` / Python 3.14 are already installed there — `model_dump` is the pydantic-v2 serializer.)

---

- [ ] **Step 9.0 — ensure the engine + test packages exist.** These are no-ops if a prior task already created them; the `mkdir -p`/test-then-write keeps the step idempotent. Run:

```bash
mkdir -p src/osrs_planner/engine tests/engine
[ -f src/osrs_planner/engine/__init__.py ] || printf '' > src/osrs_planner/engine/__init__.py
[ -f tests/engine/__init__.py ] || printf '' > tests/engine/__init__.py
ls src/osrs_planner/engine/__init__.py tests/engine/__init__.py
```

Expected output (both paths listed, no error):

```
src/osrs_planner/engine/__init__.py
tests/engine/__init__.py
```

---

- [ ] **Step 9.1 — failing test: `NodeRef` constructs and serializes.** Write `tests/engine/test_cards.py` with the first test. `NodeRef` is the card-layer (pydantic) twin of the Result-envelope `NodeRef` dataclass — same three fields (`id`, `kind`, `name`), all required.

```python
# tests/engine/test_cards.py
from osrs_planner.engine.cards import (
    NodeRef,
    ReferencedAtom,
    Step,
    UnlockCard,
    PlanCard,
)


def test_node_ref_constructs_and_dumps():
    ref = NodeRef(id="quest:fairytale_2", kind="QUEST", name="Fairytale II")
    assert ref.id == "quest:fairytale_2"
    assert ref.kind == "QUEST"
    assert ref.name == "Fairytale II"
    assert ref.model_dump() == {
        "id": "quest:fairytale_2",
        "kind": "QUEST",
        "name": "Fairytale II",
    }
```

Run:

```bash
./venv/bin/python -m pytest tests/engine/test_cards.py -q
```

Expected output (FAIL — module/symbols do not exist yet):

```
ImportError while importing test module '.../tests/engine/test_cards.py'.
...
ModuleNotFoundError: No module named 'osrs_planner.engine.cards'
```

---

- [ ] **Step 9.2 — minimal impl: create `cards.py` with `NodeRef`.** Write the file with the imports and the first model.

```python
# src/osrs_planner/engine/cards.py
"""Public, JSON-serializable return cards for the goal engine.

Convention: internal KG/state/eval types are @dataclass; the public cards the
Engine returns (inside Ok.card of the Result envelope) are pydantic BaseModels
so they project cleanly to JSON / LLM tool-schemas. See contract §5.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class NodeRef(BaseModel):
    """Card-layer twin of result.NodeRef (a node the card points at)."""

    id: str
    kind: str
    name: str
```

Run:

```bash
./venv/bin/python -m pytest tests/engine/test_cards.py -q
```

Expected output (PASS):

```
1 passed
```

---

- [ ] **Step 9.3 — failing test: `ReferencedAtom` defaults (the scalar leash, §5.6).** Append to `tests/engine/test_cards.py`. A bare numeric atom carries only its type + threshold; the optional scalars (`ref_node`, `qty`, `state`) default to `None` and `is_partial` defaults to `False`.

```python
def test_referenced_atom_defaults_to_minimal_scalar():
    atom = ReferencedAtom(atom_type="SKILL_LEVEL", ref_node="skill:attack", threshold=70)
    assert atom.atom_type == "SKILL_LEVEL"
    assert atom.ref_node == "skill:attack"
    assert atom.threshold == 70
    assert atom.qty is None
    assert atom.state is None
    assert atom.is_partial is False
    assert atom.model_dump() == {
        "atom_type": "SKILL_LEVEL",
        "ref_node": "skill:attack",
        "threshold": 70,
        "qty": None,
        "state": None,
        "is_partial": False,
    }
```

Run:

```bash
./venv/bin/python -m pytest tests/engine/test_cards.py -q
```

Expected output (FAIL):

```
ImportError... cannot import name 'ReferencedAtom' from 'osrs_planner.engine.cards'
```

---

- [ ] **Step 9.4 — minimal impl: add `ReferencedAtom`.** Append to `src/osrs_planner/engine/cards.py`.

```python
class ReferencedAtom(BaseModel):
    """A typed scalar the Engine actually read, so the grounding check can
    verify numbers the Advisor states (contract §5.6, the "scalar leash")."""

    atom_type: str
    ref_node: Optional[str] = None
    threshold: Optional[int] = None
    qty: Optional[int] = None
    state: Optional[str] = None
    is_partial: bool = False
```

Run:

```bash
./venv/bin/python -m pytest tests/engine/test_cards.py -q
```

Expected output (PASS):

```
2 passed
```

---

- [ ] **Step 9.5 — failing test: `ReferencedAtom.is_partial` for a partial quest atom (§5.6).** Append to `tests/engine/test_cards.py`. When a `quest` requirement is satisfied by a state *below* `completed` (e.g. only `in_progress` is needed), the atom is partial — `is_partial=True` lets the grounding check distinguish "started FT2" from "fully complete FT2."

```python
def test_referenced_atom_partial_quest_state():
    atom = ReferencedAtom(
        atom_type="QUEST",
        ref_node="quest:fairytale_2",
        state="in_progress",
        is_partial=True,
    )
    assert atom.state == "in_progress"
    assert atom.is_partial is True
    dumped = atom.model_dump()
    assert dumped["state"] == "in_progress"
    assert dumped["is_partial"] is True
    assert dumped["threshold"] is None
```

Run:

```bash
./venv/bin/python -m pytest tests/engine/test_cards.py -q
```

Expected output (PASS — exercises existing fields, no impl change needed; confirms semantics):

```
3 passed
```

> If this test fails, the `ReferencedAtom` field set is wrong — do not patch the test; fix `cards.py` to match the spine.

---

- [ ] **Step 9.6 — failing test: `Step` constructs (a plan/blocker line item).** Append to `tests/engine/test_cards.py`. A `Step` carries an optional `node_id` (None for a synthetic/atom-only step), a `name`, a `reason` (the failing `atom_type` or the literal `'satisfied'`), and a `status` (one of `'satisfiable' | 'impossible_for_mode' | 'satisfied' | 'cant_verify'`).

```python
def test_step_constructs_and_dumps():
    step = Step(
        node_id="skill:attack",
        name="70 Attack",
        reason="SKILL_LEVEL",
        status="satisfiable",
    )
    assert step.node_id == "skill:attack"
    assert step.name == "70 Attack"
    assert step.reason == "SKILL_LEVEL"
    assert step.status == "satisfiable"
    assert step.model_dump() == {
        "node_id": "skill:attack",
        "name": "70 Attack",
        "reason": "SKILL_LEVEL",
        "status": "satisfiable",
    }


def test_step_allows_null_node_id():
    step = Step(node_id=None, name="Combat level 100", reason="COMBAT_LEVEL", status="cant_verify")
    assert step.node_id is None
    assert step.model_dump()["node_id"] is None
```

Run:

```bash
./venv/bin/python -m pytest tests/engine/test_cards.py -q
```

Expected output (FAIL):

```
ImportError... cannot import name 'Step' from 'osrs_planner.engine.cards'
```

---

- [ ] **Step 9.7 — minimal impl: add `Step`.** Append to `src/osrs_planner/engine/cards.py`. `node_id` is `Optional` (defaults `None`); the other three fields are required.

```python
class Step(BaseModel):
    """One ordered plan line / blocker leaf.

    reason: the failing atom_type (e.g. 'SKILL_LEVEL') or the literal 'satisfied'.
    status: 'satisfiable' | 'impossible_for_mode' | 'satisfied' | 'cant_verify'.
    """

    node_id: Optional[str] = None
    name: str
    reason: str
    status: str
```

Run:

```bash
./venv/bin/python -m pytest tests/engine/test_cards.py -q
```

Expected output (PASS):

```
5 passed
```

---

- [ ] **Step 9.8 — failing test: `UnlockCard` defaults + with blockers.** Append to `tests/engine/test_cards.py`. `status` is `'unlocked' | 'locked' | 'indeterminate'`; `blockers` is a list of `Step` defaulting to empty. An UNKNOWN leaf becomes a `cant_verify` blocker (§6 / spine).

```python
def test_unlock_card_defaults_empty_blockers():
    card = UnlockCard(node_id="access:fairy_rings", status="unlocked")
    assert card.node_id == "access:fairy_rings"
    assert card.status == "unlocked"
    assert card.blockers == []
    assert card.model_dump() == {
        "node_id": "access:fairy_rings",
        "status": "unlocked",
        "blockers": [],
    }


def test_unlock_card_with_blockers_serializes_nested_steps():
    blocker = Step(
        node_id="quest:fairytale_2",
        name="Fairytale II",
        reason="QUEST",
        status="satisfiable",
    )
    card = UnlockCard(node_id="access:fairy_rings", status="locked", blockers=[blocker])
    dumped = card.model_dump()
    assert dumped["status"] == "locked"
    assert dumped["blockers"] == [
        {
            "node_id": "quest:fairytale_2",
            "name": "Fairytale II",
            "reason": "QUEST",
            "status": "satisfiable",
        }
    ]
```

Run:

```bash
./venv/bin/python -m pytest tests/engine/test_cards.py -q
```

Expected output (FAIL):

```
ImportError... cannot import name 'UnlockCard' from 'osrs_planner.engine.cards'
```

---

- [ ] **Step 9.9 — minimal impl: add `UnlockCard`.** Append to `src/osrs_planner/engine/cards.py`. The `list[Step]` default uses `default_factory=list` (the pydantic-safe form of a mutable default).

```python
from pydantic import Field  # add to the existing pydantic import line


class UnlockCard(BaseModel):
    """Answer to is_unlocked: a status verdict + the failing leaves.

    status: 'unlocked' | 'locked' | 'indeterminate'.
    An UNKNOWN (cant_verify) leaf surfaces here as a blocker Step (§6).
    """

    node_id: str
    status: str
    blockers: list[Step] = Field(default_factory=list)
```

> Edit the existing import `from pydantic import BaseModel` to `from pydantic import BaseModel, Field` rather than adding a second import line.

Run:

```bash
./venv/bin/python -m pytest tests/engine/test_cards.py -q
```

Expected output (PASS):

```
7 passed
```

---

- [ ] **Step 9.10 — failing test: `PlanCard` defaults + nested serialization.** Append to `tests/engine/test_cards.py`. `PlanCard` carries `goal_id`, an ordered `steps: list[Step]`, and `referenced_atoms: list[ReferencedAtom]` (defaults empty). Confirm a fully-populated card round-trips through `model_dump()` with both nested lists serialized.

```python
def test_plan_card_defaults_empty_referenced_atoms():
    card = PlanCard(goal_id="access:fairy_rings", steps=[])
    assert card.goal_id == "access:fairy_rings"
    assert card.steps == []
    assert card.referenced_atoms == []
    assert card.model_dump() == {
        "goal_id": "access:fairy_rings",
        "steps": [],
        "referenced_atoms": [],
    }


def test_plan_card_full_round_trips():
    step = Step(
        node_id="skill:attack",
        name="70 Attack",
        reason="SKILL_LEVEL",
        status="satisfiable",
    )
    atom = ReferencedAtom(atom_type="SKILL_LEVEL", ref_node="skill:attack", threshold=70)
    card = PlanCard(
        goal_id="access:fairy_rings",
        steps=[step],
        referenced_atoms=[atom],
    )
    assert card.model_dump() == {
        "goal_id": "access:fairy_rings",
        "steps": [
            {
                "node_id": "skill:attack",
                "name": "70 Attack",
                "reason": "SKILL_LEVEL",
                "status": "satisfiable",
            }
        ],
        "referenced_atoms": [
            {
                "atom_type": "SKILL_LEVEL",
                "ref_node": "skill:attack",
                "threshold": 70,
                "qty": None,
                "state": None,
                "is_partial": False,
            }
        ],
    }
```

Run:

```bash
./venv/bin/python -m pytest tests/engine/test_cards.py -q
```

Expected output (FAIL):

```
ImportError... cannot import name 'PlanCard' from 'osrs_planner.engine.cards'
```

---

- [ ] **Step 9.11 — minimal impl: add `PlanCard`.** Append to `src/osrs_planner/engine/cards.py`.

```python
class PlanCard(BaseModel):
    """Answer to prereqs_for / next_steps: an ordered plan + the scalars read.

    steps are in topo order (full closure for prereqs_for; the immediately-doable
    frontier subset for next_steps). referenced_atoms is the §5.6 scalar leash.
    """

    goal_id: str
    steps: list[Step] = Field(default_factory=list)
    referenced_atoms: list[ReferencedAtom] = Field(default_factory=list)
```

Run:

```bash
./venv/bin/python -m pytest tests/engine/test_cards.py -q
```

Expected output (PASS):

```
9 passed
```

---

- [ ] **Step 9.12 — full-suite green guard.** Confirm the new card tests pass alongside the rest of the engine package and the repo suite is not broken.

```bash
./venv/bin/python -m pytest tests/engine/ -q && ./venv/bin/python -m pytest -q
```

Expected output (both runs pass; engine run shows the 9 card tests, repo run shows all tests green — exact prior count varies by how many engine tasks precede this one):

```
9 passed
...
<N> passed
```

---

- [ ] **Step 9.13 — commit.** Stage the new package markers, the impl, and the tests, then commit with a conventional message.

```bash
git add src/osrs_planner/engine/__init__.py src/osrs_planner/engine/cards.py tests/engine/__init__.py tests/engine/test_cards.py
git commit -m "feat(engine): pydantic return cards (NodeRef/ReferencedAtom/Step/UnlockCard/PlanCard)"
```

Expected output (a commit is created; file list reflects whichever `__init__.py` markers were new this task):

```
[<branch> <hash>] feat(engine): pydantic return cards (NodeRef/ReferencedAtom/Step/UnlockCard/PlanCard)
 N files changed, M insertions(+)
```

---

**Notes for the implementer / downstream tasks:**
- `cards.NodeRef` (pydantic) is intentionally a *separate* type from `result.NodeRef` (frozen dataclass). The Result envelope's `Refs` uses the dataclass twin; cards use the pydantic twin so the whole card tree serializes via `model_dump()`. Do not unify them.
- `Step.status` values are `'satisfiable' | 'impossible_for_mode' | 'satisfied' | 'cant_verify'`; `Step.reason` is the failing `atom_type` (e.g. `'SKILL_LEVEL'`, `'QUEST'`) or the literal `'satisfied'`. The Engine (Task: `engine.py`) is the only writer of `impossible_for_mode` and `cant_verify`.
- `is_partial` on `ReferencedAtom` is set by the Engine when a `quest`/`achievement_diary` atom is satisfied by a required `state < completed` (§5.6); the card layer just stores/serializes the flag.
- These are deliberately flat (depth ≤ 2: card → list[Step]) matching the schema's amended depth-2 cap and the §5.3 AND-of-ORs projection; the richer `Blocker.any_of` OR-tree and `Expansion` discriminated type from §5.3/§5.5 are out of scope for this task (account-type expansion is a later task).

**Relevant absolute paths:**
- Impl: `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/src/osrs_planner/engine/cards.py`
- Tests: `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/tests/engine/test_cards.py`
- Contract §5 (cards) / §5.6 (referenced_atoms, is_partial): `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/docs/superpowers/specs/2026-06-15-engine-advisor-contract-design.md`

---

### Task 10: `Engine.is_unlocked` — verdict + blockers from Kleene evaluation (`engine/engine.py`)

Wire the three-valued evaluator (Task 7 `conditions.evaluate`) into the first public Engine read. `is_unlocked` resolves a node's `requires` cond_group, folds it via Kleene, maps `Tri → status` (`TRUE`→`unlocked`, `FALSE`→`locked`, `UNKNOWN`→`indeterminate`), and lists each failing/unverifiable leaf as a `cards.Step`. An `UNKNOWN` leaf becomes a `cant_verify` Step (never a false `locked` — contract §6/§7.2). Missing node → `Problem(NOT_FOUND)`; wholly-absent state → `Problem(MISSING_STATE)`. Contract refs: §3.1 (function surface), §4 (Result envelope), §6 (Kleene + `indeterminate`).

This task assumes the Task 8 fixture exists at `tests/engine/conftest.py` providing the worked `(70 Att AND 70 Str) OR full-Void` Scurrius KG (`npc:7221`) as an `InMemoryKGStore`, plus `AccountState` builder helpers. It depends on the spine modules from Tasks 1–9: `result`, `kleene`, `kg/model`, `kg/store`, `state`, `conditions`, `cards`.

**Files:**
- `src/osrs_planner/engine/engine.py` — new; `class Engine` with `is_unlocked` (the only method in this task; `prereqs_for`/`next_steps` are stubbed to `NotImplementedError` and filled in later tasks).
- `tests/engine/test_engine_is_unlocked.py` — new; the five-scenario suite.

---

- [ ] **Step 1 — Failing test: unlocked node → `Ok[UnlockCard]` status `'unlocked'`, no blockers.**

  The Task 8 fixture's Scurrius node (`npc:7221`) has **two** `requires` edges (D5): edge 9004 to the prerequisite node `access:scurrius-lair` (which is itself unconditional in the fixture) AND edge 9005 carrying the flagship `(70 Att AND 70 Str) OR full-Void` cond_group. `is_unlocked` folds BOTH as an AND. The main account with 75 Att / 75 Str satisfies the OR-tree, and the access prereq is unlocked, so the AND-of-edges folds `TRUE`. Create `tests/engine/test_engine_is_unlocked.py`:

  ```python
  """Engine.is_unlocked — verdict + blockers from Kleene evaluation (contract §3.1/§4/§6)."""
  import pytest

  from osrs_planner.engine.engine import Engine
  from osrs_planner.engine.result import Ok, Problem, ProblemKind
  from osrs_planner.engine.cards import UnlockCard
  from osrs_planner.engine.state import AccountState

  # The Task 8 conftest.py exposes by fixture name:
  #   scurrius_kg -> InMemoryKGStore with node npc:7221 carrying the
  #                  (70 Att AND 70 Str) OR full-Void requires cond_group
  #   fresh_main / iron_75atk_60str -> sample AccountStates (optional here;
  #   these tests construct AccountState directly via the spine constructor).
  # SCURRIUS is the goal node id under test.
  SCURRIUS = "npc:7221"


  def test_unlocked_main_meets_stat_branch(scurrius_kg):
      state = AccountState(
          mode="main",
          levels={"skill:attack": 75, "skill:strength": 75},
          observable_families={"skill_level"},  # levels are always observable (§6.4)
      )
      eng = Engine(scurrius_kg)
      res = eng.is_unlocked(state, SCURRIUS)

      assert isinstance(res, Ok)
      assert isinstance(res.card, UnlockCard)
      assert res.card.node_id == SCURRIUS
      assert res.card.status == "unlocked"
      assert res.card.blockers == []
      # grounding leash (§7.4): the subject node is in refs.nodes
      assert SCURRIUS in res.refs.nodes
  ```

  Run it:

  ```bash
  python -m pytest tests/engine/test_engine_is_unlocked.py::test_unlocked_main_meets_stat_branch -q
  ```

  Expected: **FAIL** — `ModuleNotFoundError: No module named 'osrs_planner.engine.engine'` (the module does not exist yet).

- [ ] **Step 2 — Minimal impl: `Engine.is_unlocked` happy path + node/state guards.**

  Create `src/osrs_planner/engine/engine.py`. The helper `_requires_edges` returns ALL of the node's `requires` edges from `kg.edges` (D5: a node may have many, folded as an AND); `_is_state_absent` detects a *wholly-absent* account per **D4** (only `state is None`); `_collect_failures` walks the cond tree collecting failing/unknown leaves as `cards.Step`s (used in Step 4). Use ONLY the spine names.

  ```python
  """The deterministic Engine — public reads over the KG + one AccountState snapshot.

  Contract: every method returns a Result (§4); refs ⊆ nodes touched this turn (§7.4).
  This task implements is_unlocked (§3.1); prereqs_for/next_steps land in later tasks.
  """
  from __future__ import annotations

  from typing import Optional

  from osrs_planner.engine.kg.store import KGStore
  from osrs_planner.engine.kg.model import EdgeType, Op, AtomType, ConditionAtom
  from osrs_planner.engine.state import AccountState
  from osrs_planner.engine.kleene import Tri, k_and
  from osrs_planner.engine.conditions import evaluate, atom_satisfied
  from osrs_planner.engine.result import (
      Ok,
      Problem,
      ProblemKind,
      Result,
      Refs,
      NodeRef,
  )
  from osrs_planner import engine as _engine_pkg  # noqa: F401  (keeps package importable)
  from osrs_planner.engine import cards


  def _is_state_absent(state: Optional[AccountState]) -> bool:
      """A WHOLLY-absent account -> Problem(MISSING_STATE).

      D4: MISSING_STATE fires ONLY when there is no account at all (state is None).
      A fresh real account (mode set, empty progress dicts, combat_level == 3) is a
      VALID account, not missing — its absent values resolve to FALSE/UNKNOWN via the
      absence-aware Kleene rule, never MISSING_STATE.
      """
      return state is None


  class Engine:
      def __init__(self, kg: KGStore):
          self.kg = kg

      # -- helpers ----------------------------------------------------------
      def _requires_edges(self, node_id: str) -> list:
          """ALL of node_id's `requires` edges (D5: a node may have many; folded as AND).

          Each edge contributes (cond_group, dst): the edge is satisfied iff its
          cond_group (if any) is TRUE AND its dst node (if non-NULL) is itself unlocked.
          """
          return [
              edge
              for edge in self.kg.edges
              if edge.type == EdgeType.REQUIRES and edge.src == node_id
          ]

      def _edge_verdict(self, edge, state: AccountState) -> Tri:
          """D5: a single requires edge is satisfied iff its cond_group (if any) is TRUE
          AND its dst node (if non-NULL) is itself unlocked (recursive)."""
          parts: list[Tri] = []
          if edge.cond_group is not None:
              parts.append(evaluate(edge.cond_group, state, self.kg))
          if edge.dst is not None:
              parts.append(self._node_verdict(edge.dst, state))
          return k_and(parts) if parts else Tri.TRUE

      def _node_verdict(self, node_id: str, state: AccountState) -> Tri:
          """Fold ALL of a node's requires edges as an AND (D5)."""
          edges = self._requires_edges(node_id)
          if not edges:
              return Tri.TRUE  # unconditional => unlocked
          return k_and([self._edge_verdict(e, state) for e in edges])

      def _noderef(self, node_id: str) -> NodeRef:
          n = self.kg.node(node_id)
          if n is None:
              return NodeRef(id=node_id, kind="", name=node_id)
          return NodeRef(id=n.id, kind=n.kind.value, name=n.name)

      # -- §3.1 reads -------------------------------------------------------
      def is_unlocked(self, state: Optional[AccountState], node_id: str) -> Result[cards.UnlockCard]:
          # D7: NOT_FOUND carries an EMPTY Refs; the unknown id is named in the message.
          node = self.kg.node(node_id)
          if node is None:
              return Problem(
                  kind=ProblemKind.NOT_FOUND,
                  refs=Refs(),
                  message=f"node {node_id!r} not found",
              )
          # D4: MISSING_STATE only when there is no account at all (state is None).
          if _is_state_absent(state):
              return Problem(
                  kind=ProblemKind.MISSING_STATE,
                  refs=Refs(nodes={node_id: self._noderef(node_id)}),
                  message=f"no account state to evaluate {node_id!r}",
              )

          refs_nodes = {node_id: self._noderef(node_id)}
          # D5: fold ALL of the node's requires edges as an AND.
          edges = self._requires_edges(node_id)
          verdict = self._node_verdict(node_id, state)

          status = {
              Tri.TRUE: "unlocked",
              Tri.FALSE: "locked",
              Tri.UNKNOWN: "indeterminate",
          }[verdict]

          blockers: list[cards.Step] = []
          if verdict is not Tri.TRUE:
              for edge in edges:
                  if edge.cond_group is not None:
                      blockers.extend(
                          self._collect_failures(edge.cond_group, state, refs_nodes)
                      )
                  if edge.dst is not None and self._node_verdict(edge.dst, state) is not Tri.TRUE:
                      # the prerequisite node itself is not unlocked -> surface it as a leaf
                      refs_nodes.setdefault(edge.dst, self._noderef(edge.dst))
                      blockers.append(self._dst_step(edge.dst, state))

          card = cards.UnlockCard(
              node_id=node_id,
              status=status,
              blockers=blockers,
          )
          return Ok(card=card, refs=Refs(nodes=refs_nodes))

      def _collect_failures(
          self, group_id: int, state: AccountState, refs_nodes: dict
      ) -> list[cards.Step]:
          # Filled in Step 4. Empty for now so Step 1 (no blockers) passes.
          return []

      def _dst_step(self, dst_id: str, state: AccountState) -> cards.Step:
          """A prerequisite NODE (D5 edge.dst) that is itself not unlocked -> a Step.

          'is_unlocked' is the reason family (the dst is gated by its own requires);
          UNKNOWN -> cant_verify, otherwise satisfiable.
          """
          tri = self._node_verdict(dst_id, state)
          n = self.kg.node(dst_id)
          return cards.Step(
              node_id=dst_id,
              name=n.name if n is not None else dst_id,
              reason="is_unlocked",
              status="cant_verify" if tri is Tri.UNKNOWN else "satisfiable",
          )

      def prereqs_for(self, state: AccountState, node_id: str) -> Result[cards.PlanCard]:
          raise NotImplementedError  # later task

      def next_steps(self, state: AccountState, node_id: str) -> Result[cards.PlanCard]:
          raise NotImplementedError  # later task
  ```

  Run it:

  ```bash
  python -m pytest tests/engine/test_engine_is_unlocked.py::test_unlocked_main_meets_stat_branch -q
  ```

  Expected: **PASS** — `1 passed`.

- [ ] **Step 3 — Commit.**

  ```bash
  git add src/osrs_planner/engine/engine.py tests/engine/test_engine_is_unlocked.py && git commit -m "feat: Engine.is_unlocked happy path + node/state guards"
  ```

- [ ] **Step 4 — Failing test: ironman locked on the OR-tree surfaces the cheapest blocker (train Strength to 70).**

  The fixture ironman (75 Att / 60 Str / no Void) folds the OR-tree `FALSE` (stat branch fails on Str, Void branch fails on items). The blocker list must name the failing leaf, and the cheapest branch (the single unmet Strength leaf, vs acquiring 4+ Void pieces) must be present with `reason='skill_level'` and a non-`cant_verify` status. Append to the test file:

  ```python
  def test_locked_ironman_or_tree_surfaces_strength_blocker(scurrius_kg):
      state = AccountState(
          mode="ironman",
          levels={"skill:attack": 75, "skill:strength": 60},
          counts={},  # no Void
          observable_families={"skill_level", "item"},  # both real-FALSE here
      )
      eng = Engine(scurrius_kg)
      res = eng.is_unlocked(state, SCURRIUS)

      assert isinstance(res, Ok)
      assert res.card.status == "locked"
      assert res.card.blockers, "a locked node must surface blockers"

      # The cheapest branch (train Strength to 70) is present as a failing skill_level leaf.
      strength_blockers = [
          b
          for b in res.card.blockers
          if b.node_id == "skill:strength" and b.reason == "skill_level"
      ]
      assert strength_blockers, "expected a Strength skill_level blocker"
      sb = strength_blockers[0]
      assert sb.status == "satisfiable"  # not cant_verify, not satisfied
      assert "skill:strength" in res.refs.nodes  # blocker node entered refs (§7.4)

      # No blocker is falsely flagged cant_verify when the family is observable.
      assert all(b.status != "cant_verify" for b in res.card.blockers)


  def test_is_unlocked_folds_all_requires_edges(scurrius_kg):
      # D5: Scurrius has TWO requires edges (the access:scurrius-lair prereq edge AND
      # the flagship cond_group edge). The engine must read and fold BOTH, not just one.
      from osrs_planner.engine.kg.model import EdgeType
      req_edges = [
          e for e in scurrius_kg.edges
          if e.type is EdgeType.REQUIRES and e.src == SCURRIUS
      ]
      assert len(req_edges) == 2, "fixture Scurrius must carry two requires edges (D5)"
      # both edges satisfied for the 70/70 main -> the AND-of-edges folds to unlocked
      state = AccountState(
          mode="main",
          levels={"skill:attack": 75, "skill:strength": 75},
          observable_families={"skill_level"},
      )
      res = Engine(scurrius_kg).is_unlocked(state, SCURRIUS)
      assert isinstance(res, Ok)
      assert res.card.status == "unlocked"
  ```

  Run it:

  ```bash
  python -m pytest tests/engine/test_engine_is_unlocked.py::test_locked_ironman_or_tree_surfaces_strength_blocker -q
  ```

  Expected: **FAIL** — `AssertionError: a locked node must surface blockers` (`_collect_failures` still returns `[]`). (`test_is_unlocked_folds_all_requires_edges` already passes off the Step 2 fold; it is the D5 regression lock.)

- [ ] **Step 5 — Impl: `_collect_failures` walks the cond tree, recording failing/unknown leaves as Steps.**

  Replace the stub `_collect_failures`. It recurses groups via `kg.children_of`, re-evaluates each child (a child int id → `evaluate`; a `ConditionAtom` → `atom_satisfied`), and records any non-`TRUE` leaf. A `FALSE` leaf → status `'satisfiable'` (or `'impossible_for_mode'` only when a false `account_type` atom prunes the branch — §5.3 case b); an `UNKNOWN` leaf → status `'cant_verify'` (§6). Each ref-bearing leaf's `ref_node` enters `refs_nodes`. Replace the stub in `engine.py`:

  ```python
      def _collect_failures(
          self, group_id: int, state: AccountState, refs_nodes: dict
      ) -> list[cards.Step]:
          """Walk the cond tree; record every non-TRUE *leaf* as a failing/unverifiable Step.

          - FALSE leaf            -> status 'satisfiable'  (or 'impossible_for_mode' for a
                                     false account_type atom that prunes its branch, §5.3b)
          - UNKNOWN leaf          -> status 'cant_verify'  (Kleene; never a false 'locked', §6)
          Each ref-bearing leaf's ref_node enters refs_nodes (the grounding leash, §7.4).
          """
          steps: list[cards.Step] = []
          for child in self.kg.children_of(group_id):
              if isinstance(child, ConditionAtom):
                  tri = atom_satisfied(child, state, self.kg)
                  if tri is Tri.TRUE:
                      continue
                  if child.ref_node is not None:
                      refs_nodes.setdefault(child.ref_node, self._noderef(child.ref_node))
                  steps.append(self._leaf_step(child, tri))
              else:  # a sub-group id (int)
                  steps.extend(self._collect_failures(int(child), state, refs_nodes))
          return steps

      def _leaf_step(self, atom: ConditionAtom, tri: Tri) -> cards.Step:
          if tri is Tri.UNKNOWN:
              status = "cant_verify"
          elif atom.atom_type == AtomType.ACCOUNT_TYPE:
              # a false account_type atom is a hard mode wall, not a trainable gap (§5.3b)
              status = "impossible_for_mode"
          else:
              status = "satisfiable"
          name = atom.ref_node
          if atom.ref_node is not None:
              n = self.kg.node(atom.ref_node)
              if n is not None:
                  name = n.name
          return cards.Step(
              node_id=atom.ref_node,
              name=name if name is not None else atom.atom_type.value,
              reason=atom.atom_type.value,
              status=status,
          )
  ```

  Run it:

  ```bash
  python -m pytest tests/engine/test_engine_is_unlocked.py::test_locked_ironman_or_tree_surfaces_strength_blocker -q
  ```

  Expected: **PASS** — `1 passed`.

- [ ] **Step 6 — Commit.**

  ```bash
  git add src/osrs_planner/engine/engine.py tests/engine/test_engine_is_unlocked.py && git commit -m "feat: Engine.is_unlocked blockers from cond-tree leaf walk"
  ```

- [ ] **Step 7 — Failing test: an unobservable atom → status `'indeterminate'` + a `cant_verify` blocker (NOT a false `locked`).**

  The §6 launch-common case: an account whose Strength is unknown (level absent AND `skill_level` not in `observable_families` AND not manually asserted) must fold `UNKNOWN`, not `FALSE`. With the stat branch `AND(75≥70=TRUE, Str=UNKNOWN)=UNKNOWN` and the Void branch `FALSE`, the OR folds `UNKNOWN` → `indeterminate`, surfaced through a `cant_verify` blocker naming `skill:strength`. This is the contract's headline anti-fabrication guarantee — verify it is NOT a false `locked`. Append to the test file:

  ```python
  def test_unobservable_atom_indeterminate_not_false_locked(scurrius_kg):
      # Strength absent AND not observable AND not asserted -> UNKNOWN (§6), not FALSE.
      state = AccountState(
          mode="main",
          levels={"skill:attack": 75},   # strength deliberately absent
          counts={},                      # no Void -> that branch FALSE
          observable_families={"item"},   # 'skill_level' is NOT observable here
      )
      eng = Engine(scurrius_kg)
      res = eng.is_unlocked(state, SCURRIUS)

      assert isinstance(res, Ok)
      # The whole point of §6: an unverifiable input must NOT read as locked.
      assert res.card.status == "indeterminate"
      assert res.card.status != "locked"

      cant_verify = [b for b in res.card.blockers if b.status == "cant_verify"]
      assert cant_verify, "an UNKNOWN leaf must surface a cant_verify blocker"
      assert any(b.node_id == "skill:strength" for b in cant_verify)
      assert "skill:strength" in res.refs.nodes
  ```

  Run it:

  ```bash
  python -m pytest tests/engine/test_engine_is_unlocked.py::test_unobservable_atom_indeterminate_not_false_locked -q
  ```

  Expected: **PASS** — `1 passed`. (The Kleene fold from Task 7 `evaluate` + the `cant_verify` branch added in Step 5 already produce this; this test is the regression lock for the §6 guarantee. If it FAILs, the absence-aware UNKNOWN rule in `conditions.atom_satisfied` / `state` is broken — fix there, not in the Engine.)

- [ ] **Step 8 — Failing test: missing node → `Problem(NOT_FOUND)` (empty refs, id in message); `state is None` → `Problem(MISSING_STATE)`; a fresh valid account is NOT missing.**

  Append the error-contract cases (§4 / §6 / D4 / D7). Note the order: a missing node is caught before the state guard, so `is_unlocked(None, missing_node)` is `NOT_FOUND`.

  ```python
  def test_missing_node_returns_problem_not_found(scurrius_kg):
      state = AccountState(mode="main", levels={"skill:attack": 75})
      eng = Engine(scurrius_kg)
      res = eng.is_unlocked(state, "npc:does-not-exist")

      assert isinstance(res, Problem)
      assert res.kind == ProblemKind.NOT_FOUND
      # D7: NOT_FOUND carries an EMPTY Refs; the unknown id is named in the message,
      # NOT inside refs.nodes (an unknown id is not a node, so not a NodeRef).
      assert res.refs.nodes == {}
      assert "npc:does-not-exist" in res.message


  def test_none_state_returns_problem_missing_state(scurrius_kg):
      eng = Engine(scurrius_kg)
      res = eng.is_unlocked(None, SCURRIUS)  # D4: only state is None is MISSING_STATE

      assert isinstance(res, Problem)
      assert res.kind == ProblemKind.MISSING_STATE
      assert SCURRIUS in res.refs.nodes  # the subject is named even on failure (§7.4)


  def test_fresh_valid_account_is_not_missing_state(scurrius_kg):
      # D4: a fresh real account (mode set, empty progress, combat_level == 3) is VALID,
      # not missing — its absent values resolve via the Kleene rule, never MISSING_STATE.
      fresh = AccountState(mode="main")
      res = Engine(scurrius_kg).is_unlocked(fresh, SCURRIUS)
      assert isinstance(res, Ok)
      assert res.card.status in {"locked", "indeterminate"}  # never MISSING_STATE
  ```

  Run it:

  ```bash
  python -m pytest tests/engine/test_engine_is_unlocked.py -k "not_found or missing_state or fresh_valid" -q
  ```

  Expected: **PASS** — `3 passed`. (The guards exist from Step 2; this locks the §4 error contract, the guard ordering, D4, and D7. If `test_fresh_valid_account_is_not_missing_state` FAILs, `_is_state_absent` is using a non-`None` heuristic — fix it to `state is None` per D4.)

- [ ] **Step 9 — Full-suite green check + commit.**

  ```bash
  python -m pytest tests/engine/test_engine_is_unlocked.py -q
  ```

  Expected: **PASS** — `7 passed`.

  ```bash
  git add tests/engine/test_engine_is_unlocked.py && git commit -m "test: Engine.is_unlocked indeterminate + error-contract cases (§4/§6)"
  ```

---

Drafted task file paths (load-bearing, for the plan):
- Implementation: `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/src/osrs_planner/engine/engine.py`
- Test: `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/tests/engine/test_engine_is_unlocked.py`

Cross-task dependencies the plan author must ensure are satisfied before Task 10 runs:
- Task 8 must provide `tests/engine/conftest.py` with a `scurrius_kg` fixture (the `(70 Att AND 70 Str) OR full-Void` KG on `npc:7221`, as an `InMemoryKGStore`). Task 10's tests construct `AccountState` directly via the spine constructor, so a `make_state` helper is optional.
- Task 7's `conditions.atom_satisfied` must already implement the absence-aware UNKNOWN rule (Step 7 depends on it and is written as a regression lock, not the place to implement it).

Two spine-fidelity notes for the author to confirm against earlier tasks: (1) `cards.Step.status` uses the literal `'cant_verify'` / `'satisfiable'` / `'impossible_for_mode'` strings from the spine; the spine's `'satisfied'` value is unused by `is_unlocked` (only failing leaves are emitted). (2) `cards.UnlockCard.blockers` in the spine is `list[Step]` (a flat list), so this task emits flat Steps — it does NOT use the contract's richer `Blocker{any_of, cheapest_branch}` AND-of-ORs shape from §5.3, which the fixed type-spine deliberately simplifies away.

---

### Task 11: `Engine.prereqs_for` — full ordered prereq closure as a `PlanCard`

`prereqs_for(state, node_id)` answers "the whole plan: everything this goal needs, in a valid completion order, each marked done / satisfiable / can't-verify." It walks the requires-DAG closure (`descendants`), orders it (`topo_order`), and emits one `Step` per prerequisite carrying its Kleene-derived status, plus the `referenced_atoms` the Engine actually read. Already-satisfied goal → `Empty(ALREADY_SATISFIED)`; a cyclic sub-graph → `Problem(UNSATISFIABLE_CYCLE)`; missing node → `Problem(NOT_FOUND)`; wholly-absent state → `Problem(MISSING_STATE)`. References contract §3.1 (the `PlanCard` read), §4 (the envelope + `TerminalReason`/`ProblemKind`), and the kg-schema requires-DAG projection (`a→b` = "a requires b"; closure = `descendants`; order = `reversed(topological_sort)`; `kind` separates hard `requires` from `cond_dep` OR-alternatives; I1 acyclicity).

This task assumes the type-spine modules from the earlier tasks already exist and pass: `engine/result.py`, `engine/kleene.py`, `engine/kg/model.py`, `engine/kg/store.py` (with `node`, `descendants`, `topo_order`, `find_cycles`, `requires_dag`), `engine/state.py`, `engine/conditions.py` (`evaluate`, `atom_satisfied`), `engine/cards.py` (the pydantic `Step`, `PlanCard`, `ReferencedAtom`), and `engine/engine.py` already containing `class Engine` with `__init__` + `is_unlocked` from Task 10. We only ADD the `prereqs_for` method and a small private status helper here.

**Files:**
- `tests/engine/test_engine_prereqs.py` (NEW — this task's tests)
- `src/osrs_planner/engine/engine.py` (EDIT — add `prereqs_for` + `_step_status_for` helper; existing `is_unlocked` untouched)

All run commands are from the repo root `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool`. The venv is already created in earlier tasks; activate per the project convention (`source venv/bin/activate`) before the pytest commands, or prefix with `venv/bin/python -m`.

---

- [ ] **Step 1 — Failing test: `not_found` guard before traversal (§4 / error contract).** Create `tests/engine/test_engine_prereqs.py`. The fixture builds a tiny KG: goal `npc:scur` (Scurrius) requires `access:scur-lair`, which is granted-by/requires `quest:rfd` (a completed quest). We assert a typo id returns `Problem(NOT_FOUND)` (guard `source ∈ dag` before `descendants()`, per §10).

  ```python
  # tests/engine/test_engine_prereqs.py
  from osrs_planner.engine.engine import Engine
  from osrs_planner.engine.result import Ok, Empty, Problem, ProblemKind, TerminalReason
  from osrs_planner.engine.state import AccountState
  from osrs_planner.engine.kg.store import InMemoryKGStore
  from osrs_planner.engine.kg.model import (
      Node, Edge, ConditionGroup, ConditionAtom,
      NodeKind, EdgeType, Op, AtomType,
  )


  def _fixture_kg():
      """A 3-node prereq chain:
         npc:scur --requires--> access:scur-lair --requires--> quest:rfd (state=completed)
                                  and             --requires--> skill:attack >= 50
      Goal closure of npc:scur = {access:scur-lair, quest:rfd, skill:attack}.
      """
      nodes = [
          Node(id="npc:scur", kind=NodeKind.MONSTER, name="Scurrius", slug="scurrius"),
          Node(id="access:scur-lair", kind=NodeKind.ACCESS, name="Scurrius' Lair", slug="scurrius-lair"),
          Node(id="quest:rfd", kind=NodeKind.QUEST, name="Recipe for Disaster", slug="recipe-for-disaster"),
          Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack"),
      ]
      # cond groups (one per requires edge that carries a leaf)
      groups = {
          1: ConditionGroup(id=1, op=Op.AND, parent=None, children=[
              ConditionAtom(atom_type=AtomType.IS_UNLOCKED, ref_node="access:scur-lair"),
          ]),
          2: ConditionGroup(id=2, op=Op.AND, parent=None, children=[
              ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:rfd",
                            data={"state": "completed"}),
          ]),
          3: ConditionGroup(id=3, op=Op.AND, parent=None, children=[
              ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=50),
          ]),
      }
      edges = [
          Edge(id=1, type=EdgeType.REQUIRES, src="npc:scur", dst="access:scur-lair", cond_group=1),
          Edge(id=2, type=EdgeType.REQUIRES, src="access:scur-lair", dst="quest:rfd", cond_group=2),
          Edge(id=3, type=EdgeType.REQUIRES, src="access:scur-lair", dst="skill:attack", cond_group=3),
      ]
      return InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)


  def _partial_state():
      """Attack done, quest + access not — so the goal is NOT yet satisfied."""
      return AccountState(
          mode="main",
          levels={"skill:attack": 70},
          quest_state={"quest:rfd": "not_started"},
          observable_families={"skill_level", "quest", "is_unlocked"},
      )


  def test_prereqs_for_unknown_node_is_not_found():
      eng = Engine(_fixture_kg())
      res = eng.prereqs_for(_partial_state(), "npc:does-not-exist")
      assert isinstance(res, Problem)
      assert res.kind is ProblemKind.NOT_FOUND
      # D7: NOT_FOUND carries an EMPTY Refs; the id is named in the message, not refs.
      assert res.refs.nodes == {} and res.refs.mentions == {}
      assert "npc:does-not-exist" in res.message
  ```

  Run:
  ```
  venv/bin/python -m pytest tests/engine/test_engine_prereqs.py::test_prereqs_for_unknown_node_is_not_found -q
  ```
  Expected: **FAIL** — `AttributeError: 'Engine' object has no attribute 'prereqs_for'` (the method doesn't exist yet).

- [ ] **Step 2 — Minimal impl: `prereqs_for` skeleton with the `not_found` / `missing_state` guards.** Open `src/osrs_planner/engine/engine.py` and add the method to the existing `Engine` class. Add these imports at the top of the file if not already present (Task 10 will have most of them):

  ```python
  from osrs_planner.engine.result import (
      Ok, Empty, Problem, Refs, NodeRef, ProblemKind, TerminalReason, Result,
  )
  from osrs_planner.engine.kleene import Tri
  from osrs_planner.engine.conditions import evaluate, atom_satisfied
  from osrs_planner.engine.cards import PlanCard, Step, ReferencedAtom
  from osrs_planner.engine.kg.model import ConditionAtom, ConditionGroup
  ```

  Add the method (place it after `is_unlocked`):

  ```python
      def prereqs_for(self, state, node_id) -> "Result[PlanCard]":
          # §10: guard source ∈ dag before descendants()
          node = self.kg.node(node_id)
          if node is None:
              # D7: NOT_FOUND carries an EMPTY Refs; the unknown id is named in the
              # message only (an unknown id is not a node, so it cannot be a NodeRef).
              return Problem(
                  kind=ProblemKind.NOT_FOUND,
                  refs=Refs(),
                  message=f"no node with id {node_id!r}",
              )
          # D4: MISSING_STATE only when there is no account at all (state is None);
          # a fresh valid account (mode set, empty progress, combat_level == 3) is NOT missing.
          if state is None:
              return Problem(
                  kind=ProblemKind.MISSING_STATE,
                  refs=Refs(nodes={node_id: NodeRef(id=node.id, kind=node.kind, name=node.name)}),
                  message=f"no account state to evaluate {node_id!r}",
              )
          raise NotImplementedError  # filled in by later steps
  ```

  Run:
  ```
  venv/bin/python -m pytest tests/engine/test_engine_prereqs.py::test_prereqs_for_unknown_node_is_not_found -q
  ```
  Expected: **PASS** (1 passed).

- [ ] **Step 3 — Failing test: `missing_state` only for `state is None`; a fresh valid account is NOT missing (D4).** Append to the test file:

  ```python
  def test_prereqs_for_none_state_is_missing_state():
      eng = Engine(_fixture_kg())
      res = eng.prereqs_for(None, "npc:scur")  # D4: only state is None is MISSING_STATE
      assert isinstance(res, Problem)
      assert res.kind is ProblemKind.MISSING_STATE
      assert "npc:scur" in res.refs.nodes


  def test_prereqs_for_fresh_valid_account_is_not_missing_state():
      # D4: a fresh real account (mode set, empty progress, combat_level == 3) is VALID;
      # it must NOT be MISSING_STATE — it flows into the normal closure/plan path.
      eng = Engine(_fixture_kg())
      res = eng.prereqs_for(AccountState(mode="main"), "npc:scur")
      assert not (isinstance(res, Problem) and res.kind is ProblemKind.MISSING_STATE)
  ```

  Run:
  ```
  venv/bin/python -m pytest tests/engine/test_engine_prereqs.py -k "missing_state or fresh_valid" -q
  ```
  Expected: **PASS** already (the Step-2 `state is None` guard covers it). This locks D4 before we build the closure path; if `test_prereqs_for_fresh_valid_account_is_not_missing_state` FAILS, the guard is using a non-`None` heuristic — fix it to `state is None`.

- [ ] **Step 4 — Commit the guards.**
  ```
  cd /Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool && git add tests/engine/test_engine_prereqs.py src/osrs_planner/engine/engine.py && git commit -m "feat: prereqs_for guards (not_found + missing_state)"
  ```
  Expected: one commit created listing the two files.

- [ ] **Step 5 — Failing test: cyclic sub-graph → `Problem(UNSATISFIABLE_CYCLE)`.** A cycle should never survive the KG build (I1 FAILs the build), but the Engine must still fail closed rather than loop forever if a hand-authored fixture is bad. Append:

  ```python
  def _cyclic_kg():
      """A:requires->B, B:requires->A. find_cycles() must report it."""
      nodes = [
          Node(id="a", kind=NodeKind.ACCESS, name="A", slug="a"),
          Node(id="b", kind=NodeKind.ACCESS, name="B", slug="b"),
      ]
      edges = [
          Edge(id=1, type=EdgeType.REQUIRES, src="a", dst="b"),
          Edge(id=2, type=EdgeType.REQUIRES, src="b", dst="a"),
      ]
      return InMemoryKGStore(nodes=nodes, edges=edges, groups={})


  def test_prereqs_for_cycle_is_unsatisfiable_cycle():
      eng = Engine(_cyclic_kg())
      state = AccountState(mode="main", done={"x"})  # non-empty so we pass the missing_state guard
      res = eng.prereqs_for(state, "a")
      assert isinstance(res, Problem)
      assert res.kind is ProblemKind.UNSATISFIABLE_CYCLE
      # cycle nodes are surfaced for the Advisor (§4: refs ⊆ touched nodes)
      assert "a" in res.refs.mentions or "a" in res.refs.nodes
  ```

  Run:
  ```
  venv/bin/python -m pytest tests/engine/test_engine_prereqs.py::test_prereqs_for_cycle_is_unsatisfiable_cycle -q
  ```
  Expected: **FAIL** — currently raises `NotImplementedError` (the Step-2 skeleton).

- [ ] **Step 6 — Minimal impl: cycle detection in `prereqs_for`.** Replace the `raise NotImplementedError` line with the cycle guard followed by a placeholder:

  ```python
          # I1: cycles fail the build; guard at runtime so a bad fixture fails closed (§10).
          cycles = self.kg.find_cycles()
          cycle_nodes = {n for cyc in cycles for n in cyc}
          closure = self.kg.descendants(node_id)
          relevant = cycle_nodes & (closure | {node_id})
          if relevant:
              cyc_refs = {
                  nid: NodeRef(id=nid, kind=(self.kg.node(nid).kind if self.kg.node(nid) else "?"),
                               name=(self.kg.node(nid).name if self.kg.node(nid) else nid))
                  for nid in relevant
              }
              return Problem(
                  kind=ProblemKind.UNSATISFIABLE_CYCLE,
                  refs=Refs(mentions=cyc_refs),
                  message=f"prereq cycle: {sorted(relevant)}",
              )
          raise NotImplementedError  # closure build filled in by later steps
  ```

  Run:
  ```
  venv/bin/python -m pytest tests/engine/test_engine_prereqs.py::test_prereqs_for_cycle_is_unsatisfiable_cycle -q
  ```
  Expected: **PASS** (1 passed).

- [ ] **Step 7 — Commit the cycle guard.**
  ```
  cd /Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool && git add tests/engine/test_engine_prereqs.py src/osrs_planner/engine/engine.py && git commit -m "feat: prereqs_for fails closed on prereq cycle"
  ```
  Expected: one commit created.

- [ ] **Step 8 — Failing test: already-satisfied goal → `Empty(ALREADY_SATISFIED)`.** Append. State has the access unlocked, the quest completed, and 70 Attack — so the goal's requires cond_group evaluates `TRUE` and the whole closure is met:

  ```python
  def _satisfied_state():
      return AccountState(
          mode="main",
          levels={"skill:attack": 70},
          quest_state={"quest:rfd": "completed"},
          done={"access:scur-lair"},
          observable_families={"skill_level", "quest", "is_unlocked"},
      )


  def test_prereqs_for_satisfied_goal_is_empty_already_satisfied():
      eng = Engine(_fixture_kg())
      res = eng.prereqs_for(_satisfied_state(), "npc:scur")
      assert isinstance(res, Empty)
      assert res.reason is TerminalReason.ALREADY_SATISFIED
      assert res.status == "ok"
      assert "npc:scur" in res.refs.nodes
  ```

  Run:
  ```
  venv/bin/python -m pytest tests/engine/test_engine_prereqs.py::test_prereqs_for_satisfied_goal_is_empty_already_satisfied -q
  ```
  Expected: **FAIL** — still `NotImplementedError`.

- [ ] **Step 9 — Minimal impl: already-satisfied short-circuit + the status helper.** First add the per-prereq status helper to `Engine` (returns the spine's `(status, reason)` pair for a node, mirroring the §5.2 status vocab + the §6 Kleene mapping). **D5/Defect-5: a prereq's Step status reflects whether the ACCOUNT meets that prereq, NOT the prereq's own downstream sub-requires.** A prereq is referenced from its parent by one or more condition atoms (a `quest` atom carrying its required `state`, an `is_unlocked` atom checking `done`, a `skill_level` atom with a threshold, …); the account "meets" the prereq iff every atom that references it (folded AND) is satisfied. We therefore evaluate the atoms whose `ref_node == node_id` anywhere in the closure's cond trees, via `atom_satisfied`:

  ```python
      def _atoms_referencing(self, node_id) -> list:
          """Every condition atom (in any requires cond_group across the KG) whose
          ref_node is node_id — i.e. how a PARENT references this prereq (quest state,
          is_unlocked, skill_level threshold, …). This is the account-meets-prereq test,
          not the prereq's own downstream requires (Defect 5)."""
          out = []
          for e in self.kg.edges:
              if e.type.value == "requires" and e.cond_group is not None:
                  for atom in self._iter_group_atoms(e.cond_group):
                      if atom.ref_node == node_id:
                          out.append(atom)
          return out

      def _account_meets_tri(self, state, node_id) -> "Tri":
          """AND-fold of every atom that references node_id (does the ACCOUNT meet it?).
          No referencing atom (e.g. the goal itself, or a bare dst node) -> fold its OWN
          requires edges so a node-type prereq reads as 'is it itself unlocked' (D5)."""
          from osrs_planner.engine.kleene import k_and
          refs = self._atoms_referencing(node_id)
          if refs:
              return k_and([atom_satisfied(a, state, self.kg) for a in refs])
          # node-type prereq with no referencing atom: is it itself unlocked? (D5 recursion)
          own = [
              evaluate(e.cond_group, state, self.kg)
              for e in self.kg.edges
              if e.type.value == "requires" and e.src == node_id and e.cond_group is not None
          ]
          return k_and(own) if own else Tri.TRUE

      def _step_status_for(self, state, node_id) -> tuple[str, str]:
          """Map whether the ACCOUNT meets a prereq to a Step (status, reason). §5.2 vocab:
          satisfied | satisfiable | cant_verify (UNKNOWN) | impossible_for_mode."""
          tri = self._account_meets_tri(state, node_id)
          if tri is Tri.TRUE:
              return ("satisfied", "satisfied")
          if tri is Tri.UNKNOWN:
              return ("cant_verify", self._first_reason(state, node_id, Tri.UNKNOWN))
          # FALSE -> not yet met but reachable; impossible_for_mode is set elsewhere
          # (only via Unacquirable / pruned account_type branch — not computed in v1 here).
          return ("satisfiable", self._first_reason(state, node_id, Tri.FALSE))
  ```

  Add the atom-walk + reason-extractor helpers (the `reason` names the failing/unknown atom_type per §5.2 — chosen from the atoms that REFERENCE the prereq, falling back to its own atoms):

  ```python
      def _iter_atoms_for(self, node_id):
          for e in self.kg.edges:
              if e.type.value == "requires" and e.src == node_id and e.cond_group is not None:
                  yield from self._iter_group_atoms(e.cond_group)

      def _iter_group_atoms(self, group_id):
          for child in self.kg.children_of(group_id):
              if isinstance(child, ConditionAtom):
                  yield child
              else:
                  gid = child.id if isinstance(child, ConditionGroup) else child
                  yield from self._iter_group_atoms(gid)

      def _first_reason(self, state, node_id, want) -> str:
          # name the atom (referencing the prereq) whose verdict is `want` (FALSE/UNKNOWN)
          for atom in self._atoms_referencing(node_id):
              if atom_satisfied(atom, state, self.kg) is want:
                  return atom.atom_type.value
          for atom in self._iter_atoms_for(node_id):
              if atom_satisfied(atom, state, self.kg) is want:
                  return atom.atom_type.value
          return "requires"
  ```

  Now replace the Step-6 `raise NotImplementedError` with the already-satisfied check + a placeholder for the build:

  ```python
          goal_ref = {node_id: NodeRef(id=node.id, kind=node.kind, name=node.name)}
          # Already satisfied = the goal's own requires fold is TRUE AND the account meets
          # every prereq. prereq_ids is PREREQS-FIRST (D1: reversed topological_sort).
          goal_tri = self._node_verdict(node_id, state)  # the goal's own requires fold (D5)
          prereq_ids = self.kg.topo_order(node_id)        # prerequisites BEFORE the goal (D1)
          prereq_ids = [pid for pid in prereq_ids if pid != node_id]
          all_done = all(self._account_meets_tri(state, pid) is Tri.TRUE for pid in prereq_ids)
          if goal_tri is Tri.TRUE and all_done:
              return Empty(refs=Refs(nodes=goal_ref), reason=TerminalReason.ALREADY_SATISFIED)
          raise NotImplementedError  # PlanCard build in the next step
  ```

  Run:
  ```
  venv/bin/python -m pytest tests/engine/test_engine_prereqs.py::test_prereqs_for_satisfied_goal_is_empty_already_satisfied -q
  ```
  Expected: **PASS** (1 passed). (Re-run the full file to confirm no regression in the four prior tests — the cycle/guard tests still pass.)

- [ ] **Step 10 — Commit already-satisfied + status helpers.**
  ```
  cd /Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool && git add tests/engine/test_engine_prereqs.py src/osrs_planner/engine/engine.py && git commit -m "feat: prereqs_for already-satisfied -> Empty(ALREADY_SATISFIED) + step-status helper"
  ```
  Expected: one commit created.

- [ ] **Step 11 — Failing test: the `PlanCard` itself — full closure, prereqs-first order (D1), per-step status, refs.** Append. With `_partial_state()` (Attack 70 done, quest not started, access not unlocked) the goal is NOT satisfied, so we get `Ok(PlanCard)`. We assert: the closure equals all three prereqs (goal excluded); the order is **prereqs-first** (D1: `reversed(topological_sort)`, edge `a→b` = "a requires b") so a prerequisite always precedes the node that requires it — `access:scur-lair` (which requires the quest + the skill) must come AFTER `quest:rfd` and `skill:attack`; per-step statuses reflect whether the ACCOUNT meets each prereq (Defect 5), NOT the prereq's own downstream requires; and every step node ∈ `refs.nodes` (the §7.4 grounding invariant).

  ```python
  def test_prereqs_for_returns_ordered_plancard():
      eng = Engine(_fixture_kg())
      res = eng.prereqs_for(_partial_state(), "npc:scur")
      assert isinstance(res, Ok)
      card = res.card
      assert isinstance(card, PlanCard)
      assert card.goal_id == "npc:scur"

      ids = [s.node_id for s in card.steps]
      assert set(ids) == {"access:scur-lair", "quest:rfd", "skill:attack"}

      # valid completion order: access requires quest + skill, so it must come AFTER both.
      assert ids.index("access:scur-lair") > ids.index("quest:rfd")
      assert ids.index("access:scur-lair") > ids.index("skill:attack")

      by_id = {s.node_id: s for s in card.steps}
      assert by_id["skill:attack"].status == "satisfied"      # 70 >= 50
      assert by_id["skill:attack"].reason == "satisfied"
      assert by_id["quest:rfd"].status == "satisfiable"        # not_started < completed
      assert by_id["quest:rfd"].reason == "quest"
      assert by_id["access:scur-lair"].status == "satisfiable" # is_unlocked false
      assert by_id["access:scur-lair"].reason == "is_unlocked"

      # §7.4 grounding invariant: every step node is in refs.nodes (refs live on the
      # envelope, NOT on PlanCard — see Task 9 cards.py + Task 13 integration test).
      for nid in ids:
          assert nid in res.refs.nodes


  def test_prereqs_for_collects_referenced_atoms():
      eng = Engine(_fixture_kg())
      card = eng.prereqs_for(_partial_state(), "npc:scur").card
      kinds = {(a.atom_type, a.ref_node) for a in card.referenced_atoms}
      assert ("skill_level", "skill:attack") in kinds
      assert ("quest", "quest:rfd") in kinds
      assert ("is_unlocked", "access:scur-lair") in kinds
      # the quest atom carries its required state for the §7.2 scalar check
      quest_atom = next(a for a in card.referenced_atoms if a.atom_type == "quest")
      assert quest_atom.state == "completed"
      # skill_level atom carries its threshold
      skill_atom = next(a for a in card.referenced_atoms if a.atom_type == "skill_level")
      assert skill_atom.threshold == 50
  ```

  Run:
  ```
  venv/bin/python -m pytest tests/engine/test_engine_prereqs.py::test_prereqs_for_returns_ordered_plancard tests/engine/test_engine_prereqs.py::test_prereqs_for_collects_referenced_atoms -q
  ```
  Expected: **FAIL** — still `NotImplementedError`.

- [ ] **Step 12 — Minimal impl: build the ordered `PlanCard` with steps + referenced_atoms.** Replace the Step-9 `raise NotImplementedError` with the build. Order is `topo_order(goal)` (the kg-schema `reversed(topological_sort)` of the closure — a valid completion order, prerequisites first). We also collect `referenced_atoms` by walking every prereq's atoms once (deduped):

  ```python
          steps: list[Step] = []
          refs_nodes = dict(goal_ref)
          ref_atoms: list[ReferencedAtom] = []
          seen_atoms: set[tuple] = set()

          for pid in prereq_ids:                       # prereqs-first order (D1), goal excluded
              pnode = self.kg.node(pid)
              status, reason = self._step_status_for(state, pid)   # account-meets-prereq (Defect 5)
              steps.append(Step(node_id=pid,
                                name=(pnode.name if pnode else pid),
                                reason=reason,
                                status=status))
              if pnode is not None:
                  refs_nodes[pid] = NodeRef(id=pnode.id, kind=pnode.kind, name=pnode.name)

          # referenced_atoms = every atom the Engine read across the goal's + prereqs' requires
          # trees (the goal's own atoms reference the top-level prereqs, so include node_id).
          for owner in [node_id] + prereq_ids:
              for atom in self._iter_atoms_for(owner):
                  key = (atom.atom_type.value, atom.ref_node, atom.threshold, atom.qty)
                  if key in seen_atoms:
                      continue
                  seen_atoms.add(key)
                  partial = (atom.atom_type.value == "quest"
                             and atom.data.get("state", "completed") != "completed")
                  ref_atoms.append(ReferencedAtom(
                      atom_type=atom.atom_type.value,
                      ref_node=atom.ref_node,
                      threshold=atom.threshold,
                      qty=atom.qty,
                      state=atom.data.get("state"),
                      is_partial=partial,
                  ))

          return Ok(
              card=PlanCard(goal_id=node_id, steps=steps, referenced_atoms=ref_atoms),
              refs=Refs(nodes=refs_nodes),
          )
  ```

  Run:
  ```
  venv/bin/python -m pytest tests/engine/test_engine_prereqs.py::test_prereqs_for_returns_ordered_plancard tests/engine/test_engine_prereqs.py::test_prereqs_for_collects_referenced_atoms -q
  ```
  Expected: **PASS** (2 passed).

- [ ] **Step 13 — Failing test: a `cant_verify` step when a ref-bearing atom is unobservable (§6 Kleene).** Append. Here the account does NOT mark `quest` observable, and the quest is absent + not asserted → `atom_satisfied` returns `UNKNOWN` → the step is `cant_verify` (not a false `satisfiable`/locked). Attack stays observable+done.

  ```python
  def _unobservable_quest_state():
      return AccountState(
          mode="main",
          levels={"skill:attack": 70},
          # quest_state intentionally absent; 'quest' NOT in observable_families
          observable_families={"skill_level"},
      )


  def test_prereqs_for_unobservable_atom_is_cant_verify():
      eng = Engine(_fixture_kg())
      res = eng.prereqs_for(_unobservable_quest_state(), "npc:scur")
      assert isinstance(res, Ok)
      by_id = {s.node_id: s for s in res.card.steps}
      assert by_id["quest:rfd"].status == "cant_verify"
      assert by_id["quest:rfd"].reason == "quest"
      # the observable, met skill stays satisfied (UNKNOWN must not bleed across steps)
      assert by_id["skill:attack"].status == "satisfied"
  ```

  Run:
  ```
  venv/bin/python -m pytest tests/engine/test_engine_prereqs.py::test_prereqs_for_unobservable_atom_is_cant_verify -q
  ```
  Expected: **PASS** if `conditions.atom_satisfied` already honors the absence-aware UNKNOWN rule (built in an earlier task) and `_step_status_for` maps `Tri.UNKNOWN -> cant_verify` (Step 9). If it **FAILS**, the bug is in the earlier `conditions.py` Kleene rule, not this task — fix there, do not special-case here. This test guards the §6 contract end-to-end through `prereqs_for`.

- [ ] **Step 14 — Run the whole file + the full engine suite (verification before commit, §12).**
  ```
  venv/bin/python -m pytest tests/engine/test_engine_prereqs.py -q && venv/bin/python -m pytest tests/engine -q
  ```
  Expected: the prereqs file shows **8 passed**; the full `tests/engine` run is **all green** (no regression in `result`, `kleene`, `model`, `store`, `conditions`, `cards`, `is_unlocked` tests). Do not proceed to commit until both runs are green.

- [ ] **Step 15 — Commit the `PlanCard` build.**
  ```
  cd /Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool && git add tests/engine/test_engine_prereqs.py src/osrs_planner/engine/engine.py && git commit -m "feat: prereqs_for returns ordered PlanCard with per-step status + referenced_atoms"
  ```
  Expected: one commit created listing the two files.

---

Notes for the implementer (load-bearing semantics, not optional):
- **Order source of truth:** use `KGStore.topo_order(goal_id)` (defined as `reversed(topological_sort)` of the closure in kg-schema). Do not re-sort; the test's `index(...)` assertions verify it is a valid completion order (prerequisites before dependents).
- **`reason` vocab** is exactly the failing `atom_type` value (e.g. `"quest"`, `"is_unlocked"`, `"skill_level"`) or the literal `"satisfied"` — matching `cards.Step.reason` ("the failing atom_type or 'satisfied'"). Do not invent prose reasons.
- **`status` vocab** is exactly `"satisfiable" | "impossible_for_mode" | "satisfied" | "cant_verify"`. `impossible_for_mode` is intentionally NOT computed in this task (§5.3 says it is set only via `Unacquirable` / a pruned `account_type` branch — that lands with the `expand_for_account` task); a `Tri.FALSE` prereq is `satisfiable` here.
- **Kleene must not bleed:** each step's status is evaluated from that node's own cond fold, so an `UNKNOWN` on one prereq never flips a sibling — verified by Step 13.
- **Grounding invariant (§7.4):** every node placed in a `Step` is also placed in `refs.nodes`; the goal node is in `refs.nodes` for every return path (`Ok`, `Empty`, and `Problem` other than `NOT_FOUND`, where the unknown id goes to `mentions`). No `set`/`tuple`/`networkx` object leaks into a card (§5/§11).

File paths touched: `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/tests/engine/test_engine_prereqs.py` (new) and `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/src/osrs_planner/engine/engine.py` (edit).

---

### Task 12: `Engine.next_steps` — the immediately-doable frontier

Implements the third read on the function surface (contract §3.1). `next_steps` is the **frontier subset** of `prereqs_for`: only those prerequisites whose OWN prerequisites are all already satisfied — i.e. the items the account can act on *right now*. It reuses `prereqs_for`'s machinery (closure → topo order → per-prereq status) so the two reads can never drift (contract §5.2: "the *same instances*"), then filters to the actionable layer. When nothing is actionable (everything left is blocked behind an unverifiable gate or an unmet upstream prereq), it returns `Empty(NO_FRONTIER)` — a success state, not a `Problem` (contract §4: "Empty is a success state"). An already-satisfied goal still short-circuits to `Empty(ALREADY_SATISFIED)`, exactly like `prereqs_for`.

**Frontier rule (precise):** a prereq node `p` is on the frontier iff (a) `p` is itself NOT yet satisfied (`status != 'satisfied'`), AND (b) every node in `p`'s own `requires`-closure (its descendants in the `requires_dag`) IS satisfied for the account. An `impossible_for_mode` prereq is never on the frontier (you can't act on it). A prereq blocked only by an UNKNOWN (`cant_verify`) upstream is *not* actionable either — its predecessor isn't satisfied. This matches §7.2's note that the `plan_order` check is "a no-op on the `next_steps` frontier" — frontier steps have no unmet predecessors among each other.

**Files:**
- `src/osrs_planner/engine/engine.py` (extend the existing `Engine` class — `is_unlocked` + `prereqs_for` already present from Tasks 10–11)
- `tests/engine/test_engine_next_steps.py` (new)

Assumes Tasks 1–11 are merged: `result.py`, `kleene.py`, `kg/model.py`, `kg/store.py` (`InMemoryKGStore` with `descendants`/`topo_order`), `state.py`, `conditions.py`, `cards.py`, and `Engine.is_unlocked` + `Engine.prereqs_for` returning a `PlanCard` of ordered `Step`s.

---

- [ ] **Step 1 — Write the failing test for the basic frontier case.**

  A goal `quest:goal` requires two prereqs: `skill:attack` (level 40) and `quest:sub`. `quest:sub` itself requires `skill:cooking` (level 20). The account already has 20 Cooking but not 40 Attack and has not started `quest:sub`. The frontier should be exactly the two prereqs whose own prereqs are all met: `skill:attack` (no sub-prereqs) and `quest:sub` (its only prereq, 20 Cooking, is satisfied). `skill:cooking` is already satisfied so it is NOT on the frontier (frontier excludes already-done). Create `tests/engine/test_engine_next_steps.py`:

  ```python
  import pytest

  from osrs_planner.engine.engine import Engine
  from osrs_planner.engine.kg.store import InMemoryKGStore
  from osrs_planner.engine.kg.model import (
      Node, Edge, ConditionGroup, ConditionAtom,
      NodeKind, EdgeType, Op, AtomType,
  )
  from osrs_planner.engine.state import AccountState
  from osrs_planner.engine.result import Ok, Empty, Problem, ProblemKind, TerminalReason
  from osrs_planner.engine.cards import PlanCard


  def _two_layer_kg():
      """goal --requires--> {attack>=40, quest:sub}; quest:sub --requires--> cooking>=20."""
      nodes = [
          Node(id="quest:goal", kind=NodeKind.QUEST, name="The Goal", slug="goal"),
          Node(id="quest:sub", kind=NodeKind.QUEST, name="The Sub-Quest", slug="sub"),
          Node(id="skill:attack", kind=NodeKind.SKILL, name="Attack", slug="attack"),
          Node(id="skill:cooking", kind=NodeKind.SKILL, name="Cooking", slug="cooking"),
      ]
      # goal requires: AND( skill_level attack>=40, quest sub completed )
      groups = {
          1: ConditionGroup(
              id=1, op=Op.AND, parent=None,
              children=[
                  ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:attack", threshold=40),
                  ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:sub", data={"state": "completed"}),
              ],
          ),
          # quest:sub requires: AND( skill_level cooking>=20 )
          2: ConditionGroup(
              id=2, op=Op.AND, parent=None,
              children=[
                  ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node="skill:cooking", threshold=20),
              ],
          ),
      }
      edges = [
          Edge(id=1, type=EdgeType.REQUIRES, src="quest:goal", dst=None, cond_group=1),
          Edge(id=2, type=EdgeType.REQUIRES, src="quest:sub", dst=None, cond_group=2),
      ]
      return InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)


  def _state(**kw):
      # observable skills so absent levels read as FALSE (real), not UNKNOWN
      base = dict(
          mode="main",
          levels={"skill:cooking": 20},
          observable_families={"skill_level", "skill_xp", "quest"},
      )
      base.update(kw)
      return AccountState(**base)


  def test_next_steps_returns_only_actionable_frontier():
      kg = _two_layer_kg()
      eng = Engine(kg)
      # Cooking 20 met; Attack not trained; sub not started.
      state = _state()

      res = eng.next_steps(state, "quest:goal")

      assert isinstance(res, Ok)
      card = res.card
      assert isinstance(card, PlanCard)
      assert card.goal_id == "quest:goal"
      frontier_ids = {s.node_id for s in card.steps}
      # attack (no prereqs) and sub (its only prereq, cooking, is done) are actionable;
      # cooking is already satisfied so it is NOT surfaced as a next step.
      assert frontier_ids == {"skill:attack", "quest:sub"}
      assert all(s.status == "satisfiable" for s in card.steps)

      # D8: next_steps must REUSE prereqs_for's Step instances (not rebuild them),
      # so the two reads can never drift — assert object identity, not just equality.
      plan_steps = {s.node_id: s for s in eng.prereqs_for(state, "quest:goal").card.steps}
      assert all(s is plan_steps[s.node_id] for s in card.steps)
  ```

  Run it:

  ```bash
  cd /Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool && python -m pytest tests/engine/test_engine_next_steps.py -q
  ```

  Expected: **FAIL** — `AttributeError: 'Engine' object has no attribute 'next_steps'` (the method does not exist yet).

- [ ] **Step 2 — Implement `Engine.next_steps` (minimal: frontier filter over `prereqs_for`).**

  Reuse `prereqs_for` so the two reads share Step instances and can't drift (contract §5.2). Compute the frontier by asking, for each not-yet-satisfied prereq, whether all of *its* own `requires_dag` descendants are satisfied. Add to the existing `Engine` class in `src/osrs_planner/engine/engine.py`. Ensure the imports at the top of the file include what's used below (some already present from Tasks 10–11):

  ```python
  from osrs_planner.engine.result import (
      Ok, Empty, Problem, ProblemKind, TerminalReason, Refs,
  )
  from osrs_planner.engine.cards import PlanCard, Step
  from osrs_planner.engine.conditions import evaluate
  from osrs_planner.engine.kleene import Tri
  ```

  Then add the method (place it after `prereqs_for`):

  ```python
      def next_steps(self, state, node_id):
          """The frontier subset of prereqs_for: prerequisites whose OWN prerequisites
          are all already satisfied (immediately-doable). Contract §3.1.

          - Reuses prereqs_for so the two reads share Step instances (contract §5.2).
          - A prereq is on the frontier iff it is not yet satisfied AND every node in
            its own requires-closure is satisfied for the account.
          - impossible_for_mode / cant_verify prereqs are never actionable, and any
            prereq blocked behind such a node stays off the frontier.
          - Nothing actionable -> Empty(NO_FRONTIER) (a success state, §4).
          """
          base = self.prereqs_for(state, node_id)
          # Propagate Problem (NOT_FOUND / MISSING_STATE / ...) and the
          # ALREADY_SATISFIED terminal verbatim — same preconditions as prereqs_for.
          if not isinstance(base, Ok):
              return base

          plan = base.card
          # refs live on the Ok envelope, NOT on PlanCard (see Task 9 cards.py).
          base_refs = base.refs

          # Which prereq node-ids are already satisfied?
          satisfied = {s.node_id for s in plan.steps if s.status == "satisfied"}

          frontier: list[Step] = []
          for step in plan.steps:
              if step.status == "satisfied":
                  continue
              if step.status != "satisfiable":
                  # impossible_for_mode or cant_verify is not actionable now.
                  continue
              if step.node_id is None:
                  # ref-less accumulator atom: actionable only if it has no node-prereqs,
                  # which by construction it does not (no closure to gate it).
                  frontier.append(step)
                  continue
              own_prereqs = self.kg.descendants(step.node_id)
              if all(p in satisfied for p in own_prereqs):
                  frontier.append(step)

          if not frontier:
              return Empty(refs=base_refs, reason=TerminalReason.NO_FRONTIER)

          # Reuse the parent envelope's refs/referenced_atoms (subset is still grounded;
          # every frontier node is already in base_refs). §7.4 refs ⊆ touched-this-turn.
          return Ok(
              card=PlanCard(
                  goal_id=plan.goal_id,
                  steps=frontier,
                  referenced_atoms=plan.referenced_atoms,
              ),
              refs=base_refs,
          )
  ```

  Run it:

  ```bash
  cd /Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool && python -m pytest tests/engine/test_engine_next_steps.py -q
  ```

  Expected: **PASS** (`1 passed`).

- [ ] **Step 3 — Commit.**

  ```bash
  cd /Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool && git add src/osrs_planner/engine/engine.py tests/engine/test_engine_next_steps.py && git commit -m "feat: Engine.next_steps returns the immediately-doable frontier"
  ```

- [ ] **Step 4 — Write the failing test for `Empty(NO_FRONTIER)` (blocked behind an unverifiable gate).**

  Build a goal whose only prereq is gated behind an UNKNOWN. `quest:goal` requires `quest:sub`; `quest:sub` requires a `quest` atom on `quest:gate` (state `completed`). The quest family is NOT observable and the account has not asserted any quest state, so `quest:gate` evaluates to UNKNOWN (Kleene). Therefore `quest:sub`'s own prereq is not satisfied (it's `cant_verify`), and `quest:gate` itself is `cant_verify` — nothing is actionable. Add to `tests/engine/test_engine_next_steps.py`:

  ```python
  def _gated_kg():
      """goal --req--> sub ; sub --req--> quest:gate (completed) ; gate has no prereqs."""
      nodes = [
          Node(id="quest:goal", kind=NodeKind.QUEST, name="The Goal", slug="goal"),
          Node(id="quest:sub", kind=NodeKind.QUEST, name="The Sub-Quest", slug="sub"),
          Node(id="quest:gate", kind=NodeKind.QUEST, name="The Gate Quest", slug="gate"),
      ]
      groups = {
          1: ConditionGroup(
              id=1, op=Op.AND, parent=None,
              children=[
                  ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:sub", data={"state": "completed"}),
              ],
          ),
          2: ConditionGroup(
              id=2, op=Op.AND, parent=None,
              children=[
                  ConditionAtom(atom_type=AtomType.QUEST, ref_node="quest:gate", data={"state": "completed"}),
              ],
          ),
      }
      edges = [
          Edge(id=1, type=EdgeType.REQUIRES, src="quest:goal", dst=None, cond_group=1),
          Edge(id=2, type=EdgeType.REQUIRES, src="quest:sub", dst=None, cond_group=2),
      ]
      return InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)


  def test_next_steps_empty_no_frontier_when_blocked_by_unverifiable_gate():
      kg = _gated_kg()
      eng = Engine(kg)
      # quest family NOT observable and nothing asserted -> quest:gate is UNKNOWN (cant_verify),
      # so quest:sub's prereq is unmet and nothing is immediately doable.
      state = AccountState(mode="main", levels={"skill:dummy": 1})

      res = eng.next_steps(state, "quest:goal")

      assert isinstance(res, Empty)
      assert res.reason == TerminalReason.NO_FRONTIER
      assert res.status == "ok"
      # the subject closure is still named so the Advisor can hedge (§7.4 refs leash)
      assert "quest:sub" in res.refs.nodes or "quest:gate" in res.refs.nodes
  ```

  Run it:

  ```bash
  cd /Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool && python -m pytest tests/engine/test_engine_next_steps.py::test_next_steps_empty_no_frontier_when_blocked_by_unverifiable_gate -q
  ```

  Expected: **PASS** if the gate yields `cant_verify`/`satisfiable` and the frontier filter correctly excludes the `cant_verify` `quest:gate`. If instead `quest:gate` (a leaf with no prereqs) is wrongly admitted to the frontier, this **FAILs** with `Ok` instead of `Empty` — which is the bug Step 5 hardens against. Run it and observe the result before proceeding.

  > Note for the implementer: a leaf `cant_verify` prereq has an empty closure, so the naive `all(... in satisfied)` would let it onto the frontier. The minimal impl already guards this with `if step.status != "satisfiable": continue`, so a `cant_verify` gate is correctly excluded. Confirm the test PASSES; if it FAILs, the `prereqs_for` status mapping (Task 11) is not tagging the unverifiable leaf as `cant_verify` — fix there, not here.

- [ ] **Step 5 — Write the failing test for `Empty(ALREADY_SATISFIED)` and the goal-not-found `Problem`, then confirm pass.**

  These two behaviours are inherited verbatim from `prereqs_for` (Step 2 forwards any non-`Ok`). Pin them so a future refactor can't regress the pass-through. Add:

  ```python
  def test_next_steps_already_satisfied_goal_is_empty():
      kg = _two_layer_kg()
      eng = Engine(kg)
      # everything the goal needs is met: 40 Attack, 20 Cooking, sub completed.
      state = _state(
          levels={"skill:attack": 40, "skill:cooking": 20},
          quest_state={"quest:sub": "completed"},
      )

      res = eng.next_steps(state, "quest:goal")

      assert isinstance(res, Empty)
      assert res.reason == TerminalReason.ALREADY_SATISFIED


  def test_next_steps_unknown_goal_is_problem_not_found():
      kg = _two_layer_kg()
      eng = Engine(kg)
      state = _state()

      res = eng.next_steps(state, "quest:does-not-exist")

      assert isinstance(res, Problem)
      assert res.kind == ProblemKind.NOT_FOUND
      # D7: forwarded verbatim from prereqs_for -> empty Refs, id in the message only.
      assert res.refs.nodes == {} and res.refs.mentions == {}
      assert "quest:does-not-exist" in res.message
  ```

  Run the whole file:

  ```bash
  cd /Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool && python -m pytest tests/engine/test_engine_next_steps.py -q
  ```

  Expected: **PASS** (`5 passed`) — the forwarding in Step 2 already covers both; this step proves it.

- [ ] **Step 6 — Commit.**

  ```bash
  cd /Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool && git add tests/engine/test_engine_next_steps.py && git commit -m "test: next_steps NO_FRONTIER, ALREADY_SATISFIED, NOT_FOUND cases"
  ```
```

That is the complete Task 12 markdown above. Key spec-derived decisions baked in, for the writing-plans reviewer:

- **Frontier = `prereqs_for`'s steps re-filtered** (contract §5.2: same Step instances, so the two reads can't drift), keeping `next_steps` a thin wrapper over Task 11's machinery — no duplicate closure/topo/eval logic.
- **Frontier rule:** a prereq is actionable iff it is unsatisfied AND every node in its own `requires_dag` descendants is satisfied; `impossible_for_mode` and `cant_verify` are never actionable (the `status != "satisfiable"` guard), which also keeps anything blocked *behind* an unverifiable gate off the frontier — matching §7.2 ("a no-op on the `next_steps` frontier" because frontier steps have no unmet predecessors).
- **`Empty(NO_FRONTIER)`** for "nothing doable" (a success state per §4), with the subject closure still in `refs` so the Advisor can hedge (§7.4 grounding leash).
- **Pass-through** of `Empty(ALREADY_SATISFIED)` and `Problem(NOT_FOUND)`/`Problem(MISSING_STATE)` from `prereqs_for` verbatim (returns any non-`Ok` unchanged).

One cross-task dependency the reviewer should verify against the Task 11 draft: `next_steps` relies on `prereqs_for` tagging each Step with `status ∈ {satisfied, satisfiable, impossible_for_mode, cant_verify}` and on `KGStore.descendants(node_id)` returning a node's own `requires`-closure. Both are in the type-spine (cards.Step.status; store.descendants), so no new surface is introduced.

Relevant file paths: `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/src/osrs_planner/engine/engine.py` and `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/tests/engine/test_engine_next_steps.py`.

---

### Task 13: End-to-end integration test + a demo runner

Capstone task. Wires every brick together: build the hand-authored Scurrius KG fixture (the `(70 Attack AND 70 Strength) OR full-Void` worked example from `kg-schema-v1.md`), put an ironman through it, and assert that `is_unlocked` / `prereqs_for` / `next_steps` tell **one coherent story**. Then a tiny `python -m osrs_planner.engine` demo prints that plan so a human can eyeball it. This task writes no production logic beyond `__main__.py` — it consumes the spine built in Tasks 1-12 (`result`, `kleene`, `kg.model`, `kg.store`, `state`, `conditions`, `cards`, `engine`).

The fixture story (deliberately exercises every code path):
- `npc:7221` (Scurrius) has **one** `requires` edge with `dst=None`, `cond_group=1`.
- Group 1 = `OR` of group 2 and group 3.
- Group 2 = `AND` of `skill_level(attack, 70)` and `skill_level(strength, 70)`.
- Group 3 = a single `gear_loadout(gear_loadout:void)` atom.
- `gear_loadout:void`'s composition (group 10) = `AND` of an `OR`-of-3-helms (group 11) plus top/robe/gloves `item` atoms.
- The ironman has 75 Attack, 60 Strength, no Void pieces → `OR(AND(T,F)=F, void=F) = FALSE` → **locked**, blocker = "train Strength to 70".
- Skills (`skill_level`/`skill_xp` family) are **observable** (per §6.4 levels are always visible), so absent strength is a real FALSE, not UNKNOWN. Items are **not** observable for this account → absent Void pieces are UNKNOWN, but the OR still resolves FALSE overall because the stat branch is a concrete FALSE and the void branch's UNKNOWN doesn't flip an already-decided OR (it stays FALSE since no branch is TRUE and the void branch folds to UNKNOWN → `k_or([FALSE, UNKNOWN]) = UNKNOWN`)... so we make the item family observable too in this fixture (RuneLite bank present) to get a clean deterministic `locked`. This keeps the integration story unambiguous; the UNKNOWN path is covered in the dedicated conditions/engine unit tasks.

**Files:**
- `tests/engine/test_integration.py` (new) — end-to-end pytest building the fixture + asserting the coherent story.
- `src/osrs_planner/engine/__main__.py` (new) — `python -m osrs_planner.engine` demo that prints the Scurrius plan for the fixture ironman.

**Steps:**

- [ ] **Step 1 — Write the failing integration test (real code, full fixture).**

  Create `tests/engine/test_integration.py`:

  ```python
  """End-to-end: the (70 Att AND 70 Str) OR full-Void Scurrius goal on an ironman.

  Builds the hand-authored KG fixture from kg-schema-v1.md's worked example and asserts
  is_unlocked / prereqs_for / next_steps tell ONE coherent story.
  """
  import pytest

  from osrs_planner.engine.kg.model import (
      Node, NodeKind, Edge, EdgeType, ConditionGroup, ConditionAtom, Op, AtomType,
  )
  from osrs_planner.engine.kg.store import InMemoryKGStore
  from osrs_planner.engine.state import AccountState
  from osrs_planner.engine.engine import Engine
  from osrs_planner.engine.result import Ok, Empty, Problem, ProblemKind, TerminalReason


  # ---- Node ids (kg-schema-v1.md worked example) ----
  SCURRIUS = "npc:7221"
  ATTACK = "skill:attack"
  STRENGTH = "skill:strength"
  VOID = "gear_loadout:void"
  HELM_MAGE = "item:11663"
  HELM_RANGE = "item:11664"
  HELM_MELEE = "item:11665"
  VOID_TOP = "item:8839"
  VOID_ROBE = "item:8840"
  VOID_GLOVES = "item:8842"


  @pytest.fixture
  def kg():
      """Scurrius requires (70 Att AND 70 Str) OR full-Void; Void composition = AND-of-slots."""
      nodes = [
          Node(id=SCURRIUS, kind=NodeKind.MONSTER, name="Scurrius", slug="scurrius"),
          Node(id=ATTACK, kind=NodeKind.SKILL, name="Attack", slug="attack"),
          Node(id=STRENGTH, kind=NodeKind.SKILL, name="Strength", slug="strength"),
          Node(id=VOID, kind=NodeKind.GEAR_LOADOUT, name="Full Void", slug="void"),
          Node(id=HELM_MAGE, kind=NodeKind.ITEM, name="Void mage helm", slug="void-mage-helm"),
          Node(id=HELM_RANGE, kind=NodeKind.ITEM, name="Void ranger helm", slug="void-ranger-helm"),
          Node(id=HELM_MELEE, kind=NodeKind.ITEM, name="Void melee helm", slug="void-melee-helm"),
          Node(id=VOID_TOP, kind=NodeKind.ITEM, name="Void knight top", slug="void-knight-top"),
          Node(id=VOID_ROBE, kind=NodeKind.ITEM, name="Void knight robe", slug="void-knight-robe"),
          Node(id=VOID_GLOVES, kind=NodeKind.ITEM, name="Void knight gloves", slug="void-knight-gloves"),
      ]
      groups = {
          # Scurrius requires-tree: OR( AND(att,str), void )
          1: ConditionGroup(id=1, op=Op.OR, parent=None, children=[2, 3]),
          2: ConditionGroup(id=2, op=Op.AND, parent=1, children=[
              ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=ATTACK, threshold=70),
              ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=STRENGTH, threshold=70),
          ]),
          3: ConditionGroup(id=3, op=Op.AND, parent=1, children=[
              ConditionAtom(atom_type=AtomType.GEAR_LOADOUT, ref_node=VOID),
          ]),
          # Void composition: AND( OR(3 helms), top, robe, gloves )
          10: ConditionGroup(id=10, op=Op.AND, parent=None, children=[
              11,
              ConditionAtom(atom_type=AtomType.ITEM, ref_node=VOID_TOP, qty=1),
              ConditionAtom(atom_type=AtomType.ITEM, ref_node=VOID_ROBE, qty=1),
              ConditionAtom(atom_type=AtomType.ITEM, ref_node=VOID_GLOVES, qty=1),
          ]),
          11: ConditionGroup(id=11, op=Op.OR, parent=10, children=[
              ConditionAtom(atom_type=AtomType.ITEM, ref_node=HELM_MAGE, qty=1),
              ConditionAtom(atom_type=AtomType.ITEM, ref_node=HELM_RANGE, qty=1),
              ConditionAtom(atom_type=AtomType.ITEM, ref_node=HELM_MELEE, qty=1),
          ]),
      }
      edges = [
          # Scurrius's requires edge: the constraint IS the tree (dst=None, cond_group=1)
          Edge(id=1, type=EdgeType.REQUIRES, src=SCURRIUS, dst=None, cond_group=1),
          # Void loadout composition: dst=None requires edge carrying the AND-of-slots tree (cond_group=10)
          Edge(id=2, type=EdgeType.REQUIRES, src=VOID, dst=None, cond_group=10),
      ]
      return InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)


  @pytest.fixture
  def ironman():
      """75 Att / 60 Str, no Void. Bank plugin present so item absence reads as a real FALSE."""
      return AccountState(
          mode="ironman",
          levels={ATTACK: 75, STRENGTH: 60},
          observable_families={"skill_level", "skill_xp", "item", "gear_loadout"},
      )


  def test_scurrius_is_locked_with_strength_blocker(kg, ironman):
      """Ironman is 10 levels short of the 70 Str branch and owns no Void: locked, not indeterminate."""
      engine = Engine(kg)
      res = engine.is_unlocked(ironman, SCURRIUS)

      assert isinstance(res, Ok)
      card = res.card
      assert card.node_id == SCURRIUS
      assert card.status == "locked"
      # the subject node is grounded in refs
      assert SCURRIUS in res.refs.nodes
      # the failing strength leaf is surfaced as a blocker, none are cant_verify
      blocker_reasons = {b.reason for b in card.blockers}
      assert "skill_level" in blocker_reasons
      assert all(b.status != "cant_verify" for b in card.blockers)
      strength_blocker = [b for b in card.blockers if b.node_id == STRENGTH]
      assert strength_blocker, "expected a Strength blocker step"
      assert strength_blocker[0].status == "satisfiable"


  def test_scurrius_prereqs_are_ordered_and_account_typed(kg, ironman):
      """prereqs_for yields a Step per prereq with done/satisfiable status, ordered."""
      engine = Engine(kg)
      res = engine.prereqs_for(ironman, SCURRIUS)

      assert isinstance(res, Ok)
      steps = res.card.steps
      assert res.card.goal_id == SCURRIUS
      assert steps, "expected at least the stat prereqs"
      by_node = {s.node_id: s for s in steps}
      # Attack 70 is met (75) -> satisfied; Strength 70 is not (60) -> satisfiable
      assert ATTACK in by_node and by_node[ATTACK].status == "satisfied"
      assert STRENGTH in by_node and by_node[STRENGTH].status == "satisfiable"
      # every step's node is grounded
      for s in steps:
          if s.node_id is not None:
              assert s.node_id in res.refs.nodes


  def test_scurrius_next_steps_is_the_doable_frontier(kg, ironman):
      """next_steps = the prereqs whose own prereqs are all satisfied (immediately doable)."""
      engine = Engine(kg)
      res = engine.next_steps(ironman, SCURRIUS)

      assert isinstance(res, Ok)
      frontier = {s.node_id for s in res.card.steps if s.status != "satisfied"}
      # Strength (a bare skill leaf, no sub-prereqs) is doable right now
      assert STRENGTH in frontier


  def test_already_satisfied_goal_is_empty(kg):
      """An ironman with 70/70 already meets the OR's stat branch -> Empty(ALREADY_SATISFIED)."""
      done_iron = AccountState(
          mode="ironman",
          levels={ATTACK: 99, STRENGTH: 99},
          observable_families={"skill_level", "skill_xp", "item", "gear_loadout"},
      )
      engine = Engine(kg)

      unlocked = engine.is_unlocked(done_iron, SCURRIUS)
      assert isinstance(unlocked, Ok) and unlocked.card.status == "unlocked"

      prereqs = engine.prereqs_for(done_iron, SCURRIUS)
      assert isinstance(prereqs, Empty)
      assert prereqs.reason == TerminalReason.ALREADY_SATISFIED


  def test_missing_node_is_a_problem(kg, ironman):
      engine = Engine(kg)
      res = engine.is_unlocked(ironman, "npc:does-not-exist")
      assert isinstance(res, Problem)
      assert res.kind == ProblemKind.NOT_FOUND


  def test_coherent_story_across_three_reads(kg, ironman):
      """The three reads must agree: locked <=> has prereqs <=> Strength on the frontier."""
      engine = Engine(kg)
      unlocked = engine.is_unlocked(ironman, SCURRIUS)
      prereqs = engine.prereqs_for(ironman, SCURRIUS)
      nxt = engine.next_steps(ironman, SCURRIUS)

      assert isinstance(unlocked, Ok) and unlocked.card.status == "locked"
      assert isinstance(prereqs, Ok) and isinstance(nxt, Ok)

      # the locked blocker, the unsatisfied prereq, and the frontier all point at Strength
      locked_nodes = {b.node_id for b in unlocked.card.blockers}
      unmet_prereqs = {s.node_id for s in prereqs.card.steps if s.status == "satisfiable"}
      frontier = {s.node_id for s in nxt.card.steps if s.status != "satisfied"}
      assert STRENGTH in locked_nodes
      assert STRENGTH in unmet_prereqs
      assert STRENGTH in frontier

      # next_steps is a subset of prereqs_for (the same Step universe, filtered)
      assert frontier <= unmet_prereqs
  ```

  Run it (expect FAIL — `__main__.py` not yet present is fine, but the test itself should COLLECT and run against the Tasks 1-12 engine):

  ```
  venv/bin/python -m pytest tests/engine/test_integration.py -q
  ```

  Expected output (the file collects, the assertions exercise the wired engine):
  ```
  6 passed in 0.XXs
  ```

  > If any assertion fails here, it is a real integration mismatch between bricks — debug the engine wiring (systematic-debugging), do NOT weaken the test to make it pass.

- [ ] **Step 2 — Write the demo runner `__main__.py` (real code, no placeholders).**

  Create `src/osrs_planner/engine/__main__.py`:

  ```python
  """`python -m osrs_planner.engine` — prints the Scurrius plan for a fixture ironman.

  A human-eyeball demo over the (70 Att AND 70 Str) OR full-Void worked example, so the
  end-to-end story can be seen without reading pytest output. Not used by the web/advisor.
  """
  from osrs_planner.engine.kg.model import (
      Node, NodeKind, Edge, EdgeType, ConditionGroup, ConditionAtom, Op, AtomType,
  )
  from osrs_planner.engine.kg.store import InMemoryKGStore
  from osrs_planner.engine.state import AccountState
  from osrs_planner.engine.engine import Engine
  from osrs_planner.engine.result import Ok, Empty, Problem

  SCURRIUS = "npc:7221"
  ATTACK = "skill:attack"
  STRENGTH = "skill:strength"
  VOID = "gear_loadout:void"
  HELM_MELEE = "item:11665"
  VOID_TOP = "item:8839"
  VOID_ROBE = "item:8840"
  VOID_GLOVES = "item:8842"


  def build_fixture() -> InMemoryKGStore:
      nodes = [
          Node(id=SCURRIUS, kind=NodeKind.MONSTER, name="Scurrius", slug="scurrius"),
          Node(id=ATTACK, kind=NodeKind.SKILL, name="Attack", slug="attack"),
          Node(id=STRENGTH, kind=NodeKind.SKILL, name="Strength", slug="strength"),
          Node(id=VOID, kind=NodeKind.GEAR_LOADOUT, name="Full Void", slug="void"),
          Node(id=HELM_MELEE, kind=NodeKind.ITEM, name="Void melee helm", slug="void-melee-helm"),
          Node(id=VOID_TOP, kind=NodeKind.ITEM, name="Void knight top", slug="void-knight-top"),
          Node(id=VOID_ROBE, kind=NodeKind.ITEM, name="Void knight robe", slug="void-knight-robe"),
          Node(id=VOID_GLOVES, kind=NodeKind.ITEM, name="Void knight gloves", slug="void-knight-gloves"),
      ]
      groups = {
          1: ConditionGroup(id=1, op=Op.OR, parent=None, children=[2, 3]),
          2: ConditionGroup(id=2, op=Op.AND, parent=1, children=[
              ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=ATTACK, threshold=70),
              ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=STRENGTH, threshold=70),
          ]),
          3: ConditionGroup(id=3, op=Op.AND, parent=1, children=[
              ConditionAtom(atom_type=AtomType.GEAR_LOADOUT, ref_node=VOID),
          ]),
          10: ConditionGroup(id=10, op=Op.AND, parent=None, children=[
              ConditionAtom(atom_type=AtomType.ITEM, ref_node=HELM_MELEE, qty=1),
              ConditionAtom(atom_type=AtomType.ITEM, ref_node=VOID_TOP, qty=1),
              ConditionAtom(atom_type=AtomType.ITEM, ref_node=VOID_ROBE, qty=1),
              ConditionAtom(atom_type=AtomType.ITEM, ref_node=VOID_GLOVES, qty=1),
          ]),
      }
      edges = [
          Edge(id=1, type=EdgeType.REQUIRES, src=SCURRIUS, dst=None, cond_group=1),
          Edge(id=2, type=EdgeType.REQUIRES, src=VOID, dst=None, cond_group=10),
      ]
      return InMemoryKGStore(nodes=nodes, edges=edges, groups=groups)


  def _print_unlock(engine: Engine, state: AccountState) -> None:
      res = engine.is_unlocked(state, SCURRIUS)
      if isinstance(res, Ok):
          print(f"is_unlocked: {res.card.status}")
          for b in res.card.blockers:
              print(f"  blocker: {b.name} [{b.reason}] ({b.status})")
      elif isinstance(res, Empty):
          print(f"is_unlocked: empty ({res.reason.value})")
      else:
          print(f"is_unlocked: problem ({res.kind.value}) {res.message}")


  def _print_plan(engine: Engine, state: AccountState) -> None:
      res = engine.prereqs_for(state, SCURRIUS)
      if isinstance(res, Ok):
          print("prereqs_for (ordered):")
          for s in res.card.steps:
              print(f"  - {s.name}: {s.status} ({s.reason})")
      elif isinstance(res, Empty):
          print(f"prereqs_for: empty ({res.reason.value})")
      else:
          print(f"prereqs_for: problem ({res.kind.value}) {res.message}")


  def _print_next(engine: Engine, state: AccountState) -> None:
      res = engine.next_steps(state, SCURRIUS)
      if isinstance(res, Ok):
          print("next_steps (frontier):")
          for s in res.card.steps:
              print(f"  - {s.name}: {s.status} ({s.reason})")
      elif isinstance(res, Empty):
          print(f"next_steps: empty ({res.reason.value})")
      else:
          print(f"next_steps: problem ({res.kind.value}) {res.message}")


  def main() -> None:
      kg = build_fixture()
      engine = Engine(kg)
      iron = AccountState(
          mode="ironman",
          levels={ATTACK: 75, STRENGTH: 60},
          observable_families={"skill_level", "skill_xp", "item", "gear_loadout"},
      )
      print("=== Gilded Tome engine demo: Scurrius on an ironman (75 Att / 60 Str, no Void) ===")
      _print_unlock(engine, iron)
      _print_plan(engine, iron)
      _print_next(engine, iron)


  if __name__ == "__main__":
      main()
  ```

  Run the demo (expect a coherent printed plan):

  ```
  venv/bin/python -m osrs_planner.engine
  ```

  Expected output (exact text; statuses are load-bearing — `locked`, the Strength blocker, Strength on the frontier):
  ```
  === Gilded Tome engine demo: Scurrius on an ironman (75 Att / 60 Str, no Void) ===
  is_unlocked: locked
    blocker: Strength [skill_level] (satisfiable)
  prereqs_for (ordered):
    - Attack: satisfied (satisfied)
    - Strength: satisfiable (skill_level)
  next_steps (frontier):
    - Strength: satisfiable (skill_level)
  ```

  > The engine projects the full requires-closure, so `prereqs_for` ALSO emits steps for the Void branch leaves (`gear_loadout:void` and its four item leaves) as additional `satisfiable` lines after the two stat lines shown above; that is correct and deterministic. The load-bearing, stable invariants the demo must show are concrete: (1) `is_unlocked: locked`, (2) a `Strength [skill_level] (satisfiable)` blocker line, (3) a `Strength: satisfiable (skill_level)` line under both `prereqs_for` and `next_steps`. The two stat prereqs `Attack` (satisfied) and `Strength` (satisfiable) always appear; do NOT change the engine to suppress the Void-branch lines.

- [ ] **Step 3 — Run the full engine suite to prove nothing regressed.**

  ```
  venv/bin/python -m pytest tests/engine/ -q
  ```

  Expected output (Task 13's 6 tests plus everything from Tasks 1-12, all green):
  ```
  ...
  XX passed in 0.XXs
  ```

  > If the integration test passes but a unit test from an earlier task fails, the wiring assumption in this test surfaced a real contract drift — fix the offending brick, not this test.

- [ ] **Step 4 — Commit.**

  ```
  git add tests/engine/test_integration.py src/osrs_planner/engine/__main__.py
  git commit -m "test: end-to-end Scurrius integration + engine demo runner"
  ```

  Expected: a commit is created on the current branch containing exactly the two new files; `git status` shows a clean working tree for the engine package.

---

Notes for the assembling plan author (paths are absolute):
- New test file: `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/tests/engine/test_integration.py`
- New demo runner: `/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/src/osrs_planner/engine/__main__.py`
- The fixture is built **inline** in both files (no dependency on an earlier task's fixture-helper name) so Task 13 is self-contained; it is the canonical `(70 Att AND 70 Str) OR full-Void` worked example from `research/kg-schema-v1.md` against `npc:7221` (Scurrius).
- This task assumes Tasks 1-12 delivered the spine modules `osrs_planner.engine.{result,kleene,kg.model,kg.store,state,conditions,cards,engine}` with the exact signatures from the type-spine; it consumes `Engine.is_unlocked/prereqs_for/next_steps`, the `Ok/Empty/Problem` envelope, `TerminalReason.ALREADY_SATISFIED`, and `ProblemKind.NOT_FOUND`.
- The fixture sets `observable_families={"skill_level","skill_xp","item","gear_loadout"}` deliberately so the Scurrius story resolves to a deterministic `locked` (no UNKNOWN). The Kleene-UNKNOWN/`cant_verify`/`indeterminate` path is owned by the dedicated `conditions`/`engine` unit tasks (per contract §12's three-valued-eval test), not this integration capstone.
- Test runner is the repo venv: `venv/bin/python -m pytest`. `networkx` is a new dependency introduced by an earlier task (the `requires_dag` brick); if `tests/engine/` aborts at collection with `ModuleNotFoundError: networkx`, that dependency step was skipped upstream — `venv/bin/pip install networkx` and ensure it landed in the project's dependency manifest.
