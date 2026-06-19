# src/osrs_planner/cost/overlay.py
"""expand_for_account -- the public cost overlay entry (design spec §5).

Resolves a goal/item id for the account's FAMILY into a CostCard: all viable
routes for that family + a by_gold ranking. account-type divergence emerges
from price_routes' family filter, not from branching here. KG is optional in
v1; when given, notes carries the downstream-goal strategic-timing hook and a
composite goal (Voidwaker from 3 components; full Infinity = 5 pieces) is
resolved through the KG to its item needs, priced, and rolled up.
"""
from __future__ import annotations

from osrs_planner.cost.cards import CostCard, Route, rank_by_gold, roll_up_gold_status
from osrs_planner.cost.channels import ChannelRecord
from osrs_planner.cost.prices import PriceProvider
from osrs_planner.cost.routing import price_routes
from osrs_planner.engine.kg.model import AtomType, EdgeType, Op
from osrs_planner.engine.state import AccountState, account_family


def _requires_group(kg, node_id: str) -> int | None:
    """The cond_group of node_id's REQUIRES edge (mirrors store.composition_of)."""
    for e in kg.edges:
        if e.type is EdgeType.REQUIRES and e.src == node_id and e.cond_group is not None:
            return e.cond_group
    return None


def _item_needs(kg, group_id: int, _seen=None) -> list[tuple[str, int]]:
    """Flatten a group to the CONJUNCTIVE (AND) set of (item_id, qty) needs.

    item atoms -> (ref_node, qty or 1); gear_loadout atoms -> expand via
    composition_of(ref_node); nested sub-groups (int children) recurse. v1
    assumes every contributing group is conjunctive: all collected needs are
    required together. An OR group that would contribute item/gear_loadout
    needs (only ONE branch is actually required) would overstate an assemble
    cost, so it raises NotImplementedError rather than over-collect. OR groups
    that contribute no item/gear_loadout needs -- e.g. the ironman wrappers
    OR(account_type=='main', skill_req) -- are unaffected and collect nothing.
    """
    _seen = _seen if _seen is not None else set()
    if group_id in _seen:
        return []
    _seen.add(group_id)
    needs: list[tuple[str, int]] = []
    for child in kg.children_of(group_id):
        if isinstance(child, int):
            needs.extend(_item_needs(kg, child, _seen))
        elif child.atom_type is AtomType.ITEM:
            needs.append((child.ref_node, child.qty or 1))
        elif child.atom_type is AtomType.GEAR_LOADOUT:
            needs.extend(_item_needs(kg, kg.composition_of(child.ref_node), _seen))
    if needs and kg.groups[group_id].op is Op.OR:
        raise NotImplementedError(
            f"OR-of-items composites are not supported in v1: group {group_id} "
            "(op=OR) contributes item/gear_loadout needs; only one branch is "
            "required, so collecting all would overstate the assemble cost."
        )
    return needs


def _downstream_goals(kg, item_id: str) -> list[str]:
    """Goal ids whose requires-tree references item_id (strategic-timing hook)."""
    out: list[str] = []
    for node in kg.nodes.values():
        gid = node.id
        if gid == item_id:
            continue
        grp = _requires_group(kg, gid)
        if grp is None:
            continue
        if item_id in {iid for iid, _ in _item_needs(kg, grp)}:
            out.append(gid)
    return sorted(set(out))


def expand_for_account(
    goal_id: str,
    state: AccountState,
    provider: PriceProvider,
    index: dict[str, list[ChannelRecord]],
    kg=None,
) -> CostCard:
    family = account_family(state.mode)
    name = _resolve_name(goal_id, kg)

    grp = _requires_group(kg, goal_id) if kg is not None else None
    needs = _item_needs(kg, grp) if grp is not None else []

    if needs:
        # Composite: resolve to item needs, price each, roll up.
        component_routes: list[Route] = []
        total = 0
        all_known = True
        for item_id, qty in needs:
            sub = price_routes(item_id, family, provider, index)
            # Single source of truth for the unavailable-last ordering.
            chosen = sub[rank_by_gold(sub)[0]] if sub else Route(
                channel="none", currency="currency:coins", gold_cost=None,
                gold_status="unavailable", account_allowed=False, source="kg",
                notes=[f"no {family}-allowed route for {item_id}"],
            )
            component_routes.append(chosen)
            if chosen.gold_status == "known" and chosen.gold_cost is not None:
                total += chosen.gold_cost * qty
            else:
                all_known = False
        assemble = Route(
            channel="craft", currency="currency:coins",
            gold_cost=total if all_known else None,
            gold_status="known" if all_known else "unavailable",
            inputs=component_routes, account_allowed=True, source="kg-composition",
        )
        # plus any direct route for the assembled item itself (e.g. main GE).
        direct = price_routes(goal_id, family, provider, index) if goal_id.startswith("item:") else []
        routes = direct + [assemble]
        notes = _downstream_goals(kg, goal_id) if kg is not None else []
        return CostCard(
            item_id=goal_id, name=name, account_family=family, routes=routes,
            rankings={"by_gold": rank_by_gold(routes), "by_time": []},
            notes=notes, gold_status=roll_up_gold_status(routes),
        )

    if goal_id.startswith("item:"):
        routes = price_routes(goal_id, family, provider, index)
        notes = []
        if not routes:
            notes.append(f"No {family}-allowed acquisition channel for {goal_id}.")
        if kg is not None:
            notes.extend(_downstream_goals(kg, goal_id))
        return CostCard(
            item_id=goal_id, name=name, account_family=family, routes=routes,
            rankings={"by_gold": rank_by_gold(routes), "by_time": []},
            notes=notes, gold_status=roll_up_gold_status(routes),
        )

    raise NotImplementedError(f"goal {goal_id} has no item needs and is not an item: id")


def _resolve_name(goal_id: str, kg) -> str:
    if kg is not None:
        node = kg.node(goal_id)
        if node is not None:
            return node.name
    return goal_id
