import json, os
import pytest
from data._dropsline import dropsline_query_url, parse_bucket_response

def test_query_url_targets_dropsline_bucket():
    url = dropsline_query_url("Abyssal whip", limit=30)
    assert "action=bucket" in url and "format=json" in url
    assert "bucket('dropsline')" in url
    assert "select('item_name','drop_json','rare_drop_table')" in url
    assert "Abyssal%20whip" in url or "Abyssal+whip" in url
    assert ".limit(30).run()" in url

def test_query_url_escapes_apostrophe():  # M1 — 182 clog names carry an apostrophe
    url = dropsline_query_url("Ahrim's hood")
    # the apostrophe must be backslash-escaped INSIDE the Lua literal, then URL-encoded
    from urllib.parse import unquote
    assert "\\'" in unquote(url), "apostrophe not escaped -> the API would return an error envelope"

def test_parse_bucket_raises_on_error_envelope():  # M2 — never swallow API errors
    with pytest.raises(ValueError):
        parse_bucket_response({"error": "')' expected near 's'."})

def test_parse_bucket_decodes_drop_json_string():
    # Bucket may deliver drop_json as a JSON-encoded STRING; decode it.
    payload = {"bucket": [
        {"item_name": "Abyssal whip",
         "drop_json": json.dumps({"Dropped from": "Abyssal demon#Standard",
                                  "Rarity": "1/512", "Rolls": 1, "Drop Quantity": "1"}),
         "rare_drop_table": False}
    ]}
    rows = parse_bucket_response(payload)
    assert rows[0]["drop_json"]["Dropped from"] == "Abyssal demon#Standard"
    assert rows[0]["drop_json"]["Rarity"] == "1/512"

def test_parse_bucket_passes_drop_json_object_through():
    payload = {"bucket": [
        {"item_name": "X", "drop_json": {"Dropped from": "Y", "Rarity": "1/4"}, "rare_drop_table": False}
    ]}
    rows = parse_bucket_response(payload)
    assert rows[0]["drop_json"]["Rarity"] == "1/4"
