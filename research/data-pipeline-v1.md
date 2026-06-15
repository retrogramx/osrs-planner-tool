# Data pipeline v1 (scratch — NOT a decision)

> Working draft for the eventual ingest + QA bricks. **Non-binding**; nothing here is locked.
> Companions: knowledge-graph.md, kg-schema-v1.md (the KG it loads into), and
> data-correctness-and-advisor.md (the validation philosophy + the verified Bucket/cache recon).
> Real decisions move into a plan/ADR.

**Determinism-first ETL** that moves validated OSRS data from the Weird Gloop **Bucket** API + the game **cache** into the v1 KG. The deterministic spine does the work; one narrow LLM normalizes the fuzzy residual behind a hard validation gate; a full-rebuild → QA-gate → atomic-swap guarantees a reproducible, drift-detectable static graph. `verify`-marked data is engineered to pass every FAIL invariant (structural validity is value-independent), so a half-verified KG still ships.

> **Live-recon corrections already baked into this draft** (do not relitigate; carry into `kg-schema-v1.md` and `qa/core_set.yaml` before authoring):
> - Scurrius is **`npc:7221`** (combat 250, solo/canonical) + **`npc:7222`** (combat 200, group/variant). The schema's worked example `npc:7223 / combat_level=408` is **fabricated** (`7223`=Giant rat) — it is the canary the prototype must flag, not a fact.
> - Amulet of glory base item is **`item:1704`** (not `1712`, a charge variant). Live `infobox_item.where('item_name','Amulet of glory')` returns **three** rows: `["1704"]`, `["20586"]` (a different charge variant), and `["interface8283"]` with case-variant name `'Amulet of Glory'` (an interface sprite, **not** a real item). Non-numeric and multi-numeric ids are real and live.
> - Bucket `.join()` works live (used for item×bonuses slot). Drops are filterable **only** by `page_name` (`.where('Rarity',…)` / `.where('Dropped item',…)` return a hard `error:"Field X not found in bucket dropsline"`, not empty). RDT/Gem-DT items **do not appear as `dropsline` rows at all** — a coverage hole, not a parse problem.
> - Rarity grammar and the drop-variant suffix space are **open sets** (live: `1/26.9` decimal denominator; `Vorkath#Post-quest`; undocumented `Alt Rarity`/`Approx` keys; `'5–15 (noted)'` en-dash quantity). Classify by regex + quarantine-with-verify; never enumerate.
> - Quest `requirements` is one HTML string whose `scp` spans include `data-skill="Quest points"` (route to `qp_at_least`, **not** a `skill_level` FK that fails I6).

---

## 1. Overview & stage DAG

Nine content-addressed stages. The build is a **pure function of `(wiki_oldids_sha, openrs2_build_id, extractor_sha)`** → byte-identical candidate DB (modulo `built_at`). Only S6→S7→S8 is a hard sequential spine; everything upstream parallelizes by entity type or by host.

```
S0 Pin ──► S1 Fetch-wiki (Bucket + raw wikitext, serialized, maxlag) ─┐
           S2 Fetch-cache (OpenRS2/RuneLite, different host) ─────────┼─► S3 Extract (deterministic, ∥ by type)
                                                                       │      │
                                                                       │      ▼
                                                                       │   S4 Reconcile (Bucket ⊕ cache, per-field policy)
                                                                       │      │
                                                                       │      ▼
                                                                       │   S5 Tier-3 normalize (LLM, narrow, behind FK + judge gate)
                                                                       │      │
                                                                       ▼      ▼
                                                                   S6 Transform → kg_candidate.sqlite
                                                                          │
                                                                          ▼
                                                                   S7 QA gate (I1–I17 + C1–C14 + golden + mutation + drift)
                                                                          │  zero FAIL
                                                                          ▼
                                                                   S8 Atomic swap (+ kg_meta stamp, prev kept for rollback / I11)
```

| # | Stage | Output artifact | LLM | Parallel |
|---|---|---|---|---|
| S0 | Pin | `build_manifest.json` `{(page→oldid) + (transcluded template/module→oldid), openrs2_build_id, extractor_sha, accessed_at}` | No | 1 cheap pass |
| S1 | Fetch-wiki | raw Bucket JSON snapshots (content-hashed) + pinned raw wikitext | No | serialized (one host, `maxlag=5`) |
| S2 | Fetch-cache | `ItemDefinition`/`NpcDefinition` dumps @ pinned build | No | ∥ to S1 (different host) |
| S3 | Extract | typed `Staged*` records (Tier 1+2) | No | ∥ by entity type |
| S4 | Reconcile | reconciled `recon_record` rows + `recon_report.json` | No | ∥ by type |
| S5 | Tier-3 | cond trees + split/ambiguous loadout lines (FK + judge gated) | **Yes (narrow)** | ∥ per unit, Batches API |
| S6 | Transform | `kg_candidate.sqlite` (nodes/edges/cond/loadout/prov) | No | sequential (id mint) |
| S7 | QA gate | `qa_report.json` `{fails, warns, coverage, golden, mutation}` | No | ∥ checks, one verdict |
| S8 | Swap | promoted DB + `kg_meta` row | No | n/a |

**Full rebuild** (default; game update) runs all stages. **Opinion-only incremental** (a `/Strategies` oldid moved) re-runs S1(page)→S3→S5→S6(opinion rows only)→S7 *restricted to I8/I14/C5–C8 + X3–X6*→S8, reusing prior fact tables untouched — so an opinion re-scrape **structurally cannot fail a fact invariant** (I1–I7, I15).

---

## 2. Source adapters

All extraction emits typed `Staged*` pydantic models (never direct DB writes), carrying **natural keys** (`item:name`, `npc#variant`) resolved to `node.id` only at load — so an unresolvable key is a dropped-and-flagged row **uniformly** for deterministic *and* LLM rows (FK = the universal hallucination catch).

```python
class SourceRef(BaseModel):
    source: Literal["bucket", "cache", "wikitext"]
    locator: str                 # bucket name | openrs2 build id | page title
    rev: str | None = None       # MediaWiki oldid | OpenRS2 build id | bucket-snapshot content hash
    url: str | None = None
    accessed_at: str

class StagedRow(BaseModel):
    ...
    quarantined: bool = False
    verify: str | None = None
    @classmethod
    def quarantine(cls, *, reason: str, raw: dict, src: SourceRef) -> "StagedRow":
        return cls(quarantined=True, verify=f"quarantine:{reason}", data={"raw": raw}, src=src)
```

### 2.1 Bucket client (`action=bucket`) — **v1-CORE**

Builds the Lua chain, fires one serialized GET, parses `{bucketQuery, bucket[], error}`, **asserts `error is None`** (a bad field name returns a top-level `error`, not an empty list), then normalizes quirks.

```python
WIKI_API = "https://oldschool.runescape.wiki/api.php"
UA = "GildedTome/0.1 datapipeline (contact: aalvarez0295@gmail.com)"

def to_lua(q) -> str:   # bucket('X').select('a','b').where('f','=','v').join(...).limit(n).offset(k).run()
    ...

def coerce_gid(raw) -> str:
    """Total. raw may be ["1704"], "1704", or ["interface8283"]. Never int()-crashes."""
    v = raw[0] if isinstance(raw, list) and len(raw) == 1 else raw
    if not (isinstance(v, str) and v.isdigit()):
        raise NonNumericId(raw)        # caller quarantines: reason='non_numeric_id'
    return v
```

| Quirk (verified) | Handling |
|---|---|
| ids return as **string arrays** `["7221"]` | `_norm_row` collapses len-1 lists; `coerce_gid` casts; **len≠1 ⇒ multi-id page → raise/flag, never silently pick** |
| ids can be **non-numeric** (`["interface8283"]`) | `coerce_gid` regex-guards `^[0-9]+$`; non-numeric ⇒ `StagedRow.quarantine(reason='non_numeric_id')` + `verify`, never `int()`-crash |
| Bucket **omits null/false** | `row.get(f)` → `None`; known-bool missing key ⇒ `False`, never "unknown" |
| booleans also come back as `""` | empty-string coerced to `False` alongside missing |
| ops **top-level cols only**; no LIKE/regex/JSON-subkey | builder rejects unsupported ops **and validates field names against a per-bucket column catalog** (probe once); JSON-blob filtering is client-side |
| bad field name ⇒ hard `error` | `assert resp["error"] is None`; never proceed on an empty `bucket[]` that accompanied an error |
| `.join()` **VERIFIED live (n=1)** | used for item×bonuses slot (`infobox_item.join('infobox_bonuses', page_name)`); **cross-checked against an independent `infobox_bonuses` fetch-all count at scale** (mismatch ⇒ client-merge fallback + WARN) |
| server `groupBy` **absent** | monster→drops group-by stays client-side |
| bulk/pagination caps **unknown** | `orderBy`-keyset paging as **primary**, `limit/offset` as fallback; stop-on-short-page; **tripwire vs known sizes** (`infobox_monster≈3210`, `infobox_item≈16316`, `dropsline≈38707`) is a **FAIL** if `<0.95×known_count` (silent truncation is worse than a crash) |

Politeness: serialized requests, `maxlag=5`, descriptive UA, inter-call pause, back off on `maxlag` errors. No published hard rate limit.

### 2.2 Cache client (OpenRS2 + RuneLite) — **v1-CORE**

`pick_build()` reads `archive.openrs2.org/caches.json`, filters `game=='oldschool'`, picks newest (or explicit), and **pins `openrs2_build_id` into `kg_meta`** (live: build_id **2593**, build **238**). Consumes RuneLite (BSD-2) `ItemDefinition(id, name, members, tradeable, cost, stackable, weight, notedID)` and `NpcDefinition(id, name, size, combatLevel)`. **`wearPos`→slot is deliberately NOT trusted** for the slot value — slot comes from the wiki — but the `wearPos→slot` map is built once, hand-verified on the golden anchors, and used **purely as a disagreement tripwire** against the wiki slot (a free second opinion, see X8/S1).

### 2.3 Raw-wikitext + revision pinning — **v1-CORE**

`fetch(title, oldid=None)`: with `oldid` → `action=parse&oldid=…&prop=wikitext` (reproducible re-extract); without → `action=query&prop=revisions&rvslots=main&rvprop=ids|timestamp|content` capturing current `revid`+timestamp. **Also enumerate transclusions** (`action=parse&prop=templates`) and pin each templated/`Module:` source — because most structured data is template-derived, and a fact can drift via a transcluded module whose oldid you never pinned (S2/drift). `PinnedPage.oldid` → `provenance.source_rev` and the drift key; `.url` = `…/w/PAGE?oldid=<revid>`. (Live: `Scurrius/Strategies` pageid 413365, revid **15164664**.)

> **Drift anchors, two kinds** (S2): wikitext fields drift-detect via **oldid**; Bucket fields have **no oldid** (a Bucket row is the current materialized table) → drift-detect via a **stored content-hash of the Bucket response snapshot**, diffed on the next snapshot.

---

## 3. Extraction per entity type

| KG target | Field | Source — exact | Adapter | Tier |
|---|---|---|---|---|
| `monster_attr` | combat_level | `infobox_monster.combat_level` ⊕ `NpcDefinition.combatLevel` | bucket+cache | 1 |
| `monster_attr` | is_boss / has_CA / has_clog / hiscore_index | curated lists / Hiscores `index_lite` map (§enrichers) | enricher | 1 |
| node(monster) data | hp, max_hit, levels, speed, size, slayer_* | `infobox_monster.*` | bucket | 1 |
| `item_attr` | **slot** | `infobox_bonuses.equipment_slot` (**wiki**, cache `wearPos` = tripwire only) | bucket | 1 |
| `item_attr` | tradeable / members | `infobox_item.tradeable/is_members_only` ⊕ `ItemDefinition` | bucket+cache | 1 |
| `item_attr` | stackable | `ItemDefinition.stackable` | cache | 1 |
| `item_attr` | buyable_ge | `infobox_item.buy_limit` present ∧ tradeable (heuristic, `verify`) | bucket | 1 (derived) |
| node(item) data | bonuses, combat_style, atk_speed | `infobox_bonuses.*` | bucket | 1 |
| node(item) data | examine, value, high_alch, weight, buy_limit | `infobox_item.*` | bucket | 1 |
| edge `drops` | rarity→weight, qty, rolls, variant | `dropsline.drop_json` (client group-by, **open schema**) | bucket | 1 |
| edge `drops` (RDT) | RDT/Gem-DT linkage | **separate** RDT/Gem-DT page dropsline / `Module:DropTable` | bucket+wikitext | 1 |
| edge `requires` (quest→skill) | threshold | `<span class="scp" data-skill data-level>` via **dispatch table** | wikitext | 1 |
| quest prereq/items/conditional | (prose) | `quest.*` + req-section wikitext → Tier-3 | bucket+wikitext | 3 |
| `loadout_item` | slot, rank, item, style, bracket | `{{Recommended equipment}}` raw template | wikitext | 2 |
| `loadout_item.cond_group` | (footnote) | `{{efn}}` text → Tier-3 predicate (position-bound) | wikitext | 3 |

**The item×bonuses join (resolved).** Use the **verified Bucket `.join()`** — `infobox_item.join('infobox_bonuses', page_name).select(...item fields..., equipment_slot, stab_attack_bonus, …, combat_style, weapon_attack_speed)` in one server-side call, cross-checked against the wikitext slot param when a loadout references the item. At scale, validate the join's row count against an independent `infobox_bonuses` fetch-all (multi-bonus-row pages can fan out / cap); on mismatch, fall back to the retained client-merge and WARN. **Group rows by canonical `item_id` and assert exactly one NUMERIC id per resolved node**; `>1` numeric id sharing a name (glory `1704` vs `20586`) ⇒ name-match disabled, force id-based resolution + `verify` (the recon's "never resolve gear by name" rule made executable).

**Drops extraction (resolved).** Targeted/incremental: `dropsline.where('page_name', M).select('page_name','drop_json')`. Full rebuild: one keyset-paged fetch-all, cached and grouped once. The `drop_json` schema is **OPEN**:
- **Rarity:** `Fraction` on integer denom; else regex float denom (`1/26.9` → `Decimal`); else `'Always'`→`1.0`; else `weight=None` + `data.rarity_raw` + `verify`. **Never assume integer denom.** Preserve `Alt Rarity`/`Alt Rarity Dash`/`Approx` into `data.rarity_alt` (state-conditional rates must not be lost).
- **Quantity:** parse `'5–15'` en-dash/hyphen ranges into `qty_low`/`qty_high`; strip `'(noted)'` into `data.noted=true`.
- **Variant:** split `Dropped from` on the **first** `#`, keep whatever follows **verbatim** in `data.variant` (open set — `#MVP`, `#non-MVP`, `#Post-quest`, …; do **not** validate against an enum).
- **Unknown keys:** `data.extra`, never dropped. Unparseable blob ⇒ quarantine + `verify`, never silent drop. (Live: Scurrius = 41 rows, 27 `#MVP` / 14 `#non-MVP`.)

**RDT / Gem-DT (the coverage hole).** RDT items **are not `dropsline` rows** — membership lives in a template/`Module:DropTable`. Treat the RDT as a **separate source**: extract its membership once, mint a synthetic marker node `access:rolls-rare-drop-table` (or `activity:rdt`), and link `monster --drops--> access:rolls-rare-drop-table` with `data.via='rdt'`. **Completeness check C13** measures the hole: every monster with `Rolls>1` or a known RDT flag must have explicit RDT linkage or a `verify` marker (so C9 can't pass green while the unique loot is absent). Full per-roll probability math stays deferred; presence/linkage does not.

**Quest reqs (the `scp` dispatch table).** The `scp` HTML spans are the deterministic fast-path, but **`data-skill` is NOT always a skill**:

```python
def scp_to_atom(span) -> Atom:
    skill, level = span["data-skill"], int(span["data-level"])
    if skill in SKILL_SET:          return skill_level(ref=f"skill:{slug(skill)}", threshold=level)
    if skill == "Quest points":     return qp_at_least(threshold=level)          # NO skill FK
    if skill == "Combat level":     return combat_level(threshold=level)
    return Tier3Queue(span)         # unknown → LLM + verify, never a skill_level FK
```

Extractor unit assert (pre-load, pre-I6): every emitted `skill_level` atom's `ref_node` resolves to `kind=skill`. Everything else in the requirements string (prereq quests, items, conditional/partial-completion prose) is returned **verbatim with its oldid** to the Tier-3 queue — never guessed deterministically.

**Strategies gear.** Parse raw `{{Recommended equipment}}` with `mwparserfromhell` (the `recommended_equipment` bucket is a **lossy** fallback — it drops footnotes + priority chains). `|style=` → `(style, bracket)`; `headN`/`weaponN` numeric suffix → `rank`; `{{plink|Item}}` → item natural key; `>` → ranked rows; `/` → same-rank siblings; `{{efn|name=x|text}}` → `cond_text` (→ Tier-3). **`{{efn}}` attachment is position-bound:** the splitter tracks each footnote's token position relative to the plinks and binds its `cond_group` to the **immediately-preceding plink's `loadout_item` row** (rank), not the whole cell — so a "only with full Void" footnote on the rank-2 Void helm does not falsely gate the rank-1 Slayer helm. Cell/loadout-wide `cond_group` is reserved for an efn that precedes all plinks or sits on the cell param. Every row carries the oldid-pinned `SourceRef` (satisfies I8).

**Enrichers (flagged v1 gap).** `is_boss`/`has_combat_achievements`/`has_collection_log`/`hiscore_index` exist in **no** Bucket or cache field → curated boss/CA/clog lists + Hiscores `index_lite` column map; rows carry `verify` until wired. Cheap cross-consistency where no source exists (S1): a boss with no clog, or a clog-boss not marked boss, or a boss with no boss-range `hiscore_index` → WARN.

---

## 4. Reconciliation & conflict resolution

Pre-node staging producing one `ReconRecord` per entity (persisted to a `recon_record` staging table → reproducible + diffable for drift). Only `monster` (`infobox_monster` ⊕ `NpcDefinition`) and `item` (`infobox_item` ⊕ `infobox_bonuses` ⊕ `ItemDefinition`) reconcile; skills/quests/regions are single-source (`origin='wiki-only'`).

**Join = id, with four landmines:**
1. TEXT-array/non-numeric vs INT id — `coerce_gid` normalizes (and quarantines non-numeric) before keying; multi-id row → name-match + flag.
2. Bucket-omits-null — per-field presence tracking; `WIKI_NULL` ≠ `MISSING_ENTITY`.
3. **id-agreement unverified at scale** — recon *measures* it: every id-match gets a name cross-check; `id_join_health` = % of id-matched pairs whose names agree (X7).
4. **A wiki id with no cache match** (`7223` has no `NpcDefinition`) is classified `wiki-id-with-no-cache-match` (likely-stale/wrong) and is **FAIL-on-core** — distinct from `cache-newer-than-wiki` (a benign post-update skew; see the skew guard below).

Name-matching is conservative: exactly-one unclaimed hit, else **two `missing` records** (a false split is author-recoverable; a false merge corrupts `game_id`).

**Per-field source-of-truth policy** (resolve-by-policy *and* flag the loser with `verify` — never silent):

| KG field | DISAGREE winner | verify on disagree? | Rationale |
|---|---|---|---|
| `node.game_id` | **cache** | yes (`id_name_conflict`) | cache is canonical id space (joins to Hiscores) |
| `node.name` | **cache** | yes | engine string; wiki name kept in `data.wiki_name` |
| `monster_attr.combat_level` | **cache** | **yes (FAIL on core)** | cache `combatLevel` direct field; flagship signal (the 7223/408 detector) |
| `item_attr.tradeable`/`members` | **cache** | yes | engine flags; Bucket-omitted ⇒ `False` |
| `item_attr.stackable` | cache | n/a | cache-only |
| `item_attr.slot` | **WIKI** | tripwire WARN if cache `wearPos` map disagrees | cache `wearPos` unverified → `infobox_bonuses.equipment_slot`, but disagreement is a high-value review signal (X8) |
| `buyable_ge`, examine/value/alch/weight/buy_limit, bonuses, is_boss/clog/CA, slayer | **WIKI/derived** | n/a | editorial/economic/combat-bonus; cache lacks |

**Severity wiring (the M3 fix).** Reconciliation disagreement is `WARN → reconcile_conflicts.json` for the long tail, **but it joins the core-promotion switch**: a `dual_source` core pin whose two sources disagree is a **FAIL**, not a WARN — leaving combat_level WARN means the flagship 7223/408 bug ships yellow. The `entity_verify` rollup (any field flagged, or `match_on=='name'`, or one-sided for a should-reconcile kind) copies onto `node.verify`, passes all FAIL invariants, and drives C11 verify-debt + the review queue.

**Build-time skew guard.** If the pinned `openrs2_build_id` timestamp is older than the newest wiki oldid by `> N` weeks, WARN — the wiki-newer-than-cache case is systematic right after a game update, not a per-item fluke; `id_join_health` (X7) must distinguish "cache-missing because too new" from "cache-missing because bad id."

**monster→drops aggregation.** Group-by on `page_name` (§3); fan-out multi-source lines; preserve `#variant` verbatim; keep `rolls`; RDT/Gem-DT linkage comes from its own source (§3), **not** fabricated as npcs. Output `drops` edges are **excluded from `requires_dag`** (I15).

**Cross-entity consistency** (FK-shaped, build-gate invariants; all promote WARN→FAIL on core via the uniform switch):

| Check | Rule | On miss |
|---|---|---|
| X1/X2 | drop src→`npc:`, drop item→`item:` resolve | drop edge + XFail (never fabricate a node) |
| X3 | every `{{plink}}`/`loadout_item.item_node` → real `item:` | reject slot (LLM/parser hallucination gate, pre-I14) |
| X4 | `loadout_item.slot` == item's reconciled `item_attr.slot` | `verify` (WARN; **FAIL on core** loadout) |
| X5 | `recommended_for.dst` (boss/region) resolves | drop rec + XFail (pre-C7) |
| X6 | loadout item id's cache name matches the name used | `verify` |
| X7 | `id_join_health` (metric) | **< floor ⇒ FAIL**; below threshold-but-above-floor ⇒ WARN + escalate |
| X8 | wiki slot vs cache `wearPos`-map slot | `verify` + review (slot tripwire, the discarded second source) |
| X9 | loadout `{{plink}}` whose name → `>1` numeric `item_id` | route to Tier-3 Job 3 (plink-ambiguous) with the candidate set, not a deterministic pick |

X1–X3/X5 unresolved ⇒ row dropped+logged (never node fabricated, never crash). X4/X6/X8 ⇒ `verify` (ships, unless core). The I-invariants and the core-promoted X-checks block the swap.

---

## 5. Tier-3 LLM normalization

**The only LLM in the pipeline**, touching the KG only after a hard gate. Generator = `claude-opus-4-8` via the **Batches API** (offline, 50% cost). `custom_id = <job>:<source_node>:<source_rev>` (pinned + re-runnable). **Judge is a structurally distinct call — and for the `condition` jobs a structurally distinct MODEL FAMILY** (same-family judge cannot catch same-family bias: the glory-base-vs-charged / antifire-shield-vs-potion class of plausible-but-wrong-real-node errors is correlated; see S3/break-test). Core condition trees are judged by the second family; agreement is measured.

**THE LAW.** Every entity the LLM names must FK-resolve to a real `node.id` (catches a hallucinated *node* free) **and** every condition tree must be faithful to the source text (the judge catches plausible-but-wrong *structure*). FK is **necessary, not sufficient** — a wrong-but-real node passes FK, so every Job-2 mapping to a real node still carries `verify` until a golden pin or the second-family judge confirms.

**Shared grounding catalog.** A deterministically-serialized (`ORDER BY kind, id`) slice of the `node` spine, in a `system` block with a `cache_control` breakpoint (1-hour TTL, pre-warmed) → written once at 1.25×, read at ~0.1× thereafter. Per-entity source text goes in `messages` *after* the breakpoint. **Silent-invalidator audit mandatory** (no `now()`, no per-request id, no unsorted dumps in the cached prefix; assert `cache_read_input_tokens>0` on call #2). The model may use **only** catalog ids; anything else → `unresolved` channel → `verify="tier3:unresolved"` + WARN. FK is the hard guard; the catalog just raises hit-rate.

**Three narrow jobs (strict structured output):**

1. **Quest-residual → REQUIRES cond tree** (v1-CORE). Input = `quest.requirements` with skill/qp/combat spans **stripped** (the schema's enum omits skill/combat atoms so the LLM can't re-derive them). Emits flat groups + atoms (`quest_done`, **`quest_started`** [added so partial-completion is expressible rather than dropped or wrongly upgraded to `quest_done`], `has_item`, `has_node`, `diary_done`, `ca_done`, `qp_at_least`, `account_type`) + `unresolved`. "and/both/comma"→AND, "or/either"→OR, depth ≤3. Anything still inexpressible → `unresolved` + `verify` + WARN, **never coerced**.
2. **`{{efn}}` footnote → predicate** (v1-CORE for the closed set-footnote table). Key field = **`kind` triage**: `condition`→`cond_group` FK on the loadout/rec edge; `advisory`→`loadout_item.data.note` (never a fake requirement); `none`→prose. v1 win: `"full Void"`→`AND(has_node access:full-void)` via a short cached mapping table over existing `access:*` nodes; free-text Prayer/quest-conditional tail deferred (emit only if fully grounded, else WARN). **Position-bound** (§3): the predicate attaches to the specific rank the footnote followed.
3. **In-cell `>`/`/` → ranked/alternative items** (v1-CORE, mostly deterministic). The deterministic splitter owns structure + exact-name resolution (with a **variant-suffix / charge-number normalizer** so `glory` vs `glory(6)` is resolved by rule, not LLM). The LLM is invoked **only** for a plink that fails deterministic resolution (ambiguous/renamed/variant, or the X9 multi-numeric-id case), handed the small candidate set, picks one id (constrained to the set, then FK-checked) **and the choice is round-trip checked** (`chosen_id ∈ candidates ∧ FK-resolves`; ordering preserved) — or null + `verify="tier3:plink-ambiguous"`.

**The gate (`land_tier3`):**
- **GATE 1 — FK** every `ref_node` (+ empty `unresolved`).
- **GATE 2 — tree well-formed** (I5: single root, NOT⇒1 child, AND/OR⇒≥1, no cycle).
- **GATE 3 — faithfulness** on Jobs 1–2 `condition` only. The tree is **back-rendered to English deterministically** *and* handed to the judge **as both structured JSON and the back-rendering** (so a back-renderer bug can't launder an unfaithful tree). The back-renderer is **unit-tested exhaustively** against the closed atom×op grammar (it is now in the correctness path). Judge compares meaning↔meaning (**faithfulness, not truth**); `verdict≠faithful ∨ invented ∨ ¬structure_ok` → quarantine.

Pass → write rows `verify=NULL` + provenance (oldid); fail → quarantine `verify="tier3:…"` + WARN (kept, not dropped; feeds C11). Job 3's "judge" is the deterministic round-trip check above. Tier-3 rides existing invariants I1/I2/I5/I6/I8 — no new ones.

**Judge calibration (S3).** A small hand-labeled set (~30 trees, half deliberately *unfaithful* — OR↔AND flip, dropped NOT, invented atom) measures judge precision/recall on catching the unfaithful ones. A judge that can't catch a hand-injected OR→AND flip is theater; this is the **judge's own mutation test**. DSII-class prose and an **adversarial plausible-wrong pin** (e.g. an "antifire" footnote that must NOT become `has_item Anti-dragon shield`) are golden pins with manually-authored expected trees, so the FK-passes-but-wrong class is regression-caught.

---

## 6. Transform to the KG (the LOAD step, LLM-free)

One ordered pass; later stages FK into earlier. **Idempotency = ids are pure functions of stable game ids / frozen slugs** (no autoincrement in `node.id`; `ON CONFLICT(id) DO UPDATE` upsert).

```python
def item_id(raw): return f"item:{coerce_gid(raw)}"     # raw may be ["1704"]; non-numeric → quarantine upstream
def npc_id(raw):  return f"npc:{coerce_gid(raw)}"
def slug_id(prefix, *p): return ":".join([prefix, *[slug(x) for x in p]])
# quest:dragon-slayer-ii | access:full-void | diary:varrock:hard | loadout:melee:mid
```

`slug_freeze.yaml` asserts authored slugs are stable across rebuilds (a wiki rename that would churn a slug **fails the build** → routes to `node_alias`).

**Stage 1 — nodes + side tables.** One mapping per kind (§3 source map); side-table writes obey I13 (1:1, right kind) by construction. Reconciliation already happened (§4); here we record the winning source in `node.data`, store `wiki_name` on conflict, and stamp `verify` on disagreement.

**Stage 2 — fact edges + ACCESS construction.** `drops` (verbatim `data.rate`/`qty_low`/`qty_high`/`variant`/`rarity_alt`, never re-mathed, excluded from requires_dag / I15); `located_in`; `gated_by`. **Access sink mechanism:** mint `access:<slug>` iff ≥2 nodes gate the same capability **or** it's a set-completion; else REQUIRE the producer directly. Producers `--grants-->access`, consumers `--requires-->access` — no producer edge targets another producer → the requires projection can't cycle through the glue. **Conditional grant for sets** = a *single* grant carrying an AND-of-pieces tree (NOT four OR-able grants — the false-full-Void-on-one-piece bug):

```python
cg = build_tree(AND, [has_item("item:11665"), has_item("item:8839"),
                      has_item("item:8840"),  has_item("item:8842")])
edge(type="grants", src="access:full-void", dst="access:full-void", cond_group=cg, data={"method": "own_set"})
```

I16 guard: ≥2 unconditional grants from distinct producers on one access node → WARN (alternatives belong as an OR `cond_group` on the *requirer*, not conjoined prereqs).

**Stage 3 — REQUIRES.** Skill-span fast-path: N independent skill levels → **N `requires` edges, `cond_group=NULL`, `data.threshold` on each** (implicit-AND; the chosen single-skill shape). Real OR/NOT → `build_tree` materializes `condition_group`/`condition_atom`, **resolving every atom's `ref_node` through the resolver (eager FK-hallucination catch; unresolved → drop edge + verify)**. Then assert **I1 acyclic** on the cycle-augmented projection; a cycle **FAILs the swap** and reports `simple_cycles` — never auto-mutated (it's an authoring bug: usually an alternative-grant collapse that should be an OR `cond_group`, or a producer→producer edge that should go through an access sink).

**Stage 4 — opinion.** Mint `gear_loadout` node (reused across bosses); `loadout_item` rows (`>`→ranks, `/`→same-rank siblings, `{{efn}}`→**per-line, position-bound** `cond_group`, consumables get `inv:food`/`inv:spec` slots); `recommended_for` edge (`edge_class='opinion'`, the I9 licensing seam, `data.{style,bracket,rank}` + `weight`); `loadout_override` per `(rec_edge, slot)` so a shared loadout is tailored per boss **without forking**. **`provenance` mandatory (I8 FAIL)** — one row per opinion edge / loadout_item / loadout_override with the pinned `oldid` (= attribution + drift key).

**Stage 5 — self-check** the projection-dependent invariants it built (I1 acyclic, I2/I14 FK closure), stamp `kg_meta` + `source_rev`, hand the candidate to the build-gate.

---

## 7. QA & eval harness

| Layer | Checks | Stage | Severity |
|---|---|---|---|
| DB CHECK/UNIQUE/FK | I2, I4, I9, I10, I17 | ingest/row | FAIL |
| pydantic loader | edge-prop typing, scope grammar I12, atom shape | ingest | FAIL |
| **Two-source reconcile** | combat_level / item_id / name / tradeable / members agree | ingest→build | agree=high-conf; disagree=WARN → `reconcile_conflicts.json`; **disagree on core pin = FAIL** |
| **Structural invariants** | I1, I3, I5–I8, I11, I13–I16 | build-gate | FAIL |
| **Cross-entity** | X1–X9 (loadout-says-Void-is-it-Void; slot agreement; slot tripwire; multi-id plink) | build-gate | WARN (**FAIL on core**, via the uniform switch) |
| **Completeness C1–C14** | coverage ratios + `failing_ids[]` (C13 RDT-linkage; C14 source-symmetry) | build-gate | WARN (**FAIL on core**) |
| **Golden anchors** | per-field precision/recall vs blind-authored pinned truth | build-gate + CI | **FAIL on core mismatch**; soft-FAIL on >X% regression vs `lastship` baseline |
| **Random probe tier** | violation rate on cheap invariants over a stratified sample | build-gate + CI | WARN (trend); statistical power lives here, not in the 22 anchors |
| **Mutation suite** | inject known faults (250→408, swap a rate, off-by-one a rank, wrong-real-node req) → assert RED | CI | **FAIL** if any injected fault ships green |
| **LLM-as-judge** | Tier-3 efn/prose faithfulness (FK-grounded; second family on core) | build-gate | WARN (**FAIL on core**) |
| Runtime smoke | DAG-at-startup, counts ±Y%, "fresh ironman → Scurrius non-empty plan" | post-deploy | FAIL → keep previous |
| Drift | pinned oldid moved / Bucket snapshot hash changed → re-extract + value-diff typed extraction | nightly | opens review issue |

**The uniform core-promotion switch (M3).** `core_set.yaml` lists the core entities; **one switch in the check runner** promotes WARN→FAIL when any `failing_id` ∈ core, applied uniformly across reconciliation + X1–X9 + completeness + judge (not just `promote_checks` completeness). The flagship path can't rot while the long tail is half-authored. **Swap waits on zero FAIL.**

**Severity corrections folded in (M3):** combat_level disagree on core → FAIL; X4 mis-slot on core → FAIL; **I7 missing-threshold on a `requires` atom → FAIL** (an unsatisfiable atom silently never-satisfies — worse than out-of-range); C7 ("rec reachability") is **FAIL** (an unreachable `recommended_for` target is a broken UI link), reconciled with the X5 path that drops + XFails the rec. I16 stays WARN; I11-no-alias stays the hardest FAIL.

**Mutation suite is the headline (M1).** Until you can inject `408` and watch the golden scorer go RED **without first telling it the answer is 250**, determinism-first is *asserted, not demonstrated*. `qa/mutation_tests/` programmatically corrupts the candidate DB (combat_level 250→408, swap a drop rate, off-by-one a gear rank, point a quest req at the wrong real node) and asserts a FAIL per mutation. §10's "flag 7223" gate is one hand-picked mutation; this generalizes it into a standing suite.

---

## 8. The golden set

**Two tiers (M2).** (a) **~22 curated anchors** — deep, blind-authored, FAIL-gating, chosen to cover the *failure surface* (source-path × difficulty × account-sensitivity × Bucket-quirk), sized by **≥2 anchors per core cell** (not a round number). (b) A **~200–500 random stratified probe** — machine-sampled within each `kind`, over-sampling quirk-prone rows (multi-id pages, `Rarity` strings not matching `\d+/\d+|Always`, items with `{{efn}}`), auto-scored against the **cheap invariants only** (range, FK, dual-source agreement rate). **The trended metric is the probe's violation rate** — the 22 anchors prove a path exists; they cannot estimate a coverage ratio (±15% CI on ~22 makes a ">X% regression" threshold noise). RDT/multi-variant gets **≥3 anchors** (Vorkath + a pure-RDT monster + a multi-roll raid monster) — it's the most schema-stressing drop case.

**Break the circularity (M1).** The golden set must measure *correctness*, not self-consistency with the system under test:
- **Blind authoring** — the human enters a `manual`/`dual_source` pin from the rendered wiki page + in-game **without seeing the pipeline's extracted value**; *then* diff against extraction. (The synthesis's "re-verify every pin against live Bucket+cache before commit" is the *wrong direction* — that re-verifies against the system it audits.)
- **Third, non-lineage source** for `dual_source` core pins — Bucket + cache are both wiki-adjacent in lineage (RuneLite/OpenRS2 mirror Jagex; the wiki transcribes Jagex). Add a **human in-game screenshot** of the NPC/equipment stats (or the live Hiscores boss-KC column for `hiscore_index`): three sources, two lineages. Cross-lineage disagreement is the signal `dual_source` can't produce when both wiki-side sources copy the same upstream error.

**`qa/core_set.yaml` shape** (rules-as-data; every pin revision-anchored):

```yaml
meta: {version: 1, game_version: "238", openrs2_build_id: 2593,
       promote_all_layers_on_core: true, default_severity: FAIL}
entities:
  - id: npc:7221
    strata: [boss, low-barrier, account-inert, dropsline]
    sources:
      - {url: ".../Scurrius", oldid: 15164664, license: "CC BY-NC-SA 3.0"}
      - {cache: openrs2, build_id: 2593, defn: npc}
      - {non_lineage: in_game_screenshot, asset: "qa/assets/scurrius_stats.png"}   # 3rd source
    pinned:
      combat_level: {value: 250, verified_by: tri_source, blind: true}   # NOT 408
      hitpoints:    {value: 1500, verified_by: dual_source, blind: true}
    pinned_absence:                       # N4: absence pins
      - {no_edge: {type: requires, atom_type: skill_level}}              # Scurrius has no skill gate
    pinned_edges:
      - {type: requires, dst: access:scurrius-lair, verified_by: manual}
scenarios:
  - id: scenario:vorkath-ironman
    given: {account: ironman, goal: {node: npc:8061, metric: kc, target: 1}}
    assert: {plan_nonempty: true, no_ge_step_for: [item:11665],
             contains_acquisition_for: [item:11665]}
excluded_from_recall: [drops:rdt_per_roll_probability]                   # N1: don't punish deferred roadmap
```

**Verification grades:** `tri_source` (Bucket ⊕ cache ⊕ non-lineage agree — for core combat_level/item_id/name/tradeable/members) > `dual_source` (Bucket ⊕ cache agree) > `manual` (single-source wiki: slot, rarity strings, quest reqs, loadout ranks, cond-trees — read the pinned oldid by hand, blind) > `derived` (computed, e.g. `buyable_ge`).

**Scoring.** Per-(field-type, `verified_by`) precision/recall; set-valued fields (drops, req atoms, loadout slots) use real set metrics, with deferred surfaces (`excluded_from_recall`) **not** counted as recall misses. CI hard-FAILs on any core pinned mismatch/miss, structural FAIL, or absence-pin violation; soft-FAILs on >X% precision/recall regression vs committed `qa/baselines/score_golden.lastship.json`.

**Maintenance.** Nightly drift flags pins whose source oldid moved (or whose Bucket snapshot hash changed) as `stale`. **`stale` means "re-verify required" → blocking review queue, NOT auto-downgrade to WARN** (N2: a buggy update that changes a value *and* moves the oldid must not silently soften the one check that would catch it). `verify_debt.json` trends stale + aging-`manual` pins (feeds C11). New flagship content is added to `core_set.yaml` in the same PR that authors its rows (born promoted-to-FAIL). **The set grows by failure** — every shipped extraction bug becomes a permanent pin, including an adversarial plausible-wrong pin (§5).

---

## 9. Reproducibility & versioning

Pin exactly two external versions, thread everywhere. Extended `kg_meta`:

```sql
rev TEXT PK, built_at, game_version,
openrs2_build_id INTEGER NOT NULL,      -- 2593 (exact cache, not just build 238)
openrs2_timestamp, wiki_oldids_sha NOT NULL,   -- sha256 of sorted {page-or-template:oldid}
bucket_snapshot_sha NOT NULL,           -- content hash of the Bucket responses (no oldid exists for these)
extractor_sha NOT NULL, prev_rev, qa_report_sha, source_notes
```

`node/edge.source_rev` = the build `rev` that touched the row; `provenance.source_rev` = the per-page/template **oldid** (attribution + drift key). `build_manifest.json` (S0) is the reproducibility root and pins **every extracted source, including transcluded templates/modules** (S2) — re-running S0 + diffing manifests *is* drift detection for wikitext fields; the stored Bucket snapshot hash is the drift detector for Bucket fields (no oldid to lean on). **Drift = a value diff on the typed extraction**, with the oldid as attribution/explanation, not as the change-detector itself (a cosmetic edit moves an oldid without changing a fact — diffing the typed value, not the wikitext blob, stops the nightly job crying wolf).

**Atomic swap.** Build into `kg_candidate.sqlite` → QA gate → swap (SQLite `mv` / Postgres schema-rename + view repoint); never mutate live. **I11 (id stability) is the swap's hard gate**: any `node.id` vanishing vs `prev_rev` without a `node_alias` row = FAIL (per-account `node_ref`s would dangle) — exactly why ids must be real game ids from row one and why catching `7223`-is-Giant-rat *now* matters. **Promote a minimal `node_alias(old_id, new_id)` insert path into v1-CORE** (break-test): I11 FAILs without it, so the first real rename would hard-block every rebuild with no escape hatch — `node_alias` is the escape hatch. Keep the prev DB for rollback + the next-run I11 diff. Add a drift check: same id, materially different name+slot+bonuses across builds → WARN review (a reworked item may need a clog/alias decision).

**Cadence.** Nightly cheap **S0-only drift** (re-resolve every pinned oldid + `caches.json` head + Bucket snapshot hashes; diff vs `kg_meta`; change → issue tagged by blast radius). **Game update** (build advances) → full rebuild; I11 + falling coverage = the authoring TODO. **Wiki update** (oldid moved) → opinion-only incremental, re-run I8/I14/C5–C8 + X3–X6 only, structurally cannot break a fact invariant. Maintain correctness by **diffing field-by-field vs the prior row** (surfaces changed values + both oldids as a review item), not by re-trusting.

---

## 10. Scurrius vertical-slice prototype

**`src/pipeline/proto_scurrius.py`**, ~1 day, one script exercising the whole DAG on one entity → real KG rows. The **go/no-go gate** for the full crawler. External deps are pre-validated live, so its job is to prove the *orchestration*, not discover APIs.

**The 3 design-blockers it resolves (pre-confirmed live; the prototype locks them in):**
1. **Bucket query capability** — `.join()` works (item×bonuses slot server-side), `.where('page_name',…)` works, no LIKE/regex, no server `groupBy`, ids = string-arrays (and non-numeric `["interface8283"]` is real), false = omitted/empty, **a bad field name errors hard**. Record the capability map and the bad-field-name local-raise smoke test.
2. **monster→drops pattern** — `where('page_name','Scurrius')` → 41 rows, client group-by, split `#MVP`/`#non-MVP` into `data.variant`; **open rarity/quantity grammar** exercised.
3. **cache↔wiki id agreement** — reconcile `infobox_monster` (7221/cb250, 7222/cb200) against `NpcDefinition`; **flag the schema's 7223/408 as fabricated** (the `wiki-id-with-no-cache-match` class), FAIL-on-core.

**Steps.**
(a) Reconcile id + combat_level → emit `monster_attr.combat_level ∈ {200, 250}`, choose `npc:7221` canonical + `7222` variant (both mint nodes; `recommended_for`/`located_in` target the canonical 7221, else 7222 orphans → C10), write the 7223/408 correction to `recon_report.json`.
(b) Decode one `dropsline` row + group-by → ≥1 `drops` edge with a resolved real `item:<gid>` dst + parsed rarity (open grammar) + `data.variant`.
(c) Parse `Scurrius/Strategies` @ oldid 15164664 → `loadout:melee:mid` with ≥3 `loadout_item` rows (one carrying the `{{efn}}`-derived `AND(has_node access:full-void)` from the single Tier-3 call, **position-bound to its rank**) + the neck `loadout_override`; every `{{plink}}` FK-resolves; a deliberately multi-numeric-id plink (glory) routes to Job 3, not a silent pick.
(d) Emit legal `node/monster_attr/edge/condition_*/loadout_*/provenance` into `kg_candidate.sqlite` with oldid-pinned provenance; run I2/I5/I6/I8/I9/I10/I14 on the subgraph.
(e) **Run the mutation check** — inject `combat_level 250→408` into the candidate and assert the reconcile/golden layer goes RED **without** the answer pre-told.
(f) **Run one full 38k-row `dropsline` paginate** (keyset) and assert `≥0.95×38707` — n=1 does **not** retire the pagination-truncation risk.

**Pass/fail gate.**

| Must demonstrate | Pass criterion |
|---|---|
| Reconciliation catches bad data | flags 7223/408 wrong (`wiki-id-with-no-cache-match`, FAIL-on-core); emits reconciled real id + cb; mismatch carries `verify` |
| Mutation detector works blind | injected `408` ⇒ RED, with no pre-told answer |
| Drops pattern | `where('page_name')` + client group-by → FK-valid `drops` with `#variant` split + open rarity grammar |
| Bucket capability mapped | `.join` yes, top-level-where only, no LIKE/groupBy, ids = arrays (incl. non-numeric), false = omitted, bad-field errors hard — recorded |
| Pagination doesn't truncate | full `dropsline` paginate ≥0.95×38707 |
| Tier-3 narrow & validated | exactly one LLM call; output FK-resolves to `access:full-void`; position-bound; spine has zero LLM |
| Legal provenanced rows | subgraph passes I2/I5/I6/I8/I9/I10/I14 |
| Reproducible | re-run same oldids + build_id ⇒ identical rows (modulo `built_at`) — labeled an **idempotency** gate, not a correctness one |

**If the mutation detector can't be made to flag the 7223/408 error blind, the determinism-first thesis is unproven — stop and rethink before crawling.**

---

## 11. Open questions & risks

**Resolved by live recon (lock in via prototype):** Bucket `.join()` works (n=1); drops = `page_name` + client group-by + open `#variant` split; `drop_json` keys stable on Scurrius; name→id is many-to-one **and** dirty with non-numeric + case-variant rows (reconcile, never resolve gear by name); OpenRS2 build_id 2593; revision pinning works; **schema's Scurrius `7223`/`408` is fabricated (→ 7221/7222, 250/200), glory base is `1704` not `1712`, and `infobox_item` returns 3 glory rows incl. `["interface8283"]`** — all corrections must land in `kg-schema-v1.md` + `core_set.yaml` before authoring.

**Still to confirm at scale (designed-around, with the tripwire that measures each):**
- **Bucket bulk/pagination ceiling** — `limit/offset` may silently cap; keyset `orderBy` paging is primary; tripwire vs known sizes is a **FAIL** at `<0.95×`. Prototype runs the full 38k paginate; n=1 does not retire this.
- **`.join()` behavior at scale** — verified on one query; cross-check joined-row count vs an independent `infobox_bonuses` fetch-all across the 16,316-item crawl; client-merge fallback retained.
- **cache↔wiki id agreement at scale** — `id_join_health` (X7) is the gate metric with a **hard floor** (not just WARN); the skew guard separates "cache too new" from "bad id."
- **`drop_json` schema on edge cases** — Vorkath multi-variant/RDT/Gem-DT/`Alt Rarity`/`Post-quest` is the deliberate golden canary; open schema (`data.extra`) + quarantine, never crash; full RDT per-roll math deferred but **linkage measured by C13**.
- **RDT/Gem-DT membership source** — confirm the `Module:DropTable`/RDT-page extraction path and the `access:rolls-rare-drop-table` linkage; C13 measures the hole so C9 can't pass green over absent unique loot.
- **`{{efn}}` long-tail coverage** — what fraction are `condition` vs `advisory` vs ground cleanly to existing `access:*`; decide mint-more vs defer.
- **plink ambiguity rate** — if high, strengthen the deterministic variant-suffix/charge normalizer before leaning on the LLM (X9 routes the multi-numeric-id case).
- **judge agreement & calibration** — measure second-family-judge agreement on core trees + judge precision/recall on the injected-unfaithful calibration set; the back-renderer is unit-tested (it's in the correctness path).
- **single-source editorial fields** (slot, rarity magnitude, gear rank, quest thresholds, enrichers) — slot has the cache `wearPos` tripwire (X8); rarity has the `Drop Value` recompute consistency check; rank has the parse→re-render round-trip; enrichers have cross-consistency WARNs but remain a **v1 gap carrying `verify`**.
- **rate limits** — none published; stay serialized + `maxlag` + descriptive UA.

**v1-CORE:** BucketClient (+ quirks + field-catalog validation + keyset pagination + join-count cross-check), CacheClient (build pin + `wearPos` tripwire map), WikitextFetcher (oldid + transclusion pinning), all deterministic extractors (incl. `scp` dispatch table + position-bound `{{efn}}` + open drop grammar + RDT separate-source linkage), the reconcile policy + drops group-by + X1–X9 + skew guard, Tier-3 three jobs behind the FK + second-family-judge gate + grounding catalog + calibration set, the full transform (nodes/edges/access/conditional-grant/loadouts/provenance), the QA gate (I1–I17 + C1–C14 + golden two-tier + **mutation suite** + judge), the golden set + scorer with blind/tri-source authoring, reproducibility/swap/I11 + **minimal `node_alias`**, the Scurrius prototype incl. the blind mutation check and full-paginate.
**Deferred:** RDT/Gem-DT per-roll probability math, full `node_alias` rename UX (minimal insert path is in-core), Haiku downgrade for Job 3, full LangSmith harness, `object_id`/`varbit`/`region` extractors, free-text `{{efn}}` long-tail, account-type STATE layer (separate brick).
