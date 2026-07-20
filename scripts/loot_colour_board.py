#!/usr/bin/env python3
"""Render the loot-filter colour review board from data/item_colours.json.

This is the IN-FLIGHT colour-treatment prototype (owner-directed, not yet baked into the real
emitter/palette). It captures the treatment decisions from the 2026-07-18 colour pass so they
survive between sessions:
  - crystal items -> true cyan (their pale sprites sampled grey)
  - AMMO coloured by METAL, not sprite (dragon is the ONLY red; adamant green, rune turquoise,
    mithril blue, amethyst purple, ...); poisoned (p/p+/p++) variants get a lime rim
  - TEXT is a visibly-hued tint of the item's own colour (not flat black/white) + a contrast shadow
  - BORDER is a rim-glow (the hue lifted toward white); elites get a brighter rim + a beam
Usage: ./venv/bin/python scripts/loot_colour_board.py [output.html]   (default outputs/item-colours-board.html)
Then publish the HTML as an Artifact for owner review.

STILL PENDING (next session): owner sign-off on the treatment; the finer ammo ACCENT layer
(dragon arrows = red + off-white; enchant (e) = pearl; gem-tip bolts = gem colour); then bake the
approved treatment into palette.py/emit.py + item_colours.json. See MEMORY handoff.
"""
import json, html, os, collections, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "outputs", "item-colours-board.html")
colours = json.load(open(os.path.join(REPO, "data", "item_colours.json"), encoding="utf-8"))

# --- ammo METAL / gem identity map (dragon=red is the ONLY red) ---
AMMO = {"dragon":"c83232","amethyst":"9b59b6","runite":"40e0d0","rune":"40e0d0","adamant":"3cb371",
        "mithril":"4169e1","black":"3b3b3b","steel":"9fb0b8","white":"e6e6e6","iron":"6b6b6b","bronze":"cd7f32",
        "dragonstone":"c030a0","onyx":"402030","diamond":"dfeeff","ruby":"d02030","emerald":"30c030",
        "sapphire":"1e60ff","topaz":"e8a24a","pearl":"eae0c8","jade":"7bbd6b","opal":"8fd6c0",
        "silver":"c8c8d0","bone":"c7b9a0","broad":"6b8f5a","ogre":"9c7a4a","brutal":"9c7a4a"}
AMMO_ORDER = ["dragonstone","dragon","amethyst","runite","rune","adamant","mithril","black","steel",
              "white","iron","bronze","onyx","diamond","ruby","emerald","sapphire","topaz","pearl",
              "jade","opal","silver","bone","broad","ogre","brutal"]
def ammo_hex(n):
    ln = n.lower()
    for k in AMMO_ORDER:
        if k in ln: return AMMO[k]
    return None
def poisoned(n): return bool(re.search(r"\(p\++?\)", n.lower()))

for n, v in colours.items():
    if "crystal" in n.lower():
        v["hex"] = "#ff8fe9f6" if n.lower().startswith("enhanced") else "#ff53c8dc"; v["source"] = "curated"
    if v["family"] == "ammo":
        a = ammo_hex(n)
        if a: v["hex"] = "#ff" + a; v["source"] = "curated"

def rgb(h):
    h = h.lstrip("#")
    if len(h) == 8: h = h[2:]
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
def hx(t): return "#%02x%02x%02x" % tuple(max(0, min(255, int(c))) for c in t)
def lum(h): r, g, b = rgb(h); return 0.299*r + 0.587*g + 0.114*b
def mix(h, tgt, t): r, g, b = rgb(h); return hx((r+(tgt[0]-r)*t, g+(tgt[1]-g)*t, b+(tgt[2]-b)*t))
def text_fill(h): return mix(h, (255,255,255), 0.58) if lum(h) <= 140 else mix(h, (0,0,0), 0.70)
def text_shadow(h): return "rgba(0,0,0,.72)" if lum(text_fill(h)) > 128 else "rgba(255,255,255,.30)"
def rim(h, t): return mix(h, (255,255,255), t)
LIME = "#b6e03a"

FAM_ORDER = ["seed","herb","rune","ore","bar","log","plank","gem","ammo","food","bones","essence"]
FAM_LABEL = {"seed":"Seeds","herb":"Herbs","rune":"Runes","ore":"Ores","bar":"Bars","log":"Logs",
             "plank":"Planks","gem":"Gems","ammo":"Ammo","food":"Food","bones":"Prayer (bones)","essence":"Essence"}
SRC = {"curated":"curated","sprite":"sprite","sprite-muted":"sprite (muted)","sprite-fixup":"agent-fixed"}
ELITE = ["Enhanced crystal weapon seed","Zenyte","Onyx","Dragonstone","Torstol seed","Dragon arrow"]

by_fam = collections.defaultdict(list)
for name, v in colours.items(): by_fam[v["family"]].append((name, v))
comp = collections.Counter(v["source"] for v in colours.values())

def chip(name, v, elite=False):
    bg = "#" + v["hex"][3:]; tc = text_fill(v["hex"]); sh = text_shadow(v["hex"])
    br = LIME if (v["family"] == "ammo" and poisoned(name)) else rim(v["hex"], 0.6 if elite else 0.42)
    cls, beam = ("chip elite" if elite else "chip"), ""
    if elite: beam = f'<span class="beam" style="--b:{rim(v["hex"],0.25)}"></span>'
    return (f'<div class="{cls}" style="background:{bg};color:{tc};--rim:{br};--sh:{sh}" '
            f'title="{html.escape(name)} — {v["hex"]}">{beam}'
            f'<span class="nm">{html.escape(name)}</span><span class="hx">{"#"+v["hex"][3:]}</span></div>')

elite_row = "\n".join(chip(n, colours[n], elite=True) for n in ELITE if n in colours)
sections = []
for fam in FAM_ORDER:
    items = sorted(by_fam.get(fam, []), key=lambda t: t[0].lower())
    if not items: continue
    chips = "\n".join(chip(n, v) for n, v in items)
    sections.append(f'<section class="fam"><header class="famhead"><h2>{FAM_LABEL.get(fam, fam.title())}</h2>'
                    f'<span class="count">{len(items)}</span></header><div class="grid">{chips}</div></section>')
stat = lambda k: f'<div class="stat"><b>{comp.get(k,0)}</b><span>{SRC[k]}</span></div>'

page = f"""<title>Loot filter — item colours</title>
<style>
:root {{ --bg:#e9e5dd; --panel:#f3efe8; --panel2:#eae5db; --line:#d6cfc2; --ink:#2b2723;
  --muted:#726a5d; --accent:#b07a2b; --shadow:0 1px 2px rgba(40,34,26,.09); }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#1b1916; --panel:#24211c; --panel2:#2b2721;
  --line:#3a352d; --ink:#ece7dd; --muted:#9b9384; --accent:#d8a24a; --shadow:0 1px 3px rgba(0,0,0,.4); }} }}
:root[data-theme="dark"] {{ --bg:#1b1916; --panel:#24211c; --panel2:#2b2721; --line:#3a352d;
  --ink:#ece7dd; --muted:#9b9384; --accent:#d8a24a; --shadow:0 1px 3px rgba(0,0,0,.4); }}
:root[data-theme="light"] {{ --bg:#e9e5dd; --panel:#f3efe8; --panel2:#eae5db; --line:#d6cfc2;
  --ink:#2b2723; --muted:#726a5d; --accent:#b07a2b; --shadow:0 1px 2px rgba(40,34,26,.09); }}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); line-height:1.45;
  font-family:ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif; -webkit-font-smoothing:antialiased; }}
.wrap {{ max-width:1180px; margin:0 auto; padding:40px 24px 80px; }}
.eyebrow {{ font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:var(--accent); font-weight:600; }}
h1 {{ font-size:30px; margin:.15em 0 .1em; letter-spacing:-.01em; text-wrap:balance; }}
.lede {{ color:var(--muted); max-width:66ch; margin:0 0 22px; }}
.stats {{ display:flex; flex-wrap:wrap; gap:10px; margin:0 0 26px; }}
.stat {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:8px 13px;
  display:flex; flex-direction:column; box-shadow:var(--shadow); }}
.stat b {{ font-size:19px; font-variant-numeric:tabular-nums; }} .stat span {{ font-size:11.5px; color:var(--muted); }}
h2.sec {{ font-size:13px; letter-spacing:.1em; text-transform:uppercase; color:var(--muted);
  margin:0 0 12px; padding-bottom:7px; border-bottom:1px solid var(--line); }}
.fam {{ margin:0 0 28px; }}
.famhead {{ display:flex; align-items:center; gap:9px; position:sticky; top:0; z-index:2;
  background:linear-gradient(var(--bg) 72%, transparent); padding:9px 0 8px; }}
.famhead h2 {{ font-size:16px; margin:0; }}
.famhead .count {{ font-size:12px; color:var(--muted); font-variant-numeric:tabular-nums;
  background:var(--panel2); border:1px solid var(--line); border-radius:20px; padding:1px 9px; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(146px,1fr)); gap:8px; }}
.chip {{ border:1.5px solid var(--rim); border-radius:7px; padding:9px 10px 8px; min-height:52px;
  display:flex; flex-direction:column; justify-content:space-between; overflow:hidden; box-shadow:var(--shadow); }}
.chip .nm {{ font-size:12.5px; font-weight:700; line-height:1.2; word-break:break-word;
  text-shadow:0 1px 0 var(--sh), 0 0 2px var(--sh); }}
.chip .hx {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:10px; opacity:.62; margin-top:5px; }}
.elitegrid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(210px,1fr)); gap:12px; margin:0 0 34px; }}
.chip.elite {{ border-width:2.5px; padding:16px 14px 13px; min-height:88px; position:relative;
  box-shadow:0 0 0 1px var(--rim), 0 0 22px -4px var(--rim); }}
.chip.elite .nm {{ font-size:16px; font-weight:800; letter-spacing:-.01em; }}
.chip.elite .beam {{ position:absolute; top:-2px; right:14px; width:12px; height:26px; border-radius:0 0 6px 6px;
  background:linear-gradient(var(--b), transparent); filter:blur(.5px); }}
</style>
<div class="wrap">
  <div class="eyebrow">Gilded Tome · ironman filter</div>
  <h1>Item colours — review board</h1>
  <p class="lede">Ammo coloured by its metal (dragon-only red, poison=lime rim); text a visibly-hued tint
  of the item's own colour with a contrast shadow; border a rim-glow; elites brighter rim + a beam.
  Panel, border and text are all real filter levers.</p>
  <div class="stats">{''.join(stat(k) for k in ["curated","sprite","sprite-muted","sprite-fixup"])}</div>
  <h2 class="sec">Elite drops</h2>
  <div class="elitegrid">{elite_row}</div>
  <h2 class="sec">All families — hued text · metal-based ammo · rim-glow border</h2>
  {''.join(sections)}
</div>"""
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, "w", encoding="utf-8").write(page)
print("wrote", OUT)
