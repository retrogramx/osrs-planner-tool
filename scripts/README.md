# scripts/

Standalone, runnable developer scripts (demos and eyeball tools). These are **not**
part of the app or the test suite — they exist to *see* the engine work. Run them
from the repo root so relative paths resolve.

| Script | What it does |
|--------|--------------|
| `demo_showcase.py` | Narrative demo of the deterministic engine reasoning over the **real committed KG** (`kg/*.json` via `JsonKGStore`): the Dragon scimitar journey, the "you can wield it but your quest log is inconsistent" case, the Barrows-gloves mountain, account-type divergence (main vs ironman/UIM), the Voidwaker 3-component build, and full Infinity. Verdicts are computed live. |
| `demo_connective.py` | Showcase of the **connective vertical** (slices 6-7) over the real committed KG: "where can I buy a battlestaff and can MY account?" (the place▸npc▸shop▸item spine + the account-aware three-valued evaluator across fresh/mid-game/unsynced accounts), Lowe's exact Storeline stock, reverse acquisition (item → shops), and an item-facet coda (variants/charges/degradation/bonuses). |
| `scenario_runner.py` | Older engine-behavior aid that builds its **own** small, wiki-verified in-memory KG fixture (does not read `kg/*.json`) to exercise quest/diary 3-state gates and prerequisite chains. Self-contained; useful for probing engine semantics in isolation. |

Run:

```bash
./venv/bin/python scripts/demo_showcase.py
./venv/bin/python scripts/demo_connective.py
./venv/bin/python scripts/scenario_runner.py
```

Captured output lands in [`../outputs/`](../outputs/).
