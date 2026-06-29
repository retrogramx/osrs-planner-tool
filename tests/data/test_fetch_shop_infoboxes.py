import importlib.util, os
_spec = importlib.util.spec_from_file_location(
    "fetch_shop_infoboxes",
    os.path.join(os.path.dirname(__file__), "..", "..", "data", "fetch_shop_infoboxes.py"))
fsi = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(fsi)

SINGLE = "{{Infobox Shop\n|name = Lumbridge General Store\n|members = No\n|location = [[Lumbridge]]\n|owner = [[Shop keeper]]/[[Shop assistant]]\n}}\n==Stock=="
VERSIONED = ("{{Infobox Shop\n|name = Slayer Rewards\n|members = Yes\n"
             "|location1 = [[Burthorpe]]\n|location2 = [[Draynor Village]]\n"
             "|owner1 = [[Turael]]/[[Aya]]\n|owner2 = [[Spria]]\n}}")
NESTED = "{{Infobox Shop\n|name = X\n|location = [[Falador]] {{Map|x}}\n|members = Yes\n}}"

def test_extract_block_isolates_infobox():
    b = fsi.extract_infobox_block(SINGLE)
    assert "name = Lumbridge General Store" in b
    assert "==Stock==" not in b

def test_extract_block_handles_nested_template():
    b = fsi.extract_infobox_block(NESTED)
    assert "{{Map|x}}" in b           # nested template fully inside the block

def test_single_location():
    p = fsi.split_top_level_params(fsi.extract_infobox_block(SINGLE))
    assert fsi.shop_locations(p) == ["[[Lumbridge]]"]
    assert fsi.shop_members(p) == "No"
    assert fsi.shop_owners(p) == ["[[Shop keeper]]/[[Shop assistant]]"]

def test_versioned_locations_unioned_in_order():
    p = fsi.split_top_level_params(fsi.extract_infobox_block(VERSIONED))
    assert fsi.shop_locations(p) == ["[[Burthorpe]]", "[[Draynor Village]]"]
    assert fsi.shop_members(p) == "Yes"

def test_no_infobox_returns_empty():
    assert fsi.extract_infobox_block("just prose, no infobox") == ""

def test_nested_pipe_not_split():
    p = fsi.split_top_level_params(fsi.extract_infobox_block(NESTED))
    assert p["location"] == "[[Falador]] {{Map|x}}"   # the {{Map|x}} pipe did NOT split the param
