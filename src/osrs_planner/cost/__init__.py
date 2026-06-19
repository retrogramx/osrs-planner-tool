"""Cost / currency overlay (account-type-aware acquisition pricing).

Sibling to ``osrs_planner.engine``. ONE-WAY BOUNDARY: ``cost`` imports from
``engine`` (AccountState, account_family); ``engine`` NEVER imports ``cost``,
and the knowledge graph (kg/*.json) stays cost-free. See
docs/superpowers/specs/2026-06-19-cost-currency-design.md.
"""
