# kg_ingest/builders/farming_tables.py
"""Deterministic parser for the OSRS farming-patch location tables (spec §7).

Turns the committed table wikitext (wiki_farming_patch_tables.json) into typed patch
rows. Anti-fabrication rules live here:
  * type emission is PER-ROW from the row's actual "Types" cell links (never a fixed
    3-way expansion) — a herb-only site emits ONLY herb (spec D6);
  * the place is the TRAILING [[Place]] link of the location HEAD phrase (before any
    gardener / requirement / <ref> note) — not first-wins, not a note link;
  * gardeners are 0..n;
  * NO coordinates are read or stored (spec D5).

Table-first design: each page holds >=1 wikitable; we keep only tables that have BOTH a
"Location" and a "Map"/"Image" column (this auto-skips the coordinate-less Activity
sub-table [spec D4] and the coral-frags stats table), read the header to find the
Type/Location columns, then parse each data row by column index. The only page using the
{{!}} table-escape idiom is the parameterized `Allotment patch/Patches` template; we
normalize {{!}} back to table syntax first. Pure, offline.
"""
from __future__ import annotations
import re

from kg_ingest.ids import slugify

# Which single patch_type a page's rows are, or None for the multi-type / typed-column pages.
PAGE_DEFAULT_TYPE = {
    "Allotment patch/Patches": None,        # allotment/flower/herb — read the Types cell per row
    "Bush patch/Patches": "bush",
    "Hops patch/Patches": "hops",
    "Tree patch/Patches": "tree",
    "Fruit tree patch/Patches": "fruit_tree",
    "Spirit Tree (Farming)/Patches": "spirit_tree",
    "Special patches/Patches": None,        # umbrella — type from the row's Type/Sapling cell or section
    "Coral nursery (patch)": None,          # coral row carries its own Types cell -> coral
}

# Map a linked patch-type PAGE title -> the closed core patch_type token (spec D8).
_TYPE_PAGE = {
    "allotment patch": "allotment", "flower patch": "flower", "herb patch": "herb",
    "bush patch": "bush", "hops patch": "hops", "tree patch": "tree",
    "fruit tree patch": "fruit_tree", "spirit tree": "spirit_tree",
    "coral nursery (patch)": "coral", "coral nursery": "coral",
}

_LINK = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")            # -> link TARGET
_LINK_LABEL = re.compile(r"\[\[[^\]|#]+(?:#[^\]|]*)?\|([^\]]+)\]\]|\[\[([^\]|#]+)\]\]")  # -> display LABEL


# ------------------------------------------------------------------ table structure

def find_tables(wikitext):
    """Yield each wikitable body ({| ... |}) with its char start offset. Tables never nest
    here; the infobox uses {{...}} so `{|` matches only real table starts."""
    out, i = [], 0
    while True:
        start = wikitext.find("{|", i)
        if start == -1:
            break
        end = wikitext.find("\n|}", start)
        end = end + 3 if end != -1 else (wikitext.find("|}", start) + 2)
        out.append((start, wikitext[start:end]))
        i = end
    return out


def section_of(wikitext, table_start):
    """The nearest `== Heading ==` (any level) whose text precedes table_start; else None."""
    last = None
    for m in re.finditer(r"={2,}\s*(.+?)\s*={2,}", wikitext):
        if m.start() < table_start:
            last = m.group(1).strip()
        else:
            break
    return last


def header_columns(table_body):
    """Ordered header labels from the leading `!` header block (before the first `|-`)."""
    head = re.split(r"\n\|-", table_body, maxsplit=1)[0]
    cols = []
    for line in head.split("\n"):
        if not line.lstrip().startswith("!"):
            continue
        for cell in re.split(r"!!", line):
            cell = cell.strip().lstrip("!").strip()
            if not cell:
                continue
            if "|" in cell:                              # strip a leading `attr |` prefix
                left, right = cell.split("|", 1)
                if re.search(r'=|"|style|class|width|scope|rowspan|colspan', left):
                    cell = right
            cols.append(re.sub(r"\[\[[^\]|]*\|?([^\]]*)\]\]", r"\1", cell).strip())
    return cols


def keep_table(cols):
    """A location table iff it has BOTH a Location and a Map/Image column. Auto-skips the
    Activity sub-table (Location but no Map — spec D4) and the coral-frags stats table."""
    low = [c.lower() for c in cols]
    return "location" in low and ("map" in low or "image" in low)


def _col_index(cols, names):
    for i, c in enumerate(cols):
        if c.lower() in names:
            return i
    return None


# ------------------------------------------------------------------ row / cell split

def normalize(table_body):
    """Expand the {{!}} table-escape idiom (the Allotment template). Order matters:
    the row-marker {{!}}- must be rewritten before the cell-marker {{!}}."""
    return table_body.replace("{{!}}-", "\n|-").replace("{{!}}", "\n|")


def split_rows(table_body):
    """Data-row segments of one (normalized) table body: the pieces between `|-` markers,
    dropping segment 0 (the `{|`+header preamble, incl. any trailing template-guard opener)."""
    return re.split(r"\n\|-+", normalize(table_body))[1:]


def split_cells(row_text):
    """Cells of a row, splitting on `||` (inline) or a line-leading `|` at [[]]/{{}} depth 0
    (so pipes inside [[a|b]] and {{Map|..}} never split). The leading pre-first-pipe fragment
    is dropped; interior empty cells are KEPT (column-index alignment). Inline `attr="..."|`
    cell-attribute prefixes are stripped."""
    cells, buf, depth = [], [], 0
    i, s = 0, row_text
    while i < len(s):
        two = s[i:i + 2]
        if two in ("{{", "[["):
            depth += 1; buf.append(two); i += 2; continue
        if two in ("}}", "]]"):
            depth = max(0, depth - 1); buf.append(two); i += 2; continue
        if depth == 0 and two == "||":
            cells.append("".join(buf)); buf = []; i += 2; continue
        if depth == 0 and s[i] == "|" and (i == 0 or s[i - 1] == "\n"):
            cells.append("".join(buf)); buf = []; i += 1; continue
        buf.append(s[i]); i += 1
    cells.append("".join(buf))
    if cells and cells[0].strip() == "":
        cells = cells[1:]
    return [re.sub(r'^\s*[A-Za-z-]+="[^"]*"\s*\|', "", c) for c in cells]


# ------------------------------------------------------------------ field extractors

def _links(text):
    return _LINK.findall(text or "")


def types_in_cell(cell):
    """Core patch_types explicitly linked in a Types/Type cell, de-duped first-seen. Empty
    when the cell links no known patch page (caller falls back to special/default)."""
    out = []
    for target in _links(cell):
        t = _TYPE_PAGE.get(target.strip().lower())
        if t and t not in out:
            out.append(t)
    return out


def special_type(cell):
    """Special-crop token when a Type/Sapling cell is not a known patch page: the leading
    plain-text descriptor (e.g. 'Hardwood'), else the first link's display label
    ('[[Grape seeds|Grape]]' -> 'grape'). None if neither. Never touches {{Map}} (spec D5)."""
    lead = re.split(r"<br|\[\[|\n", cell.strip(), maxsplit=1)[0].strip().strip("'").strip()
    if lead and not lead.startswith(("*", "(")):
        return slugify(lead) or None
    m = _LINK_LABEL.search(cell)
    if m:
        return slugify((m.group(1) or m.group(2)).strip()) or None
    return None


def trailing_place_link(location_cell):
    """The place anchor: the LAST [[link]] target in the location HEAD phrase — truncated at
    the first gardener / <br> / <ref> / requirement note so a trailing note link
    ('...([[Elite Morytania Diary]] required)') is never mistaken for the place. None if no
    link. Fixes both the multi-link mis-home ([[Hemenster|North]] of [[Ardougne]] -> Ardougne)
    and the note-link mis-home."""
    head = re.split(r"<br|<ref|\n\(|\(requires|gardener",
                    location_cell or "", flags=re.IGNORECASE)[0]
    links = _links(head)
    return links[-1].strip() if links else None


def gardeners_in(location_cell):
    """0..n gardener names from the 'Gardener(s): ...' clause; [] if none. The clause tail is
    cut at the closing italic / newline / <br> / requirement so quest/note links after the
    name are not captured. Returns link TARGETS (display-label form is a cosmetic option)."""
    parts = re.split(r"gardener[s]?\s*:", location_cell or "", flags=re.IGNORECASE)
    if len(parts) < 2:
        return []
    tail = re.split(r"''|\n|<br|\(requires|\(the |\(\[\[", parts[1])[0]
    return [g.strip() for g in _links(tail)]


# ------------------------------------------------------------------ orchestration

def parse_patch_tables(tables):
    """All patch rows across the committed tables. One row dict per (patch_type x location
    row) — a multi-type Allotment row fans out to one dict per type in its Types cell. Rows
    with no resolvable patch_type or no place link are dropped (never a placeholder)."""
    rows = []
    for page, rec in sorted(tables.items()):
        wikitext = rec.get("wikitext", "")
        default = PAGE_DEFAULT_TYPE.get(page)
        for start, body in find_tables(wikitext):
            cols = header_columns(body)
            if not keep_table(cols):
                continue
            lci = _col_index(cols, {"location"})
            tci = _col_index(cols, {"types", "type", "sapling"})
            section = section_of(wikitext, start)
            section_type = None
            if default is None and tci is None:                       # Cactus: type from section
                section_type = slugify(re.sub(r"(?i)\bpatches?\b", "", section or "").strip()) or None
            for seg in split_rows(body):
                cells = split_cells(seg)
                if lci is None or lci >= len(cells):
                    continue
                loc_cell = cells[lci]
                place = trailing_place_link(loc_cell)
                if place is None:
                    continue                                          # blank/spacer row
                if default is not None:
                    types = [default]
                elif tci is not None and tci < len(cells):
                    types = types_in_cell(cells[tci]) or [t for t in (special_type(cells[tci]),) if t]
                else:
                    types = [section_type] if section_type else []
                for t in [x for x in types if x]:
                    rows.append({
                        "patch_type": t,
                        "place_link": place,
                        "gardeners": gardeners_in(loc_cell),
                        "location_raw": loc_cell.strip(),
                        "source_page": page,
                        "source_url": rec.get("source_url", ""),
                        "row_index": len(rows),
                    })
    return rows
