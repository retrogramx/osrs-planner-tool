#!/usr/bin/env python3
"""Pull each family item's identity hue from its OSRS-wiki inventory sprite (dominant body colour).

Output: data/item_sprite_colours.json -- {name: {hex, family, item_id, sat, status, source_url}}.
Resumable (skips names already present). `status`: ok | ambiguous (low saturation -> needs a human/agent
eye) | fetch-fail (no wiki image found). Politeness: single-threaded, small delay, real User-Agent.

The dominant-body recipe (validated): fully-opaque pixels only (drops the semi-transparent drop shadow),
minus the near-black 1px outline and near-white highlights, then the modal 16-step colour bucket, averaged.
"""
from __future__ import annotations
import collections, io, json, os, sys, time, urllib.request
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
IMP = os.path.join(HERE, "loot_importance.json")
OUT = os.path.join(HERE, "item_sprite_colours.json")
UA = "GildedTome/1.0 (OSRS planner colour pass; contact aalvarez0295@gmail.com)"
AMBIGUOUS_SAT = 40   # max(r,g,b)-min(r,g,b) below this = greyish -> flag for review

def fetch(url: str) -> bytes:
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=25).read()

def icon_bytes(name: str):
    fn = name.replace(" ", "_") + ".png"
    for url in (f"https://oldschool.runescape.wiki/images/{fn}",
                f"https://oldschool.runescape.wiki/w/Special:FilePath/{fn}"):
        try:
            return fetch(url), url
        except Exception:
            continue
    return None, None

def dominant(name: str):
    raw, url = icon_bytes(name)
    if raw is None:
        return None, None, "fetch-fail"
    im = Image.open(io.BytesIO(raw)).convert("RGBA")
    body = [(r, g, b) for r, g, b, a in im.get_flattened_data()
            if a >= 250 and (r + g + b) > 48 and min(r, g, b) < 230]
    if not body:
        return None, url, "fetch-fail"
    buckets = collections.Counter((r // 16, g // 16, b // 16) for r, g, b in body)
    best = buckets.most_common(1)[0][0]
    reps = [c for c in body if (c[0] // 16, c[1] // 16, c[2] // 16) == best]
    r = sum(c[0] for c in reps) // len(reps)
    g = sum(c[1] for c in reps) // len(reps)
    b = sum(c[2] for c in reps) // len(reps)
    sat = max(r, g, b) - min(r, g, b)
    return f"#ff{r:02x}{g:02x}{b:02x}", url, ("ambiguous" if sat < AMBIGUOUS_SAT else "ok")

def main() -> int:
    rows = json.load(open(IMP, encoding="utf-8"))["records"]
    by_name = {}
    for x in rows:
        by_name.setdefault(x["name"], x)   # first id/family per unique name
    out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    only = sys.argv[1] if len(sys.argv) > 1 else None   # optional family filter
    todo = [n for n, x in by_name.items() if n not in out and (only is None or x["family"] == only)]
    print(f"{len(todo)} to fetch ({'family=' + only if only else 'all families'}); {len(out)} already done")
    for i, name in enumerate(todo, 1):
        x = by_name[name]
        hexv, url, status = dominant(name)
        out[name] = {"hex": hexv, "family": x["family"], "item_id": x["item_id"],
                     "status": status, "source_url": url}
        if i % 25 == 0 or i == len(todo):
            json.dump(out, open(OUT, "w", encoding="utf-8"), indent=0, ensure_ascii=False)
            print(f"  {i}/{len(todo)} ... {name} -> {hexv} [{status}]")
        time.sleep(0.15)
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=0, ensure_ascii=False)
    ok = sum(1 for v in out.values() if v["status"] == "ok")
    amb = sum(1 for v in out.values() if v["status"] == "ambiguous")
    fail = sum(1 for v in out.values() if v["status"] == "fetch-fail")
    print(f"DONE: {len(out)} items | ok {ok} | ambiguous {amb} | fetch-fail {fail}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
