# data/_raid_scaling.py
"""CoX/ToB raid-scaling DISCLOSURE. dropsline gives a flat chest rate; the real
chance scales with points (CoX) / team size + mode (ToB). v1 attaches a disclosure
note to variants[]; the detailed formula is a v2 follow-up (like clue caskets)."""
from __future__ import annotations

_RAID_CHESTS = {"Ancient chest", "Monumental chest"}  # CoX, ToB (ToA -> apply_toa)

def apply_raid_scaling(record):
    if record.get("source") in _RAID_CHESTS:
        record = dict(record)
        record["variants"] = list(record.get("variants", [])) + [
            {"condition": "scales with points/team size", "drop_rate": None, "drop_rate_raw": ""}
        ]
    return record
