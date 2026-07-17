"""Tests for kg_ingest.builders.farming_tables (Task 3, spec §7).

Per the task-3 brief's REVISED-DURING-EXECUTION note: the parser was redesigned
(table-first: find_tables/keep_table/header_columns) and proven against the real
committed snapshot. This test module keeps the plan's original Step-1 unit tests
verbatim (they exercise the preserved public helpers: split_cells, types_in_cell,
trailing_place_link, gardeners_in, PAGE_DEFAULT_TYPE) and adds unit tests for the
new helpers (keep_table, normalize, special_type) plus the census test — the real
proof, run against data/raw/wiki_farming_patch_tables.json.
"""
import json
import pathlib

from kg_ingest.builders.farming_tables import (
    split_rows, split_cells, types_in_cell, trailing_place_link, gardeners_in,
    parse_patch_tables, PAGE_DEFAULT_TYPE, keep_table, normalize, special_type,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]


# ------------------------------------------------------------------ Step 1 (original, kept verbatim)

def test_split_cells_respects_template_and_link_pipes():
    row = "| *[[Herb patch|Herb]] || North of [[Catherby]] || {{Map|2810,3464|r=6}}"
    cells = split_cells(row)
    assert cells[0].strip() == "*[[Herb patch|Herb]]"
    assert cells[1].strip() == "North of [[Catherby]]"
    assert cells[2].strip() == "{{Map|2810,3464|r=6}}"   # pipe inside {{ }} not split


def test_types_in_cell_reads_the_bullet_links():
    cell = "*[[Allotment patch|Allotment]]\n*[[Flower patch|Flower]]\n*[[Herb patch|Herb]]"
    assert types_in_cell(cell) == ["allotment", "flower", "herb"]


def test_types_in_cell_herb_only_row_yields_only_herb():
    # the anti-fabrication case: a herb-only site must NOT emit allotment/flower
    assert types_in_cell("*[[Herb patch|Herb]]") == ["herb"]


def test_types_in_cell_flower_only_row_yields_only_flower():
    assert types_in_cell("*[[Flower patch|Flower]]") == ["flower"]


def test_trailing_place_link_takes_the_last_link():
    assert trailing_place_link("[[Hemenster|North]] of [[Ardougne]]") == "Ardougne"
    assert trailing_place_link("South of [[Falador]]") == "Falador"
    assert trailing_place_link("Roof of the [[Troll Stronghold (location)|Troll Stronghold]]") == "Troll Stronghold (location)"
    assert trailing_place_link("no link here") is None


def test_gardeners_in_parses_zero_one_and_many():
    assert gardeners_in("South of [[Falador]]<br>''Gardener: [[Elstan]]''") == ["Elstan"]
    assert gardeners_in("[[Catherby]]<br>''Gardeners: [[A]] or [[B]]''") == ["A", "B"]
    assert gardeners_in("[[Weiss]]") == []


def test_page_default_type_map_covers_the_single_type_subpages():
    assert PAGE_DEFAULT_TYPE["Bush patch/Patches"] == "bush"
    assert PAGE_DEFAULT_TYPE["Fruit tree patch/Patches"] == "fruit_tree"
    assert PAGE_DEFAULT_TYPE["Spirit Tree (Farming)/Patches"] == "spirit_tree"
    assert PAGE_DEFAULT_TYPE["Allotment patch/Patches"] is None   # multi-type: read the cell


# ------------------------------------------------------------------ new helpers (revised design)

def test_keep_table_requires_both_location_and_map_column():
    assert keep_table(["Location", "Map", "Types"]) is True
    assert keep_table(["Location", "Image"]) is True
    assert keep_table(["Location"]) is False          # Location-only (e.g. the Activity sub-table) -> skipped
    assert keep_table(["Map"]) is False
    assert keep_table([]) is False


def test_normalize_expands_the_table_escape_idiom_in_order():
    assert normalize("{{!}}foo") == "\n|foo"
    assert normalize("{{!}}-\n") == "\n|-\n"
    # order matters: {{!}}- must become \n|- BEFORE the bare {{!}} rewrite runs,
    # else it would double-expand into \n|\n-
    body = "{|\n{{!}}-\n{{!}} cell one {{!}}{{!}} cell two\n{{!}}}"
    out = normalize(body)
    assert "\n|-\n" in out
    assert "\n| cell one " in out


def test_special_type_reads_the_link_label_when_no_leading_plain_text():
    assert special_type("[[Grape seeds|Grape]]") == "grape"


def test_special_type_reads_the_leading_plain_text_word():
    assert special_type("Hardwood") == "hardwood"


# ------------------------------------------------------------------ Step 5 census (the real proof)

def test_parse_real_snapshot_census():
    tables = json.loads((ROOT / "data" / "raw" / "wiki_farming_patch_tables.json").read_text())["tables"]
    rows = parse_patch_tables(tables)

    assert len(rows) == 77

    distinct_nodes = {(r["patch_type"], r["place_link"]) for r in rows}
    assert len(distinct_nodes) == 76

    types = {r["patch_type"] for r in rows}
    core = {"herb", "allotment", "flower", "bush", "hops", "tree", "fruit_tree", "spirit_tree", "coral"}
    special = {
        "cactus", "redwood", "calquat", "celastrus", "crystal", "hardwood",
        "belladonna", "hespori", "anima", "grape", "mushroom", "seaweed",
    }
    assert core <= types
    assert special <= types

    assert "" not in types
    assert all(r["patch_type"] for r in rows)
    assert all(r["place_link"] for r in rows)
