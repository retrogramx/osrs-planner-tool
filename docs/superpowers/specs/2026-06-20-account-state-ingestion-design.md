# Account-State Ingestion — Design (v1)

**Status:** design approved 2026-06-20; spec under review → implementation plan next.
**Brick:** `feat/account-ingest`. Ingests a player's REAL account state from two runtime sources into the engine's `AccountState`, so every overlay (engine, cost, income, the upcoming tailored loot filter) runs against *their* account instead of generic assumptions.
**Companions:** the merged engine `AccountState` (`src/osrs_planner/engine/state.py`), the cost `PriceProvider` (`src/osrs_planner/cost/prices.py`), the loot-filter design (`2026-06-20-loot-filter-design.md`, the tailoring seam this feeds).

---

## 1. Purpose & scope

Turn Gilded Tome from "generic" into "your account" by ingesting two real account signals — **what you HOLD** and **what you've COMPLETED** — into `AccountState`:

1. **Bank** — the RuneLite **Bank Memory** plugin's right-click **TSV export** (`item_id ⇥ name ⇥ quantity`) → `AccountState.counts` (live owned quantities) + a **bank value** (iron-realizable coins+High-Alch = spend-now gold; total GE value = reference wealth).
2. **Collection log** — the **TempleOSRS API** (`player_collection_log.php?player=<name>&categories=all`) → the set of **obtained** collection-log item ids → *done vs missing* slots.

**v1 delivers:** `build_account_state(mode, bank_tsv=None, clog_obtained=None) -> AccountState` (both sources optional; `clog_obtained` is the already-parsed obtained set), the two parsers, and the bank-value computation (a separate `bank_value(...)` call) — producing an `AccountState` with `counts` + `clog_obtained` + the right `observable_families`, plus the value figures.

**v1 does NOT:** consume the state (the loot-filter tailoring, income/cost re-eval are separate follow-ups — §10); read the RuneLite config/H2 stores or run a custom RuneLite plugin (the source is kept pluggable so those are drop-in later — §8); ingest banked XP, GE history, or per-tab layout. The bank is a manual TSV export (matched to the "regenerate periodically" cadence — automation isn't worth a Java plugin yet); the clog is fully automatic via the API.

---

## 2. Load-bearing decisions (settled in brainstorm)

1. **Two runtime sources → one `AccountState`.** Bank → `counts`; clog → `clog_obtained`. Both optional.
2. **Bank source = the clean Bank Memory TSV export** (stable, parseable). Clog source = the **TempleOSRS API** (public, live, verified working). The source is **pluggable** (a future config/H2/RuneLite-plugin adapter normalises to the same `{item_id: qty}` / obtained-set — no redesign).
3. **Personal data → runtime inputs, NOT committed source-of-truth.** We commit only small **synthetic** test fixtures. (Unlike the wiki-sourced bricks; no `data/` dataset, no committed validator.)
4. **Reuse, don't rebuild:** ownership lands in the existing `AccountState.counts` (documented "item / gear_loadout (live owned quantities)"); bank value reuses the cost `PriceProvider`.
5. **One minimal engine change:** add `AccountState.clog_obtained` (collection-log completion is genuinely account state; the field is **forward-looking** — there is no `clog` atom_type today, so v1 stores it but no evaluator reads it). Backward-compatible (defaulted).

---

## 3. Architecture & boundary

A new package `src/osrs_planner/account/`:

| File | Responsibility |
|---|---|
| `account/bank.py` | `parse_bank_tsv(text) -> dict[str,int]` (KG-style `"item:<n>"` → qty) + `bank_value(counts, provider, family) -> BankValue`. |
| `account/temple.py` | TempleOSRS clog client: `collection_log_url(player) -> str`; `parse_temple_clog(payload) -> TempleClog`; `fetch_collection_log(player, fetcher=…) -> TempleClog` (injectable fetcher; cached raw for tests). |
| `account/state.py` | `build_account_state(mode, bank_tsv=None, clog_obtained=None) -> AccountState` — the combiner (value is a separate `bank_value` call). |
| `src/osrs_planner/engine/state.py` | **MODIFY:** add `clog_obtained: set[str] = field(default_factory=set)`. |
| `scripts/account_demo.py` | demo over the committed fixtures (or a `--bank`/`--player` the user passes). |
| `tests/account/` + `tests/account/fixtures/{sample_bank.tsv, sample_temple.json}` | per-unit tests + synthetic fixtures. |

**Boundary:** `account/` imports only `engine.state` (`AccountState`) + `cost.prices` (`PriceProvider`, a leaf) + stdlib. It must NOT import the income/cost OVERLAY logic (`osrs_planner.cost.overlay`/`routing`/`channels`, `osrs_planner.income.*`), and the KG (`kg/*.json`) is untouched. Network only inside `temple.fetch_collection_log` (descriptive User-Agent; the raw response is cached so validate/test never fetch live).

---

## 4. Bank ingestion (TSV → ownership + value)

**Parse (`parse_bank_tsv`):** the Bank Memory export is tab-delimited `item_id ⇥ name(space-padded) ⇥ quantity`, one row per stack (verified: 883 rows). Parser splits on tab, strips, → `{"item:<id>": qty}` (KG-style ids to match `counts`/the engine). Blank lines / malformed rows are skipped (with a reason), never fabricated.

**Value (`bank_value(counts, provider, family)`):** reuses `PriceProvider.ge_price`/`.high_alch`. Returns a `BankValue` dict:
- `iron_realizable`: Σ over items of the spend-now coin value — **currency at face** (coins `item:995` = 1gp, **platinum token `item:13204` = 1000gp**, neither of which the GE snapshot prices), plus `high_alch(id) × qty` **only for items with a live GE price** (i.e. tradeable → actually alchable). An item with no live GE price (or the int-max `2147483647` "no price" sentinel) is untradeable → its nominal High-Alch is unusable, so it adds **0** and is counted in `unpriced_count` (never inflates the figure). This is the gold an iron can actually turn the bank into.
- `ge_value`: Σ `ge_price(id) × qty` — reference wealth (what a main's bank is "worth").
- `per_item`: optional breakdown; `unpriced_count`: untradeable / no-real-GE items (absence ≠ 0 — disclosed, not invented).

`family` (from `account_family(mode)`) selects the headline figure: main → `ge_value`; iron/uim → `iron_realizable` (the Hiscores blind spot — what they could spend now).

---

## 5. Collection-log ingestion (Temple API → completion)

**Client (`temple.py`):** `collection_log_url(player)` builds
`https://templeosrs.com/api/collection-log/player_collection_log.php?player=<urlenc>&categories=all`.
`fetch_collection_log(player, fetcher)` GETs it (injectable `fetcher` for tests; real = a urllib fetch with a descriptive UA) and caches the raw JSON.

**Parse (`parse_temple_clog(payload)`):** the response is
`{"data": {"player", "game_mode", "total_collections_finished", "total_collections_available", "last_changed", "items": {"<source>": [{"id", "count", "date"}, …], …}}}`.
Returns `TempleClog`: `obtained = {"item:<id>" for every item across all sources with count >= 1}`, plus `finished`, `available`, `game_mode`, `last_changed`. (Verified live: Tiger0295 → 268/1701, game_mode 1 = ironman.)

**Done vs missing** (for the consumer): `missing = {clog item_ids in data/collection_log.json} - obtained`. Computed by the consumer (the loot-filter tailoring), not stored — `AccountState` carries the raw `clog_obtained` set; the full clog set lives in `collection_log.json`.

---

## 6. AccountState integration (`build_account_state`)

`build_account_state(mode, bank_tsv=None, clog_obtained=None) -> AccountState`:
- `counts = parse_bank_tsv(bank_tsv)` when a bank is given; else `{}`.
- `clog_obtained` is the already-parsed obtained set (from `temple.parse_temple_clog(...)["obtained"]` or `fetch_collection_log(...)["obtained"]`), so the fixture and live paths compose identically; else `set()`.
- `observable_families`: add `"item"` when a bank was ingested (so item-ownership atoms become a real own/don't-own, absence-aware §6, instead of UNKNOWN); add `"clog"` when clog was ingested.
- Returns the `AccountState` (mode + counts + clog_obtained + observable_families). Bank value is computed separately via `bank_value` (so it's not forced when only clog is present).

Observability is **source-gated on `is not None`** (mark a family observed only if its source was actually ingested — even an empty bank/clog counts as observed "own/completed nothing") — so a family whose source was NOT ingested stays UNKNOWN (absence ≠ zero), preserving the engine's Kleene contract.

---

## 7. The engine change

`src/osrs_planner/engine/state.py`: add one field to the `AccountState` dataclass —
`clog_obtained: set[str] = field(default_factory=set)  # collection-log items obtained; reserved for a future 'clog' completion atom (no evaluator in v1)`
— and a one-line docstring entry. Defaulted ⇒ every existing `AccountState(...)` construction and all current engine/income/cost tests keep working unchanged. **There is no `clog` atom_type today** (`CLOG_SLOT` is a NodeKind, not an atom — the locked condition-atom vocabulary confirms the engine does not evaluate clog), so this field is forward-looking: v1 stores it and the `"clog"` observability marker is reserved; wiring an evaluator path (and introducing a `clog` atom_type) is a separate future task.

---

## 8. Pluggable source (future adapters, not built)

The brick normalises every source to the same shapes (`{item_id: qty}` for ownership; an obtained-`set` for completion), so future adapters slot in with no redesign:
- **Auto-read RuneLite config** (the Bank Memory `bankmemory.*` / Quest Helper `bankitems` blobs in `~/.runelite/profiles2/*.properties`) — brittle (undocumented format), deferred.
- **Local TempleOSRS H2 db** (`~/.runelite/templeosrs/runelite-collections.mv.db`) — an offline clog source.
- **A "Gilded Tome companion" RuneLite plugin** exposing a localhost JSON endpoint — the robust full-automation path, a separate Java project (out of this Python repo's scope), worth it only if the manual cadence proves too costly.

---

## 9. Privacy & committed fixtures

The bank TSV and Temple response are **personal account data** — never committed. Tests use **small synthetic fixtures**: `tests/account/fixtures/sample_bank.tsv` (~6 hand-written rows incl. coins, an alchable item, an untradeable) and `tests/account/fixtures/sample_temple.json` (~2 sources, a few obtained items). The demo defaults to fixtures and accepts a `--bank <path>` / `--player <name>` for the user's real data, which it does NOT write into the repo.

---

## 10. What it unlocks (consumers — NOT built here)

- **Loot-filter tailoring** (the immediate next step): `counts` → *hide what you own*; `clog_obtained` vs `collection_log.json` → *beam the ~1,433 slots you still need* (the magic version). The loot filter's `generate_filter(account_state=…)` seam already accepts this.
- **Income/cost item-gates resolve:** with `"item"` observed, item-requirement atoms become real own/don't-own instead of UNKNOWN (closes the income/cost "absence ≠ zero until bank ingest" residual).
- **Iron realizable-gold figure** — the spend-now wealth the Hiscores can't see.

---

## 11. Validation & testing

No committed source dataset ⇒ no `data/validate_*` gate; correctness is enforced by tests:
- `parse_bank_tsv`: a TSV sample → `{"item:<id>": qty}`; malformed/blank rows skipped; ids are KG-style.
- `bank_value`: over `sample_bank.tsv` + a `SnapshotPriceProvider`, `iron_realizable` (coins + HA) and `ge_value` differ correctly; coins counted at face; an untradeable contributes 0 to realizable; `unpriced_count` honest.
- `parse_temple_clog`: the fixture → the obtained set (count ≥ 1 only), `finished`/`available`/`game_mode`.
- `build_account_state`: bank-only sets `counts` + observes `"item"` (not `"clog"`); clog-only sets `clog_obtained` + observes `"clog"`; both sets both; observability is source-gated.
- Engine regression: existing engine/income/cost tests stay green after the `clog_obtained` addition (the defaulted field breaks nothing).
- Boundary test: `account/` imports no income/cost OVERLAY module; the KG is untouched.
- Full suite green; the 4 existing validators still exit 0.

---

## 12. Scope boundaries / deferred to v2 (designed-for, not built)

- **Consuming the state:** loot-filter tailoring (hide owned / beam missing), income & cost re-evaluation with real ownership — separate follow-ups.
- **Auto-source adapters** (RuneLite config blob, H2 db, companion plugin) — §8.
- **Banked XP / GE history / bank-tab layout / equipment + inventory** beyond the bank container.
- **A clog-atom evaluator path** (reading `clog_obtained` in `conditions.py`) — only when a clog atom is actually exercised by a goal.
- **Multi-account management / persistence** (storing per-account state) — runtime-only in v1.
