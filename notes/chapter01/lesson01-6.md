# Lesson 1.6: The Account Model

## Files
- `src/osrs_planner/models.py` — added `Account` model with nested `Skill` dict

---

## Nested Pydantic Models
- Models can contain other models as fields: `skills: dict[str, Skill]`
- Pydantic validates the nested models too — a bad `Skill` inside an `Account` still gets caught

## dict[str, Skill]
- A dictionary maps **keys** to **values**: `{"agility": Skill(...)}`
- `dict[str, Skill]` means: keys are strings, values are Skill objects
- You define the **shape**, not the contents — the actual skills get filled in when creating an Account
- Access values with: `account.skills["agility"]`

## Default Values
- Give a field a default to make it optional: `is_skiller: bool = False`
- If not provided when creating the model, the default is used automatically
- Fields without defaults are **required** — omitting them raises a ValidationError

## Enums as Fields
- `mode: AccountMode` — Pydantic validates that the value is a valid enum member
- Access with dot notation: `AccountMode.ironman`

## Account Restrictions
- `is_skiller` — level 3 skill pure, cannot gain combat XP
- `is_pure` — 1 Defence pure
- These are boolean flags that will affect plan generation later (Chapter 4)
- Easy to extend — add more flags as needed (`is_zerker`, `is_10hp`, etc.)

## References
- **Pydantic nested models**: https://docs.pydantic.dev/latest/concepts/models/#nested-models — models inside models
- **Python dict type hint**: https://docs.python.org/3/library/stdtypes.html#dict — `dict[str, Skill]` syntax
- **Default values**: https://docs.pydantic.dev/latest/concepts/fields/#default-values — optional fields with defaults
- **Boolean type**: https://docs.python.org/3/library/stdtypes.html#boolean-type-bool — `True`, `False`
