"""One-way boundary: income may import engine; engine must NOT import income."""
from __future__ import annotations

import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENGINE_DIR = os.path.join(REPO, "src", "osrs_planner", "engine")


def test_engine_source_does_not_reference_income():
    offenders = []
    for root, _dirs, files in os.walk(ENGINE_DIR):
        if "__pycache__" in root:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = os.path.join(root, fn)
            with open(p, encoding="utf-8") as f:
                if "osrs_planner.income" in f.read():
                    offenders.append(p)
    assert offenders == [], f"engine references income: {offenders}"


def test_importing_engine_does_not_load_income():
    # Purge engine+income modules, re-import engine FRESH, and assert the fresh
    # import pulled in NO income module. CRITICAL: a bare purge leaves the freshly
    # re-imported engine classes (e.g. engine.kg.model.ConditionAtom) as NEW class
    # objects whose identity differs from the ones every OTHER test (and the
    # importlib-loaded data/validate_kg.py + assemble.py) already hold -- so a later
    # isinstance(child, ConditionAtom) silently returns False and the kg_ingest
    # suite crashes (int(ConditionAtom)). Snapshot the affected sys.modules entries
    # and RESTORE them in a finally so this experiment never leaks corrupted module
    # identity into the rest of the session.
    saved = {
        m: sys.modules[m]
        for m in list(sys.modules)
        if m.startswith("osrs_planner.income") or m.startswith("osrs_planner.engine")
    }
    try:
        for m in saved:
            del sys.modules[m]
        import osrs_planner.engine  # noqa: F401
        leaked = [m for m in sys.modules if m.startswith("osrs_planner.income")]
        assert leaked == [], f"importing engine pulled in income modules: {leaked}"
    finally:
        # drop anything the fresh import added, then restore the originals so the
        # canonical (already-referenced) module/class objects are authoritative again.
        for m in [
            m for m in list(sys.modules)
            if m.startswith("osrs_planner.income") or m.startswith("osrs_planner.engine")
        ]:
            del sys.modules[m]
        sys.modules.update(saved)
