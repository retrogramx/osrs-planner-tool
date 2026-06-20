# Drop-Rate / Rarity Data Brick — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Source true `1/N` drop rarity for the 1,907 OSRS collection-log items from the Wiki Bucket `dropsline` API into a committed, validator-gated `data/drop_rates.json`.

**Architecture:** A pure DATA brick (no engine/overlay changes). A committed builder (`parse_drop_rates.py`) reads a committed raw `dropsline` cache (`data/raw/`), resolves each item's real dropping sources, parses rarities via an isolated grammar, and emits a canonical `(item_id, source)` rarity table. A committed validator gates it. Deterministic + regenerable from the cached raw (no live fetch at validate time), exactly like `kg/*.json` assemble and `ge_prices.json`.

**Tech Stack:** Python 3 (stdlib `json`/`re`/`urllib`), pydantic not required (plain dicts + JSON), pytest. Source = OSRS Wiki Bucket API (`action=bucket`, bucket `dropsline`).

## Global Constraints

- **Data sourcing ONLY from the OSRS Wiki** (Bucket `dropsline`); pin values from the source, never from memory. Descriptive `User-Agent` required on every wiki API call (default client UAs are blocked).
- **Never fabricate:** a numeric `drop_rate` MUST have a `drop_rate_raw` string that re-parses to it; otherwise `drop_rate` is `null` with a machine-readable `drop_rate_status` reason. No invented/blended numbers.
- **Committed + deterministic:** raw API responses are cached to committed `data/raw/dropsline_*.json`; `drop_rates.json` is regenerable from that cache byte-stably. No live fetch during validate/test.
- **Scope = collection-log items only** (1,907 records / 1,701 distinct item ids / **1,609 distinct item names** in `data/collection_log.json`; the fetch loops over distinct names). Clue reward-casket rarities and regular-monster full tables are deferred (spec §12).
- **IDs:** items are numeric `item_id` (resolve via `data/item_dictionary.json`); the dataset stores the integer `item_id` + display `item`/`source`.
- **Confirmed API shape (verified live 2026-06-19):** `GET https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query=bucket('dropsline').select('item_name','drop_json','rare_drop_table').where('item_name','<NAME>').limit(<N>).run()`. Each result row's `drop_json` carries keys `"Dropped from"` (source, may have a `#variant` suffix e.g. `"Abyssal demon#Wilderness Slayer Cave"`), `"Rarity"` (e.g. `"1/512"`, `"12/128"`), `"Drop Quantity"`, `"Rolls"` (int, may be >1), `"Drop level"`. Golden truth: Abyssal whip → `Abyssal demon` @ `1/512`.

---

## File Structure

| File | Responsibility |
|---|---|
| `data/_rarity_grammar.py` | Pure: parse a Rarity string → `(rate, status)`. No I/O. |
| `data/_dropsline.py` | Bucket `dropsline` client: build query URL, fetch, cache to `data/raw/`. |
| `data/parse_drop_rates.py` | Orchestrator: clog items → cached raw → resolve sources → parse → emit `drop_rates.json`. Re-runnable, deterministic. |
| `data/_toa_drop_rates.py` | ToA invocation/points resolver (the §7 deep-dive). |
| `data/drop_rates.json` | Output dataset (committed). |
| `data/raw/dropsline_*.json` | Committed raw API cache (provenance). |
| `data/validate_drop_rate.py` | Committed validator gate. |
| `tests/drop_rates/test_rarity_grammar.py` | Grammar unit tests (the brittle unit). |
| `tests/drop_rates/test_parse_drop_rates.py` | Source-resolution + join tests over a fixture. |
| `tests/drop_rates/test_drop_rates_golden.py` | Pinned wiki-verified rarities read from committed data. |
| `tests/drop_rates/test_validate_drop_rate.py` | Validator green-on-committed / fails-on-broken. |

---

## Task 1: Scaffold + `dropsline` client + committed raw fixture

**Files:**
- Create: `data/_dropsline.py`, `tests/drop_rates/__init__.py`, `tests/drop_rates/test_dropsline_client.py`
- Create (committed, by running): `data/raw/dropsline_fixture.json`

**Interfaces:**
- Produces: `dropsline_query_url(item_name: str, limit: int = 500) -> str`; `parse_bucket_response(payload: dict) -> list[dict]` (returns the list of result rows, each `{item_name, drop_json (dict), rare_drop_table}`, with `drop_json` json-decoded if it arrives as a string); `fetch_dropsline(item_names: list[str], cache_path: str, fetcher) -> dict` where `fetcher(url) -> dict` is injected (so tests pass a fake; real runs pass a urllib-based fetcher).

- [ ] **Step 1: Write the failing test** (`tests/drop_rates/test_dropsline_client.py`)

```python
import json, os
import pytest
from data._dropsline import dropsline_query_url, parse_bucket_response

def test_query_url_targets_dropsline_bucket():
    url = dropsline_query_url("Abyssal whip", limit=30)
    assert "action=bucket" in url and "format=json" in url
    assert "bucket('dropsline')" in url
    assert "select('item_name','drop_json','rare_drop_table')" in url
    assert "Abyssal%20whip" in url or "Abyssal+whip" in url
    assert ".limit(30).run()" in url

def test_query_url_escapes_apostrophe():  # M1 — 182 clog names carry an apostrophe
    url = dropsline_query_url("Ahrim's hood")
    # the apostrophe must be backslash-escaped INSIDE the Lua literal, then URL-encoded
    from urllib.parse import unquote
    assert "\\'" in unquote(url), "apostrophe not escaped -> the API would return an error envelope"

def test_parse_bucket_raises_on_error_envelope():  # M2 — never swallow API errors
    with pytest.raises(ValueError):
        parse_bucket_response({"error": "')' expected near 's'."})

def test_parse_bucket_decodes_drop_json_string():
    # Bucket may deliver drop_json as a JSON-encoded STRING; decode it.
    payload = {"bucket": [
        {"item_name": "Abyssal whip",
         "drop_json": json.dumps({"Dropped from": "Abyssal demon#Standard",
                                  "Rarity": "1/512", "Rolls": 1, "Drop Quantity": "1"}),
         "rare_drop_table": False}
    ]}
    rows = parse_bucket_response(payload)
    assert rows[0]["drop_json"]["Dropped from"] == "Abyssal demon#Standard"
    assert rows[0]["drop_json"]["Rarity"] == "1/512"

def test_parse_bucket_passes_drop_json_object_through():
    payload = {"bucket": [
        {"item_name": "X", "drop_json": {"Dropped from": "Y", "Rarity": "1/4"}, "rare_drop_table": False}
    ]}
    rows = parse_bucket_response(payload)
    assert rows[0]["drop_json"]["Rarity"] == "1/4"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/drop_rates/test_dropsline_client.py -v`
Expected: FAIL (module `data._dropsline` not found).

- [ ] **Step 3: Write minimal implementation** (`data/_dropsline.py`)

```python
# data/_dropsline.py
"""Bucket `dropsline` client (OSRS Wiki). Build query URLs, fetch with a
descriptive User-Agent, cache raw responses to data/raw/. drop_json may arrive
as a JSON-encoded string OR a nested object; parse_bucket_response normalizes it
to a dict. Confirmed live 2026-06-19; see plan Global Constraints."""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request

API = "https://oldschool.runescape.wiki/api.php"
UA = "GildedTome/0.1 (drop-rate data brick; contact: retrogramx on github)"

def _lua_escape(name: str) -> str:
    """Escape a name for a single-quoted Lua bucket string literal. An unescaped
    apostrophe (Ahrim's, Tumeken's, d'hide -- 182 of the 1,609 clog names) closes
    the literal early and the API returns an ERROR envelope, not rows. Verified
    fix: backslash-escape backslashes then apostrophes."""
    return name.replace(chr(92), chr(92) * 2).replace(chr(39), chr(92) + chr(39))

def dropsline_query_url(item_name: str, limit: int = 500) -> str:
    q = ("bucket('dropsline')"
         ".select('item_name','drop_json','rare_drop_table')"
         f".where('item_name','{_lua_escape(item_name)}')"
         f".limit({limit}).run()")
    return f"{API}?action=bucket&format=json&query={urllib.parse.quote(q)}"

def parse_bucket_response(payload: dict) -> list[dict]:
    # An API error (e.g. a malformed query) returns an envelope with NO 'bucket'
    # key but an 'error' string. RAISE -- never let it silently become [] (which
    # build_records would mislabel 'null-not-in-bucket', hiding a real failure).
    rows = payload.get("bucket")
    if rows is None:
        rows = payload.get("data", {}).get("bucket")
    if rows is None:
        if "error" in payload:
            raise ValueError(f"dropsline query error: {payload['error']}")
        rows = []
    out = []
    for r in rows:
        dj = r.get("drop_json")
        if isinstance(dj, str):
            try:
                dj = json.loads(dj)
            except (ValueError, TypeError):
                dj = {}
        out.append({"item_name": r.get("item_name"),
                    "drop_json": dj or {},
                    "rare_drop_table": r.get("rare_drop_table")})
    return out

def _urllib_fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def fetch_dropsline(item_names: list[str], cache_path: str, fetcher=_urllib_fetch,
                    sleep_s: float = 0.0) -> dict:
    """Fetch dropsline rows for each item_name; return {item_name: [rows]} and
    write the raw cache to cache_path. fetcher is injectable for tests."""
    cache: dict[str, list] = {}
    for name in item_names:
        payload = fetcher(dropsline_query_url(name))
        cache[name] = parse_bucket_response(payload)
        if sleep_s:
            time.sleep(sleep_s)
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, sort_keys=True, ensure_ascii=False)
    return cache
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/drop_rates/test_dropsline_client.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Produce the committed raw fixture (live fetch, small)**

Fetch a representative set live and commit it as the fixture every later task tests against. Each item pins a specific case the adversarial review found on real data:
- `Abyssal whip` — note-1 proof (→ `Abyssal demon` 1/512) + a superior alt-source (`Greater abyssal demon`, no `#`) + Unsired.
- `Tumeken's shadow (uncharged)` — **apostrophe (M1)** AND the ToA case (→ `Chest (Tombs of Amascut)` **1/24**, a flat fraction — M4).
- `Ahrim's hood` — another **apostrophe (M1)**.
- `Pet kraken` — **comma denominator (M3)** (→ `Kraken` `1/3,000`).
- `Imbued heart` — **superior + comma (M3/M6)** (rows like `1/1,288`).
- `Twisted bow` — CoX raid (→ `Ancient chest` 2/69).
- `Granite maul` — generic-Slayer resolution (→ `Gargoyle`).
- `Coins` — **multi-slot same base (M6)** (`Mithril dragon` at 17/128, 7/128, 1/780.19).

Run:
```bash
venv/bin/python -c "
from data._dropsline import fetch_dropsline
items=['Abyssal whip',\"Tumeken's shadow (uncharged)\",\"Ahrim's hood\",'Pet kraken',
       'Imbued heart','Twisted bow','Granite maul','Coins']
fetch_dropsline(items, 'data/raw/dropsline_fixture.json')
print('fixture written')
"
```
Then eyeball `data/raw/dropsline_fixture.json` and confirm ON REAL DATA: (1) `Abyssal whip` → `"Dropped from":"Abyssal demon#..."`, `"Rarity":"1/512"`; (2) the **apostrophe** items (`Tumeken's shadow`, `Ahrim's hood`) returned real rows, NOT an error/empty list (proves M1/M2); (3) `Pet kraken` Rarity is literally `"1/3,000"` (proves the M3 comma case is live). If any apostrophe item is empty, the escaping is broken — fix before committing. **Commit only after the fixture is confirmed correct.**

- [ ] **Step 6: Commit**

```bash
git add data/_dropsline.py tests/drop_rates/__init__.py tests/drop_rates/test_dropsline_client.py data/raw/dropsline_fixture.json
git commit -m "drop-rates: dropsline client + committed raw fixture"
```

---

## Task 2: Rarity grammar (`_rarity_grammar.py`)

**Files:**
- Create: `data/_rarity_grammar.py`, `tests/drop_rates/test_rarity_grammar.py`

**Interfaces:**
- Produces: `parse_rarity(raw) -> tuple[float | None, int, str]` returning `(rate_per_roll, rolls_in_string, status)` where `status ∈ {"sourced","null-qualitative","null-unparsed"}`. `rate_per_roll` is a probability in `(0,1]` or `None`. `rolls_in_string` is the multiplier embedded in the string (e.g. `"2 × 1/128"` → 2), else 1 — the orchestrator reconciles this with the drop_json `"Rolls"` field.

- [ ] **Step 1: Write the failing test** (`tests/drop_rates/test_rarity_grammar.py`)

```python
import math
from data._rarity_grammar import parse_rarity

def approx(a, b): return a is not None and math.isclose(a, b, rel_tol=1e-6)

def test_simple_fraction():
    rate, rolls, status = parse_rarity("1/512")
    assert approx(rate, 1/512) and rolls == 1 and status == "sourced"

def test_non_unit_numerator():
    rate, _, status = parse_rarity("12/128")
    assert approx(rate, 12/128) and status == "sourced"

def test_decimal_denominator():
    rate, _, status = parse_rarity("1/26.9")
    assert approx(rate, 1/26.9) and status == "sourced"

def test_comma_thousands_separator():  # M3 — real API emits "1/3,000", "1/16,384"
    rate, _, status = parse_rarity("1/3,000")
    assert approx(rate, 1/3000) and status == "sourced"
    rate2, _, status2 = parse_rarity("1/16,384")
    assert approx(rate2, 1/16384) and status2 == "sourced"
    rate3, _, status3 = parse_rarity("1/2,687.2")  # comma + decimal
    assert approx(rate3, 1/2687.2) and status3 == "sourced"

def test_embedded_rolls_multiplier():
    rate, rolls, status = parse_rarity("2 × 1/128")
    assert approx(rate, 1/128) and rolls == 2 and status == "sourced"

def test_always_is_one():
    assert parse_rarity("Always") == (1.0, 1, "sourced")
    assert parse_rarity("1/1") == (1.0, 1, "sourced")

def test_qualitative_is_null_not_fabricated():
    for q in ("Common", "Uncommon", "Varies", "~", ""):
        rate, _, status = parse_rarity(q)
        assert rate is None and status == "null-qualitative"

def test_unparseable_is_null_unparsed():
    rate, _, status = parse_rarity("see notes")
    assert rate is None and status == "null-unparsed"

def test_none_input():
    rate, _, status = parse_rarity(None)
    assert rate is None and status == "null-qualitative"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/drop_rates/test_rarity_grammar.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Write minimal implementation** (`data/_rarity_grammar.py`)

```python
# data/_rarity_grammar.py
"""Parse a dropsline `Rarity` string into a numeric per-roll probability.

NEVER fabricates: a qualitative word ("Common") or an unparseable string returns
None with a status, never a guessed number. Pure + deterministic (no I/O)."""
from __future__ import annotations

import re

_FRACTION = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)\s*$")
_TIMES = re.compile(r"^\s*(\d+)\s*[x×*]\s*(.+)$")
_QUALITATIVE = {"", "~", "always*", "common", "uncommon", "rare", "very rare",
                "varies", "random", "unknown"}

def parse_rarity(raw):
    """Return (rate_per_roll: float|None, rolls_in_string: int, status: str)."""
    if raw is None:
        return (None, 1, "null-qualitative")
    # M3: the API emits comma thousands-separators ("1/3,000", "1/16,384") for the
    # RAREST uniques -- strip them so the fraction regex matches (a comma never
    # appears except as a group separator in these strings). Without this every
    # denominator >=1000 silently becomes null-unparsed.
    s = str(raw).strip().replace(",", "")
    low = s.lower()
    if low in ("always", "1/1"):
        return (1.0, 1, "sourced")
    if low in _QUALITATIVE:
        return (None, 1, "null-qualitative")
    m = _TIMES.match(s)
    if m:
        mult = int(m.group(1))
        rate, _inner_rolls, status = parse_rarity(m.group(2))
        return (rate, mult, status)
    m = _FRACTION.match(s)
    if m:
        num, denom = float(m.group(1)), float(m.group(2))
        if denom <= 0 or num <= 0:
            return (None, 1, "null-unparsed")
        rate = num / denom
        if rate > 1.0:
            return (None, 1, "null-unparsed")
        return (rate, 1, "sourced")
    return (None, 1, "null-unparsed")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/drop_rates/test_rarity_grammar.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add data/_rarity_grammar.py tests/drop_rates/test_rarity_grammar.py
git commit -m "drop-rates: rarity grammar parser (never-fabricate)"
```

---

## Task 3: Parser core — source resolution + emit over the fixture

**Files:**
- Create: `data/parse_drop_rates.py`, `tests/drop_rates/test_parse_drop_rates.py`

**Interfaces:**
- Consumes: `data._dropsline` (cache shape `{item_name: [rows]}`), `data._rarity_grammar.parse_rarity`.
- Produces: `split_source(dropped_from) -> (base, variant|None)` (`"Abyssal demon#Wilderness Slayer Cave"` → `("Abyssal demon", "Wilderness Slayer Cave")`); `classify_node_type(base, clog_node) -> str`; `build_records(clog_records, cache) -> list[dict]` — one record per `(item_id, base source)` per spec §3, iterating per `item_id` (a name maps to several ids), emitting `source_condition` ("superior"|None), keeping EVERY input row (non-canonical rows → `variants[]`), and deferring clue reward-caskets to null. ToA disclosure is layered by Task 5's `apply_toa`.

- [ ] **Step 1: Write the failing test** (`tests/drop_rates/test_parse_drop_rates.py`)

```python
import json, math, os
from data.parse_drop_rates import split_source, build_records

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_split_source_strips_hash_variant():
    assert split_source("Abyssal demon#Wilderness Slayer Cave") == ("Abyssal demon", "Wilderness Slayer Cave")
    assert split_source("Gargoyle") == ("Gargoyle", None)

def test_build_records_resolves_whip_to_abyssal_demon():
    cache = json.load(open(os.path.join(REPO, "data", "raw", "dropsline_fixture.json")))
    clog = [{"item": "Abyssal whip", "item_id": 4151, "source": "Slayer", "node_type": "activity"}]
    recs = build_records(clog, cache)
    # at least one record: Abyssal whip @ Abyssal demon = 1/512, sourced
    ad = [r for r in recs if r["source"] == "Abyssal demon"]
    assert ad, "expected an Abyssal demon record for the whip"
    assert ad[0]["item_id"] == 4151
    assert ad[0]["drop_rate_status"] == "sourced"
    assert math.isclose(ad[0]["drop_rate"], 1/512, rel_tol=1e-6)
    assert ad[0]["drop_rate_raw"] == "1/512"
    assert ad[0]["rolls"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/drop_rates/test_parse_drop_rates.py -v`
Expected: FAIL (module not found).

- [ ] **Step 3: Write minimal implementation** (`data/parse_drop_rates.py`)

```python
# data/parse_drop_rates.py
"""Build data/drop_rates.json from the committed dropsline raw cache.

Queries are by ITEM (the cache is {item_name: [dropsline rows]}); each row's
drop_json gives the real dropping source ("Dropped from", with an optional
#variant suffix), Rarity, and Rolls. One output record per (item_id, base
source). Source resolution sidesteps the collection log's fake "Slayer" bundle
(spec §5). Never fabricates (spec §2.4)."""
from __future__ import annotations

import json
import os
import sys

# repo root on path so `from data.X import ...` resolves BOTH when run as a script
# (`python data/parse_drop_rates.py` puts data/ on the path, not the root) AND under
# pytest (pyproject pythonpath="."). _toa_drop_rates (Task 5) imports the same way.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data._rarity_grammar import parse_rarity

DATA = os.path.dirname(os.path.abspath(__file__))

def split_source(dropped_from):
    """'Abyssal demon#Wilderness Slayer Cave' -> ('Abyssal demon', 'Wilderness Slayer Cave')."""
    if not dropped_from:
        return ("", None)
    base, _, variant = str(dropped_from).partition("#")
    return (base.strip(), variant.strip() or None)

def _status_for_no_rows(node_type):
    if node_type in ("minigame", "activity"):
        return "null-activity"
    return "null-not-in-bucket"

# Raid reward-chest source labels (dropsline names the CHEST, not the raid).
_RAID_CHESTS = {"Chest (Tombs of Amascut)", "Ancient chest", "Monumental chest"}
# Deterministic canonical pick (N3): prefer the plain/Standard/Regular variant.
_CANON_RANK = {None: 0, "Standard": 1, "Regular": 1, "Normal": 1}

def _is_superior(base):  # M6 — superior slayer monsters are a distinct source
    low = (base or "").lower()
    return low.startswith("greater ") or "superior" in low

def classify_node_type(base, clog_node):
    """Coarse v1 source classification (disclosed simplification): clue if a reward
    casket; raid if a known raid chest; else 'monster' (boss vs monster is not
    distinguished without a curated list -- a documented v1 limitation)."""
    if base.startswith("Reward casket"):
        return "clue"
    if base in _RAID_CHESTS:
        return "raid"
    return "monster"

def _null_record(item_id, item, source, node_type, status):
    return {"item_id": item_id, "item": item, "source": source,
            "source_node_type": node_type, "source_condition": None,
            "drop_rate": None, "drop_rate_raw": "", "rolls": 1,
            "drop_rate_status": status, "variants": []}

def build_records(clog_records, cache):
    """One record per (item_id, base source). NO input row is dropped (M6): every
    non-canonical row of a base -- alternate drop-table slots AND #variants -- lands
    in variants[]. Iterates per item_id, since a name can map to several ids (M5).
    Clue reward-casket sources are DEFERRED to v2 (spec §12): null + reason. Never
    fabricates. ToA canonical/scaling is layered on in Task 5 (apply_toa)."""
    # item_id -> (name, fallback clog node_type); a name may carry several ids (M5)
    by_id = {}
    for c in clog_records:
        by_id.setdefault(c["item_id"], (c["item"], c.get("node_type", "other")))
    out = []
    for item_id, (item_name, clog_node) in by_id.items():
        rows = cache.get(item_name) or []
        by_base = {}
        for row in rows:
            dj = row.get("drop_json") or {}
            base, variant = split_source(dj.get("Dropped from"))
            if base:
                by_base.setdefault(base, []).append((variant, dj))
        if not by_base:
            out.append(_null_record(item_id, item_name, "(unsourced)", clog_node,
                                    _status_for_no_rows(clog_node)))
            continue
        for base, entries in by_base.items():
            node_type = classify_node_type(base, clog_node)
            if base.startswith("Reward casket"):  # N2: clue caskets deferred (spec §12)
                out.append(_null_record(item_id, item_name, base, node_type,
                                        "null-clue-casket-deferred"))
                continue
            # N3: deterministic canonical (prefer plain/Standard/Regular, then name)
            entries = sorted(entries, key=lambda e: (_CANON_RANK.get(e[0], 2), e[0] or ""))
            _pv, dj = entries[0]
            rate, str_rolls, status = parse_rarity(dj.get("Rarity"))
            field_rolls = dj.get("Rolls")
            rolls = int(field_rolls) if isinstance(field_rolls, (int, float)) and field_rolls else str_rolls
            variants = []
            for variant, edj in entries[1:]:  # M6: keep EVERY other row, none dropped
                vrate, _vr, _vs = parse_rarity(edj.get("Rarity"))
                cond = variant if variant else "alternate drop-table slot"
                variants.append({"condition": cond, "drop_rate": vrate,
                                 "drop_rate_raw": str(edj.get("Rarity") or "")})
            out.append({
                "item_id": item_id, "item": item_name, "source": base,
                "source_node_type": node_type,
                "source_condition": "superior" if _is_superior(base) else None,
                "drop_rate": rate,
                "drop_rate_raw": str(dj.get("Rarity")) if status == "sourced" else "",
                "rolls": rolls, "drop_rate_status": status, "variants": variants,
            })
    out.sort(key=lambda r: (r["item_id"], r["source"]))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/bin/python -m pytest tests/drop_rates/test_parse_drop_rates.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add data/parse_drop_rates.py tests/drop_rates/test_parse_drop_rates.py
git commit -m "drop-rates: parser core — source resolution + record emit (fixture slice)"
```

---

## Task 4: Bulk fetch + emit the committed `drop_rates.json`

**Files:**
- Modify: `data/parse_drop_rates.py` (add `load_clog()`, `name_index()`, `main()` + envelope writer)
- Create (committed, by running): `data/raw/dropsline_full.json`, `data/drop_rates.json`

**Interfaces:**
- Consumes: `data/collection_log.json`, `data/item_dictionary.json`.
- Produces: `python data/parse_drop_rates.py` writes `data/drop_rates.json` (envelope `{_provenance, records, _excluded}`) from `data/raw/dropsline_full.json`; re-running is byte-stable.

- [ ] **Step 1: Add the orchestration (`main`) to `data/parse_drop_rates.py`**

```python
def load_clog():
    recs = json.load(open(os.path.join(DATA, "collection_log.json"), encoding="utf-8"))["records"]
    return recs

def write_dataset(records, path):
    sourced = sum(1 for r in records if r["drop_rate_status"] == "sourced")
    envelope = {
        "_provenance": {
            "domain": "drop_rates",
            "source_urls": ["https://oldschool.runescape.wiki/w/Module:DropsLine",
                            "https://oldschool.runescape.wiki/api.php (bucket dropsline)"],
            "license": "OSRS Wiki content CC BY-NC-SA 3.0",
            "accessed_at": "2026-06-19",
            "record_count": len(records),
            "sourced_count": sourced,
            "note": "Per-(item_id, source) rarity for collection-log items via Bucket dropsline. "
                    "Clue caskets + activity/minigame mostly null-by-reason (v1). ToA invocation-canonical.",
        },
        "records": records,
        "_excluded": [],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(envelope, f, indent=2, ensure_ascii=False)

def main():
    clog = load_clog()
    cache = json.load(open(os.path.join(DATA, "raw", "dropsline_full.json"), encoding="utf-8"))
    records = build_records(clog, cache)
    write_dataset(records, os.path.join(DATA, "drop_rates.json"))
    print(f"drop_rates.json: {len(records)} records")

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Bulk-fetch the raw cache (live)**

The Bucket `where('item_name','in',[...])` form is REJECTED by the API (`"unexpected symbol near '['"`), so a **per-item loop is mandatory** — ~**1,609 distinct clog item names** (verified), with `sleep_s` + the descriptive UA. The M1 apostrophe escape + M2 error-raise mean apostrophe items now resolve (and a real API error aborts the run loudly instead of caching `[]`).

```bash
venv/bin/python -c "
import json
from data._dropsline import fetch_dropsline
clog=json.load(open('data/collection_log.json'))['records']
names=sorted({c['item'] for c in clog})
print('fetching', len(names), 'items...')  # ~1,609
fetch_dropsline(names, 'data/raw/dropsline_full.json', sleep_s=0.1)
print('done')
"
```
Spot-check `data/raw/dropsline_full.json`: confirm `Abyssal whip`/`Granite maul` have rows; AND confirm an **apostrophe item** (`Ahrim's hood`, `Osmumten's fang`) returned real rows (proves the M1 fix held over the full run). If the wiki rate-limits, raise `sleep_s`. (~1,609 × 0.1s ≈ 3 min + latency.)

- [ ] **Step 3: Generate + sanity-check the dataset**

Run: `venv/bin/python data/parse_drop_rates.py`
Then:
```bash
venv/bin/python -c "
import json
d=json.load(open('data/drop_rates.json'))['records']
print('records:', len(d), 'sourced:', sum(1 for r in d if r['drop_rate_status']=='sourced'))
whip=[r for r in d if r['item']=='Abyssal whip' and r['source']=='Abyssal demon']
print('whip@AbyssalDemon:', whip[0]['drop_rate'], whip[0]['drop_rate_raw'])
gm=[r for r in d if r['item']=='Granite maul']
print('granite maul sources:', [(r['source'], r['drop_rate_raw']) for r in gm])
"
```
Expected: whip@AbyssalDemon ≈ 0.001953 / "1/512"; Granite maul resolves to `Gargoyle` (+ maybe Grotesque Guardians). Confirms note 1 on real data.

- [ ] **Step 4: Verify byte-stability**

Run: `venv/bin/python data/parse_drop_rates.py && git diff --stat data/drop_rates.json`
Expected: re-running produces no diff (deterministic).

- [ ] **Step 5: Commit**

```bash
git add data/parse_drop_rates.py data/raw/dropsline_full.json data/drop_rates.json
git commit -m "drop-rates: bulk-source dropsline + emit committed drop_rates.json"
```

---

## Task 5: ToA invocation/points deep-dive (`_toa_drop_rates.py`)

**Files:**
- Create: `data/_toa_drop_rates.py`, `tests/drop_rates/test_toa.py`
- Modify: `data/parse_drop_rates.py` (apply ToA overrides in `build_records`)

**Interfaces:**
- Produces: `TOA_UNIQUES: dict[str, dict]` (per-unique invocation/points notes, keyed by item name) and `apply_toa(record: dict) -> dict`. **Reality (verified live, M4):** dropsline gives ToA uniques a SINGLE flat row `"Dropped from": "Chest (Tombs of Amascut)"`, `"Rarity": "1/24"` (Osmumten's fang `7/24`) — already a `sourced` numeric, NOT a formula and NOT `"Tombs of Amascut"`. So `apply_toa` does NOT rescue a null; it keys on `record["source"] == "Chest (Tombs of Amascut)"` and, for an already-`sourced` record, **ATTACHES** an invocation-scaling disclosure to `variants[]` (the points→chance formula is self-sourced from the ToA wiki, since dropsline does not expose it). No-op for every other source.

- [ ] **Step 1: RESEARCH (pin from the wiki, not memory)**

dropsline gives only the flat reference fraction (`1/24` at the chest). The raid-level (invocation) + points → unique-chance formula is NOT in dropsline — **self-source it** from the OSRS Wiki ToA pages (`Tombs_of_Amascut`, `Tombs_of_Amascut/Strategies`, the rewards/unique-table mechanic). Determine, with source URLs in the module docstring:
- The unique-chance vs raid level (invocation) relationship + how points partition which unique drops, and the per-unique split.
- Each ToA unique item name + confirm its `dropsline` `Dropped from` label is `"Chest (Tombs of Amascut)"` and its flat rate (from the committed fixture/full cache).

Write the findings as a module docstring with pinned formulae + source URLs. **Keep the dropsline flat fraction as the record's `drop_rate`/`drop_rate_raw`** (it is a real reference number); the formula goes in `variants[]`/notes as a disclosure.

- [ ] **Step 2: Write the failing test** (`tests/drop_rates/test_toa.py`)

```python
from data._toa_drop_rates import TOA_UNIQUES, apply_toa

def test_toa_attaches_invocation_disclosure():
    # dropsline already gives a flat 1/24 -> 'sourced'. apply_toa ATTACHES the
    # invocation-scaling disclosure to variants[]; it does NOT rescue a null (M4).
    rec = {"item": "Tumeken's shadow (uncharged)", "source": "Chest (Tombs of Amascut)",
           "source_node_type": "raid", "source_condition": None,
           "drop_rate": 1/24, "drop_rate_raw": "1/24", "rolls": 1,
           "drop_rate_status": "sourced", "variants": []}
    out = apply_toa(rec)
    assert out["drop_rate_status"] == "sourced" and out["drop_rate"] is not None
    assert any("invocation" in v["condition"].lower() for v in out["variants"])

def test_apply_toa_noop_for_non_toa():
    rec = {"item": "Abyssal whip", "source": "Abyssal demon", "source_node_type": "monster",
           "source_condition": None, "drop_rate": 1/512, "drop_rate_raw": "1/512",
           "rolls": 1, "drop_rate_status": "sourced", "variants": []}
    assert apply_toa(rec) == rec
```

- [ ] **Step 3: Implement `data/_toa_drop_rates.py`** with the researched `TOA_UNIQUES` table (per-unique invocation/points notes, pinned from Step 1) and `apply_toa(record) -> record`. `apply_toa` is a no-op unless `record["source"] == "Chest (Tombs of Amascut)"`. For a ToA record (already `sourced` with the flat `1/24`-style `drop_rate` from dropsline), it does NOT overwrite `drop_rate`/`drop_rate_raw`; it APPENDS an `{"condition": "invocation <ref> (scales with raid level/points)", "drop_rate": <if known>, "drop_rate_raw": ""}` disclosure to `variants[]`.

  Then wire it into `build_records`: add `from data._toa_drop_rates import apply_toa` to the imports (the repo-root path insert already makes `data.X` resolve), and wrap the MAIN sourced append — change `out.append({ ... })` (the sourced-record branch, not the two `_null_record` branches) to `out.append(apply_toa({ ... }))` so ToA records get the disclosure and every other record passes through unchanged. Re-run `venv/bin/python data/parse_drop_rates.py` to regenerate `drop_rates.json`.

- [ ] **Step 4: Run tests + regenerate**

Run: `venv/bin/python -m pytest tests/drop_rates/test_toa.py -v` (PASS), then `venv/bin/python data/parse_drop_rates.py`.

- [ ] **Step 5: Commit**

```bash
git add data/_toa_drop_rates.py tests/drop_rates/test_toa.py data/parse_drop_rates.py data/drop_rates.json
git commit -m "drop-rates: ToA invocation/points resolver (deep-dive, wiki-pinned)"
```

---

## Task 6: CoX/ToB raid-scaling disclosure + verify variants/superior on real data

Superior tagging (`source_condition`), `#variant` location/mode rows, and multi-slot
no-drop were all folded into Task 3's `build_records`. This task (a) VERIFIES that
behavior on the committed fixture (so M5/M6 are pinned by tests), and (b) adds the
remaining §6 raid-scaling DISCLOSURE for CoX/ToB (parallel to Task 5's ToA). Detailed
CoX/ToB formulae are a v2 follow-up; v1 ships the disclosure note.

**Files:**
- Create: `data/_raid_scaling.py`
- Modify: `data/parse_drop_rates.py` (apply the raid disclosure), `tests/drop_rates/test_parse_drop_rates.py`

**Interfaces:**
- Produces: `apply_raid_scaling(record) -> record`, a no-op unless `record["source"]` is a CoX (`"Ancient chest"`) or ToB (`"Monumental chest"`) raid chest; for those it APPENDS a `{"condition": "scales with points/team size", "drop_rate": None, "drop_rate_raw": ""}` disclosure to `variants[]` (the flat dropsline rate stays as `drop_rate`).

- [ ] **Step 1: Write the failing tests** (append to `tests/drop_rates/test_parse_drop_rates.py`)

```python
import math
from data.parse_drop_rates import build_records
from data._raid_scaling import apply_raid_scaling

def _fixture():
    import json, os
    return json.load(open(os.path.join(REPO, "data", "raw", "dropsline_fixture.json")))

def test_superior_source_tagged_on_real_data():  # M6 — superior is a record field
    cache = _fixture()
    clog = [{"item": "Abyssal whip", "item_id": 4151, "source": "Slayer", "node_type": "activity"}]
    recs = build_records(clog, cache)
    greater = [r for r in recs if r["source"] == "Greater abyssal demon"]
    assert greater and greater[0]["source_condition"] == "superior"

def test_multi_slot_same_base_keeps_all_rates():  # M6 — no input row dropped
    cache = {"Coins": [
        {"item_name": "Coins", "drop_json": {"Dropped from": "Mithril dragon", "Rarity": "17/128", "Rolls": 1}},
        {"item_name": "Coins", "drop_json": {"Dropped from": "Mithril dragon", "Rarity": "7/128", "Rolls": 1}},
    ]}
    clog = [{"item": "Coins", "item_id": 995, "source": "x", "node_type": "other"}]
    recs = build_records(clog, cache)
    md = [r for r in recs if r["source"] == "Mithril dragon"]
    assert len(md) == 1
    rates = [md[0]["drop_rate"]] + [v["drop_rate"] for v in md[0]["variants"]]
    assert any(math.isclose(x, 17/128) for x in rates) and any(math.isclose(x, 7/128) for x in rates)

def test_apply_raid_scaling_attaches_for_cox_noop_otherwise():
    cox = {"source": "Ancient chest", "variants": []}
    assert any("scales" in v["condition"].lower() for v in apply_raid_scaling(cox)["variants"])
    other = {"source": "Abyssal demon", "variants": []}
    assert apply_raid_scaling(other)["variants"] == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/drop_rates/test_parse_drop_rates.py -k "superior or multi_slot or raid_scaling" -v`
Expected: FAIL (`data._raid_scaling` not found).

- [ ] **Step 3: Implement `data/_raid_scaling.py`**

```python
# data/_raid_scaling.py
"""CoX/ToB raid-scaling DISCLOSURE. dropsline gives a flat chest rate; the real
chance scales with points (CoX) / team size + mode (ToB). v1 attaches a disclosure
note to variants[]; the detailed formula is a v2 follow-up (like clue caskets)."""
from __future__ import annotations

_RAID_CHESTS = {"Ancient chest", "Monumental chest"}  # CoX, ToB (ToA -> apply_toa)

def apply_raid_scaling(record):
    if record.get("source") in _RAID_CHESTS:
        record = dict(record)
        record["variants"] = list(record.get("variants", [])) + [
            {"condition": "scales with points/team size", "drop_rate": None, "drop_rate_raw": ""}
        ]
    return record
```
Wire it into `build_records`: add `from data._raid_scaling import apply_raid_scaling` and wrap the main sourced append as `out.append(apply_raid_scaling(apply_toa({ ... })))`. Re-run `venv/bin/python data/parse_drop_rates.py`.

- [ ] **Step 4: Run tests + regenerate**

Run: `venv/bin/python -m pytest tests/drop_rates/ -v` (all PASS), then `venv/bin/python data/parse_drop_rates.py`.

- [ ] **Step 5: Commit**

```bash
git add data/_raid_scaling.py data/parse_drop_rates.py tests/drop_rates/test_parse_drop_rates.py data/drop_rates.json
git commit -m "drop-rates: CoX/ToB raid-scaling disclosure + superior/multi-slot verification"
```

---

## Task 7: Validator (`validate_drop_rate.py`)

**Files:**
- Create: `data/validate_drop_rate.py`, `tests/drop_rates/test_validate_drop_rate.py`

**Interfaces:**
- Produces: `python data/validate_drop_rate.py` exits 0 on valid committed data, 1 on any violation; prints a coverage report (spec §9).

- [ ] **Step 1: Write the failing test** (`tests/drop_rates/test_validate_drop_rate.py`)

```python
import json, os, subprocess, sys
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VALIDATOR = os.path.join(REPO, "data", "validate_drop_rate.py")
PY = sys.executable

def _run(*args): return subprocess.run([PY, VALIDATOR, *args], capture_output=True, text=True)

def test_passes_on_committed_data():
    r = _run()
    assert r.returncode == 0, f"validator failed on committed data:\n{r.stdout}\n{r.stderr}"

def test_fabricated_rate_without_raw_fails(tmp_path):
    bad = {"_provenance": {"record_count": 1}, "records": [
        {"item_id": 4151, "item": "Abyssal whip", "source": "X", "source_node_type": "monster",
         "drop_rate": 0.5, "drop_rate_raw": "", "rolls": 1, "drop_rate_status": "sourced", "variants": []}
    ], "_excluded": []}
    p = tmp_path / "drop_rates.json"; p.write_text(json.dumps(bad))
    r = _run("--dataset", str(p))
    assert r.returncode == 1 and "fabricat" in (r.stdout + r.stderr).lower()

def test_probability_over_one_fails(tmp_path):
    bad = {"_provenance": {"record_count": 1}, "records": [
        {"item_id": 4151, "item": "X", "source": "Y", "source_node_type": "monster",
         "drop_rate": 1.5, "drop_rate_raw": "3/2", "rolls": 1, "drop_rate_status": "sourced", "variants": []}
    ], "_excluded": []}
    p = tmp_path / "drop_rates.json"; p.write_text(json.dumps(bad))
    assert _run("--dataset", str(p)).returncode == 1

def test_null_with_sourced_status_fails(tmp_path):
    bad = {"_provenance": {"record_count": 1}, "records": [
        {"item_id": 4151, "item": "X", "source": "Y", "source_node_type": "monster",
         "drop_rate": None, "drop_rate_raw": "", "rolls": 1, "drop_rate_status": "sourced", "variants": []}
    ], "_excluded": []}
    p = tmp_path / "drop_rates.json"; p.write_text(json.dumps(bad))
    assert _run("--dataset", str(p)).returncode == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `venv/bin/python -m pytest tests/drop_rates/test_validate_drop_rate.py -v`
Expected: FAIL (validator missing).

- [ ] **Step 3: Implement `data/validate_drop_rate.py`**

```python
#!/usr/bin/env python3
"""Drop-rate dataset validator (iron-gate tradition; design §9). Exits non-zero
on any violation. Re-parses every numeric rate from its raw string to prove no
fabrication. Prints a coverage report (by node_type + status; slayer-resolution
line; ToA-canonical disclosure)."""
from __future__ import annotations

import argparse, json, math, os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from data._rarity_grammar import parse_rarity  # noqa: E402

errors: list[str] = []
def check(cond, msg):
    if not cond: errors.append(msg)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=os.path.join(HERE, "drop_rates.json"))
    ap.add_argument("--data", default=HERE)
    ns = ap.parse_args()
    doc = json.load(open(ns.dataset, encoding="utf-8"))
    records = doc["records"]
    idict = json.load(open(os.path.join(ns.data, "item_dictionary.json"), encoding="utf-8"))
    item_ids = {r["item_id"] for r in idict["records"]}
    clog_ids = {r["item_id"] for r in
                json.load(open(os.path.join(ns.data, "collection_log.json"), encoding="utf-8"))["records"]}

    for r in records:
        rate = r.get("drop_rate"); status = r.get("drop_rate_status"); raw = r.get("drop_rate_raw")
        # Inv 1: rate null or in (0,1]
        check(rate is None or (isinstance(rate, (int, float)) and 0 < rate <= 1),
              f"drop_rate out of range: {r['item']}@{r['source']} = {rate}")
        # Inv 2: no fabrication — numeric rate must re-parse from raw to the same value
        if rate is not None:
            check(bool(raw), f"fabricated rate (no raw): {r['item']}@{r['source']}")
            if raw:
                rp, _rolls, _st = parse_rarity(raw)
                check(rp is not None and math.isclose(rp, rate, rel_tol=1e-6),
                      f"raw does not re-parse to rate (fabricated?): {r['item']}@{r['source']} raw={raw!r} rate={rate}")
        # Inv 3: null rate -> a real reason (status != sourced)
        if rate is None:
            check(status and status != "sourced",
                  f"null rate with status 'sourced': {r['item']}@{r['source']}")
        # Inv 4: rolls int >= 1
        check(isinstance(r.get("rolls"), int) and r["rolls"] >= 1,
              f"rolls must be int>=1: {r['item']}@{r['source']} = {r.get('rolls')}")
        # Inv 5: item_id resolves + within clog scope
        check(r["item_id"] in item_ids, f"item_id not in dictionary: {r['item_id']}")
        check(r["item_id"] in clog_ids, f"item_id outside collection-log scope: {r['item_id']}")
        # Inv 6: variants well-formed
        for v in r.get("variants", []):
            check("condition" in v, f"variant missing condition: {r['item']}@{r['source']}")
            vr = v.get("drop_rate")
            check(vr is None or (isinstance(vr, (int, float)) and 0 < vr <= 1),
                  f"variant rate out of range: {r['item']}@{r['source']} {v}")

    # Inv 7: envelope consistency
    check(doc.get("_provenance", {}).get("record_count") == len(records),
          "record_count != len(records)")
    check(isinstance(doc.get("_excluded"), list), "_excluded missing/not a list")

    if errors:
        print(f"DROP-RATE VALIDATION FAILED -- {len(errors)} violation(s):")
        for e in errors[:50]: print("  -", e)
        return 1
    # coverage report (informational; spec §9.8)
    by_status = Counter(r["drop_rate_status"] for r in records)
    by_node = Counter(r["source_node_type"] for r in records)
    clog = json.load(open(os.path.join(ns.data, "collection_log.json"), encoding="utf-8"))["records"]
    slayer_ids = {c["item_id"] for c in clog if c.get("source") == "Slayer"}
    resolved_ids = {r["item_id"] for r in records if r["drop_rate_status"] == "sourced"}
    slayer_resolved = len(slayer_ids & resolved_ids)
    toa = sum(1 for r in records if r["source"] == "Chest (Tombs of Amascut)")
    print("DROP-RATE VALIDATION PASSED -- all invariants hold.")
    print(f"  records: {len(records)} | sourced: {by_status.get('sourced', 0)}")
    print(f"  by status: {dict(by_status)}")
    print(f"  by source_node_type: {dict(by_node)}")
    print(f"  slayer-bundle uniques resolved to a real monster rate: {slayer_resolved}/{len(slayer_ids)}")
    print(f"  ToA records (invocation-canonical, scaling disclosed in variants): {toa}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests + the validator on committed data**

Run: `venv/bin/python -m pytest tests/drop_rates/test_validate_drop_rate.py -v` (PASS), then `venv/bin/python data/validate_drop_rate.py` (exit 0, prints coverage). If real-data violations surface, fix the PARSER (Task 3/5/6) or disclose via status — never loosen an invariant to pass.

- [ ] **Step 5: Commit**

```bash
git add data/validate_drop_rate.py tests/drop_rates/test_validate_drop_rate.py
git commit -m "drop-rates: committed validator + coverage report"
```

---

## Task 8: Golden rarity set + final verification

**Files:**
- Create: `tests/drop_rates/test_drop_rates_golden.py`

**Interfaces:**
- Consumes: committed `data/drop_rates.json` (values read at runtime).

- [ ] **Step 1: Write the golden test** (`tests/drop_rates/test_drop_rates_golden.py`)

```python
import json, math, os
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RECS = json.load(open(os.path.join(REPO, "data", "drop_rates.json")))["records"]

def _find(item, source):
    hits = [r for r in RECS if r["item"] == item and r["source"] == source]
    assert len(hits) == 1, f"{item}@{source}: expected 1, got {len(hits)}"
    return hits[0]

def test_whip_from_abyssal_demon():  # note-1 proof on real data
    r = _find("Abyssal whip", "Abyssal demon")
    assert math.isclose(r["drop_rate"], 1/512, rel_tol=1e-6) and r["drop_rate_raw"] == "1/512"

def test_granite_maul_resolves_to_a_real_monster():
    hits = [r for r in RECS if r["item"] == "Granite maul" and r["drop_rate_status"] == "sourced"]
    assert hits, "Granite maul did not resolve to any sourced monster rate"

def test_comma_denominator_unique_parsed():  # M3 — a rare unique with a comma rate
    pk = [r for r in RECS if r["item"] == "Pet kraken" and r["source"] == "Kraken"]
    assert pk and pk[0]["drop_rate_status"] == "sourced"
    assert math.isclose(pk[0]["drop_rate"], 1/3000, rel_tol=1e-6)  # raw "1/3,000"

def test_superior_condition_present_somewhere():  # M6 — superior tagging survived to data
    assert any(r.get("source_condition") == "superior" for r in RECS)

def test_no_fabricated_rates():
    for r in RECS:
        if r["drop_rate"] is not None:
            assert r["drop_rate_raw"], f"fabricated: {r['item']}@{r['source']}"

def test_every_null_has_a_reason():
    for r in RECS:
        if r["drop_rate"] is None:
            assert r["drop_rate_status"] not in (None, "", "sourced")
```

- [ ] **Step 2: Run the golden test**

Run: `venv/bin/python -m pytest tests/drop_rates/test_drop_rates_golden.py -v`
Expected: PASS. (If `test_whip_from_abyssal_demon` fails, the bulk source/parse missed it — fix Task 4 before proceeding.)

- [ ] **Step 3: Full verification**

Run:
```bash
venv/bin/python -m pytest tests/ -q
venv/bin/python data/validate_drop_rate.py
for v in validate_income validate_cost validate_kg; do venv/bin/python data/$v.py >/dev/null && echo "$v ok"; done
venv/bin/python data/parse_drop_rates.py && git diff --quiet data/drop_rates.json && echo "byte-stable"
```
Expected: full suite passes (existing 481 + new drop_rates tests); `validate_drop_rate` exits 0; the other three validators still exit 0; `drop_rates.json` regenerates byte-stably.

- [ ] **Step 4: Commit**

```bash
git add tests/drop_rates/test_drop_rates_golden.py
git commit -m "drop-rates: golden rarity set + final verification"
```

---

## Deferred (spec §12 — do NOT build)
Clue reward-casket rarities (674 clue items); full per-variant enumeration beyond the captured conditions; regular-monster full drop tables; consumer wiring (income recompute, loot-filter beams); live refresh. Each is a separate future brick.
