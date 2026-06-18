#!/usr/bin/env python3
"""Authoritative parser: build achievement_diaries.json records from the 12
individual OSRS Wiki diary pages (oldschool.runescape.wiki/w/<Region>_Diary).

Why individual pages and not only All_achievements:
  Achievement_Diary/All_achievements groups tasks by requirement type and
  contains cross-section phrasing drift (the same task worded two ways) plus
  "Multiple/Various" placeholder rows -> a text-keyed dedup both double-counts
  and misses tasks. The individual diary pages number every task per tier
  (1., 2., ...), giving the exact universe and clean per-tier requirements.
  All_achievements is retained as a raw cross-check artifact only.

Record schema (domain spec):
  { diary_region, tier, task_number, task,
    requirements: { skills:[{skill,level}], quests:[...], items:[...] },
    boostable, reward (per-tier reward text), source_url }
"""
import re, json
from collections import OrderedDict, Counter

DIARIES = [
    ("Ardougne", "Ardougne"), ("Desert", "Desert"), ("Falador", "Falador"),
    ("Fremennik", "Fremennik"), ("Kandarin", "Kandarin"), ("Karamja", "Karamja"),
    ("Kourend_&_Kebos", "Kourend & Kebos"),
    ("Lumbridge_&_Draynor", "Lumbridge & Draynor"), ("Morytania", "Morytania"),
    ("Varrock", "Varrock"), ("Western_Provinces", "Western Provinces"),
    ("Wilderness", "Wilderness"),
]
TIERS = ["Easy", "Medium", "Hard", "Elite"]
WIKI = "https://oldschool.runescape.wiki/w/"

SCP_RE = re.compile(r"\{\{SCP\|([A-Za-z ]+)\|([0-9]+)(?:-[0-9]+)?[^}]*\}\}")

# A primary multi-skill bullet ("Agility 36, Strength 22, and Ranged 39"), once
# its {{SCP|...}} templates are stripped, leaves only connectives (", , and").
# Such remainders carry no information and must not be emitted as item reqs.
_CONNECTIVE_ONLY_RE = re.compile(r"^[\s,.&]*(?:and[\s,.&]*)*$", re.I)

def expand_templates(s):
    """Replace known templates with readable text before stripping links."""
    s = re.sub(r"\{\{#[a-z]+:[^{}]*\}\}", "", s)  # parser functions {{#vardefine:..}}
    s = re.sub(r"\{\{RuneReq\|([^}]*)\}\}", lambda m: "runes: " + m.group(1).replace("|", ", "), s)
    s = re.sub(r"\{\{Fairycode\|([^}]*)\}\}", lambda m: "fairy ring " + m.group(1).replace("|", ""), s)
    s = re.sub(r"\{\{GEPT?\|([^}|]+)[^}]*\}\}", r"\1", s)
    s = re.sub(r"\{\{NoCoins(?:\|[^}]*)?\}\}", "", s)
    s = re.sub(r"\{\{[Ss]ic\}\}", "", s)
    s = re.sub(r"\{\{[Bb]oostable\|[^}]*\}\}", "", s)
    s = re.sub(r"\{\{efn\|.*?\}\}", "", s, flags=re.S)
    s = re.sub(r"\{\{[Cc]oins\|([0-9,]+)\}\}", r"\1 coins", s)
    return s

def strip_nested_templates(s):
    """Remove all {{...}} including nested ones by repeatedly deleting the
    innermost (brace-free) template until none remain."""
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    return s

def clean(s):
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = expand_templates(s)
    s = strip_nested_templates(s)  # drop any remaining (possibly nested) templates
    s = re.sub(r"\[\[[^\]|]*\|([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"'''?", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&nbsp;", " ").replace("&ndash;", "-").replace("&amp;", "&")
    s = re.sub(r"\s+", " ", s).strip()
    return s.strip(" .")  # trailing periods normalised off for items

def linked_targets(s):
    out = []
    for m in re.finditer(r"\[\[([^\]|#]+)", s):
        out.append(m.group(1).strip())
    return out

def get_tier_blocks(txt):
    """Return tier -> (task_table_text, reward_text)."""
    blocks = {}
    for tier in TIERS:
        m = re.search(r"\n==\s*%s\s*==" % re.escape(tier), txt)
        if not m:
            blocks[tier] = ("", "")
            continue
        start = m.end()
        # tier section ends at next level-2 header
        nm = re.search(r"\n==[^=]", txt[start:])
        end = start + nm.start() if nm else len(txt)
        sec = txt[start:end]
        # reward subsection (=== Rewards ===) within the tier section
        # NB: tolerate trailing whitespace after the closing '===' (some pages,
        # e.g. Varrock hard/elite, write "===Rewards=== \n"); the old anchor
        # required '===' immediately before the newline and silently dropped
        # those reward blocks.
        rm = re.search(r"===\s*Rewards?\s*===[ \t]*\n(.*)$", sec, re.S)
        reward = rm.group(1) if rm else ""
        task_part = sec[:rm.start()] if rm else sec
        blocks[tier] = (task_part, reward)
    return blocks

def parse_tasks(task_part):
    """Yield (number, task_raw, req_raw) from a tier's diary-table.

    A tier section may contain a leading {{Map}} "Task locations" collapsible
    table; the real task list is the wikitable carrying the diary-table class /
    data-diary-tier attribute, so anchor on that rather than the first {|.
    """
    dm = re.search(r"diary-table|data-diary-tier", task_part)
    if dm:
        tstart = task_part.rfind("{|", 0, dm.start())
    else:
        tstart = task_part.find("{|")
    if tstart == -1:
        return
    tend = task_part.find("\n|}", tstart)
    block = task_part[tstart: tend if tend != -1 else len(task_part)]
    rows = re.split(r"\n\|-", block)
    for rb in rows:
        tm = re.search(r"^\|\s*(\d+)\.\s(.+?)(?=\n\|)", rb, re.S | re.M)
        if not tm:
            continue
        num = int(tm.group(1))
        task_raw = tm.group(2)
        after = rb[tm.end():]
        req_m = re.search(r"\n\|(.*)$", after, re.S)
        req_raw = req_m.group(1) if req_m else ""
        yield num, task_raw, req_raw

def parse_requirements(req_raw):
    """Parse a tier-row's requirement cell into skills / quests / items.

    Flat skills: every {{SCP|Skill|level}} in the cell, deduped, EXCEPT that the
    same skill is only carried at its first (lowest-index = primary,
    unconditional) level. Later occurrences of the *same* skill are conditional
    alternatives -- gear/account reductions the wiki lists on extra bullets such
    as
        *{{SCP|Runecraft|88}}
        *{{SCP|Runecraft|77}} with 2 Raiments of the Eye pieces
      or
        *{{SCP|Farming|23}} (Ironman accounts require {{SCP|Farming|47}} ...)
    Emitting all of them as flat skills falsely implies a player needs *both*
    Runecraft 88 and 77 (the conditional-skill parse artifact). Those secondary
    same-skill SCPs are instead kept as self-contained item-notes with their
    skill+level inline (so no "with 2 Raiments..." fragment is stranded), and
    the bullet they came from is suppressed from the item list to avoid the
    duplicate / "(... require or ...)" leftover the old text-strip produced.
    """
    skills, quests, items = [], [], []
    boostable = bool(re.search(r"\{\{[Bb]oostable\|y", req_raw))

    # 1) Flat skills: first level per skill is primary; remember which
    #    (skill, level) pairs are *secondary* (conditional) so we can both keep
    #    them out of flat skills and surface them as inline item-notes.
    seen_pairs = set()
    primary_level = {}
    conditional = []  # list of (skill, level) secondary occurrences, in order
    for sm in SCP_RE.finditer(req_raw):
        skill, level = sm.group(1).strip(), int(sm.group(2))
        if skill.lower() == "quest":
            continue  # quest marker, handled via bullets below
        if (skill, level) in seen_pairs:
            continue
        seen_pairs.add((skill, level))
        if skill not in primary_level:
            primary_level[skill] = level
            skills.append({"skill": skill, "level": level})
        else:
            conditional.append((skill, level))

    # 2) Bullets -> quests / items. Bullets carrying a *secondary* same-skill SCP
    #    are the conditional-alternative bullets; replace them with one inline
    #    note per secondary SCP (skill+level + the bullet's qualifier text)
    #    rather than the SCP-stripped fragment.
    for b in re.split(r"\n\*+", "\n" + req_raw):
        b = b.strip()
        if not b:
            continue
        is_quest = bool(re.search(r"\{\{SCP\|Quest", b))

        bullet_secondary = [(s, l) for s, l in conditional
                            if re.search(r"\{\{SCP\|%s\|%d\b" % (re.escape(s), l), b)]
        if bullet_secondary:
            # Render the conditional bullet as one readable item-note, keeping
            # each SCP in place as "Skill level" so the qualifier reads
            # naturally whether the secondary SCP is trailing ("...with 2
            # Raiments...") or embedded ("(Ironman accounts require Farming 47
            # or ...)"). The primary SCP, already a flat skill req, is dropped
            # from the rendered note.
            b_rendered = SCP_RE.sub(
                lambda m: ("" if (m.group(1).strip(), int(m.group(2))) not in bullet_secondary
                           else "%s %s" % (m.group(1).strip(), m.group(2))),
                b)
            note = clean(b_rendered)
            note = re.sub(r"\s+", " ", note).strip(" ,.")
            if note and note.lower() != "none":
                items.append(note)
            continue

        bclean = clean(b)
        if not bclean or bclean.lower() == "none":
            continue
        if is_quest:
            quests.append(bclean)
        elif SCP_RE.search(b) and (len(bclean.split()) <= 2
                                   or _CONNECTIVE_ONLY_RE.match(bclean)):
            # Leftover from a primary skill bullet: either a short skill-name
            # remnant (original behaviour) or pure connective punctuation from a
            # multi-skill bullet (e.g. ", , and"). Neither is a real item req.
            continue
        else:
            items.append(bclean)
    return skills, quests, items, boostable

records = []
domain_stats_by_diary = {}
for slug, region in DIARIES:
    with open(f"data/raw/diary_{slug}.wikitext") as f:
        txt = f.read()
    src_url = WIKI + slug + "_Diary"
    tier_blocks = get_tier_blocks(txt)
    per_tier_counts = {}
    for tier in TIERS:
        task_part, reward_raw = tier_blocks[tier]
        if reward_raw.strip():
            # strip (possibly nested) parser-functions/templates first because
            # they may contain '|', then convert bullets to a readable separator.
            rw = strip_nested_templates(reward_raw)
            rw = re.sub(r"\n\*+\s*", " | ", "\n" + rw)
            reward = clean(rw)
            reward = re.sub(r"\s*\|\s*", " | ", reward).strip(" |")
        else:
            reward = None
        cnt = 0
        for num, task_raw, req_raw in parse_tasks(task_part):
            cnt += 1
            skills, quests, items, boostable = parse_requirements(req_raw)
            records.append(OrderedDict([
                ("diary_region", region),
                ("tier", tier.lower()),
                ("task_number", num),
                ("task", clean(task_raw)),
                ("requirements", OrderedDict([
                    ("skills", skills), ("quests", quests), ("items", items),
                ])),
                ("boostable", boostable),
                ("reward", reward),
                ("source_url", src_url),
            ]))
        per_tier_counts[tier.lower()] = cnt
    domain_stats_by_diary[region] = {"per_tier": per_tier_counts,
                                     "total": sum(per_tier_counts.values())}

print("total records:", len(records))
for r, st in domain_stats_by_diary.items():
    print(f"  {r}: {st['total']}  {st['per_tier']}")
print("by tier:", dict(Counter(r["tier"] for r in records)))
json.dump({"records": records, "domain_stats_by_diary": domain_stats_by_diary},
          open("data/raw/diaries_authoritative_intermediate.json", "w"), indent=1)
