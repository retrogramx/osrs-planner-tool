# Knowledge-graph node/edge schema — v1 (scratch — NOT a decision)

> Working draft for the eventual `feat/goal-tracker` plan. **Non-binding**; nothing here is locked.
> Companion to [`knowledge-graph.md`](knowledge-graph.md) (direction + sourcing + licensing).
> Real decisions move into a plan/ADR when we build the brick.

---

## Design principles

Gilded Tome's differentiator is an **account-type-aware goal tracker** built on a prerequisite knowledge graph. The KG is the static spine; the tracker overlays per-account state on it to answer *"what is unlocked / what is next."* Five firm separations structure the whole schema.

**(a) Data model, not a graph database.** Nodes and edges are relational tables in SQLite (dev) → Postgres (hosted), loaded into a single in-memory `networkx.MultiDiGraph` and traversed in Python. The graph is small (low tens of thousands of nodes, low hundreds of thousands of edges) — it fits in memory, so we never depend on DB-side graph queries. Postgres is durable storage plus the per-account state layer; it does **no** traversal. No Neo4j.

**(b) Facts vs. Opinion split — for modeling *and* licensing.** Two edge classes that stay cleanly separable:

- **FACTS** (the neutral constraint engine, unencumbered — facts aren't copyrightable, re-derived freely): `REQUIRES`, `GRANTS`, `DROPS`, `LOCATED_IN`, `GATED_BY`.
- **OPINION** (curated/swappable, CC BY-NC-SA 3.0 from the OSRS Wiki): `RECOMMENDED_FOR` + curated path weights/orderings.

The seam is physical (see Opinion layer + Storage). **The test of separability: drop the opinion layer and the engine still loads, traverses, and answers "what's unlocked / next" — it only loses gear recommendations.**

**(c) Global static game-data vs. per-account state.** Every table in the KG is global, shared by all accounts, versioned with game updates, rebuildable by a pure pipeline with **zero per-account columns**. Per-account progress (levels, KC, goals-done) lives in a physically separate schema/file. The engine loads the KG once and overlays each account's state at query time. A KG rebuild can drop/reload the static side without touching user data.

**(d) Account-type-awareness is traversal-time, not data duplication.** The graph is one global structure. Account type (`NORMAL`, `IRONMAN`, `HARDCORE_IRONMAN`, `ULTIMATE_IRONMAN`, + group variants) flips which path is required — an ironman must self-acquire an item (follow its source) where a main can buy it (a gp goal). This is resolved at traversal time via an **edge `scope`** filter + an **engine expansion policy** keyed on item acquisition methods + account mode. The facts themselves stay mode-neutral.

**(e) Schema validity is data-independent.** Any row may carry a `verify` marker ("verify vs wiki later"); structural QA (acyclic REQUIRES, FK integrity, provenance presence) passes regardless of whether exact drop ids or req thresholds are confirmed. The model's expressiveness is what's being validated, not the data values.

---

## Node model

### Storage shape — hybrid (one spine + a few typed side tables)

A single uniform **spine** (`node`) gives a trivial NetworkX load and lets every edge join `node`↔`node` regardless of endpoint type. Typed **side tables** exist *only* for the three kinds whose fields the engine filters/joins on in hot paths (`item`, `skill`, `monster`) because SQLite cannot cheaply index into JSON. Everything else keeps its attributes in a `data` JSON blob. Rationale: pay for indexable columns exactly where the account-type engine hammers them, and nowhere else (YAGNI).

```sql
-- The spine: every node, one row. (v1-CORE)
CREATE TABLE node (
    id          TEXT PRIMARY KEY,            -- namespaced stable id (see ID convention)
    kind        TEXT NOT NULL,               -- closed enum (see taxonomy)
    name        TEXT NOT NULL,               -- display name: "Scurrius"
    slug        TEXT NOT NULL,               -- url/stable slug: "scurrius"
    game_id     INTEGER,                     -- canonical cache id (item/npc); else NULL
    data        TEXT NOT NULL DEFAULT '{}',  -- JSON: kind-specific fields the engine does NOT hot-filter
    verify      TEXT,                        -- 'verify vs wiki later' marker; NULL when confirmed
    source_rev  TEXT,                        -- KG build revision that last touched this row
    CHECK (json_valid(data)),
    UNIQUE (kind, slug),
    CHECK (kind IN (
        'skill','item','monster','quest','access','region','account_type',
        'gear_loadout','activity','diary','combat_achievement','minigame',
        'spellbook','spell','clog_slot'
    ))
);
CREATE INDEX ix_node_kind    ON node(kind);
CREATE INDEX ix_node_game_id ON node(kind, game_id);   -- resolve "item 4151" → node; (kind,game_id), never game_id alone
```

Three typed side tables, 1:1 with `node.id`, only for engine-hot kinds:

```sql
-- (v1-CORE) Items: the engine constantly asks how is this acquired? what slot? — account-type-critical.
CREATE TABLE item_attr (
    id          TEXT PRIMARY KEY REFERENCES node(id) ON DELETE CASCADE,
    slot        TEXT,        -- head|cape|neck|ammo|weapon|body|shield|legs|hands|feet|ring|2h|NULL
    buyable_ge  INTEGER NOT NULL DEFAULT 0,  -- on the Grand Exchange? one acquisition option (see Conditions §)
    tradeable   INTEGER NOT NULL DEFAULT 0,
    members     INTEGER NOT NULL DEFAULT 1,
    stackable   INTEGER NOT NULL DEFAULT 0
);

-- (v1-CORE) Skills: the state overlay compares level/xp vs thresholds.
CREATE TABLE skill_attr (
    id            TEXT PRIMARY KEY REFERENCES node(id) ON DELETE CASCADE,
    is_combat     INTEGER NOT NULL DEFAULT 0,
    is_members    INTEGER NOT NULL DEFAULT 0,
    max_level     INTEGER NOT NULL DEFAULT 99,
    hiscore_index INTEGER       -- column index in Hiscores index_lite (links to state layer)
);

-- (v1-CORE) Monsters/Bosses: drives boss/KC/CA/clog engine branches.
CREATE TABLE monster_attr (
    id                      TEXT PRIMARY KEY REFERENCES node(id) ON DELETE CASCADE,
    is_boss                 INTEGER NOT NULL DEFAULT 0,
    combat_level            INTEGER,
    hiscore_index           INTEGER,   -- boss KC column in Hiscores (NULL if untracked)
    has_combat_achievements INTEGER NOT NULL DEFAULT 0,
    has_collection_log      INTEGER NOT NULL DEFAULT 0
);
```

**Promotion rule (YAGNI gate):** a deferred kind gets its own side table only when the engine starts filtering its fields in a hot loop. That promotion is a clean additive migration thanks to the spine — never add JSON indexing instead.

### Type taxonomy

`kind` is a closed enum. **v1-CORE** = needed to prove the Scurrius worked example end-to-end plus the account-type acquisition logic. Non-core kinds are **ID-reserved now** (prefixes frozen, see ID convention) so later data doesn't churn, but carry no DDL beyond the spine.

> **Fix applied (stress-test secondary + Scurrius GAP):** `diary` and `combat_achievement` are **promoted to v1-CORE**. They are spine-only (cheap), but the "a task gates a downstream unlock" chain cannot be *authored or proven* end-to-end unless they exist as real nodes. Promoting them lets the gating chain be demonstrated, and pairs with the conditional-`GRANTS` fix below so a completed task can grant an access.

| kind | Purpose | Storage | v1 |
|---|---|---|---|
| **skill** | Leveled resource; state overlay compares level/xp vs thresholds | `skill_attr` | **CORE** |
| **item** | Gear/consumable/material; node of DROPS, GRANTS, RECOMMENDED_FOR | `item_attr` | **CORE** |
| **monster** | Killable NPC (boss + non-boss); target of RECOMMENDED_FOR, source of DROPS | `monster_attr` | **CORE** |
| **quest** | Quest; GRANTS access, REQUIRES skills/quests. Acyclic-critical | spine | **CORE** |
| **access** | Abstract unlock/capability ("morytania access", "fairy rings", "full Void"). The glue node that keeps REQUIRES expressive and acyclic | spine | **CORE** |
| **region** | Geographic area; LOCATED_IN target; can be GATED_BY | spine | **CORE** |
| **account_type** | Game mode; flips acquisition rules. Mirrors `AccountMode` enum | spine | **CORE** |
| **gear_loadout** | Reusable style×bracket gear set (RECOMMENDED_FOR many bosses). The opinion-layer normalization node | spine | **CORE** |
| **activity** | Doable thing that isn't a single monster/quest (GE buy, Wintertodt, minigame completion). Lets goals/recs point at non-boss content and models acquisition routes | spine | **CORE** |
| **diary** | Achievement diary region+tier | spine | **CORE** (promoted) |
| **combat_achievement** | CA task or tier | spine | **CORE** (promoted) |
| **minigame** | Minigame | spine | deferred (id-reserved) |
| **spellbook** | Standard/Ancient/Lunar/Arceuus | spine | deferred (id-reserved) |
| **spell** | Individual spell (teleport/combat) | spine | deferred (id-reserved) |
| **clog_slot** | A specific clog item-in-source slot | spine | deferred (id-reserved) |

**`combat_achievement` scope (v1):** `combat_achievement` nodes model per-TASK gates only, tested by the BINARY `combat_achievement` atom (a single task is completed or not — never "in progress"); CA tier-reward gates (Ghommal's hilt etc.) use the `combat_achievement_points` atom against the point total (a tier is reached via points from ANY tasks), NOT a `ca:<tier>` done-membership and NOT "all that tier's tasks done" (neither is a real OSRS state). (scale-G3/G6 de-overload.)

**Why `access` is the most important invented node:** it absorbs the messy real world ("can I get to X / do X / have the full set?") into one clean kind, so REQUIRES edges stay simple *and* the prereq graph stays acyclic. Quests/diaries/items/CA-tasks `GRANTS` an `access:*`; bosses/regions `REQUIRES` it. Producers never point at each other directly — they meet at `access` sink nodes (the acyclicity mechanism). **Guidance — `access` vs `gear_loadout` (the discriminator):** use `access:*` only for a **permanent unlock** — a capability *granted by completing content* (quest/diary/CA/region) that you cannot lose (fairy rings, a spellbook, a slayer unlock, region/instance entry). Use **`gear_loadout`** for a **worn equipment set** — items that resolve to equippable gear in `items_equipment.json` (Void, Barrows, Bandos): ownable, losable, variant (3 Void helms), and tiered (base → Elite). **Oracle:** if a node's composition is dominated by `item` atoms resolving to *equippable* items, it is a `gear_loadout`, **not** an `access` (enforced by invariant I18). Create an `access:*` node only when ≥2 things gate on the same unlock; otherwise REQUIRE the quest/item directly.

**Why `account_type` is a node, not just an enum:** acquisition rules become *data* (`data.must_self_acquire`, `data.can_ge`) the engine reads, rather than game modes special-cased in Python.

**Selected `data` JSON shapes** (load-time validated by pydantic, not the DB):

- `account_type` → `{ "must_self_acquire": true, "can_ge": false }` ← drives account-type path logic
- `gear_loadout` → `{ "style": "melee", "bracket": "mid" }`
- `diary` → `{ "region": "varrock", "tier": "hard" }`
- `combat_achievement` → `{ "tier": "medium", "monster": "npc:7221" }`
- `activity` → `{ "activity_kind": "acquire" }` (also: `shop` | `skilling` | `quest_reward` | `minigame`)
- `access` → `{ "note": "ability to enter the Scurrius fight instance" }`

### ID convention

**Format:** `<prefix>:<key>` — lowercase, namespaced, **immutable**. IDs are the contract between the static KG and per-account `node_ref`s; they **must survive a game-update rebuild** or every account's goals dangle.

| kind | prefix | key source | example |
|---|---|---|---|
| item | `item:` | game item id | `item:4151` |
| monster | `npc:` | game npc id | `npc:7221` |
| skill | `skill:` | canonical slug | `skill:attack` |
| quest | `quest:` | slug | `quest:dragon-slayer-i` |
| access | `access:` | slug | `access:fairy-rings`, `access:scurrius-lair` |
| region | `region:` | slug | `region:varrock-sewers` |
| account_type | `account:` | slug (from `AccountMode`) | `account:ironman` |
| gear_loadout | `gear_loadout:` / `loadout:` | slug or `style:bracket[:variant]` | `gear_loadout:void`, `loadout:melee:mid` |
| activity | `activity:` | slug | `activity:ge-buy`, `activity:fight-caves` |
| diary | `diary:` | `region:tier` | `diary:varrock:hard` |
| combat_achievement | `ca:` | `monster-slug:task-slug` | `ca:scurrius:smashing-the-rat` |
| minigame | `minigame:` | slug | `minigame:wintertodt` |
| spellbook | `spellbook:` | slug | `spellbook:lunar` |
| spell | `spell:` | slug | `spell:high-alchemy` |
| clog_slot | `clog:` | `source-slug:item-slug` | `clog:scurrius:scurrius-spine` |

**Stability rules:**

1. **`id` is immutable.** A rename changes `name`/`slug`, never `id`.
2. **Canonical game ids where they exist** (items, NPCs): the id IS the key — `item:<id>`, `npc:<id>`. Jagex never recycles these; they survive renames and join directly to Hiscores/RuneLite/cache dumps. Store the integer also in `node.game_id`.
3. **Slugs where no game id exists** (skills, quests, access, regions, loadouts, diaries, CAs): authored once via a fixed slugify (lowercase, spaces→`-`, strip punctuation, keep roman numerals: `dragon-slayer-ii`) and **frozen** — never re-derived from a changed name.
4. **`UNIQUE(kind, slug)`** catches accidental dup-slug authoring; cross-kind collisions are impossible by prefix namespacing.
5. **Parse on the first colon** for the prefix; the remainder is the opaque key (single-key slugs never contain colons; composite-key kinds — `gear_loadout`, `diary`, `combat_achievement`, `clog_slot` — carry colon-separated slugs, e.g. `melee:mid`, `varrock:hard`, so the slug is the full post-prefix key that `UNIQUE(kind,slug)` needs).
6. **Look up game ids before authoring** — swapping `npc:scurrius` → `npc:7221` later is a breaking id change. A `node_alias(old_id, new_id)` table (deferred) absorbs the rare unavoidable rename.

---

## Edge model — facts

### Storage shape — one `edge` table, conditions out-of-line

One typed `edge` table holds all edge types. It promotes only `qty` and `weight` to columns (the two scalars read on a hot path / used for opinion ordering), references a condition tree by id, and carries a `scope` JSON for account-type filtering.

> **Fix applied (stress-test MUST-FIX #1):** `GRANTS` edges **and `gear_loadout` composition edges** may carry a `cond_group`. The column already lives on the shared `edge` table; the change is to **lift the CHECK that implicitly treated grants as unconditional** and let the loader evaluate the tree. This enables both **conditional access grants** (an unlock gated by a conjunction, e.g. quest AND skill) and **gear-set compositions** — "full Void = an `AND`-of-4-slots `item` tree (helm = `OR` of 3)" carried on the `gear_loadout:void` node — which the flagship `(70 Att AND 70 Str) OR full Void` example *depends on*: otherwise its full-Void branch is either unsatisfiable or falsely true on a single piece.

```sql
CREATE TABLE edge (
    id          INTEGER PRIMARY KEY,              -- surrogate; edges have no natural key
    type        TEXT NOT NULL,                    -- enum (see edge-type table)
    edge_class  TEXT NOT NULL,                    -- 'fact' | 'opinion'  (the licensing seam)
    src         TEXT NOT NULL REFERENCES node(id) ON DELETE CASCADE,
    dst         TEXT          REFERENCES node(id) ON DELETE CASCADE,  -- nullable: NULL when the
                                                                     -- constraint IS the cond tree
    cond_group  INTEGER REFERENCES condition_group(id) ON DELETE SET NULL,  -- NULL ⇒ unconditional
    scope       TEXT,                             -- JSON account-type filter; NULL ⇒ all modes
    qty         INTEGER,                          -- quantity on the edge itself (100x bones); NULL ⇒ 1/NA
    weight      REAL,                             -- opinion: curated ordering/cost; facts usually NULL
    data        TEXT NOT NULL DEFAULT '{}',       -- JSON: per-edge extras (rate, method, style, bracket, rank…)
    verify      TEXT,
    source_rev  TEXT,
    CHECK (json_valid(data)),
    CHECK (scope IS NULL OR json_valid(scope)),
    CHECK (edge_class IN ('fact','opinion')),
    CHECK (type IN (
        'requires','grants','drops','located_in','gated_by',   -- facts
        'recommended_for'                                       -- opinion
    )),
    -- licensing invariant: recommended_for ⟺ opinion; all else ⟺ fact
    CHECK ((type = 'recommended_for') = (edge_class = 'opinion'))
    -- NOTE: NO check forcing grants.cond_group to be NULL — grants may be conditional (fix #1)
);
CREATE INDEX ix_edge_type_src ON edge(type, src);   -- "what does X require / grant"
CREATE INDEX ix_edge_type_dst ON edge(type, dst);   -- reverse: "what requires / sources X"
CREATE INDEX ix_edge_class    ON edge(edge_class);  -- bulk-load facts only, or opinion only
CREATE INDEX ix_edge_cond     ON edge(cond_group);  -- hydrate conditions in one pass
```

### Fact edge-type table

We store **5 fact types only.** `UNLOCKS` and `SOURCED_FROM` are *inverse projections*, derived from the reverse index (`G.reverse()`) rather than stored — storing them would duplicate every fact and risk drift. Single source of truth.

Direction convention: producer-style edges read `producer → produced`; `REQUIRES` reads `dependent → prerequisite`.

| type | Direction (src → dst) | Legal src → dst | Key props | v1 |
|---|---|---|---|---|
| **requires** | "src needs dst" | Quest, Activity, Item(craft), Diary, CA, Access, GearLoadout, Monster → Skill, Quest, Item, Access, Diary, CA, AccountType | `cond_group` (thresholds/OR), `qty` (item counts) | **CORE** |
| **grants** | "src gives dst" | Quest, Diary, CA, Minigame, Item, Activity, Region → Access, Spellbook, Region | `cond_group` (**now allowed** — conjunctive/conditional grants) | **CORE** |
| **drops** | "src drops dst" | Monster, Activity → Item, ClogSlot | `data.rate` (verbatim string e.g. "1/3000"), `data.members` | **CORE** |
| **located_in** | "src is in dst" | Monster, Quest, Item-source, Activity, Access → Region | — | **CORE** |
| **gated_by** | "src is gated behind dst" | Region, Activity, Item → Access | — | **CORE** |

- **`GATED_BY`** is kept distinct from `REQUIRES` deliberately: it is a *coarse* "you can't even enter without X" gate, so the engine can message "region locked" vs. "stat too low" differently. It does **not** participate in the prereq DAG.
- **`DROPS`** is a fact but an *acquisition option*, resolved per-mode (see Conditions §) — it deliberately stays **out** of the REQUIRES DAG (a boss "requiring" its own drop is not a prerequisite).

### Edge-property typing

SQLite won't type a JSON blob, so the contract two engineers build to is a **pydantic discriminated union keyed on `type`**, enforced by the loader:

```python
class RequiresProps(BaseModel):
    metric: Literal["level","xp","kc","cl"] | None = None  # interprets cond atoms / qty
    consumed: bool = False                                 # is the item consumed satisfying the req?

class DropsProps(BaseModel):
    rate: str | None = None        # "1/200" — verbatim from wiki; engine doesn't math on it in v1
    members: bool = True

class GrantsProps(BaseModel):
    method: Literal["complete","own_set","reward"] | None = None  # how the grant fires (gloss)

EDGE_PROPS = {
    "requires": RequiresProps, "grants": GrantsProps, "drops": DropsProps,
    "located_in": NoProps, "gated_by": NoProps, "recommended_for": RecommendedProps,
}
```

Structural integrity lives in SQL (FKs, CHECKs, the acyclic invariant); payload shape lives in pydantic at load time.

### The acyclic REQUIRES projection

**The prereq DAG is built from `requires` edges plus synthetic dependency edges; `grants` is NOT projected structurally.**

> **Fix applied (stress-test MUST-FIX #2):** the original "flip every `grants` edge into the DAG" was semantically lossy in two ways and is **replaced**:
> 1. **Alternative grant sources must not collapse into an AND.** If `access:A` is granted by `Q1` *or* `Q2` (common in OSRS), flipping both emits `A→Q1` and `A→Q2`, so `nx.descendants(A)` falsely claims you must complete *both*. **Fix:** grant disjunction is represented as an **`OR` `cond_group`** on whatever *requires* A (an `OR` of the specific typed atoms — e.g. `quest` atoms, or an `is_unlocked` atom on the granted `access` node), so alternatives are **evaluated, not conjoined**. Grants are not hard prereq edges.
> 2. **Parallel `requires` edges must not collapse.** Projecting a `MultiDiGraph` into a plain `DiGraph` silently drops parallel edges' distinct `cond_group`/`qty` (last-writer-wins). **Fix:** project into a `MultiDiGraph` (or merge parallels under an implicit AND) so every condition survives.
> 3. **Cycle-checking sees grants and all ref-bearing cond-leaves.** Grant edges are cycle-only synthetics; ref-bearing condition leaves (`item`, `is_unlocked`, `gear_loadout`, `quest`, `achievement_diary`, `combat_achievement`, `kill_count`) are projected as real `cond_dep` edges (so the closure is complete) that the cycle check also sees — so a tangle through a grant **or** any ref-bearing atom is caught, without grant flips being treated as hard prerequisites.

```python
def requires_dag(g: nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Acyclic REQUIRES projection. Edge a→b means 'a requires b' (b is the prerequisite).
       Parallel edges preserved (MultiDiGraph). Ref-bearing condition leaves are projected as
       'cond_dep' edges so the prereq closure is COMPLETE even for dst=NULL pure-condition edges;
       grant flips remain cycle-only synthetics."""
    dag = nx.MultiDiGraph()
    dag.add_nodes_from(g.nodes(data=True))

    # 1) real prerequisite edges — keep parallels, keep each condition
    for u, v, d in g.edges(data=True):
        if d["etype"] == "requires" and v is not None:
            dag.add_edge(u, v, cond_group=d["cond_group"], qty=d["qty"], kind="requires")

    # 1b) ref-bearing condition leaves → real closure edges (FIX gap 1: a dst=NULL requires edge
    #     carries its prereqs ONLY in its cond tree, so without this descendants(dag, goal) misses
    #     them). EVERY atom whose atom_type carries a ref_node FK — item, is_unlocked, gear_loadout,
    #     quest, achievement_diary, combat_achievement, kill_count — projects as a 'cond_dep' edge (a dependency,
    #     possibly an OR alternative; NOT a forced single step). Planner reads `kind` to tell hard
    #     'requires' from 'cond_dep'. Non-ref atoms (quest_points, combat_achievement_points, account_type) → skipped.
    for atom in iter_ref_leaves(g):
        dag.add_edge(atom.owner_src, atom.ref_node, kind="cond_dep", cond_group=atom.group_id)

    # 2) cycle-only synthetic: grant flips. cyc inherits dag's cond_dep edges, so the acyclicity
    #    check now sees ALL ref-bearing atoms (FIX gap 2: previously only item/is_unlocked leaves were checked).
    cyc = dag.copy()
    for u, v, d in g.edges(data=True):
        if d["etype"] == "grants":
            cyc.add_edge(v, u, kind="grant_synthetic")   # granted depends-on granter (cycle check only)

    if not nx.is_directed_acyclic_graph(cyc):            # ← QA INVARIANT — fails the build
        raise ValueError(f"REQUIRES projection has a cycle: {list(nx.simple_cycles(cyc))[:20]}")
    return dag
```

**Direction is fixed and documented:** `a → b` = "a requires b", so the full prerequisite closure of a goal is `nx.descendants(dag, goal)`; a valid completion order is `reversed(list(nx.topological_sort(dag)))`. The acyclicity check runs on the grant-flip-augmented graph; the returned `dag` (hard `requires` **plus** `cond_dep` leaves, parallels preserved) is what the planner traverses — it filters on `kind` to tell a forced prerequisite from an OR-alternative dependency, and `nx.descendants(dag, goal)` is now a complete closure even for `dst=NULL` condition edges.

---

## Conditions & account-type-awareness

### Representation — normalized condition-group tree

Conditions are stored as a **normalized side-table tree** (`condition_group` + `condition_atom`), evaluated by a recursive AST-style evaluator. This keeps the node namespace pure (real game entities only — it also powers public search/autocomplete), gives **referential integrity for free** via real FK rows from atoms to nodes (a JSON-AST blob hides node refs and needs a custom linter to recover integrity), and maps cleanly to a recursive `evaluate`. The cost — a couple of joins to hydrate a tree — is negligible: conditions are evaluated only for the handful of nodes on a candidate path.

The common case stays zero-overhead: **`cond_group IS NULL` means unconditional**, and multiple null-condition `requires` edges out of one `src` are **implicitly AND-ed**. You only author a tree when there's genuine OR/NOT/threshold-alternative structure (~15% of real OSRS reqs).

```sql
-- Boolean expression trees, normalized. Referenced by edge.cond_group (requires AND grants) and loadout lines.
CREATE TABLE condition_group (
    id      INTEGER PRIMARY KEY,
    op      TEXT NOT NULL CHECK (op IN ('AND','OR','NOT')),       -- NOT ⇒ exactly one child
    parent  INTEGER REFERENCES condition_group(id) ON DELETE CASCADE,  -- NULL ⇒ root
    note    TEXT                                                  -- human gloss / wiki footnote text
);
CREATE INDEX ix_cg_parent ON condition_group(parent);

-- Leaves: one testable predicate each.
CREATE TABLE condition_atom (
    id        INTEGER PRIMARY KEY,
    group_id  INTEGER NOT NULL REFERENCES condition_group(id) ON DELETE CASCADE,
    atom_type TEXT NOT NULL CHECK (atom_type IN (
                'skill_level','skill_xp','combat_level','quest','achievement_diary',
                'combat_achievement','item','is_unlocked','gear_loadout','kill_count','quest_points','account_type',
                'clue_scrolls','combat_achievement_points'
              )),
    ref_node  TEXT REFERENCES node(id) ON DELETE CASCADE,  -- the skill/quest/item/access the atom tests
    threshold INTEGER,                                     -- 70 (level), 43 (prayer), KC count, qp…
    qty       INTEGER,                                     -- quantity for item (100x)
    data      TEXT NOT NULL DEFAULT '{}',                  -- e.g. account_type value
    CHECK (json_valid(data))
);
CREATE INDEX ix_atom_group ON condition_atom(group_id);
CREATE INDEX ix_atom_ref   ON condition_atom(ref_node);
-- quest: data.state = required quest progress ∈ {not_started, in_progress, completed} (ORDERED enum; "state >= required"); a bare quest prereq = completed, the wiki "Started:" convention = in_progress
-- combat_achievement_points:   threshold = total Combat Achievement points >=, no ref_node (twin of quest_points)
-- clue_scrolls:  threshold = n; names its set via data.set_ref = [node ids]; '>= n members satisfied'
```

Atom semantics (always `>=` for thresholds — the only comparator OSRS prereqs use; a `cmp` field is deferred until a `<` requirement appears, which it never does in prereqs):

- `skill_level` / `skill_xp` → `progress[ref_node] >= threshold`
- `combat_level` → `state.combat_level >= threshold` (OSRS combat level is a derived formula computed once into state, not re-derived in the tree)
- `quest` → `state.quest_state[ref_node] >= data.state` (ref_node = the quest; `data.state` ∈ {not_started, in_progress, completed}, an ORDERED enum, so a `completed` requirement is met only by `completed` while an `in_progress` requirement is met by `in_progress` or `completed`; account-state may be any of the three)
- `achievement_diary` → `state.diary_state[ref_node] >= data.state` (3-state {not_started, in_progress, completed}; a diary TIER reaches `completed` only when ALL its tasks are done — task-based)
- `combat_achievement` → `ref_node ∈ state.done` (per-TASK and BINARY: a single CA task is either completed or not — never "in progress")
- `item` → `progress[ref_node] >= (qty or 1)`
- `is_unlocked` → `ref_node ∈ state.done` — boolean presence of a **permanent unlock** (an `access:*` node: fairy rings, a spellbook, a slayer unlock, region/instance entry). Once granted it persists; checked against the durable `done` set.
- `gear_loadout` → evaluate the `gear_loadout:*` node's **composition** cond_group (the AND/OR-of-`item` tree that defines the worn set) against **current** `state.counts`. **Dynamic, not `done`:** gear is ownable/losable, so it is re-checked from live item counts every time — the key difference from `is_unlocked`. (e.g. `gear_loadout:void` = a Void helm + top + robe + gloves, with variant ORs; see the worked example.)
- `kill_count` → `progress[ref_node] >= threshold` (ref_node = the monster whose KC is tested)
- `quest_points` → `state.qp >= threshold` (global quest-point counter, no ref_node — like `combat_level`)
- `combat_achievement_points` → `state.combat_achievement_points >= threshold` (global Combat-Achievement point total, no ref_node; a CA TIER reward is reached via this points threshold accumulated from ANY tasks, NOT a "all that tier's tasks done" membership)
- `clue_scrolls` → `count(m in data.set_ref if m satisfied) >= threshold` (cardinality over a named set; no single ref_node)
- `account_type` → `account.mode == data.value` (lets a branch be mode-specific)

### Account-type-awareness mechanism

Account type acts at **three distinct stages** that operate at different times and compose cleanly. Crucially, **none duplicates the fact graph** — the data is one global structure, and facts stay mode-neutral.

**1. `scope` (graph-construction filter).** A nullable JSON column on `edge`. Closed grammar over `AccountMode` strings:

```jsonc
null                                              // applies to ALL modes (the default)
{ "modes": ["normal"] }                           // only mains
{ "not_modes": ["normal"] }                       // everyone except mains (all irons)
```

An edge is in-scope iff `scope IS NULL` OR `mode ∈ modes` OR (`not_modes` present AND `mode ∉ not_modes`). Filtering is the **first** step of graph build: `G_account = (nodes, [e for e in edges if in_scope(e, mode)])`.

**2. The engine expansion policy (the actual buy-vs-acquire decision).** This is where account-type-awareness earns its keep and stays mode-neutral in the data. When resolving an unmet "need item X", the engine reads the item's **acquisition methods** and the account's `data` flags.

> **Fix applied (stress-test partial-finding on ironman acquisition):** a single `buyable_ge` boolean **under-models acquisition** — it mislabels NPC-shop / quest-reward / skilling routes, and `DROPS`-only sourcing omits non-drop acquisition entirely (Fire cape, Barrows gloves, Void come from *activity/minigame completion*, not a drop). **Fix:** generalize sourcing into an **acquisition-method dimension**. The `activity` kind already models non-drop routes; the expansion policy enumerates *all* in-scope acquisition methods for an item and picks the cheapest per mode, instead of branching on one boolean.

Acquisition methods for item X are enumerated from the facts:

| method | fact pattern | available to main? | available to iron? |
|---|---|---|---|
| `ge` | `item_attr.buyable_ge=1` | yes (gp goal) | no (`can_ge=false`) |
| `drop` | `Monster/Activity --drops--> X` | yes | yes (self-acquire → recurse) |
| `shop` | `activity(shop) --grants/drops--> X` | yes | yes |
| `quest_reward` | `Quest --grants--> X` (or activity) | yes | yes |
| `skilling` | `activity(skilling) --drops/grants--> X` | yes | yes |

```python
def expand_need_item(item_id, account, kg):
    at      = kg.account_type[account.mode].data          # must_self_acquire, can_ge
    methods = kg.acquisition_methods(item_id, account.mode)  # in-scope ge|drop|shop|quest_reward|skilling
    if at["can_ge"] and not at["must_self_acquire"] and "ge" in methods:
        return GpGoal(item_id, gp=price(item_id))         # MAIN: a gp goal (price from ingest layer)
    candidates = [m for m in methods if m != "ge"] if not at["can_ge"] else methods
    if not candidates:
        return Unacquirable(item_id, reason="no in-scope acquisition method")  # surface the dead end
    chosen = cheapest_method(candidates, account, kg)     # ranks by per-method data.cost (see below)
    cost = kg.method_cost(item_id, chosen)                # {currency, amount} | None  (G4 cost model)
    if cost and cost["currency"] == "coins":
        return AcquireVia(chosen, gp=cost["amount"], recurse=True)   # coin shop cost = a gp goal
    if cost:
        return AcquireVia(chosen, currency=cost, recurse=True)       # alt currency → its producer goal
    return AcquireVia(chosen, recurse=True)               # IRON: self-acquire via chosen route → recurse
```

Cost model (scale-G4): shop/quest_reward acquisition facts may carry `data.cost = {currency, amount}` (currency ∈ `coins | void_commendation | …`); the planner emits a gp goal for coins or a currency goal (recursing into the currency's producer, e.g. Pest Control for commendation points) for alt currencies. Without it `cheapest_method` has nothing to rank — it is what makes per-mode effort estimation real.

For one `npc:7221` (Scurrius) goal, a NORMAL account's gear leaves terminate at gp goals; an IRONMAN's *same* leaves expand into the bosses/minigames/skills that produce the gear — a genuinely different required subgraph from one shared graph. GE price is **not** in the KG (it's volatile; the ingest layer caches it). The KG only flags *that* an item is buyable and *what other routes exist*.

**3. `account_type` atoms (rare, for reqs that are intrinsically mode-conditional).** When a prerequisite itself differs by mode in a way that isn't just buy-vs-acquire, an `OR` branch carries an `account_type` atom; the evaluator prunes branches whose atom is false for the account.

### Worked condition: `(70 Attack AND 70 Strength) OR full Void`

Stored as a tree on a `requires` edge whose `dst` is NULL (the constraint *is* the tree):

```
condition_group:                         condition_atom:
  G_root  (id=1, op=OR,  parent=NULL)      a1 (group=2, skill_level, ref=skill:attack,    threshold=70)
    ├─ G_stats (id=2, op=AND, parent=1)    a2 (group=2, skill_level, ref=skill:strength,  threshold=70)
    └─ G_void  (id=3, op=AND, parent=1)    a3 (group=3, gear_loadout, ref=gear_loadout:void)
```

```sql
-- the requires edge that carries it
INSERT INTO edge (type, edge_class, src, dst, cond_group, scope)
VALUES ('requires','fact','npc:7221', NULL, 1, NULL);
```

**What makes `gear_loadout:void` satisfied (its composition, re-checked against current items).** A `gear_loadout:*` node carries its **composition** as a `cond_group` on a `requires` edge with `dst=NULL` — the same "the constraint *is* the tree" pattern as above. The `gear_loadout` leaf is satisfied **iff the account currently owns the set** (evaluated from live item counts, never cached as `done` — gear is losable):

```
condition_group:  G_set (id=10, op=AND, parent=NULL, note="full Void Knight set, currently owned")
                    └─ G_helm (id=11, op=OR, parent=10, note="any one Void helm")
condition_atom:   (in G_helm) item ref=item:11663 (mage helm) ; item ref=item:11664 (ranger helm) ;
                              item ref=item:11665 (melee helm)
                  (in G_set)  item ref=item:8839 (top) ; item ref=item:8840 (robe) ;
                              item ref=item:8842 (gloves)
```

```sql
-- the gear_loadout node + its composition: a dst=NULL `requires` edge carrying the AND-of-slots tree
INSERT INTO node (id, kind, name, slug, data)
VALUES ('gear_loadout:void','gear_loadout','Full Void','void','{"styles":["melee","ranged","magic"]}');
INSERT INTO edge (type, edge_class, src, dst, cond_group)
VALUES ('requires','fact','gear_loadout:void', NULL, 10);
-- (the composition is owned by the loadout node itself; the `gear_loadout` atom re-evaluates this
--  tree against current item counts every read, so a dropped/alched piece is reflected immediately.)
```

Without the `AND` tree, four independent piece checks would be **implicitly OR-ed**, so owning *one* piece would falsely satisfy "full Void." The helm clause is an `OR` of the three Void helms (mage/ranger/melee) — the real set rule (the helm slot has three valid fillers), not a false-OR; the conjunction is across the four *slots*. **Tiers:** a stricter `gear_loadout:elite-void` swaps the top/robe for their Elite versions — which themselves carry `requires → achievement_diary(western-provinces:hard, completed)` to obtain — so the engine routes an account through the diary before the upgrade. Modeling Void as `is_unlocked`/`access` would instead collapse all of this (the 3 style helms, base→Elite tiers, and *partial* 3/4-piece progress) into one binary, which it is not.

The recursive evaluator (state from the per-account overlay):

```python
def evaluate(group_id, st, kg) -> bool:
    g = kg.cond_group[group_id]
    children = kg.children_of(group_id)          # sub-groups + atoms
    results = [evaluate(c, st, kg) if c.is_group else atom_satisfied(c, st) for c in children]
    if g.op == "AND": return all(results)
    if g.op == "OR":  return any(results)
    if g.op == "NOT": return not results[0]

def atom_satisfied(a, st) -> bool:
    if a.atom_type == "skill_level": return st.levels.get(a.ref_node, 1) >= a.threshold
    if a.atom_type == "combat_level":return st.combat_level >= a.threshold
    if a.atom_type == "item":    return st.counts.get(a.ref_node, 0) >= (a.qty or 1)
    if a.atom_type == "is_unlocked": return a.ref_node in st.done                          # permanent unlock
    if a.atom_type == "gear_loadout":return evaluate(kg.composition_of(a.ref_node), st, kg)  # dynamic: re-check the set's item tree vs current counts
    if a.atom_type == "account_type":return st.mode == a.data["value"]
    if a.atom_type == "quest":   return QUEST_STATE_ORDER[st.quest_state.get(a.ref_node, "not_started")] >= QUEST_STATE_ORDER[a.data["state"]]
    ...
```

On an ironman with 75 Atk / 60 Str / no Void: `OR( AND(75≥70=T, 60≥70=F)=F, gear_loadout(void)=F ) = False`. A sibling `unmet_leaves` walk returns the cheapest failing branch — `[skill_level strength 70]` (cheaper than acquiring full Void) → *"next: train Strength to 70."*

### Ironman-vs-main divergence (concrete)

For *reaching* Scurrius there is **no** divergence — access is free for all modes. The divergence appears only in the **gear-acquisition** subgraph: a NORMAL account's recommended-gear leaves terminate at gp goals; an IRONMAN's *same* leaves expand into source content (e.g. Fire cape → `activity:fight-caves` completion; Barrows gloves → an activity/quest reward; Void → Pest Control). This is handled entirely by the expansion policy reading acquisition methods + `account_type.data`, from one shared graph.

### Condition QA

- **Acyclic REQUIRES includes condition leaves.** The linter emits each `is_unlocked`/`gear_loadout`/`item` atom referencing node N as a synthetic `src → N` dependency edge *to the cycle checker only* (not stored), so OR/AND logic — on `requires` **and** the new conditional `grants` / loadout-composition trees — can't smuggle in a cycle.
- **Referential integrity comes free** from the `condition_atom.ref_node` FK.
- **Grammar validity:** a load-time linter rejects unknown `op`/`atom_type` and malformed trees (NOT with ≠1 child, AND/OR with 0 children). Caught in CI, not production.

---

## Opinion layer

### RECOMMENDED_FOR — per-loadout, not per-slot-item

`gear_loadout` is a **node**; `RECOMMENDED_FOR` is a loadout→target `edge` row in the unified table; loadout contents live in one `loadout_item` side table. The recommendation edge is per-*loadout*, never per-slot-item, for four reasons:

1. **Conditions are loadout-scoped** — "only with full Void" governs a *combination* of slots, not one cell.
2. **Reuse is the normalization win** — generic mid/high tables repeat across dozens of bosses. One `recommended_for` edge per (loadout, boss) instead of ~11 per boss.
3. **Ranking is internal to the table**, not a property of the edge to the boss.
4. **Style × bracket is the loadout's identity**, encoded once on the node.

The 4-D wiki structure maps as: **style** + **bracket** on the `gear_loadout` node (denormalized onto the edge for filter-without-join); **slot** + **ranked list** as rows in `loadout_item`; **footnote conditions** as `cond_group` FKs at three granularities (per-line, per-consumable, whole-loadout edge); **consumables/inventory** as `loadout_item` rows with non-slot `slot` values (`inv:food`, `inv:spec`, `inv:potion`, …).

```sql
-- Loadout contents: the 4-D table (style × bracket × slot × rank) + consumables. (v1-CORE)
CREATE TABLE loadout_item (
    id          INTEGER PRIMARY KEY,
    loadout     TEXT NOT NULL REFERENCES node(id) ON DELETE CASCADE,   -- the gear_loadout node
    item_node   TEXT NOT NULL REFERENCES node(id) ON DELETE CASCADE,   -- kind='item' (FK into FACT catalog)
    slot        TEXT NOT NULL,        -- 'head'…'ring','2h' OR 'inv:food'/'inv:spec'/'inv:potion'/'inv:rune'/'inv:teleport'
    style       TEXT,                 -- 'melee'|'ranged'|'magic'|NULL (slot-agnostic, e.g. teleports)
    bracket     TEXT,                 -- 'mid'|'high'|NULL
    rank        INTEGER NOT NULL DEFAULT 1,   -- 1 = most effective (the ranked-list dimension)
    qty         INTEGER,                       -- consumable counts (8x brews)
    cond_group  INTEGER REFERENCES condition_group(id) ON DELETE SET NULL,  -- per-line footnote (loadout-wide)
    verify      TEXT,                 -- 'verify vs wiki later' marker
    data        TEXT NOT NULL DEFAULT '{}',
    CHECK (json_valid(data))
);
CREATE INDEX ix_loadout_item ON loadout_item(loadout, style, bracket, slot, rank);
```

`loadout_item.item_node` FKs into the **fact** `item` catalog — opinion points *into* facts, never the reverse. That one-way directionality keeps facts unencumbered.

A `recommended_for` edge (in the unified `edge` table) carries `data.style`, `data.bracket`, `data.rank` (which loadout wins when several compete for the same target+style+bracket), `weight` (curated ordering), `cond_group` (whole-loadout footnote), and **must** carry provenance.

### Per-boss line override (the reuse-vs-tailoring fix)

> **Fix applied (stress-test MUST-FIX #3 + Scurrius GAP-4):** a shared `gear_loadout` is `RECOMMENDED_FOR` many bosses, but `loadout_item.cond_group` is shared by **every** referencing boss — so a per-boss slot swap (the wiki's per-slot footnotes routinely need this, e.g. "Scurrius wants the neck slot swapped") forces a fork that **destroys the reuse the `gear_loadout` node exists to provide**. The original draft had to choose reuse XOR per-boss tailoring. **Fix:** a small override table keyed on `(recommended_for_edge, slot)` that the resolver layers over the base loadout for that one target. One shared loadout; per-boss line swaps without forking.

```sql
-- Per-(recommended_for edge, slot) override of a SHARED loadout. (v1-CORE)
CREATE TABLE loadout_override (
    id          INTEGER PRIMARY KEY,
    rec_edge    INTEGER NOT NULL REFERENCES edge(id) ON DELETE CASCADE,   -- the recommended_for edge (loadout→boss)
    slot        TEXT NOT NULL,        -- the slot being overridden for THIS target only
    item_node   TEXT REFERENCES node(id) ON DELETE CASCADE,  -- replacement item (NULL = suppress this slot here)
    rank        INTEGER NOT NULL DEFAULT 1,
    cond_group  INTEGER REFERENCES condition_group(id) ON DELETE SET NULL,  -- per-target line footnote
    verify      TEXT,                 -- 'verify vs wiki later' marker
    data        TEXT NOT NULL DEFAULT '{}',
    CHECK (json_valid(data))
);
CREATE INDEX ix_loadout_override ON loadout_override(rec_edge, slot);
```

Resolver: `resolved_loadout(rec_edge) = base loadout_item rows, with any (slot) overridden by loadout_override where rec_edge matches`. Provenance attaches to the override row too (an override is itself a wiki footnote). This preserves the headline normalization (one `loadout:melee:mid` reused) **and** expresses Scurrius's neck swap.

### Provenance & separability

Provenance is a side table so attribution is data-driven and the opinion+provenance dataset is a clean separable export:

```sql
CREATE TABLE provenance (
    id             INTEGER PRIMARY KEY,
    edge_id        INTEGER REFERENCES edge(id) ON DELETE CASCADE,            -- an opinion edge…
    loadout_item   INTEGER REFERENCES loadout_item(id) ON DELETE CASCADE,    -- …or a loadout line…
    loadout_override INTEGER REFERENCES loadout_override(id) ON DELETE CASCADE, -- …or a per-boss override
    source_url     TEXT NOT NULL,                  -- permanent/oldid wiki revision URL
    source_license TEXT NOT NULL DEFAULT 'CC BY-NC-SA 3.0',
    source_title   TEXT,                           -- 'Scurrius/Strategies — OSRS Wiki'
    source_rev     TEXT,                            -- MediaWiki oldid: exact attribution + re-scrape diff key
    accessed_at    TEXT NOT NULL,                   -- ISO-8601 date
    origin         TEXT NOT NULL DEFAULT 'wiki' CHECK (origin IN ('wiki','author','community')),
    CHECK (edge_id IS NOT NULL OR loadout_item IS NOT NULL OR loadout_override IS NOT NULL)
);
CREATE INDEX ix_prov_edge     ON provenance(edge_id);
CREATE INDEX ix_prov_loadout  ON provenance(loadout_item);
CREATE INDEX ix_prov_override ON provenance(loadout_override);
```

- **Attribution is data-driven:** the UI renders a "Sources" credit by joining whatever provenance rows the displayed loadouts reference. Add a wiki-derived loadout → its attribution appears automatically.
- **`origin='author'`** rows are self-authored recommendations under your own license — the **monetization escape hatch**: NC only bites the `wiki` dataset; an author dataset sidesteps it. Schema supports it now; authoring a second dataset is deferred.

**Three concentric separability boundaries:**

1. **Storage** — opinion rows are identified by `edge_class='opinion'` + the `loadout_item`/`loadout_override`/`provenance` side tables. Cross-boundary references resolve *into* fact nodes one-way; integrity is checked at load by QA, so the opinion data is droppable. **Drop it → engine still loads/traverses/answers; only recommendations vanish.**
2. **Dataset/license file** — opinion tables serialize to a single distributable export (`data/opinion/*.jsonl` + `LICENSE` CC-BY-NC-SA-3.0 + `ATTRIBUTION.md` generated from `provenance`). Share-alike scope is contained to that directory; engine code stays MIT/Apache; fact data stays unencumbered.
3. **Swappable provider** — the engine consumes opinion only through `recommendations_for(target_id, style?, bracket?, account_state) -> [ranked loadouts]`. Swapping datasets = pointing the loader elsewhere; zero engine changes.

### Curated path orderings (seam reserved, mostly deferred)

Opinion over *ordering* is a thin overlay, never a mutation of the fact graph: `edge.weight` decorates `requires` edges (absent ⇒ default 1.0, traversal still works), and a deferred `op_path`/`op_path_step` pair holds named curated orderings that **must be a valid topological order of the REQUIRES projection** (a QA check) — so opinion can *order* but never *contradict* facts. Neutral graph is the source of truth; curated path is one optional layer the user can ignore.

---

## Storage

### Full v1-CORE DDL (consolidated)

```sql
PRAGMA foreign_keys = ON;   -- required per-connection in SQLite; always on in Postgres
-- ╔═══════════════════════════════════════════════════════════════════════╗
-- ║ GLOBAL STATIC GAME-DATA — shared by all accounts, versioned with game  ║
-- ║ updates, rebuilt by a pure pipeline. NO per-account column appears here.║
-- ╚═══════════════════════════════════════════════════════════════════════╝
-- node, item_attr, skill_attr, monster_attr      (Node model)
-- edge                                            (Edge model — grants.cond_group now allowed)
-- condition_group, condition_atom                 (Conditions)
-- loadout_item, loadout_override                  (Opinion layer)
-- provenance                                      (Opinion layer)

CREATE TABLE kg_meta (                            -- one row per build
    rev          TEXT PRIMARY KEY,                -- '2026.06.14+osrs-week-of-x'
    built_at     TEXT NOT NULL,
    game_version TEXT,
    source_notes TEXT
);
```

**Indexes (the ones traversal/QA actually hit):** `ix_node_kind`, `ix_node_game_id`, `ix_edge_type_src`, `ix_edge_type_dst`, `ix_edge_class`, `ix_edge_cond`, `ix_cg_parent`, `ix_atom_group`, `ix_atom_ref`, `ix_loadout_item`, `ix_loadout_override`, `ix_prov_edge`, `ix_prov_loadout`, `ix_prov_override`. All plain B-trees — portable SQLite↔Postgres as-is.

### NetworkX load sketch

Graph type: **`networkx.MultiDiGraph`** (directed; multi because two nodes can share several typed edges — an item is both `drops` and `recommended_for` the same boss). One in-memory graph holds all edge types; the `requires_dag` projection is the planning view (also a `MultiDiGraph`, parallels preserved). Conditions ride as a `cond_group` *id* only — the tree is hydrated by id for the handful of nodes on a candidate path.

```python
import json, sqlite3, networkx as nx

def load_kg(conn: sqlite3.Connection) -> nx.MultiDiGraph:
    conn.row_factory = sqlite3.Row
    g = nx.MultiDiGraph()
    for r in conn.execute("SELECT id, kind, name, slug, game_id, data FROM node"):
        g.add_node(r["id"], kind=r["kind"], name=r["name"], slug=r["slug"],
                   game_id=r["game_id"], **json.loads(r["data"]))
    # enrich the 3 engine-hot kinds from side tables in 3 bulk passes (not 15)
    for r in conn.execute("SELECT * FROM item_attr"):
        g.nodes[r["id"]].update({k: r[k] for k in r.keys() if k != "id"})
    for r in conn.execute("SELECT * FROM skill_attr"):
        g.nodes[r["id"]].update({k: r[k] for k in r.keys() if k != "id"})
    for r in conn.execute("SELECT * FROM monster_attr"):
        g.nodes[r["id"]].update({k: r[k] for k in r.keys() if k != "id"})
    for r in conn.execute(
        "SELECT id, type, edge_class, src, dst, cond_group, scope, qty, weight, data FROM edge"):
        g.add_edge(r["src"], r["dst"], key=f'{r["type"]}:{r["id"]}',
                   etype=r["type"], eclass=r["edge_class"], cond_group=r["cond_group"],
                   scope=json.loads(r["scope"]) if r["scope"] else None,
                   qty=r["qty"], weight=r["weight"], **json.loads(r["data"]))
    return g
```

Planning ops on `requires_dag(g)`: `nx.topological_sort`, `nx.descendants(dag, goal)` (full prereq closure), `nx.dag_longest_path` on a `weight`-decorated view (opinion influences ordering without entering the fact structure).

### Global-vs-per-account seam

Per-account data lives in a **physically separate schema/file** (Postgres schema `account_state`, or a separate SQLite file in dev). It references KG nodes **by string id, deliberately not a SQL FK** — so the two layers can be rebuilt/migrated independently and even live in different databases. Integrity is enforced at load by resolving `node_ref`s against the KG.

```sql
-- ╔═══════════════════════════════════════════════════════════════════════╗
-- ║ PER-ACCOUNT STATE — separate schema/file. Sketch of the seam only;     ║
-- ║ the full goal model is the feat/goal-tracker plan's job.               ║
-- ╚═══════════════════════════════════════════════════════════════════════╝
CREATE TABLE account (
    id           INTEGER PRIMARY KEY,
    account_hash TEXT UNIQUE,          -- RuneLite hash = ownership credential
    rsn          TEXT,
    account_type TEXT NOT NULL DEFAULT 'normal'
                 CHECK (account_type IN ('normal','ironman','hardcore_ironman',
                        'ultimate_ironman','group_ironman','hardcore_group_ironman'))  -- mirrors AccountMode
);

-- The overlay: current state keyed by KG node id (a string reference, not a SQL FK).
CREATE TABLE account_progress (
    account_id INTEGER NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    node_ref   TEXT NOT NULL,        -- 'skill:attack', 'quest:dragon-slayer-i', 'npc:7221'
    metric     TEXT NOT NULL,        -- 'level'|'xp'|'kc'|'qty'|'done'
    value      INTEGER,              -- level / xp / kc / qty-owned / 1=done
    updated_at TEXT,
    PRIMARY KEY (account_id, node_ref, metric)
);

CREATE TABLE goal (
    id         INTEGER PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES account(id) ON DELETE CASCADE,
    node_ref   TEXT NOT NULL,        -- the KG node the goal is about ('npc:7221','skill:slayer')
    metric     TEXT NOT NULL,
    target     INTEGER,              -- target level/kc/qty; NULL for boolean (quest/diary done)
    status     TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','done','paused')),
    created_at TEXT
);
CREATE INDEX ix_goal_account ON goal(account_id, status);
```

**The overlay operation:** load the KG once (shared across all requests/accounts); per account, fetch `account_progress` + `goal` into an `AccountState(mode, levels, xp, counts, done, combat_level)`; evaluate. *"Is node X unlocked?"* = walk its scoped `requires` edges and evaluate each `cond_group` against the state. *Unlocked* = every in-scope `requires` edge satisfied; *next* = unlocked-or-one-step-away nodes not yet done. No account data ever touches the KG tables.

### SQLite → Postgres portability & id-stability

| Concern | SQLite (dev) | Postgres (hosted) |
|---|---|---|
| JSON | `TEXT` + JSON1 (`json_valid`, `json_extract`) | `jsonb` (access via `->>`); keep all JSON access behind one helper |
| Surrogate PK | `INTEGER PRIMARY KEY` | `BIGINT GENERATED ALWAYS AS IDENTITY` |
| Enums | `CHECK ... IN (...)` | same, or promote to native `ENUM`/domain |
| Booleans | `0/1` int | real `boolean` (normalize in loader) |
| Cascade | needs `PRAGMA foreign_keys=ON` | always enforced |

**Refresh = full rebuild + atomic swap, never in-place mutation.** Regenerate the static tables into a new schema/file, run QA invariants, then swap. Because the static layer holds no per-account data, the swap cannot lose user state. Stamp every build with a `kg_rev` (recorded in `kg_meta`, stamped onto `node.source_rev`/`edge.source_rev`). IDs stay stable across rebuilds so account `node_ref`s never dangle.

---

## QA invariants

Every check has a **severity** (`FAIL` blocks the atomic swap; `WARN` surfaces in a coverage report but ships; `FAIL*` = FAIL in CI, downgradable to WARN locally via `--draft`), and runs against a freshly built candidate DB *before* swap. The dividing rule: **"would a user get a wrong or broken answer?" → FAIL; "is the catalog incomplete here?" → WARN.** `verify`-marked data is designed to pass all FAIL checks (structural validity is value-independent), so a half-verified KG still ships.

### Invariant table

| # | Invariant | Statement | Why | How-checked | Sev |
|---|---|---|---|---|---|
| **I1** | Acyclic REQUIRES | The `requires` + synthetic (`grants`-flip + ref-bearing cond-leaf) projection is a DAG; report **all** simple cycles (capped) | Planner does `topological_sort`/`descendants`; a cycle = infinite loop / unsatisfiable goal | NetworkX `is_directed_acyclic_graph` on the cycle-augmented graph | **FAIL** |
| **I2** | Edge endpoint integrity | Every `edge.src`/`edge.dst` resolves to a `node.id` | Dangling edge crashes loader / silently drops a path | SQL `LEFT JOIN ... IS NULL` | **FAIL** |
| **I3** | Edge type legality | Each edge type's endpoints match the allowed-`kind` matrix | A `drops` from a Quest is meaningless data | SQL vs data-driven `_qa_edge_typing` | **FAIL\*** |
| **I4** | dst-nullability | `dst IS NULL` only where a pure-condition edge is allowed (`requires`, and conditional `grants`) | Null `dst` on `drops` is a load-time NPE | SQL | **FAIL** |
| **I5** | Condition tree well-formed | Single root; `NOT`⇒1 child; `AND`/`OR`⇒≥1 child; no orphan atoms; no `parent` cycles | Malformed tree makes `evaluate` raise / return garbage | SQL child-counts + NetworkX parent-acyclicity | **FAIL** |
| **I6** | Condition ref typing | Every `condition_atom.ref_node` resolves to a node of the kind its `atom_type` implies | A `skill_level` atom on a quest is silently never satisfied → goal looks permanently locked | SQL vs `atom_type→kind` map | **FAIL** |
| **I7** | Threshold sanity | `threshold`/`qty` in-range per atom type (skill 1–max_level, qp 0–~350, kc/qty ≥1) | Out-of-range = unsatisfiable / trivially-true reqs (a missing threshold on a `requires` atom silently never-satisfies — worse than out-of-range; aligns with pipeline §7) | SQL (joins `skill_attr.max_level`) | **FAIL\*** range / **FAIL** missing |
| **I8** | Provenance completeness | Every `edge_class='opinion'` edge AND every `loadout_item` AND every `loadout_override` has ≥1 `provenance` row with non-null url/license/accessed_at | CC BY-NC-SA attribution is data-driven; a missing source = a licensing defect shipped | SQL `NOT EXISTS` | **FAIL** |
| **I9** | Edge-class coherence | `(type='recommended_for') = (edge_class='opinion')` | The licensing seam: a fact mislabeled opinion breaks separability | DB CHECK | **FAIL** |
| **I10** | ID format & uniqueness | `id` matches `<prefix>:<key>`; prefix legal for `kind`; `UNIQUE(kind,slug)`; canonical kinds carry `game_id` and `id = prefix:game_id` | IDs are the cross-layer contract; malformed/dup id dangles account refs | SQL vs `_qa_id_prefix` + DB UNIQUE | **FAIL** |
| **I11** | ID stability | No id present in the prior shipped `kg_meta` rev disappeared without a `node_alias` row | A vanished id orphans every account goal referencing it — the single most important user-trust invariant | SQL diff vs `_prev_node_ids` | **FAIL** (no-alias) / **WARN** (alias'd) |
| **I12** | Scope grammar | Every `edge.scope` is null or exactly one of `{modes}`/`{not_modes}` with values ∈ AccountMode | An unknown mode silently mis-scopes an edge | Python at load | **FAIL** |
| **I13** | Side-table 1:1 | Every `item_attr`/`skill_attr`/`monster_attr` row matches a `node` of the right kind, and vice-versa | A skill without `skill_attr` has no `hiscore_index` → state can't map it | SQL full-outer presence | **FAIL** |
| **I14** | Opinion→fact one-way | `loadout_item.item_node`, `loadout_override.item_node`, `recommended_for.src/dst` resolve into fact nodes; no fact edge references an opinion-only node | Directionality keeps facts unencumbered/separable | SQL | **FAIL** |
| **I15** | Drops excluded from DAG | No `drops`/`located_in`/`gated_by` edge leaks into `requires_dag` | A boss "requiring" its own drop = false/cyclic prereq | Asserted in the projection | **FAIL** |
| **I16** | Grant-OR not conjoined | No `access` node is the `dst` of >1 unconditional `grants` edge from distinct producers that the projection would treat as AND (alternatives must be modeled as an `OR` `cond_group` on the requirer, or as conditional grants) | The MUST-FIX #2 regression guard: prevents alternative grant sources collapsing into a false AND prereq | NetworkX: flag any `access` with ≥2 unconditional inbound grants for author review | **WARN** |
| **I17** | Enum domain | `kind`,`type`,`edge_class`,`op`,`atom_type`,`slot`,`account_type` ∈ closed sets | Typos ("mage" vs "magic") fragment data invisibly | DB CHECK | **FAIL** |
| **I18** | access-vs-gear typing | An `access:*` node whose grant/composition is dominated by `item` atoms resolving to *equippable* items (present in `items_equipment`) should be a `gear_loadout` — and a `gear_loadout` granted only by quest/diary should be an `access` | A worn set mis-tagged as a permanent unlock collapses its variants/tiers/partial-progress into a binary (the Void class) — and gear is losable while `access` is `done`-permanent | join composition `item` ref_nodes vs `items_equipment` (equip slot present) | **FAIL** |

### Completeness checks (coverage — measured, mostly WARN)

Completeness is **measured, not gated** — each check emits `(check_id, total, passing, ratio, failing_ids[])`, written to a diffable `coverage.json` + human `coverage.md`. A curated **core content set** (`qa/core_set.yaml`, initially the Scurrius worked example end-to-end + the account-type acquisition demo) **promotes** the listed WARNs to FAIL, so the flagship path can't silently rot while the catalog is 5% authored.

| # | Check | Rule | Sev |
|---|---|---|---|
| C1 | Boss locatability | every `is_boss=1` has ≥1 `located_in` or `gated_by` | WARN (FAIL core) |
| C2 | Boss access | every boss has an inbound prereq story (`requires` or unlocked region) | WARN |
| C3 | Quest reqs present | every `quest` has ≥1 `requires` or `data.no_requirements=true` | WARN |
| C4 | Quest grants | every `quest` has ≥1 `grants` | WARN |
| C5 | Loadout slot coverage | every `gear_loadout` fills its style's required slots | WARN (FAIL core) |
| C6 | Rank density | per (loadout, slot) `rank` starts at 1, gap-free | WARN |
| C7 | Rec reachability | every `recommended_for` target is a real reachable node | WARN→FAIL |
| C8 | Consumable presence | every combat loadout has ≥1 `inv:food` | WARN |
| C9 | Drop coverage | every `has_collection_log=1` boss has ≥1 `drops` | WARN |
| C10 | Orphan nodes | degree-0 nodes (authoring stubs) | WARN |
| C11 | Verify-debt | count of `verify`-marked rows, trended | WARN (trend) |
| C12 | Iron acquirability | every boss whose gear includes a non-buyable item has *some* acquisition route (drop/shop/quest/skilling) for irons | WARN |
| C13 | RDT linkage | every monster with `Rolls>1` or a known RDT flag has explicit RDT linkage (`access:rolls-rare-drop-table`) or a `verify` marker | WARN (FAIL core) |
| C14 | Source symmetry | reconcile-eligible kinds (`monster`,`item`) have both expected sources present or a `verify` marker | WARN |

### Where validation runs

Four stages, by cost and locality; the **atomic swap waits on the build-gate**:

1. **Ingest (per row):** DB `CHECK`/`UNIQUE`/`FK` (I2, I4, I9, I10-unique, I17) + pydantic loader (edge-prop typing, scope grammar I12, atom shape). Fails the author's row at the source with the clearest message.
2. **Build-gate (whole-graph, authoritative):** everything needing the assembled graph — I1, I3, I5–I8, I11, I13–I16, plus all completeness checks. The swap promotes the candidate only if every FAIL-severity check is clean. Output: one `qa_report.json` `{fails, warns, coverage}`.
3. **CI (merge gate):** stages 1+2 on every `data/` PR, **plus** coverage-regression (a ratio drop >X% vs last shipped build → soft-FAIL) and core-set promotion. `--draft` downgrades are **not** honored in CI.
4. **Runtime smoke (post-deploy):** `is_directed_acyclic_graph(requires_dag)` once at startup, node/edge counts within ±Y% of `kg_meta`, and a canned "resolve Scurrius for a fresh ironman returns a non-empty plan." On failure the loader keeps the previous graph (fail-safe — the static layer is swappable).

**Update triggers:** a **game update** (new `game_version`) rebuilds and leans on **I11** (id-stability) + falling coverage as the authoring to-do list; a **wiki update** (changed `oldid`) rebuilds only the affected **opinion** subgraph and re-runs I8/I14/C5–C8 — because opinion is separable, a re-scrape **cannot** break fact invariants (an explicit blast-radius guarantee). A nightly job re-runs the full gate against latest game-version + wiki-hash and opens an issue on any FAIL or coverage regression.

**Rules-as-data:** the QA matrices live in tables/files (`_qa_edge_typing`, `_qa_required_slots`, `_qa_id_prefix`, `core_set.yaml`) — auditable, reviewable in PRs, editable without touching check code. The runner is generic.

---

## Worked example — Scurrius

Every row below is a legal instance of the v1-CORE DDL. Uncertain real-world values carry `verify`.

> **Correction (2026-06-14, live recon — see [`data-pipeline-v1.md`](data-pipeline-v1.md) §10).** This
> example originally used **fabricated** ids, caught by querying the live wiki: `npc:7223` is actually a
> *Giant rat*, and `combat_level 408` + the glory id `1712` were wrong. Corrected below to the real
> values — **`npc:7221`** (canonical Scurrius, **combat 250**); a group variant **`npc:7222`** (combat
> 200) also exists and is minted as a sibling node by the pipeline (kept out of this example for
> brevity); amulet of glory base is **`item:1704`** (`1712` is a charge variant). These corrections are
> the prototype's blind mutation-test canary.

### Nodes

```json
[
  { "id": "npc:7221", "kind": "monster", "name": "Scurrius", "slug": "scurrius",
    "game_id": 7221, "data": {}, "verify": null },
  { "id": "region:scurrius-lair", "kind": "region", "name": "Scurrius's Lair (instance)",
    "slug": "scurrius-lair", "data": { "instanced": true },
    "verify": "verify vs wiki later: exact entrance mechanic" },
  { "id": "region:varrock-sewers", "kind": "region", "name": "Varrock Sewers",
    "slug": "varrock-sewers", "data": {} },
  { "id": "access:scurrius-lair", "kind": "access", "name": "Scurrius Lair Access",
    "slug": "scurrius-lair", "data": { "note": "ability to enter the Scurrius fight instance" } },
  { "id": "gear_loadout:void", "kind": "gear_loadout", "name": "Full Void Knight", "slug": "void",
    "data": { "styles": ["melee", "ranged", "magic"] } },
  { "id": "account:normal",  "kind": "account_type", "name": "Normal", "slug": "normal",
    "data": { "must_self_acquire": false, "can_ge": true } },
  { "id": "account:ironman", "kind": "account_type", "name": "Ironman", "slug": "ironman",
    "data": { "must_self_acquire": true, "can_ge": false } },
  { "id": "loadout:melee:mid",  "kind": "gear_loadout", "name": "Melee (mid-level)",
    "slug": "melee:mid",  "data": { "style": "melee",  "bracket": "mid" } },
  { "id": "loadout:ranged:mid", "kind": "gear_loadout", "name": "Ranged (mid-level)",
    "slug": "ranged:mid", "data": { "style": "ranged", "bracket": "mid" } },
  { "id": "activity:fight-caves", "kind": "activity", "name": "Fight Caves", "slug": "fight-caves",
    "data": { "activity_kind": "minigame" } }
]
```

`monster_attr`: `npc:7221` → `is_boss=1`, `combat_level=250`, `hiscore_index=(verify)`, `has_combat_achievements=1`, `has_collection_log=1`. Scurrius **does** have CAs (e.g. "Smashing the Rat") and a collection log.

**Generic, reusable loadouts.** `loadout:melee:mid` / `loadout:ranged:mid` are the generic mid tables — the same nodes are `RECOMMENDED_FOR` many bosses. Scurrius's per-boss tailoring rides on `loadout_override`, **not** a forked loadout (the MUST-FIX #3 win in action).

### Fact prerequisites to fight Scurrius

Scurrius is a deliberately low-barrier first boss: no quest, no hard stat gate. The only hard prerequisite is lair access, granted by reaching the sewers.

```json
[
  { "id": 9001, "type": "located_in", "edge_class": "fact", "src": "npc:7221",
    "dst": "region:scurrius-lair", "cond_group": null },
  { "id": 9002, "type": "gated_by", "edge_class": "fact", "src": "region:scurrius-lair",
    "dst": "access:scurrius-lair", "cond_group": null },
  { "id": 9003, "type": "grants", "edge_class": "fact", "src": "region:varrock-sewers",
    "dst": "access:scurrius-lair", "cond_group": null,
    "verify": "verify vs wiki later: any agility/wrench gate?" },
  { "id": 9004, "type": "requires", "edge_class": "fact", "src": "npc:7221",
    "dst": "access:scurrius-lair", "cond_group": null }
]
```

`descendants(requires_dag, "npc:7221") ≈ {access:scurrius-lair}` — correctly trivial for this boss. Ironman vs main: **identical** for access (no item to acquire). The account-type axis is inert here; it fires only in the gear subgraph below.

### Gear-loadout composition — what makes `gear_loadout:void` satisfied

A `gear_loadout:*` node carries its **item-composition** directly: a `requires` edge with `dst=NULL` whose `cond_group` is the AND-of-slots tree ("the constraint *is* the tree"). No minted producer activity and no `grants` to an access node — the loadout is owned (or not), evaluated against current items.

```json
[
  { "id": 9100, "type": "requires", "edge_class": "fact", "src": "gear_loadout:void",
    "dst": null, "cond_group": 10 }
]
```

with `cond_group 10 = AND( OR(item item:11663, item item:11664, item item:11665), item item:8839, item item:8840, item item:8842 )` (any one of the three Void helms AND top AND robe AND gloves). No false single-piece OR (MUST-FIX #1). (Conditional `grants` still serve **genuine** `access:*` unlocks gated by a conjunction — e.g. quest AND skill — but full Void is a worn set, so it lives as a loadout composition, not a grant.)

### Opinion — RECOMMENDED_FOR + a per-boss override

```json
[
  { "id": 9101, "type": "recommended_for", "edge_class": "opinion", "src": "loadout:ranged:mid",
    "dst": "npc:7221", "cond_group": null, "weight": 1.0,
    "data": { "style": "ranged", "bracket": "mid", "rank": 1,
              "note": "ranged preferred vs the rat-king mechanic" },
    "verify": "verify vs wiki later: confirm wiki ranks ranged above melee" },
  { "id": 9102, "type": "recommended_for", "edge_class": "opinion", "src": "loadout:melee:mid",
    "dst": "npc:7221", "cond_group": null, "weight": 2.0,
    "data": { "style": "melee", "bracket": "mid", "rank": 2 } }
]
```

A `loadout_item` row in the **generic** `loadout:melee:mid` (reused across bosses):

| id | loadout | item_node | slot | style | bracket | rank | cond_group |
|---|---|---|---|---|---|---|---|
| 4 | `loadout:melee:mid` | `item:4587` Dragon scimitar | weapon | melee | mid | 1 | NULL |
| 12 | `loadout:melee:mid` | `item:11665` Void melee helm | head | melee | mid | 3 | **50** |

with `cond_group 50 = AND( gear_loadout gear_loadout:void )` — the loadout-wide "only with full Void" footnote, cross-referencing the `gear_loadout` set-composition node above.

**Scurrius-specific neck swap, without forking the shared loadout** (MUST-FIX #3):

```json
[
  { "id": 1, "rec_edge": 9102, "slot": "neck", "item_node": "item:1704",
    "rank": 1, "cond_group": null, "data": { "note": "Scurrius wants amulet of glory in neck" } }
]
```

`resolved_loadout(9102)` = the generic `loadout:melee:mid` rows, with the `neck` slot overridden for Scurrius only.

**Consumables** (non-slot `slot`, style-tagged): `inv:food` Shark ×8 `(verify)`, `inv:potion` Super combat ×1 (`style=melee`), `inv:potion` Ranging ×1 (`style=ranged`), `inv:teleport` Varrock teleport ×1, `inv:rune` Rune pouch ×1.

**Provenance** (data-driven CC BY-NC-SA): one row per opinion edge + per `loadout_item` + per `loadout_override`, all pointing at `https://oldschool.runescape.wiki/w/Scurrius/Strategies?oldid=<rev>` with `source_license='CC BY-NC-SA 3.0'`, `accessed_at='2026-06-14'`, `origin='wiki'` (`oldid` to verify).

**Separability check passes:** delete every `edge_class='opinion'` row + `loadout_item` + `loadout_override` + `provenance` → the engine still loads `npc:7221`, its access/region facts, and answers "is Scurrius unlocked?" It only loses gear recommendations.

### The goal: "Scurrius 100 KC" resolved for an ironman

State (separate layer): account `ironman`; goal `node_ref=npc:7221, metric=kc, target=100`; progress `kc=0`, `attack=70`, `strength=65`, `access:scurrius-lair` not done, `gear_loadout:void` not owned (evaluated from current items, not the `done` set).

1. **Fact gate:** `requires npc:7221 → access:scurrius-lair` (unconditional); `access:scurrius-lair` granted free by Varrock Sewers ⇒ **gate OPEN**, identical for main/iron.
2. **Goal target is a count:** unlocked ✓ + `kc (0) >= 100` ✗ ⇒ goal **active, 0/100**. "Next: Scurrius is unlocked — kill it 100 times."
3. **Opinion overlay (account-type-aware):** `recommendations_for("npc:7221", iron)` ranks ranged-mid (weight 1.0) above melee-mid (2.0); resolves the per-boss override; for each item runs `expand_need_item`. For the **ironman**, a non-buyable piece like the Fire cape expands via its acquisition method into `activity:fight-caves` completion — a sub-goal with its own prereqs — a genuinely larger required subgraph from the same global data. A **main**'s same leaves terminate at gp goals. This is the account-type differentiator firing correctly.

---

## Open questions (deferred past v1)

| Deferred | Why safe to defer | Trigger to revisit |
|---|---|---|
| Non-core node kinds as *data* (`minigame`, `spellbook`, `spell`, `clog_slot`) | Enum + ID prefixes reserved; no DDL change needed | When authoring that content |
| Side-table promotion for a deferred kind | Hybrid spine makes it an additive migration | When the engine hot-filters that kind's fields |
| `node_alias(old_id, new_id)` rename machinery | IDs are designed immutable; renames rare | First unavoidable rename |
| Comparator field (`cmp`) on thresholds | OSRS prereqs only ever use `>=` | If a `<` requirement ever appears |
| Deeper condition nesting beyond 2–3 levels | Two-level AND-of-ORs covers all real v1 reqs | A real requirement needing deeper trees |
| `clue_scrolls` cardinality atom (N-of-M over a named set) | Subquest structure is deferred; headline set-gated items need the FULL quest (a `quest` atom with `data.state = completed`) which works today | When intermediate-tier / subquest acquisition routes are authored |
| `combat_achievement_points` accumulator atom + `combat_achievement` de-overload | Per-task `combat_achievement` ships; tier-reward gating is post-v1 content | When CA tier-reward unlocks are authored (needs STATE layer) |
| Acquisition `cost{currency, amount}` (shop/alt-currency) | Static display KG needs no costs; structural QA passes without them | HARD when the planner makes per-mode effort/cost estimates (the moat) |
| `item_set` sugar node (full Void / Inquisitor's / blood moon) | A `gear_loadout` node + its composition `cond_group` (AND-of-slots, helm-OR) express set ownership now; sugar is ergonomics, not capability | When many sets make hand-wiring `gear_loadout` compositions tedious |
| Drop-table-as-unit + roll structure ("rolls main table 3×, unique 1×") | `DROPS` handles single lines; v1 only needs uniques/clog | When a loot-tracker feature needs per-roll math |
| First-class `clog_slot` edges (vs `clog.data` JSON) | Clog membership not yet traversed as edges | When a clog tracker queries membership |
| Soft/advisory stat guidance ("suggested combat, prefer ranged") | Neither a hard `requires` nor gear; lives as a note for now | When advisory UI is built (candidate: an `advisory` edge type) |
| Consumable quantity scaling with trip length / KC-per-trip | `qty` is static; fine for display | When "supplies for N KC" planning is needed |
| `style` overload on shared consumables | Works because v1 loadouts are mostly per-style; ambiguous only under heavy reuse | When a shared consumable must mean "this style only" precisely |
| GIM/HCGIM buy-from-teammate; UIM no-bank scope nuances | v1 treats group irons like solo irons; UIM edge cases flagged `verify` | When group/UIM accuracy matters |
| Curated path weights (`edge.weight`) + path templates (`op_path`/`op_path_step`) | `weight` defaults 1.0; the consuming planner is the engine brick | When the planner does weighted ordering |
| Swappable `origin='author'` opinion dataset | Schema + narrow interface support it now | When monetization/own-license recs are authored |
| GE price storage | Volatile; belongs in the ingest layer | Never in the KG; ingest caches it |
| Native Postgres `ENUM` / `jsonb` GIN indexes | Plain B-trees + CHECKs portable and sufficient at this scale | Only if profiling demands |
| Per-account loadout overrides (user edits a recommended loadout) | That's the state layer, not the opinion KG | The goal-tracker plan |

> **Note (scale amendment).** The load-bearing claim "depth≤3 / two-level AND-of-ORs covers all real reqs" is AMENDED to: "covers all single-scalar and set-cardinality reqs via {the `quest` atom's `state` field, `clue_scrolls`, `combat_achievement_points`}; deeper/stage/accumulator structure via those atoms." The `quest` atom's 3-state `state` field (not_started/in_progress/completed) is now IN v1-CORE and models partial completion (it resolves the pipeline-emits-`in_progress`-vs-enum-rejects contradiction). See research/scale-gaps.md.
