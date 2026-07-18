#!/usr/bin/env python3
"""Merge the item colour list (spec §6b/A per-item identity): for every family item pick the best
identity hue by priority — curated map (categorize/palette) > wiki sprite (ok) > wiki sprite (muted)
> family hue. Output data/item_colours.json {name:{hex, source, family, item_id, sprite_status}}.

Curated wins for gems/base-runes/main-metals/main-woods (hand-authored, wiki-informed, reliable);
sprite fills the rest (seeds/herbs/food/niche items); family hue backstops fetch-fails.
"""
from __future__ import annotations
import json, os
from osrs_planner.lootfilter.emit import hue_for
from osrs_planner.lootfilter.palette import FAMILY_HUES

HERE = os.path.dirname(os.path.abspath(__file__))
IMP = os.path.join(HERE, "loot_importance.json")
SPRITES = os.path.join(HERE, "item_sprite_colours.json")
FIXUPS = os.path.join(HERE, "sprite_colours_fixups.json")   # agent-resolved fetch-fails (page/variant + visual)
OUT = os.path.join(HERE, "item_colours.json")

def main() -> int:
    rows = json.load(open(IMP, encoding="utf-8"))["records"]
    sprites = json.load(open(SPRITES, encoding="utf-8")) if os.path.exists(SPRITES) else {}
    fixups = json.load(open(FIXUPS, encoding="utf-8")) if os.path.exists(FIXUPS) else {}
    by_name = {}
    for x in rows:
        by_name.setdefault(x["name"], x)
    out, counts = {}, {"curated": 0, "sprite": 0, "sprite-muted": 0, "sprite-fixup": 0, "family": 0}
    for name, x in sorted(by_name.items()):
        fam = x["family"]
        fam_hue = FAMILY_HUES.get(fam, "#ff9e9e9e")
        curated = hue_for(name, fam)
        sp = sprites.get(name, {})
        sp_hex, sp_status = sp.get("hex"), sp.get("status")
        if curated != fam_hue:
            hexv, source = curated, "curated"
        elif sp_status == "ok" and sp_hex:
            hexv, source = sp_hex, "sprite"
        elif sp_status == "ambiguous" and sp_hex:
            hexv, source = sp_hex, "sprite-muted"
        elif fixups.get(name, {}).get("hex"):   # agent-resolved fetch-fail (correct page/variant + visual)
            hexv, source = fixups[name]["hex"], "sprite-fixup"
        else:                                   # genuinely unresolved -> family backstop
            hexv, source = fam_hue, "family"
        counts[source] += 1
        out[name] = {"hex": hexv, "source": source, "family": fam,
                     "item_id": x["item_id"], "sprite_status": sp_status}
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=0, ensure_ascii=False)
    print(f"wrote {OUT}: {len(out)} items")
    for k, v in counts.items():
        print(f"  {k:12} {v}")
    # what the agents should fix: the family-fallbacks (fetch-fails)
    fam_fallbacks = [n for n, v in out.items() if v["source"] == "family"]
    print(f"agent fix-list (family fallback / fetch-fail): {len(fam_fallbacks)}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
