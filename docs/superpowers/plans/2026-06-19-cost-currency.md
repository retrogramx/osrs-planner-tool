# Cost / Currency Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the account-type-aware acquisition cost overlay (expand_for_account) over real datasets — gold cost + channel divergence, with an extensible skeleton.

**Architecture:** A new src/osrs_planner/cost/ overlay package (engine never imports cost; KG stays cost-free): PriceProvider + currency table + 5 channel datasets feeding an item->channels index + a recursive price_routes walk + a multi-route CostCard that never auto-picks.

**Tech Stack:** Python, pydantic cards, hand-curated JSON datasets, pytest.

---

## File structure

| File | New/Extend | Responsibility |
|---|---|---|
| `src/osrs_planner/cost/__init__.py` | new (T1) | Package marker + one-way-boundary docstring (cost→engine only). |
| `src/osrs_planner/cost/prices.py` | new (T1) | `PriceProvider(ABC)` + `SnapshotPriceProvider` over `data/ge_prices.json` (`price.high`); strips `item:` prefix. |
| `src/osrs_planner/cost/currency.py` | new (T2) | `Currency` pydantic model + `load_currencies(path)`. |
| `src/osrs_planner/cost/channels.py` | new (T3); extend (T6/T7/T8) | `CHANNELS` taxonomy + `ChannelRecord` (frozen) + loaders (`load_shop`/`load_recipes`/`load_gather`/`load_spawns`) + synthetic `ge_record` + `build_index(...)`. |
| `src/osrs_planner/cost/cards.py` | new (T4 Route); extend (T5 CostCard) | `Route` + `CostCard` pydantic output + `rank_by_gold` / `roll_up_gold_status` helpers. |
| `src/osrs_planner/cost/routing.py` | new (T4); extend (T6 craft/gather recursion) | `price_routes(...)` recursive acquisition walk (ge/shop/spawn/craft/gather), cycle + depth guards. |
| `src/osrs_planner/cost/overlay.py` | new (T5); extend (T9 composite + notes) | `expand_for_account(goal_id, state, provider, index, kg=None) -> CostCard`. |
| `data/currencies.json` | new (T2) | Hand-curated currency reference table (coins/tokkul/honour-points/marks-of-grace seed). |
| `data/shop_prices.json` | new (T3); extend (T7) | Hand-curated shop rows (scimitar, obby maul; +Guam seed in T7). |
| `data/recipes.json` | new (T6) | Hand-curated craft recipes (Guam potion chain). |
| `data/gather.json` | new (T7) | Hand-curated gather entries (Guam leaf via Farming). |
| `data/spawns.json` | new (T8) | Hand-curated free item-spawns (Hammer). |
| `data/validate_cost.py` | new (T10) | Committed cost-data validator (iron-gate tradition). |
| `scripts/cost_demo.py` | new (T11) | Read-only demo printing golden cards × {main, ironman}. |
| `tests/cost/__init__.py` | new (T1) | Test package marker (mirrors `tests/engine/__init__.py`). |
| `tests/cost/test_*.py` | new (T1–T11) | RED/GREEN unit + golden + boundary tests. |

---

## Resolved decisions

These are the BINDING contract. Every task uses these exact names/signatures — do not rename or drift.

- **Package boundary (one-way):** `src/osrs_planner/cost/` is a sibling of `engine/`. `cost` imports from `engine` (`AccountState`, `account_family`, `JsonKGStore`); **`engine` NEVER imports `cost`** (asserted by a test scanning `src/osrs_planner/engine/**.py`). The KG stays cost-free (no `price`/`cost`/`currency` token in `kg/*.json`, asserted by `validate_cost.py`).
- **IDs are KG-style strings everywhere in the cost layer:** items `"item:<n>"` (e.g. `"item:4587"`), currencies `"currency:<slug>"` (e.g. `"currency:coins"`, `"currency:tokkul"`). `data/ge_prices.json` and `data/item_dictionary.json` key by NUMERIC `item_id`, so `SnapshotPriceProvider` strips the `"item:"` prefix internally.
- **PriceProvider constructor (RECONCILED):** the canonical loader classmethod is **`SnapshotPriceProvider.from_file(path)`**. There is exactly ONE constructor classmethod. (Drafts that wrote `from_path(...)` or `SnapshotPriceProvider("data/...")` are reconciled to `from_file(...)` throughout this plan.)
- **`build_index` signature (RECONCILED):** keyword-only, takes pre-loaded record lists + a GE-priced-id set:
  `build_index(*, shop_records=None, recipe_records=None, gather_records=None, spawn_records=None, ge_item_ids=frozenset(), extra_records=None) -> dict[str, list[ChannelRecord]]`.
  It accepts ALREADY-LOADED `list[ChannelRecord]` (not file paths) so `channels.py` imports nothing from `prices.py` at load. A convenience helper **`build_index_from_repo(repo_root, provider) -> dict[str, list[ChannelRecord]]`** loads every committed dataset + derives `ge_item_ids` from the provider's snapshot and calls `build_index`. Tests and the demo/golden runners use `build_index_from_repo`. (Drafts that wrote `build_index(REPO)` or `build_index(shop=..., recipes=...)` are reconciled to these two functions.)
- **`ge` channel is synthetic + main-only:** it is NEVER a dataset row. `build_index` injects a `ge_record(item_id)` for every `item_id` in `ge_item_ids`. `account_allow`: `ge` → `frozenset({"main"})`; **all other channels** (shop/craft/gather/spawn/drop/quest_reward/activity_reward) → `frozenset({"main","ironman","uim"})`. Account divergence EMERGES from filtering channels by family in `account_allow`, never hard-coded.
- **Gate-field discipline (iron-gate tradition):** every `ChannelRecord` carries `audience`, `pricing_basis`, `realization_channel`, `requires_ge`. The `ge` record has `requires_ge=True` / `audience="main_only"`; shop/craft/gather/spawn have `requires_ge=False` / `audience="both"`. `validate_cost.py` asserts no `ge` channel is iron-eligible.
- **Datasets are HAND-CURATED, wiki-verified, committed source-of-truth** covering the golden-set goals + a small representative sample. **Bulk wiki sourcing (Bucket storeline ~6.2k rows; full production/farming/spawn tables; the full ~50 Currencies page) is a DISCLOSED v1 follow-up** — stated in each dataset's `_provenance` and in `validate_cost.py`. NO step fetches live from the wiki during execution.
- **Index built in-memory at load:** `build_index` produces the `item_id → [ChannelRecord]` index fresh in memory. There is NO committed derived artifact, so NO freshness-guard on the index — `validate_cost.py` is the gate.
- **Skeleton fields DEFINED from the start, UNUSED in v1:** `Currency.earn_rate_per_hour` (null), `ChannelRecord.yield_` (=1), `ChannelRecord.time` (=None), `Route.time_status` (="not_estimated"), `CostCard.rankings["by_time"]` (=[]), `price_routes(..., owned=frozenset())` (threaded, unused). Tests lock the skeleton (assert null/empty/default).
- **PriceProvider absence ≠ zero:** `ge_price`/`high_alch` return `None` when missing/untraded (never a fabricated number) so routing can mark `gold_status="unavailable"`.
- **CostCard never names a single "best":** `rankings["by_gold"]` is the indices of routes sorted ascending by `gold_cost` with `gold_status=="unavailable"` sorted LAST. The card returns ALL routes; selection stays with the player/advisor.
- **Real GE highs (verified against committed `data/ge_prices.json`; `price.high`):** scimitar `item:4587`=60748 (alch 60000); obby maul `item:6528`=215000; Attack potion(3) `item:121`=11; Guam potion (unf) `item:91`=434; Guam leaf `item:249`=248; Eye of newt `item:221`=5; Vial of water `item:227`=4; Guam seed `item:5291`=27; Hammer `item:2347`=177; Voidwaker `item:27690`=40512000, components `item:27681`=4100000 + `item:27684`=1750000 + `item:27687`=32999997 (sum 38849997 < assembled 40512000); Infinity `item:6918`=2885000 + `item:6916`=1934927 + `item:6924`=2697811 + `item:6922`=781122 + `item:6920`=646705 (sum 8945565). Golden tests READ these from the snapshot at runtime (never hardcode) so a price refresh never breaks the structural contract.
- **Real KG composite facts (verified via `JsonKGStore.from_dir("kg")`):** `kg.nodes` is a `dict`; `kg.edges` is a `list[Edge]` (212 edges); `Edge` has `.id/.type/.src/.dst/.cond_group`; there is NO goal→cond_group accessor, so find the requires edge by iterating `kg.edges` for `e.type is EdgeType.REQUIRES and e.src==goal_id and e.cond_group is not None`. `item:27690` requires cond_group 4184444 = AND of 3 ITEM atoms (27681/27684/27687, qty 1). `gear_loadout_goal:infinity` requires cond_group 4436538 = AND(GEAR_LOADOUT atom ref `gear_loadout:infinity`, skill_level magic, skill_level defence); the 5 pieces are reached via `kg.composition_of("gear_loadout:infinity")` → 5214366 = AND of 5 ITEM atoms (6918/6916/6924/6922/6920, qty 1). `item:4587` requires cond_group 4340138 = skill+quest only (NO item atoms) → a leaf item priced directly. `children_of(group_id)` returns a MIXED list of `ConditionAtom` and `int` sub-group ids; flatten recursively, collecting `atom_type is AtomType.ITEM` and expanding `atom_type is AtomType.GEAR_LOADOUT` via `composition_of(ref_node)`. Import `AtomType, EdgeType` from `osrs_planner.engine.kg.model`.
- **Test layout:** `tests/engine/__init__.py` EXISTS, so `tests/cost/__init__.py` IS created (mirror it). There is no top-level `tests/__init__.py`. `pyproject.toml` is the only pytest config. Tests reach `data/`/`kg/` via paths relative to the test file (`os.path.dirname(...)`).
- **Baseline:** the full suite is **304 passed** before this plan; the cost layer is purely additive (zero engine/kg regressions). Run everything with `./venv/bin/python -m pytest`.
- **Commit footer (verbatim):** `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.

---

## Task 1: cost package scaffold + `prices.py` (PriceProvider ABC + SnapshotPriceProvider)

Stands up `src/osrs_planner/cost/` (sibling to `engine/`, one-way boundary: `cost` may import `engine`, `engine` never imports `cost`) and the first seam — `PriceProvider` plus `SnapshotPriceProvider` reading the committed `data/ge_prices.json`. IDs are KG-style `"item:<n>"` in the cost layer; the provider strips the `"item:"` prefix internally because `ge_prices.json` keys by numeric `item_id`.

Real data confirmed from `data/ge_prices.json` (envelope `{_provenance, records:[...], _excluded:[...]}`, `records` is a **list** of `{item_id:int, name, price:{high,low,capturedAt}, pricing_basis, high_alch, low_alch, buy_limit, members}`):
- `item:4587` (Dragon scimitar): `price.high` = **60748**, `high_alch` = **60000**
- `item:30682` (Accumulation charm): `price.high` = **None** (untraded), `high_alch` = **6000** — proves `high_alch` present even when GE price absent
- `item:99999999` — absent from records entirely (missing-item case)

**Files:** `src/osrs_planner/cost/__init__.py`, `src/osrs_planner/cost/prices.py`, `tests/cost/__init__.py`, `tests/cost/test_prices.py` (all new).

**Steps:**

- [ ] **Create the test package marker.** Write `tests/cost/__init__.py` with exactly:
  ```python
  """Tests for osrs_planner.cost (pytest)."""
  ```

- [ ] **Write the failing test** `tests/cost/test_prices.py`:
  ```python
  # tests/cost/test_prices.py
  """SnapshotPriceProvider over the committed data/ge_prices.json.

  Real values asserted (read from data/ge_prices.json, records list):
    item:4587  (Dragon scimitar)  price.high  = 60748, high_alch = 60000
    item:30682 (Accumulation charm) price.high = None  (untraded), high_alch = 6000
    item:99999999  absent from records entirely
  """
  from __future__ import annotations

  import os

  import pytest

  from osrs_planner.cost.prices import PriceProvider, SnapshotPriceProvider

  GE_PRICES = os.path.join(
      os.path.dirname(__file__), "..", "..", "data", "ge_prices.json"
  )


  @pytest.fixture
  def provider() -> SnapshotPriceProvider:
      return SnapshotPriceProvider.from_file(GE_PRICES)


  def test_is_a_price_provider(provider: SnapshotPriceProvider) -> None:
      assert isinstance(provider, PriceProvider)


  def test_ge_price_returns_snapshot_high(provider: SnapshotPriceProvider) -> None:
      # Dragon scimitar price.high in the committed snapshot.
      assert provider.ge_price("item:4587") == 60748


  def test_ge_price_strips_item_prefix(provider: SnapshotPriceProvider) -> None:
      # IDs are KG-style "item:<n>" in the cost layer; provider strips internally.
      assert provider.ge_price("item:4587") == provider._records[4587]["price"]["high"]


  def test_ge_price_untraded_is_none(provider: SnapshotPriceProvider) -> None:
      # Accumulation charm is mapped but has no GE price (high is null).
      assert provider.ge_price("item:30682") is None


  def test_ge_price_missing_item_is_none(provider: SnapshotPriceProvider) -> None:
      # Item id absent from the records list entirely.
      assert provider.ge_price("item:99999999") is None


  def test_high_alch_lookup(provider: SnapshotPriceProvider) -> None:
      assert provider.high_alch("item:4587") == 60000


  def test_high_alch_present_even_when_ge_price_missing(
      provider: SnapshotPriceProvider,
  ) -> None:
      # high_alch is on the mapping, independent of a live GE price.
      assert provider.ge_price("item:30682") is None
      assert provider.high_alch("item:30682") == 6000


  def test_high_alch_missing_item_is_none(provider: SnapshotPriceProvider) -> None:
      assert provider.high_alch("item:99999999") is None


  def test_abstract_base_cannot_instantiate() -> None:
      with pytest.raises(TypeError):
          PriceProvider()  # type: ignore[abstract]
  ```

- [ ] **Run RED:** `./venv/bin/python -m pytest tests/cost/test_prices.py -q`
  Expected: `ModuleNotFoundError: No module named 'osrs_planner.cost'`.

- [ ] **Create the package marker** `src/osrs_planner/cost/__init__.py`:
  ```python
  """Cost / currency overlay (account-type-aware acquisition pricing).

  Sibling to ``osrs_planner.engine``. ONE-WAY BOUNDARY: ``cost`` imports from
  ``engine`` (AccountState, account_family); ``engine`` NEVER imports ``cost``,
  and the knowledge graph (kg/*.json) stays cost-free. See
  docs/superpowers/specs/2026-06-19-cost-currency-design.md.
  """
  ```

- [ ] **Implement** `src/osrs_planner/cost/prices.py`:
  ```python
  # src/osrs_planner/cost/prices.py
  """Price providers for the cost overlay.

  ``PriceProvider`` is the single seam where snapshot -> daily-refresh -> live
  all plug in (design spec §7). v1 ships ``SnapshotPriceProvider`` over the
  committed ``data/ge_prices.json`` (deterministic, testable). A
  ``LivePriceProvider`` is a later drop-in on the same interface.

  IDs in the cost layer are KG-style ``"item:<n>"`` strings. ``ge_prices.json``
  keys by NUMERIC ``item_id``, so the provider strips the ``"item:"`` prefix
  internally. A missing or untraded price returns ``None`` (never a fabricated
  number) so the routing walk can mark the route ``gold_status="unavailable"``.
  """
  from __future__ import annotations

  import json
  from abc import ABC, abstractmethod


  def _strip_item_prefix(item_id: str) -> int:
      """`"item:4587"` -> ``4587``. Raises on a malformed id (fail loud)."""
      if not item_id.startswith("item:"):
          raise ValueError(f"expected an 'item:<n>' id, got {item_id!r}")
      return int(item_id[len("item:") :])


  class PriceProvider(ABC):
      """Abstract price source. ``None`` means 'no known price' (absence != 0)."""

      @abstractmethod
      def ge_price(self, item_id: str) -> int | None:
          """Grand Exchange price for an ``"item:<n>"`` id, or ``None``."""

      @abstractmethod
      def high_alch(self, item_id: str) -> int | None:
          """High-alchemy value for an ``"item:<n>"`` id, or ``None``."""


  class SnapshotPriceProvider(PriceProvider):
      """``PriceProvider`` backed by a committed ``data/ge_prices.json`` snapshot.

      The envelope is ``{_provenance, records: [...], _excluded: [...]}`` where
      each record is
      ``{item_id, name, price: {high, low, capturedAt}, high_alch, ...}``.
      ``ge_price`` reads ``price.high`` (the instant-buy side); a null ``high``
      or an unmapped item -> ``None``.
      """

      def __init__(self, records: dict[int, dict]) -> None:
          self._records = records

      @classmethod
      def from_file(cls, path: str) -> "SnapshotPriceProvider":
          with open(path, encoding="utf-8") as f:
              envelope = json.load(f)
          records = {r["item_id"]: r for r in envelope["records"]}
          return cls(records)

      def ge_price(self, item_id: str) -> int | None:
          rec = self._records.get(_strip_item_prefix(item_id))
          if rec is None:
              return None
          return (rec.get("price") or {}).get("high")

      def high_alch(self, item_id: str) -> int | None:
          rec = self._records.get(_strip_item_prefix(item_id))
          if rec is None:
              return None
          return rec.get("high_alch")
  ```

- [ ] **Run GREEN:** `./venv/bin/python -m pytest tests/cost/test_prices.py -q`
  Expected: `9 passed`.

- [ ] **Commit:**
  ```
  git add src/osrs_planner/cost/__init__.py src/osrs_planner/cost/prices.py tests/cost/__init__.py tests/cost/test_prices.py
  git commit -m "$(cat <<'EOF'
  feat(cost): scaffold cost package + SnapshotPriceProvider

  New src/osrs_planner/cost/ (sibling to engine, one-way boundary).
  PriceProvider ABC + SnapshotPriceProvider over committed data/ge_prices.json:
  ge_price reads price.high (item:4587 -> 60748), high_alch lookup, "item:"
  prefix stripped internally, missing/untraded -> None (absence != zero).

  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 2: `data/currencies.json` (hand-curated seed) + `currency.py` (Currency model + loader)

Adds the currency reference table — a **cost denomination**, not a KG node-kind (design spec §3.1; confirmed reference-table in `research/currency-model.md`). Seeds coins plus the non-coin currencies the golden-set channels reference (`tokkul` for the obby maul, plus honour-points + marks-of-grace so the taxonomy categories are exercised). `self_earned_only` is the structural convergence mechanism: a currency with no market has no cheaper main route.

Real anchors from `research/currency-model.md`: coins = `physical_tradeable / is_item / ge_tradeable / NOT self_earned_only`; tokkul = `physical_untradeable / is_item / not ge_tradeable / self_earned_only`, source `activity:tzhaar`, obby maul sink **75,001 Tokkul** (65,001 with Karamja gloves), item `item:6528` (Tzhaar-ket-om). honour-points = `virtual / not is_item / self_earned_only` (Fighter torso `item:10551`, 375/role). marks-of-grace = `physical_untradeable / is_item / self_earned_only`, source `minigame:rooftop-agility` (Graceful hood `item:11850`).

**Files:** `data/currencies.json`, `src/osrs_planner/cost/currency.py`, `tests/cost/test_currency.py` (all new).

**Steps:**

- [ ] **Write the failing test** `tests/cost/test_currency.py`:
  ```python
  # tests/cost/test_currency.py
  """Currency reference-table model + loader (design spec §3.1).

  A currency is a cost DENOMINATION, not a prerequisite. The committed seed
  covers coins (universal baseline) plus the non-coin currencies the golden-set
  channels reference (tokkul for the obby maul) + a couple more from
  research/currency-model.md so the category taxonomy is exercised.
  """
  from __future__ import annotations

  import os

  import pytest

  from osrs_planner.cost.currency import Currency, load_currencies

  CURRENCIES = os.path.join(
      os.path.dirname(__file__), "..", "..", "data", "currencies.json"
  )


  @pytest.fixture
  def currencies() -> dict[str, Currency]:
      return load_currencies(CURRENCIES)


  def test_load_returns_dict_keyed_by_id(currencies: dict[str, Currency]) -> None:
      assert "currency:coins" in currencies
      assert "currency:tokkul" in currencies
      for cid, cur in currencies.items():
          assert cur.id == cid  # key == record id


  def test_values_are_currency_models(currencies: dict[str, Currency]) -> None:
      assert all(isinstance(c, Currency) for c in currencies.values())


  def test_coins_is_tradeable_universal(currencies: dict[str, Currency]) -> None:
      coins = currencies["currency:coins"]
      assert coins.name == "Coins"
      assert coins.category == "physical_tradeable"
      assert coins.is_item is True
      assert coins.ge_tradeable is True
      assert coins.self_earned_only is False  # universal; main vs iron diverge in HOW


  def test_tokkul_is_self_earned_only(currencies: dict[str, Currency]) -> None:
      tokkul = currencies["currency:tokkul"]
      assert tokkul.category == "physical_untradeable"
      assert tokkul.is_item is True
      assert tokkul.ge_tradeable is False
      assert tokkul.self_earned_only is True  # no market -> converges main vs iron
      assert tokkul.source_activity == "activity:tzhaar"


  def test_tokkul_has_obby_maul_sink(currencies: dict[str, Currency]) -> None:
      # research/currency-model.md: Tzhaar-ket-om = 75,001 Tokkul at the TzHaar store.
      tokkul = currencies["currency:tokkul"]
      sinks = {s["item"]: s for s in tokkul.example_sinks}
      assert "item:6528" in sinks
      assert sinks["item:6528"]["amount"] == 75001


  def test_all_required_fields_present(currencies: dict[str, Currency]) -> None:
      required = {
          "id", "name", "category", "is_item", "ge_tradeable", "observable",
          "source_activity", "earn_rate_per_hour", "self_earned_only",
          "example_sinks",
      }
      for cur in currencies.values():
          assert required <= set(cur.model_dump().keys())


  def test_earn_rate_is_skeleton_null(currencies: dict[str, Currency]) -> None:
      # earn_rate_per_hour is a wired-but-empty skeleton in v1 (design spec §9).
      assert all(c.earn_rate_per_hour is None for c in currencies.values())


  def test_category_values_are_in_taxonomy(currencies: dict[str, Currency]) -> None:
      allowed = {
          "physical_tradeable", "physical_untradeable", "physical_fare", "virtual",
      }
      assert all(c.category in allowed for c in currencies.values())


  def test_observable_values_are_in_taxonomy(currencies: dict[str, Currency]) -> None:
      allowed = {"hiscores", "plugin", "plugin_or_unknown", "none"}
      assert all(c.observable in allowed for c in currencies.values())
  ```

- [ ] **Run RED:** `./venv/bin/python -m pytest tests/cost/test_currency.py -q`
  Expected: `ModuleNotFoundError: No module named 'osrs_planner.cost.currency'`.

- [ ] **Create the hand-curated seed** `data/currencies.json` (`earn_rate_per_hour` null everywhere — skeleton). Bulk currency coverage (the full ~50 from the Wiki Currencies page) is a disclosed v1 follow-up:
  ```json
  {
    "_provenance": {
      "domain": "currencies",
      "source_urls": ["https://oldschool.runescape.wiki/w/Currencies"],
      "accessed": "2026-06-19T00:00:00+00:00",
      "license": "CC BY-NC-SA 3.0",
      "extraction_method": "hand-curated",
      "notes": "v1 seed: coins (universal baseline) + the non-coin currencies the golden-set channels reference (tokkul for the obby maul) + honour-points/marks-of-grace to exercise the virtual + physical_untradeable categories. Sinks/categories verified from research/currency-model.md. earn_rate_per_hour is a null skeleton (filled when skill/minigame rate baselines land). Full Currencies-page coverage (~50) is a disclosed v1 follow-up."
    },
    "records": [
      {
        "id": "currency:coins",
        "name": "Coins",
        "category": "physical_tradeable",
        "is_item": true,
        "ge_tradeable": true,
        "observable": "plugin",
        "source_activity": null,
        "earn_rate_per_hour": null,
        "self_earned_only": false,
        "example_sinks": [
          {"item": "item:4587", "name": "Dragon scimitar", "amount": 100000, "note": "Daga shop (Dragon Slayer); GE ~60k is cheaper for a main"}
        ]
      },
      {
        "id": "currency:tokkul",
        "name": "Tokkul",
        "category": "physical_untradeable",
        "is_item": true,
        "ge_tradeable": false,
        "observable": "plugin",
        "source_activity": "activity:tzhaar",
        "earn_rate_per_hour": null,
        "self_earned_only": true,
        "example_sinks": [
          {"item": "item:6528", "name": "Tzhaar-ket-om", "amount": 75001, "note": "TzHaar-Hur store; 65,001 with Karamja gloves (diary discount)"}
        ]
      },
      {
        "id": "currency:honour-points",
        "name": "Honour points",
        "category": "virtual",
        "is_item": false,
        "ge_tradeable": false,
        "observable": "plugin_or_unknown",
        "source_activity": "activity:barbarian-assault",
        "earn_rate_per_hour": null,
        "self_earned_only": true,
        "example_sinks": [
          {"item": "item:10551", "name": "Fighter torso", "amount": 375, "note": "375 per role x4 + 1 Penance Queen kill"}
        ]
      },
      {
        "id": "currency:marks-of-grace",
        "name": "Marks of grace",
        "category": "physical_untradeable",
        "is_item": true,
        "ge_tradeable": false,
        "observable": "plugin",
        "source_activity": "minigame:rooftop-agility",
        "earn_rate_per_hour": null,
        "self_earned_only": true,
        "example_sinks": [
          {"item": "item:11850", "name": "Graceful hood", "amount": 35, "note": "Rooftop Agility shops"}
        ]
      }
    ],
    "_excluded": []
  }
  ```

- [ ] **Implement** `src/osrs_planner/cost/currency.py`:
  ```python
  # src/osrs_planner/cost/currency.py
  """Currency reference table (design spec §3.1).

  A currency is a cost DENOMINATION, not a prerequisite — a reference table, not
  a KG node-kind (research/currency-model.md). ``self_earned_only`` is the
  convergence mechanism: a currency with no market has no cheaper main route, so
  items priced in it converge main-vs-iron structurally.

  ``earn_rate_per_hour`` is a wired-but-empty skeleton in v1 (design spec §9);
  it stays ``None`` until skill/minigame rate baselines land.
  """
  from __future__ import annotations

  import json

  from pydantic import BaseModel


  class Currency(BaseModel):
      """One currency / cost denomination. Fields mirror design spec §3.1."""

      id: str
      name: str
      category: str  # physical_tradeable | physical_untradeable | physical_fare | virtual
      is_item: bool
      ge_tradeable: bool
      observable: str  # hiscores | plugin | plugin_or_unknown | none
      source_activity: str | None
      earn_rate_per_hour: int | None = None  # SKELETON (null in v1)
      self_earned_only: bool
      example_sinks: list[dict]


  def load_currencies(path: str) -> dict[str, Currency]:
      """Load ``data/currencies.json`` -> ``{currency_id: Currency}``."""
      with open(path, encoding="utf-8") as f:
          envelope = json.load(f)
      return {rec["id"]: Currency(**rec) for rec in envelope["records"]}
  ```

- [ ] **Run GREEN:** `./venv/bin/python -m pytest tests/cost/test_currency.py -q`
  Expected: `9 passed`.

- [ ] **Run the cost suite so far:** `./venv/bin/python -m pytest tests/cost -q`
  Expected: `18 passed` (Task 1's 9 + Task 2's 9).

- [ ] **Commit:**
  ```
  git add data/currencies.json src/osrs_planner/cost/currency.py tests/cost/test_currency.py
  git commit -m "$(cat <<'EOF'
  feat(cost): currency reference table (data/currencies.json + Currency model)

  Hand-curated v1 seed: coins (universal, ge_tradeable, not self_earned_only)
  + tokkul (self_earned_only, source activity:tzhaar, obby-maul sink 75,001)
  + honour-points + marks-of-grace to exercise virtual/physical_untradeable.
  earn_rate_per_hour is a null skeleton (design spec §9). Currency pydantic
  model + load_currencies(path) -> dict[str, Currency] keyed by id.

  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 3: `channels.py` — 8-channel taxonomy, ChannelRecord, ge + shop loaders, build_index, hand-curated `data/shop_prices.json`

Define the `CHANNELS` taxonomy (8 strings), the shared `ChannelRecord` shape, the `shop` and (synthetic) `ge` channel builders, and `build_index(...)` (+ the convenience `build_index_from_repo`) that returns the in-memory `item_id -> list[ChannelRecord]` index the routing walk reads. Hand-curate `data/shop_prices.json` with the two flagship proof rows (Dragon scimitar 100000 coins @ Daga's Scimitar Smithy; obby maul 75001 Tokkul @ TzHaar weapon shop) plus the canonical gate fields on every row.

**Architecture invariants (binding):** `cost` imports from `engine`, never the reverse; KG stays cost-free. `ge` channel is **main-only** + synthetic (not a shop row); all other channels allow `{"main","ironman","uim"}`. `build_index` imports nothing from `prices.py` at load (takes `ge_item_ids` as a param); `build_index_from_repo` is the only place that touches a `PriceProvider`.

**Disclosed v1 follow-up (state in `_provenance.notes`):** `data/shop_prices.json` is HAND-CURATED with the golden-set proof rows + a small representative sample. Bulk wiki sourcing (Bucket `storeline`, ~6.2k rows) is a deferred v1 follow-up — NO step fetches live from the wiki. The item->channels index is built in-memory at load; there is no committed derived artifact, so no freshness guard (Task 10's validator is the gate).

**Files:** `data/shop_prices.json`, `src/osrs_planner/cost/channels.py`, `tests/cost/test_channels.py` (all new; `tests/cost/__init__.py` created in Task 1).

**Steps:**

- [ ] **Create `data/shop_prices.json`** (hand-curated; envelope `{_provenance, records}`):
  ```json
  {
    "_provenance": {
      "domain": "shop_prices",
      "source_urls": [
        "https://oldschool.runescape.wiki/w/Daga%27s_Scimitar_Smithy",
        "https://oldschool.runescape.wiki/w/TzHaar-Hur-Tel%27s_Equipment_Store",
        "https://oldschool.runescape.wiki/w/Tokkul"
      ],
      "accessed": "2026-06-19T00:00:00+00:00",
      "license": "CC BY-NC-SA 3.0",
      "extraction_method": "hand-curated",
      "notes": "v1 HAND-CURATED proof rows for the cost-layer golden set (Dragon scimitar divergence; obby maul non-coin currency). Bulk wiki sourcing (Bucket storeline ~6.2k rows) is a DISCLOSED v1 follow-up; no live wiki fetch happens during build. Obby maul Tokkul base price = 75001 (65001 with Karamja gloves -- a deferred account-STATE cost modifier, not modeled in v1; see research/currency-model.md). Gate fields {audience,pricing_basis,realization_channel,requires_ge} present on every row; iron-gate discipline (shop rows are audience=both, requires_ge=false). Task 7 appends the Guam seed row.",
      "record_count": 2
    },
    "records": [
      {
        "item_id": "item:4587",
        "shop": "Daga's Scimitar Smithy",
        "amount": 100000,
        "currency": "currency:coins",
        "audience": "both",
        "pricing_basis": "shop",
        "realization_channel": "shop",
        "requires_ge": false
      },
      {
        "item_id": "item:6528",
        "shop": "TzHaar-Hur-Tel's Equipment Store",
        "amount": 75001,
        "currency": "currency:tokkul",
        "audience": "both",
        "pricing_basis": "shop",
        "realization_channel": "shop",
        "requires_ge": false
      }
    ]
  }
  ```

- [ ] **Write the failing test** `tests/cost/test_channels.py`:
  ```python
  # tests/cost/test_channels.py
  """Tests for osrs_planner.cost.channels — taxonomy, ChannelRecord, loaders, index."""
  from __future__ import annotations

  import json
  import os

  import pytest

  DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
  SHOP_PRICES = os.path.join(DATA, "shop_prices.json")


  def test_shop_prices_dataset_has_proof_rows_with_gate_fields():
      with open(SHOP_PRICES, encoding="utf-8") as f:
          doc = json.load(f)
      by_item = {r["item_id"]: r for r in doc["records"]}

      scim = by_item["item:4587"]
      assert scim["amount"] == 100000
      assert scim["currency"] == "currency:coins"
      assert scim["shop"] == "Daga's Scimitar Smithy"

      maul = by_item["item:6528"]
      assert maul["amount"] == 75001
      assert maul["currency"] == "currency:tokkul"

      for r in doc["records"]:
          assert r["audience"] == "both"
          assert r["requires_ge"] is False
          for f in ("audience", "pricing_basis", "realization_channel", "requires_ge"):
              assert f in r, f"shop row {r['item_id']} missing gate field {f}"


  def test_channel_taxonomy_is_the_eight_strings():
      from osrs_planner.cost.channels import CHANNELS

      assert CHANNELS == frozenset(
          {"ge", "shop", "craft", "gather", "spawn", "drop", "quest_reward", "activity_reward"}
      )


  def test_channel_record_shape_and_defaults():
      from osrs_planner.cost.channels import ChannelRecord

      rec = ChannelRecord(
          item_id="item:4587",
          channel="shop",
          currency="currency:coins",
          amount=100000,
          account_allow=frozenset({"main", "ironman", "uim"}),
          source="Daga's Scimitar Smithy",
          audience="both",
          pricing_basis="shop",
          realization_channel="shop",
          requires_ge=False,
      )
      assert rec.item_id == "item:4587"
      assert rec.channel == "shop"
      assert rec.amount == 100000
      # skeleton fields DEFINED-but-unused with their defaults
      assert rec.inputs == []
      assert rec.output_qty == 1
      assert rec.yield_ == 1
      assert rec.time is None
      # frozen / immutable
      with pytest.raises(Exception):
          rec.amount = 5


  def test_load_shop_records_from_dataset():
      from osrs_planner.cost.channels import ALL_ALLOW, load_shop

      recs = load_shop(SHOP_PRICES)
      by_item = {r.item_id: r for r in recs}

      scim = by_item["item:4587"]
      assert scim.channel == "shop"
      assert scim.amount == 100000
      assert scim.currency == "currency:coins"
      assert scim.source == "Daga's Scimitar Smithy"
      assert scim.account_allow == ALL_ALLOW
      assert scim.requires_ge is False
      assert scim.audience == "both"

      maul = by_item["item:6528"]
      assert maul.amount == 75001
      assert maul.currency == "currency:tokkul"


  def test_ge_channel_factory_is_main_only():
      from osrs_planner.cost.channels import GE_ALLOW, ge_record

      rec = ge_record("item:4587")
      assert rec.channel == "ge"
      assert rec.currency == "currency:coins"
      assert rec.amount is None  # priced live via PriceProvider in routing
      assert rec.account_allow == GE_ALLOW
      assert rec.account_allow == frozenset({"main"})  # MAIN ONLY
      assert rec.requires_ge is True
      assert rec.audience == "main_only"
      assert rec.pricing_basis == "ge"
      assert rec.realization_channel == "ge"


  def test_build_index_yields_ge_and_shop_for_scimitar():
      from osrs_planner.cost.channels import build_index, load_shop

      shop = load_shop(SHOP_PRICES)
      ge_ids = frozenset({"item:4587", "item:6528"})
      index = build_index(shop_records=shop, ge_item_ids=ge_ids)

      scim_channels = {r.channel for r in index["item:4587"]}
      assert scim_channels == {"ge", "shop"}

      by_channel = {r.channel: r for r in index["item:4587"]}
      assert by_channel["ge"].account_allow == frozenset({"main"})
      assert by_channel["shop"].account_allow == frozenset({"main", "ironman", "uim"})
      assert by_channel["shop"].amount == 100000
      assert by_channel["shop"].currency == "currency:coins"


  def test_build_index_yields_tokkul_shop_for_obby_maul():
      from osrs_planner.cost.channels import build_index, load_shop

      index = build_index(
          shop_records=load_shop(SHOP_PRICES),
          ge_item_ids=frozenset({"item:4587", "item:6528"}),
      )
      by_channel = {r.channel: r for r in index["item:6528"]}
      assert by_channel["shop"].currency == "currency:tokkul"
      assert by_channel["shop"].amount == 75001
      assert by_channel["ge"].account_allow == frozenset({"main"})


  def test_build_index_ge_only_when_not_in_shop():
      from osrs_planner.cost.channels import build_index, load_shop

      index = build_index(
          shop_records=load_shop(SHOP_PRICES),
          ge_item_ids=frozenset({"item:4587", "item:6528", "item:1215"}),
      )
      assert {r.channel for r in index["item:1215"]} == {"ge"}


  def test_build_index_shop_only_when_not_ge_priced():
      from osrs_planner.cost.channels import build_index, load_shop

      index = build_index(
          shop_records=load_shop(SHOP_PRICES),
          ge_item_ids=frozenset(),
      )
      assert {r.channel for r in index["item:4587"]} == {"shop"}
      assert {r.channel for r in index["item:6528"]} == {"shop"}


  def test_build_index_from_repo_real_datasets():
      # The convenience loader builds the whole index from committed data + a
      # provider's snapshot (ge_item_ids derived from the provider).
      from osrs_planner.cost.channels import build_index_from_repo
      from osrs_planner.cost.prices import SnapshotPriceProvider

      repo = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
      provider = SnapshotPriceProvider.from_file(os.path.join(repo, "data", "ge_prices.json"))
      index = build_index_from_repo(repo, provider)
      # scimitar (GE-priced + shop row) yields both channels
      assert {r.channel for r in index["item:4587"]} == {"ge", "shop"}
  ```

- [ ] **Run RED:** `./venv/bin/python -m pytest tests/cost/test_channels.py -q`
  Expected: `test_shop_prices_dataset_has_proof_rows_with_gate_fields` passes (data-only); the rest fail with `ModuleNotFoundError: No module named 'osrs_planner.cost.channels'`.

- [ ] **Implement** `src/osrs_planner/cost/channels.py`:
  ```python
  # src/osrs_planner/cost/channels.py
  """Channel taxonomy, the shared ChannelRecord, per-channel loaders, and the
  in-memory item->channels index for the cost layer.

  A "channel" is one way to acquire an item (ge, shop, craft, gather, spawn, and
  the deferred drop/quest_reward/activity_reward). Every channel normalizes to one
  ChannelRecord so routing.price_routes never branches per type. The index
  (item_id -> [ChannelRecord]) is built in memory at load from the committed
  datasets + the snapshot's set of GE-priced item ids (the ge channel is
  synthetic -- priced live via PriceProvider in routing, never a dataset row).

  Account-allow rule (spec §3.5): ge -> {"main"} only; every other channel ->
  {"main","ironman","uim"}. Iron-gate discipline: the synthetic ge record carries
  requires_ge=True / audience="main_only"; all other rows are audience="both".

  This module imports nothing from prices.py at load time: build_index takes the
  set of GE-priced item ids as a parameter, so channels stays independently
  testable and the engine->cost one-way boundary is preserved. The convenience
  build_index_from_repo is the single place a PriceProvider is touched.
  """
  from __future__ import annotations

  import json
  import os

  from pydantic import BaseModel, ConfigDict, Field

  # --- taxonomy: the 8 channel names (spec §3.2) ---
  CHANNELS: frozenset[str] = frozenset(
      {"ge", "shop", "craft", "gather", "spawn", "drop", "quest_reward", "activity_reward"}
  )

  # account-allow rule (spec §3.5)
  GE_ALLOW: frozenset[str] = frozenset({"main"})
  ALL_ALLOW: frozenset[str] = frozenset({"main", "ironman", "uim"})


  class ChannelRecord(BaseModel):
      """One acquisition channel for one item, normalized across all 8 channels.

      Frozen/immutable so records are hashable and de-dup-safe in the index.
      amount is the direct cost in `currency` (shop) or None (ge: priced live;
      craft/gather: computed from inputs by routing). inputs is (item_id, qty)
      pairs for craft/gather; empty for buy/spawn. yield_/time are DEFINED-but-
      unused skeleton slots (spec §9). The four gate fields mirror the iron-gate
      discipline (data/validate_iron_gate.py).
      """

      model_config = ConfigDict(frozen=True)

      item_id: str
      channel: str
      currency: str
      amount: int | None = None
      inputs: list[tuple[str, int]] = Field(default_factory=list)
      output_qty: int = 1
      account_allow: frozenset[str]
      yield_: int = 1  # SKELETON
      time: None = None  # SKELETON
      source: str
      audience: str
      pricing_basis: str
      realization_channel: str
      requires_ge: bool


  def ge_record(item_id: str) -> ChannelRecord:
      """Build the SYNTHETIC ge channel for an item (main-only, priced live).

      The ge channel is never a dataset row: its gold cost is provider.ge_price()
      at routing time, so amount stays None here. Iron-gate discipline: ge is
      main-only and requires_ge=True (an iron cannot use the GE).
      """
      return ChannelRecord(
          item_id=item_id,
          channel="ge",
          currency="currency:coins",
          amount=None,
          account_allow=GE_ALLOW,
          source="Grand Exchange",
          audience="main_only",
          pricing_basis="ge",
          realization_channel="ge",
          requires_ge=True,
      )


  def load_shop(path: str) -> list[ChannelRecord]:
      """Load shop channel records from data/shop_prices.json.

      Shop is allowed for all three account families (spec §3.5). The dataset's
      gate fields are carried through verbatim; shop rows are audience="both",
      requires_ge=False by curation.
      """
      with open(path, encoding="utf-8") as f:
          doc = json.load(f)
      records: list[ChannelRecord] = []
      for r in doc["records"]:
          records.append(
              ChannelRecord(
                  item_id=r["item_id"],
                  channel="shop",
                  currency=r["currency"],
                  amount=r["amount"],
                  account_allow=ALL_ALLOW,
                  source=r["shop"],
                  audience=r["audience"],
                  pricing_basis=r["pricing_basis"],
                  realization_channel=r["realization_channel"],
                  requires_ge=r["requires_ge"],
              )
          )
      return records


  def build_index(
      *,
      shop_records: list[ChannelRecord] | None = None,
      recipe_records: list[ChannelRecord] | None = None,
      gather_records: list[ChannelRecord] | None = None,
      spawn_records: list[ChannelRecord] | None = None,
      ge_item_ids: frozenset[str] = frozenset(),
      extra_records: list[ChannelRecord] | None = None,
  ) -> dict[str, list[ChannelRecord]]:
      """Build the in-memory item_id -> [ChannelRecord] acquisition index.

      Merges dataset-backed channel records (shop now; craft/gather/spawn wired
      below as later tasks add their loaders) with synthetic `ge` records for
      every GE-priced item id the caller passes (the snapshot's keys). Built
      fresh in memory at load -- there is no committed derived artifact, so no
      freshness guard is needed; data/validate_cost.py (Task 10) is the gate.
      """
      index: dict[str, list[ChannelRecord]] = {}

      def add(rec: ChannelRecord) -> None:
          index.setdefault(rec.item_id, []).append(rec)

      for group in (
          shop_records,
          recipe_records,
          gather_records,
          spawn_records,
          extra_records,
      ):
          for rec in group or []:
              add(rec)
      for item_id in ge_item_ids:
          add(ge_record(item_id))

      return index


  def build_index_from_repo(repo_root: str, provider) -> dict[str, list[ChannelRecord]]:
      """Load every committed channel dataset + derive ge_item_ids from the
      provider's snapshot, then call build_index.

      The single place a PriceProvider is touched at index-build time. Datasets
      that do not yet exist (later tasks add recipes/gather/spawns) are skipped.
      """
      data = os.path.join(repo_root, "data")

      def _maybe(loader, fname):
          p = os.path.join(data, fname)
          return loader(p) if os.path.exists(p) else []

      shop = _maybe(load_shop, "shop_prices.json")
      recipes = _maybe(load_recipes, "recipes.json")
      gather = _maybe(load_gather, "gather.json")
      spawns = _maybe(load_spawns, "spawns.json")
      ge_item_ids = frozenset(f"item:{iid}" for iid in provider._records.keys())
      return build_index(
          shop_records=shop,
          recipe_records=recipes,
          gather_records=gather,
          spawn_records=spawns,
          ge_item_ids=ge_item_ids,
      )
  ```
  NOTE: `build_index_from_repo` references `load_recipes`/`load_gather`/`load_spawns`, which Tasks 6/7/8 add to this same module. To keep Task 3 self-contained and green, add minimal forward stubs now and replace them with the real loaders in Tasks 6–8:
  ```python
  def load_recipes(path: str) -> list[ChannelRecord]:  # replaced in Task 6
      return []


  def load_gather(path: str) -> list[ChannelRecord]:  # replaced in Task 7
      return []


  def load_spawns(path: str) -> list[ChannelRecord]:  # replaced in Task 8
      return []
  ```

- [ ] **Run GREEN:** `./venv/bin/python -m pytest tests/cost/test_channels.py -q`
  Expected: `11 passed`.

- [ ] **Run the full suite (cost is additive):** `./venv/bin/python -m pytest -q`
  Expected: ZERO failures, ZERO errors (304 baseline + Tasks 1–3 cost tests).

- [ ] **Commit:**
  ```
  git add data/shop_prices.json src/osrs_planner/cost/channels.py tests/cost/test_channels.py
  git commit -m "$(cat <<'EOF'
  feat(cost): channel taxonomy + ChannelRecord + ge/shop loaders + build_index

  8-channel taxonomy, the shared frozen ChannelRecord, load_shop + the synthetic
  main-only ge_record, build_index (keyword-only, takes loaded record lists +
  ge_item_ids) and build_index_from_repo. Hand-curated data/shop_prices.json with
  the flagship proof rows: Dragon scimitar (item:4587) 100000 coins @ Daga's
  Scimitar Smithy and Tzhaar-ket-om (item:6528) 75001 tokkul @ TzHaar weapon
  shop, four iron-gate fields per row. ge channel main-only; all others all three
  families. load_recipes/load_gather/load_spawns are forward stubs (Tasks 6-8).
  Bulk wiki sourcing of shop_prices is a disclosed v1 follow-up.

  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 4: `routing.py` — `price_routes` for BUY channels (ge / shop / spawn) + craft/gather recursion wired

Implements the account-aware acquisition walk. The three direct-buy channels are fully priced here: `ge` (gold via PriceProvider, **main only**), `shop` (record amount, in its currency, both families), `spawn` (gold cost 0, both families). Family filtering is via each ChannelRecord's `account_allow`; the walk returns **all** matching routes (never collapses), with a cycle guard (`_visited`) and a depth cap. Craft/gather recursion is wired here (so the signature + helpers are final) and proven on real data in Task 6.

NOTE: Tests hand-build the `ChannelRecord` index so Task 4 does not couple to Task 3 loader output, but the integration step proves the GE number (60748) on the REAL `SnapshotPriceProvider`.

**Files:** `src/osrs_planner/cost/routing.py` (new), `src/osrs_planner/cost/cards.py` (new — `Route` only; `CostCard` in Task 5), `tests/cost/test_routing.py` (new). Depends on Tasks 1–3.

**Steps:**

- [ ] **Step 4.1 — RED: import smoke.** `tests/cost/test_routing.py`:
  ```python
  from osrs_planner.cost.routing import price_routes


  def test_price_routes_is_importable():
      assert callable(price_routes)
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_routing.py -q`
  Expected RED: `ModuleNotFoundError: No module named 'osrs_planner.cost.routing'`.

- [ ] **Step 4.2 — GREEN scaffold: cards.py Route + routing.py skeleton.**
  `src/osrs_planner/cost/cards.py`:
  ```python
  # src/osrs_planner/cost/cards.py
  """Public cost-layer output cards (pydantic), mirroring engine/cards.py style."""
  from __future__ import annotations

  from typing import Literal

  from pydantic import BaseModel, Field


  class Route(BaseModel):
      """One acquisition channel's quote for an item, for one account family."""

      channel: str
      currency: str
      gold_cost: int | None
      gold_status: Literal["known", "unavailable"]
      inputs: list["Route"] = Field(default_factory=list)
      time_status: str = "not_estimated"
      account_allowed: bool
      source: str
      notes: list[str] = Field(default_factory=list)
  ```
  `src/osrs_planner/cost/routing.py`:
  ```python
  # src/osrs_planner/cost/routing.py
  """price_routes -- the account-aware acquisition walk (design spec §4)."""
  from __future__ import annotations

  from osrs_planner.cost.cards import Route
  from osrs_planner.cost.channels import ChannelRecord
  from osrs_planner.cost.prices import PriceProvider

  DEPTH_CAP = 12


  def price_routes(
      item_id: str,
      family: str,
      provider: PriceProvider,
      index: dict[str, list[ChannelRecord]],
      owned: frozenset[str] = frozenset(),
      _visited: frozenset[str] = frozenset(),
      _depth: int = 0,
  ) -> list[Route]:
      return []
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_routing.py -q`
  Expected GREEN: `1 passed`.

- [ ] **Step 4.3 — RED: main on item:4587 yields a ge route AND a shop route.** Append to `tests/cost/test_routing.py`:
  ```python
  import pytest

  from osrs_planner.cost.channels import ChannelRecord
  from osrs_planner.cost.prices import PriceProvider


  class _FakeProvider(PriceProvider):
      """Returns the REAL data/ge_prices.json high for the scimitar (60748)."""

      def __init__(self, ge: dict[str, int]):
          self._ge = ge

      def ge_price(self, item_id: str) -> int | None:
          return self._ge.get(item_id)

      def high_alch(self, item_id: str) -> int | None:
          return None


  SCIMITAR = "item:4587"


  def _scimitar_ge_record() -> ChannelRecord:
      return ChannelRecord(
          item_id=SCIMITAR, channel="ge", currency="currency:coins",
          amount=None, inputs=[], output_qty=1,
          account_allow=frozenset({"main"}), source="Grand Exchange",
          audience="main_only", pricing_basis="ge", realization_channel="ge",
          requires_ge=True,
      )


  def _scimitar_shop_record() -> ChannelRecord:
      return ChannelRecord(
          item_id=SCIMITAR, channel="shop", currency="currency:coins",
          amount=100000, inputs=[], output_qty=1,
          account_allow=frozenset({"main", "ironman", "uim"}),
          source="Daga's Scimitar Smithy",
          audience="both", pricing_basis="shop", realization_channel="shop",
          requires_ge=False,
      )


  @pytest.fixture
  def scimitar_index() -> dict[str, list[ChannelRecord]]:
      return {SCIMITAR: [_scimitar_ge_record(), _scimitar_shop_record()]}


  @pytest.fixture
  def provider() -> _FakeProvider:
      return _FakeProvider({"item:4587": 60748})


  def test_main_gets_ge_and_shop_routes(scimitar_index, provider):
      routes = price_routes(SCIMITAR, "main", provider, scimitar_index)
      assert {r.channel for r in routes} == {"ge", "shop"}
      ge = next(r for r in routes if r.channel == "ge")
      shop = next(r for r in routes if r.channel == "shop")
      assert ge.gold_cost == 60748
      assert ge.gold_status == "known"
      assert ge.currency == "currency:coins"
      assert ge.account_allowed is True
      assert shop.gold_cost == 100000
      assert shop.gold_status == "known"
      assert shop.currency == "currency:coins"
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_routing.py -q`
  Expected RED: `assert set() == {'ge','shop'}`.

- [ ] **Step 4.4 — RED: ironman on item:4587 — NO ge route, shop only.** Append:
  ```python
  def test_ironman_has_no_ge_route(scimitar_index, provider):
      routes = price_routes(SCIMITAR, "ironman", provider, scimitar_index)
      assert {r.channel for r in routes} == {"shop"}
      shop = routes[0]
      assert shop.gold_cost == 100000
      assert shop.gold_status == "known"
      assert shop.account_allowed is True
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_routing.py -q` → RED (empty result).

- [ ] **Step 4.5 — RED: family value is engine account_family (no string drift).** Append:
  ```python
  from osrs_planner.engine.state import account_family


  def test_family_is_engine_account_family(scimitar_index, provider):
      fam = account_family("hardcore_ironman")  # collapses to "ironman"
      assert fam == "ironman"
      routes = price_routes(SCIMITAR, fam, provider, scimitar_index)
      assert {r.channel for r in routes} == {"shop"}
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_routing.py -q` → RED.

- [ ] **Step 4.6 — RED: spawn = 0; missing GE price -> unavailable (not fabricated).** Append:
  ```python
  def _spawn_record(item_id: str) -> ChannelRecord:
      return ChannelRecord(
          item_id=item_id, channel="spawn", currency="currency:coins",
          amount=0, inputs=[], output_qty=1,
          account_allow=frozenset({"main", "ironman", "uim"}),
          source="Free item spawn", audience="both", pricing_basis="spawn",
          realization_channel="spawn", requires_ge=False,
      )


  def test_spawn_is_zero_gold():
      item = "item:1965"
      index = {item: [_spawn_record(item)]}
      routes = price_routes(item, "main", _FakeProvider({}), index)
      assert len(routes) == 1
      assert routes[0].channel == "spawn"
      assert routes[0].gold_cost == 0
      assert routes[0].gold_status == "known"


  def test_ge_missing_price_is_unavailable():
      index = {SCIMITAR: [_scimitar_ge_record()]}
      routes = price_routes(SCIMITAR, "main", _FakeProvider({}), index)
      assert len(routes) == 1
      ge = routes[0]
      assert ge.channel == "ge"
      assert ge.gold_cost is None
      assert ge.gold_status == "unavailable"
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_routing.py -q` → RED.

- [ ] **Step 4.7 — RED: cycle + unknown-item guard.** Append:
  ```python
  def test_unknown_item_returns_empty(provider):
      assert price_routes("item:999999", "main", provider, {}) == []


  def test_self_referential_craft_does_not_recurse_forever():
      item = "item:777"
      rec = ChannelRecord(
          item_id=item, channel="craft", currency="currency:coins",
          amount=None, inputs=[(item, 1)], output_qty=1,
          account_allow=frozenset({"main", "ironman", "uim"}),
          source="craft:self", audience="both", pricing_basis="inputs",
          realization_channel="craft", requires_ge=False,
      )
      index = {item: [rec]}
      routes = price_routes(item, "main", _FakeProvider({}), index)
      assert len(routes) == 1
      assert routes[0].channel == "craft"
      assert routes[0].gold_status == "unavailable"
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_routing.py -q` → RED.

- [ ] **Step 4.8 — GREEN: implement price_routes.** Replace the body of `src/osrs_planner/cost/routing.py`:
  ```python
  # src/osrs_planner/cost/routing.py
  """price_routes -- the account-aware acquisition walk (design spec §4).

  Enumerates an item's channels from the prebuilt index, keeps those whose
  account_allow includes the family, prices each (ge via PriceProvider, shop via
  the record amount, spawn = 0, craft/gather = sum of cheapest input routes), and
  returns ALL routes. Cycle-safe (_visited) + depth-capped.
  """
  from __future__ import annotations

  from osrs_planner.cost.cards import Route
  from osrs_planner.cost.channels import ChannelRecord
  from osrs_planner.cost.prices import PriceProvider

  DEPTH_CAP = 12
  _PRODUCE_CHANNELS = {"craft", "gather"}


  def _cheapest_gold(routes: list[Route]) -> int | None:
      """Smallest known gold_cost among routes, or None if none are priced."""
      known = [
          r.gold_cost
          for r in routes
          if r.gold_status == "known" and r.gold_cost is not None
      ]
      return min(known) if known else None


  def price_routes(
      item_id: str,
      family: str,
      provider: PriceProvider,
      index: dict[str, list[ChannelRecord]],
      owned: frozenset[str] = frozenset(),
      _visited: frozenset[str] = frozenset(),
      _depth: int = 0,
  ) -> list[Route]:
      if _depth > DEPTH_CAP:
          return []
      out: list[Route] = []
      for rec in index.get(item_id, []):
          if family not in rec.account_allow:
              continue
          if rec.channel == "ge":
              price = provider.ge_price(item_id)
              if price is None:
                  out.append(Route(
                      channel="ge", currency=rec.currency, gold_cost=None,
                      gold_status="unavailable", account_allowed=True,
                      source=rec.source, notes=["ge price unavailable"],
                  ))
              else:
                  out.append(Route(
                      channel="ge", currency=rec.currency, gold_cost=int(price),
                      gold_status="known", account_allowed=True, source=rec.source,
                  ))
          elif rec.channel == "shop":
              out.append(Route(
                  channel="shop", currency=rec.currency, gold_cost=rec.amount,
                  gold_status="known" if rec.amount is not None else "unavailable",
                  account_allowed=True, source=rec.source,
              ))
          elif rec.channel == "spawn":
              out.append(Route(
                  channel="spawn", currency=rec.currency, gold_cost=0,
                  gold_status="known", account_allowed=True, source=rec.source,
              ))
          elif rec.channel in _PRODUCE_CHANNELS:
              out.append(_price_produce(
                  rec, family, provider, index, owned, _visited, _depth,
              ))
      return out


  def _price_produce(
      rec: ChannelRecord,
      family: str,
      provider: PriceProvider,
      index: dict[str, list[ChannelRecord]],
      owned: frozenset[str],
      _visited: frozenset[str],
      _depth: int,
  ) -> Route:
      """Price a craft/gather record: sum cheapest(input) * qty / output_qty."""
      sub_routes: list[Route] = []
      total = 0
      priced = True
      next_visited = _visited | {rec.item_id}
      for input_id, qty in rec.inputs:
          if input_id in next_visited or _depth + 1 > DEPTH_CAP:
              priced = False
              continue
          input_routes = price_routes(
              input_id, family, provider, index, owned, next_visited, _depth + 1,
          )
          cheapest = _cheapest_gold(input_routes)
          if cheapest is None:
              priced = False
          else:
              # record the cheapest priced sub-route for the breakdown
              chosen = next(
                  r for r in input_routes
                  if r.gold_status == "known" and r.gold_cost == cheapest
              )
              sub_routes.append(chosen)
              total += cheapest * qty
      if priced and rec.inputs:
          return Route(
              channel=rec.channel, currency=rec.currency,
              gold_cost=total // rec.output_qty, gold_status="known",
              inputs=sub_routes, account_allowed=True, source=rec.source,
          )
      return Route(
          channel=rec.channel, currency=rec.currency, gold_cost=None,
          gold_status="unavailable", inputs=sub_routes, account_allowed=True,
          source=rec.source, notes=["input not priceable"],
      )
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_routing.py -q`
  Expected GREEN: all pass.

- [ ] **Step 4.9 — Integration: prove the GE number on the REAL SnapshotPriceProvider.** Append:
  ```python
  import os

  from osrs_planner.cost.prices import SnapshotPriceProvider

  _GE = os.path.join(os.path.dirname(__file__), "..", "..", "data", "ge_prices.json")


  def test_main_ge_route_matches_real_snapshot(scimitar_index):
      real = SnapshotPriceProvider.from_file(_GE)
      routes = price_routes(SCIMITAR, "main", real, scimitar_index)
      ge = next(r for r in routes if r.channel == "ge")
      # data/ge_prices.json records[item_id=4587].price.high == 60748
      assert ge.gold_cost == 60748
      assert ge.gold_status == "known"
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_routing.py -q` → GREEN.

- [ ] **Step 4.10 — Boundary test: engine never imports cost.** Append:
  ```python
  import pathlib


  def test_engine_does_not_import_cost():
      engine_dir = pathlib.Path(__file__).resolve().parents[2] / "src" / "osrs_planner" / "engine"
      offenders = []
      for py in engine_dir.rglob("*.py"):
          text = py.read_text(encoding="utf-8")
          if "osrs_planner.cost" in text or "from ..cost" in text or "from .cost" in text:
              offenders.append(str(py))
      assert offenders == [], f"engine imports cost: {offenders}"
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_routing.py -q` → GREEN.

- [ ] **Step 4.11 — Full suite + commit.**
  Run: `./venv/bin/python -m pytest -q` → all green (cost is additive).
  Commit:
  ```
  git add src/osrs_planner/cost/routing.py src/osrs_planner/cost/cards.py tests/cost/test_routing.py
  git commit -m "$(cat <<'EOF'
  feat(cost): price_routes for ge/shop/spawn + craft/gather recursion wired

  Account-aware acquisition walk: ge (PriceProvider, main-only), shop (record
  amount), spawn (0); craft/gather recurse into inputs summing the cheapest
  priced sub-route. Returns ALL family-allowed routes (never collapses); cycle
  (_visited) + depth (12) guards. Route card added. Boundary guard asserts engine
  never imports cost. GE number 60748 proven on the real snapshot.

  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 5: `cards.py` CostCard + `overlay.expand_for_account` (single item) — flagship scimitar divergence

Adds `CostCard` (rolls a family's routes up with a `by_gold` ranking — unavailable sorted LAST, no single "best") and `expand_for_account` (public entry: resolves an item goal to its routes for the account's family). Proves the flagship scimitar divergence end-to-end on real data: main `by_gold[0]` -> GE (60748 < 100000), ironman `by_gold[0]` -> shop (no ge route exists). **This completes the thin vertical slice (Tasks 1–5): self-contained, green, ending on the scimitar divergence.**

**Files:** `src/osrs_planner/cost/cards.py` (extend — add `CostCard` + helpers), `src/osrs_planner/cost/overlay.py` (new), `tests/cost/test_cards.py` (new), `tests/cost/test_overlay.py` (new). Depends on Task 4 + engine.

**Steps:**

- [ ] **Step 5.1 — RED: CostCard constructs + never names a "best".** `tests/cost/test_cards.py`:
  ```python
  from osrs_planner.cost.cards import CostCard, Route


  def _route(channel, gold, status="known"):
      return Route(
          channel=channel, currency="currency:coins", gold_cost=gold,
          gold_status=status, account_allowed=True, source=channel,
      )


  def test_costcard_constructs_and_dumps():
      card = CostCard(
          item_id="item:4587", name="Dragon scimitar", account_family="main",
          routes=[_route("ge", 60748)],
          rankings={"by_gold": [0], "by_time": []},
          notes=[], gold_status="known",
      )
      assert card.item_id == "item:4587"
      assert card.account_family == "main"
      assert card.rankings["by_time"] == []
      dumped = card.model_dump()
      assert dumped["routes"][0]["gold_cost"] == 60748
      assert "best" not in dumped
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_cards.py -q` → RED (`ImportError: cannot import name 'CostCard'`).

- [ ] **Step 5.2 — GREEN: add CostCard + rank_by_gold + roll_up_gold_status.** Append to `src/osrs_planner/cost/cards.py`:
  ```python
  class CostCard(BaseModel):
      """Family-resolved cost roll-up for a goal/item: ALL routes + a gp ranking.

      Tags the gold-cheapest via rankings["by_gold"] but NEVER names a single
      "best" field -- selection stays with the player/advisor (design spec §5).
      """

      item_id: str
      name: str
      account_family: str
      routes: list[Route] = Field(default_factory=list)
      rankings: dict[str, list[int]] = Field(
          default_factory=lambda: {"by_gold": [], "by_time": []}
      )
      notes: list[str] = Field(default_factory=list)
      gold_status: Literal["known", "partial", "unavailable"]


  def rank_by_gold(routes: list[Route]) -> list[int]:
      """Indices of routes sorted ascending by gold_cost; unavailable LAST."""

      def key(i: int):
          r = routes[i]
          unavailable = r.gold_status == "unavailable" or r.gold_cost is None
          return (1 if unavailable else 0, r.gold_cost if not unavailable else 0)

      return sorted(range(len(routes)), key=key)


  def roll_up_gold_status(routes: list[Route]) -> Literal["known", "partial", "unavailable"]:
      """known = all priced; unavailable = none priced / empty; partial = mixed."""
      if not routes:
          return "unavailable"
      known = sum(1 for r in routes if r.gold_status == "known")
      if known == len(routes):
          return "known"
      if known == 0:
          return "unavailable"
      return "partial"
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_cards.py -q` → `1 passed`.

- [ ] **Step 5.3 — RED then GREEN: ranking helpers behave.** Append to `tests/cost/test_cards.py`:
  ```python
  from osrs_planner.cost.cards import rank_by_gold, roll_up_gold_status


  def test_rank_by_gold_ascending_unavailable_last():
      routes = [
          _route("shop", 100000),
          _route("ge", 60748),
          _route("craft", None, status="unavailable"),
          _route("spawn", 0),
      ]
      # spawn(0) < ge(60748) < shop(100000) < craft(unavailable)
      assert rank_by_gold(routes) == [3, 1, 0, 2]


  def test_roll_up_gold_status_modes():
      assert roll_up_gold_status([_route("ge", 1)]) == "known"
      assert roll_up_gold_status([_route("ge", None, "unavailable")]) == "unavailable"
      assert roll_up_gold_status(
          [_route("ge", 1), _route("craft", None, "unavailable")]
      ) == "partial"
      assert roll_up_gold_status([]) == "unavailable"
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_cards.py -q` → `3 passed`.

- [ ] **Step 5.4 — RED: expand_for_account on item:4587 (main) — routes NOT collapsed.** `tests/cost/test_overlay.py`:
  ```python
  import pytest

  from osrs_planner.cost.overlay import expand_for_account
  from osrs_planner.cost.channels import ChannelRecord
  from osrs_planner.cost.prices import PriceProvider
  from osrs_planner.engine.state import AccountState

  SCIMITAR = "item:4587"


  class _FakeProvider(PriceProvider):
      def __init__(self, ge):
          self._ge = ge

      def ge_price(self, item_id):
          return self._ge.get(item_id)

      def high_alch(self, item_id):
          return None


  def _ge_rec():
      return ChannelRecord(
          item_id=SCIMITAR, channel="ge", currency="currency:coins",
          amount=None, inputs=[], output_qty=1,
          account_allow=frozenset({"main"}), source="Grand Exchange",
          audience="main_only", pricing_basis="ge", realization_channel="ge",
          requires_ge=True,
      )


  def _shop_rec():
      return ChannelRecord(
          item_id=SCIMITAR, channel="shop", currency="currency:coins",
          amount=100000, inputs=[], output_qty=1,
          account_allow=frozenset({"main", "ironman", "uim"}),
          source="Daga's Scimitar Smithy",
          audience="both", pricing_basis="shop", realization_channel="shop",
          requires_ge=False,
      )


  @pytest.fixture
  def index():
      return {SCIMITAR: [_ge_rec(), _shop_rec()]}


  @pytest.fixture
  def provider():
      return _FakeProvider({"item:4587": 60748})


  def test_main_card_not_collapsed_ge_is_cheapest(index, provider):
      card = expand_for_account(SCIMITAR, AccountState(mode="main"), provider, index)
      assert card.item_id == SCIMITAR
      assert card.account_family == "main"
      assert len(card.routes) >= 2  # NOT collapsed to a single winner
      assert {r.channel for r in card.routes} == {"ge", "shop"}
      best_idx = card.rankings["by_gold"][0]
      assert card.routes[best_idx].channel == "ge"  # 60748 < 100000
      assert card.routes[best_idx].gold_cost == 60748
      assert card.gold_status == "known"
      assert "best" not in card.model_dump()
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_overlay.py -q` → RED (`ModuleNotFoundError: No module named 'osrs_planner.cost.overlay'`).

- [ ] **Step 5.5 — RED: ironman card — shop cheapest, NO ge route.** Append to `tests/cost/test_overlay.py`:
  ```python
  def test_ironman_card_shop_only_no_ge(index, provider):
      card = expand_for_account(SCIMITAR, AccountState(mode="ironman"), provider, index)
      assert card.account_family == "ironman"
      assert {r.channel for r in card.routes} == {"shop"}
      best_idx = card.rankings["by_gold"][0]
      assert card.routes[best_idx].channel == "shop"
      assert card.routes[best_idx].gold_cost == 100000
      assert card.gold_status == "known"


  def test_hardcore_ironman_collapses_to_ironman(index, provider):
      card = expand_for_account(SCIMITAR, AccountState(mode="hardcore_ironman"), provider, index)
      assert card.account_family == "ironman"
      assert {r.channel for r in card.routes} == {"shop"}
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_overlay.py -q` → RED.

- [ ] **Step 5.6 — RED: no allowed channel -> empty routes + unavailable + note.** Append:
  ```python
  def test_no_allowed_channel_is_unavailable(provider):
      idx = {SCIMITAR: [_ge_rec()]}  # only a ge channel -> ironman has nothing
      card = expand_for_account(SCIMITAR, AccountState(mode="ironman"), provider, idx)
      assert card.routes == []
      assert card.rankings["by_gold"] == []
      assert card.gold_status == "unavailable"
      assert card.notes  # explanatory note present
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_overlay.py -q` → RED.

- [ ] **Step 5.7 — GREEN: implement overlay.expand_for_account (single-item branch).** `src/osrs_planner/cost/overlay.py`:
  ```python
  # src/osrs_planner/cost/overlay.py
  """expand_for_account -- the public cost overlay entry (design spec §5).

  Resolves a goal/item id for the account's FAMILY into a CostCard: all viable
  routes for that family + a by_gold ranking. account-type divergence emerges
  from price_routes' family filter, not from branching here. KG is optional in
  v1; when given, notes carries the downstream-goal strategic-timing hook
  (Task 9 fills it; empty otherwise). The composite-goal branch is added in
  Task 9 -- this slice handles single item: goals.
  """
  from __future__ import annotations

  from osrs_planner.cost.cards import CostCard, rank_by_gold, roll_up_gold_status
  from osrs_planner.cost.channels import ChannelRecord
  from osrs_planner.cost.prices import PriceProvider
  from osrs_planner.cost.routing import price_routes
  from osrs_planner.engine.state import AccountState, account_family


  def expand_for_account(
      goal_id: str,
      state: AccountState,
      provider: PriceProvider,
      index: dict[str, list[ChannelRecord]],
      kg=None,
  ) -> CostCard:
      family = account_family(state.mode)
      name = _resolve_name(goal_id, kg)

      if goal_id.startswith("item:"):
          routes = price_routes(goal_id, family, provider, index)
          notes: list[str] = []
          if not routes:
              notes.append(f"No {family}-allowed acquisition channel for {goal_id}.")
          return CostCard(
              item_id=goal_id, name=name, account_family=family, routes=routes,
              rankings={"by_gold": rank_by_gold(routes), "by_time": []},
              notes=notes, gold_status=roll_up_gold_status(routes),
          )

      raise NotImplementedError(
          f"composite goal {goal_id} not supported in the single-item slice"
      )


  def _resolve_name(goal_id: str, kg) -> str:
      if kg is not None:
          node = kg.node(goal_id)
          if node is not None:
              return node.name
      return goal_id
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_overlay.py -q` → all overlay tests pass.

- [ ] **Step 5.8 — Integration: flagship divergence on REAL SnapshotPriceProvider + real KG name.** Append to `tests/cost/test_overlay.py`:
  ```python
  import os

  from osrs_planner.cost.prices import SnapshotPriceProvider
  from osrs_planner.engine.kg.json_store import JsonKGStore

  _REPO = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


  def test_flagship_divergence_real_data(index):
      provider = SnapshotPriceProvider.from_file(os.path.join(_REPO, "data", "ge_prices.json"))
      kg = JsonKGStore.from_dir(os.path.join(_REPO, "kg"))

      main = expand_for_account(SCIMITAR, AccountState(mode="main"), provider, index, kg=kg)
      iron = expand_for_account(SCIMITAR, AccountState(mode="ironman"), provider, index, kg=kg)

      assert main.name == "Dragon scimitar"  # real kg/nodes.json item:4587
      m0 = main.routes[main.rankings["by_gold"][0]]
      assert m0.channel == "ge"
      assert m0.gold_cost == 60748  # real records[4587].price.high
      assert {r.channel for r in iron.routes} == {"shop"}
      assert iron.routes[iron.rankings["by_gold"][0]].gold_cost == 100000
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_overlay.py -q` → GREEN.

- [ ] **Step 5.9 — Full suite + commit.**
  Run: `./venv/bin/python -m pytest -q` → all green.
  Commit:
  ```
  git add src/osrs_planner/cost/cards.py src/osrs_planner/cost/overlay.py tests/cost/test_cards.py tests/cost/test_overlay.py
  git commit -m "$(cat <<'EOF'
  feat(cost): CostCard + expand_for_account single-item overlay

  CostCard (all routes + by_gold ranking, unavailable sorted last, never names a
  single best) + rank_by_gold/roll_up_gold_status helpers + expand_for_account
  for item: goals. Flagship scimitar divergence on REAL data: main by_gold[0]=GE
  (60748<100000), ironman shop-only. Completes the thin vertical slice.

  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 6: `craft` channel — recipes dataset + loader + routing recursion into inputs

Add `data/recipes.json` (a real, wiki-verified Herblore potion chain), replace the `load_recipes` stub with a real loader producing `craft` `ChannelRecord`s, ensure `build_index_from_repo` folds them in, and confirm `routing.price_routes` (whose craft/gather recursion was wired in Task 4) prices a `craft` route as `Σ (cheapest gold route of each input) × qty ÷ output_qty`.

The chain (real, wiki-verified, two craft levels so recursion is exercised):
- **Attack potion(3)** `item:121` = **Guam potion (unf)** `item:91` ×1 + **Eye of newt** `item:221` ×1 → output 1.
- **Guam potion (unf)** `item:91` = **Guam leaf** `item:249` ×1 + **Vial of water** `item:227` ×1 → output 1.

Expected craft golds for a main (GE highs): Guam potion (unf) craft = `ge(249)=248 + ge(227)=4 = 252`; Attack potion(3) craft = `min(unf ge 434, unf craft 252)=252 + ge(eye of newt 221)=5 = 257`.

**Files:** `data/recipes.json` (new), `src/osrs_planner/cost/channels.py` (extend: real `load_recipes`), `tests/cost/test_channels_craft.py` (new), `tests/cost/test_routing_craft.py` (new).

**Steps:**

- [ ] **6.1 (RED) — recipes loader test.** Create `tests/cost/test_channels_craft.py`:
  ```python
  # tests/cost/test_channels_craft.py
  """Task 6: craft channel -- recipes.json loader + craft ChannelRecords."""
  from __future__ import annotations

  import os

  from osrs_planner.cost.channels import load_recipes

  RECIPES = os.path.join(
      os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "recipes.json"
  )


  def test_load_recipes_yields_craft_records():
      records = load_recipes(RECIPES)
      by_item = {r.item_id: r for r in records}

      atk = by_item["item:121"]
      assert atk.channel == "craft"
      assert atk.currency == "currency:coins"
      assert atk.amount is None  # craft cost computed from inputs, not a face amount
      assert atk.inputs == [("item:91", 1), ("item:221", 1)]
      assert atk.output_qty == 1
      assert atk.account_allow == frozenset({"main", "ironman", "uim"})
      assert atk.yield_ == 1
      assert atk.time is None

      unf = by_item["item:91"]
      assert unf.channel == "craft"
      assert unf.inputs == [("item:249", 1), ("item:227", 1)]
      assert unf.output_qty == 1
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_channels_craft.py -q`
  Expected RED: `load_recipes` is the empty stub, so `by_item["item:121"]` raises `KeyError`.

- [ ] **6.2 — create `data/recipes.json`** (hand-curated, wiki-verified; ids verified against item_dictionary.json):
  ```json
  {
    "_provenance": {
      "dataset": "recipes",
      "description": "Hand-curated, wiki-verified production recipes for the cost-layer craft channel. v1 covers the golden-set potion chain (Attack potion via Guam) only; bulk recipe sourcing from the OSRS Wiki production tables is a disclosed v1 follow-up. No live wiki fetch during build.",
      "source_urls": [
        "https://oldschool.runescape.wiki/w/Attack_potion",
        "https://oldschool.runescape.wiki/w/Guam_potion_(unf)"
      ],
      "license": "OSRS Wiki content CC BY-NC-SA 3.0",
      "curated": true
    },
    "records": [
      {
        "output_item_id": "item:121",
        "name": "Attack potion(3)",
        "channel": "craft",
        "skill": "Herblore",
        "level": 3,
        "inputs": [
          { "item_id": "item:91", "qty": 1 },
          { "item_id": "item:221", "qty": 1 }
        ],
        "output_qty": 1,
        "currency": "currency:coins",
        "source": "Herblore: mix Guam potion (unf) + Eye of newt",
        "audience": "both",
        "pricing_basis": "inputs",
        "realization_channel": "craft",
        "requires_ge": false
      },
      {
        "output_item_id": "item:91",
        "name": "Guam potion (unf)",
        "channel": "craft",
        "skill": "Herblore",
        "level": 3,
        "inputs": [
          { "item_id": "item:249", "qty": 1 },
          { "item_id": "item:227", "qty": 1 }
        ],
        "output_qty": 1,
        "currency": "currency:coins",
        "source": "Herblore: Guam leaf + Vial of water",
        "audience": "both",
        "pricing_basis": "inputs",
        "realization_channel": "craft",
        "requires_ge": false
      }
    ],
    "_excluded": []
  }
  ```

- [ ] **6.3 (GREEN) — replace the `load_recipes` stub in `channels.py`:**
  ```python
  def load_recipes(path: str) -> list[ChannelRecord]:
      """Load data/recipes.json into `craft` ChannelRecords.

      Cost is computed from inputs at routing time (amount=None). Inputs are
      (item_id, qty) tuples; output_qty divides the summed input cost.
      """
      with open(path, encoding="utf-8") as f:
          payload = json.load(f)
      records: list[ChannelRecord] = []
      for r in payload["records"]:
          records.append(
              ChannelRecord(
                  item_id=r["output_item_id"],
                  channel="craft",
                  currency=r["currency"],
                  amount=None,
                  inputs=[(i["item_id"], i["qty"]) for i in r["inputs"]],
                  output_qty=r["output_qty"],
                  account_allow=frozenset({"main", "ironman", "uim"}),
                  source=r["source"],
                  audience=r["audience"],
                  pricing_basis=r["pricing_basis"],
                  realization_channel=r["realization_channel"],
                  requires_ge=r["requires_ge"],
              )
          )
      return records
  ```
  (`build_index_from_repo` already calls `load_recipes` and reads `recipes.json` when present — no further wiring.)
  Run: `./venv/bin/python -m pytest tests/cost/test_channels_craft.py -q` → `1 passed`.

- [ ] **6.4 — commit.**
  ```
  git add data/recipes.json src/osrs_planner/cost/channels.py tests/cost/test_channels_craft.py
  git commit -m "$(cat <<'EOF'
  feat(cost): craft channel -- recipes.json + load_recipes loader

  Hand-curated Guam potion chain (Attack potion(3) <- Guam potion (unf) + Eye of
  newt; Guam potion (unf) <- Guam leaf + Vial of water). load_recipes replaces
  the Task 3 stub; build_index_from_repo folds craft records in. Bulk recipe
  sourcing is a disclosed v1 follow-up.

  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  EOF
  )"
  ```

- [ ] **6.5 (RED) — routing recurses into craft inputs.** Create `tests/cost/test_routing_craft.py`:
  ```python
  # tests/cost/test_routing_craft.py
  """Task 6: routing recursion -- craft route gold = summed priced inputs."""
  from __future__ import annotations

  import os

  from osrs_planner.cost.channels import build_index_from_repo
  from osrs_planner.cost.prices import SnapshotPriceProvider
  from osrs_planner.cost.routing import price_routes

  REPO = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


  def _setup():
      provider = SnapshotPriceProvider.from_file(os.path.join(REPO, "data", "ge_prices.json"))
      index = build_index_from_repo(REPO, provider)
      return provider, index


  def test_main_craft_unf_gold_is_summed_ge_inputs():
      provider, index = _setup()
      routes = price_routes("item:91", "main", provider, index)
      craft = [r for r in routes if r.channel == "craft"]
      assert len(craft) == 1
      # Guam leaf (item:249) GE 248 + Vial of water (item:227) GE 4 = 252
      assert craft[0].gold_cost == 252
      assert craft[0].gold_status == "known"
      assert len(craft[0].inputs) == 2  # recursive sub-routes recorded


  def test_main_craft_attack_potion_recurses_one_level():
      provider, index = _setup()
      routes = price_routes("item:121", "main", provider, index)
      craft = [r for r in routes if r.channel == "craft"]
      assert len(craft) == 1
      # unf cheapest = min(ge 434, craft 252) = 252 ; + eye of newt (item:221) ge 5 = 257
      assert craft[0].gold_cost == 257
      assert craft[0].gold_status == "known"
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_routing_craft.py -q`
  Expected: GREEN immediately if Task 4's craft recursion is correct (`2 passed`). The recursion code already exists — this task proves it on real recipe data. If RED, the bug is in Task 4's `_price_produce`; fix there with systematic-debugging, do not stub the test.

- [ ] **6.6 — full suite + commit.**
  Run: `./venv/bin/python -m pytest -q` → all pass.
  ```
  git add tests/cost/test_routing_craft.py
  git commit -m "$(cat <<'EOF'
  test(cost): craft routing recursion on real recipe data

  Guam potion (unf) craft = 252 (Guam leaf 248 + Vial of water 4); Attack
  potion(3) craft = 257 (cheapest unf 252 + Eye of newt 5) -- proves price_routes
  recurses into inputs and picks the cheapest sub-route per input.

  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 7: `gather` channel — gather dataset + loader + recursion (iron vs main divergence)

Add `data/gather.json` (a real Farming herb with a seed input), replace the `load_gather` stub, append a Guam seed shop row to `data/shop_prices.json` so the ironman's gather route is priceable without GE, and prove the divergence: a **main** prices the herb directly via GE; an **ironman** (no GE) prices the *same* herb via its `gather` route, which bottoms out at the seed's non-GE (shop) route. The gather recursion reuses Task 4's craft/gather input-summing branch.

The gather entry (real, wiki-verified): **Guam leaf** `item:249` via **Farming**, input **Guam seed** `item:5291` ×1 → output 1. Guam seed is shop-sold at Olivia's Seed Stall (Draynor) for 25 coins.

Expected: main Guam leaf routes include `ge` (248) and `gather` (gather gold = cheapest seed route = `min(ge 27, shop 25) = 25`); ironman Guam leaf has **no `ge` route**, `gather` gold = seed via shop only = `25`.

**Files:** `data/gather.json` (new), `data/shop_prices.json` (extend — Guam seed row), `src/osrs_planner/cost/channels.py` (extend: real `load_gather`), `tests/cost/test_channels_gather.py` (new), `tests/cost/test_routing_gather.py` (new).

**Steps:**

- [ ] **7.1 (RED) — gather loader test.** Create `tests/cost/test_channels_gather.py`:
  ```python
  # tests/cost/test_channels_gather.py
  """Task 7: gather channel -- gather.json loader + gather ChannelRecords."""
  from __future__ import annotations

  import os

  from osrs_planner.cost.channels import load_gather

  GATHER = os.path.join(
      os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "gather.json"
  )


  def test_load_gather_yields_gather_records():
      records = load_gather(GATHER)
      by_item = {r.item_id: r for r in records}

      guam = by_item["item:249"]
      assert guam.channel == "gather"
      assert guam.currency == "currency:coins"
      assert guam.amount is None  # cost computed from seed/bait inputs
      assert guam.inputs == [("item:5291", 1)]
      assert guam.output_qty == 1
      assert guam.account_allow == frozenset({"main", "ironman", "uim"})
      assert guam.yield_ == 1
      assert guam.time is None
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_channels_gather.py -q`
  Expected RED: `load_gather` is the empty stub → `KeyError`.

- [ ] **7.2 — create `data/gather.json`** (hand-curated, wiki-verified):
  ```json
  {
    "_provenance": {
      "dataset": "gather",
      "description": "Hand-curated, wiki-verified gathered resources for the cost-layer gather channel. v1 covers the golden-set herb (Guam via Farming) only; bulk gather sourcing (Farming/Fishing/Mining/Woodcutting/Hunter tables) is a disclosed v1 follow-up. No live wiki fetch during build.",
      "source_urls": [
        "https://oldschool.runescape.wiki/w/Guam_leaf",
        "https://oldschool.runescape.wiki/w/Guam_seed"
      ],
      "license": "OSRS Wiki content CC BY-NC-SA 3.0",
      "curated": true
    },
    "records": [
      {
        "resource_item_id": "item:249",
        "name": "Guam leaf",
        "channel": "gather",
        "skill": "Farming",
        "level": 9,
        "inputs": [
          { "item_id": "item:5291", "qty": 1 }
        ],
        "output_qty": 1,
        "currency": "currency:coins",
        "source": "Farming: Guam seed in a herb patch",
        "audience": "both",
        "pricing_basis": "inputs",
        "realization_channel": "gather",
        "requires_ge": false
      }
    ],
    "_excluded": []
  }
  ```

- [ ] **7.3 — append the Guam seed shop row to `data/shop_prices.json`.** Read the file first, then add this record to the `records` array (matching the Task 3 shop schema: `item_id`, `shop`, `amount`, `currency`, gate fields) and bump `_provenance.record_count` to 3:
  ```json
  {
    "item_id": "item:5291",
    "shop": "Olivia's Seed Stall",
    "amount": 25,
    "currency": "currency:coins",
    "audience": "both",
    "pricing_basis": "shop",
    "realization_channel": "shop",
    "requires_ge": false
  }
  ```

- [ ] **7.4 (GREEN) — replace the `load_gather` stub in `channels.py`** (note the dataset key is `resource_item_id`):
  ```python
  def load_gather(path: str) -> list[ChannelRecord]:
      """Load data/gather.json into `gather` ChannelRecords.

      Cost is computed from seed/bait/compost inputs at routing time
      (amount=None), reusing the same input-summing branch as craft.
      """
      with open(path, encoding="utf-8") as f:
          payload = json.load(f)
      records: list[ChannelRecord] = []
      for r in payload["records"]:
          records.append(
              ChannelRecord(
                  item_id=r["resource_item_id"],
                  channel="gather",
                  currency=r["currency"],
                  amount=None,
                  inputs=[(i["item_id"], i["qty"]) for i in r["inputs"]],
                  output_qty=r["output_qty"],
                  account_allow=frozenset({"main", "ironman", "uim"}),
                  source=r["source"],
                  audience=r["audience"],
                  pricing_basis=r["pricing_basis"],
                  realization_channel=r["realization_channel"],
                  requires_ge=r["requires_ge"],
              )
          )
      return records
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_channels_gather.py -q` → `1 passed`. Also re-run `tests/cost/test_channels.py` to confirm the new shop row didn't break the proof-row test (it asserts specific items, not row count) — `./venv/bin/python -m pytest tests/cost/test_channels.py -q`.

- [ ] **7.5 — commit.**
  ```
  git add data/gather.json data/shop_prices.json src/osrs_planner/cost/channels.py tests/cost/test_channels_gather.py
  git commit -m "$(cat <<'EOF'
  feat(cost): gather channel -- gather.json + load_gather; guam seed shop leaf

  Guam leaf (item:249) via Farming from Guam seed (item:5291). load_gather
  replaces the Task 3 stub. Guam seed shop row (Olivia's Seed Stall, 25 coins)
  added to shop_prices.json so an ironman's gather route is priceable without GE.
  Bulk gather sourcing is a disclosed v1 follow-up.

  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  EOF
  )"
  ```

- [ ] **7.6 (RED) — gather routing divergence test.** Create `tests/cost/test_routing_gather.py`:
  ```python
  # tests/cost/test_routing_gather.py
  """Task 7: gather routing -- main prices herb via GE, iron via gather (no GE)."""
  from __future__ import annotations

  import os

  from osrs_planner.cost.channels import build_index_from_repo
  from osrs_planner.cost.prices import SnapshotPriceProvider
  from osrs_planner.cost.routing import price_routes

  REPO = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


  def _setup():
      provider = SnapshotPriceProvider.from_file(os.path.join(REPO, "data", "ge_prices.json"))
      index = build_index_from_repo(REPO, provider)
      return provider, index


  def test_main_guam_has_ge_and_gather_routes():
      provider, index = _setup()
      routes = price_routes("item:249", "main", provider, index)
      channels = {r.channel for r in routes}
      assert "ge" in channels      # main may GE-buy the herb directly
      assert "gather" in channels
      ge = next(r for r in routes if r.channel == "ge")
      assert ge.gold_cost == 248   # Guam leaf GE high
      gather = next(r for r in routes if r.channel == "gather")
      # seed (item:5291) cheapest = min(ge 27, shop 25) = 25
      assert gather.gold_cost == 25
      assert gather.gold_status == "known"


  def test_ironman_guam_has_no_ge_route_and_gathers_via_shop_seed():
      provider, index = _setup()
      routes = price_routes("item:249", "ironman", provider, index)
      channels = {r.channel for r in routes}
      assert "ge" not in channels  # ge is main-only
      assert "gather" in channels
      gather = next(r for r in routes if r.channel == "gather")
      # iron: seed has no GE route, only the shop (25 coins) -> gather = 25
      assert gather.gold_cost == 25
      assert gather.gold_status == "known"
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_routing_gather.py -q`
  Expected: GREEN (`2 passed`) — gather reuses Task 4's recursion + Task 7's data. If RED, debug the seed shop record shape vs Task 3's schema (systematic-debugging).

- [ ] **7.7 — full suite + commit.**
  Run: `./venv/bin/python -m pytest -q` → all pass.
  ```
  git add tests/cost/test_routing_gather.py
  git commit -m "$(cat <<'EOF'
  test(cost): gather routing divergence -- main GE vs ironman gather-via-shop-seed

  Guam leaf: main has both ge (248) and gather (25); ironman has no ge route,
  gathers via the seed's shop route (25). Divergence emerges from account_allow
  filtering, not special-casing.

  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 8: `spawn` channel — spawns dataset + loader (gold_cost = 0)

Add `data/spawns.json` (a real free item-spawn with locations), replace the `load_spawns` stub, and prove a spawn item's `spawn` route `gold_cost == 0` (the `spawn` pricing branch already exists from Task 4). Hammer `item:2347` is also GE-priced (177) for a main, so the test shows `spawn` (0) is cheaper than the main's `ge` route.

**Files:** `data/spawns.json` (new), `src/osrs_planner/cost/channels.py` (extend: real `load_spawns`), `tests/cost/test_channels_spawn.py` (new), `tests/cost/test_routing_spawn.py` (new).

**Steps:**

- [ ] **8.1 (RED) — spawns loader test.** Create `tests/cost/test_channels_spawn.py`:
  ```python
  # tests/cost/test_channels_spawn.py
  """Task 8: spawn channel -- spawns.json loader + spawn ChannelRecords."""
  from __future__ import annotations

  import os

  from osrs_planner.cost.channels import load_spawns

  SPAWNS = os.path.join(
      os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "spawns.json"
  )


  def test_load_spawns_yields_spawn_records():
      records = load_spawns(SPAWNS)
      by_item = {r.item_id: r for r in records}

      hammer = by_item["item:2347"]
      assert hammer.channel == "spawn"
      assert hammer.currency == "currency:coins"
      assert hammer.amount == 0          # free spawn
      assert hammer.inputs == []         # no inputs for a spawn
      assert hammer.output_qty == 1
      assert hammer.account_allow == frozenset({"main", "ironman", "uim"})
      assert hammer.yield_ == 1
      assert hammer.time is None
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_channels_spawn.py -q`
  Expected RED: `load_spawns` is the empty stub → `KeyError`.

- [ ] **8.2 — create `data/spawns.json`** (hand-curated, wiki-verified):
  ```json
  {
    "_provenance": {
      "dataset": "spawns",
      "description": "Hand-curated, wiki-verified free item-spawn locations for the cost-layer spawn channel. v1 covers a representative free spawn (Hammer); bulk item-spawn sourcing from the OSRS Wiki spawn-location tables is a disclosed v1 follow-up. No live wiki fetch during build.",
      "source_urls": [
        "https://oldschool.runescape.wiki/w/Hammer",
        "https://oldschool.runescape.wiki/w/Item_spawn"
      ],
      "license": "OSRS Wiki content CC BY-NC-SA 3.0",
      "curated": true
    },
    "records": [
      {
        "item_id": "item:2347",
        "name": "Hammer",
        "channel": "spawn",
        "locations": [
          "Lumbridge castle (upstairs)",
          "Barbarian Village (hut)",
          "Dwarven Mine"
        ],
        "count": 1,
        "currency": "currency:coins",
        "source": "Free item spawn",
        "audience": "both",
        "pricing_basis": "spawn",
        "realization_channel": "spawn",
        "requires_ge": false
      }
    ],
    "_excluded": []
  }
  ```

- [ ] **8.3 (GREEN) — replace the `load_spawns` stub in `channels.py`:**
  ```python
  def load_spawns(path: str) -> list[ChannelRecord]:
      """Load data/spawns.json into `spawn` ChannelRecords (gold cost 0)."""
      with open(path, encoding="utf-8") as f:
          payload = json.load(f)
      records: list[ChannelRecord] = []
      for r in payload["records"]:
          records.append(
              ChannelRecord(
                  item_id=r["item_id"],
                  channel="spawn",
                  currency=r["currency"],
                  amount=0,
                  inputs=[],
                  output_qty=r.get("count", 1),
                  account_allow=frozenset({"main", "ironman", "uim"}),
                  source=r["source"],
                  audience=r["audience"],
                  pricing_basis=r["pricing_basis"],
                  realization_channel=r["realization_channel"],
                  requires_ge=r["requires_ge"],
              )
          )
      return records
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_channels_spawn.py -q` → `1 passed`.

- [ ] **8.4 — commit.**
  ```
  git add data/spawns.json src/osrs_planner/cost/channels.py tests/cost/test_channels_spawn.py
  git commit -m "$(cat <<'EOF'
  feat(cost): spawn channel -- spawns.json + load_spawns loader

  Hammer (item:2347) free item spawn. load_spawns replaces the Task 3 stub;
  build_index_from_repo folds spawn records in. Bulk spawn sourcing is a
  disclosed v1 follow-up.

  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  EOF
  )"
  ```

- [ ] **8.5 (RED) — spawn routing test (gold_cost = 0).** Create `tests/cost/test_routing_spawn.py`:
  ```python
  # tests/cost/test_routing_spawn.py
  """Task 8: spawn routing -- a spawn route's gold_cost is 0."""
  from __future__ import annotations

  import os

  from osrs_planner.cost.channels import build_index_from_repo
  from osrs_planner.cost.prices import SnapshotPriceProvider
  from osrs_planner.cost.routing import price_routes

  REPO = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


  def _setup():
      provider = SnapshotPriceProvider.from_file(os.path.join(REPO, "data", "ge_prices.json"))
      index = build_index_from_repo(REPO, provider)
      return provider, index


  def test_spawn_route_gold_cost_is_zero_for_both_families():
      provider, index = _setup()
      for family in ("main", "ironman"):
          routes = price_routes("item:2347", family, provider, index)
          spawn = next(r for r in routes if r.channel == "spawn")
          assert spawn.gold_cost == 0
          assert spawn.gold_status == "known"
          assert spawn.account_allowed is True


  def test_main_hammer_also_has_ge_route_but_spawn_is_free():
      provider, index = _setup()
      routes = price_routes("item:2347", "main", provider, index)
      ge = next(r for r in routes if r.channel == "ge")
      assert ge.gold_cost == 177       # Hammer GE high
      spawn = next(r for r in routes if r.channel == "spawn")
      assert spawn.gold_cost == 0      # spawn is the free alternative
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_routing_spawn.py -q`
  Expected: GREEN (`2 passed`) — the spawn branch exists from Task 4; this proves it on real data.

- [ ] **8.6 — full suite + commit (disclose the residual in the body).**
  Run: `./venv/bin/python -m pytest -q` → all pass.
  ```
  git add tests/cost/test_routing_spawn.py
  git commit -m "$(cat <<'EOF'
  test(cost): spawn routing -- gold_cost 0 for both families

  Hammer spawn route = 0 for main and ironman; main also has a ge route (177),
  spawn is the free alternative. v1 hand-curates only the golden-set + a
  representative sample for craft/gather/spawn; bulk wiki sourcing of all
  recipes/gather/spawns is a disclosed v1 follow-up (no live wiki fetch occurs).

  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 9: Composite goals + strategic-timing notes (`overlay.py`)

Extend `expand_for_account` so a composite goal (Voidwaker assembled from 3 components, or the full Infinity loadout of 5 pieces) resolves through the real KG to its item needs, prices each via `price_routes`, and rolls them up into one `CostCard`. Add the strategic-timing hook: when a `kg` is passed, populate `CostCard.notes` with the downstream goal ids whose requires-tree references this item. TDD against the real `kg/*.json` via `JsonKGStore.from_dir("kg")`.

Real KG facts (verified — see Resolved decisions): Voidwaker `item:27690` requires cond_group 4184444 = AND of 3 ITEM atoms; `gear_loadout_goal:infinity` requires cond_group 4436538 = AND(GEAR_LOADOUT atom + 2 skill atoms), the 5 pieces reached via `composition_of("gear_loadout:infinity")` → 5214366; `item:4587` requires a skill+quest-only group (no item atoms) → leaf. `kg.nodes` is a dict; `kg.edges` is a list; find the requires edge by iterating `kg.edges`. `children_of(group)` returns mixed `ConditionAtom | int`; flatten recursively.

**Files:** `src/osrs_planner/cost/overlay.py` (extend — composite branch + notes hook; do NOT change the single-item branch), `tests/cost/test_overlay_composite.py` (new).

**Steps:**

- [ ] **9.1 RED — composite Voidwaker (main) resolves to its 3 components.** Create `tests/cost/test_overlay_composite.py`:
  ```python
  # tests/cost/test_overlay_composite.py
  """Composite-goal resolution + strategic-timing notes (cost overlay, design §5).

  A composite goal (Voidwaker from 3 components; full Infinity = 5 pieces) is
  resolved through the REAL knowledge graph to its item needs, each priced via
  price_routes, then rolled up into one CostCard. The notes hook records the
  downstream goals an item feeds (KG read-only). All numbers are read from the
  committed snapshot, never hardcoded.
  """
  from __future__ import annotations

  import json
  import os

  import pytest

  from osrs_planner.cost.channels import build_index_from_repo
  from osrs_planner.cost.overlay import expand_for_account
  from osrs_planner.cost.prices import SnapshotPriceProvider
  from osrs_planner.engine.kg.json_store import JsonKGStore
  from osrs_planner.engine.state import AccountState

  REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
  GE_PRICES = os.path.join(REPO, "data", "ge_prices.json")
  KG_DIR = os.path.join(REPO, "kg")

  VOIDWAKER = "item:27690"
  VW_COMPONENTS = ("item:27681", "item:27684", "item:27687")
  INFINITY_GOAL = "gear_loadout_goal:infinity"
  INFINITY_PIECES = ("item:6918", "item:6916", "item:6924", "item:6922", "item:6920")


  @pytest.fixture(scope="module")
  def provider() -> SnapshotPriceProvider:
      return SnapshotPriceProvider.from_file(GE_PRICES)


  @pytest.fixture(scope="module")
  def kg() -> JsonKGStore:
      return JsonKGStore.from_dir(KG_DIR)


  @pytest.fixture(scope="module")
  def index(provider):
      return build_index_from_repo(REPO, provider)


  def _ge_high(item_id: str) -> int | None:
      num = int(item_id.split(":", 1)[1])
      with open(GE_PRICES, encoding="utf-8") as f:
          recs = json.load(f)["records"]
      rec = next((r for r in recs if r["item_id"] == num), None)
      if rec is None or not rec.get("price"):
          return None
      return rec["price"].get("high")


  def test_voidwaker_main_rolls_up_three_components(provider, kg, index):
      state = AccountState(mode="main")
      card = expand_for_account(VOIDWAKER, state, provider, index, kg=kg)
      assert card.item_id == VOIDWAKER
      assert card.account_family == "main"
      assemble = [r for r in card.routes if r.inputs]
      assert assemble, "composite goal must expose an assemble-from-components route"
      inputs = assemble[0].inputs
      assert len(inputs) == len(VW_COMPONENTS)
      expected = {c: _ge_high(c) for c in VW_COMPONENTS}
      got = {comp_id: sub.gold_cost for comp_id, sub in zip(VW_COMPONENTS, inputs)}
      assert got == expected
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_overlay_composite.py::test_voidwaker_main_rolls_up_three_components -q` → RED (`NotImplementedError` for the non-`item:`... wait — VOIDWAKER is an `item:` id, so the single-item branch returns no assemble route → the `assemble` assertion fails). Either way, RED until 9.3.

- [ ] **9.3 GREEN — add composite resolution + notes hook to `overlay.py`.** Append the helpers and extend `expand_for_account`. The composite branch runs for ANY goal whose requires-tree carries item/gear_loadout atoms (including an `item:` goal like Voidwaker that ALSO has a direct route), so the single-item path stays the fallback. Add at the top of `overlay.py` (after the existing imports):
  ```python
  from osrs_planner.cost.cards import Route
  from osrs_planner.engine.kg.model import AtomType, EdgeType
  ```
  Add these module-level helpers:
  ```python
  def _requires_group(kg, node_id: str) -> int | None:
      """The cond_group of node_id's REQUIRES edge (mirrors store.composition_of)."""
      for e in kg.edges:
          if e.type is EdgeType.REQUIRES and e.src == node_id and e.cond_group is not None:
              return e.cond_group
      return None


  def _item_needs(kg, group_id: int, _seen=None) -> list[tuple[str, int]]:
      """Flatten an AND/OR group to (item_id, qty) needs.

      item atoms -> (ref_node, qty or 1); gear_loadout atoms -> expand via
      composition_of(ref_node); nested sub-groups (int children) recurse.
      """
      _seen = _seen if _seen is not None else set()
      if group_id in _seen:
          return []
      _seen.add(group_id)
      needs: list[tuple[str, int]] = []
      for child in kg.children_of(group_id):
          if isinstance(child, int):
              needs.extend(_item_needs(kg, child, _seen))
          elif child.atom_type is AtomType.ITEM:
              needs.append((child.ref_node, child.qty or 1))
          elif child.atom_type is AtomType.GEAR_LOADOUT:
              needs.extend(_item_needs(kg, kg.composition_of(child.ref_node), _seen))
      return needs


  def _downstream_goals(kg, item_id: str) -> list[str]:
      """Goal ids whose requires-tree references item_id (strategic-timing hook)."""
      out: list[str] = []
      for node in kg.nodes.values():
          gid = node.id
          if gid == item_id:
              continue
          grp = _requires_group(kg, gid)
          if grp is None:
              continue
          if item_id in {iid for iid, _ in _item_needs(kg, grp)}:
              out.append(gid)
      return sorted(set(out))
  ```
  Now rewrite `expand_for_account`'s body so it tries the composite branch first when a `kg` is supplied:
  ```python
  def expand_for_account(
      goal_id: str,
      state: AccountState,
      provider: PriceProvider,
      index: dict[str, list[ChannelRecord]],
      kg=None,
  ) -> CostCard:
      family = account_family(state.mode)
      name = _resolve_name(goal_id, kg)

      grp = _requires_group(kg, goal_id) if kg is not None else None
      needs = _item_needs(kg, grp) if grp is not None else []

      if needs:
          # Composite: resolve to item needs, price each, roll up.
          component_routes: list[Route] = []
          total = 0
          all_known = True
          for item_id, qty in needs:
              sub = price_routes(item_id, family, provider, index)
              ranked = sorted(
                  sub,
                  key=lambda r: (r.gold_status == "unavailable" or r.gold_cost is None,
                                 r.gold_cost if r.gold_cost is not None else 0),
              )
              chosen = ranked[0] if ranked else Route(
                  channel="none", currency="currency:coins", gold_cost=None,
                  gold_status="unavailable", account_allowed=False, source="kg",
                  notes=[f"no {family}-allowed route for {item_id}"],
              )
              component_routes.append(chosen)
              if chosen.gold_status == "known" and chosen.gold_cost is not None:
                  total += chosen.gold_cost * qty
              else:
                  all_known = False
          assemble = Route(
              channel="craft", currency="currency:coins",
              gold_cost=total if all_known else None,
              gold_status="known" if all_known else "unavailable",
              inputs=component_routes, account_allowed=True, source="kg-composition",
          )
          # plus any direct route for the assembled item itself (e.g. main GE).
          direct = price_routes(goal_id, family, provider, index) if goal_id.startswith("item:") else []
          routes = direct + [assemble]
          notes = _downstream_goals(kg, goal_id) if kg is not None else []
          return CostCard(
              item_id=goal_id, name=name, account_family=family, routes=routes,
              rankings={"by_gold": rank_by_gold(routes), "by_time": []},
              notes=notes, gold_status=roll_up_gold_status(routes),
          )

      if goal_id.startswith("item:"):
          routes = price_routes(goal_id, family, provider, index)
          notes = []
          if not routes:
              notes.append(f"No {family}-allowed acquisition channel for {goal_id}.")
          if kg is not None:
              notes.extend(_downstream_goals(kg, goal_id))
          return CostCard(
              item_id=goal_id, name=name, account_family=family, routes=routes,
              rankings={"by_gold": rank_by_gold(routes), "by_time": []},
              notes=notes, gold_status=roll_up_gold_status(routes),
          )

      raise NotImplementedError(f"goal {goal_id} has no item needs and is not an item: id")
  ```
  NOTE: `rank_by_gold` already pushes the unavailable assemble route last and the priced direct GE route first, so Voidwaker (direct GE 40512000 vs assemble-from-components 38849997) lists BOTH and ranks the cheaper one first — never collapsed.
  Run: `./venv/bin/python -m pytest tests/cost/test_overlay_composite.py::test_voidwaker_main_rolls_up_three_components -q` → `1 passed`.

- [ ] **9.5 RED — ironman Voidwaker has NO direct GE route, only assemble.** Append:
  ```python
  def test_voidwaker_ironman_has_no_ge_direct_route(provider, kg, index):
      state = AccountState(mode="ironman")
      card = expand_for_account(VOIDWAKER, state, provider, index, kg=kg)
      direct_ge = [r for r in card.routes if r.channel == "ge" and not r.inputs]
      assert direct_ge == []
      assemble = [r for r in card.routes if r.inputs]
      assert assemble and len(assemble[0].inputs) == len(VW_COMPONENTS)
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_overlay_composite.py::test_voidwaker_ironman_has_no_ge_direct_route -q` → GREEN (divergence emerges from `account_allow` filtering in `price_routes`). If RED because `direct` includes a ge route for an ironman, the bug is in `price_routes` family filtering — fix there, not here.

- [ ] **9.7 RED — full Infinity (5 pieces) via composition_of + skeleton lock.** Append:
  ```python
  def test_full_infinity_rolls_up_five_pieces(provider, kg, index):
      state = AccountState(mode="main")
      card = expand_for_account(INFINITY_GOAL, state, provider, index, kg=kg)
      assemble = [r for r in card.routes if r.inputs]
      assert assemble, "loadout goal must expose a roll-up route"
      assert len(assemble[0].inputs) == len(INFINITY_PIECES)
      assert card.rankings["by_time"] == []  # skeleton stays empty
      for r in card.routes:
          assert r.time_status == "not_estimated"
      expected_total = sum(_ge_high(p) for p in INFINITY_PIECES)
      assert assemble[0].gold_cost == expected_total
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_overlay_composite.py::test_full_infinity_rolls_up_five_pieces -q` → GREEN (`_item_needs` expands the `gear_loadout` atom in 4436538 via `composition_of`). Note: `INFINITY_GOAL` is NOT an `item:` id, so `direct` is empty and the only route is the assemble route.

- [ ] **9.9 RED — strategic-timing notes hook.** Append:
  ```python
  def test_notes_records_downstream_goals_when_kg_passed(provider, kg, index):
      state = AccountState(mode="main")
      card = expand_for_account("item:27681", state, provider, index, kg=kg)
      assert VOIDWAKER in card.notes  # a Voidwaker component feeds the Voidwaker goal


  def test_notes_empty_without_kg(provider, index):
      state = AccountState(mode="main")
      card = expand_for_account("item:4587", state, provider, index, kg=None)
      assert card.notes == []
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_overlay_composite.py -q` → all pass.

- [ ] **9.11 Full cost suite + full suite green.**
  Run: `./venv/bin/python -m pytest tests/cost -q` then `./venv/bin/python -m pytest -q` → all pass (no Tasks 1–8 regression).

- [ ] **9.12 Commit:**
  ```
  git add src/osrs_planner/cost/overlay.py tests/cost/test_overlay_composite.py
  git commit -m "$(cat <<'EOF'
  feat(cost): composite-goal roll-up + strategic-timing notes hook

  Resolve a composite goal (Voidwaker from 3 components; full Infinity = 5 pieces
  via composition_of) through the real KG to its item needs, price each via
  price_routes, roll up into one CostCard with an assemble-from-components route
  alongside any direct route. notes carries downstream goals an item feeds when a
  kg is passed (else []). Divergence (no ironman GE-direct route) emerges from
  account_allow filtering, not special-casing.

  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 10: `data/validate_cost.py` — committed cost-data validator

A committed validator (iron-gate tradition) that enforces the cost-layer data invariants and exits non-zero on any violation. Mirrors `data/validate_iron_gate.py` (errors list, `check()`, `sys.exit(1)`, summary on pass). It is THE gate for the hand-curated channel datasets and the cost-free-KG guarantee; the item→channels index is built in-memory at load so there is no committed derived artifact and thus NO freshness-guard for the index.

Invariants (design §8.1):
1. Every channel record's `item_id` resolves in `data/item_dictionary.json`.
2. Every `currency` ref resolves in `data/currencies.json`.
3. `craft`/`gather` `inputs` item_ids resolve in `item_dictionary.json`.
4. Gate coherence: no `ge` channel is iron-eligible (the synthetic ge record is main-only by construction; this validator asserts that any dataset row claiming `channel="ge"` has `requires_ge=True` and `account_allow=={"main"}`).
5. KG stays cost-free: no `"price"`/`"cost"`/`"currency"` token appears in `kg/*.json`. (This is a raw-text substring guard — verified zero matches on the current KG. If a future KG node ever legitimately needs a field literally named `price`/`cost`/`currency`, relax this to a structured key check; leave a comment saying so.)
6. Shop `currency` values join to `currencies.json`.

**Files:** `data/validate_cost.py` (new, executable), `tests/cost/test_validate_cost.py` (new — runs the validator on committed data; constructed-broken fixtures in tmp dirs, never mutating frozen committed JSON).

**Steps:**

- [ ] **10.1 RED — validator exits 0 on committed data.** Create `tests/cost/test_validate_cost.py`:
  ```python
  # tests/cost/test_validate_cost.py
  """validate_cost.py runs clean on committed data; constructed-broken inputs fail.

  Negative fixtures are CONSTRUCTED in tmp dirs (never mutate the frozen committed
  JSON). The committed datasets are hand-curated, wiki-verified source-of-truth
  covering the golden-set goals + a small representative sample; bulk wiki sourcing
  is a disclosed v1 follow-up.
  """
  from __future__ import annotations

  import json
  import os
  import subprocess
  import sys

  REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
  VALIDATOR = os.path.join(REPO, "data", "validate_cost.py")
  PY = sys.executable


  def _run(*args):
      return subprocess.run([PY, VALIDATOR, *args], capture_output=True, text=True)


  def test_validator_passes_on_committed_data():
      r = _run()
      assert r.returncode == 0, f"validate_cost failed on committed data:\n{r.stdout}\n{r.stderr}"
      assert "COST VALIDATION PASSED" in r.stdout
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_validate_cost.py::test_validator_passes_on_committed_data -q` → RED (no `data/validate_cost.py`).

- [ ] **10.3 GREEN — write `data/validate_cost.py`** (datasets/kg resolved from configurable `--data`/`--kg` roots so negative fixtures can point at a tmp dir):
  ```python
  #!/usr/bin/env python3
  """Cost-layer data validator (iron-gate tradition; design §8.1).

  Exits non-zero if any cost-data invariant is violated so it can run in CI /
  pre-commit. The committed channel datasets are HAND-CURATED, wiki-verified
  source-of-truth covering the golden-set goals + a small representative sample;
  BULK WIKI SOURCING IS A DISCLOSED v1 FOLLOW-UP. The item->channels index is
  built in-memory at load (no committed derived artifact) so this validator is the
  sole gate -- there is no index freshness-guard to run.

  Invariants:
    1. Every channel record item_id resolves in item_dictionary.json.
    2. Every currency ref resolves in currencies.json.
    3. craft/gather input item_ids resolve in item_dictionary.json.
    4. Gate coherence: no `ge` channel is iron-eligible
       (ge record => requires_ge True AND account_allow == {"main"}).
    5. KG stays cost-free: no price/cost/currency token in kg/*.json.
    6. Shop currency values join to currencies.json.

  Usage: python3 data/validate_cost.py [--data DATA_DIR] [--kg KG_DIR]
  """
  import argparse
  import glob
  import json
  import os
  import re
  import sys

  errors: list[str] = []


  def check(cond, msg):
      if not cond:
          errors.append(msg)


  def load(path):
      with open(path, encoding="utf-8") as f:
          return json.load(f)


  def item_num(item_id):
      if isinstance(item_id, int):
          return item_id
      if isinstance(item_id, str) and item_id.startswith("item:"):
          try:
              return int(item_id.split(":", 1)[1])
          except ValueError:
              return None
      return None


  def main() -> int:
      here = os.path.dirname(os.path.abspath(__file__))
      repo = os.path.dirname(here)
      ap = argparse.ArgumentParser()
      ap.add_argument("--data", default=here)
      ap.add_argument("--kg", default=os.path.join(repo, "kg"))
      ns = ap.parse_args()
      data, kg = ns.data, ns.kg

      # --- resolution sets ---
      idict = load(os.path.join(data, "item_dictionary.json"))
      item_ids = {r["item_id"] for r in idict["records"]}
      cur_doc = load(os.path.join(data, "currencies.json"))
      cur_ids = {c["id"] for c in cur_doc["records"]}

      # --- channel datasets (those present; coverage is a disclosed follow-up) ---
      CHANNEL_FILES = {
          "shop": "shop_prices.json",
          "craft": "recipes.json",
          "gather": "gather.json",
          "spawn": "spawns.json",
      }
      n_channel_records = 0
      for channel, fname in CHANNEL_FILES.items():
          fpath = os.path.join(data, fname)
          if not os.path.exists(fpath):
              continue
          doc = load(fpath)
          for rec in doc["records"]:
              n_channel_records += 1
              iid = (
                  rec.get("item_id")
                  or rec.get("output_item_id")
                  or rec.get("resource_item_id")
              )
              num = item_num(iid)
              check(num in item_ids, f"[{channel}] item_id does not resolve: {iid}")
              cur = rec.get("currency", "currency:coins")
              check(cur in cur_ids, f"[{channel}] currency ref does not resolve: {cur}")
              for inp in (rec.get("inputs") or []):
                  in_id = inp["item_id"] if isinstance(inp, dict) else inp[0]
                  check(
                      item_num(in_id) in item_ids,
                      f"[{channel}] input item_id does not resolve: {in_id}",
                  )
              if rec.get("channel") == "ge":
                  allow = set(rec.get("account_allow") or [])
                  check(rec.get("requires_ge") is True, f"[ge] record not requires_ge=True: {iid}")
                  check(allow == {"main"}, f"[ge] channel marked iron-eligible: {iid} allow={sorted(allow)}")

      # --- KG stays cost-free ---
      COST_TOKENS = re.compile(r'"(price|cost|currency)"', re.I)
      for kgf in sorted(glob.glob(os.path.join(kg, "*.json"))):
          with open(kgf, encoding="utf-8") as f:
              raw = f.read()
          m = COST_TOKENS.search(raw)
          check(m is None, f"[kg] cost token leaked into {os.path.basename(kgf)}: {m.group(0) if m else ''}")

      # --- report ---
      if errors:
          print(f"COST VALIDATION FAILED -- {len(errors)} violation(s):")
          for e in errors[:50]:
              print("  -", e)
          if len(errors) > 50:
              print(f"  ... and {len(errors) - 50} more")
          return 1
      print("COST VALIDATION PASSED -- all cost-data invariants hold.")
      print(f"  item_dictionary: {len(item_ids)} resolvable item_ids")
      print(f"  currencies: {len(cur_ids)} ids")
      print(f"  channel records validated: {n_channel_records}")
      print("  NOTE: hand-curated golden-set + sample coverage; bulk wiki sourcing is a v1 follow-up.")
      return 0


  if __name__ == "__main__":
      sys.exit(main())
  ```

- [ ] **10.4 Run GREEN:** `chmod +x data/validate_cost.py && ./venv/bin/python data/validate_cost.py` → exit 0, prints `COST VALIDATION PASSED`. Then `./venv/bin/python -m pytest tests/cost/test_validate_cost.py::test_validator_passes_on_committed_data -q` → `1 passed`.

- [ ] **10.5 RED — negative fixtures.** Append to `tests/cost/test_validate_cost.py`:
  ```python
  def _make_broken_root(tmp_path, *, shop_records=None, kg_text=None):
      """Construct a minimal broken data+kg root (never touch committed files)."""
      data = tmp_path / "data"
      kgd = tmp_path / "kg"
      data.mkdir()
      kgd.mkdir()
      (data / "item_dictionary.json").write_text(json.dumps(
          {"records": [{"item_id": 4587, "name": "Dragon scimitar"}]}))
      (data / "currencies.json").write_text(json.dumps(
          {"records": [{"id": "currency:coins", "name": "Coins"}]}))
      (data / "shop_prices.json").write_text(json.dumps(
          {"records": shop_records if shop_records is not None else []}))
      (kgd / "nodes.json").write_text(kg_text if kg_text is not None else "[]")
      return str(data), str(kgd)


  def test_unresolvable_item_id_fails(tmp_path):
      d, k = _make_broken_root(tmp_path, shop_records=[
          {"channel": "shop", "item_id": "item:99999999", "currency": "currency:coins",
           "amount": 1, "account_allow": ["main", "ironman", "uim"], "requires_ge": False}])
      r = _run("--data", d, "--kg", k)
      assert r.returncode == 1
      assert "does not resolve" in r.stdout


  def test_unresolvable_currency_fails(tmp_path):
      d, k = _make_broken_root(tmp_path, shop_records=[
          {"channel": "shop", "item_id": "item:4587", "currency": "currency:bogus",
           "amount": 1, "account_allow": ["main", "ironman", "uim"], "requires_ge": False}])
      r = _run("--data", d, "--kg", k)
      assert r.returncode == 1
      assert "currency ref does not resolve" in r.stdout


  def test_ge_channel_marked_iron_eligible_fails(tmp_path):
      d, k = _make_broken_root(tmp_path, shop_records=[
          {"channel": "ge", "item_id": "item:4587", "currency": "currency:coins",
           "amount": 1, "account_allow": ["main", "ironman"], "requires_ge": True}])
      r = _run("--data", d, "--kg", k)
      assert r.returncode == 1
      assert "iron-eligible" in r.stdout


  def test_cost_token_in_kg_fails(tmp_path):
      d, k = _make_broken_root(
          tmp_path, shop_records=[],
          kg_text=json.dumps([{"id": "item:4587", "kind": "item", "data": {"price": 60000}}]))
      r = _run("--data", d, "--kg", k)
      assert r.returncode == 1
      assert "cost token leaked" in r.stdout
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_validate_cost.py -q` → all pass. (If a negative test passes the validator unexpectedly, the invariant branch is wrong — fix `validate_cost.py`, not the test.)

- [ ] **10.7 Document in BUILD.md.** With a single `Edit`, append a section to `data/BUILD.md` noting `data/validate_cost.py` enforces the cost-layer invariants and that channel-dataset coverage is the golden-set + representative sample (bulk wiki sourcing = disclosed v1 follow-up).

- [ ] **10.8 Commit:**
  ```
  git add data/validate_cost.py tests/cost/test_validate_cost.py data/BUILD.md
  git commit -m "$(cat <<'EOF'
  feat(cost): data/validate_cost.py committed validator + negative fixtures

  Enforces the six cost-data invariants (item_id/currency/input resolution, no
  iron-eligible ge channel, cost-free KG, shop currency join). Exits 0 on
  committed data; constructed-broken fixtures (never mutated-frozen) cover each
  failure. Channel coverage = golden-set + representative sample; bulk wiki
  sourcing is a disclosed v1 follow-up.

  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Task 11: Golden cost-set + cost demo runner

End-to-end golden tests over the REAL datasets (`SnapshotPriceProvider` + `JsonKGStore` + `build_index_from_repo`) proving the flagship divergences, the craft recursion, and the composite roll-ups — each asserting the FULL route set + `by_gold`, never a collapsed winner. Numbers are READ from the snapshot. Plus a demo runner and a full-suite-green gate.

> **Note (handled, not a bug):** `item:121` (Attack potion) and `item:2347` (Hammer) are priced via the channel index but are NOT KG nodes, so their `CostCard.name` resolves to the raw id (e.g. `"item:121"`); the demo's printed label comes from its hardcoded `GOALS` list, not the KG. `_downstream_goals` only iterates existing `kg.nodes`, so the notes-hook path is safe. Don't mistake the raw-id name for a failure — no test asserts a KG name for these two.

**Files:** `tests/cost/test_golden_cost.py` (new), `scripts/cost_demo.py` (new).

**Steps:**

- [ ] **11.1 RED — scimitar main=GE vs iron=shop.** Create `tests/cost/test_golden_cost.py`:
  ```python
  # tests/cost/test_golden_cost.py
  """Golden cost-set over REAL datasets (design §8.2 / §10).

  Each test asserts the FULL route set + by_gold ranking -- never a single
  collapsed winner (enforces no-auto-pick). Numeric expectations are READ from the
  committed snapshot at runtime, so a price refresh never breaks the structural
  contract. Datasets are hand-curated, wiki-verified source-of-truth covering the
  golden-set goals + a representative sample; bulk wiki sourcing is a disclosed v1
  follow-up.
  """
  from __future__ import annotations

  import json
  import os

  import pytest

  from osrs_planner.cost.channels import build_index_from_repo
  from osrs_planner.cost.overlay import expand_for_account
  from osrs_planner.cost.prices import SnapshotPriceProvider
  from osrs_planner.engine.kg.json_store import JsonKGStore
  from osrs_planner.engine.state import AccountState

  REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
  GE_PRICES = os.path.join(REPO, "data", "ge_prices.json")
  KG_DIR = os.path.join(REPO, "kg")

  SCIMITAR = "item:4587"
  OBBY_MAUL = "item:6528"
  ATTACK_POTION = "item:121"
  VOIDWAKER = "item:27690"
  INFINITY_GOAL = "gear_loadout_goal:infinity"


  @pytest.fixture(scope="module")
  def provider():
      return SnapshotPriceProvider.from_file(GE_PRICES)


  @pytest.fixture(scope="module")
  def kg():
      return JsonKGStore.from_dir(KG_DIR)


  @pytest.fixture(scope="module")
  def index(provider):
      return build_index_from_repo(REPO, provider)


  def _ge_high(item_id: str):
      num = int(item_id.split(":", 1)[1])
      with open(GE_PRICES, encoding="utf-8") as f:
          recs = json.load(f)["records"]
      rec = next((r for r in recs if r["item_id"] == num), None)
      if rec is None or not rec.get("price"):
          return None
      return rec["price"].get("high")


  def test_scimitar_main_lists_ge_and_shop_ge_ranks_first(provider, kg, index):
      card = expand_for_account(SCIMITAR, AccountState(mode="main"), provider, index, kg=kg)
      channels = {r.channel for r in card.routes}
      assert "ge" in channels and "shop" in channels
      ge = next(r for r in card.routes if r.channel == "ge")
      shop = next(r for r in card.routes if r.channel == "shop")
      assert ge.gold_cost == _ge_high(SCIMITAR)
      assert shop.gold_cost > ge.gold_cost
      assert card.routes[card.rankings["by_gold"][0]].channel == "ge"
      assert len(card.rankings["by_gold"]) == len(card.routes)


  def test_scimitar_ironman_only_shop_no_ge(provider, kg, index):
      card = expand_for_account(SCIMITAR, AccountState(mode="ironman"), provider, index, kg=kg)
      channels = {r.channel for r in card.routes}
      assert "ge" not in channels
      assert "shop" in channels
      shop = next(r for r in card.routes if r.channel == "shop")
      assert shop.currency == "currency:coins"
      assert shop.gold_cost > 0
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_golden_cost.py -q` → passes once the scimitar shop row + ge wiring resolve (they do from Tasks 3–5). Expected GREEN: `2 passed`.

- [ ] **11.4 RED — obby maul ironman in Tokkul.** Append:
  ```python
  def test_obby_maul_ironman_priced_in_tokkul(provider, kg, index):
      card = expand_for_account(OBBY_MAUL, AccountState(mode="ironman"), provider, index, kg=kg)
      channels = {r.channel for r in card.routes}
      assert "ge" not in channels
      shop = next(r for r in card.routes if r.channel == "shop")
      assert shop.currency == "currency:tokkul"     # non-coin currency surfaces
      assert shop.gold_cost is None                 # coins-only -> None for tokkul
      assert shop.amount == 75001                   # face figure, in tokkul
      assert shop.gold_status == "known"
      assert shop.time_status == "not_estimated"


  def test_obby_maul_main_lists_ge_and_tokkul_shop(provider, kg, index):
      card = expand_for_account(OBBY_MAUL, AccountState(mode="main"), provider, index, kg=kg)
      channels = {r.channel for r in card.routes}
      assert "ge" in channels and "shop" in channels
      ge = next(r for r in card.routes if r.channel == "ge")
      assert ge.gold_cost == _ge_high(OBBY_MAUL)
      # Tokkul trap fixed: by_gold[0] is the GE COIN route, not the tokkul shop.
      assert card.routes[card.rankings["by_gold"][0]].channel == "ge"
  ```
  NOTE on the Tokkul figure (implemented model, spec §11): `gold_cost` means **coins only** (the coin-equivalent), and is `None` for any non-coin currency. The figure in the route's own `currency` lives in `Route.amount`. For the obby maul shop route that is `gold_cost=None`, `amount=75001`, `currency=currency:tokkul`, `gold_status="known"` (a tokkul shop buy IS a known acquisition — just not coin-priced). Because the tokkul route has `gold_cost=None`, `rank_by_gold` sorts it last (it sorts `gold_cost is None` last), so for a main `by_gold[0]` is the 215,000-coin GE route — the cross-currency face-amount comparison spec §11 forbids never happens. (The earlier draft of this NOTE described stuffing the tokkul amount into `gold_cost`; that WAS the §11 "Tokkul trap" and is what this model removes — `by_gold` ranks coins only and a tokkul figure is never compared to a coin figure.) `currency:tokkul` must exist in `data/currencies.json` (Task 2, `self_earned_only:true`).
  Run: `./venv/bin/python -m pytest tests/cost/test_golden_cost.py -k obby -q` → GREEN.

- [ ] **11.6 RED — Attack potion craft recursion (main GE inputs vs iron gather inputs).** Append:
  ```python
  def test_attack_potion_craft_recurses_into_inputs_main(provider, kg, index):
      card = expand_for_account(ATTACK_POTION, AccountState(mode="main"), provider, index, kg=kg)
      craft = next(r for r in card.routes if r.channel == "craft")
      assert craft.inputs, "craft route must expose recursive input sub-routes"
      assert any(sub.gold_cost is not None for sub in craft.inputs)
      assert craft.gold_status in ("known", "partial")
      # unf cheapest (252) + eye of newt ge (5) = 257
      assert craft.gold_cost == 257


  def test_attack_potion_inputs_diverge_for_ironman(provider, kg, index):
      card = expand_for_account(ATTACK_POTION, AccountState(mode="ironman"), provider, index, kg=kg)
      craft = next(r for r in card.routes if r.channel == "craft")
      # ironman input sub-routes never draw from ge (ge is main-only).
      sub_channels = {s.channel for s in craft.inputs}
      assert "ge" not in sub_channels
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_golden_cost.py -k potion -q` → GREEN. (Attack potion(3) `item:121` and its chain are in `recipes.json`/`gather.json`; the ironman path bottoms out at the Guam seed shop route, never ge.)

- [ ] **11.8 RED — Voidwaker + full Infinity full-route-set assertions.** Append:
  ```python
  def test_voidwaker_main_full_route_set_and_ranking(provider, kg, index):
      card = expand_for_account(VOIDWAKER, AccountState(mode="main"), provider, index, kg=kg)
      direct_ge = [r for r in card.routes if r.channel == "ge" and not r.inputs]
      assemble = [r for r in card.routes if r.inputs]
      assert direct_ge and assemble               # full set, never collapsed
      assert len(assemble[0].inputs) == 3
      assert len(card.rankings["by_gold"]) == len(card.routes)
      comps = ("item:27681", "item:27684", "item:27687")
      assert assemble[0].gold_cost == sum(_ge_high(c) for c in comps)


  def test_full_infinity_five_pieces_sum(provider, kg, index):
      card = expand_for_account(INFINITY_GOAL, AccountState(mode="main"), provider, index, kg=kg)
      assemble = next(r for r in card.routes if r.inputs)
      pieces = ("item:6918", "item:6916", "item:6924", "item:6922", "item:6920")
      assert len(assemble.inputs) == 5
      assert assemble.gold_cost == sum(_ge_high(p) for p in pieces)
      assert card.rankings["by_time"] == []       # skeleton stays empty
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_golden_cost.py -q` → all golden tests pass.

- [ ] **11.10 Cost demo runner.** Create `scripts/cost_demo.py`:
  ```python
  #!/usr/bin/env python3
  """Cost-layer demo: golden goals x account family (read-only over committed data).

  Run: ./venv/bin/python scripts/cost_demo.py
  Prints the full CostCard route set + by_gold ranking for each golden goal under
  both a main and an ironman -- the flagship divergences, no auto-pick.
  """
  from __future__ import annotations

  import os

  from osrs_planner.cost.channels import build_index_from_repo
  from osrs_planner.cost.overlay import expand_for_account
  from osrs_planner.cost.prices import SnapshotPriceProvider
  from osrs_planner.engine.kg.json_store import JsonKGStore
  from osrs_planner.engine.state import AccountState

  REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
  GOALS = [
      ("Dragon scimitar", "item:4587"),
      ("Tzhaar-ket-om (obby maul)", "item:6528"),
      ("Attack potion(3)", "item:121"),
      ("Voidwaker", "item:27690"),
      ("Full Infinity", "gear_loadout_goal:infinity"),
  ]


  def fmt_gold(r):
      return f"{r.gold_cost:,} {r.currency}" if r.gold_cost is not None else f"{r.gold_status} ({r.currency})"


  def main():
      provider = SnapshotPriceProvider.from_file(os.path.join(REPO, "data", "ge_prices.json"))
      kg = JsonKGStore.from_dir(os.path.join(REPO, "kg"))
      index = build_index_from_repo(REPO, provider)
      for name, goal_id in GOALS:
          print(f"\n=== {name} ({goal_id}) ===")
          for mode in ("main", "ironman"):
              card = expand_for_account(goal_id, AccountState(mode=mode), provider, index, kg=kg)
              print(f"  [{mode}] gold_status={card.gold_status} routes={len(card.routes)}")
              for rank, i in enumerate(card.rankings["by_gold"]):
                  r = card.routes[i]
                  tag = " (cheapest gold)" if rank == 0 else ""
                  extra = f"  inputs={len(r.inputs)}" if r.inputs else ""
                  print(f"    - {r.channel:>5}: {fmt_gold(r)}{extra}{tag}")
              if card.notes:
                  print(f"    notes (downstream goals): {card.notes}")


  if __name__ == "__main__":
      main()
  ```

- [ ] **11.11 Run the demo:** `./venv/bin/python scripts/cost_demo.py` → prints all five goals × {main, ironman}; eyeball that scimitar main shows ge cheapest / ironman shop-only; obby maul ironman shows the tokkul route; Voidwaker shows both direct + assemble. (No auto-open; user refreshes manually.)

- [ ] **11.12 Full suite green (gate):** `./venv/bin/python -m pytest -q` from repo root → ALL tests pass (engine + cost + existing). The cost layer is additive — zero engine regressions.

- [ ] **11.13 Boundary guard — engine never imports cost (import-walk).** Append to `tests/cost/test_golden_cost.py`:
  ```python
  def test_engine_never_imports_cost():
      import importlib
      import pkgutil

      import osrs_planner.engine as eng

      bad = []
      for mod in pkgutil.walk_packages(eng.__path__, eng.__name__ + "."):
          spec = importlib.util.find_spec(mod.name)
          src_file = spec.origin if spec else None
          if not src_file or not src_file.endswith(".py"):
              continue
          with open(src_file, encoding="utf-8") as f:
              text = f.read()
          if "osrs_planner.cost" in text or "from osrs_planner import cost" in text:
              bad.append(mod.name)
      assert bad == [], f"engine modules import cost (one-way boundary violated): {bad}"
  ```
  Run: `./venv/bin/python -m pytest tests/cost/test_golden_cost.py::test_engine_never_imports_cost -q` → `1 passed`.

- [ ] **11.15 Commit:**
  ```
  git add tests/cost/test_golden_cost.py scripts/cost_demo.py
  git commit -m "$(cat <<'EOF'
  feat(cost): golden cost-set over real data + demo runner + boundary guard

  Scimitar main=GE vs iron=shop; obby maul main lists ge+tokkul-shop, iron=tokkul;
  Attack potion craft recursion (main GE inputs vs iron gather, never ge);
  Voidwaker direct+assemble; full Infinity 5-piece sum. Every test asserts the
  FULL route set + by_gold, never a collapsed winner; numbers read from the
  snapshot. Plus a cost_demo runner and an import-walk guard that engine never
  imports cost.

  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  EOF
  )"
  ```

---

## Done criteria

1. `expand_for_account(goal_id, state, provider, index, kg=None)` returns a `CostCard` listing ALL viable routes for the account family, with a `by_gold` ranking, for every golden-set goal (scimitar, obby maul, Attack potion, Voidwaker, full Infinity). It never names a single "best".
2. The flagship divergence holds on real data: scimitar main `by_gold[0]`=GE (60748), ironman=shop (100000); obby maul main lists ge + tokkul shop, ironman=tokkul shop (75001 in `currency:tokkul`, surfaced as a non-coin currency).
3. A potion's `craft` route recurses into inputs (Attack potion(3) = 257 for a main); the ironman input sub-routes never draw from `ge`.
4. Composite goals roll up via the real KG: Voidwaker = 3 components + a direct GE route (both listed); full Infinity = 5 pieces via `composition_of`. The `notes` strategic-timing hook lists downstream goals when a kg is passed (`[]` otherwise).
5. `data/validate_cost.py` exits 0 on committed data and exits 1 on each constructed-broken fixture (unresolvable item_id / currency, iron-eligible ge channel, cost token in KG).
6. The KG remains cost-free; `engine` does not import `cost` (asserted by two boundary tests: a text scan in Task 4 and an import-walk in Task 11).
7. All skeleton slots are wired and locked empty/default: `Currency.earn_rate_per_hour` null, `ChannelRecord.yield_`/`time`, `Route.time_status="not_estimated"`, `CostCard.rankings["by_time"]==[]`, `price_routes(..., owned=...)` threaded-unused.
8. The full suite stays green; the cost layer is purely additive (304 baseline + the new cost tests, zero engine/kg regressions). Run with `./venv/bin/python -m pytest`.

**Disclosed v1 follow-ups (not blockers):** bulk wiki sourcing of `shop_prices`/`recipes`/`gather`/`spawns`/`currencies` (golden-set + representative sample only in v1); `LivePriceProvider` + daily-refresh job; reading player balances/inventory (`owned` subtraction); non-coin→time normalization; `drop`/`quest_reward`/`activity_reward` channels (incl. probabilistic rewards); time/long-term ranking dimensions; account-state cost modifiers (diary/glove discounts, e.g. obby maul 65,001 with Karamja gloves).
