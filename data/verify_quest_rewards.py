#!/usr/bin/env python3
"""Quest-reward source-grounding verifier (quest-foundation fabrication gate).

Checks that each seed reward in data/quest_rewards.json has a distinctive
SOURCE TOKEN present (case-insensitive) in the quest's cached ==Rewards==
wiki block.  This is a heuristic fabrication gate, NOT a full semantic parser:
it confirms that a key identifying term for each reward appears in the Rewards
section of the wiki page, which is enough to catch fabricated rewards (like an
unlock listed under "Required for completing" instead of "Rewards").

Scope:
  - FATAL discrepancy: a required token is missing from the quest's reward block.
  - INFORMATIONAL missing_note: a wiki reward bullet has no matching seed reward
    (completeness gap in the seed — expected by design for a shape-sample seed).
  - A quest in the seed with no cache entry is FATAL (can't verify).
  NOT checked: semantic accuracy beyond token presence, XP formula correctness,
  or post-live wiki text beyond what the cache captured.

Cache (data/raw/quest_reward_blocks.json):
  Committed snapshot of each quest's ==Rewards== block. Reproducible offline.
  --refresh re-fetches live wiki pages and rewrites the cache.

Usage:
  ./venv/bin/python data/verify_quest_rewards.py          # offline (default)
  ./venv/bin/python data/verify_quest_rewards.py --refresh
Exit 0 if no discrepancies (PASSED), 1 otherwise (FAILED).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REWARDS_PATH = os.path.join(ROOT, "data", "quest_rewards.json")
CACHE_PATH = os.path.join(ROOT, "data", "raw", "quest_reward_blocks.json")
WIKI_BASE = "https://oldschool.runescape.wiki/w/{name}?action=raw"
UA = "GildedTome-research/1.0 (aalvarez0295@gmail.com)"
CACHE_DATE = "2026-06-22"


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------

def extract_rewards_block(wikitext: str) -> str:
    """Return the text of the quest's ==Rewards== section (from the ==Rewards==
    heading to the next ==-level heading).  This block-scoping is critical:
    tokens are checked against ONLY this section, not the whole page — that is
    what makes a fabricated unlock listed under "Required for completing" get
    flagged even if it appears elsewhere on the page."""
    m = re.search(r"(==Rewards==\s*\n.*?)(?=\n==[^=]|\Z)", wikitext, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


# ---------------------------------------------------------------------------
# Token derivation
# ---------------------------------------------------------------------------

def source_tokens(reward: dict) -> list[str]:
    """Return the distinctive token(s) that MUST appear (case-insensitive) in
    the quest's Rewards block for this reward to be considered grounded.

    Escape hatch: if the reward dict has an explicit ``"source_token"`` string,
    that is used as the sole required token.  It must still be a genuine
    substring of the block — it cannot be used to fake grounding.

    Token rules by reward_type:
      items       -> item name
      xp/fixed    -> skill name AND comma-formatted amount (e.g. "13,750")
      xp/lamp     -> comma-formatted amount (e.g. "2,500")
      unlock      -> source_token (if set) else access field
      cosmetic    -> cosmetic name
      effect      -> SKIPPED (rides on a granted item already token-checked)
    """
    # Escape hatch
    if "source_token" in reward:
        return [reward["source_token"]]

    rt = reward.get("reward_type")

    if rt == "items":
        return [reward["item"]]

    if rt == "xp":
        form = reward.get("form")
        amount = f"{reward['amount']:,}"
        if form == "fixed":
            return [reward["skill"], amount]
        # choice_lamp -- lamp appears as "antique lamp ... N experience"
        return [amount]

    if rt == "unlock":
        # Use access field as the distinctive locator; fall back to name.
        token = reward.get("access") or reward.get("name", "")
        return [token] if token else []

    if rt == "cosmetic":
        return [reward.get("name", "")]

    # effect -> skip
    return []


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def _wiki_bullets(block: str) -> list[str]:
    """Extract bare text from bullet lines (starting with * in the block)."""
    lines = []
    for line in block.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("*"):
            lines.append(stripped.lstrip("* \t"))
    return lines


def verify_quest_rewards(
    seed_records: list[dict],
    blocks: dict,
) -> tuple[list[dict], list[dict]]:
    """Verify seed rewards against committed wiki blocks.

    Args:
        seed_records: list of quest reward records from quest_rewards.json
        blocks: mapping of quest name -> cache entry with 'rewards_block' key

    Returns:
        discrepancies   -- FATAL: a required token is absent from the block.
                           Each entry: {quest, reward_type, token, detail}
        missing_notes   -- INFORMATIONAL: wiki bullet lines with no matching seed
                           reward (real rewards the seed omits -- expected for a
                           shape-sample seed).
                           Each entry: {quest, wiki_line}
    """
    discrepancies: list[dict] = []
    missing_notes: list[dict] = []

    for rec in seed_records:
        quest = rec.get("quest", "?")
        cache_entry = blocks.get(quest)
        if cache_entry is None:
            discrepancies.append({
                "quest": quest,
                "reward_type": None,
                "token": None,
                "detail": f"No cache entry for quest {quest!r} -- run --refresh to populate.",
            })
            continue

        block = cache_entry.get("rewards_block", "")
        if not block:
            discrepancies.append({
                "quest": quest,
                "reward_type": None,
                "token": None,
                "detail": f"Cache entry for {quest!r} has an empty rewards_block.",
            })
            continue

        block_lower = block.lower()

        # Check each seed reward
        for rw in rec.get("rewards", []):
            rt = rw.get("reward_type")
            if rt == "effect":
                continue  # effects ride on granted items; no direct token to check
            tokens = source_tokens(rw)
            for tok in tokens:
                if not tok:
                    continue
                if tok.lower() not in block_lower:
                    discrepancies.append({
                        "quest": quest,
                        "reward_type": rt,
                        "token": tok,
                        "detail": (
                            f"{quest!r} reward ({rt}) token {tok!r} not found in "
                            f"Rewards block -- possible fabrication or stale seed."
                        ),
                    })

        # Informational: wiki bullets with no matching seed reward
        wiki_lines = _wiki_bullets(block)
        for wl in wiki_lines:
            wl_lower = wl.lower()
            matched = False
            for rw in rec.get("rewards", []):
                for tok in source_tokens(rw):
                    if tok and tok.lower() in wl_lower:
                        matched = True
                        break
                if matched:
                    break
            if not matched:
                missing_notes.append({"quest": quest, "wiki_line": wl})

    return discrepancies, missing_notes


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------

def _quest_wiki_name(quest: str) -> str:
    """Convert quest name to wiki URL slug (underscores for spaces)."""
    return quest.replace(" ", "_")


def _fetch_block(quest: str) -> dict:
    url = WIKI_BASE.format(name=_quest_wiki_name(quest))
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        wikitext = r.read().decode("utf-8")
    block = extract_rewards_block(wikitext)
    return {
        "rewards_block": block,
        "source_url": url.replace("?action=raw", ""),
        "accessed": CACHE_DATE,
    }


def refresh_cache(seed_records: list[dict]) -> dict:
    """Re-fetch wiki pages for all seed quests and return a fresh blocks dict."""
    blocks: dict = {}
    for rec in seed_records:
        quest = rec["quest"]
        print(f"  fetching: {quest}", flush=True)
        try:
            blocks[quest] = _fetch_block(quest)
        except Exception as exc:
            print(f"  ERROR fetching {quest!r}: {exc}", file=sys.stderr)
    return blocks


def load_cache() -> dict:
    with open(CACHE_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_cache(blocks: dict) -> None:
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(blocks, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Verify quest reward source-grounding against committed wiki cache."
    )
    ap.add_argument(
        "--refresh",
        action="store_true",
        help="Re-fetch live wiki pages and rewrite the cache (network required).",
    )
    args = ap.parse_args(argv)

    with open(REWARDS_PATH, encoding="utf-8") as f:
        reward_data = json.load(f)
    seed_records = reward_data.get("records", [])

    if args.refresh:
        print("QUEST-REWARDS SOURCE-GROUNDING: refreshing cache from live wiki ...")
        blocks = refresh_cache(seed_records)
        save_cache(blocks)
        print(f"  Cache written to {CACHE_PATH}")
    else:
        if not os.path.exists(CACHE_PATH):
            print(
                "QUEST-REWARDS SOURCE-GROUNDING FAILED -- cache not found. "
                "Run with --refresh to populate.",
                file=sys.stderr,
            )
            return 1
        blocks = load_cache()

    discrepancies, missing_notes = verify_quest_rewards(seed_records, blocks)

    if missing_notes:
        print(
            f"QUEST-REWARDS SOURCE-GROUNDING: {len(missing_notes)} informational "
            f"missing-note(s) (wiki rewards not in seed -- expected for shape-sample):"
        )
        for mn in missing_notes:
            print(f"  [note] {mn['quest']!r}: wiki has {mn['wiki_line']!r}")

    if discrepancies:
        print(f"\nQUEST-REWARDS SOURCE-GROUNDING FAILED -- {len(discrepancies)} discrepancy(ies):")
        for d in discrepancies:
            print(f"  [FATAL] {d['detail']}")
        return 1

    print(
        f"\nQUEST-REWARDS SOURCE-GROUNDING PASSED -- "
        f"{len(seed_records)} quest(s) verified, 0 discrepancies."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
