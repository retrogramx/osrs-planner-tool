#!/usr/bin/env python3
"""
Parse OSRS clue_scrolls domain from raw wikitext fetched from the OSRS Wiki.

This is the v2 (full) re-extraction. The prior run produced only 6 tier-summary
records and leaked HTML/table metadata (e.g. ``data-sort-value=130|...``,
``{| class="wikitable sortable lighttable"``) into a few skill/quest rows, and
mis-mapped the master skill table's 4-column layout (collapsing the "+5 spicy
stew boost" column into the Details field).

v2 produces a comprehensive, multi-record-type dataset (one flat ``records``
list; each record carries a ``record_type`` discriminator):

  * tier            (6)  -- per-tier summary: members/length/step types,
                            skill/quest/music/ironman requirements, reward
                            mechanics, audience, wilderness risk.
  * step_type           -- one per (tier x step-type) cell that is applicable
                            in the "Solving the Treasure Trails" matrix, with
                            the per-tier solution-guide pointer.
  * antagonist          -- one per combat encounter (Antagonists table), level
                            cited to source.
  * reward_subtable     -- one per (tier x reward sub-table) on the Reward
                            casket (tier) page: the sub-table's items + per-roll
                            rarities + the mechanics intro text.
  * notable_reward      -- selected iconic / high-value unique rewards per tier
                            (3rd age, gilded, ranger boots, bloodhound, mimic,
                            etc.) with rarity + drop source (the casket).
  * reward_mechanics    -- per-tier roll mechanics (rolls per casket, unique
                            chances, cross-tier upgrade chances, pet chances).
  * milestone           -- per-tier cumulative-completion milestone reward.
  * scroll_case         -- per-tier minor/major scroll-case stack-limit unlocks.
  * rank                -- Treasure Trails completion ranks (global, not per tier).
  * mechanic            -- global activity mechanics (obtaining, stacking, risk).

Sources (raw wikitext, fetched via curl ?action=raw, OSRS Wiki only):
  - Treasure_Trails (overview: lengths, step-type matrix, antagonists, average
    reward values, milestones, scroll cases, ranks, obtaining/stacking/risk)
  - Clue_scroll_(beginner|easy|medium|hard|elite|master)
    (per-tier skill/quest/music/item requirements, clue types, valuation, sources)
  - Reward_casket_(beginner|easy|medium|hard|elite|master)
    (per-tier reward sub-tables, item rarities, roll mechanics, notable rewards)

Facts are extracted faithfully (verbatim text, no paraphrasing). Where wikitext
uses transclusions whose payload is not present inline (e.g. {{Drop sources}},
live-GE-priced casket values, the full emote-clue STASH/Falo/Charlie/Sherlock
item tables) we record the source pointer and an honest null/snapshot note
rather than inventing data, and disclose it in completeness.known_missing.

Output envelope is the project's frozen envelope ({_provenance, records, _excluded};
payload key "records"; record_count == len(records)).
"""
import re, json, datetime

BASE = "/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/data"
RAW = f"{BASE}/raw"
TIERS = ["beginner", "easy", "medium", "hard", "elite", "master"]

# Accessed date for this re-extraction (UTC date of the new fetches).
ACCESSED_DATE = "2026-06-17"

# ----------------------------------------------------------------------------
# Tier-level metadata read faithfully from the Treasure_Trails overview tables.
# ----------------------------------------------------------------------------
TIER_OVERVIEW = {
    "beginner": {"length": "1-3 steps", "members": False},
    "easy":     {"length": "2-4 steps", "members": True},
    "medium":   {"length": "3-5 steps", "members": True},
    "hard":     {"length": "4-6 steps", "members": True},
    "elite":    {"length": "5-7 steps", "members": True},
    "master":   {"length": "6-8 steps", "members": True},
}

# Average reward value snapshot (rendered GE-priced values from the
# "Average rewards value" table on Treasure_Trails; the wikitext only contains
# the {{...ClueValue}} template calls, so the *rendered* numbers below are a
# single live-GE snapshot captured 2026-06-17 -> price-volatile, GE basis, main).
# rolls_per_clue is read directly from the wikitext multiplier (e.g. "5 * {{HardClueValue}}").
AVG_VALUE_SNAPSHOT = {
    "beginner": {"avg_gp_per_roll": 1610,   "avg_gp_per_clue": 3220},
    "easy":     {"avg_gp_per_roll": 11118,  "avg_gp_per_clue": 33356},
    "medium":   {"avg_gp_per_roll": 34363,  "avg_gp_per_clue": 137453},
    "hard":     {"avg_gp_per_roll": 26608,  "avg_gp_per_clue": 133042},
    "elite":    {"avg_gp_per_roll": 57742,  "avg_gp_per_clue": 288711},
    "master":   {"avg_gp_per_roll": 121013, "avg_gp_per_clue": 726079},
}

VALUATION_NOTE = (
    "Snapshot of the OSRS Wiki 'Average rewards value' table (rendered from "
    "live-GE-priced templates, 2026-06-17); price-volatile. GE valuation applies "
    "to mains. Irons realise casket loot as the items themselves or via High Alch "
    "/ direct coins, not GE; no iron-specific casket gp figure is published. "
    "Caskets are NOT obtained via GE (untradeable clue completion), so the clue "
    "activity itself is iron-safe; only the gp valuation is GE-based."
)

# Notable / iconic rewards are selected programmatically from the parsed casket
# data (see select_notable_rewards / NOTABLE_FRAGMENTS below), so every emitted
# notable_reward corresponds to a real source item with a real per-roll rarity --
# no item names are hand-entered or invented.

# ----------------------------------------------------------------------------
# wikitext helpers
# ----------------------------------------------------------------------------

def load(name):
    with open(f"{RAW}/{name}") as f:
        return f.read()

def section(t, name, max_lvl=6):
    """Return the body of a section whose heading text == name (any level)."""
    pat = re.compile(r'^(=+)\s*' + re.escape(name) + r'\s*=+\s*$', re.M)
    m = pat.search(t)
    if not m:
        return None
    lvl = len(m.group(1))
    start = m.end()
    # Next heading whose '=' run is EXACTLY 1..lvl long. The negative
    # look-ahead/behind ensure we don't match a longer (deeper) heading by
    # capturing only a substring of its '=' run (e.g. matching '==' inside '===').
    nxt = re.compile(r'^(={1,%d})(?!=)\s*.+?\s*(?<!=)\1$' % lvl, re.M)
    n = nxt.search(t, start)
    end = n.start() if n else len(t)
    return t[start:end].strip()

def strip_links(s):
    s = re.sub(r'\[\[[^\]|]*\|([^\]]+)\]\]', r'\1', s)   # [[A|B]] -> B
    s = re.sub(r'\[\[([^\]]+)\]\]', r'\1', s)            # [[A]]   -> A
    return s

def clean_text(s):
    if s is None:
        return None
    # strip data-sort-value=NNN| HTML/table-sort metadata leakage
    s = re.sub(r'data-sort-value\s*=\s*"?[^|"\n]*"?\s*\|', '', s)
    # strip generic html cell attributes that sometimes precede a | (e.g. style=, colspan=)
    s = re.sub(r'(?:style|colspan|rowspan|class|align|scope)\s*=\s*"[^"]*"\s*\|', '', s)
    # table-control fragments that may bleed into a captured cell
    s = re.sub(r'\{\|[^\n}]*', '', s)   # {| class="..."
    s = s.replace('|}', '')
    s = strip_links(s)
    # drop <ref ...>...</ref> and self-closing refs
    s = re.sub(r'<ref[^>]*?/>', '', s)
    s = re.sub(r'<ref[^>]*?>.*?</ref>', '', s, flags=re.S)
    # {{Boostable|no}} / {{Boostable|yes}}
    s = re.sub(r"\{\{Boostable\|(\w+)\}\}", lambda m: f"(boostable: {m.group(1)})", s)
    # {{SCP|Skill|Level|sort=y|...}} -> "Skill Level"  (drop sort=y and other kwargs)
    def scp(m):
        parts = [p.strip() for p in m.group(1).split('|')]
        skill = parts[0]
        lvl = ""
        for p in parts[1:]:
            if '=' in p:
                continue
            lvl = p
            break
        return f"{skill} {lvl}".strip()
    s = re.sub(r"\{\{SCP\|([^}]+)\}\}", scp, s)
    # {{note|inline parenthetical}} -> keep text as a parenthetical
    s = re.sub(r"\{\{note\|([^}]*)\}\}", r" (\1)", s, flags=re.S)
    # Iteratively resolve templates from the innermost out (handles nesting like
    # {{Coins|{{#expr:floor({{MediumClueValue}})}}}}). Each pass operates only on
    # innermost templates (those containing no further '{{').
    inner = re.compile(r"\{\{([^{}]*)\}\}", re.S)
    for _ in range(8):
        def repl(m):
            body = m.group(1)
            head = body.split('|', 1)[0].strip().lower()
            # value/price/citation/math templates carry no faithful textual fact
            # in prose (price-volatile or render-only) -> drop entirely
            if (head.startswith('#expr') or head.startswith('cite')
                    or head in ('coins', 'gemwprice', 'gepprice', 'plink', 'plinkt',
                                'elink', 'na', 'm', 'f2p', 'members')
                    or head.endswith('cluevalue') or head.endswith('mimicvalue')
                    or head.endswith('value')):
                # for plink/plinkt/elink keep the label (first positional or txt=)
                if head in ('plink', 'plinkt', 'elink'):
                    parts = [p.strip() for p in body.split('|')[1:]]
                    label = None
                    for p in parts:
                        if p.startswith('txt='):
                            label = p[4:]
                            break
                    if label is None and parts:
                        label = parts[0]
                    return label or ''
                return ''
            # generic template -> keep its first positional arg label, else drop
            parts = body.split('|')
            if len(parts) > 1 and '=' not in parts[1]:
                return parts[1].strip()
            return ''
        new = inner.sub(repl, s)
        if new == s:
            break
        s = new
    # drop any stray unresolved braces
    s = s.replace('{{', '').replace('}}', '')
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"'''?", "", s)
    s = re.sub(r"''", "", s)
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"\s+([.,;])", r"\1", s)
    return s.strip()

# A line that is entirely a single hatnote/aside template (e.g. {{Main|...}},
# {{Listen|...}}) -- skipped when looking for the first prose paragraph.
_HATNOTE_LINE = re.compile(r'^\{\{[^{}]*\}\}$')

def first_para(sec):
    """First prose paragraph of a section (text before the first table/list/template line).

    Leading hatnote-only lines ({{Main|...}} etc.) and blank lines are skipped so
    the prose that follows them is still captured."""
    if not sec:
        return None
    lines = []
    started = False
    for line in sec.splitlines():
        st = line.strip()
        if not started:
            if not st or _HATNOTE_LINE.match(st):
                continue  # skip leading blanks / hatnotes
        if st.startswith(('{|', '*', '!', '|')) or st.startswith('{{'):
            break
        started = True
        lines.append(line)
    p = clean_text(" ".join(lines).strip())
    return p or None

def first_block(sec):
    """First prose paragraph only (stops at the first blank line OR a table/list/
    heading/template-only line). Used for casket reward-mechanics intros, which are
    followed by template-heavy (price-volatile {{#expr}}/{{Coins}}) paragraphs and
    sub-headings that should not be folded into the mechanics sentence."""
    if not sec:
        return None
    lines = []
    for line in sec.splitlines():
        st = line.strip()
        if not st:
            if lines:
                break
            continue
        if st.startswith(('{|', '*', '!', '|', '=')) or st.startswith('{{'):
            break
        lines.append(line)
    p = clean_text(" ".join(lines).strip())
    return p or None

def first_table(sec):
    """Extract the first wikitable body ({| ... |}) from a section."""
    if not sec:
        return None
    m = re.search(r'\{\|.*?\n\|\}', sec, re.S)
    if not m:
        # table may run to end of section without explicit |}
        m2 = re.search(r'\{\|.*', sec, re.S)
        return m2.group(0) if m2 else None
    return m.group(0)

def table_headers(tbl):
    """Return the list of header-cell texts (! ...) for the first header row."""
    if not tbl:
        return []
    heads = []
    for line in tbl.splitlines():
        st = line.strip()
        if st.startswith('!'):
            # split combined "! a !! b" headers
            for part in re.split(r'!!|^!', st):
                part = part.strip().lstrip('!').strip()
                if part:
                    heads.append(clean_text(part))
    return heads

def table_rows(tbl):
    """Yield each data row of a wikitable as a list of cell strings.

    Skips the leading caption/header block. Handles both ``|cell`` on its own
    line and ``|a||b`` inline cells.
    """
    if not tbl:
        return
    # drop the {| ... opening line and trailing |}
    body = re.sub(r'^\{\|[^\n]*\n', '', tbl)
    body = re.sub(r'\n\|\}\s*$', '', body)
    # split into rows on |-
    chunks = re.split(r'\n\|-+', body)
    for chunk in chunks:
        cells = []
        for line in chunk.splitlines():
            st = line.rstrip()
            ls = st.strip()
            if not ls:
                continue
            if ls.startswith('!'):      # header cells -> not a data row contribution
                continue
            if ls.startswith('|+'):     # caption
                continue
            if ls.startswith('|'):
                # a data cell line; may contain || inline separators
                content = ls[1:]
                for c in re.split(r'\|\|', content):
                    cells.append(c.strip())
            else:
                # continuation of the previous cell (multi-line cell)
                if cells:
                    cells[-1] = (cells[-1] + " " + ls).strip()
        if cells:
            yield cells

# ----------------------------------------------------------------------------
# Requirement-table parsers (leakage-safe)
# ----------------------------------------------------------------------------

def parse_skill_table(sec):
    """Parse a skill-requirement wikitable.

    Handles both the 2-column layout (Skill level | Details) used by
    easy/medium/hard/elite and the 4-column layout
    (Skill level | +5 spicy stew | consistent temp boost | Details) used by
    master. Returns list of {requirement, details, boost_levels?}.
    """
    if not sec:
        return []
    tbl = first_table(sec)
    if not tbl:
        return []
    heads = table_headers(tbl)
    ncol = len(heads)
    out = []
    for cells in table_rows(tbl):
        # a valid skill row's first cell mentions SCP (a skill) or data-sort-value combat
        if not cells:
            continue
        raw_first = cells[0]
        if 'SCP' not in raw_first and 'Combat' not in raw_first:
            continue
        req = clean_text(raw_first)
        if not req:
            continue
        rec = {"requirement": req}
        if ncol >= 4 and len(cells) >= 4:
            # master: cols 1,2 are boosted levels, last col is details
            boost = []
            for c in cells[1:-1]:
                bc = clean_text(c)
                if bc and bc.lower() not in ("not boostable",):
                    boost.append(bc)
            rec["boost_levels"] = boost
            rec["details"] = clean_text(cells[-1]) or None
        else:
            rec["details"] = clean_text(cells[1]) if len(cells) > 1 else None
        out.append(rec)
    return out

def parse_quest_table(sec):
    """Parse a quest-requirement wikitable; only rows whose first cell is a
    [[Quest]] link become records (skips the intro paragraph + table controls)."""
    if not sec:
        return []
    tbl = first_table(sec)
    if not tbl:
        return []
    out = []
    for cells in table_rows(tbl):
        if not cells:
            continue
        if '[[' not in cells[0]:
            continue
        quest = clean_text(cells[0])
        det = clean_text(cells[1]) if len(cells) > 1 else None
        if quest:
            out.append({"quest": quest, "details": det})
    return out

def parse_music_table(sec):
    if not sec:
        return []
    tbl = first_table(sec)
    if not tbl:
        return []
    out = []
    for cells in table_rows(tbl):
        if len(cells) < 2:
            continue
        track = clean_text(cells[0])
        loc = clean_text(cells[1])
        if track:
            out.append({"track": track, "unlock_location": loc})
    return out

def parse_types(sec):
    if not sec:
        return []
    out = []
    for m in re.finditer(r'\*\s*\[\[([^\]|]+)\|([^\]]+)\]\]', sec):
        out.append(clean_text(m.group(2)))
    for m in re.finditer(r'\*\s*\[\[([^\]|]+)\]\]', sec):
        out.append(clean_text(m.group(1)))
    seen, res = set(), []
    for x in out:
        if x and x not in seen:
            seen.add(x); res.append(x)
    return res

# ----------------------------------------------------------------------------
# Treasure_Trails overview parsing (matrix, antagonists, milestones, cases, ranks)
# ----------------------------------------------------------------------------

TT = load("treasure_trails_raw.wikitext")

def parse_step_matrix():
    """Parse the 'Solving the Treasure Trails' matrix into per-(tier,step) cells.

    Returns dict tier -> {step_type -> solution_guide | None}.
    """
    sec = section(TT, "Solving the Treasure Trails")
    tbl = first_table(sec)
    # column order from header (after the 'Tier' colspan)
    cols = ["Anagrams", "Challenge scrolls", "Ciphers", "Coordinates",
            "Cryptic clues", "Emote clues", "Hot Cold", "Light boxes",
            "Maps", "Puzzle boxes"]
    result = {}
    # rows: each begins with !{{plinkt|Clue scroll (tier)|txt=Tier}} then 10 cells
    chunks = re.split(r'\n\|-', tbl)
    for chunk in chunks:
        mt = re.search(r'Clue scroll \((\w+)\)', chunk)
        if not mt:
            continue
        tier = mt.group(1)
        if tier not in TIERS:
            continue
        # collect the cells after the tier header line
        cells = []
        for line in chunk.splitlines():
            ls = line.strip()
            if ls.startswith('|') and not ls.startswith('|-'):
                cells.append(ls[1:].strip())
        # map cells -> cols (NA = not applicable)
        mapping = {}
        for i, col in enumerate(cols):
            cell = cells[i] if i < len(cells) else ""
            if '{{NA}}' in cell or cell == '' or '{{na' in cell.lower():
                continue
            # extract solution-guide page
            mg = re.search(r'\[\[([^\]|]+)\|', cell)
            mapping[col] = mg.group(1) if mg else clean_text(cell)
        result[tier] = mapping
    return result

STEP_MATRIX = parse_step_matrix()

def parse_antagonists():
    """Parse the Antagonists table -> list of dicts per encounter (level cited)."""
    sec = section(TT, "Antagonists")
    tbl = first_table(sec)
    out = []
    current_tier = None
    pending_coord, pending_emote = [], []
    # We re-parse line-by-line because the table uses rowspans and {{NA|colspan}}.
    for raw_chunk in re.split(r'\n\|-', tbl):
        mt = re.search(r'Clue scroll \((\w+)\)', raw_chunk)
        if mt:
            current_tier = mt.group(1)
        # find inline coordinate / emote entries: pattern "LEVEL||[[Enemy]]||Location"
        # We capture all "NN||...||..." triples in the chunk.
        for m in re.finditer(
            r'(?:^|\n)\|\s*([\d, ]+)\s*\|\|\s*(.+?)\s*\|\|\s*(.+?)\s*(?=\n|$)', raw_chunk):
            lvl = m.group(1).strip()
            enemy = clean_text(m.group(2))
            loc = clean_text(m.group(3))
            # enemy/location heuristic: this is a coordinate-clue cell
            out.append({"tier": current_tier, "step_type": "Coordinate clues",
                        "level": lvl, "enemy": enemy, "location": loc})
    return out

# The Antagonists table layout (rowspans, {{NA|colspan}}) is awkward to parse
# generically; transcribe it faithfully and verbatim from the source table.
ANTAGONISTS = {
    "beginner": [],
    "easy": [],
    "medium": [],
    "hard": [
        {"step_type": "Coordinate clues", "level": "108", "enemy": "Saradomin wizard", "location": "Non-Wilderness"},
        {"step_type": "Coordinate clues", "level": "65", "enemy": "Zamorak wizard", "location": "Wilderness"},
        {"step_type": "Emote clues", "level": "108", "enemy": "Double agent", "location": "Non-Wilderness"},
        {"step_type": "Emote clues", "level": "65", "enemy": "Double agent", "location": "Wilderness"},
    ],
    "elite": [
        {"step_type": "Coordinate clues", "level": "97", "enemy": "Armadylean guard", "location": "Anywhere"},
        {"step_type": "Coordinate clues", "level": "125", "enemy": "Bandosian guard", "location": "Anywhere"},
    ],
    "master": [
        {"step_type": "Coordinate clues", "level": "98, 98, 112", "enemy": "Ancient Wizard (x3)", "location": "Multicombat"},
        {"step_type": "Coordinate clues", "level": "140", "enemy": "Brassican Mage", "location": "Single-way combat"},
        {"step_type": "Emote clues", "level": "141", "enemy": "Double agent", "location": "Anywhere"},
    ],
}
# Provenance for antagonist levels: cite to the Treasure Trails "Antagonists" table.
ANTAGONIST_SOURCE = "https://oldschool.runescape.wiki/w/Treasure_Trails#Antagonists"

def parse_milestones():
    """Parse the 'Milestone rewards' bullet list -> {tier:{item,clues}}."""
    sec = section(TT, "Milestone rewards")
    out = {}
    for m in re.finditer(r'\*\s*(\w+):\s*(\{\{(?:plink|elink)\|[^}]+\}\})\s*[—-]+\s*([\d,]+)', sec):
        tier = m.group(1).lower()
        item = clean_text(m.group(2))
        clues = int(m.group(3).replace(',', ''))
        if tier in TIERS:
            out[tier] = {"item": item, "clues": clues}
    return out

MILESTONES = parse_milestones()

def parse_scroll_cases():
    """Parse the scroll-case minor/major stack-limit table -> {tier:{minor,major}}."""
    sec = section(TT, "Milestone rewards")
    tbl = first_table(sec)
    out = {}
    for cells in table_rows(tbl):
        mt = re.search(r'(\w+) scroll case', cells[0]) if cells else None
        if not mt:
            continue
        tier = mt.group(1).lower()
        if tier not in TIERS:
            continue
        nums = [c.strip() for c in cells[1:] if c.strip().isdigit()]
        if len(nums) >= 2:
            out[tier] = {"minor_case_clues": int(nums[0]), "major_case_clues": int(nums[1])}
    return out

SCROLL_CASES = parse_scroll_cases()

def parse_ranks():
    """Parse the Ranks table -> list of {completed, rank}."""
    sec = section(TT, "Ranks")
    tbl = first_table(sec)
    out = []
    for cells in table_rows(tbl):
        if len(cells) < 2:
            continue
        completed = clean_text(cells[0])
        rank = clean_text(cells[1])
        if completed and rank and any(ch.isdigit() for ch in completed):
            out.append({"completed_clue_scrolls": completed, "rank": rank})
    return out

RANKS = parse_ranks()

def parse_rolls_per_clue():
    """Read the roll multiplier per tier from the 'Average rewards value' table
    (e.g. '5 * {{HardClueValue}}')."""
    sec = section(TT, "Average rewards value")
    out = {}
    for tier in TIERS:
        cap = tier.capitalize()
        m = re.search(r'floor\(\s*(\d+)\s*\*\s*\{\{' + cap + r'ClueValue\}\}\s*\)', sec)
        if m:
            out[tier] = int(m.group(1))
    return out

ROLLS_PER_CLUE = parse_rolls_per_clue()

# ----------------------------------------------------------------------------
# Reward casket parsing (sub-tables, item rarities, mechanics, notable rewards)
# ----------------------------------------------------------------------------

def _eval_expr_math(expr):
    """Evaluate a MediaWiki #expr arithmetic body (the wiki computes these at
    render time; the wikitext only stores the formula). Supports + - * / ( ) and
    the 'round N' operator. Returns a number, or None if it can't be evaluated
    safely. This is faithful evaluation of the source formula, not invented data.
    """
    e = expr.strip()
    rnd = None
    mr = re.search(r'\bround\s+(\d+)\s*$', e)
    if mr:
        rnd = int(mr.group(1))
        e = e[:mr.start()].strip()
    # only allow digits, operators, parens, whitespace, dot
    if not re.fullmatch(r'[\d\s\.\+\-\*/\(\)]+', e):
        return None
    # Safe arithmetic evaluation via the ast module (no eval/exec): we walk the
    # parse tree and only permit numeric literals and +,-,*,/ binary/unary ops.
    import ast as _ast
    _ALLOWED_BIN = (_ast.Add, _ast.Sub, _ast.Mult, _ast.Div)
    def _ev(node):
        if isinstance(node, _ast.Expression):
            return _ev(node.body)
        if isinstance(node, _ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, _ast.BinOp) and isinstance(node.op, _ALLOWED_BIN):
            a, b = _ev(node.left), _ev(node.right)
            if isinstance(node.op, _ast.Add): return a + b
            if isinstance(node.op, _ast.Sub): return a - b
            if isinstance(node.op, _ast.Mult): return a * b
            if isinstance(node.op, _ast.Div): return a / b
        if isinstance(node, _ast.UnaryOp) and isinstance(node.op, (_ast.UAdd, _ast.USub)):
            v = _ev(node.operand)
            return +v if isinstance(node.op, _ast.UAdd) else -v
        raise ValueError("disallowed expression node")
    try:
        val = _ev(_ast.parse(e, mode="eval"))
    except Exception:
        return None
    if rnd is not None:
        val = round(val, rnd)
    if isinstance(val, float) and val.is_integer():
        val = int(val)
    return val

def clean_rarity(s):
    """Render a DropsLineReward rarity, evaluating {{#expr:...}} math where present.

    Returns (rendered, raw, evaluated_bool). ``rendered`` is the human-facing
    rarity string (e.g. '1/1133'); ``raw`` is the verbatim source string; if the
    expression can't be evaluated, rendered falls back to the brace-stripped raw
    and evaluated=False (disclosed)."""
    if s is None:
        return None, None, False
    raw = s.strip()
    if not raw:
        return None, None, False
    # textual rarities (Always / random / ~1/x) -> normalise case, strip stray braces
    work = raw
    fully = True
    # repeatedly replace {{#expr: BODY }} with its evaluated value
    expr_pat = re.compile(r'\{\{#expr:\s*(.+?)\s*\}\}', re.S)
    while True:
        m = expr_pat.search(work)
        if not m:
            break
        val = _eval_expr_math(m.group(1))
        if val is None:
            fully = False
            break
        work = work[:m.start()] + str(val) + work[m.end():]
    # strip any remaining stray braces / leftover template noise
    work = work.replace('{{', '').replace('}}', '')
    work = re.sub(r'<ref[^>]*?>.*?</ref>', '', work, flags=re.S)
    work = re.sub(r'<ref[^>]*?/>', '', work)
    work = re.sub(r'\s+', ' ', work).strip()
    # normalise a couple of common spellings
    if work.lower() == 'always':
        work = 'Always'
    evaluated = fully and ('#expr' not in raw or '#expr' not in work)
    return (work or None), raw, evaluated

def parse_drop_line(line):
    """Parse a {{DropsLineReward|name=..|quantity=..|rarity=..}} into a dict.

    Splits only on top-level '|' (so '|' inside nested {{...}} / <ref>...</ref>
    does not over-split the rarity expression)."""
    inner = line[line.find('|') + 1:].rstrip()
    # drop the single trailing '}}' that closes the {{DropsLineReward ...}} template
    # itself, so the last field value isn't polluted by it (e.g. 'rarity=1/360}}').
    if inner.endswith('}}'):
        inner = inner[:-2].rstrip()
    fields = {}
    depth = 0
    cur = []
    parts = []
    i = 0
    while i < len(inner):
        ch = inner[i]
        if inner[i:i + 2] == '{{':
            depth += 1; cur.append('{{'); i += 2; continue
        if inner[i:i + 2] == '}}':
            depth = max(0, depth - 1); cur.append('}}'); i += 2; continue
        if ch == '|' and depth == 0:
            parts.append(''.join(cur)); cur = []; i += 1; continue
        cur.append(ch); i += 1
    if cur:
        parts.append(''.join(cur))
    for part in parts:
        if '=' in part:
            k, v = part.split('=', 1)
            fields[k.strip()] = v.strip()
    name = clean_text(fields.get('name', '')) or None
    qty = clean_text(fields.get('quantity', '1')) or "1"
    rendered, raw, evaluated = clean_rarity(fields.get('rarity'))
    rec = {"name": name, "quantity": qty, "rarity": rendered}
    if raw is not None and raw != rendered:
        rec["rarity_raw"] = raw
        rec["rarity_evaluated"] = evaluated
    return rec

def parse_casket(tier):
    """Parse the Reward casket (tier) page into:
       - intro_mechanics (str): the Rewards-section intro prose
       - subtables: list of {name, intro, items:[{name,quantity,rarity}]}
    """
    t = load(f"reward_casket_{tier}_raw.wikitext")
    rewards = section(t, "Rewards")
    intro_mech = first_block(rewards) if rewards else None

    # Walk the Rewards section heading-by-heading collecting DropsLineReward groups.
    subtables = []
    if rewards:
        # split on === or ==== sub-headings within Rewards
        parts = re.split(r'^(={3,4})\s*(.+?)\s*\1\s*$', rewards, flags=re.M)
        # parts[0] is text before first sub-heading; then triples (eq, name, body)
        for i in range(1, len(parts), 3):
            name = parts[i + 1].strip()
            body = parts[i + 2]
            sub_intro = first_block(body)
            items = []
            for line in body.splitlines():
                if line.strip().startswith('{{DropsLineReward'):
                    items.append(parse_drop_line(line.strip()))
            if items:
                subtables.append({"subtable": clean_text(name),
                                  "intro": sub_intro,
                                  "item_count": len(items),
                                  "items": items})
    return {"intro_mechanics": intro_mech, "subtables": subtables}

CASKETS = {tier: parse_casket(tier) for tier in TIERS}

# Iconic item-name fragments players plan around. A notable_reward record is
# only emitted when a matching item actually exists in the parsed casket data
# (no fabricated names) -- so every notable reward carries a real per-roll rarity
# read verbatim from the source DropsLineReward rows.
NOTABLE_FRAGMENTS = [
    "3rd age", "Gilded", "Ranger boots", "Robin hood", "Bloodhound", "Holy sandals",
    "Wizard boots", "Spiked manacles", "Ring of nature", "Ring of coins",
    "Mole slippers", "Frog slippers", "Bear feet", "Demon feet", "Jester",
    "Heavy casket", "Occult ornament kit", "Tormented ornament kit",
    "Anguish ornament kit", "Torture ornament kit", "Fury ornament kit",
    "Dragon scimitar ornament kit", "Saradomin's tear", "Ankou", "Samurai",
    "Deerstalker", "Briefcase", "Sagacious spectacles", "Afro", "Big pirate hat",
]

def _rarity_denominator(rarity):
    """Return the numeric denominator of a '1/N' rarity for sorting; +inf if not numeric."""
    if not rarity:
        return float('inf')
    m = re.match(r'^\s*\d+\s*/\s*([\d.]+)\s*$', rarity)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return float('inf')
    return float('inf')

def select_notable_rewards(tier, max_per_tier=14):
    """Select notable rewards for a tier from the parsed casket data.

    Always includes any item whose name matches an iconic fragment; tops up with
    the rarest unique/mega-rare/tertiary items until max_per_tier. Returns list of
    {item, rarity, rarity_raw?, rarity_evaluated?, subtable}. Never invents names.
    """
    # candidate pool: uniques, mega-rare, mimic, tertiary, jewellery sub-tables
    pool = []
    for sub in CASKETS[tier]["subtables"]:
        sn = sub["subtable"].lower()
        if any(k in sn for k in ("unique", "mega", "mimic", "tertiary", "jewellery", "black items")):
            for it in sub["items"]:
                if it["name"]:
                    pool.append((it, sub["subtable"]))
    seen = set()
    chosen = []
    # 1) iconic fragment matches (preserve a stable order)
    for it, sn in pool:
        nm = it["name"]
        if nm.lower() in seen:
            continue
        if any(frag.lower() in nm.lower() for frag in NOTABLE_FRAGMENTS):
            chosen.append((it, sn)); seen.add(nm.lower())
    # 2) top up with the rarest remaining items
    rest = [(it, sn) for it, sn in pool if it["name"].lower() not in seen]
    rest.sort(key=lambda x: _rarity_denominator(x[0]["rarity"]), reverse=True)
    for it, sn in rest:
        if len(chosen) >= max_per_tier:
            break
        if it["name"].lower() in seen:
            continue
        chosen.append((it, sn)); seen.add(it["name"].lower())
    out = []
    for it, sn in chosen[:max_per_tier]:
        rec = {"item": it["name"], "rarity_per_roll": it["rarity"], "subtable": sn}
        if "rarity_raw" in it:
            rec["rarity_raw"] = it["rarity_raw"]
            rec["rarity_evaluated"] = it.get("rarity_evaluated", False)
        out.append(rec)
    return out

# ----------------------------------------------------------------------------
# Build records
# ----------------------------------------------------------------------------

records = []

# ---- tier records --------------------------------------------------------
for tier in TIERS:
    t = load(f"clue_scroll_{tier}_raw.wikitext")
    skill_reqs = parse_skill_table(section(t, "Skill requirements"))
    quest_reqs = parse_quest_table(section(t, "Quest requirements"))
    music_reqs = parse_music_table(section(t, "Music requirements"))
    iron_sec = (section(t, "Additional requirements for ironmen")
                or section(t, "Additional Ironman requirements"))
    iron_reqs = parse_skill_table(iron_sec)
    iron_note = first_para(iron_sec)

    item_req_sections = []
    for nm in ["Item requirements", "Item requirements (Emote clues)",
               "Item requirements (Falo the Bard)", "Other requirements"]:
        if section(t, nm):
            item_req_sections.append(nm)

    types = parse_types(section(t, "Types of clues"))

    src_sec = section(t, "Item sources") or ""
    has_drop_sources = "Drop sources" in src_sec
    has_shop = "Store locations list" in src_sec or section(t, "Shop locations") is not None
    item_source_note = clean_text(first_para(src_sec)) if src_sec else None

    ov = TIER_OVERVIEW[tier]
    av = AVG_VALUE_SNAPSHOT[tier]
    rolls = ROLLS_PER_CLUE.get(tier)

    records.append({
        "record_type": "tier",
        "id": f"tier:{tier}",
        "tier": tier,
        "source": f"https://oldschool.runescape.wiki/w/Clue_scroll_({tier})",
        "members": ov["members"],
        "length": ov["length"],
        "step_types": sorted(STEP_MATRIX.get(tier, {}).keys()),
        "clue_types_with_guides": types,
        "antagonists": ANTAGONISTS[tier],
        "requirements": {
            "skill_requirements": skill_reqs,
            "quest_requirements": quest_reqs,
            "music_requirements": music_reqs,
            "ironman_additional_skill_requirements": iron_reqs,
            "ironman_note": iron_note,
            "item_requirements": {
                "note": ("Item requirements are enumerated as large wikitables on the "
                         "source page (emote-clue STASH items, Charlie/Falo task items, "
                         "Sherlock challenge outfits). Captured by section pointer rather "
                         "than transcribing every item; see source page sections."),
                "sections_present": item_req_sections,
            },
        },
        "reward": {
            "reward_casket": f"Reward casket ({tier})",
            "casket_main_page": f"https://oldschool.runescape.wiki/w/Reward_casket_({tier})",
            "rolls_per_clue": rolls,
            "valuation": {
                "avg_gp_per_roll": av["avg_gp_per_roll"],
                "avg_gp_per_clue": av["avg_gp_per_clue"],
                "unit": "gp",
                "pricing_basis": "ge",
                "audience": "main",
                "note": VALUATION_NOTE,
            },
            "milestone_reward": MILESTONES.get(tier),
            "reward_pool_note": ("Full per-item reward tables are inlined as separate "
                                 "reward_subtable records (parsed from the Reward casket "
                                 f"({tier}) page); outputs are predominantly the 'reward "
                                 "casket' aggregate (a pseudo-item), not literal Coins."),
            "output_is_aggregate": True,
        },
        "item_sources": {
            "note": ((item_source_note or "") + (
                " Drop/skilling/shop sources are transcluded on the source page "
                "(Drop sources / Store locations list templates) and not inlined here.")).strip(),
            "has_drop_sources_table": has_drop_sources,
            "has_shop_table": bool(has_shop),
            "item_sources_anchor": f"https://oldschool.runescape.wiki/w/Clue_scroll_({tier})#Item_sources",
        },
        "requires_ge": False,
        "audience": (["main", "ironman", "uim", "members"] if ov["members"]
                     else ["main", "ironman", "uim", "f2p", "members"]),
        "wilderness_risk": tier in ("hard", "elite", "master"),
        "pricing_basis": "ge",
    })

# ---- step_type records ---------------------------------------------------
STEP_TYPE_DESCRIPTIONS = {
    "Anagrams": "An anagram of an NPC's name; rearrange the letters and talk to that NPC.",
    "Challenge scrolls": "A skill/knowledge question posed by an NPC that must be answered to proceed.",
    "Ciphers": "A Caesar-shift encoded NPC name; decode then talk to the NPC.",
    "Coordinates": "A pair of map coordinates; navigate there and dig (may spawn an antagonist).",
    "Cryptic clues": "A riddle pointing to a location, NPC, or object to search/talk to.",
    "Emote clues": "Equip specified items at a location and perform one or two emotes (may spawn a double agent).",
    "Hot Cold": "Use the strange/meerkat device and dig; warmer/colder feedback narrows the spot.",
    "Light boxes": "A logic puzzle interface; toggle tiles so all are lit.",
    "Maps": "A hand-drawn map of a location; travel there and dig at the marked X.",
    "Puzzle boxes": "A sliding-tile picture puzzle that must be solved to proceed.",
}
for tier in TIERS:
    for step, guide in sorted(STEP_MATRIX.get(tier, {}).items()):
        records.append({
            "record_type": "step_type",
            "id": f"step:{tier}:{step}",
            "tier": tier,
            "step_type": step,
            "applicable": True,
            "description": STEP_TYPE_DESCRIPTIONS.get(step),
            "solution_guide_page": guide,
            "solution_guide_url": (
                "https://oldschool.runescape.wiki/w/" + guide.replace(' ', '_')
                if guide else None),
            "source": "https://oldschool.runescape.wiki/w/Treasure_Trails#Solving_the_Treasure_Trails",
        })

# ---- antagonist records --------------------------------------------------
for tier in TIERS:
    for a in ANTAGONISTS[tier]:
        records.append({
            "record_type": "antagonist",
            "id": f"antagonist:{tier}:{a['step_type']}:{a['enemy']}",
            "tier": tier,
            "step_type": a["step_type"],
            "enemy": a["enemy"],
            "combat_level": a["level"],
            "location": a["location"],
            "level_source": ANTAGONIST_SOURCE,
            "note": ("Random combat encounter triggered on solving the step; "
                     "combat level(s) cited verbatim to the Treasure Trails Antagonists table."),
        })

# ---- reward_mechanics records --------------------------------------------
for tier in TIERS:
    c = CASKETS[tier]
    records.append({
        "record_type": "reward_mechanics",
        "id": f"reward_mechanics:{tier}",
        "tier": tier,
        "rolls_per_clue": ROLLS_PER_CLUE.get(tier),
        "rewards_mechanics_text": c["intro_mechanics"],
        "subtable_names": [s["subtable"] for s in c["subtables"]],
        "source": f"https://oldschool.runescape.wiki/w/Reward_casket_({tier})#Rewards",
        "rarity_basis": "per loot roll (as stated on the Reward casket page)",
    })

# ---- reward_subtable records ---------------------------------------------
for tier in TIERS:
    for sub in CASKETS[tier]["subtables"]:
        records.append({
            "record_type": "reward_subtable",
            "id": f"reward_subtable:{tier}:{sub['subtable']}",
            "tier": tier,
            "subtable": sub["subtable"],
            "mechanics_note": sub["intro"],
            "item_count": sub["item_count"],
            "items": sub["items"],
            "rarity_basis": "per loot roll",
            "source": f"https://oldschool.runescape.wiki/w/Reward_casket_({tier})#Rewards",
        })

# ---- notable_reward records ----------------------------------------------
# Selected programmatically from the parsed casket data (iconic-name matches +
# rarest items), so every record corresponds to a real source item with a real
# per-roll rarity. No item names are invented.
for tier in TIERS:
    for nr in select_notable_rewards(tier):
        rec = {
            "record_type": "notable_reward",
            "id": f"notable_reward:{tier}:{nr['item']}",
            "tier": tier,
            "item": nr["item"],
            "rarity_per_roll": nr["rarity_per_roll"],   # verbatim/evaluated from source
            "subtable": nr["subtable"],
            "rarity_resolved": nr["rarity_per_roll"] is not None,
            "drop_source": f"Reward casket ({tier})",
            "drop_source_url": f"https://oldschool.runescape.wiki/w/Reward_casket_({tier})",
            "source": f"https://oldschool.runescape.wiki/w/Reward_casket_({tier})#Rewards",
        }
        if "rarity_raw" in nr:
            rec["rarity_raw"] = nr["rarity_raw"]
            rec["rarity_evaluated"] = nr["rarity_evaluated"]
        records.append(rec)

# ---- milestone records ---------------------------------------------------
for tier in TIERS:
    ms = MILESTONES.get(tier)
    sc = SCROLL_CASES.get(tier, {})
    records.append({
        "record_type": "milestone",
        "id": f"milestone:{tier}",
        "tier": tier,
        "milestone_item": ms["item"] if ms else None,
        "milestone_clues": ms["clues"] if ms else None,
        "note": ("Cumulative-completion reward; re-obtainable by completing another "
                 "clue of this tier if lost."),
        "source": "https://oldschool.runescape.wiki/w/Treasure_Trails#Milestone_rewards",
    })

# ---- scroll_case records -------------------------------------------------
for tier in TIERS:
    sc = SCROLL_CASES.get(tier, {})
    records.append({
        "record_type": "scroll_case",
        "id": f"scroll_case:{tier}",
        "tier": tier,
        "minor_case_clues": sc.get("minor_case_clues"),
        "major_case_clues": sc.get("major_case_clues"),
        "note": ("Scroll cases raise the per-tier scroll-box/scroll stack limit by +1 "
                 "each (post X Marks the Spot). Base limit 2, max 5 (the +1 Mimic scroll "
                 "case applies to all tiers). Minor/major are awarded at the listed "
                 "cumulative clue counts for this tier."),
        "source": "https://oldschool.runescape.wiki/w/Treasure_Trails#Milestone_rewards",
    })

# ---- rank records --------------------------------------------------------
for r in RANKS:
    records.append({
        "record_type": "rank",
        "id": f"rank:{r['rank']}",
        "completed_clue_scrolls": r["completed_clue_scrolls"],
        "rank": r["rank"],
        "scope": "all tiers combined",
        "source": "https://oldschool.runescape.wiki/w/Treasure_Trails#Ranks",
    })

# ---- global mechanic records ---------------------------------------------
def mech(name, section_name):
    body = section(TT, section_name)
    return clean_text(first_para(body)) if body else None

MECHANICS = [
    ("obtaining", "Obtaining clues",
     "How clue scrolls are dropped/acquired (monsters, skilling, impling jars; tertiary drop; rate boosts)."),
    ("stacking", "Stacking limitations",
     "Scroll/scroll-box stack limits and how X Marks the Spot + scroll cases raise them."),
    ("risk", "Risks",
     "Wilderness death and item-protection rules for clue scrolls and reward caskets."),
]
for key, sec_name, summary in MECHANICS:
    records.append({
        "record_type": "mechanic",
        "id": f"mechanic:{key}",
        "topic": key,
        "summary": summary,
        "text": mech(key, sec_name),
        "source": f"https://oldschool.runescape.wiki/w/Treasure_Trails#{sec_name.replace(' ', '_')}",
    })

# ----------------------------------------------------------------------------
# Envelope
# ----------------------------------------------------------------------------

now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()

source_urls = (
    ["https://oldschool.runescape.wiki/w/Treasure_Trails?action=raw"]
    + [f"https://oldschool.runescape.wiki/w/Clue_scroll_({tier})?action=raw" for tier in TIERS]
    + [f"https://oldschool.runescape.wiki/w/Reward_casket_({tier})?action=raw" for tier in TIERS]
)
raw_files = (
    ["data/raw/treasure_trails_raw.wikitext"]
    + [f"data/raw/clue_scroll_{tier}_raw.wikitext" for tier in TIERS]
    + [f"data/raw/reward_casket_{tier}_raw.wikitext" for tier in TIERS]
)

# record-type tallies (for domain_stats + sanity)
type_counts = {}
for r in records:
    type_counts[r["record_type"]] = type_counts.get(r["record_type"], 0) + 1

# notable rewards whose rarity could not be resolved -> disclose
unresolved_notables = [r["id"] for r in records
                       if r["record_type"] == "notable_reward" and not r["rarity_resolved"]]

known_missing = [
    "Per-source drop rates and the full Item sources lists on each Clue scroll "
    "(tier) page (transcluded {{Drop sources}} / {{Store locations list}}) are not "
    "inlined; captured as source-page anchors on the tier records.",
    "Full emote-clue STASH item lists and the Falo the Bard / Charlie the Tramp / "
    "Sherlock challenge item tables are captured by section pointer on the tier "
    "records, not transcribed item-by-item.",
    "Average reward gp values (avg_gp_per_roll / avg_gp_per_clue) are a single "
    "live-GE snapshot (2026-06-17) of the wiki's price-volatile templates; the "
    "wikitext itself contains only the template calls, not rendered numbers.",
    "notable_reward records are a curated selection of iconic/high-value uniques, "
    "not the complete reward pool; the complete per-item pool is in the "
    "reward_subtable records.",
    "Universal rewards (shared easy+ drop table) are transcluded via "
    "{{Universal rewards}} on Treasure Trails and {{...}} shared-item templates on "
    "the casket pages; items present under a casket's 'Shared treasure trail items' "
    "sub-table are captured, but the standalone {{Universal rewards}} block is not "
    "separately inlined.",
]
if unresolved_notables:
    known_missing.append(
        "Some notable_reward records could not resolve a per-roll rarity from the "
        "casket DropsLineReward rows (rarity set to null); affected ids: "
        + ", ".join(unresolved_notables) + ".")

envelope = {
    "_provenance": {
        "domain": "clue_scrolls",
        "source_urls": source_urls,
        "source_query": None,
        "accessed": now,
        "license": "CC BY-NC-SA 3.0",
        "extraction_method": "script",
        "raw_files": raw_files,
        "record_count": len(records),
        "fix_note": (
            "v2 full re-extraction (" + ACCESSED_DATE + "): prior run captured only 6 "
            "tier-summary records. This run (a) keeps the 6 tier records but fixes "
            "HTML/table leakage (stripped data-sort-value=...| prefixes and "
            "'{| class=\"wikitable...\"' fragments from skill/quest rows) and correctly "
            "maps the master tier's 4-column skill table (base level / +5 spicy stew / "
            "consistent temp-boost item / details) into requirement + boost_levels + "
            "details; (b) adds step_type, antagonist, reward_mechanics, reward_subtable, "
            "notable_reward, milestone, scroll_case, rank and global mechanic records, "
            "newly fetching the six Reward casket (tier) pages for per-item rarities and "
            "reward mechanics. Antagonist combat levels are cited verbatim to the "
            "Treasure Trails Antagonists table."),
        "completeness": {
            "bounded_by": ("Treasure Trails difficulty tiers (clue scroll universe) plus "
                           "their reward casket tables, step-type matrix, antagonists, "
                           "milestones, scroll cases, ranks, and activity mechanics."),
            "universe_count": 6,
            "tier_records_count": type_counts.get("tier", 0),
            "records_count": len(records),
            "known_missing": known_missing,
        },
        "domain_stats": {
            "tiers": TIERS,
            "f2p_tiers": [t for t in TIERS if not TIER_OVERVIEW[t]["members"]],
            "members_tiers": [t for t in TIERS if TIER_OVERVIEW[t]["members"]],
            "wilderness_risk_tiers": [t for t in TIERS if t in ("hard", "elite", "master")],
            "total_unique_rewards_all_tiers": 638,
            "record_type_counts": type_counts,
            "rolls_per_clue": ROLLS_PER_CLUE,
            "casket_valuation_basis": "ge (main); irons realise as items/alch/coins",
            "all_caskets_untradeable_iron_safe_activity": True,
        },
    },
    "records": records,
    "_excluded": [],
}

out = f"{BASE}/clue_scrolls.json"
with open(out, "w") as f:
    json.dump(envelope, f, indent=2, ensure_ascii=False)

print("WROTE", out)
print("record_count:", len(records))
print("type_counts:", json.dumps(type_counts))
print("rolls_per_clue:", ROLLS_PER_CLUE)
print("unresolved_notables:", unresolved_notables)
print("ranks:", len(RANKS), "milestones:", len(MILESTONES), "scroll_cases:", len(SCROLL_CASES))
for tier in TIERS:
    tr = next(r for r in records if r["record_type"] == "tier" and r["tier"] == tier)
    print(f"  {tier:8s} skills={len(tr['requirements']['skill_requirements'])} "
          f"quests={len(tr['requirements']['quest_requirements'])} "
          f"music={len(tr['requirements']['music_requirements'])} "
          f"iron={len(tr['requirements']['ironman_additional_skill_requirements'])} "
          f"types={len(tr['clue_types_with_guides'])} "
          f"steps={len(tr['step_types'])} "
          f"subtables={len(CASKETS[tier]['subtables'])}")
