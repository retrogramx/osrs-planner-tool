import ast, os
PKG = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "src", "osrs_planner", "account")
FORBIDDEN = ("osrs_planner.income", "osrs_planner.cost.overlay", "osrs_planner.cost.routing",
             "osrs_planner.cost.channels", "osrs_planner.cost.cards", "osrs_planner.cost.currency")

def test_account_imports_no_overlay_logic():
    offenders = []
    for fn in os.listdir(PKG):
        if not fn.endswith(".py"):
            continue
        tree = ast.parse(open(os.path.join(PKG, fn), encoding="utf-8").read())
        for node in ast.walk(tree):
            mods = ([a.name for a in node.names] if isinstance(node, ast.Import)
                    else [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for m in mods:
                if any(f in (m or "") for f in FORBIDDEN):
                    offenders.append(f"{fn}: {m}")
    assert not offenders, f"account/ imports forbidden overlay logic: {offenders}"
