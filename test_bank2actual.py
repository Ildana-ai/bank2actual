"""Tests for bank2actual.py. Run: python3 -m pytest test_bank2actual.py"""

from decimal import Decimal

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


def test_ynab_and_generic_formats(tmp_path):
    rows = rows_from(tmp_path, "a.csv", BOFA_CARD
                     + "08/01/2026,2469001,COFFEE,,-4.50\n"
                     + "08/02/2026,2469002,REFUND,,10.00\n")
    out = tmp_path / "o.csv"
    b2a.write_out(out, rows, "ynab")
    lines = out.read_text().splitlines()
    assert lines[0] == "Date,Payee,Memo,Outflow,Inflow"
    assert lines[1] == "2026-08-01,COFFEE,,4.50,"
    assert lines[2] == "2026-08-02,REFUND,,,10.00"
    b2a.write_out(out, rows, "generic")
    lines = out.read_text().splitlines()
    assert lines[0] == "Date,Description,Category,Amount,Reference"
    assert lines[1] == "2026-08-01,COFFEE,,-4.50,2469001"


# Synthetic text in the shape pypdf extracts from a Chase checking statement.
CHASE_CHECKING_PDF = [
    "December 24, 2025 through January 23, 2026",
    "JPMorgan Chase Bank, N.A. Account Number: 000000000000000",
    "CHECKING SUMMARY",
    "Beginning Balance $100.00",
    "Ending Balance $485.00",
    "TRANSACTION DETAIL",
    "DATE DESCRIPTION AMOUNT BALANCE",
    "Beginning Balance $100.00",
    "12/26 Deposit 1234567890 250.00350.00",
    "12/30 Zelle Payment To Friend 1234567890 - 45.50 304.50",
    "01/05 Fedwire Credit Via: Some Bank 1,000.00 1,304.50",
    "Trn: 123 Ref: ABC",
    "*end*transaction detail",
    "Page 1 of 2",
    "December 24, 2025 through January 23, 2026",
    "Account Number: 000000000000000",
    "TRANSACTION DETAIL (continued)",
    "DATE DESCRIPTION AMOUNT BALANCE",
    "01/05 Domestic Incoming Wire Fee - 15.00 1,289.50",
    "01/10 Card Purchase 01/09 Coffee Shop Card- 4.50 1,285.00",
    "1234",
    # pypdf output seen in real statements: card digits and balance-first glued numbers.
    "01/12 ATM Check Deposit 01/12 Main St Card 12341,485.00200.00",
    "01/15 Online Payment 9876 To Landlord - 485.001,000.00",
    "Ending Balance $485.00",
]


def test_chase_checking_pdf_parses_and_reconciles():
    result, err = b2a.parse_chase_checking_pdf(CHASE_CHECKING_PDF)
    assert err is None, err
    assert result["recon"] == (Decimal("100.00"), Decimal("485.00"))
    assert result["period"] == ("2025-12-24", "2026-01-23")
    assert result["rows"] == [
        ("2025-12-26", "Deposit 1234567890", "", Decimal("250.00"), None),
        ("2025-12-30", "Zelle Payment To Friend 1234567890", "", Decimal("-45.50"), None),
        ("2026-01-05", "Fedwire Credit Via: Some Bank", "Trn: 123 Ref: ABC", Decimal("1000.00"), None),
        ("2026-01-05", "Domestic Incoming Wire Fee", "", Decimal("-15.00"), None),
        ("2026-01-10", "Card Purchase 01/09 Coffee Shop Card", "1234", Decimal("-4.50"), None),
        ("2026-01-12", "ATM Check Deposit 01/12 Main St Card 1234", "", Decimal("200.00"), None),
        ("2026-01-15", "Online Payment 9876 To Landlord", "", Decimal("-1000.00"), None),
    ]


def test_balance_chain_notes_report_gaps_without_enforcing():
    jan = ("2025-12-24", "2026-01-23", Decimal("100"), Decimal("50"))
    feb = ("2026-01-24", "2026-02-23", Decimal("50"), Decimal("70"))
    mar = ("2026-02-24", "2026-03-23", Decimal("80"), Decimal("90"))
    notes = b2a.balance_chain_notes([mar, jan, feb])
    assert notes[0] == "NOTE  3 checking PDF statements cover 2025-12-24 to 2026-03-23; 1 break(s) in the balance chain"
    assert len(notes) == 2 and "ending 2026-02-23 and the one starting 2026-02-24" in notes[1]
    assert b2a.balance_chain_notes([jan, feb])[0].endswith("balances chain with no gaps")


def test_chase_checking_pdf_refuses_unreconciled():
    lines = [l.replace("- 15.00", "- 16.00") for l in CHASE_CHECKING_PDF]
    result, err = b2a.parse_chase_checking_pdf(lines)
    assert result is None
    assert err.startswith("does not reconcile")
