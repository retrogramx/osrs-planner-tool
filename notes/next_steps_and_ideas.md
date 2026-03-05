# Next Steps & Ideas

## Tier 1: Quick Wins (build on what you have)

### 1. More Goal Definitions
Add 2-3 more goals beyond `full_graceful.json` — things like `99_fishing`, `quest_point_cape`, or `barrows_gloves`. Right now the planner only handles one goal, so adding more will immediately reveal where the code is too tightly coupled to agility and marks of grace. For example, a fishing goal doesn't have "marks" at all — it's just XP to a target level. This will push you to rethink the `Goal` and `Task` models to be more flexible. Start with a simple single-skill goal (like 99 Fishing) before attempting multi-skill goals (like Barrows Gloves).

**What you'll learn:** Designing flexible data models, refactoring existing code without breaking tests.

**Files to modify:** `models.py`, `planner.py`, new JSON files in `goals/`.

---

### 2. `--marks` Flag
The planner always assumes you have 0 marks of grace. In reality, you might already have 120 marks saved up and want to plan from there. Adding a `--marks 120` flag to the CLI (and a `marks` query parameter to the API) would let users resume partway through a goal. This is a small change that touches the CLI, API, and planner — good practice for making changes across multiple files.

**What you'll learn:** Passing data through multiple layers (CLI -> planner -> output), updating tests for new parameters.

**Files to modify:** `cli.py`, `api.py`, `planner.py`, `test_planner.py`.

---

### 3. API Error Handling
Right now if you pass a bad player name or invalid goal ID to the API, FastAPI returns an ugly 500 Internal Server Error. Users should get a clean 404 with a helpful message like `{"detail": "Player 'FakeName123' not found"}`. FastAPI has a built-in `HTTPException` class for this — wrap your endpoint logic in `try`/`except` blocks that catch `PlayerNotFoundError` and `FileNotFoundError` and return proper HTTP status codes.

**What you'll learn:** HTTP status codes (404, 400, 500), FastAPI error handling patterns, defensive programming.

**Files to modify:** `api.py`.

---

## Tier 2: Bigger Features

### 4. OSRS Wiki API Integration
The OSRS Wiki has a real REST API that returns structured data about items, skills, quests, NPCs, and more. Instead of hardcoding XP rates and mark rates in your JSON files, you could pull them from the wiki programmatically. Start small — fetch the data for one agility course and compare it to your hardcoded values. The wiki API uses MediaWiki's format, which is more complex than the hiscores JSON, so expect to spend time learning how to navigate nested response structures.

**Wiki API base:** `https://oldschool.runescape.wiki/api.php`

**What you'll learn:** Working with a more complex API, query parameters, parsing deeply nested JSON, caching responses (so you're not hitting the wiki on every request).

**New files:** A new module like `wiki.py` for wiki API functions.

---

### 5. Automate Goal JSON Creation
Instead of hand-writing JSON goal files, build a script that pulls data from the OSRS Wiki and generates them automatically. For example, it could fetch all rooftop agility courses, their level requirements, XP rates, and mark rates, then output a properly formatted `full_graceful.json`. This pairs well with #4 (Wiki API) — do that first, then build this on top of it.

**What you'll learn:** Data pipelines (fetch -> transform -> save), file I/O with `json.dump()`, scripting vs application code, data validation (making sure wiki data matches your model).

**New files:** A script like `scripts/generate_goal.py` or a new CLI command.

---

### 6. Frontend UI (Jinja2 + HTMX)
Make the planner accessible through a real web page instead of just JSON endpoints. The recommended path is **Jinja2 + HTMX** because it builds directly on your existing FastAPI backend — no need to learn a separate frontend framework. Jinja2 is a template engine that lets you write HTML with Python variables embedded in it. HTMX lets you make pages interactive (like fetching a plan without a full page reload) with just HTML attributes — no JavaScript required.

You could host it for free on platforms like Railway, Render, or Fly.io so friends can use it from their browser.

**The alternative path** — building a separate frontend with React, Vue, or Svelte — is more work and requires learning JavaScript, but is a more marketable skill if you're interested in web development.

**What you'll learn:** HTML/CSS basics, template engines, how web pages are served, static files, form handling.

**New files:** `templates/` directory with `.html` files, `static/` directory for CSS, new FastAPI routes that return HTML instead of JSON.

**References:**
- Jinja2: https://jinja.palletsprojects.com/
- HTMX: https://htmx.org/
- FastAPI templates: https://fastapi.tiangolo.com/advanced/templates/

---

### 7. RuneLite Plugin
RuneLite is the most popular OSRS client and supports custom plugins. A planner plugin could overlay training steps directly in the game UI. However, RuneLite plugins are written in **Java**, not Python. None of your existing Python code would carry over — this would be a completely separate project. You'd need to learn Java, the RuneLite plugin API, Gradle/Maven build systems, and Java's type system. The RuneLite developer community is active and has good documentation, but the learning curve is steep.

**Consider this when:** You've built out the Python version as far as you want and are ready to learn a second language. Or if you specifically want to learn Java.

**What you'll learn:** A second programming language (Java), plugin architectures, event-driven programming, GUI development.

**References:**
- RuneLite plugin guide: https://github.com/runelite/plugin-hub
- RuneLite wiki: https://github.com/runelite/runelite/wiki/

---

## Tier 2.5: Bigger Vision

### 8. Discord Bot for Your GIM Group
Build a Discord bot that brings the planner into your Hardcore Group Ironman's Discord server. Your group has a brand new player and a returning player — a bot that generates plans on command would help them figure out what to train and in what order without needing to alt-tab to a website.

**Example commands:**
- `!plan WalksUnseen graceful` — Generate a plan for a specific player and goal
- `!stats Tiger0295` — Quick stat lookup without leaving Discord
- `!group` — Show all 5 group members' stats side by side
- `!suggest WalksUnseen` — "Based on your stats, here's what to work on next"

The bot is a perfect "surprise your friends" project — deploy it to your server and let them discover it. Python's `discord.py` library handles all the Discord connection logic, so your bot is really just another thin layer on top of your existing `fetch_stats`, `load_goal`, and `generate_plan` functions — the same pattern as your FastAPI layer.

**Group-specific features you could add later:**
- Shared goal tracking ("our group needs 5 Barrows Gloves — who's closest?")
- Skill comparison ("who has the highest Fishing?")
- Session coordination ("Adrian is doing Agility tonight, who wants to fish?")

**What you'll learn:** Async programming (`discord.py` uses `async`/`await`), bot deployment, event-driven architecture, building for real users who will give you immediate feedback.

**New files:** `bot.py` or `discord_bot.py` for the bot, possibly a config file for the bot token.

**References:**
- discord.py docs: https://discordpy.readthedocs.io/
- Discord developer portal (create your bot): https://discord.com/developers/applications
- discord.py bot tutorial: https://discordpy.readthedocs.io/en/stable/quickstart.html

---

### 9. Session Planner
Instead of "here's how to get Graceful," answer the question **"I have 2 hours tonight, what should I work on?"** You'd set multiple active goals, and the planner prioritizes tasks based on your current stats, goal progress, and available time. This turns the tool from a one-time plan generator into something you check every time you sit down to play.

**What you'll learn:** Prioritization algorithms, multi-goal planning, time-boxing calculations.

**Files to modify:** `planner.py`, `cli.py`, `api.py`.

---

### 10. Ironman Dependency Resolver
This is the most unique and ambitious direction. Ironmen can't trade, so every goal has hidden dependencies — want to craft something? You need to gather materials yourself. Need materials? You might need a certain skill level to access them. Your backwards-planning algorithm is already a dependency resolver at its core. Extending it to handle chains like "Barrows Gloves requires X quest, which requires Y skill, which requires Z items, which requires W skill to gather" would make this tool genuinely unique in the OSRS ecosystem. Nothing like this exists right now.

**What you'll learn:** Dependency graphs, topological sorting, recursive planning, handling circular dependencies.

**Files to modify:** `models.py`, `planner.py`, new goal definitions with dependency chains.

---

## Tier 3: Architectural Improvements

### 11. Make the Planner Generic
This is the most important change for the project's long-term future. Right now `generate_plan()` is hardcoded around agility and marks of grace — it tracks `current_marks`, checks `marks_per_hour`, and stops at 260. If you want to support goals like "99 Fishing" (no marks, just XP), "Barrows Gloves" (multiple skills + quests), or "Fire Cape" (combat + gear requirements), the planner needs to handle different types of requirements and tasks generically.

This means rethinking how `Goal` and `Task` are structured. Instead of `target_marks` on every goal, goals could have a list of generic requirements (skill levels, item quantities, quest completions). Instead of every task having `marks_per_hour`, tasks could produce different types of "output" depending on the goal.

**What you'll learn:** Abstraction, refactoring a working system without breaking it, designing for extensibility, keeping tests green while changing internals.

**Files to modify:** `models.py`, `planner.py`, `test_planner.py`, all goal JSON files.

---

### 12. SQLite Persistence
Save generated plans to a database so users can track their progress over time. Instead of generating a fresh plan every time, users could save a plan, mark steps as complete, and see what's left. Python has a built-in `sqlite3` module — no extra dependencies needed. The database would store accounts, saved plans, and completion status.

**What you'll learn:** SQL basics (CREATE TABLE, INSERT, SELECT, UPDATE), database design, connecting a database to your API, migrations (updating the database schema as your models change).

**New files:** `database.py` for DB functions, a `.sql` or migration file for the schema, new API endpoints for CRUD operations.

---

## Recommended Order
1. More goal definitions (exposes how to generalize the planner)
2. `--marks` flag (quick win, immediately useful)
3. API error handling (small but important)
4. Make the planner generic (required before most features below)
5. Discord bot for your GIM group (real users, immediate feedback)
6. OSRS Wiki API integration (big learning opportunity)
7. Session planner (makes the tool something you use daily)
8. Jinja2 + HTMX frontend (makes it a real product)
9. Ironman dependency resolver (the unique killer feature)
10. SQLite persistence (when you want to save plans)
11. Automate goal JSON creation (pairs with Wiki API)
12. RuneLite plugin (when you're ready for Java)

---

## Data Sources & Limitations

There is no single source for a player's "full" data. Jagex's APIs are limited, and community tools fill the gaps with RuneLite plugins. Here's what's available:

### What You Can Pull Automatically

| Data | Source | Requires Plugin? | Notes |
|---|---|---|---|
| Skills, levels, XP | Jagex Hiscores API | No | What we already use in `hiscores.py` |
| Boss kill counts | Jagex Hiscores API | No | In the same JSON response, currently filtered out |
| Minigame scores | Jagex Hiscores API | No | Same response — LMS, Soul Wars, GOTR, etc. |
| XP history & gains | Temple OSRS API | No | Auto-tracked from hiscores snapshots |
| Collection log | Temple OSRS API | Yes (Temple plugin) | Players must install and sync |

### What You CANNOT Pull From Any Public API

| Data | Workaround |
|---|---|
| Quest completions | Manual input (`!complete dragon_slayer`) or build your own RuneLite plugin |
| Achievement diary completions | Manual input or own plugin |
| Combat achievements | Manual input or own plugin |
| Character appearance/model | Only accessible from within the game client |
| Bank contents | Not exposed anywhere externally |
| Equipment worn | Not exposed anywhere externally |

### Key Tools & How They Get Data

**RuneProfile** (https://runeprofile.com/)
- Shows skills, collection log, quests, diaries, combat achievements, and character model
- Works via a **RuneLite plugin** that reads game state directly and uploads to their servers
- No public API for third-party use — data is display-only on their website
- Source code (TypeScript): https://github.com/ReinhardtR/runeprofile

**Temple OSRS** (https://templeosrs.com/)
- Tracks skills, XP gains, boss KC, collection log, pets, and group stats
- **Has a public API** with documented endpoints: https://templeosrs.com/api_doc.php
- Key endpoints: player stats, player gains, collection log items, group members
- Collection log requires their RuneLite plugin to be installed
- Does NOT track quests or diaries

**Wise Old Man** (https://wiseoldman.net/)
- Similar to Temple — tracks skills, XP gains, boss KC, competitions
- Has a public API: https://docs.wiseoldman.net/
- Has built-in GIM group support
- Does NOT track quests or diaries

**WikiSync** (https://oldschool.runescape.wiki/w/RuneScape:WikiSync)
- RuneLite plugin that uploads quest completions, diary completions, and skill levels
- The only external source for quest/diary data
- **API is restricted** — the wiki team explicitly says it's for wiki use only and actively blocks third-party access
- Source code: https://github.com/weirdgloop/wikisync-api

### What This Means For The Project

For the Discord bot and planner, the realistic approach is:
1. **Skills/bosses/minigames** — Pull from Jagex Hiscores API (already built)
2. **XP tracking over time** — Use Temple OSRS or Wise Old Man API
3. **Collection log** — Use Temple OSRS API (group needs Temple RuneLite plugin)
4. **Quest/diary completions** — Manual input via Discord bot commands, stored in your own database (SQLite)
5. **Goal requirements** — Pull from OSRS Wiki API (quest/diary requirements are game data, not player data)

If you eventually want automatic quest/diary tracking without manual input, the answer is building your own RuneLite plugin — that's how RuneProfile and WikiSync do it. That's the Java project from the ideas list.

---

## Reference Sources
- **OSRS Wiki** — Primary source for XP rates, quest requirements, skill training guides: https://oldschool.runescape.wiki/
- **OSRS Wiki API** — Structured data access for items, skills, quests: https://oldschool.runescape.wiki/api.php
- **OSRS Portal** — Community calculators with detailed XP rates, method breakdowns, and level brackets for most skills. No public API, but useful as a reference for verifying your data and seeing how other tools handle things like multiple training methods at the same level, profit/cost per method, and tick manipulation rates: https://osrsportal.com/
- **Temple OSRS API docs** — Public API for player stats, gains, collection log, groups: https://templeosrs.com/api_doc.php
- **Wise Old Man API docs** — Public API for player tracking, competitions, groups: https://docs.wiseoldman.net/
- **RuneProfile source** — TypeScript codebase showing how they structure player data: https://github.com/ReinhardtR/runeprofile
- **WikiSync source** — How the wiki syncs quest/diary data (restricted API): https://github.com/weirdgloop/wikisync-api
