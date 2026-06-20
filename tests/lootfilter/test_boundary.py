import ast, os
PKG = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "src", "osrs_planner", "lootfilter")
FORBIDDEN = ("osrs_planner.engine", "osrs_planner.cost", "osrs_planner.income")

def test_lootfilter_imports_no_overlay():
    bad = []
    for fn in os.listdir(PKG):
        if not fn.endswith(".py"): continue
        for node in ast.walk(ast.parse(open(os.path.join(PKG, fn), encoding="utf-8").read())):
            mods = ([a.name for a in node.names] if isinstance(node, ast.Import)
                    else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for m in mods:
                if any(b in (m or "") for b in FORBIDDEN): bad.append(f"{fn}: {m}")
    assert not bad, f"forbidden overlay import: {bad}"
