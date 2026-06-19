"""validate_income.py: exits 0 on committed data; negative fixtures fail (iron-gate)."""
from __future__ import annotations

import importlib.util
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VALIDATOR = os.path.join(REPO, "data", "validate_income.py")


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_income", VALIDATOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(data_dir: str, kg_dir: str):
    mod = _load_validator()
    mod.errors.clear()    # module-level accumulators; reset between in-process runs
    mod.warnings.clear()
    rc = mod.main(["--data", data_dir, "--kg", kg_dir])
    return rc, mod


def test_committed_data_passes():
    # Exits 0 with EXACTLY the 2 disclosed [known-gap] warnings (Crack the Clue III,
    # Sleeping Giants) -- real KG quest-coverage gaps, NOT income's job to fix. The
    # diary-shaped iron refs (Ardougne Diary ...) are skipped, not fatal.
    rc, mod = _run(os.path.join(REPO, "data"), os.path.join(REPO, "kg"))
    assert rc == 0
    gap_quests = {w for w in mod.warnings if "[known-gap]" in w}
    assert any("crack-the-clue-iii" in w for w in gap_quests)
    assert any("sleeping-giants" in w for w in gap_quests)
    # no diary ref should appear as an unresolved-quest warning/error
    assert not any("diary" in w.lower() for w in mod.warnings)


def _write_envelope(path, records, excluded=None, record_count=None):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({
            "_provenance": {"record_count": len(records) if record_count is None else record_count},
            "records": records,
            "_excluded": [] if excluded is None else excluded,
        }, f)


def _scaffold(tmp_path):
    data = tmp_path / "data"
    kg = tmp_path / "kg"
    data.mkdir()
    kg.mkdir()
    with open(data / "item_dictionary.json", "w") as f:
        json.dump({"_provenance": {}, "records": [{"item_id": 1753, "name": "Green dragonhide"}], "_excluded": []}, f)
    with open(kg / "nodes.json", "w") as f:
        json.dump([{"id": "quest:dragon-slayer-ii", "kind": "quest", "name": "Dragon Slayer II", "slug": "dragon-slayer-ii"}], f)
    _write_envelope(str(data / "money_making.json"), [])
    return str(data), str(kg)


def test_requires_ge_must_be_iron_ineligible(tmp_path):
    data, kg = _scaffold(tmp_path)
    _write_envelope(os.path.join(data, "money_making.json"),
                    [{"name": "Flipping X", "requires_ge": True, "iron_eligible": True}])
    assert _run(data, kg)[0] == 1


def test_unresolvable_output_item_id_fails(tmp_path):
    data, kg = _scaffold(tmp_path)
    _write_envelope(os.path.join(data, "money_making.json"),
                    [{"name": "Bad", "requires_ge": False, "outputs": [{"item_id": "item:99999999", "is_coins": False}]}])
    assert _run(data, kg)[0] == 1


def test_unresolvable_structured_quest_ref_fails(tmp_path):
    # The STRICT path: a structured requirements.quests ref that is neither a diary
    # nor a disclosed known-missing quest stays FATAL (curated quest-id list).
    data, kg = _scaffold(tmp_path)
    _write_envelope(os.path.join(data, "money_making.json"),
                    [{"name": "Q", "requires_ge": False,
                      "requirements": {"quests": ["Not A Real Quest"]}}])
    assert _run(data, kg)[0] == 1


def test_main_quest_prose_wikilink_is_non_fatal(tmp_path):
    # The main `quest` markup is FREE-FORM PROSE (items/places/diaries/quests mixed),
    # so an unresolved wikilink is a NON-FATAL [main-quest-prose] disclosure, not an
    # error -- otherwise the validator would fail on ~171 committed refs.
    data, kg = _scaffold(tmp_path)
    _write_envelope(os.path.join(data, "money_making.json"),
                    [{"name": "Skel", "requires_ge": False,
                      "quest": "Completed [[Some Item]] and [[A Place]] (optional)"}])
    rc, mod = _run(data, kg)
    assert rc == 0
    assert any("[main-quest-prose]" in w for w in mod.warnings)


def test_known_missing_iron_quest_is_non_fatal_warning(tmp_path):
    # DR-3: a disclosed known-missing quest ref -> exit 0 + a [known-gap] warning.
    data, kg = _scaffold(tmp_path)
    _write_envelope(os.path.join(data, "money_making.json"),
                    [{"name": "Ruby rings", "requires_ge": False,
                      "requirements": {"quests": ["Crack the Clue III"]}}])
    rc, mod = _run(data, kg)
    assert rc == 0
    assert any("[known-gap]" in w and "crack-the-clue-iii" in w for w in mod.warnings)


def test_diary_shaped_iron_quest_ref_is_skipped_not_fatal(tmp_path):
    # DR-3: a DIARY-shaped requirements.quests entry is NOT a quest gate -> no error.
    data, kg = _scaffold(tmp_path)
    _write_envelope(os.path.join(data, "money_making.json"),
                    [{"name": "Knights", "requires_ge": False,
                      "requirements": {"quests": ["Ardougne Diary medium tasks"]}}])
    rc, mod = _run(data, kg)
    assert rc == 0
    assert not any("diary" in w.lower() for w in mod.warnings + mod.errors)


def test_genuinely_unknown_iron_quest_ref_still_fatal(tmp_path):
    # A quest ref that is neither diary nor disclosed-known-missing stays FATAL.
    data, kg = _scaffold(tmp_path)
    _write_envelope(os.path.join(data, "money_making.json"),
                    [{"name": "Bad", "requires_ge": False,
                      "requirements": {"quests": ["Totally Fake Quest"]}}])
    assert _run(data, kg)[0] == 1


def test_negative_gp_hr_is_non_fatal_disclosure(tmp_path):
    # A negative stored gp_hr is a real net-loss/sink method (e.g. "Catching
    # anglerfish (Diabolic worms)" on committed data) -> NON-FATAL [net-loss], not
    # an error (the stored gp_hr is untrusted; recomputed per family at query time).
    data, kg = _scaffold(tmp_path)
    _write_envelope(os.path.join(data, "money_making.json"),
                    [{"name": "Neg", "requires_ge": False, "gp_hr": -5}])
    rc, mod = _run(data, kg)
    assert rc == 0
    assert any("[net-loss]" in w for w in mod.warnings)


def test_non_numeric_gp_hr_fails(tmp_path):
    # A non-numeric stored gp_hr IS garbage -> fatal.
    data, kg = _scaffold(tmp_path)
    _write_envelope(os.path.join(data, "money_making.json"),
                    [{"name": "Junk", "requires_ge": False, "gp_hr": "lots"}])
    assert _run(data, kg)[0] == 1


def test_record_count_mismatch_fails(tmp_path):
    data, kg = _scaffold(tmp_path)
    _write_envelope(os.path.join(data, "money_making.json"),
                    [{"name": "A", "requires_ge": False}], record_count=99)
    assert _run(data, kg)[0] == 1


def test_kg_income_token_leak_fails(tmp_path):
    data, kg = _scaffold(tmp_path)
    with open(os.path.join(kg, "nodes.json"), "w") as f:
        json.dump([{"id": "quest:dragon-slayer-ii", "gp_hr": 5}], f)
    assert _run(data, kg)[0] == 1
