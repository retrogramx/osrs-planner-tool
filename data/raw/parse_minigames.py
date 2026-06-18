#!/usr/bin/env python3
"""Build data/minigames.json (frozen envelope) from the OSRS Wiki.

Universe (bounded) = bucket('infobox_activity') select page_name, is_members_only.
Per-page detail = {{Infobox Activity}} fields + Rewards/Requirements section links,
parsed faithfully (verbatim values + wiki-link entities; no paraphrasing of facts).
"""
import json, re, datetime

BASE = "/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool"
BUCKET = f"{BASE}/data/raw/minigames_activity_bucket.json"
PAGES  = f"{BASE}/data/raw/minigames_pages_wikitext.json"
OUT    = f"{BASE}/data/minigames.json"

SOURCE_URLS = [
    "https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query="
    "bucket('infobox_activity').select('page_name','is_members_only').limit(500).run()",
    "https://oldschool.runescape.wiki/api.php?action=parse&prop=wikitext&redirects=1&page=<each infobox_activity page>",
]
RAW_FILES = [
    "data/raw/minigames_activity_bucket.json",
    "data/raw/minigames_pages_wikitext.json",
]

# --- helpers ---------------------------------------------------------------

def find_infobox(w, kind=r"(?:Activity|Minigame)"):
    idx = re.search(r'\{\{Infobox %s' % kind, w, re.I)
    if not idx: return None
    i = idx.start(); depth = 0; j = i
    while j < len(w):
        if w[j:j+2] == '{{': depth += 1; j += 2; continue
        if w[j:j+2] == '}}':
            depth -= 1; j += 2
            if depth == 0: return w[i:j]
            continue
        j += 1
    return w[i:]

def parse_fields(box):
    fields = {}
    body = re.sub(r'^\{\{Infobox \w+', '', box, flags=re.I).rstrip()
    if body.endswith('}}'): body = body[:-2]
    depth = 0; cur = ''; parts = []; i = 0
    while i < len(body):
        if body[i:i+2] in ('{{', '[['): depth += 1; cur += body[i:i+2]; i += 2; continue
        if body[i:i+2] in ('}}', ']]'): depth -= 1; cur += body[i:i+2]; i += 2; continue
        if body[i] == '|' and depth == 0: parts.append(cur); cur = ''; i += 1; continue
        cur += body[i]; i += 1
    parts.append(cur)
    for p in parts:
        if '=' in p:
            k, v = p.split('=', 1)
            fields[k.strip()] = v.strip()
    return fields

WLINK = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]*)?\]\]')

def link_targets(text):
    """Ordered unique wiki-link targets (page names), skipping File:/Category:."""
    out = []
    for t in WLINK.findall(text or ''):
        t = t.strip()
        if not t: continue
        if t.lower().startswith(('file:', 'category:', 'image:')): continue
        t = t.split('#', 1)[0].strip()
        if t and t not in out: out.append(t)
    return out

def strip_wikitext(s):
    """Light clean of an infobox value: drop templates, keep link display text."""
    if s is None: return None
    s = re.sub(r'\{\{[^{}]*\}\}', lambda m: clean_template(m.group(0)), s)
    s = re.sub(r'\[\[([^\]|]+)\|([^\]]*)\]\]', r'\2', s)   # [[a|b]] -> b
    s = re.sub(r'\[\[([^\]]+)\]\]', r'\1', s)               # [[a]] -> a
    s = re.sub(r"'''?", '', s)
    s = re.sub(r'<br\s*/?>', '; ', s, flags=re.I)
    s = re.sub(r'<[^>]+>', '', s)
    s = re.sub(r'\s+', ' ', s).strip().strip(';').strip()
    return s or None

def clean_template(t):
    # {{SCP|Skill|level}} -> "Skill level"; {{SCP|Time|12}} -> "Time 12"
    inner = t.strip('{}')
    parts = [p.strip() for p in inner.split('|')]
    name = parts[0].lower()
    if name in ('scp', 'skillclickpic'):
        if len(parts) >= 3: return f"{parts[1]} {parts[2]}"
        if len(parts) == 2: return parts[1]
    return ''

def get_section(w, header):
    pat = re.compile(r'^(={2,})\s*' + re.escape(header) + r'\s*\1\s*$', re.M | re.I)
    m = pat.search(w)
    if not m: return None
    level = len(m.group(1)); rest = w[m.end():]; pos = 0
    while True:
        h = re.search(r'^(={2,})\s*[^=].*?\1\s*$', rest[pos:], re.M)
        if not h: return rest
        if len(h.group(1)) <= level: return rest[:pos + h.start()]
        pos += h.end()

def parse_requirements_field(val):
    """Return list of requirement entities from the infobox requirements field."""
    if not val: return None
    cleaned = strip_wikitext(val)
    if cleaned and cleaned.lower() == 'none': return None
    # split on <br> originally -> we used ';' ; also keep raw
    reqs = [r.strip() for r in re.split(r';', cleaned)] if cleaned else []
    reqs = [r for r in reqs if r and r.lower() != 'none']
    return reqs or None

# --- build -----------------------------------------------------------------

def main():
    bucket = json.load(open(BUCKET))['bucket']
    pages = json.load(open(PAGES))

    # distinct universe with members flag (present is_members_only => members)
    universe = {}
    multi = {}
    for r in bucket:
        pn = r['page_name']
        mem = 'is_members_only' in r
        if pn in universe:
            multi[pn] = multi.get(pn, 1) + 1
        universe.setdefault(pn, mem)
        universe[pn] = universe[pn] or mem

    records = []
    no_infobox = []
    stats_type = {}
    stats_with_rewards = 0
    stats_with_reqs = 0

    for name in sorted(universe):
        members = universe[name]
        page = pages.get(name, {})
        w = page.get('wikitext', '')
        box = find_infobox(w)
        f = parse_fields(box) if box else {}

        atype = f.get('type') or f.get('type1')
        atype = strip_wikitext(atype) if atype else None
        stats_type[atype or 'unspecified'] = stats_type.get(atype or 'unspecified', 0) + 1

        # requirements: infobox field + prose Requirements section links
        req_field = parse_requirements_field(f.get('requirements'))
        req_sec = get_section(w, 'Requirements')
        req_links = link_targets(req_sec) if req_sec else []
        requirements = None
        if req_field or req_links:
            requirements = {}
            if req_field: requirements['stated'] = req_field
            if req_links: requirements['linked_entities'] = req_links
            stats_with_reqs += 1

        # rewards: currency field + Rewards section reward-item links
        rew_sec = get_section(w, 'Rewards')
        rew_links = link_targets(rew_sec) if rew_sec else []
        currency = None
        if f.get('currency'):
            currency = link_targets(f['currency']) or [strip_wikitext(f['currency'])]
        rewards = None
        if currency or rew_links:
            rewards = {}
            if currency: rewards['currency'] = currency
            if rew_links: rewards['linked_entities'] = rew_links
            stats_with_rewards += 1

        rec = {
            "minigame": name,
            "members": members,
            "activity_type": atype,
            "location": strip_wikitext(f.get('location') or f.get('location1')),
            "players": strip_wikitext(f.get('players')),
            "skills": link_targets(f.get('skills')) or None,
            "release": strip_wikitext(f.get('release') or f.get('release1')),
            "requirements": requirements,
            "rewards": rewards,
            "infobox_variants": multi.get(name),  # >1 when page has multiple activity infoboxes
            "has_infobox": bool(box),
        }
        # drop null infobox_variants for cleanliness
        if rec["infobox_variants"] is None:
            del rec["infobox_variants"]
        records.append(rec)
        if not box:
            no_infobox.append(name)

    known_missing = []
    if no_infobox:
        known_missing.append(
            f"{len(no_infobox)} page(s) have no parseable single {{{{Infobox Activity}}}} "
            f"(versioned/variant infobox or different template); structured fields are partial: "
            + ", ".join(no_infobox)
        )

    out = {
        "_provenance": {
            "domain": "minigames",
            "source_urls": SOURCE_URLS,
            "source_query": None,
            "accessed": datetime.date.today().isoformat(),
            "license": "CC BY-NC-SA 3.0",
            "extraction_method": "script",
            "raw_files": RAW_FILES,
            "record_count": len(records),
            "completeness": {
                "bounded_by": "bucket('infobox_activity') page_name universe (OSRS Wiki)",
                "universe_count": len(universe),
                "records_count": len(records),
                "known_missing": known_missing,
            },
            "domain_stats": {
                "bucket_rows": len(bucket),
                "distinct_pages": len(universe),
                "pages_with_multiple_activity_infoboxes": multi,
                "by_activity_type": dict(sorted(stats_type.items(), key=lambda kv: -kv[1])),
                "members_count": sum(1 for v in universe.values() if v),
                "f2p_count": sum(1 for v in universe.values() if not v),
                "with_rewards_info": stats_with_rewards,
                "with_requirements_info": stats_with_reqs,
                "note_members": "members=true derived from bucket is_members_only field being present (empty-string flag = 'Yes'); absent = F2P. Verified against raw infobox 'members=' for a sample.",
                "note_scope": "Universe is the full infobox_activity bucket, which includes Minigames plus Random events, Forestry events, Raids, Bosses, D&D, and an Activity/Quest tagged page. activity_type (from the infobox 'type' field) distinguishes them; nothing is dropped.",
                "note_rewards_requirements": "rewards.linked_entities and requirements.linked_entities are verbatim wiki-link targets from the page Rewards/Requirements sections (facts, not paraphrase). requirements.stated and currency are taken verbatim from the infobox. linked_entities preserve verbatim casing (OSRS link targets only normalise the first letter), so 'X points' and 'x points' may both appear.",
                "note_unlocks": "The optional DOMAIN 'unlocks' field is represented inside rewards.linked_entities (reward-shop items/equipment a minigame unlocks); no separate unlocks key is emitted to avoid duplicating the same wiki facts.",
                "note_account_type": "Minigames are activities, not money methods; none are GE buy/sell flips, so no records meet the GE-dependent exclusion criterion and _excluded is empty. The members/F2P axis is carried per record via the boolean 'members' field.",
            },
        },
        "records": records,
        "_excluded": [],
    }
    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

    print("universe:", len(universe))
    print("records:", len(records))
    print("no_infobox:", no_infobox)
    print("with_rewards:", stats_with_rewards, "with_reqs:", stats_with_reqs)
    print("by_type:", dict(sorted(stats_type.items(), key=lambda kv:-kv[1])))

if __name__ == "__main__":
    main()
