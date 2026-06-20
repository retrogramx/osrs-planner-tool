#!/usr/bin/env python3
"""Demo account-state ingestion over the synthetic fixtures (or --bank / --player).
The user's real data is read, used, and NEVER written into the repo."""
import argparse, json, os
from osrs_planner.account.state import build_account_state
from osrs_planner.account.bank import bank_value
from osrs_planner.account.temple import fetch_collection_log, parse_temple_clog
from osrs_planner.cost.prices import SnapshotPriceProvider
from osrs_planner.engine.state import account_family

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(REPO, "tests", "account", "fixtures")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bank")     # path to a Bank Memory TSV export
    ap.add_argument("--player")   # OSRS name for the live Temple clog
    ap.add_argument("--mode", default="ironman")
    ns = ap.parse_args()

    bank_tsv = (open(ns.bank, encoding="utf-8").read() if ns.bank
                else open(os.path.join(FIX, "sample_bank.tsv"), encoding="utf-8").read())
    # both paths normalise to the obtained SET: live fetch, or parse the fixture payload
    clog = (fetch_collection_log(ns.player) if ns.player
            else parse_temple_clog(json.load(open(os.path.join(FIX, "sample_temple.json"), encoding="utf-8"))))
    obtained = clog["obtained"]

    state = build_account_state(ns.mode, bank_tsv=bank_tsv, clog_obtained=obtained)

    provider = SnapshotPriceProvider.from_file(os.path.join(REPO, "data", "ge_prices.json"))
    val = bank_value(state.counts, provider, account_family(ns.mode))
    print(f"mode={ns.mode} | owned items={len(state.counts)} | clog obtained={len(state.clog_obtained)}")
    print(f"  iron-realizable (coins+HA): {val['iron_realizable']:,}  | GE value: {val['ge_value']:,}"
          f"  | unpriced: {val['unpriced_count']}")

if __name__ == "__main__":
    main()
