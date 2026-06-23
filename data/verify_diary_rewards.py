#!/usr/bin/env python3
"""Achievement-diary reward source-grounding verifier (the diary fabrication gate).

The diary analog of data/verify_quest_rewards.py. Checks that each structured
reward in data/diary_rewards.json has a distinctive SOURCE TOKEN present
(case-insensitive) in that tier's cached wiki reward block. This is a heuristic
fabrication gate, NOT a full semantic parser: it confirms a key identifying term
for each reward (the regional item name, the lamp XP amount, an extra-unlock name,
an explicit effect source_token) appears in the tier's reward text — enough to
catch a fabricated item/lamp/unlock that the live wiki never lists.

SOURCE OF TRUTH (and why the cache is offline-reproducible):
  The committed data/achievement_diaries.json carries, per task, the tier's
  `reward` prose string transcribed from the wiki diary pages (with provenance +
  accessed date in that file's _provenance). All 492 tasks of a tier share one
  consistent reward string, so the per-tier reward block is exactly that string.
  The cache (data/raw/diary_reward_blocks.json) is therefore BUILT FROM that
  committed wiki snapshot — deterministic and offline, unlike the quest verifier
  whose --refresh hits the live wiki. A future live re-pull updates
  achievement_diaries.json itself (its own gate); --refresh here rebuilds the
  cache from it. The periodic LLM verbatim sweep remains the deep audit on top.

Cache (data/raw/diary_reward_blocks.json):
  { "<region>:<tier>": {rewards_block, source_url, accessed}, ... }
  Committed provenance; whitelisted in .gitignore (re-derivable offline).

Usage:
  ./venv/bin/python data/verify_diary_rewards.py            # offline verify (default)
  ./venv/bin/python data/verify_diary_rewards.py --refresh  # rebuild cache from achievement_diaries.json
Exit 0 if no discrepancies (PASSED), 1 otherwise (FAILED).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REWARDS_PATH = os.path.join(ROOT, "data", "diary_rewards.json")
DIARIES_PATH = os.path.join(ROOT, "data", "achievement_diaries.json")
CACHE_PATH = os.path.join(ROOT, "data", "raw", "diary_reward_blocks.json")

# region display -> slug (mirror kg_ingest.builders.supporting.DIARY_REGION_LABELS, inverted)
_REGION_SLUG = {
    "Ardougne": "ardougne", "Desert": "desert", "Falador": "falador",
    "Fremennik": "fremennik", "Kandarin": "kandarin", "Karamja": "karamja",
    "Kourend & Kebos": "kourend", "Lumbridge & Draynor": "lumbridge",
    "Morytania": "morytania", "Varrock": "varrock",
    "Western Provinces": "western", "Wilderness": "wilderness",
}


# ---------------------------------------------------------------------------
# Token derivation
# ---------------------------------------------------------------------------

def source_tokens(record: dict) -> list[tuple[str, str]]:
    """Return (label, token) pairs that MUST appear (case-insensitive) in the
    tier's reward block for this record to be considered grounded.

    Token rules:
      regional_item      -> its name (e.g. "Morytania legs 3")
      lamp               -> comma-formatted XP amount (e.g. "2,500")
      extra_unlocks[]    -> each unlock's name
      effects[]          -> each effect's explicit "source_token" IF present
                            (else skipped — an editorial perk with no verbatim
                            anchor rides on the already-checked regional item).
    """
    out: list[tuple[str, str]] = []

    ri = record.get("regional_item") or {}
    if ri.get("name"):
        out.append(("regional_item", ri["name"]))

    lamp = record.get("lamp") or {}
    if lamp.get("amount") is not None:
        out.append(("lamp", f"{lamp['amount']:,}"))

    for unlock in record.get("extra_unlocks", []):
        if unlock.get("name"):
            out.append(("extra_unlock", unlock["name"]))

    for ef in record.get("effects", []):
        tok = ef.get("source_token")
        if tok:
            out.append(("effect", tok))

    return out


def _block_bullets(block: str) -> list[str]:
    """The diary reward prose is pipe-delimited: 'Item N: | bullet | bullet'.
    Split into bare bullet strings (drop the leading 'Item N:' label fragment)."""
    parts = [p.strip() for p in block.split("|")]
    return [p for p in parts if p]


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_diary_rewards(
    seed_records: list[dict],
    blocks: dict,
) -> tuple[list[dict], list[dict]]:
    """Verify structured diary rewards against committed wiki reward blocks.

    Returns (discrepancies, missing_notes):
      discrepancies -- FATAL: a required token absent from the tier's block, or
                       no cache entry for a seeded tier.
      missing_notes -- INFORMATIONAL: a wiki reward bullet with no matching seed
                       token (a reward the structured overlay omits — expected
                       while the overlay is a partial seed).
    """
    discrepancies: list[dict] = []
    missing_notes: list[dict] = []

    for rec in seed_records:
        region = rec.get("region", "?")
        tier = rec.get("tier", "?")
        key = f"{region}:{tier}"
        entry = blocks.get(key)
        if entry is None:
            discrepancies.append({
                "tier": key, "label": None, "token": None,
                "detail": f"No cache entry for tier {key!r} -- run --refresh to populate.",
            })
            continue
        block = entry.get("rewards_block", "")
        if not block:
            discrepancies.append({
                "tier": key, "label": None, "token": None,
                "detail": f"Cache entry for {key!r} has an empty rewards_block.",
            })
            continue

        block_lower = block.lower()
        tokens = source_tokens(rec)
        for label, tok in tokens:
            if tok and tok.lower() not in block_lower:
                discrepancies.append({
                    "tier": key, "label": label, "token": tok,
                    "detail": (
                        f"{key!r} reward ({label}) token {tok!r} not found in reward "
                        f"block -- possible fabrication or stale seed."
                    ),
                })

        # Informational: wiki bullets with no matching seed token.
        for bullet in _block_bullets(block):
            bl = bullet.lower()
            if not any(tok and tok.lower() in bl for _, tok in tokens):
                missing_notes.append({"tier": key, "wiki_line": bullet})

    return discrepancies, missing_notes


# ---------------------------------------------------------------------------
# Cache management (offline, from the committed wiki snapshot)
# ---------------------------------------------------------------------------

def build_cache_from_data() -> dict:
    """Build the per-tier reward block cache from data/achievement_diaries.json.

    All tasks of a (region, tier) share one reward prose string (verified: 48/48
    tiers are internally consistent); that string is the tier's reward block.
    """
    with open(DIARIES_PATH, encoding="utf-8") as f:
        doc = json.load(f)
    accessed = doc.get("_provenance", {}).get("accessed", "")
    by_tier: dict[str, dict] = {}
    for rec in doc["records"]:
        slug = _REGION_SLUG.get(rec["diary_region"])
        if slug is None:
            raise ValueError(f"unknown diary_region {rec['diary_region']!r}")
        key = f"{slug}:{rec['tier']}"
        block = rec.get("reward", "")
        if key in by_tier:
            if by_tier[key]["rewards_block"] != block:
                raise ValueError(
                    f"inconsistent reward strings within tier {key!r} -- the cache "
                    f"assumes one reward block per tier")
            continue
        by_tier[key] = {
            "rewards_block": block,
            "source_url": rec.get("source_url", ""),
            "accessed": accessed,
        }
    return dict(sorted(by_tier.items()))


def load_cache() -> dict:
    with open(CACHE_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_cache(blocks: dict) -> None:
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(blocks, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Verify diary reward source-grounding against the committed wiki cache."
    )
    ap.add_argument(
        "--refresh", action="store_true",
        help="Rebuild the cache from data/achievement_diaries.json (the committed wiki snapshot).",
    )
    args = ap.parse_args(argv)

    with open(REWARDS_PATH, encoding="utf-8") as f:
        seed_records = json.load(f).get("records", [])

    if args.refresh:
        print("DIARY-REWARDS SOURCE-GROUNDING: rebuilding cache from achievement_diaries.json ...")
        blocks = build_cache_from_data()
        save_cache(blocks)
        print(f"  Cache written to {CACHE_PATH} ({len(blocks)} tier blocks)")
    else:
        if not os.path.exists(CACHE_PATH):
            print(
                "DIARY-REWARDS SOURCE-GROUNDING FAILED -- cache not found. "
                "Run with --refresh to populate.",
                file=sys.stderr,
            )
            return 1
        blocks = load_cache()

    discrepancies, missing_notes = verify_diary_rewards(seed_records, blocks)

    if missing_notes:
        print(
            f"DIARY-REWARDS SOURCE-GROUNDING: {len(missing_notes)} informational "
            f"missing-note(s) (wiki reward bullets not yet in the structured overlay):"
        )
        for mn in missing_notes:
            print(f"  [note] {mn['tier']!r}: wiki has {mn['wiki_line']!r}")

    if discrepancies:
        print(f"\nDIARY-REWARDS SOURCE-GROUNDING FAILED -- {len(discrepancies)} discrepancy(ies):")
        for d in discrepancies:
            print(f"  [FATAL] {d['detail']}")
        return 1

    print(
        f"\nDIARY-REWARDS SOURCE-GROUNDING PASSED -- "
        f"{len(seed_records)} tier(s) verified, 0 discrepancies."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
