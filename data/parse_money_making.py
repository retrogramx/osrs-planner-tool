#!/usr/bin/env python3
"""Deterministic parser for the OSRS Wiki money-making-guide Bucket API data.

Reads the raw Bucket API response (data/raw/money_making_bucket_full.json) and
normalizes each row into a stable record shape, writing the array to
data/money_making.json.

Source: OSRS Wiki Bucket API (action=bucket) — bucket('money_making_guide')
Content licensed CC BY-NC-SA 3.0.

No heuristics / no inference: every field is taken verbatim from the API.
The original inner 'json' blob is preserved as raw_json so nothing is lost.
"""
import json
import os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
RAW_PATH = os.path.join(HERE, "raw", "money_making_bucket_full.json")
OUT_PATH = os.path.join(HERE, "money_making.json")

SOURCE_URL = (
    "https://oldschool.runescape.wiki/api.php?action=bucket&format=json&query="
    "bucket('money_making_guide').select('page_name','value','recurring','json')"
    ".limit(5000).run()"
)


def to_number(v):
    """Convert the API 'value' string to int when whole, else float. Deterministic."""
    if v is None or v == "":
        return None
    f = float(v)
    return int(f) if f.is_integer() else f


def normalize(row):
    """Map a single Bucket row -> normalized record. Verbatim, no inference."""
    inner = json.loads(row["json"])

    # method: the human-readable guide name (page_name with the wiki prefix stripped)
    page_name = row["page_name"]
    method = page_name.split("Money making guide/", 1)[-1]

    # requirements: the wiki's own requirement fields, taken verbatim from the
    # inner json. No parsing of the wikitext — kept exactly as the API returns it.
    requirements = {
        "members": inner.get("members"),
        "skill": inner.get("skill"),
        "quest": inner.get("quest"),
        "other": inner.get("other"),
    }
    # drop keys the API did not provide for this row (keep members even if False)
    requirements = {
        k: v for k, v in requirements.items() if v is not None or k == "members"
    }

    record = {
        "method": method,
        "page_name": page_name,
        "gp_value": to_number(row.get("value")),
        # 'recurring' is a flag column on the Bucket: present (empty string) iff
        # the method is recurring. Mirror that as a boolean, and surface the
        # inner cadence string when available.
        "recurring": "recurring" in row,
        "recurrence": inner.get("recurrence"),
        "category": inner.get("category"),
        "skill_category": inner.get("skillcategory"),
        "intensity": inner.get("intensity"),
        "is_per_kill": inner.get("isperkill"),
        "members": inner.get("members"),
        "requirements": requirements,
        "inputs": inner.get("inputs", []),
        "outputs": inner.get("outputs", []),
        "prices": inner.get("prices"),
        # original inner json blob, fully preserved so nothing is lost
        "raw_json": inner,
    }
    return record


def main():
    with open(RAW_PATH) as f:
        data = json.load(f)
    rows = data["bucket"]

    records = [normalize(r) for r in rows]

    out = {
        "_provenance": {
            "source": "OSRS Wiki — Money making guide (Bucket API)",
            "source_url": SOURCE_URL,
            "bucket_query": data.get("bucketQuery"),
            "accessed": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "license": "CC BY-NC-SA 3.0 (oldschool.runescape.wiki)",
            "record_count": len(records),
        },
        "money_making": records,
    }

    with open(OUT_PATH, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("records:", len(records))
    print("recurring:", sum(1 for r in records if r["recurring"]))
    print("wrote:", OUT_PATH)


if __name__ == "__main__":
    main()
