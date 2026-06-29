# NPC Layer (shop operators) — Design

> **Status:** DESIGN (finalized 2026-06-29). Branch: `feat/npc-layer` (off `main`, all-shops layer PR #21 +
> edge-id widen PR #22 merged). The **second bottom-up layer** on the world skeleton. It builds the shop
> *operators* — closing the shop layer's deferred `operates` edges and resolving its 14 multi-location shops —
> from the operator roster the shop brick already captured. Mirrors the shop layer almost exactly.

---

## 1. Goal

Turn the shop layer's captured `owner` data into the **operator NPCs of Gielinor**: each distinct shop operator
(~435) becomes an `npc:` node, `located_in` a skeleton place via a new npc-infobox brick, with an `operates`
edge to each shop it runs (~455). This closes the shop layer's deferred operators and — because the 9 slayer
masters operate Slayer Rewards — resolves the 14 multi-location shops through their operators' locations.

## 2. Architecture (mirrors the shop layer)

Two sources, one new builder — the shop layer's backbone+snapshot+infobox triad, one rung down:

```
data/raw/wiki_shop_infoboxes.json   (have)  shop `owner` field = the operator roster + shop->npc mapping →┐ build_npcs   npc nodes
data/raw/wiki_npc_infoboxes.json    (NEW)   each operator's {{Infobox NPC}} location                     →┘ (builders/npcs) + located_in + operates
```

`build_npcs` runs **after** `build_shops` in `assemble.py`; its edges are npc-`src` (`located_in` + `operates`)
and re-key in their own seeded `rekey` call (collision-safe post the PR #22 SPAN widen). **Zero schema changes**
(npc/operates/located_in are all live). Byte-stable.

## 3. Locked decisions (brainstorm outcomes)

- **D1 — Scope = shop operators.** The 447-shop `owner` field is the ready, grounded operator roster (~435
  distinct NPCs over the 568 derived shops). The broader functional-NPC roles (tutors, slayer masters, bankers,
  quest-givers) are NOT cleanly category-sourceable on the wiki (`Category:Slayer masters`/`Skill tutors`/`Shop
  owners` don't exist) — they need their own source-hunt and are deferred to follow-up slices.
- **D2 — `role` left UNSET on derived operators.** `{{Infobox NPC}}` has no role field; defaulting one would be
  inference. The `operates` edge + the operated shop's `shop_type` already encode the role relationally.
  **Future enhancement (owner-flagged):** derive `role` from the operated shop's `shop_type` (grounded, not
  fabricated — an operator of an Archery shop is an archery shopkeeper).
- **D3 — `operates` edge is the single source of truth; `shop.operator` left unset** on derived shops (it is
  derivable from the edge). Avoids `build_npcs` back-mutating shop nodes that `build_shops` owns.
- **D4 — Multi-location shops resolved via operators, no role node.** A multi-owner shop (Slayer Rewards' 9
  masters, the 15 multi-owner shops) gets one `operates` edge per operator; each operator npc is `located_in`
  its own place. The shop's reachability = the union of its operators' locations. **No separate `slayer-master`
  role node** (YAGNI — 9 plain npcs achieve it).
- **D5 — slug npc ids** (`npc:<slug>`), matching the 15 Varrock npcs. The schema's `id_basis: cache_id` is the
  deferred cache-import future; slug is the practical id today. A collision guard (per the shop layer) is the
  defensive backstop.

## 4. Sources & the new brick

### 4a. The shop brick `owner` field (have it)
`data/raw/wiki_shop_infoboxes.json` records each shop's `owner` (a list of `[[wikilink]]`s, incl. `owner1..N`
for multi-owner shops). Over the 568 derived shops: **415 have an owner**, **~435 distinct operator NPCs**,
**~455 `operates` edges**, **15 multi-owner shops**. This is the shop→npc mapping AND the operator roster.

### 4b. NEW npc-infobox brick — `data/fetch_npc_infoboxes.py` → `data/raw/wiki_npc_infoboxes.json`
Mirrors `data/fetch_shop_infoboxes.py`. Roster = the distinct operator page-names parsed (via
`parse_infobox_links`) from the shop brick's `owner` fields over the derived roster. For each, fetch the page's
`{{Infobox NPC}}` and record **verbatim**: `location` (+ `location1..N`), `source_url`, `_provenance`. A page
with **no `{{Infobox NPC}}`** (a quest/item mis-linked as an owner, e.g. `[[Sins of the Father]]`) is recorded
as such → it never becomes an npc node (the brick is the NPC filter; never fabricated).

## 5. Data model (what lands in the graph)

- **`npc:<slug>` node** per distinct operator (slug from the NPC page-name, deterministic, collision-guarded).
  `data`: **no `role`** (D2), `members` omitted (NPC infobox membership is out of scope this slice). The 15
  Varrock operators are excluded via `extra_seen` (build_map owns them).
- **`located_in`** edge: npc → place — emitted when the NPC's infobox `location` resolves to **exactly one**
  distinct place (the shop layer's 1/>1/0 rule, reused: >1 → `multi_location: true`, no edge; 0 → FLAG).
- **`operates`** edge: npc → shop — one per shop the NPC owns (from the shop brick's owner mapping). `cond_group`
  forbidden (schema). This is the reciprocal of `shop.operator` (left unset, D3).

## 6. Multi-location resolution (the shop-layer loop, closed)

The shop layer left 14 shops `multi_location: true` (no `located_in`, no arbitrary primary) — Slayer Rewards and
kin. This slice resolves them from the operator side: each operator npc (e.g. the 9 slayer masters) is
`located_in` its own place and `operates` → the shop. So "where can I access Slayer Rewards?" = follow `operates`
backward to the operators → their `located_in` places. The shop keeps its `multi_location` flag (honest: it has
no single home); the operators supply the reachability. No `slayer-master` role node is introduced.

## 7. Schema (no changes)

- `node_kinds.npc` (live): `role_enum` + `data_keys: [role, aliases]`. We populate neither `role` (D2) nor
  `aliases` this slice — additive when sourced.
- `edge_kinds.operates` (live): domain `npc`, range `shop`, `cond_group: forbidden` — exactly what we emit.
- `edge_kinds.located_in` (live): domain already includes `npc`, range `place`.
- **Note (no change required):** the schema's `npc.id_basis: cache_id` documents the eventual cache import; the
  shipped npc ids are slugs (matching Varrock). The committed-graph `located_in` tree gate is place-only, so npc
  `located_in` edges don't stress it (and we emit ≤1 per npc).

## 8. Verification & never-fabricate

- **NEW `data/verify_npcs.py`** (source-grounding gate, pattern of `verify_shops.py`): every `operates` edge
  traces to a shop's brick `owner` entry; every npc `located_in` resolves to a committed place node. Structural
  breaches hard-fail; resolution residuals (owner links with no `{{Infobox NPC}}`, unparented npcs) are REPORTED.
- **NEW `data/verify_npc_coverage.py`** (completeness gate, report-not-fail): of the 415 owner-bearing derived
  shops, how many got ≥1 operator; per-residual breakdown {owner-not-an-npc (no infobox), npc-no-location,
  npc-location-unresolved} — the honest categorization discipline (PR #21's lesson).
- **`validate_kg`/`validate_cost`** stay green (npc nodes + operates/located_in are schema-valid; no cost token).

## 9. Testing & competency questions

TDD via subagent-driven-development, mirroring the shop layer's slice shape:
1. **npc-infobox brick** — `fetch_npc_infoboxes.py` + the `{{Infobox NPC}}` parsers (reuse the shop brick's
   block-extraction/param-split helpers) + committed snapshot + snapshot test.
2. **`build_npcs` roster + nodes** — distinct operators − Varrock (`extra_seen`); `npc:<slug>` + collision guard.
3. **Parenting + multi-location** — reuse the place name-index + `resolve_*_places` + 1/>1/0 rule.
4. **`operates` edges** — npc → shop from the owner mapping (incl. multi-owner shops).
5. **Verifiers** — `verify_npcs` + `verify_npc_coverage`.
6. **Assemble wiring + byte-stable + competency** — npc-`src` seeded rekey after `build_shops`; golden re-assemble.

**Competency questions** (`kg/competency_questions.json`): "who operates shop X" (a new `operated_by` method, or
reuse an `operates`-traversal), "where is npc Y" (region_chain over an operator), and a Slayer-Rewards
reachability question (shop → operators → places) demonstrating the closed multi-location loop.

## 10. Scope / non-goals

**IN:** operator npc nodes · `located_in` · `operates` (closing the shop loop + multi-location) · the two
verifiers · competency questions.

**OUT (deferred):**
- **Non-operator NPCs** — skill tutors, slayer masters *as a role class*, bankers, quest-givers, rumour npcs
  (their own source-hunt + slices).
- **`role` population** (D2; future: derive from `shop_type`).
- **`shop.operator` backfill** (D3).
- **`members`/`aliases`/cache-id** on npc nodes; the cache-id import.
- **Objects/resources, transport, facilities** layers (later bottom-up slices).

## 11. Open micro-items (settle in implementation)

- npc-`src` edge band + seeded rekey ordering (after `build_shops`; both `located_in` and `operates` are npc-src).
- The npc-infobox brick reuses the shop brick's pure parsers — factor the shared `extract_infobox_block` /
  `split_top_level_params` into a common module, or import them from `fetch_shop_infoboxes`.
- Whether `build_npcs` reuses `shops.resolve_shop_places`/`build_place_name_index` directly or via a small shared
  helper (the parenting logic is identical — DRY it).
- Slug determinism for NPC page-names with disambiguators (`Shop keeper (Lumbridge)`); collision guard.
- The competency `operated_by` method handler (add to the test runner if not present).
