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
    # Keep the Lua-query punctuation literal -- parens, single-quotes, commas, dot
    # are valid in a query string and the URL stays human-auditable (and the test
    # pins the literal `bucket('dropsline')`/`select(...)` substrings). Spaces and
    # the backslash escape (apostrophe items) are still percent-encoded. Verified
    # live 2026-06-19: the wiki accepts this unencoded punctuation.
    safe_chars = "()',."
    return f"{API}?action=bucket&format=json&query={urllib.parse.quote(q, safe=safe_chars)}"

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
