"""K5: account_family(mode) maps specific OSRS modes to product families
{main, ironman, uim} (§6.4). HCIM/GIM/HCGIM ride the 'ironman' family; UIM is
its own 'uim'; everything else (normal/main/unknown) is 'main'."""
from osrs_planner.engine.state import account_family


def test_account_family_main_variants():
    assert account_family("normal") == "main"
    assert account_family("main") == "main"
    assert account_family("") == "main"
    assert account_family("anything_unknown") == "main"


def test_account_family_ironman_variants_collapse():
    assert account_family("ironman") == "ironman"
    assert account_family("hardcore_ironman") == "ironman"
    assert account_family("group_ironman") == "ironman"
    assert account_family("hardcore_group_ironman") == "ironman"


def test_account_family_uim_is_its_own_family():
    assert account_family("ultimate_ironman") == "uim"


from osrs_planner.engine.kleene import Tri
from osrs_planner.engine.kg.model import AtomType, ConditionAtom
from osrs_planner.engine.kg.store import InMemoryKGStore
from osrs_planner.engine.state import AccountState
from osrs_planner.engine.conditions import atom_satisfied


def _empty_kg() -> InMemoryKGStore:
    return InMemoryKGStore(nodes=[], edges=[], groups={})


def test_account_type_atom_family_value_matches_all_iron_variants():
    kg = _empty_kg()
    atom = ConditionAtom(atom_type=AtomType.ACCOUNT_TYPE, data={"value": "ironman"})
    assert atom_satisfied(atom, AccountState(mode="ironman"), kg) is Tri.TRUE
    assert atom_satisfied(atom, AccountState(mode="hardcore_ironman"), kg) is Tri.TRUE
    assert atom_satisfied(atom, AccountState(mode="group_ironman"), kg) is Tri.TRUE
    assert atom_satisfied(atom, AccountState(mode="hardcore_group_ironman"), kg) is Tri.TRUE
    assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.FALSE
    assert atom_satisfied(atom, AccountState(mode="ultimate_ironman"), kg) is Tri.FALSE


def test_account_type_atom_main_family_value():
    kg = _empty_kg()
    atom = ConditionAtom(atom_type=AtomType.ACCOUNT_TYPE, data={"value": "main"})
    assert atom_satisfied(atom, AccountState(mode="normal"), kg) is Tri.TRUE
    assert atom_satisfied(atom, AccountState(mode="ironman"), kg) is Tri.FALSE


def test_account_type_atom_uim_family_value():
    kg = _empty_kg()
    atom = ConditionAtom(atom_type=AtomType.ACCOUNT_TYPE, data={"value": "uim"})
    assert atom_satisfied(atom, AccountState(mode="ultimate_ironman"), kg) is Tri.TRUE
    assert atom_satisfied(atom, AccountState(mode="ironman"), kg) is Tri.FALSE


def test_account_type_atom_specific_mode_value_is_literal():
    kg = _empty_kg()
    atom = ConditionAtom(atom_type=AtomType.ACCOUNT_TYPE, data={"value": "hardcore_ironman"})
    assert atom_satisfied(atom, AccountState(mode="hardcore_ironman"), kg) is Tri.TRUE
    assert atom_satisfied(atom, AccountState(mode="ironman"), kg) is Tri.FALSE
