"""kg_ingest — deterministic transforms turning committed data/*.json into the
serialized KG (kg/nodes.json, kg/edges.json, kg/condition_groups.json).

Builders are pure functions ((domain records) -> (nodes, edges, condition_groups));
assemble.py merges them, re-keys to stable global ids (§6.6), dedups nodes, writes kg/*.json.
"""
