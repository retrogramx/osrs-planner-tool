# Achievement Diaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Model the Achievement Diaries domain on the KG — 48 tier nodes (requirements from the 492 tasks), full per-tier rewards (upgrade-ladder items via `supersedes`, scaling XP lamps, tiered effects, extra unlocks), a **queryable content-node layer** (`effect → content`), and `goal:achievement-diary-cape` (+ trimmed cross-cape) — reusing the quest-foundation taxonomy.

**Architecture:** A new `kg_ingest/builders/diaries.py` turns committed data (`data/achievement_diaries.json` tasks + new `data/diary_rewards.json` overlay + new `data/diary_content_nodes.json`) into diary tier nodes, `requires`/`grants`/`effect`/`supersedes`/`progress_towards` edges, content nodes, and the cape goal — assembled by the existing byte-stable pipeline. Minimal engine additions: `EdgeType.SUPERSEDES`, `AtomType.COUNT_SATISFIED` (+ its evaluator). Two committed gates: `data/validate_diary_rewards.py` (structure) and `data/verify_diary_rewards.py` (source-grounding, the diary analog of `verify_quest_rewards.py`).

**Tech Stack:** Python 3 (stdlib only — `urllib`, `json`, `re`, `dataclasses`, `enum`); `networkx`; `pytest`. No new dependencies.

## Global Constraints

- **Depends on the quest-foundation brick (PR #15)** — this branch (`feat/achievement-diaries`) is stacked on `feat/quest-foundation`; `Edge.data`, `EdgeType.EFFECT`/`PROGRESS_TOWARDS`, `NodeKind.GOAL`, the per-owner-cumulative `rekey`, the `quest_rewards`/`completion_goals` builders, and `validate_quest_rewards.py`/`verify_quest_rewards.py` already exist and are the patterns this plan mirrors. Begin only after PR #15 merges (or while stacked on it).
- **Source-grounded, never fabricated.** Every reward/effect/lamp datum is transcribed from the *current* wiki diary pages with provenance; the `reward` prose strings in `data/achievement_diaries.json` are a *starting point, not truth*. Editorial values are gated by `verify_diary_rewards.py` + owner review. A datum that can't be sourced is left out and disclosed. TDD pins *machinery* with synthetic fixtures; real values live in committed data, owner-gated.
- **Full 48-tier capture** (diaries are bounded), not a seed — but verifier-gated.
- **Deterministic, byte-stable build.** `python -m kg_ingest.assemble` is byte-identical on re-run (sorted, `json.dumps(..., indent=2, sort_keys=True, ensure_ascii=False)` + trailing newline). Builders mint builder-local ids in disjoint bands; `rekey` derives global ids from the owning node. New bands: **diaries `0x90000000`/`0x98000000`**, **content `0xA0000000`/`0xA8000000`** (disjoint from quests `0x10/0x20`, goals `0x30/0x40`, quest_rewards `0x50/0x60`, completion_goals `0x70/0x78`).
- **Node id prefixes** (mint via `kg_ingest/ids.py`): `diary:<region-slug>:<tier>`, `activity:<slug>`, `region:<slug>`, `monster:<slug>`, `goal:<slug>`; existing `item:<id>`, `skill:<slug>`. Region slugs use `supporting.DIARY_REGION_LABELS` (e.g. `kourend`→"Kourend & Kebos", `western`→"Western Provinces", `lumbridge`→"Lumbridge & Draynor").
- **The diary cape is ONE base node** (`goal:achievement-diary-cape`) + one trimmed node (`goal:achievement-diary-cape-t`). Mirrors "Quest cape = QP cape, one node."
- **Validators** follow the committed idiom (`check_*(...) -> list[str]` + `main() -> int` printing `... PASSED/FAILED`, exit 0/1); tests import scripts via `importlib.util`.
- **Tests:** `./venv/bin/python -m pytest` from the venv. Run the full suite with `--continue-on-collection-errors` (4 PRE-EXISTING `tests/drop_rates/` collection errors — `ModuleNotFoundError: data._toa_drop_rates` — predate this work; do NOT touch drop_rates).
- **Engine inertness:** `supersedes`, `effect`, `progress_towards` are inert to the prereq DAG (only `requires` gates; `grants` flips for cycle detection). Do not wire the new edges into gating.

---

## File Structure

**Schema (Task 1):**
- Modify `src/osrs_planner/engine/kg/model.py` — `EdgeType.SUPERSEDES`, `AtomType.COUNT_SATISFIED`.
- Modify `src/osrs_planner/engine/conditions.py` — `COUNT_SATISFIED` evaluator.
- Modify `kg_ingest/ids.py` — `diary_tier_id`, `activity_id`, `region_id`, `monster_id`, `goal_id`.
- Test `tests/engine/test_count_satisfied.py`, extend `tests/engine/test_reward_edge_types.py`.

**Structure (Tasks 2–3):**
- Create `kg_ingest/builders/diaries.py` — `build_diaries(...)` (grows across Tasks 2/5/7).
- Modify `kg_ingest/assemble.py` — wire the diary builder.
- Create `data/diary_content_nodes.json` (Task 6), `data/diary_rewards.json` (Task 4), `data/diary_goals.json` (Task 3).
- Tests `tests/kg_ingest/test_build_diaries.py`.

**Rewards + effects (Tasks 4–7):**
- Create `data/validate_diary_rewards.py`, tests.

**Verifier + integration (Tasks 8–9):**
- Create `data/verify_diary_rewards.py`, `data/raw/diary_reward_blocks.json`, tests.
- Modify `data/validate_kg.py`, `data/QUEST_REWARDS.md` (rename mention / add a diary doc `data/DIARY_REWARDS.md`).

---

## Task 1: Schema — `supersedes` edge, `count_satisfied` atom, id helpers

**Files:**
- Modify: `src/osrs_planner/engine/kg/model.py`
- Modify: `src/osrs_planner/engine/conditions.py`
- Modify: `kg_ingest/ids.py`
- Test: `tests/engine/test_count_satisfied.py`; extend `tests/engine/test_reward_edge_types.py`

**Interfaces:**
- Produces: `EdgeType.SUPERSEDES = "supersedes"`; `AtomType.COUNT_SATISFIED = "count_satisfied"`. `ids.diary_tier_id(region_slug: str, tier: str) -> str` → `f"diary:{region_slug}:{tier}"`; `ids.activity_id(name) -> "activity:<slug>"`; `ids.region_id(name) -> "region:<slug>"`; `ids.monster_id(name) -> "monster:<slug>"`; `ids.goal_id(slug) -> "goal:<slug>"`. `count_satisfied` evaluates: of `atom.data["set_ref"]` diary-tier ids, the count whose `state.diary_state[id] == "completed"` ≥ `atom.threshold`, Kleene-aware via `family_is_observed("achievement_diary", ...)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/engine/test_count_satisfied.py`:

```python
"""count_satisfied atom — Kleene cardinality over diary-tier completion (diaries Task 1)."""
from osrs_planner.engine.kg.model import AtomType, ConditionAtom
from osrs_planner.engine.conditions import atom_satisfied
from osrs_planner.engine.kleene import Tri
from osrs_planner.engine.state import AccountState


def _atom(set_ref, threshold):
    return ConditionAtom(atom_type=AtomType.COUNT_SATISFIED, threshold=threshold,
                         data={"set_ref": set_ref})


def test_enough_completed_is_true():
    st = AccountState(mode="main", observable_families={"achievement_diary"},
                      diary_state={"diary:ardougne:easy": "completed",
                                   "diary:desert:easy": "completed"})
    assert atom_satisfied(_atom(["diary:ardougne:easy", "diary:desert:easy"], 2), st, None) is Tri.TRUE


def test_observed_absence_short_of_threshold_is_false():
    st = AccountState(mode="main", observable_families={"achievement_diary"},
                      diary_state={"diary:ardougne:easy": "completed"})
    # 1 completed, 1 observed-not-done, threshold 2 -> can't reach -> FALSE
    assert atom_satisfied(_atom(["diary:ardougne:easy", "diary:desert:easy"], 2), st, None) is Tri.FALSE


def test_unobserved_members_are_unknown():
    st = AccountState(mode="main", observable_families=set(),  # diary not observed
                      diary_state={"diary:ardougne:easy": "completed"})
    # 1 known-true, 1 unknown, threshold 2 -> might reach -> UNKNOWN
    assert atom_satisfied(_atom(["diary:ardougne:easy", "diary:desert:easy"], 2), st, None) is Tri.UNKNOWN
```

Extend `tests/engine/test_reward_edge_types.py` with:

```python
def test_supersedes_enum_exists_and_is_inert():
    from osrs_planner.engine.kg.model import EdgeType, Edge, Node, NodeKind
    from osrs_planner.engine.kg.store import InMemoryKGStore
    assert EdgeType.SUPERSEDES.value == "supersedes"
    nodes = [Node(id="item:1", kind=NodeKind.ITEM, name="A", slug="1"),
             Node(id="item:2", kind=NodeKind.ITEM, name="B", slug="2")]
    edges = [Edge(id=1, type=EdgeType.SUPERSEDES, src="item:2", dst="item:1", cond_group=None, data={})]
    assert InMemoryKGStore(nodes, edges, {}).find_cycles() == []
```

- [ ] **Step 2: Run to verify failure**

Run: `./venv/bin/python -m pytest tests/engine/test_count_satisfied.py -v`
Expected: FAIL — `AttributeError: COUNT_SATISFIED`.

- [ ] **Step 3: Add the enums**

In `model.py`, add to `EdgeType` (after `PROGRESS_TOWARDS`): `SUPERSEDES = "supersedes"  # item upgrade ladder (cloak 1≺2≺3≺4); inert to gating`.
Add to `AtomType` (after `COMBAT_ACHIEVEMENT_POINTS`): `COUNT_SATISFIED = "count_satisfied"  # cardinality of completed members of data.set_ref (goal:*-cape)`.

- [ ] **Step 4: Add the `count_satisfied` evaluator**

In `conditions.py`, inside `atom_satisfied`, before the final `raise NotImplementedError`, add (mirroring the `CLUE_SCROLLS` Kleene-cardinality branch):

```python
    if at is AtomType.COUNT_SATISFIED:
        # Count members of data.set_ref whose diary tier is completed (the cape goal).
        # Same Kleene cardinality shape as clue_scrolls: known-true vs observed-false vs unknown.
        members = atom.data.get("set_ref", [])
        threshold = atom.threshold or 0
        fam = atom.data.get("member_family", "achievement_diary")
        per_member: list[Tri] = []
        for m in members:
            have = state.diary_state.get(m)
            if have is not None and QUEST_STATE_ORDER.get(have, 0) >= QUEST_STATE_ORDER["completed"]:
                per_member.append(Tri.TRUE)
            elif family_is_observed(fam, state, manually_asserted=False):
                per_member.append(Tri.FALSE)
            else:
                per_member.append(Tri.UNKNOWN)
        n_true = sum(1 for t in per_member if t is Tri.TRUE)
        n_unknown = sum(1 for t in per_member if t is Tri.UNKNOWN)
        if n_true >= threshold:
            return Tri.TRUE
        if n_true + n_unknown < threshold:
            return Tri.FALSE
        return Tri.UNKNOWN
```

`QUEST_STATE_ORDER` is already imported in `conditions.py` (from `osrs_planner.engine.state`). *(Generalization to clue tiers reads a different state dict — deferred to the Clues brick; this brick's `count_satisfied` is diary-tier-focused.)*

- [ ] **Step 5: Add the id helpers**

In `kg_ingest/ids.py`, add:

```python
def diary_tier_id(region_slug: str, tier: str) -> str:
    return f"diary:{region_slug}:{tier}"


def activity_id(name: str) -> str:
    return f"activity:{slugify(name)}"


def region_id(name: str) -> str:
    return f"region:{slugify(name)}"


def monster_id(name: str) -> str:
    return f"monster:{slugify(name)}"


def goal_id(slug: str) -> str:
    return f"goal:{slugify(slug)}"
```

- [ ] **Step 6: Run tests, re-assemble, full suite**

Run: `./venv/bin/python -m pytest tests/engine/test_count_satisfied.py tests/engine/test_reward_edge_types.py -v` → all pass.
Run: `./venv/bin/python -m kg_ingest.assemble && git diff --quiet kg/ && echo BYTE-STABLE` → BYTE-STABLE (no builder change yet).
Run: `./venv/bin/python -m pytest -q --continue-on-collection-errors` → all pass except the 4 pre-existing drop_rates errors.

- [ ] **Step 7: Commit**

```bash
git add src/osrs_planner/engine/kg/model.py src/osrs_planner/engine/conditions.py kg_ingest/ids.py tests/engine/
git commit -m "diaries: schema — supersedes edge + count_satisfied atom + id helpers"
```

---

## Task 2: Diary tier nodes + requirement gates

**Files:**
- Create: `kg_ingest/builders/diaries.py`
- Modify: `kg_ingest/assemble.py`
- Test: `tests/kg_ingest/test_build_diaries.py`

**Interfaces:**
- Consumes: `data/achievement_diaries.json` records (`{diary_region, tier, task_number, task, requirements{skills:[{skill,level}], quests:[str], items:[str]}, boostable, reward, source_url}`); `ids.diary_tier_id`, `quest_id`, `skill_id`; `supporting.DIARY_REGION_LABELS`.
- Produces: `build_diaries(task_records, reward_records=None, content_records=None) -> tuple[list[Node], list[Edge], dict[int, ConditionGroup]]`. Task 2 uses only `task_records`, emitting 48 `diary:` tier nodes (`NodeKind.DIARY`, `data={region, tier, tasks:[...]}`) + one `requires` edge per tier (AND of the tier's aggregate skill gates [max level per skill across the tier's tasks; `boostable` honored per the strictest task] + the union of quest prereqs as `quest` atoms `state=completed`). Builder-local id bands `0x90000000`/`0x98000000`.

- [ ] **Step 1: Write the failing test**

Create `tests/kg_ingest/test_build_diaries.py`:

```python
"""kg_ingest/builders/diaries.py — diary tier nodes + requirement gates (diaries Task 2+)."""
from kg_ingest.builders.diaries import build_diaries
from osrs_planner.engine.kg.model import AtomType, ConditionAtom, EdgeType, NodeKind


def _tasks():
    return [
        {"diary_region": "Ardougne", "tier": "easy", "task_number": 1, "task": "T1",
         "requirements": {"skills": [{"skill": "Thieving", "level": 5}], "quests": [], "items": []},
         "boostable": False, "reward": "Ardougne cloak 1:", "source_url": "u"},
        {"diary_region": "Ardougne", "tier": "easy", "task_number": 2, "task": "T2",
         "requirements": {"skills": [{"skill": "Thieving", "level": 25}], "quests": ["Biohazard"], "items": []},
         "boostable": False, "reward": "Ardougne cloak 1:", "source_url": "u"},
    ]


def test_one_tier_node_per_region_tier():
    nodes, edges, groups = build_diaries(_tasks())
    diary_nodes = [n for n in nodes if n.kind is NodeKind.DIARY]
    assert [n.id for n in diary_nodes] == ["diary:ardougne:easy"]
    n = diary_nodes[0]
    assert n.data["region"] == "ardougne" and n.data["tier"] == "easy"
    assert len(n.data["tasks"]) == 2  # per-task list retained for route detail


def test_tier_requires_edge_aggregates_max_skill_and_union_quests():
    nodes, edges, groups = build_diaries(_tasks())
    req = [e for e in edges if e.type is EdgeType.REQUIRES and e.src == "diary:ardougne:easy"][0]
    atoms = [c for c in groups[req.cond_group].children if isinstance(c, ConditionAtom)]
    skill = [a for a in atoms if a.atom_type is AtomType.SKILL_LEVEL]
    quest = [a for a in atoms if a.atom_type is AtomType.QUEST]
    assert len(skill) == 1 and skill[0].ref_node == "skill:thieving" and skill[0].threshold == 25  # MAX level
    assert len(quest) == 1 and quest[0].ref_node == "quest:biohazard"
```

- [ ] **Step 2: Run to verify failure**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_build_diaries.py -v` → FAIL (module missing).

- [ ] **Step 3: Implement the structural builder**

Create `kg_ingest/builders/diaries.py`:

```python
"""Achievement-diary builder (diaries spec §2,§3,§4,§6). Grows across Tasks 2/5/7.

Task 2: 48 diary:<region>:<tier> tier nodes + a requires edge per tier (the tier's
aggregate gate: max skill level per skill across the tier's tasks + union of quest
prereqs). The 492 per-task details are retained in node.data["tasks"] for route detail;
the engine gates tier completion via the existing achievement_diary atom, not per-task.

IDs (K9): builder-local bands 0x90000000 (group) / 0x98000000 (edge). assemble.rekey()
re-keys to global ids. Region display->slug via supporting.DIARY_REGION_LABELS (inverted).
"""
from __future__ import annotations

from osrs_planner.engine.kg.model import (
    AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, Node, NodeKind, Op,
)
from kg_ingest.ids import _stable_hash, diary_tier_id, quest_id, skill_id
from kg_ingest.builders.supporting import DIARY_REGION_LABELS

_GROUP_BAND = 0x90000000
_EDGE_BAND = 0x98000000
_REGION_SLUG = {label: slug for slug, label in DIARY_REGION_LABELS.items()}
_TIERS = ("easy", "medium", "hard", "elite")


def _gid(owner: str, slot: int) -> int:
    return _GROUP_BAND | _stable_hash(f"{owner}#diary-group#{slot}")


def _eid(owner: str, slot: int) -> int:
    return _EDGE_BAND | _stable_hash(f"{owner}#diary-edge#{slot}")


def _region_slug(display: str) -> str:
    if display not in _REGION_SLUG:
        raise ValueError(f"build_diaries: unknown diary_region {display!r}")
    return _REGION_SLUG[display]


def build_diaries(
    task_records: list[dict],
    reward_records: list[dict] | None = None,
    content_records: list[dict] | None = None,
) -> tuple[list[Node], list[Edge], dict[int, ConditionGroup]]:
    nodes: list[Node] = []
    edges: list[Edge] = []
    groups: dict[int, ConditionGroup] = {}

    # group tasks by (region_slug, tier)
    by_tier: dict[tuple[str, str], list[dict]] = {}
    for rec in task_records:
        key = (_region_slug(rec["diary_region"]), rec["tier"])
        by_tier.setdefault(key, []).append(rec)

    for (region, tier) in sorted(by_tier):
        tasks = by_tier[(region, tier)]
        nid = diary_tier_id(region, tier)
        region_label = DIARY_REGION_LABELS[region]
        nodes.append(Node(
            id=nid, kind=NodeKind.DIARY, name=f"{region_label} {tier.capitalize()}",
            slug=f"{region}-{tier}",
            data={"region": region, "tier": tier,
                  "tasks": [{"n": t["task_number"], "task": t["task"]} for t in sorted(tasks, key=lambda t: t["task_number"])]}))

        # aggregate requirement: max level per skill (strictest boostable wins=False), union of quests
        max_skill: dict[str, tuple[int, bool]] = {}
        quests: dict[str, None] = {}
        for t in tasks:
            for s in t["requirements"].get("skills", []):
                lvl, boost = s["level"], bool(t.get("boostable", False))
                cur = max_skill.get(s["skill"])
                if cur is None or lvl > cur[0]:
                    max_skill[s["skill"]] = (lvl, boost)
            for q in t["requirements"].get("quests", []):
                quests[_normalize_quest(q)] = None

        children: list = []
        for skill in sorted(max_skill):
            lvl, boost = max_skill[skill]
            children.append(ConditionAtom(atom_type=AtomType.SKILL_LEVEL, ref_node=skill_id(skill),
                                          threshold=lvl, data={"boostable": boost}))
        for q in sorted(quests):
            children.append(ConditionAtom(atom_type=AtomType.QUEST, ref_node=quest_id(q),
                                          data={"state": "completed"}))
        root = _gid(nid, 0)
        groups[root] = ConditionGroup(id=root, op=Op.AND, parent=None, children=children)
        edges.append(Edge(id=_eid(nid, 0), type=EdgeType.REQUIRES, src=nid, dst=None, cond_group=root))

    return nodes, edges, groups


def _normalize_quest(raw: str) -> str:
    """Diary quest reqs are prose ('Completion of Rune Mysteries', 'Started Fairytale II...').
    Strip the leading 'Completion of '/'Started ' so quest_id matches the quest node name."""
    s = raw.strip()
    for prefix in ("Completion of ", "Started "):
        if s.startswith(prefix):
            s = s[len(prefix):].strip()
    return s
```

> Note: `_normalize_quest` handles the diary data's prose quest refs. The aggregate gate uses `boostable=False` when *any* task's skill req is non-boostable at the max level; the strictest-task rule is "max level wins, that task's boostable flag applies." For the seed test both are non-boostable. *(Diary quest prose may not always map cleanly to a quest node; Task 9's `validate_kg` tolerates known-missing quest refs the same way it does for quests.)*

- [ ] **Step 4: Run the test → pass**

Run: `./venv/bin/python -m pytest tests/kg_ingest/test_build_diaries.py -v` → 2 passed.

- [ ] **Step 5: Wire into `kg_ingest/assemble.py`**

Add import: `from kg_ingest.builders.diaries import build_diaries`. Add a loader `_load_diary_task_records()` reading `data/achievement_diaries.json`'s `records`. In `assemble()`, build + rekey the diaries independently (their `diary:` owners are disjoint from quests/goals) and merge:

```python
    d_nodes, d_edges, d_groups = build_diaries(_load_diary_task_records())
    d_nodes, d_edges, d_groups = rekey(d_nodes, d_edges, d_groups)
    edges = q_edges + g_edges + cg_edges + d_edges
    groups = {**q_groups, **g_groups, **cg_groups, **d_groups}
```

Add `d_nodes` to `owned_ids` and to the final `dedup_nodes(...)` call — this **promotes** the supporting `diary:` nodes (the diary builder's definition wins; `dedup_nodes` raises only on a *content* conflict, so ensure the diary builder's node matches/extends the supporting shape — same id/kind/slug, richer `data`). Since `dedup_nodes` is first-wins and raises on conflict, place `d_nodes` BEFORE `s_nodes` in the dedup list, and exclude `diary:` ids from `build_supporting`'s `referenced` set (add `"diary"` removal: only send leaf domains MINUS diary that the diary builder owns).

- [ ] **Step 6: Re-assemble + validate + suite**

Run: `./venv/bin/python -m kg_ingest.assemble && ./venv/bin/python data/validate_kg.py` → `KG VALIDATION PASSED`. The KG now has 48 `diary:` tier nodes with requirement gates. (`git diff --stat kg/` shows additive diary nodes/edges/groups + the promoted diary nodes gaining `data`.)
Run: `./venv/bin/python -m pytest -q --continue-on-collection-errors` → all pass (+pre-existing drop_rates).

- [ ] **Step 7: Commit**

```bash
git add kg_ingest/builders/diaries.py kg_ingest/assemble.py tests/kg_ingest/test_build_diaries.py kg/
git commit -m "diaries: 48 tier nodes + aggregate requirement gates from the 492 tasks"
```

---

## Task 3: Diary cape goal + `progress_towards` + `count_satisfied`

**Files:**
- Create: `data/diary_goals.json`
- Create: `kg_ingest/builders/diary_goals.py`
- Modify: `kg_ingest/builders/diaries.py` (emit `progress_towards` from each tier)
- Modify: `kg_ingest/assemble.py`
- Test: extend `tests/kg_ingest/test_build_diaries.py`; create `tests/kg_ingest/test_build_diary_goals.py`

**Interfaces:**
- Produces: `build_diary_goals(goal_records, tier_ids) -> (nodes, edges, groups)` emitting `goal:achievement-diary-cape` (`NodeKind.GOAL`, `data={counter_type:"member_count", thresholds:[48]}`) with a completion `requires` edge whose cond_group leaf is `count_satisfied(set_ref=tier_ids, threshold=48)`, plus a threshold-gated `grants` (the cape reward). `build_diaries` additionally emits one `progress_towards` edge per tier (`src=diary:<r>:<t>, dst=goal:achievement-diary-cape, data={weight:1}`). Builder-local bands for diary_goals: `0xB0000000`/`0xB8000000`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/kg_ingest/test_build_diaries.py`:

```python
def test_each_tier_has_progress_towards_the_cape():
    from osrs_planner.engine.kg.model import EdgeType
    _, edges, _ = build_diaries(_tasks())
    pt = [e for e in edges if e.type is EdgeType.PROGRESS_TOWARDS]
    assert pt and all(e.dst == "goal:achievement-diary-cape" and e.data == {"weight": 1} for e in pt)
```

Create `tests/kg_ingest/test_build_diary_goals.py`:

```python
"""diary cape goal + count_satisfied completion gate (diaries Task 3)."""
from kg_ingest.builders.diary_goals import build_diary_goals
from osrs_planner.engine.kg.model import AtomType, ConditionAtom, EdgeType, NodeKind


def _rec():
    return {"id": "goal:achievement-diary-cape", "name": "Achievement diary cape",
            "counter_type": "member_count", "thresholds": [48],
            "grants": {"reward": "unlock", "category": "equipment",
                       "name": "Achievement diary cape", "access": "Achievement diary cape"}}


def test_cape_node_and_count_satisfied_gate():
    tier_ids = [f"diary:r{i}:easy" for i in range(48)]
    nodes, edges, groups = build_diary_goals([_rec()], tier_ids)
    goal = [n for n in nodes if n.kind is NodeKind.GOAL][0]
    assert goal.id == "goal:achievement-diary-cape"
    assert goal.data == {"counter_type": "member_count", "thresholds": [48]}
    req = [e for e in edges if e.type is EdgeType.REQUIRES][0]
    atom = groups[req.cond_group].children[0]
    assert isinstance(atom, ConditionAtom) and atom.atom_type is AtomType.COUNT_SATISFIED
    assert atom.threshold == 48 and atom.data["set_ref"] == tier_ids


def test_cape_threshold_gated_grant():
    nodes, edges, groups = build_diary_goals([_rec()], ["diary:r:easy"])
    grant = [e for e in edges if e.type is EdgeType.GRANTS][0]
    assert grant.src == "goal:achievement-diary-cape" and grant.cond_group is not None
    assert grant.data["reward"] == "unlock"
```

- [ ] **Step 2: Run → fail.** `./venv/bin/python -m pytest tests/kg_ingest/test_build_diary_goals.py -v` → import error.

- [ ] **Step 3: Implement `kg_ingest/builders/diary_goals.py`** (mirror `kg_ingest/builders/completion_goals.py`, with `count_satisfied` instead of `quest_points`):

```python
"""Diary completion goals (diaries Task 3). Mirrors completion_goals.py but the
accumulator is count_satisfied over the 48 diary tier states (member_count cape)."""
from __future__ import annotations

from osrs_planner.engine.kg.model import (
    AtomType, ConditionAtom, ConditionGroup, Edge, EdgeType, Node, NodeKind, Op,
)
from kg_ingest.ids import _stable_hash, access_id, slugify

_GROUP_BAND = 0xB0000000
_EDGE_BAND = 0xB8000000


def _gid(owner: str, slot: int) -> int:
    return _GROUP_BAND | _stable_hash(f"{owner}#dgoal-group#{slot}")


def _eid(owner: str, slot: int) -> int:
    return _EDGE_BAND | _stable_hash(f"{owner}#dgoal-edge#{slot}")


def build_diary_goals(goal_records: list[dict], tier_ids: list[str]):
    nodes: list[Node] = []
    edges: list[Edge] = []
    groups: dict[int, ConditionGroup] = {}
    for rec in goal_records:
        gid_node = rec["id"]
        thresholds = rec["thresholds"]
        nodes.append(Node(id=gid_node, kind=NodeKind.GOAL, name=rec["name"], slug=slugify(rec["name"]),
                          data={"counter_type": rec["counter_type"], "thresholds": thresholds}))
        # completion gate: count_satisfied over the diary tiers >= final threshold
        req_g = _gid(gid_node, 0)
        groups[req_g] = ConditionGroup(id=req_g, op=Op.AND, parent=None, children=[
            ConditionAtom(atom_type=AtomType.COUNT_SATISFIED, threshold=thresholds[-1],
                          data={"set_ref": list(tier_ids)})])
        edges.append(Edge(id=_eid(gid_node, 0), type=EdgeType.REQUIRES, src=gid_node, dst=None, cond_group=req_g))
        # threshold-gated grant (the cape reward)
        grant = rec.get("grants")
        if grant:
            grant_g = _gid(gid_node, 1)
            groups[grant_g] = ConditionGroup(id=grant_g, op=Op.AND, parent=None, children=[
                ConditionAtom(atom_type=AtomType.COUNT_SATISFIED, threshold=thresholds[-1],
                              data={"set_ref": list(tier_ids)})])
            dst = access_id(grant["access"]) if grant.get("access") else None
            data = {k: v for k, v in grant.items() if k != "access"}
            if grant.get("access"):
                data["access"] = grant["access"]
            edges.append(Edge(id=_eid(gid_node, 1), type=EdgeType.GRANTS, src=gid_node, dst=dst,
                              cond_group=grant_g, data=data))
    return nodes, edges, groups
```

- [ ] **Step 4: Emit `progress_towards` from each tier in `build_diaries`.** In `diaries.py`, after appending the tier's requires edge, add:

```python
        edges.append(Edge(id=_eid(nid, 1), type=EdgeType.PROGRESS_TOWARDS, src=nid,
                          dst="goal:achievement-diary-cape", cond_group=None, data={"weight": 1}))
```

- [ ] **Step 5: Author `data/diary_goals.json`** (the base cape; the trimmed cape is added in Task 9 once both base capes exist):

```json
{
  "_provenance": {"domain": "diary_goals", "source_urls": ["https://oldschool.runescape.wiki/w/Achievement_diary_cape"],
    "accessed": "2026-06-23", "license": "CC BY-NC-SA 3.0", "extraction_method": "manual-transcription-from-wiki", "record_count": 1},
  "records": [
    {"id": "goal:achievement-diary-cape", "name": "Achievement diary cape",
     "counter_type": "member_count", "thresholds": [48],
     "grants": {"reward": "unlock", "category": "equipment", "name": "Achievement diary cape", "access": "Achievement diary cape"}}
  ]
}
```

- [ ] **Step 6: Wire into assemble.** Load `data/diary_goals.json`; pass the 48 tier ids (collect from the diary builder's nodes) to `build_diary_goals`; rekey independently; merge; add to `owned_ids` + dedup. The `progress_towards` `goal:` dst resolves to the goal node (not sent to `build_supporting`, as `goal:` is not a leaf domain).

- [ ] **Step 7: Re-assemble + validate + suite + commit**

Run assemble + `validate_kg` (PASSED) + full suite. Then:
```bash
git add kg_ingest/builders/diary_goals.py kg_ingest/builders/diaries.py data/diary_goals.json kg_ingest/assemble.py tests/kg_ingest/ kg/
git commit -m "diaries: achievement-diary-cape goal (count_satisfied) + progress_towards"
```

---

## Task 4: `data/diary_rewards.json` format + `validate_diary_rewards.py`

**Files:**
- Create: `data/diary_rewards.json` (initial: 1–2 tiers covering item + lamp + effect shapes; expanded to all 48 in Task 9)
- Create: `data/validate_diary_rewards.py`
- Test: `tests/kg_ingest/test_validate_diary_rewards.py`

**Interfaces:**
- Produces: the `data/diary_rewards.json` record schema and `validate_diary_rewards.check_diary_rewards(reward_data, item_ids, item_tradeable, content_ids, skill_ids) -> list[str]` + `main() -> int`. Record per tier:
  ```json
  {"region": "morytania", "tier": "hard",
   "regional_item": {"name": "Morytania legs 3", "item_id": 13110, "supersedes_item_id": 13109},
   "lamp": {"amount": 15000, "min_level": 50, "eligible_skills": "any", "lamp_item": "Antique lamp (hard)"},
   "effects": [{"effect_kind": "rate_multiplier", "magnitude": 0.5, "target_facet": "runes from the chest",
                "target": {"kind": "activity", "name": "Barrows"}, "condition": "unconditional-once-earned", "tier_source": "morytania:hard"}],
   "extra_unlocks": [{"reward_type": "items", "name": "Bonecrusher", "item_id": 13116, "tradeable": false}],
   "source_url": "https://oldschool.runescape.wiki/w/Morytania_Diary"}
  ```

- [ ] **Step 1: Write the failing test** — `tests/kg_ingest/test_validate_diary_rewards.py`: a valid record passes; a bad `effect_kind` is flagged; an unresolved `regional_item.item_id` is flagged; a `lamp.amount` ≤ 0 is flagged; a `target.kind` not in `{skill,activity,monster,region,item}` is flagged; a `supersedes_item_id` not resolving is flagged; the committed seed passes (`main([]) == 0`). (Mirror `tests/kg_ingest/test_validate_quest_rewards.py` structure.)

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement `data/validate_diary_rewards.py`** following the `data/validate_quest_rewards.py` idiom (`errors[]`, `check()`, `main()->int`, print `DIARY-REWARDS VALIDATION PASSED/FAILED`). Invariants: `region` in the 12 region slugs; `tier` in `{easy,medium,hard,elite}`; `regional_item.item_id` resolves in `items_equipment.json`; `supersedes_item_id` (if present) resolves; `lamp.amount` positive int, `lamp.min_level` null-or-positive-int, `lamp.eligible_skills == "any"`; each effect's `effect_kind` in the §4 enum (`stat_multiplier|rate_multiplier|capacity_change|fee_waiver|behavior_toggle|recurring_resource|access`); `effect.target.kind` in `{skill,activity,monster,region,item}` and (when `kind==skill`) the skill resolves; `magnitude` numeric when present; `tier_source == f"{region}:{tier}"`; extra-unlock item_ids resolve + tradeable matches; provenance `source_urls` present.

- [ ] **Step 4: Author the initial seed** (`data/diary_rewards.json`, 1–2 real tiers, source-grounded — e.g. Morytania hard + Ardougne easy — verifying every item_id against `items_equipment.json`).

- [ ] **Step 5: Run tests + `./venv/bin/python data/validate_diary_rewards.py` → PASSED. Commit.**

```bash
git add data/validate_diary_rewards.py data/diary_rewards.json tests/kg_ingest/test_validate_diary_rewards.py
git commit -m "diaries: reward-overlay format + structural validator"
```

---

## Task 5: Diary reward builder — regional items + lamps + `supersedes`

**Files:**
- Modify: `kg_ingest/builders/diaries.py` (consume `reward_records`)
- Modify: `kg_ingest/assemble.py` (load `data/diary_rewards.json`, pass to `build_diaries`)
- Test: extend `tests/kg_ingest/test_build_diaries.py`

**Interfaces:**
- Consumes: `data/diary_rewards.json` records (Task 4 schema).
- Produces: for each reward record, `build_diaries` emits — a `grants` `items` edge (tier → `item:<regional_item.item_id>`); a `supersedes` edge (`item:<this> → item:<supersedes_item_id>`) when present; a `grants` `xp` choice-lamp edge (`dst=None`, `data={reward:"xp", form:"choice_lamp", amount, count:1, eligible_skills:"any", min_level, lamp_item}`); and `grants` edges for each `extra_unlocks` entry. (Effects → Task 7.)

- [ ] **Step 1: Write failing tests** (extend `test_build_diaries.py`): feed a reward record + assert the regional-item `grants` edge (`dst=item:<id>`), the `supersedes` edge (src=higher, dst=lower), the choice-lamp `grants` (with Karamja's `min_level: null` honored as `null`, eligible_skills "any"), and an extra-unlock `grants`. Pass a `reward_records` list to `build_diaries(_tasks(), reward_records=[...])`.

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** the reward emission in `build_diaries` (a `_emit_rewards(tier_id, rec, edges, slot_start)` helper): regional item grant + supersedes; lamp grant; extra-unlock grants. Mirror the `quest_rewards.py` grant-construction (exclude internal keys from edge `data`). Use the diary builder's `_eid(tier_id, slot)` with a running slot so the tier's requires/progress_towards/grants/supersedes edges get distinct builder-local ids (rekey re-derives globals per-owner-cumulatively).

- [ ] **Step 4: Run tests → pass.**

- [ ] **Step 5: Wire `data/diary_rewards.json` into assemble** (load records, pass to `build_diaries(tasks, reward_records=...)`). Re-assemble + `validate_kg` + `validate_diary_rewards` → PASSED. Item nodes (regional items, extra unlocks) resolve via `build_supporting`.

- [ ] **Step 6: Commit.**
```bash
git add kg_ingest/builders/diaries.py kg_ingest/assemble.py tests/kg_ingest/test_build_diaries.py data/diary_rewards.json kg/
git commit -m "diaries: regional item ladder (supersedes) + scaling XP lamps + extra unlocks"
```

---

## Task 6: Content nodes (`data/diary_content_nodes.json` + builder)

**Files:**
- Create: `data/diary_content_nodes.json`
- Create: `kg_ingest/builders/content_nodes.py`
- Modify: `kg_ingest/assemble.py`
- Test: `tests/kg_ingest/test_build_content_nodes.py`

**Interfaces:**
- Produces: `build_content_nodes(content_records) -> list[Node]`. Each record `{id, kind, name, slug, data?}` → one `Node` of the matching `NodeKind` (`activity`/`monster`/`region`; `skill:` targets are NOT created here — they exist). `id` must match its `kind` prefix. Builder-local: content nodes need no edges/groups, so this returns nodes only (like `build_supporting`).

- [ ] **Step 1–4 (TDD):** test that a content record `{"id":"activity:barrows","kind":"activity","name":"Barrows","slug":"barrows"}` → `Node(kind=NodeKind.ACTIVITY, ...)`; an id/kind-prefix mismatch raises; `skill:` ids are rejected (skills aren't content-node-created here). Implement `build_content_nodes` (a small factory like `supporting._build_one`, restricted to `activity/monster/region`).

- [ ] **Step 5: Author `data/diary_content_nodes.json`** — the bounded set of activity/monster/region nodes the 48 tiers' effects target (Barrows, Slayer Tower, Pyramid Plunder, Tears of Guthix, etc.), sourced from the wiki page names. Start with the targets the Task-4 seed effects reference; expand in Task 9.

- [ ] **Step 6: Wire into assemble** (load `data/diary_content_nodes.json`, `nodes += build_content_nodes(records)`, include in `dedup_nodes`). Re-assemble + `validate_kg` → PASSED.

- [ ] **Step 7: Commit.**

---

## Task 7: Effect edges with `dst` = content node

**Files:**
- Modify: `kg_ingest/builders/diaries.py` (emit `effect` edges from reward records)
- Test: extend `tests/kg_ingest/test_build_diaries.py`

**Interfaces:**
- Consumes: the reward record `effects[]` (Task 4 schema) + the content nodes (Task 6).
- Produces: for each effect, an `effect` edge `src = item:<regional_item.item_id>` (the item the effect rides on; or the extra-unlock item), `dst = <resolved content id>` (`skill:<slug>` for `target.kind=="skill"`, else `activity_id/region_id/monster_id(target.name)`, or `item:<id>` for `kind=="item"`), `data = {effect_kind, magnitude?, target_facet, tier_source, condition}`.

- [ ] **Step 1: Write failing test** — a reward record with an effect (`rate_multiplier`, `target.kind="activity"`, `name="Barrows"`) → an `effect` edge `src=item:<regional_item_id>`, `dst="activity:barrows"`, `data.effect_kind=="rate_multiplier"`, `data.magnitude==0.5`, `data.tier_source=="morytania:hard"`. And a `skill`-target effect → `dst="skill:slayer"`.

- [ ] **Step 2: Run → fail.**

- [ ] **Step 3: Implement** `_emit_effects` in `build_diaries`: resolve `target` to a content id (skill via `skill_id`, activity/region/monster via the id helpers, item via `item:<id>`); emit the `effect` edge owned by the regional item (or the extra-unlock item the effect rides on, if the record marks it). Exclude `target`/internal keys from edge `data`; keep `target_facet`/`magnitude`/`tier_source`/`condition`.

- [ ] **Step 4: Run → pass.**

- [ ] **Step 5: Wire + re-assemble + validate.** The effect `dst` content ids must resolve to nodes from Task 6 (`validate_kg` [ref] check enforces this — any effect targeting a missing content node fails, catching an unlisted target). Re-assemble + `validate_kg` + `validate_diary_rewards` → PASSED.

- [ ] **Step 6: Commit.**

---

## Task 8: `verify_diary_rewards.py` — source-grounding gate

**Files:**
- Create: `data/verify_diary_rewards.py`
- Create: `data/raw/diary_reward_blocks.json` (committed cache: per region, the verbatim `==Rewards==` block of the diary wiki page)
- Test: `tests/kg_ingest/test_verify_diary_rewards.py`

**Interfaces:**
- Produces: the diary analog of `data/verify_quest_rewards.py`. For each reward record, derive source tokens (regional item name; lamp amount comma-formatted; each effect's `target_facet` key phrase + magnitude; extra-unlock item names) and assert presence in that region's cached `==Rewards==` block (one block per region covers all 4 tiers — scope-check the tier sub-section where the page separates them). `discrepancy` = token absent → FATAL; `missing_notes` = block bullets unmatched → informational. Offline-default vs the cache + `--refresh`. Optional per-reward `source_token` escape hatch (must be a real substring). `source_token` is verification metadata — EXCLUDE it from KG edge data (Task 5/7 grant/effect data construction must drop `source_token`, mirroring the quest-brick fix).

- [ ] **Step 1–6:** mirror `data/verify_quest_rewards.py` (TDD: a fabricated regional item / effect token is flagged; the committed seed passes; `--refresh` rebuilds the cache; the `extract_rewards_block` regex tolerates `\n*==` heading boundaries). Build the cache from the 12 diary pages. Document in `data/DIARY_REWARDS.md` that this is the deterministic fabrication gate; the LLM verbatim sweep remains the periodic deep audit. Commit.

---

## Task 9: Full 48-tier capture + trimmed cape + integration

**Files:**
- Modify: `data/diary_rewards.json` (expand to all 48 tiers), `data/diary_content_nodes.json` (all targeted content), `data/diary_goals.json` (+ trimmed cape)
- Modify: `data/validate_kg.py` (reward-aware coverage for diary edges/goals)
- Create: `data/DIARY_REWARDS.md`
- Modify: `kg_ingest/builders/diary_goals.py` (trimmed cape supersedes + cross-cape requires)

**Interfaces:**
- `goal:achievement-diary-cape-t` — `NodeKind.GOAL`; a `requires` edge AND-ing two `is_unlocked`/`quest`-style references to **both** `goal:achievement-diary-cape` and `goal:quest-point-cape` (the cross-domain link); a `supersedes` edge (`goal:achievement-diary-cape-t → goal:achievement-diary-cape`).

- [ ] **Step 1: Extend `validate_kg.check_kg`** with diary-aware invariants (mirror the quest reward-edge invariants): every `supersedes` edge's src/dst resolve to `item`/`goal` nodes; every `effect` edge with a `diary:`/`item:` src has a `dst` that resolves to a content node (skill/activity/monster/region/item) and a `data.effect_kind` in the enum; every `diary:` tier node has `data.region`+`data.tier`; `goal:achievement-diary-cape` has `counter_type`/`thresholds`. Add tests to `tests/kg_ingest/test_validate_kg.py`.

- [ ] **Step 2: Author the trimmed cape** in `data/diary_goals.json` + emit it in `diary_goals.py` (the cross-cape `requires` + `supersedes`). Test it.

- [ ] **Step 3: Full capture** — expand `data/diary_rewards.json` to all 48 tiers and `data/diary_content_nodes.json` to every targeted content node, **transcribed from the 12 wiki diary pages** (the `verify_diary_rewards.py` gate + the magnitudes/tier ladders from the item pages). Honor the **Karamja lamp quirk** (easy 1,000/any, medium 5,000/30, hard 10,000/40, elite 50,000/70; distinct `Antique lamp (Karamja Diary)`). Anything uncertain → `known_missing`, not invented.

- [ ] **Step 4: Integration** — run, all green:
  ```bash
  ./venv/bin/python -m kg_ingest.assemble
  ./venv/bin/python data/validate_kg.py            # PASSED
  ./venv/bin/python data/validate_diary_rewards.py # PASSED
  ./venv/bin/python data/verify_diary_rewards.py   # SOURCE-GROUNDING PASSED
  ./venv/bin/python -m kg_ingest.assemble && git diff --quiet kg/ && echo BYTE-STABLE
  ./venv/bin/python -m pytest -q --continue-on-collection-errors
  ```
- [ ] **Step 5: `data/DIARY_REWARDS.md`** — the record schemas + the effect→content model + the Karamja quirk + disclosed limitations (content nodes existence-only; per-task completion is route-only; trimmed-cape reciprocal deferred to quests) + the verifier note.

- [ ] **Step 6: Owner editorial review** — present the 48-tier reward data + the content-node set for the live-player check (the gate the verifier can't make). Apply corrections. Do not consider the brick done until the owner reviews. Commit.

---

## Self-Review

**1. Spec coverage:** §2 structure → Tasks 2 (tiers+reqs), 1 (`count_satisfied`). §3.1 item ladder/`supersedes` → Tasks 1+5. §3.2 lamp (per-tier, Karamja) → Tasks 4+5+9. §3.3 effects (tiered) → Task 7. §3.4 extra unlocks → Task 5. §4 effect→content queryable layer → Tasks 6+7. §5 schema pieces → Task 1 (`supersedes`, `count_satisfied`) + Tasks 6/7 (content nodes, effect.dst). §6 cape (+trimmed) → Tasks 3+9. §7 source map → Tasks 4/8/9. §9 scope / §10 discipline → Tasks 8 (verifier) + 9 (owner review, disclosures). §11 phasing → the Task order. Reconciliation of existing supporting `diary:` nodes → Task 2 Step 5.

**2. Placeholder scan:** No "TBD"/"handle errors". Tasks 4/6/8/9 compress the validator/verifier/content tasks to "mirror the quest-brick equivalent" — legitimate because those files (`validate_quest_rewards.py`, `verify_quest_rewards.py`) exist verbatim on this branch as the exact pattern; the diary-specific schema/invariants are spelled out in each task's Interfaces. The genuinely-new code (count_satisfied eval, the diary builder's aggregation, effect→content resolution) is shown in full.

**3. Type consistency:** `build_diaries(task_records, reward_records=None, content_records=None)` consistent across Tasks 2/5/7. `build_diary_goals(goal_records, tier_ids)` consistent (Tasks 3/9). `goal:achievement-diary-cape` / `count_satisfied` / `EdgeType.SUPERSEDES` consistent throughout. Builder-local id bands disjoint (diaries `0x90/0x98`, content `0xA0/0xA8`, diary_goals `0xB0/0xB8`). Region slug↔label via the single `DIARY_REGION_LABELS` source.
