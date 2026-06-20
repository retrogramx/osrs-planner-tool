"""Money-making / income overlay (account-type-aware gold realization).

Sibling to ``osrs_planner.engine`` and ``osrs_planner.cost``. ONE-WAY
BOUNDARY: ``income`` imports from ``engine`` (AccountState, account_family,
the condition-evaluator) and reuses ``cost.prices.PriceProvider``; ``engine``
NEVER imports ``income`` and the knowledge graph (kg/*.json) stays
income-free. See docs/superpowers/specs/2026-06-19-income-design.md.
"""
