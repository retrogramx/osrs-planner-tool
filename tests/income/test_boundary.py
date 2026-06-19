"""One-way dependency: engine must never import income."""
from __future__ import annotations

import ast
import os

ENGINE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "src", "osrs_planner", "engine",
)


def _imports(path: str) -> set[str]:
    with open(path, encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=path)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module)
    return names


def test_engine_never_imports_income():
    offenders = []
    for root, _dirs, files in os.walk(ENGINE_DIR):
        if "__pycache__" in root:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(root, fn)
            for mod in _imports(path):
                if "osrs_planner.income" in mod or mod == "income":
                    offenders.append(f"{path}: {mod}")
    assert not offenders, f"engine imports income: {offenders}"
