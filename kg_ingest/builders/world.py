"""build_world — the comprehensive location graph (world skeleton).

Reads data/map/world.json (owner-authored geographic backbone) + the committed
wiki location-category snapshot, filters by the IN/OUT granularity rule, types each
place (coarse place_type + fine content_kind), parents it (region-category ->
name-heuristic -> FLAG), and emits place nodes + located_in + same_entity. Edges are
place-src -> assemble re-keys them in their OWN seeded call. Never fabricates.
"""
from __future__ import annotations

import re

from osrs_planner.engine.kg.model import Edge, EdgeType, Node, NodeKind
from kg_ingest.ids import _stable_hash

_EDGE_BAND = 0xB0000000


def parse_infobox_links(location_wikitext):
    """Extract [[Target]] / [[Target|alias]] link targets from an infobox location value,
    in order, de-duped. Verbatim source -> deterministic targets (no inference)."""
    out = []
    for m in re.finditer(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]", location_wikitext or ""):
        target = m.group(1).strip()
        if target and target not in out:
            out.append(target)
    return out


def _edge_id(src_id: str, slot: str) -> int:
    return _EDGE_BAND | _stable_hash(f"{src_id}#edge#{slot}")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\s*\(.*?\)\s*$", "", s.lower()))


# priority-ordered IN type-categories -> (place_type, content_kind). First match wins.
IN_TYPE = [("Raids", "dungeon", "raid"), ("Slayer dungeons", "dungeon", "slayer dungeon"),
           ("Dungeons", "dungeon", "dungeon"), ("Caves", "dungeon", "cave"),
           ("Minigames", "point_of_interest", "minigame"), ("Guilds", "point_of_interest", "guild"),
           ("Agility courses", "point_of_interest", "agility course"), ("Hunter areas", "point_of_interest", "hunter area"),
           ("Castles", "point_of_interest", "castle"), ("Mines", "point_of_interest", "mine"),
           ("Islands", "island", "island"), ("Settlements", "settlement", "settlement")]

IN_NAMES = {cat for cat, _pt, _ck in IN_TYPE}        # self-referential category-index page titles
NOISE_CATS = {"Discontinued content", "Locations that do not appear in-game"}


def is_excluded(title, page_categories):
    """The OUT clause of the IN/OUT filter: list/index pages + discontinued/non-existent.
    Shared by build_world AND verify_world_coverage so coverage stays honest."""
    if title.lower().startswith("list of "):
        return True
    if title in IN_NAMES:
        return True
    if set(page_categories) & NOISE_CATS:
        return True
    return False


def classify(page_categories):
    for cat, pt, ck in IN_TYPE:
        if cat in page_categories:
            return (pt, ck)
    return None


def parent_for(title, page_categories, name_index, infobox_links=None, overrides=None,
               backbone_names=None):
    """Precision-first signal stack -> (parent_id, signal). First hit wins.
    name_index maps a normalized place name -> a place id (backbone + ingested content);
    a noise-excluded page is never in it, and a page never parents to itself.
    backbone_names (set of normalized backbone place names) makes backbone-preference apply
    WITHIN each rung: a rung prefers a BACKBONE match over a content one, but the rung ORDER
    is strict precision-first (category > name-suffix > infobox). So a content CATEGORY match
    (a specific town) beats a backbone INFOBOX link (a less-specific kingdom) — the owner's
    explicit precision-first decision. (Per-rung, not whole-stack: an earlier-but-content rung
    must not be skipped just because a later rung has a backbone hit.) backbone_names=None =
    no preference (the 3-arg unit-test contract)."""
    slug = _slug(title)
    # (1) owner override (editorial escape hatch)
    if overrides and slug in overrides:
        return (overrides[slug]["parent"], "override")

    def _rung(candidates):
        # within a rung: prefer a backbone match, else any (content). deterministic order.
        if backbone_names is not None:
            for nc in candidates:
                pid = name_index.get(nc)
                if pid and pid != slug and nc in backbone_names:
                    return pid
        for nc in candidates:
            pid = name_index.get(nc)
            if pid and pid != slug:
                return pid
        return None

    # (2) category-match: a place-node name among the page's categories (sorted -> deterministic)
    pid = _rung([_norm(c) for c in sorted(page_categories)])
    if pid:
        return (pid, "category")
    # (3) name minus a type suffix -> a place node
    base = re.sub(r"\b(dungeon|caves?|mine|lair|tunnels?|cellar|crypt|vault|arena|course|guild|camp)\b.*$", "", title.lower())
    base = re.sub(r"\s*\(.*?\)\s*$", "", base).strip()
    pid = _rung([_norm(base)]) if _norm(base) else None
    if pid:
        return (pid, "name-suffix")
    # (4) infobox location (deterministic wikitext order)
    pid = _rung([_norm(n) for n in (infobox_links or [])])
    if pid:
        return (pid, "infobox")
    # (5) unresolved -> FLAG (never guess)
    return ("place:gielinor", "FLAG")


def members_of(title, fpts, mbrs):
    if title in mbrs:
        return True
    if title in fpts:
        return False
    return None


def _slug(name: str) -> str:
    return "place:" + re.sub(r"[^a-z0-9]+", "-", re.sub(r"\s*\(.*?\)\s*$", "", name.lower())).strip("-")


def _resolve_reachable(parent):
    """Demote any non-root node that cannot reach place:gielinor (cycle/dangling) to the
    root. Deterministic fixpoint (sorted order). Guarantees single-root + acyclic.
    NOTE: reaches_root reads the ORIGINAL immutable `parent` (not the evolving `out`), so a
    demotion never lengthens another node's path — this converges in at most two passes (it is
    NOT a Bellman-Ford relaxation despite the `while changed` shape)."""
    def reaches_root(s):
        seen, cur = set(), s
        while cur != "place:gielinor":
            if cur is None or cur in seen:
                return False
            seen.add(cur); cur = parent.get(cur)
        return True
    out = dict(parent)
    changed = True
    while changed:
        changed = False
        for s in sorted(out):
            if s != "place:gielinor" and out[s] != "place:gielinor" and not reaches_root(s):
                out[s] = "place:gielinor"; changed = True
    return out


def resolve_parents(backbone, snapshot, extra_seen=None, infoboxes=None, overrides=None):
    """Shared parenting core. Returns (kept, parent_map, signal_map):
      kept       = [(title, place_type, content_kind, pid)]   (filtered, typed, sorted)
      parent_map = {pid: parent_id}                            (Task 3 adds reachability)
      signal_map = {pid: signal}                               (override/category/name-suffix/infobox/FLAG)
    name_index spans backbone + ingested content; backbone WINS on a name collision."""
    pc = snapshot["page_categories"]
    by = {p["id"]: p for p in backbone["places"]}
    def _depth(p):
        d, cur = 0, p.get("located_in")
        while cur and cur in by and d < 12:
            d += 1; cur = by[cur].get("located_in")
        return d
    name_index = {}
    for p in sorted(backbone["places"], key=_depth):     # deepest-backbone-wins among backbone
        name_index[_norm(p["name"])] = p["id"]
    backbone_names = {_norm(p["name"]) for p in backbone["places"]}
    seen = {p["id"] for p in backbone["places"]}
    if extra_seen:
        seen |= set(extra_seen)
    kept = []
    for title in sorted({t for lst in snapshot["categories"].values() for t in lst}):
        cls = classify(set(pc.get(title, [])))
        if cls is None or is_excluded(title, pc.get(title, [])):
            continue
        pid = _slug(title)
        if pid in seen:
            continue
        seen.add(pid)
        kept.append((title, cls[0], cls[1], pid))
    for title, _pt, _ck, pid in kept:
        name_index.setdefault(_norm(title), pid)         # content joins; backbone precedence preserved
    parent_map, signal_map = {}, {}
    for title, _pt, _ck, pid in kept:
        parent, signal = parent_for(title, set(pc.get(title, [])), name_index,
                                    infobox_links=(infoboxes or {}).get(title), overrides=overrides,
                                    backbone_names=backbone_names)
        parent_map[pid] = parent; signal_map[pid] = signal
    backbone_parent = {p["id"]: p.get("located_in") or None for p in backbone["places"]}
    backbone_parent["place:gielinor"] = None
    resolved = _resolve_reachable({**backbone_parent, **parent_map})
    for pid in parent_map:
        if resolved[pid] == "place:gielinor" and parent_map[pid] != "place:gielinor":
            signal_map[pid] = "FLAG"                      # demoted by reachability -> FLAG
        parent_map[pid] = resolved[pid]
    return kept, parent_map, signal_map


def build_world(backbone, snapshot, region_ids, extra_seen=None, infoboxes=None, overrides=None):
    """Build place nodes + located_in/same_entity edges from the world backbone and snapshot.

    extra_seen: additional place ids to treat as already-known during content ingest (used
    by the assembler to pass the varrock.json place ids so build_world doesn't re-emit places
    that build_map owns — avoids a node-data conflict in dedup_nodes).
    infoboxes, overrides: passed through to resolve_parents (inert until Tasks 4-5).
    """
    nodes: list[Node] = []
    edges: list[Edge] = []

    # --- backbone (owner-authored geographic frame) ---
    for p in backbone["places"]:
        data = {"place_type": p["place_type"]}
        for k in ("ruled_by", "faction", "members"):
            if p.get(k) not in (None, ""):
                data[k] = p[k]
        nodes.append(Node(id=p["id"], kind=NodeKind.PLACE, name=p["name"], slug=p["id"].split(":", 1)[1], data=data))
        if p.get("located_in"):
            edges.append(Edge(id=_edge_id(p["id"], "located_in"), type=EdgeType.LOCATED_IN,
                              src=p["id"], dst=p["located_in"], cond_group=None, data={}))
        se = p.get("same_entity")
        if se and se in region_ids:
            edges.append(Edge(id=_edge_id(p["id"], "same_entity"), type=EdgeType.SAME_ENTITY,
                              src=p["id"], dst=se, cond_group=None, data={}))

    # --- content ingest (filtered, typed, parented via resolve_parents) ---
    kept, parent_map, _signals = resolve_parents(backbone, snapshot, extra_seen, infoboxes, overrides)
    fpts, mbrs = set(snapshot["free_to_play"]), set(snapshot["members"])
    for title, place_type, content_kind, pid in kept:
        data = {"place_type": place_type, "content_kind": content_kind}
        m = members_of(title, fpts, mbrs)
        if m is not None:
            data["members"] = m
        nodes.append(Node(id=pid, kind=NodeKind.PLACE, name=title, slug=pid.split(":", 1)[1], data=data))
        edges.append(Edge(id=_edge_id(pid, "located_in"), type=EdgeType.LOCATED_IN,
                          src=pid, dst=parent_map[pid], cond_group=None, data={}))

    return nodes, edges, {}
