#!/usr/bin/env python3
"""Deterministically parse Module:Questreq/data Lua table into JSON.

The Lua source is a single `local questReqs = { ... }` table. Each entry is:
    ['Quest Name'] = {
        ['quests'] = { 'a', 'b', ... },   -- optional
        ['skills'] = { {'Skill', level}, {'Skill', level, 'ironman'}, ... }  -- optional
    },

We parse it with a small tokenizer/recursive-descent reader rather than paraphrasing,
so the output reflects the real data exactly. Lua string escapes are handled.
"""
import json
import re
import sys

LUA_PATH = "/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/data/raw/questreq.lua"
BUCKET_PATH = "/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/data/raw/quest_bucket.json"
OUT_PATH = "/Users/adrian/Documents/workspace/github.com/retrogramx/osrs-planner-tool/data/quests.json"

SOURCE_URLS = [
    "https://oldschool.runescape.wiki/w/Module:Questreq/data?action=raw",
    "https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query="
    "bucket('quest').select('page_name','official_difficulty','official_length',"
    "'requirements','items_required','ironman_concerns').run()",
]


# ---------------------------------------------------------------------------
# Minimal Lua-value tokenizer / reader.
# Supports: tables { ... }, single/double quoted strings, integers, keyed
# entries ['key'] = value and identifier keys foo = value.
# Strips Lua comments (-- line and --[[ block ]]).
# ---------------------------------------------------------------------------

def strip_comments(src: str) -> str:
    # Remove block comments --[[ ... ]] (non-greedy, dotall).
    src = re.sub(r"--\[\[.*?\]\]", "", src, flags=re.DOTALL)
    # Remove line comments -- ... to end of line. Must avoid eating inside
    # strings; the questreq data has no '--' inside strings, but guard anyway
    # by only stripping when not within quotes. Simple line-based pass:
    out_lines = []
    for line in src.splitlines():
        # find '--' not inside a quote
        in_s = None
        i = 0
        cut = None
        while i < len(line):
            c = line[i]
            if in_s:
                if c == "\\":
                    i += 2
                    continue
                if c == in_s:
                    in_s = None
            else:
                if c in ("'", '"'):
                    in_s = c
                elif c == "-" and i + 1 < len(line) and line[i + 1] == "-":
                    cut = i
                    break
            i += 1
        out_lines.append(line if cut is None else line[:cut])
    return "\n".join(out_lines)


class Reader:
    def __init__(self, s):
        self.s = s
        self.i = 0
        self.n = len(s)

    def ws(self):
        while self.i < self.n and self.s[self.i] in " \t\r\n":
            self.i += 1

    def peek(self):
        self.ws()
        return self.s[self.i] if self.i < self.n else ""

    def expect(self, ch):
        self.ws()
        if self.i >= self.n or self.s[self.i] != ch:
            raise ValueError(f"expected {ch!r} at pos {self.i}: ...{self.s[self.i:self.i+40]!r}")
        self.i += 1

    def read_string(self):
        self.ws()
        q = self.s[self.i]
        assert q in ("'", '"')
        self.i += 1
        buf = []
        while self.i < self.n:
            c = self.s[self.i]
            if c == "\\":
                nxt = self.s[self.i + 1]
                mapping = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "'": "'", '"': '"'}
                buf.append(mapping.get(nxt, nxt))
                self.i += 2
                continue
            if c == q:
                self.i += 1
                return "".join(buf)
            buf.append(c)
            self.i += 1
        raise ValueError("unterminated string")

    def read_number(self):
        self.ws()
        m = re.match(r"-?\d+(?:\.\d+)?", self.s[self.i:])
        if not m:
            raise ValueError(f"bad number at {self.i}: {self.s[self.i:self.i+20]!r}")
        self.i += m.end()
        txt = m.group(0)
        return int(txt) if "." not in txt else float(txt)

    def read_key(self):
        # ['string'] or [number] or identifier
        self.ws()
        if self.s[self.i] == "[":
            self.i += 1
            self.ws()
            if self.s[self.i] in ("'", '"'):
                k = self.read_string()
            else:
                k = self.read_number()
            self.expect("]")
            return k
        # bare identifier key
        m = re.match(r"[A-Za-z_]\w*", self.s[self.i:])
        if not m:
            return None
        self.i += m.end()
        return m.group(0)

    def read_value(self):
        c = self.peek()
        if c == "{":
            return self.read_table()
        if c in ("'", '"'):
            return self.read_string()
        if c == "-" or c.isdigit():
            return self.read_number()
        # booleans / nil / identifiers (none expected, but handle)
        m = re.match(r"[A-Za-z_]\w*", self.s[self.i:])
        if m:
            self.i += m.end()
            word = m.group(0)
            return {"true": True, "false": False, "nil": None}.get(word, word)
        raise ValueError(f"unexpected value at {self.i}: {self.s[self.i:self.i+30]!r}")

    def read_table(self):
        self.expect("{")
        # Decide: array, map, or mixed. We collect both.
        arr = []
        mp = {}
        while True:
            self.ws()
            if self.peek() == "}":
                self.i += 1
                break
            # Determine if this field is keyed.
            save = self.i
            keyed = False
            key = None
            c = self.s[self.i]
            if c == "[":
                key = self.read_key()
                self.ws()
                if self.peek() == "=":
                    self.i += 1
                    keyed = True
                else:
                    raise ValueError("'[key]' without '='")
            else:
                # could be identifier = value, or a plain value
                m = re.match(r"[A-Za-z_]\w*", self.s[self.i:])
                if m:
                    look = self.i + m.end()
                    j = look
                    while j < self.n and self.s[j] in " \t\r\n":
                        j += 1
                    if j < self.n and self.s[j] == "=" and (j + 1 >= self.n or self.s[j + 1] != "="):
                        key = m.group(0)
                        self.i = j + 1
                        keyed = True
                    else:
                        self.i = save
            val = self.read_value()
            if keyed:
                mp[key] = val
            else:
                arr.append(val)
            self.ws()
            if self.peek() in (",", ";"):
                self.i += 1
        if mp and not arr:
            return mp
        if arr and not mp:
            return arr
        if not arr and not mp:
            return []  # empty table
        # mixed: return dict with array under special key (not expected here)
        mp["__array__"] = arr
        return mp


def parse_lua(src: str) -> dict:
    src = strip_comments(src)
    m = re.search(r"local\s+questReqs\s*=\s*", src)
    if not m:
        raise ValueError("could not find 'local questReqs ='")
    r = Reader(src)
    r.i = m.end()
    table = r.read_table()
    return table


# ---------------------------------------------------------------------------
# Normalize.
# ---------------------------------------------------------------------------

def normalize_skill(entry):
    # entry is a list like ['Skill', level, 'ironman', 'boostable']
    if not isinstance(entry, list) or len(entry) < 2:
        raise ValueError(f"unexpected skill entry: {entry!r}")
    skill = entry[0]
    level = entry[1]
    flags = entry[2:]
    rec = {"skill": skill, "level": level}
    rec["ironman"] = "ironman" in flags
    rec["boostable"] = "boostable" in flags
    # surface any unknown flags so nothing is silently dropped
    known = {"ironman", "boostable"}
    extra = [f for f in flags if f not in known]
    if extra:
        rec["other_flags"] = extra
    return rec


def main():
    with open(LUA_PATH, "r", encoding="utf-8") as f:
        lua_src = f.read()
    table = parse_lua(lua_src)

    with open(BUCKET_PATH, "r", encoding="utf-8") as f:
        bucket = json.load(f)["bucket"]
    bmap = {}
    for r in bucket:
        bmap[r["page_name"]] = r

    records = []
    matched_bucket = 0
    for quest in sorted(table.keys()):
        body = table[quest]
        prereq = body.get("quests", []) if isinstance(body, dict) else []
        skills_raw = body.get("skills", []) if isinstance(body, dict) else []
        skill_reqs = [normalize_skill(s) for s in skills_raw]
        rec = {
            "quest": quest,
            "prereq_quests": list(prereq),
            "skill_reqs": skill_reqs,
        }
        b = bmap.get(quest)
        if b:
            matched_bucket += 1
            diff = b.get("official_difficulty")
            length = b.get("official_length")
            ic = b.get("ironman_concerns")
            if diff and diff != "None":
                rec["difficulty"] = diff
            if length:
                rec["length"] = length
            if ic:
                rec["ironman_concerns"] = ic
        records.append(rec)

    out = {
        "_provenance": {
            "source_urls": SOURCE_URLS,
            "accessed": "Fetched 2026-06-16 via curl from the OSRS Wiki "
                        "(Module:Questreq/data raw + bucket API).",
            "license": "CC BY-NC-SA 3.0",
            "notes": (
                "quest, prereq_quests, and skill_reqs are parsed deterministically "
                "from Module:Questreq/data. difficulty/length/ironman_concerns are "
                "joined by exact page_name from the quest bucket; the bucket covers "
                f"{len(bucket)} pages so not every Questreq entry has these fields "
                "(Questreq also includes Achievement Diary tiers and quest-series "
                "subtasks that are not standalone bucket 'quest' pages)."
            ),
            "questreq_entry_count": len(table),
            "bucket_record_count": len(bucket),
            "records_matched_to_bucket": matched_bucket,
        },
        "quests": records,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # report
    print("questreq entries parsed:", len(table))
    print("records written:", len(records))
    print("matched to bucket:", matched_bucket)
    total_prereq = sum(len(r["prereq_quests"]) for r in records)
    total_skill = sum(len(r["skill_reqs"]) for r in records)
    print("total prereq edges:", total_prereq)
    print("total skill reqs:", total_skill)
    with_diff = sum(1 for r in records if "difficulty" in r)
    with_len = sum(1 for r in records if "length" in r)
    with_ic = sum(1 for r in records if "ironman_concerns" in r)
    print("with difficulty:", with_diff, "with length:", with_len, "with ironman_concerns:", with_ic)


if __name__ == "__main__":
    main()
