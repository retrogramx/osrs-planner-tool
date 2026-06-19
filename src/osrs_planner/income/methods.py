# src/osrs_planner/income/methods.py
"""Normalized money-making method model (income design §3).

One ``MethodRecord`` (frozen pydantic) unifies the two source datasets
(data/money_making.json: 377 main, HTML requirements; data/ironman_money_making.json:
49 iron, native structured requirements). gp/hr is COMPUTED at query time from
``outputs x PriceProvider`` (realize.py) -- the stored ``gp_hr`` is NOT trusted.

IDs are KG-style strings: methods ``method:<slug>``, items ``item:<n>``,
quests ``quest:<slug>``, skills ``skill:<name>``.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Flow(BaseModel):
    """One output or input stream of a method, per hour.

    ``item_id`` is a KG-style ``"item:<n>"`` string, or ``None`` for a pure
    coins flow (``is_coins=True``). A non-coin flow with ``item_id=None`` is an
    un-resolvable / aggregate stream (e.g. the "Gem drop table" pseudo-output)
    that realize.py treats as unpriceable. ``qty_per_hour`` is ``None`` when the
    rate is not modelled (realize.py surfaces that as ``unknown``, never 0).
    """

    item_id: Optional[str] = None
    is_coins: bool = False
    qty_per_hour: Optional[float] = None


class Requirements(BaseModel):
    """Structured requirements feeding the engine condition-evaluator (filter.py).

    ``skills`` maps a KG ``"skill:<name>"`` id to a required level; ``quests``
    is a list of ``"quest:<slug>"`` ids; ``items`` is a list of ``"item:<n>"``
    ids (item gates stay UNKNOWN until bank data -- absence != zero).
    """

    skills: dict[str, int] = Field(default_factory=dict)
    quests: list[str] = Field(default_factory=list)
    items: list[str] = Field(default_factory=list)


class MethodRecord(BaseModel, frozen=True):
    """A single money-making method, normalized across both datasets (§3).

    Frozen: loaded once and shared across requests (like the KG static value
    types). ``stage`` is a SOFT hint only -- the requirement check (filter.py),
    not this tag, decides doability. ``processing_dependent`` flags methods whose
    iron income needs a processing chain not yet covered, so v1 marks them
    ``gp_hr_status=unknown`` rather than under-counting.
    """

    id: str
    name: str
    category: str
    members: bool
    audience: str
    requires_ge: bool
    iron_eligible: bool
    realization_channel: str
    outputs: list[Flow] = Field(default_factory=list)
    inputs: list[Flow] = Field(default_factory=list)
    requirements: Requirements = Field(default_factory=Requirements)
    stage: Optional[str] = None
    tags: dict = Field(default_factory=dict)
    processing_dependent: bool = False
    net_sign: Literal["earner", "sink"]
    source: str
    url: str
    accessed_at: str


# Pseudo-"skills" in skill_requirements_html that are NOT KG skill nodes
# (combat level is derived; quest points handled by the engine elsewhere).
_NON_SKILL_PSEUDO = frozenset({"combat level", "quest points"})


def _slug(name: str) -> str:
    """A wiki page name -> a KG slug fragment.

    Lowercase; apostrophes dropped; every run of non-alphanumerics -> a single
    hyphen; trim leading/trailing hyphens. "Fairytale II - Cure a Queen" ->
    "fairytale-ii-cure-a-queen".
    """
    s = name.strip().lower().replace("'", "")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


_WIKILINK = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
# data-skill, then OPTIONALLY a data-level somewhere later in the same tag.
_SCP_SPAN = re.compile(r'data-skill="([^"]+)"(?:[^>]*?data-level="([^"]+)")?')
# Leading integer of a data-level value. Real money_making data carries free-form
# levels ("68 or 85 (recommended)", "43+ or 77+", "94 Recommended", "5-90"); take
# the FIRST integer as the conservative lower-bound gate. A value with no leading
# integer ("Decent", "High agility") yields no match -> treated as a level-less
# recommendation and dropped (same as a span with no data-level at all).
_LEADING_INT = re.compile(r"\d[\d,]*")


def parse_requirements_html(skill_html, quest_html=None) -> Requirements:
    """Parse the main dataset's prose requirement fields into Requirements.

    ``skill_html`` = a money_making.json ``skill_requirements_html`` value.
    Each span with a numeric ``data-level`` becomes a ``skill:<name>`` gate
    (trailing ``+`` stripped; pseudo-skills combat-level/quest-points dropped; a
    span with no level is a recommendation, dropped). ``quest_html`` = the
    ``quest`` prose field; EVERY ``[[Quest]]`` wikilink becomes a ``quest:<slug>``
    gate (v1 is conservative -- a "recommended" quest over-gates to future_gated,
    which is safe; under-gating is not, spec §11).
    """
    skills: dict[str, int] = {}
    if skill_html:
        for m in _SCP_SPAN.finditer(skill_html):
            raw_skill = m.group(1).strip()
            raw_level = m.group(2)
            if raw_skill.lower() in _NON_SKILL_PSEUDO:
                continue
            if not raw_level:
                continue  # no numeric gate -> recommendation, not a requirement
            lm = _LEADING_INT.search(raw_level)
            if not lm:
                continue  # free-form level with no number ("Decent") -> drop
            level = int(lm.group(0).replace(",", ""))
            skills[f"skill:{_slug(raw_skill)}"] = level

    quests: list[str] = []
    if quest_html and quest_html.strip().lower() != "none":
        seen: set[str] = set()
        for m in _WIKILINK.finditer(quest_html):
            qid = f"quest:{_slug(m.group(1))}"
            if qid not in seen:
                seen.add(qid)
                quests.append(qid)

    return Requirements(skills=skills, quests=quests, items=[])


# gerund verbs stripped from an activity to form a dedupe key (so the iron
# "Green dragons (...)" matches the main "Killing green dragons").
_ACTIVITY_VERBS = (
    "killing", "crafting", "collecting", "pickpocketing", "mining",
    "fishing", "making", "cutting", "smithing", "hunting", "catching",
    "picking", "selling", "processing", "stealing", "blast",
)


def _activity_key(text: str) -> str:
    """Normalize a method name/activity to a LOOSE dedupe key for IRON merging.

    Strips ``[[wikilinks]]``, lowercases, drops a leading gerund verb and any
    trailing ``(...)`` parenthetical, collapses non-alphanumerics. So both
    "Killing green dragons" and "Green dragons (lance setup)" -> "green dragons".

    This key is intentionally lossy (gear/mode variants collapse together), so it
    is used ONLY to find which MAIN an iron record should fold onto -- never to
    dedupe mains against each other (mains key by their full ``_slug(name)`` so
    "Killing green dragons (Myths Guild)" stays distinct from the base; see
    ``load_methods``).
    """
    s = _WIKILINK.sub(r"\1", text or "")
    s = re.sub(r"\([^)]*\)", " ", s)  # drop parentheticals
    s = re.sub(r"[^a-z0-9 ]+", " ", s.lower())
    words = s.split()
    if words and words[0] in _ACTIVITY_VERBS:
        words = words[1:]
    return " ".join(words).strip()


# A name ending in a "(...)" parenthetical is a gear/mode VARIANT, not the base
# method. The canonical iron-merge target is the base (no trailing parenthetical);
# e.g. among {"Killing green dragons", "...(Myths Guild)", "...(Ironman)"} the base
# "Killing green dragons" wins. When EVERY candidate is parenthesised (e.g. the
# Hallowed Sepulchre floors), the loop falls back to dataset order (first).
_TRAILING_PAREN = re.compile(r"\([^)]*\)\s*$")


def _has_trailing_paren(name: str) -> bool:
    return bool(_TRAILING_PAREN.search(name.strip()))


def _load_envelope(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)["records"]


@lru_cache(maxsize=None)
def _name_index(data_dir: str) -> dict[str, int]:
    """item name (lowercased) -> deterministic item_id.

    item_dictionary.json names are NOT unique (e.g. "Nature rune" -> 561/11693).
    Resolve deterministically: prefer ``is_canonical``; among equal-canonical,
    lowest item_id. Cached per data_dir (15496 rows).
    """
    recs = _load_envelope(os.path.join(data_dir, "item_dictionary.json"))
    best: dict[str, tuple[int, int]] = {}  # name -> (canonical_rank, item_id)
    for r in recs:
        nm = (r.get("name") or "").strip().lower()
        if not nm:
            continue
        iid = r["item_id"]
        rank = 0 if r.get("is_canonical") else 1
        cur = best.get(nm)
        if cur is None or (rank, iid) < cur:
            best[nm] = (rank, iid)
    return {nm: v[1] for nm, v in best.items()}


def _resolve_item_id(name: str, name_idx: dict[str, int]) -> str | None:
    iid = name_idx.get((name or "").strip().lower())
    return f"item:{iid}" if iid is not None else None


def _qty_per_hour(flow: dict, kph) -> float:
    """Per-hour quantity for a main-dataset flow.

    ``isph`` flows are already per-hour. For a per-kill activity (kph set) a
    non-``isph`` flow is per-kill -> multiply by kph. Falls back to raw qty.
    """
    qty = float(flow.get("qty") or 0)
    if flow.get("isph"):
        return qty
    if kph:
        return qty * float(kph)
    return qty


def _flow_from_main(flow: dict, kph, name_idx: dict[str, int]) -> Flow:
    qph = _qty_per_hour(flow, kph)
    if flow.get("is_coins"):
        return Flow(item_id=None, is_coins=True, qty_per_hour=qph)
    item_id = None if flow.get("is_aggregate") else _resolve_item_id(flow.get("name", ""), name_idx)
    return Flow(item_id=item_id, is_coins=False, qty_per_hour=qph)


def _net_sign(outputs: list[Flow], inputs: list[Flow]) -> str:
    """v1 naive: a record with at least one value-bearing output is an earner;
    one with none is a sink. (REFINED at load in T8 with face-value compare +
    a curated sink set; recomputed precisely in realize.py per family.)"""
    has_out = any(o.is_coins or o.item_id is not None for o in outputs)
    return "earner" if has_out else "sink"


def _from_main(rec: dict, name_idx: dict[str, int]) -> MethodRecord:
    kph = rec.get("kph")
    outputs = [_flow_from_main(o, kph, name_idx) for o in (rec.get("outputs") or [])]
    inputs = [_flow_from_main(i, kph, name_idx) for i in (rec.get("inputs") or [])]
    reqs = parse_requirements_html(rec.get("skill_requirements_html"), quest_html=rec.get("quest"))
    return MethodRecord(
        id=f"method:{_slug(rec['name'])}",
        name=rec["name"],
        category=rec.get("category") or "Uncategorized",
        members=bool(rec.get("members")),
        audience=rec.get("audience") or "main",
        requires_ge=bool(rec.get("requires_ge")),
        iron_eligible=bool(rec.get("iron_eligible")),
        realization_channel=rec.get("realization_channel") or "unknown",
        outputs=outputs,
        inputs=inputs,
        requirements=reqs,
        stage=None,
        tags={"intensity": rec.get("intensity"), "wilderness": bool(rec.get("wilderness"))},
        processing_dependent=False,
        net_sign=_net_sign(outputs, inputs),
        source="OSRS Wiki money_making_guide",
        url=rec.get("url") or "https://oldschool.runescape.wiki/w/Money_making_guide",
        accessed_at="2026-06-18T04:06:25Z",
    )


# A trailing "(...)" prose suffix on an iron quest ref, e.g.
# "A Kingdom Divided (for thralls)" -> stripped before slugging (DR-4) so the
# loader and the validator's quest_slug() AGREE on "quest:a-kingdom-divided".
_PAREN_SUFFIX = re.compile(r"\s*\([^)]*\)\s*$")
# A DIARY-shaped requirement string is NOT a quest gate (DR-3): route it to
# advisory tags, never requirements.quests. Matches "Easy Ardougne Diary (...)",
# "Ardougne Diary medium tasks", etc.
_DIARY_RE = re.compile(r"diary", re.IGNORECASE)


def _iron_requirements(rec: dict) -> tuple[Requirements, list[str]]:
    """Map the iron dataset's NATIVE requirements into (Requirements, advisory_reqs).

    Iron ``requirements.skills`` keys are display names ("Magic") -> ``skill:<slug>``;
    a NON-int threshold (e.g. {"Combat":"High"}) is skipped. Quests -> ``quest:<slug>``
    AFTER stripping a trailing "(...)" parenthetical (DR-4) so the loader matches the
    validator's slugging (``A Kingdom Divided (for thralls)`` -> ``quest:a-kingdom-divided``).
    A DIARY-shaped quest entry (matches /diary/i, e.g. "Easy Ardougne Diary (...)",
    "Ardougne Diary medium tasks") is NOT a quest gate (DR-3) — it is returned in the
    ``advisory_reqs`` list for tags, never ``requirements.quests``. ``items`` are mostly
    prose ("fire/nature runes ...") -> NOT emitted as item:<n> gates unless already an
    ``item:<n>`` literal (the validator's id-resolution stays clean; prose item notes
    go to tags, a disclosed v1 residual).
    """
    req = rec.get("requirements") or {}
    skills = {
        f"skill:{_slug(k)}": int(v)
        for k, v in (req.get("skills") or {}).items()
        if isinstance(v, int)
    }
    quests: list[str] = []
    advisory: list[str] = []
    for q in (req.get("quests") or []):
        if _DIARY_RE.search(q):
            advisory.append(q)  # a DIARY, not a quest -> advisory, never a gate
            continue
        stripped = _PAREN_SUFFIX.sub("", q).strip()  # DR-4: strip "(...)" before slug
        quests.append(f"quest:{_slug(stripped)}")
    items = [it for it in (req.get("items") or []) if isinstance(it, str) and it.startswith("item:")]
    return Requirements(skills=skills, quests=quests, items=items), advisory


def _from_iron(rec: dict) -> MethodRecord:
    name = rec["method"]
    reqs, advisory_reqs = _iron_requirements(rec)
    out = rec.get("outputs") or {}
    gold = out.get("gold")
    outputs: list[Flow] = []
    if isinstance(gold, (int, float)):
        outputs.append(Flow(item_id=None, is_coins=True, qty_per_hour=float(gold)))
    prose_items = [
        it for it in (rec.get("requirements", {}).get("items") or [])
        if isinstance(it, str) and not it.startswith("item:")
    ]
    return MethodRecord(
        id=f"method:{_slug(name)}",
        name=name,
        category=rec.get("realization_channel") or "Ironman",
        members=True,
        audience=rec.get("audience") or "ironman",
        requires_ge=bool(rec.get("requires_ge")),
        iron_eligible=not bool(rec.get("requires_ge")),
        realization_channel=rec.get("realization_channel") or "coins",
        outputs=outputs,
        inputs=[],
        requirements=reqs,
        stage=rec.get("stage"),
        tags={
            "risk": rec.get("risk"),
            "stage_hint": rec.get("stage"),
            "iron_item_notes": prose_items,
            # DR-3: DIARY-shaped reqs routed here, NOT to requirements.quests.
            "advisory_reqs": advisory_reqs,
        },
        # an iron method whose outputs are prose-only (no numeric gold) needs a
        # realization chain v1 hasn't covered -> mark honestly.
        processing_dependent=not outputs,
        net_sign="earner",
        source="OSRS Wiki Ironman_money_making_guide",
        url="https://oldschool.runescape.wiki/w/Ironman_money_making_guide",
        accessed_at="2026-06-17T00:00:00Z",
    )


def _merge_requirements(main_req: Requirements, iron_req: Requirements) -> Requirements:
    """UNION the merged record's requirements (DR-1) — never overwrite.

    The main record carries the HTML-parsed ``skills`` (e.g. green dragons
    ``skill:prayer=25`` + ``skill:ranged=60``); the iron record carries native
    structured ``quests``/``items`` (e.g. the ``quest:a-kingdom-divided`` gate).
    Overwriting the whole Requirements with the iron one would WIPE the parsed
    main skills. Merge field-wise instead:
      - skills: main ∪ iron, with the MAIN HTML parse authoritative on a key
        collision (the main parse is the canonical skill source) and iron adding
        any skill main lacked.
      - quests: ordered union (main first, then iron refs not already present).
      - items: ordered union likewise.
    """
    # main skills authoritative on collision; iron adds any skill main lacked.
    skills = {**iron_req.skills, **main_req.skills}
    quests = list(main_req.quests)
    for q in iron_req.quests:
        if q not in quests:
            quests.append(q)
    items = list(main_req.items)
    for it in iron_req.items:
        if it not in items:
            items.append(it)
    return Requirements(skills=skills, quests=quests, items=items)


def load_methods(data_dir: str) -> list[MethodRecord]:
    """Normalize data/money_making.json + data/ironman_money_making.json into
    one list of MethodRecord.

    Dedupe design (corrected — the original over-collapsed mains by the loose
    activity key, which merged distinct gear/mode variants and dropped the base
    method; that defect was found during execution):

    1. **Mains key by the FULL ``_slug(name)``.** All 377 main records stay
       distinct — gear/mode variants (Vorkath blowpipe/dhcb/dhl, CoX Normal/
       Challenge, the three green-dragons mains) remain separate methods. There
       is NO main-vs-main merging.
    2. **Iron records merge onto the CANONICAL base-main.** For each iron record,
       compute its looser ``_activity_key``; among the mains sharing that key,
       pick the canonical one (the base name with NO trailing ``(...)``
       parenthetical; tie-break by dataset order when every candidate is
       parenthesised). Fold the iron record onto that main: keep the main's
       structured outputs/inputs (so realize.py values per family) and **UNION
       requirements field-wise** (DR-1) — the main's HTML-parsed ``skills`` are
       KEPT and the iron's ``quests``/``items`` are ADDED; the Requirements object
       is NEVER wholesale-replaced (that would wipe the parsed skill gates). Iron
       ``stage`` and non-empty iron ``tags`` also fold in.
    3. **No matching main -> the iron record is added as its own iron-only
       MethodRecord** (its activity has no main counterpart).

    Deterministic. On the committed data this yields 377 main + 36 iron-only = 413
    (13 iron records merge onto a canonical main); ``test_counts_are_sane``
    asserts that exact total.
    """
    name_idx = _name_index(data_dir)
    main = [_from_main(r, name_idx) for r in _load_envelope(os.path.join(data_dir, "money_making.json"))]
    iron = [_from_iron(r) for r in _load_envelope(os.path.join(data_dir, "ironman_money_making.json"))]

    # Mains keyed by full slug (all distinct); preserve dataset order.
    by_id: dict[str, MethodRecord] = {}
    order: list[str] = []
    for m in main:
        if m.id not in by_id:
            order.append(m.id)
        by_id[m.id] = m

    # Index mains by their looser activity key (in dataset order) for iron merge.
    key_to_mains: dict[str, list[MethodRecord]] = {}
    for m in main:
        key_to_mains.setdefault(_activity_key(m.name), []).append(m)

    for im in iron:
        candidates = key_to_mains.get(_activity_key(im.name))
        if candidates:
            # canonical = base name (no trailing parenthetical); else first by order
            canon = next(
                (c for c in candidates if not _has_trailing_paren(c.name)),
                candidates[0],
            )
            base = by_id[canon.id]  # MERGE: keep main outputs/inputs; UNION reqs
            by_id[canon.id] = base.model_copy(update={
                "requirements": _merge_requirements(base.requirements, im.requirements),
                "stage": im.stage or base.stage,
                "tags": {**base.tags, **{kk: vv for kk, vv in im.tags.items() if vv}},
            })
        else:
            # no main shares this activity -> add the iron record on its own
            if im.id not in by_id:
                order.append(im.id)
            by_id[im.id] = im
    return [by_id[k] for k in order]


def build_method_index(methods: list[MethodRecord]) -> list[MethodRecord]:
    """Return the in-memory method index (a thin pass-through list; the realize/
    filter walks iterate it). A dict keyed by id is an equivalent shape."""
    return list(methods)


def build_recipe_reverse_index(recipes_doc: dict) -> dict[str, list]:
    """Reverse-index recipes by INPUT item id -> list of FULL product recipe records.

    realize.py walks this DROP-UPWARD: given a drop (e.g. green dragonhide
    ``item:1753``), find what it can become (green dragon leather, then a d'hide
    body) to compute the iron process-then-alch realization. Each value is the raw
    recipe record (``output_item_id``, ``inputs``, ``level``, ``skill``,
    ``output_qty``, optional ``service_fee_coins``) so the walk reads the gate +
    ratios + service fee. A recipe appears under each DISTINCT input item id.
    """
    index: dict[str, list] = {}
    for rec in recipes_doc.get("records", []):
        seen: set[str] = set()
        for inp in rec.get("inputs") or []:
            iid = inp["item_id"] if isinstance(inp, dict) else inp[0]
            if iid in seen:
                continue
            seen.add(iid)
            index.setdefault(iid, []).append(rec)
    return index
