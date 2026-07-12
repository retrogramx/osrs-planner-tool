from osrs_planner.engine.kg.model import Node, NodeKind, EdgeType
from kg_ingest.builders.farming import build_farming_patches, resolve_place


def _places(*names):
    return [Node(id=f"place:{n.lower().replace(' ', '-')}", kind=NodeKind.PLACE,
                 name=n, slug=n.lower().replace(" ", "-"), data={}) for n in names]


def _row(pt, link, page="Herb patch/Patches", gardeners=None, loc=None, idx=0):
    return {"patch_type": pt, "place_link": link, "gardeners": gardeners or [],
            "location_raw": loc or f"[[{link}]]", "source_page": page,
            "source_url": f"https://oldschool.runescape.wiki/w/{page.replace(' ', '_')}",
            "row_index": idx}


def test_emits_node_and_located_in_for_resolved_place():
    nodes, edges, groups = build_farming_patches(
        [_row("herb", "Catherby", gardeners=["Dantaera"])], _places("Catherby"), {})
    assert groups == {}
    n = next(x for x in nodes if x.id == "farming_patch:herb-catherby")
    assert n.kind == NodeKind.FARMING_PATCH and n.name == "Herb patch (Catherby)"
    assert n.data["patch_type"] == "herb" and n.data["gardener"] == "Dantaera"
    assert n.data["source_token"] == "[[Catherby]]"
    e = next(x for x in edges if x.src == n.id)
    assert e.type == EdgeType.LOCATED_IN and e.dst == "place:catherby"
    assert e.cond_group is None and e.data == {}


def test_underscore_patch_type_slugs_to_dash():
    nodes, _, _ = build_farming_patches([_row("fruit_tree", "Catherby")], _places("Catherby"), {})
    assert any(n.id == "farming_patch:fruit-tree-catherby" for n in nodes)


def test_unresolved_place_is_flag_no_edge():
    nodes, edges, _ = build_farming_patches([_row("herb", "Nowhereton")], _places("Catherby"), {})
    assert any(n.id == "farming_patch:herb-nowhereton" for n in nodes)
    assert edges == []   # FLAG: node kept, no located_in


def test_place_override_resolves_a_flag():
    ov = {"place_overrides": [{"location": "Ortus Farm", "place_id": "place:catherby"}]}
    nodes, edges, _ = build_farming_patches([_row("herb", "Ortus Farm")], _places("Catherby"), ov)
    assert any(e.dst == "place:catherby" for e in edges)


def test_multi_source_same_id_collapses_to_one_byte_identical_node():
    # coral appears in the inline table AND the Special-patches row -> same (type, place) -> ONE node
    rows = [_row("coral", "Coral Nurseries", page="Coral nursery (patch)", gardeners=["Chet"], idx=0),
            _row("coral", "Coral Nurseries", page="Special patches/Patches", gardeners=["Chet"], idx=1)]
    nodes, edges, _ = build_farming_patches(rows, _places("Coral Nurseries"), {})
    coral = [n for n in nodes if n.id == "farming_patch:coral-coral-nurseries"]
    assert len(coral) == 1                      # collapsed in the builder (no dedup_nodes crash)
    assert len([e for e in edges if e.src == "farming_patch:coral-coral-nurseries"]) == 1


def test_coral_node_keeps_gardener_from_the_gardenered_row():
    # coral appears in two sources: the coral page (Gardener: [[Chet]]) and the Special
    # patches table (no gardener). They collapse to ONE node — the winner must be the
    # gardener'd row, not whichever sorts first by (location_raw, source_url, row_index).
    # location_raw mirrors the real asymmetry: the gardener'd row's cell text is the
    # gardener-less row's text PLUS a trailing "Gardener: [[Chet]]" clause, so under a
    # bare (location_raw, source_url, row_index) sort the shorter, gardener-less string
    # is a prefix of the longer one and sorts FIRST (wins) -- reproducing the bug the
    # revision fixes. row_index is also set so a bare sort would pick the gardener-less
    # row even if location_raw tied.
    rows = [_row("coral", "Coral Nurseries", page="Coral nursery (patch)",
                 gardeners=["Chet"], idx=0,
                 loc="[[Coral Nurseries]] Gardener: [[Chet]]"),
            _row("coral", "Coral Nurseries", page="Special patches/Patches",
                 gardeners=[], idx=1,
                 loc="[[Coral Nurseries]]")]
    nodes, edges, _ = build_farming_patches(rows, _places("Coral Nurseries"), {})
    coral = [n for n in nodes if n.id == "farming_patch:coral-coral-nurseries"]
    assert len(coral) == 1
    assert coral[0].data["gardener"] == "Chet"
    assert len([e for e in edges if e.src == "farming_patch:coral-coral-nurseries"]) == 1


def test_same_type_place_from_two_rows_collapses_not_raises():
    # two rows for the same (type, resolved place) — one via override — collapse to ONE node,
    # never a -k suffix. (The injectivity `raise` in the builder is a defensive guard: (type,
    # place_comp) -> id is injective by construction with real data, so it fires only on a
    # contrived type/place slug clash, which valid data cannot produce.)
    rows = [_row("herb", "Catherby", idx=0), _row("herb", "Catherby Alt", idx=1)]
    ov = {"place_overrides": [{"location": "Catherby Alt", "place_id": "place:catherby"}]}
    nodes, _, _ = build_farming_patches(rows, _places("Catherby"), ov)
    assert sum(1 for n in nodes if n.id == "farming_patch:herb-catherby") == 1
    assert not any(n.id.startswith("farming_patch:herb-catherby-") for n in nodes)  # no -k


def test_deterministic_order_independent():
    a = build_farming_patches([_row("herb", "Catherby", idx=0), _row("bush", "Catherby", idx=1)],
                              _places("Catherby"), {})[0]
    b = build_farming_patches([_row("bush", "Catherby", idx=0), _row("herb", "Catherby", idx=1)],
                              _places("Catherby"), {})[0]
    assert [n.id for n in a] == [n.id for n in b]


def test_group_place_id_from_any_resolved_member_not_just_the_winner():
    # Row A ("Catherby", unresolved -- no matching place/override) sorts FIRST (wins the
    # display pick: no gardener on either row ties the first sort field, then location_raw
    # "[[AAA]]" < "[[ZZZZ]]" breaks the tie). Row B ("Catherby Alt", resolved via override to
    # place:catherby) sorts SECOND (loses the pick) but slugifies to the SAME place_comp
    # ("catherby") as row A's unresolved link, so both land in one group.
    # Under the old winner-only backfill (`cand["place_id"] = cand["place_id"] or
    # prev["place_id"]`, applied only when cand WINS), B's resolved place_id never reaches the
    # stored group entry because B never wins the sort -> the node keeps place_id=None -> the
    # located_in edge is silently dropped (a FLAG), even though a group member resolved.
    ov = {"place_overrides": [{"location": "Catherby Alt", "place_id": "place:catherby"}]}
    rows = [
        _row("herb", "Catherby", loc="[[AAA]]", idx=0),        # unresolved, wins the sort
        _row("herb", "Catherby Alt", loc="[[ZZZZ]]", idx=1),   # resolved, loses the sort
    ]
    nodes, edges, _ = build_farming_patches(rows, _places("Unrelated"), ov)
    n = next(x for x in nodes if x.id == "farming_patch:herb-catherby")
    e = next((x for x in edges if x.src == n.id), None)
    assert e is not None and e.type == EdgeType.LOCATED_IN and e.dst == "place:catherby"


def test_resolve_place_uses_norm_index():
    from kg_ingest.builders.farming import _name_index
    idx = _name_index(_places("Port Phasmatys"))
    assert resolve_place("Port Phasmatys", idx, []) == "place:port-phasmatys"
    assert resolve_place("Nonexistent", idx, []) is None
