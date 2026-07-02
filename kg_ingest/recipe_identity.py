"""Shared recipe-identity helpers: resolve a Bucket:recipe row to its intrinsic
payload, hash that payload to a stable, order-independent identity, and mint
readable slugs. Used by build_recipe_roster (registry lookup),
data/update_recipe_registry.py (seed/mint), and data/validate_kg.py. Recipe ids
derive from the identity via the committed data/recipe_slug_registry.json."""
from __future__ import annotations

import hashlib, html, json

from kg_ingest.ids import slugify, skill_id
from kg_ingest.builders.map_varrock import make_item_resolver  # noqa: F401 (re-export convenience)


def _as_list(v):
    return v if isinstance(v, list) else ([] if v in (None, "") else [v])


def _num(v):
    """Parse a quantity/xp/level string -> int (or float if fractional); None if non-numeric."""
    try:
        f = float(str(v))
    except (TypeError, ValueError):
        return None
    return int(f) if f == int(f) else f


def _facility_lookup(facility_nodes):
    """name / alias -> facility node id, from the committed facility roster."""
    lut: dict[str, str] = {}
    for n in facility_nodes:
        lut.setdefault(n.name, n.id)
        for a in (n.data or {}).get("aliases", []):
            lut.setdefault(a, n.id)
    return lut


def resolve_recipe_payload(row, resolve_item, fac_lut):
    """Bucket:recipe row -> resolved payload dict, or None if the output is unresolvable.
    resolve_item(name) -> 'item:<id>' | None; fac_lut: name -> 'facility:<..>' | None.
    Only resolved references are included (unresolvable materials/facilities skipped),
    matching what the graph carries — so identity hashes match between seed and build."""
    try:
        pj = json.loads(row.get("production_json") or "{}")
    except Exception:
        pj = {}
    out = pj.get("output")
    if not (isinstance(out, dict) and out.get("name")):
        return None
    out_dst = resolve_item(out["name"])
    if out_dst is None:
        return None
    out_name = html.unescape(out["name"].strip())
    subtxt = (out.get("subtxt") or "").strip()

    consumes = []
    for m in (pj.get("materials") or []):
        dst = resolve_item(m.get("name"))
        if dst is not None:
            consumes.append((dst, _num(m.get("quantity")) or 1, "material"))
    for tname in _as_list(row.get("uses_tool")):
        dst = resolve_item(tname)
        if dst is not None:
            consumes.append((dst, 1, "tool"))

    produces = [(out_dst, _num(out.get("quantity")) or 1)]

    facilities = []
    for fname in _as_list(row.get("uses_facility")):
        fid = fac_lut.get((fname or "").strip())
        if fid is not None:
            facilities.append(fid)

    atoms, xp = [], {}
    for s in (pj.get("skills") or []):
        nm = (s.get("name") or "").strip()
        lvl = _num(s.get("level"))
        if nm and lvl is not None and float(lvl) == int(lvl):
            atoms.append((skill_id(nm), int(lvl),
                          str(s.get("boostable", "")).strip().lower() == "yes"))
        ev = _num(s.get("experience"))
        if nm and ev is not None:
            xp[nm] = ev

    return {"page": row.get("page_name") or "", "out_name": out_name, "out_dst": out_dst,
            "subtxt": subtxt, "consumes": consumes, "produces": produces,
            "facilities": facilities, "atoms": atoms, "xp": xp,
            "ticks": _num(pj.get("ticks")),
            "members": pj["members"] if isinstance(pj.get("members"), bool) else None}


def recipe_identity_hash(payload) -> str:
    """Stable sha256 hex over the intrinsic identity: consumes (item/qty/role),
    produces (item/qty), facilities, skill-gates (skill/threshold), and slugified
    subtxt. Sorted => order-independent. Excludes xp/ticks/members (properties, not
    identity), and boostable (derivable from skill)."""
    ident = {
        "consumes": sorted(([c[0], c[1], c[2]] for c in payload["consumes"]),
                           key=lambda x: json.dumps(x, sort_keys=True)),
        "produces": sorted(([p[0], p[1]] for p in payload["produces"]),
                           key=lambda x: json.dumps(x, sort_keys=True)),
        "facilities": sorted(payload["facilities"]),
        "skills": sorted(([a[0], a[1]] for a in payload["atoms"]),
                         key=lambda x: json.dumps(x, sort_keys=True)),
        "subtxt": slugify(payload["subtxt"]) if payload["subtxt"] else "",
    }
    return hashlib.sha256(
        json.dumps(ident, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def mint_slug(out_name, subtxt, claimed) -> str:
    """Readable slug for a NEW recipe: slugify(output), + -slugify(subtxt) if subtxt,
    -k guarded against `claimed` (a set, mutated). Deterministic given call order."""
    base = f"{slugify(out_name)}-{slugify(subtxt)}" if subtxt else slugify(out_name)
    slug = base
    if slug in claimed:
        k = 2
        while f"{slug}-{k}" in claimed:
            k += 1
        slug = f"{slug}-{k}"
    claimed.add(slug)
    return slug


def is_method_suffixed(slug, out_name, subtxt) -> bool:
    """True iff `slug` is the method-suffixed form of out_name (base-<subtxt>[-k]).
    Reproduces the exact source_token `method=` annotation for byte-stability:
    the pre-registry builder emitted method= exactly when the slug carried the suffix."""
    if not subtxt:
        return False
    stem = f"{slugify(out_name)}-{slugify(subtxt)}"
    return slug == stem or slug.startswith(stem + "-")
