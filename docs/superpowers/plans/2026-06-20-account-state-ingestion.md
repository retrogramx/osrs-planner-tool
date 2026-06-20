# Account-State Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest a player's real account state — bank (Bank Memory TSV) + collection log (TempleOSRS API) — into the engine's `AccountState`, plus a bank-value figure.

**Architecture:** A new independent package `src/osrs_planner/account/` (`bank.py` parser+value, `temple.py` clog client/parser, `state.py` combiner) that imports only `engine.state` (`AccountState`) + `cost.prices` (`PriceProvider`, a leaf). One engine touch: a defaulted `AccountState.clog_obtained` set. Personal data is a RUNTIME input (synthetic fixtures only); network lives solely in the Temple fetch.

**Tech Stack:** Python 3 (stdlib `json`/`urllib`), pytest. Reuses `cost.prices.SnapshotPriceProvider`.

## Global Constraints

- **Personal data is NEVER committed.** Bank TSV / Temple responses are runtime inputs; tests use small SYNTHETIC fixtures (`tests/account/fixtures/`).
- **IDs are KG-style `"item:<n>"` strings** (to match `AccountState.counts` + the engine's `atom.ref_node`). The TSV/Temple sources use bare integer ids → the parsers prefix `"item:"`.
- **Never fabricate value:** an item the `PriceProvider` can't price contributes 0 and is counted in `unpriced_count` (absence ≠ a real 0).
- **Boundary:** `account/` imports ONLY `osrs_planner.engine.state`, `osrs_planner.cost.prices`, and stdlib. It must NOT import the overlay logic — `osrs_planner.income.*`, `osrs_planner.cost.overlay`/`.routing`/`.channels`/`.cards`/`.currency`. `cost.prices` IS allowed (a leaf). The KG (`kg/*.json`) is untouched.
- **Engine change is backward-compatible:** add `clog_obtained: set[str] = field(default_factory=set)` to `AccountState` (defaulted ⇒ all existing constructions + tests keep working).
- **Temple API:** `GET https://templeosrs.com/api/collection-log/player_collection_log.php?player=<urlenc>&categories=all` → `{"data": {"game_mode", "total_collections_finished", "total_collections_available", "last_changed", "items": {"<source>": [{"id", "count", "date"}, …]}}}`. Verified live (Tiger0295 → 268/1701, game_mode 1). Descriptive User-Agent; tests use an injected fetcher (no live network).
- **No committed data validator** (no source dataset). Correctness = tests. Full suite must stay green; the 4 existing validators (`validate_income`/`validate_cost`/`validate_kg`/`validate_drop_rate`) must still exit 0.

---

## File Structure

| File | Responsibility |
|---|---|
| `src/osrs_planner/engine/state.py` | MODIFY: add `clog_obtained` to `AccountState`. |
| `src/osrs_planner/account/__init__.py` | package marker. |
| `src/osrs_planner/account/bank.py` | `parse_bank_tsv(text) -> dict[str,int]` + `bank_value(counts, provider, family) -> dict`. |
| `src/osrs_planner/account/temple.py` | `collection_log_url(player)`, `parse_temple_clog(payload) -> dict`, `fetch_collection_log(player, fetcher)`. |
| `src/osrs_planner/account/state.py` | `build_account_state(mode, bank_tsv=None, clog_obtained=None) -> AccountState`. |
| `scripts/account_demo.py` | demo over fixtures (or `--bank`/`--player`). |
| `tests/account/fixtures/sample_bank.tsv`, `sample_temple.json` | synthetic fixtures. |
| `tests/account/test_*.py` | per-unit tests. |

---

## Task 1: Engine `clog_obtained` field + package scaffold + boundary

**Files:**
- Modify: `src/osrs_planner/engine/state.py:48-49`
- Create: `src/osrs_planner/account/__init__.py`, `tests/account/__init__.py`, `tests/account/test_state_field.py`, `tests/account/test_boundary.py`

**Interfaces:**
- Produces: `AccountState.clog_obtained: set[str]` (default empty).

- [ ] **Step 1: Write the failing test** (`tests/account/test_state_field.py`)

```python
from osrs_planner.engine.state import AccountState

def test_clog_obtained_defaults_empty():
    s = AccountState(mode="ironman")
    assert s.clog_obtained == set()

def test_clog_obtained_accepts_ids():
    s = AccountState(mode="ironman", clog_obtained={"item:4151"})
    assert "item:4151" in s.clog_obtained
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/account/test_state_field.py -v`
Expected: FAIL (`TypeError: __init__() got an unexpected keyword argument 'clog_obtained'`).

- [ ] **Step 3: Add the field** — in `src/osrs_planner/engine/state.py`, insert one line before `observable_families` (line 49):

```python
    clue_counts: dict[str, int] = field(default_factory=dict)
    clog_obtained: set[str] = field(default_factory=set)  # collection-log items obtained; reserved for a future 'clog' completion atom (no evaluator in v1)
    observable_families: set[str] = field(default_factory=set)
```
Also add to the docstring family map (after the `clue_counts` line ~33). NOTE: there is no `clog` atom_type today (`CLOG_SLOT` is a NodeKind, not an atom) — this field is forward-looking, so label it as reserved, not as feeding an existing atom:
```python
      clue_counts      -> clue_scrolls
      clog_obtained    -> (reserved) future clog-completion atom; no evaluator in v1
```

- [ ] **Step 4: Run to verify it passes + no engine regression**

Run: `venv/bin/python -m pytest tests/account/test_state_field.py tests/engine/ -q`
Expected: PASS (new tests + all existing engine tests — the defaulted field breaks nothing).

- [ ] **Step 5: Write the boundary test** (`tests/account/test_boundary.py`)

```python
import ast, os
PKG = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "src", "osrs_planner", "account")
FORBIDDEN = ("osrs_planner.income", "osrs_planner.cost.overlay", "osrs_planner.cost.routing",
             "osrs_planner.cost.channels", "osrs_planner.cost.cards", "osrs_planner.cost.currency")

def test_account_imports_no_overlay_logic():
    offenders = []
    for fn in os.listdir(PKG):
        if not fn.endswith(".py"):
            continue
        tree = ast.parse(open(os.path.join(PKG, fn), encoding="utf-8").read())
        for node in ast.walk(tree):
            mods = ([a.name for a in node.names] if isinstance(node, ast.Import)
                    else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for m in mods:
                if any(f in (m or "") for f in FORBIDDEN):
                    offenders.append(f"{fn}: {m}")
    assert not offenders, f"account/ imports forbidden overlay logic: {offenders}"
```
Create `src/osrs_planner/account/__init__.py` (empty) and `tests/account/__init__.py` (empty) so the test has a package to scan.

- [ ] **Step 6: Run boundary + commit**

Run: `venv/bin/python -m pytest tests/account/ -q` (PASS)
```bash
git add src/osrs_planner/engine/state.py src/osrs_planner/account/__init__.py tests/account/
git commit -m "account: AccountState.clog_obtained field + account package scaffold + boundary"
```

---

## Task 2: Bank TSV parser

**Files:**
- Create: `src/osrs_planner/account/bank.py`, `tests/account/test_bank_parse.py`

**Interfaces:**
- Produces: `parse_bank_tsv(text: str) -> dict[str, int]` — `{"item:<id>": qty}`. Robust to the Bank Memory layout (`id ⇥ name(space-padded) ⇥⇥ qty` — variable tabs); id = first non-empty field, qty = last non-empty field; blank/malformed rows skipped (never fabricated).

- [ ] **Step 1: Write the failing test** (`tests/account/test_bank_parse.py`)

```python
from osrs_planner.account.bank import parse_bank_tsv

def test_parses_id_name_qty():
    text = "995\tCoins              \t\t1000000\n561\tNature rune\t5000\n"
    assert parse_bank_tsv(text) == {"item:995": 1000000, "item:561": 5000}

def test_skips_blank_and_malformed():
    text = "\n4151\tAbyssal whip\t1\ngarbage line\n\t\t\n"
    assert parse_bank_tsv(text) == {"item:4151": 1}

def test_dedupes_and_sums_repeats():
    assert parse_bank_tsv("995\tCoins\t10\n995\tCoins\t5\n") == {"item:995": 15}

def test_strips_commas_in_qty():
    assert parse_bank_tsv("561\tNature rune\t1,234\n") == {"item:561": 1234}
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/account/test_bank_parse.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Write minimal implementation** (`src/osrs_planner/account/bank.py`)

```python
# src/osrs_planner/account/bank.py
"""Bank Memory TSV ingestion + bank value (design §4). Personal data is a RUNTIME
input; never committed. IDs are KG-style 'item:<n>' to match AccountState.counts."""
from __future__ import annotations

def parse_bank_tsv(text: str) -> dict[str, int]:
    """Bank Memory 'Copy item data to clipboard' TSV -> {'item:<id>': qty}.

    Layout is `id <tab> name(space-padded) <tab..> qty`; tab count varies, so we
    take the FIRST non-empty field as the id and the LAST as the quantity. Blank /
    unparseable rows are skipped, not fabricated."""
    out: dict[str, int] = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.split("\t")]
        nonempty = [c for c in cells if c]
        if len(nonempty) < 2:
            continue
        try:
            item_id = int(nonempty[0])
            qty = int(nonempty[-1].replace(",", ""))
        except ValueError:
            continue
        key = f"item:{item_id}"
        out[key] = out.get(key, 0) + qty
    return out
```

- [ ] **Step 4: Run to verify it passes**

Run: `venv/bin/python -m pytest tests/account/test_bank_parse.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/osrs_planner/account/bank.py tests/account/test_bank_parse.py
git commit -m "account: Bank Memory TSV parser"
```

---

## Task 3: Bank value (iron-realizable + GE) + sample fixture

**Files:**
- Modify: `src/osrs_planner/account/bank.py` (add `bank_value`)
- Create: `tests/account/fixtures/sample_bank.tsv`, `tests/account/test_bank_value.py`

**Interfaces:**
- Consumes: a `PriceProvider`-shaped object (`.ge_price(id)`, `.high_alch(id)` → int|None).
- Produces: `bank_value(counts, provider, family) -> dict` with keys `iron_realizable` (currency at face + `high_alch × qty` for TRADEABLE items only), `ge_value` (`ge_price × qty`), `headline` (`ge_value` for family "main", else `iron_realizable`), `per_item` (id → {ge, ha}), `unpriced_count` (untradeable / no-real-GE items). Currency (coins `item:995` = 1gp, platinum token `item:13204` = 1000gp) counts at face in BOTH; an item with no live GE price (or the int-max sentinel) is untradeable → its nominal High-Alch is NOT added to `iron_realizable` (it's counted in `unpriced_count`).

- [ ] **Step 1: Create the synthetic fixture** (`tests/account/fixtures/sample_bank.tsv`)

```
995	Coins                  	1000000
13204	Platinum token         	5000
561	Nature rune            	5000
4151	Abyssal whip           	1
30682	Accumulation charm     	1
```

- [ ] **Step 2: Write the failing test** (`tests/account/test_bank_value.py`)

```python
import os
from osrs_planner.account.bank import parse_bank_tsv, bank_value

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "sample_bank.tsv")

class FakeProvider:  # deterministic prices, no dependency on the committed snapshot
    GE = {"item:561": 120, "item:4151": 1_500_000}        # nature rune, whip (tradeable)
    HA = {"item:561": 108, "item:4151": 72_000,           # whip alchs for far less than GE
          "item:30682": 6_000}                            # Accumulation charm: HA but NO GE (untradeable)
    def ge_price(self, i): return self.GE.get(i)
    def high_alch(self, i): return self.HA.get(i)

def test_iron_realizable_vs_ge_plat_and_untradeable():
    counts = parse_bank_tsv(open(FIX, encoding="utf-8").read())
    v = bank_value(counts, FakeProvider(), "ironman")
    plat = 5000 * 1000                                     # 5000 platinum tokens @ 1000gp each
    # coins 1,000,000 + plat face; nature 5000*120 GE vs *108 HA; whip 1.5M GE vs 72k HA
    assert v["ge_value"] == 1_000_000 + plat + 5000*120 + 1*1_500_000
    assert v["iron_realizable"] == 1_000_000 + plat + 5000*108 + 1*72_000
    assert v["iron_realizable"] < v["ge_value"]            # iron can't realise GE, only HA
    assert v["headline"] == v["iron_realizable"]           # iron headline
    assert v["unpriced_count"] == 1                        # Accumulation charm (untradeable HA)

def test_untradeable_ha_not_counted_as_realizable():
    # an untradeable item with a NOMINAL high-alch must NOT inflate iron_realizable
    v = bank_value({"item:30682": 10}, FakeProvider(), "ironman")
    assert v["iron_realizable"] == 0 and v["ge_value"] == 0 and v["unpriced_count"] == 1

def test_platinum_tokens_count_as_currency():
    v = bank_value({"item:13204": 3}, FakeProvider(), "ironman")
    assert v["iron_realizable"] == 3000 and v["ge_value"] == 3000

def test_main_headline_is_ge():
    counts = parse_bank_tsv(open(FIX, encoding="utf-8").read())
    v = bank_value(counts, FakeProvider(), "main")
    assert v["headline"] == v["ge_value"]
```

- [ ] **Step 3: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/account/test_bank_value.py -v`
Expected: FAIL (`bank_value` undefined).

- [ ] **Step 4: Implement `bank_value` in `bank.py`**

```python
# Currencies the GE snapshot does not price -> count at face. Plat tokens are how
# large coin stacks are stored, so omitting them badly understates spend-now gold.
_CURRENCY = {"item:995": 1, "item:13204": 1000}   # coins=1gp, platinum token=1000gp
_NO_GE = 2_000_000_000  # ge_prices.json uses int-max (2147483647) as a "no real GE price" sentinel

def bank_value(counts: dict[str, int], provider, family: str) -> dict:
    """Iron-realizable (currency + High-Alch of TRADEABLE items) + total GE value
    of a bank (design §4). An item with no live GE price is untradeable -> it yields
    no realizable gold (its nominal High-Alch is unusable), so it is counted in
    unpriced_count, NOT added to iron_realizable. Never fabricates value."""
    iron = 0
    ge = 0
    per_item: dict[str, dict] = {}
    unpriced = 0
    for item_id, qty in counts.items():
        if item_id in _CURRENCY:
            face = qty * _CURRENCY[item_id]
            iron += face
            ge += face
            continue
        gp = provider.ge_price(item_id)
        if not gp or gp >= _NO_GE:           # untradeable / no real GE price -> not realizable
            unpriced += 1
            continue
        ha = provider.high_alch(item_id) or 0
        ge += gp * qty
        iron += ha * qty                     # an iron realizes a TRADEABLE item via High-Alch
        per_item[item_id] = {"ge": gp * qty, "ha": ha * qty}
    headline = ge if family == "main" else iron
    return {"iron_realizable": iron, "ge_value": ge, "headline": headline,
            "per_item": per_item, "unpriced_count": unpriced}
```

- [ ] **Step 5: Run + commit**

Run: `venv/bin/python -m pytest tests/account/test_bank_value.py -v` (PASS)
```bash
git add src/osrs_planner/account/bank.py tests/account/fixtures/sample_bank.tsv tests/account/test_bank_value.py
git commit -m "account: bank value (iron-realizable coins+HA, GE reference)"
```

---

## Task 4: TempleOSRS collection-log client + parser + fixture

**Files:**
- Create: `src/osrs_planner/account/temple.py`, `tests/account/fixtures/sample_temple.json`, `tests/account/test_temple.py`

**Interfaces:**
- Produces: `collection_log_url(player: str) -> str`; `parse_temple_clog(payload: dict) -> dict` with `obtained: set[str]` (`"item:<id>"` for every item with `count >= 1`), `finished`, `available`, `game_mode`, `last_changed`; `fetch_collection_log(player, fetcher=<urllib>) -> dict` (injectable `fetcher(url) -> dict`).

- [ ] **Step 1: Create the synthetic fixture** (`tests/account/fixtures/sample_temple.json`)

```json
{"data": {"player": "TestIron", "game_mode": 1, "total_collections_finished": 2,
  "total_collections_available": 1701, "last_changed": "2026-06-20 10:00:00",
  "items": {
    "alchemical_hydra": [{"id": 22804, "count": 79, "date": "2026-06-18 01:23:43"}],
    "amoxliatl": [{"id": 29889, "count": 1, "date": "2025-11-15 00:00:00"}],
    "abyssal_sire": [{"id": 13262, "count": 0, "date": null}]
  }}}
```

- [ ] **Step 2: Write the failing test** (`tests/account/test_temple.py`)

```python
import json, os
from osrs_planner.account.temple import collection_log_url, parse_temple_clog, fetch_collection_log

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "sample_temple.json")

def test_url_targets_temple_clog_api():
    u = collection_log_url("Tiger0295")
    assert "templeosrs.com/api/collection-log/player_collection_log.php" in u
    assert "player=Tiger0295" in u and "categories=all" in u

def test_parse_obtained_only_count_ge_1():
    payload = json.load(open(FIX, encoding="utf-8"))
    c = parse_temple_clog(payload)
    assert c["obtained"] == {"item:22804", "item:29889"}   # count 0 item EXCLUDED
    assert c["finished"] == 2 and c["available"] == 1701 and c["game_mode"] == 1

def test_fetch_uses_injected_fetcher():
    payload = json.load(open(FIX, encoding="utf-8"))
    c = fetch_collection_log("TestIron", fetcher=lambda url: payload)
    assert "item:22804" in c["obtained"]
```

- [ ] **Step 3: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/account/test_temple.py -v`
Expected: FAIL (module not found).

- [ ] **Step 4: Write minimal implementation** (`src/osrs_planner/account/temple.py`)

```python
# src/osrs_planner/account/temple.py
"""TempleOSRS collection-log ingestion (design §5). Public API; live + cached.
Returns the OBTAINED clog item ids; 'missing' is computed by the consumer against
data/collection_log.json. IDs are KG-style 'item:<n>'."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

API = "https://templeosrs.com/api/collection-log/player_collection_log.php"
UA = "GildedTome/0.1 (account-state ingest; contact: retrogramx on github)"

def collection_log_url(player: str) -> str:
    return f"{API}?player={urllib.parse.quote(player)}&categories=all"

def parse_temple_clog(payload: dict) -> dict:
    data = payload.get("data") or {}
    obtained: set[str] = set()
    for _source, items in (data.get("items") or {}).items():
        for it in items or []:
            if (it.get("count") or 0) >= 1:
                obtained.add(f"item:{it['id']}")
    return {"obtained": obtained,
            "finished": data.get("total_collections_finished"),
            "available": data.get("total_collections_available"),
            "game_mode": data.get("game_mode"),
            "last_changed": data.get("last_changed")}

def _urllib_fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def fetch_collection_log(player: str, fetcher=_urllib_fetch) -> dict:
    return parse_temple_clog(fetcher(collection_log_url(player)))
```

- [ ] **Step 5: Run + commit**

Run: `venv/bin/python -m pytest tests/account/test_temple.py -v` (PASS)
```bash
git add src/osrs_planner/account/temple.py tests/account/fixtures/sample_temple.json tests/account/test_temple.py
git commit -m "account: TempleOSRS collection-log client + parser"
```

---

## Task 5: Combiner (`build_account_state`) + demo + final verification

**Files:**
- Create: `src/osrs_planner/account/state.py`, `tests/account/test_build_state.py`, `scripts/account_demo.py`

**Interfaces:**
- Consumes: `bank.parse_bank_tsv`, `engine.state.AccountState`.
- Produces: `build_account_state(mode, bank_tsv=None, clog_obtained=None) -> AccountState`. `clog_obtained` is the already-parsed OBTAINED SET (from `parse_temple_clog(...)["obtained"]` or `fetch_collection_log(...)["obtained"]`) — so the fixture and live paths compose identically. (Value is a SEPARATE `bank_value` call — §6.) Observability is SOURCE-GATED: `"item"` added iff `bank_tsv is not None`; `"clog"` iff `clog_obtained is not None` (an ingested-but-empty source still counts as observed).

- [ ] **Step 1: Write the failing test** (`tests/account/test_build_state.py`)

```python
import json, os
from osrs_planner.account.state import build_account_state
from osrs_planner.account.temple import parse_temple_clog

FIX = os.path.join(os.path.dirname(__file__), "fixtures")

def _obtained():
    payload = json.load(open(os.path.join(FIX, "sample_temple.json"), encoding="utf-8"))
    return parse_temple_clog(payload)["obtained"]

def test_bank_only_sets_counts_observes_item_not_clog():
    s = build_account_state("ironman", bank_tsv="995\tCoins\t100\n4151\tAbyssal whip\t1\n")
    assert s.counts == {"item:995": 100, "item:4151": 1}
    assert "item" in s.observable_families and "clog" not in s.observable_families
    assert s.clog_obtained == set()

def test_clog_only_sets_clog_observes_clog_not_item():
    s = build_account_state("ironman", clog_obtained=_obtained())
    assert s.clog_obtained == {"item:22804", "item:29889"}
    assert "clog" in s.observable_families and "item" not in s.observable_families
    assert s.counts == {}

def test_both_sources_combine():
    s = build_account_state("ironman", bank_tsv="995\tCoins\t100\n", clog_obtained=_obtained())
    assert s.counts == {"item:995": 100} and "item:22804" in s.clog_obtained
    assert {"item", "clog"} <= s.observable_families

def test_ingested_but_empty_source_still_observed():
    # an empty bank / empty clog is OBSERVED (own nothing / completed nothing), not UNKNOWN
    s = build_account_state("ironman", bank_tsv="", clog_obtained=set())
    assert s.counts == {} and s.clog_obtained == set()
    assert {"item", "clog"} <= s.observable_families

def test_neither_source_is_empty_state():
    s = build_account_state("main")
    assert s.counts == {} and s.clog_obtained == set() and s.observable_families == set()
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/account/test_build_state.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `state.py`**

```python
# src/osrs_planner/account/state.py
"""Combine the runtime account sources into one AccountState (design §6).
Observability is SOURCE-GATED on `is not None`: a family is marked observed only
when its source was actually INGESTED (even if empty -> own/completed nothing is a
real observed zero), preserving the engine's absence-aware UNKNOWN contract for
sources that were NOT ingested. `clog_obtained` is the already-parsed obtained set
(from temple.parse_temple_clog/fetch_collection_log), so fixture + live compose."""
from __future__ import annotations

from osrs_planner.engine.state import AccountState
from osrs_planner.account.bank import parse_bank_tsv

def build_account_state(mode: str, bank_tsv: str | None = None,
                        clog_obtained: set[str] | None = None) -> AccountState:
    counts = parse_bank_tsv(bank_tsv) if bank_tsv is not None else {}
    clog = set(clog_obtained) if clog_obtained is not None else set()
    observable: set[str] = set()
    if bank_tsv is not None:
        observable.add("item")        # item-ownership now a real own/don't-own
    if clog_obtained is not None:
        observable.add("clog")
    return AccountState(mode=mode, counts=counts, clog_obtained=clog,
                        observable_families=observable)
```

- [ ] **Step 4: Run + write the demo** (`scripts/account_demo.py`)

```python
#!/usr/bin/env python3
"""Demo account-state ingestion over the synthetic fixtures (or --bank / --player).
The user's real data is read, used, and NEVER written into the repo."""
import argparse, json, os
from osrs_planner.account.state import build_account_state
from osrs_planner.account.bank import bank_value
from osrs_planner.account.temple import fetch_collection_log, parse_temple_clog
from osrs_planner.cost.prices import SnapshotPriceProvider
from osrs_planner.engine.state import account_family

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(REPO, "tests", "account", "fixtures")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank")     # path to a Bank Memory TSV export
    ap.add_argument("--player")   # OSRS name for the live Temple clog
    ap.add_argument("--mode", default="ironman")
    ns = ap.parse_args()

    bank_tsv = (open(ns.bank, encoding="utf-8").read() if ns.bank
                else open(os.path.join(FIX, "sample_bank.tsv"), encoding="utf-8").read())
    # both paths normalise to the obtained SET: live fetch, or parse the fixture payload
    clog = (fetch_collection_log(ns.player) if ns.player
            else parse_temple_clog(json.load(open(os.path.join(FIX, "sample_temple.json"), encoding="utf-8"))))
    obtained = clog["obtained"]

    state = build_account_state(ns.mode, bank_tsv=bank_tsv, clog_obtained=obtained)

    provider = SnapshotPriceProvider.from_file(os.path.join(REPO, "data", "ge_prices.json"))
    val = bank_value(state.counts, provider, account_family(ns.mode))
    print(f"mode={ns.mode} | owned items={len(state.counts)} | clog obtained={len(state.clog_obtained)}")
    print(f"  iron-realizable (coins+HA): {val['iron_realizable']:,}  | GE value: {val['ge_value']:,}"
          f"  | unpriced: {val['unpriced_count']}")

if __name__ == "__main__":
    main()
```

Run: `venv/bin/python -m pytest tests/account/test_build_state.py -v` (PASS), then `venv/bin/python scripts/account_demo.py` (prints the fixture summary).

- [ ] **Step 5: Full verification + commit**

Run:
```bash
venv/bin/python -m pytest tests/ -q
for v in validate_income validate_cost validate_kg validate_drop_rate; do venv/bin/python data/$v.py >/dev/null && echo "$v ok"; done
```
Expected: full suite passes (existing + new account tests); the engine/income/cost suites stay green after the `clog_obtained` addition; the 4 validators still exit 0.
```bash
git add src/osrs_planner/account/state.py tests/account/test_build_state.py scripts/account_demo.py
git commit -m "account: build_account_state combiner + demo + final verification"
```

---

## Deferred (spec §12 — do NOT build)
Consuming the state (loot-filter tailoring, income/cost re-eval); auto-source adapters (RuneLite config blob, H2 db, companion plugin); banked XP / GE history / equipment; a clog-atom evaluator path; multi-account persistence.
