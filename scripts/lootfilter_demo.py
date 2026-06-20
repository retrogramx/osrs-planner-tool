#!/usr/bin/env python3
"""Regenerate outputs/gilded-tome-iron.rs2f (generic) + print a tailored example."""
import json, os
from osrs_planner.lootfilter.generate import write_filter, generate_filter, load_clog_ids
from osrs_planner.account.state import build_account_state
from osrs_planner.account.temple import parse_temple_clog

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, "outputs", "gilded-tome-iron.rs2f")
FIX = os.path.join(REPO, "tests", "account", "fixtures")

def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    write_filter(OUT)
    g = generate_filter()
    print(f"generic: {OUT} | bytes {len(g)} | rules {g.count('rule (')}")
    obtained = parse_temple_clog(json.load(open(os.path.join(FIX, "sample_temple.json"), encoding="utf-8")))["obtained"]
    st = build_account_state("ironman", bank_tsv=open(os.path.join(FIX, "sample_bank.tsv"), encoding="utf-8").read(), clog_obtained=obtained)
    t = generate_filter(account_state=st)
    miss = len(set(load_clog_ids()) - {int(k.split(':')[1]) for k in st.clog_obtained})
    print(f"tailored: bytes {len(t)} | has tailoring module: {'module:tailoring' in t} | missing-clog slots beamed: {miss}")

if __name__ == "__main__":
    main()
