# Task: Baseline XP/hr rates, one skill at a time

**Why this exists.** The wiki source audit (`research/wiki-source-catalog.md`) found that *skill XP/hr rates are the least machine-readable data in the whole project* — scattered across ~92 guide pages in inconsistent formats. So instead of trying to auto-scrape them all up front, we'll establish a **manual baseline, one skill at a time**, then automate/refine later. The user will fill these in (with help) in **dedicated sessions** so we don't flood the design session with raw data.

**How to use this:** pick one skill per session. For each meaningful level band, record the *recommended* method(s) and a rough XP/hr, per account family (**main** vs **ironman** — HCIM/GIM = ironman; UIM only if it differs). Rough is fine — we show ranges, never exact. Add the source URL you took it from.

**Completeness is required (a partial list reads as wrong to real players).** Each skill must capture **all** real method categories, not just the obvious click-methods:
- **Active methods** (the standard training tables).
- **Minigame methods** — e.g. **Mahogany Homes** for Construction; often the *best* ironman option.
- **Quest XP** — quests that grant the skill (ties to the optimal-quest order).
- **Passive / over-real-time sources** — e.g. **Managing Miscellania** (hardwood logs, herbs), farming runs, birdhouse runs — resources/XP that accrue in the background.
- For each, note the **account family** it applies to and (for gold-touching methods) how cost/income is realized (main = GE; ironman = gather + High Alch/shops). See the engine↔advisor contract §8.

**Canonical sources per skill** (substitute the skill name):
- Main / general: `https://oldschool.runescape.wiki/w/<Skill>_training` or `https://oldschool.runescape.wiki/w/Pay-to-play_<Skill>_training`
- F2P (if relevant): `https://oldschool.runescape.wiki/w/Free-to-play_<Skill>_training`
- Ironman: `https://oldschool.runescape.wiki/w/Ironman_Guide/<Skill>`
- Structured rate data (where it exists): the `{{Skilling experience rate chart}}` params via `https://oldschool.runescape.wiki/w/<Page>?action=raw`

**Suggested order** (early-game-relevant + structured-data-friendly first):
1. Woodcutting, Fishing, Mining, Cooking, Firemaking (gathering/early, some structured)
2. Thieving, Agility, Crafting, Smithing, Fletching
3. Combat skills: Attack, Strength, Defence, Hitpoints, Ranged, Magic, Prayer
4. Slayer, Herblore, Farming, Hunter, Construction, Runecraft
5. (Sailing — when released)

---

## Per-skill worksheet (fill in)

Copy this block per skill. Leave a column blank if unknown; that becomes a known gap.

### <Skill name>
Sources consulted: `<url(s)>`

| Account family | Level band | Method | ~XP/hr | Cost note (main = GP/XP; iron = gather/effort) | Notes |
|---|---|---|---|---|---|
| main | e.g. 1–15 |  |  |  |  |
| main | 15–30 |  |  |  |  |
| ironman | 1–15 |  |  | gather-time |  |
| ironman | 15–30 |  |  | gather-time |  |

Known gaps for this skill:
- 

---

> When a skill is baselined here, it can be promoted into the real method/rate database (the `recommended_method` opinion edges + rates, per spec §8). Until then the app shows that skill's steps with "effort not yet estimated" (spec §13.3 safety net).
