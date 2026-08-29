"""Tests for bank2actual.py. Run: python3 -m pytest test_bank2actual.py"""

import bank2actual as b2a

BOFA_CARD = "Posted Date,Reference Number,Payee,Address,Amount\n"
AMEX = "Date,Description,Amount\n"


def rows_from(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text)
    bank, result, err = b2a.convert(path)
    assert err is None, err
    return result["rows"]


def test_merge_dedupes_on_reference_despite_rewritten_description(tmp_path):
    # The same charge in two overlapping exports: pending "SQ *COFFEE" posted as
    # "SQUARE COFFEE". Same reference number, so it must count once.
    a = rows_from(tmp_path, "a.csv", BOFA_CARD
                  + "08/01/2026,24692169000000000000001,SQ *COFFEE,,-4.50\n"
                  + "08/02/2026,24692169000000000000002,GROCER,,-20.00\n")
    b = rows_from(tmp_path, "b.csv", BOFA_CARD
                  + "08/01/2026,24692169000000000000001,SQUARE COFFEE,,-4.50\n"
                  + "08/03/2026,24692169000000000000003,GAS,,-30.00\n")
    merged = b2a.merge_rows([a, b])
    assert len(merged) == 3
    payees = [r[1] for r in merged]
    assert "SQ *COFFEE" in payees  # first file given wins
    assert "SQUARE COFFEE" not in payees


def test_merge_preserves_same_day_identical_charges(tmp_path):
    # Two identical same-day charges in one file are real; a cross-file copy is overlap.
    twice = AMEX + "08/05/2026,COFFEE SHOP,4.50\n" * 2
    a = rows_from(tmp_path, "jul.csv", twice)
    b = rows_from(tmp_path, "aug.csv", twice)
    assert len(b2a.merge_rows([a])) == 2
    assert len(b2a.merge_rows([a, b])) == 2


def test_empty_and_zero_refs_fall_back_to_row_equality(tmp_path):
    # BofA reuses blank/"0" references; rows under them must behave like no-ref rows.
    a = rows_from(tmp_path, "a.csv", BOFA_CARD
                  + "08/04/2026,0,PAYMENT,,-100.00\n"
                  + "08/04/2026,0,PAYMENT,,-100.00\n")
    b = rows_from(tmp_path, "b.csv", BOFA_CARD
                  + "08/04/2026,,PAYMENT,,-100.00\n")
    assert all(r[4] is None for r in a + b)
    assert len(b2a.merge_rows([a, b])) == 2


def test_output_keeps_four_columns(tmp_path):
    rows = rows_from(tmp_path, "a.csv", BOFA_CARD
                     + "08/01/2026,24692169000000000000001,SQ *COFFEE,,-4.50\n")
    assert rows[0][4] == "24692169000000000000001"
    out = tmp_path / "out.csv"
    b2a.write_out(out, rows)
    lines = out.read_text().splitlines()
    assert lines[0] == "Date,Payee,Notes,Amount"
    assert lines[1] == "2026-08-01,SQ *COFFEE,,-4.50"
