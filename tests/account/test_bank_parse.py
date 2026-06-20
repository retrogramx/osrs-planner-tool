from osrs_planner.account.bank import parse_bank_tsv

def test_parses_id_name_qty():
    text = "995\tCoins              \t\t1000000\n561\tNature rune\t5000\n"
    assert parse_bank_tsv(text) == {"item:995": 1000000, "item:561": 5000}

def test_skips_blank_and_malformed():
    text = "\n4151\tAbyssal whip\t1\ngarbage line\n\t\t\n"
    assert parse_bank_tsv(text) == {"item:4151": 1}

def test_dedupes_and_sums_repeats():
    assert parse_bank_tsv("995\tCoins\t10\n995\tCoins\t5\n") == {"item:995": 15}

def test_strips_commas_in_qty():
    assert parse_bank_tsv("561\tNature rune\t1,234\n") == {"item:561": 1234}
