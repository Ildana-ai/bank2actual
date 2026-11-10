#!/usr/bin/env python3
"""Convert bank CSV exports (BofA, Chase, Citi, Amex) into Actual-ready CSVs.

Output columns: Date,Payee,Notes,Amount  (ISO dates, negative = money out).
Usage: bank2actual.py FILE [FILE ...] [--outdir DIR] [--merge NAME] [--format actual|generic|ynab]
"""

import argparse
import csv
import sys
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

FORMAT_HEADERS = {
    "actual": ["Date", "Payee", "Notes", "Amount"],
    "generic": ["Date", "Description", "Category", "Amount", "Reference"],
    "ynab": ["Date", "Payee", "Memo", "Outflow", "Inflow"],
}

# (bank key, set of column names that identify the header row)
SIGNATURES = [
    ("bofa-bank", {"Date", "Description", "Amount", "Running Bal."}),
    ("bofa-card", {"Posted Date", "Reference Number", "Payee", "Amount"}),
    ("chase-card", {"Transaction Date", "Post Date", "Description", "Amount"}),
    ("chase-bank", {"Details", "Posting Date", "Description", "Amount", "Balance"}),
    ("citi-card", {"Status", "Date", "Description", "Debit", "Credit"}),
    ("amex-card", {"Date", "Description", "Amount"}),
]


def lenient_csv(text):
    """CSV parse that survives BofA's unescaped quotes inside quoted fields:
    a bare quote mid-field is literal text; only quote-before-delimiter closes."""
    rows, row, field, inq = [], [], [], False
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if inq:
            if c == '"':
                # A quote closes the field only when a delimiter follows it (or follows
                # a "" pair); otherwise it is literal text BofA failed to escape.
                is_end = lambda j: j >= n or text[j] in ",\r\n"
                if is_end(i + 1):
                    inq = False
                elif text[i + 1] == '"':
                    field.append('"')
                    i += 1
                    if is_end(i + 1):
                        inq = False
                else:
                    field.append('"')
            else:
                field.append(c)
        elif c == '"':
            inq = True
        elif c == ",":
            row.append("".join(field))
            field = []
        elif c in "\r\n":
            if c == "\r" and i + 1 < n and text[i + 1] == "\n":
                i += 1
            row.append("".join(field))
            rows.append(row)
            row, field = [], []
        else:
            field.append(c)
        i += 1
    if field or row:
        row.append("".join(field))
        rows.append(row)
    return rows


def parse_amount(raw):
    s = (raw or "").strip().replace("$", "").replace(",", "")
    if not s:
        return None
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def clean_ref(raw):
    """A usable bank transaction reference. BofA reuses blank/zero for some rows,
    so those count as no-ref and fall back to row-equality dedupe."""
    s = (raw or "").strip()
    return s if s.strip("0") else None


def parse_date(raw):
    s = (raw or "").strip()
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def detect(rows):
    """Return (bank, header_line_index, header_row). Scans the first 25 rows."""
    for i, row in enumerate(rows[:25]):
        cols = {c.strip() for c in row if c.strip()}
        for bank, sig in SIGNATURES:
            if sig <= cols:
                return bank, i, [c.strip() for c in row]
    return None, None, None


def records_after(rows, header_idx, header):
    for row in rows[header_idx + 1:]:
        if not any(c.strip() for c in row):
            continue
        row = row + [""] * (len(header) - len(row))
        yield dict(zip(header, (c.strip() for c in row)))


def bofa_summary(rows):
    """Pull Total credits/debits from the BofA preamble, if present."""
    totals = {}
    for row in rows[:6]:
        if row and row[0].startswith("Total credits"):
            totals["credits"] = parse_amount(row[-1])
        if row and row[0].startswith("Total debits"):
            totals["debits"] = parse_amount(row[-1])
    return totals


def pdf_lines(path):
    """Chase statement PDFs: extract text lines via pypdf (optional dependency)."""
    from pypdf import PdfReader
    import re as _re
    reader = PdfReader(path)
    if reader.is_encrypted:
        reader.decrypt("")
    lines = []
    for page in reader.pages:
        for ln in page.extract_text(extraction_mode="layout").splitlines():
            ln = _re.sub(r"\s+", " ", ln).strip()
            if ln:
                lines.append(ln)
    return lines


def parse_chase_pdf(lines):
    """Mirror of the browser parser: statement signs are negated so negative = money out;
    output is refused unless the transactions reconcile with New minus Previous Balance."""
    import re as _re

    def money(s):
        neg = "-" in s
        cents = round(float(s.replace("-", "").replace("$", "").replace("+", "").replace(",", "")) * 100)
        return -cents if neg else cents

    if not any("chase.com/cardhelp" in l.lower() for l in lines) or not any("Opening/Closing Date" in l for l in lines):
        return None, "not a recognized Chase credit-card statement PDF"
    closing, opening, prev, new_bal = None, None, None, None
    raw = []
    for line in lines:
        m = _re.search(r"Opening/Closing Date\s+(\d{2})/(\d{2})/(\d{2})\s*-\s*(\d{2})/(\d{2})/(\d{2})", line)
        if m:
            opening = (2000 + int(m.group(3)), int(m.group(1)), int(m.group(2)))
            closing = (2000 + int(m.group(6)), int(m.group(4)), int(m.group(5)))
            continue
        m = _re.search(r"Previous Balance\s+(-?\$[\d,]+\.\d{2})$", line)
        if m:
            prev = money(m.group(1))
            continue
        m = _re.search(r"New Balance\s+(-?\$[\d,]+\.\d{2})$", line)
        if m:
            new_bal = money(m.group(1))
            continue
        m = _re.match(r"^(\d{2})/(\d{2})\s+(.+?)\s+(-?\$?[\d,]+\.\d{2})$", line)
        if m:
            raw.append((int(m.group(1)), int(m.group(2)), m.group(3), money(m.group(4))))
    if closing is None:
        return None, "could not find the Opening/Closing Date line"
    if prev is None or new_bal is None:
        return None, "could not find Previous/New Balance in the account summary"
    if not raw:
        return None, "no transaction lines found"
    total = sum(c for *_, c in raw)
    if total != new_bal - prev:
        return None, (f"does not reconcile: transactions sum to {total / 100:.2f} "
                      f"but New minus Previous Balance is {(new_bal - prev) / 100:.2f}")
    cy, cm, cd = closing
    out = []
    for mo, d, desc, cents in raw:
        year = cy - 1 if (mo, d) > (cm, cd) else cy
        out.append((f"{year:04d}-{mo:02d}-{d:02d}", desc, "", Decimal(-cents).scaleb(-2), None))
    return {"rows": out, "skipped": 0, "recon": (prev, new_bal), "opening": opening}, None


def parse_chase_checking_pdf(lines):
    """Chase checking statement PDF (CLI only for now). Statement signs already mean
    negative = money out; description continuation lines go to Notes. pypdf may glue a
    line's amount and balance together, emit them balance-first, or glue card digits
    onto them, so every possible reading is chained through the running balance from
    Beginning to Ending Balance; output is refused unless exactly one chain fits."""
    import re as _re

    money_pat = r"-?\s?\$?[\d,]+\.\d{2}"
    period_re = _re.compile(r"([A-Z][a-z]+ \d{1,2}, \d{4}) through ([A-Z][a-z]+ \d{1,2}, \d{4})")
    bal_re = _re.compile(rf"^(Beginning|Ending) Balance\s+({money_pat})$")
    ends_re = _re.compile(r"(?=(?:0|[1-9]\d{0,2})(?:,\d{3})*\.\d{2}\Z)")

    def money(s):
        return parse_amount(s.replace(" ", ""))

    def readings(rest):
        """Every (description, amount, balance) the line's two trailing numbers could mean."""
        out = set()
        for j in (m.start() for m in ends_re.finditer(rest)):
            glued = rest[j - 1:j].isdigit()
            head = rest[:j].rstrip(" $")
            neg_mid = head.endswith("-")
            head = head.rstrip("-").rstrip(" $")
            for i in (m.start() for m in ends_re.finditer(head)):
                desc = head[:i]
                if _re.search(r"[,.]\d*\Z", desc):  # would split a number, not peel off card digits
                    continue
                desc = desc.rstrip(" $")
                neg_lead = desc.endswith("-")
                desc = desc.rstrip("-").strip()
                if not desc:
                    continue
                a, b = Decimal(head[i:].replace(",", "")), Decimal(rest[j:].replace(",", ""))
                if neg_lead and neg_mid:
                    signs = [(-1, -1)]
                elif neg_lead or neg_mid:
                    signs = [(-1, 1), (1, -1)]
                else:
                    signs = [(1, 1)]
                for x, y in ((a, b), (b, a)) if glued else ((a, b),):
                    out.update((desc, sx * x, sy * y) for sx, sy in signs)
        return out

    if not any("jpmorgan chase bank" in l.lower() for l in lines) or not any(l.startswith("CHECKING SUMMARY") for l in lines):
        return None, "not a recognized Chase credit-card or checking statement PDF"
    opening = closing = None
    for line in lines:
        m = period_re.search(line)
        if m:
            try:
                opening, closing = (datetime.strptime(s, "%B %d, %Y").date() for s in m.groups())
            except ValueError:
                pass
            break
    begin, end, in_detail, cur = None, None, False, None
    raw = []
    for line in lines:
        if line.startswith("TRANSACTION DETAIL"):
            if end is not None:
                return None, "more than one account in this statement; only single-account statements are supported"
            in_detail, cur = True, None
            continue
        if not in_detail:
            continue
        m = bal_re.match(line)
        if m:
            if m.group(1) == "Beginning":
                begin = money(m.group(2))
            else:
                end, in_detail = money(m.group(2)), False
            cur = None
            continue
        m = _re.match(r"(\d{2})/(\d{2})\s+(.+)", line)
        if m:
            options = readings(m.group(3))
            if not options:
                return None, f"could not read the amounts of the {m.group(1)}/{m.group(2)} transaction"
            cur = [int(m.group(1)), int(m.group(2)), options, []]
            raw.append(cur)
        elif line.startswith(("*", "Page ", "Account Number", "DATE DESCRIPTION")) or period_re.search(line):
            cur = None  # page break artifacts never belong to a transaction
        elif cur:
            cur[3].append(line)
    if closing is None:
        return None, "could not find the statement period line"
    if begin is None or end is None:
        return None, "could not find Beginning/Ending Balance in the transaction detail"
    states = {begin: []}  # running balance -> rows reaching it; None once two readings do
    for mo, d, options, notes in raw:
        nxt = {}
        for prev, rows in states.items():
            for desc, amount, bal in options:
                if prev + amount == bal:
                    nxt[bal] = None if rows is None or bal in nxt else rows + [(mo, d, desc, notes, amount)]
        if not nxt:
            return None, f"does not reconcile: the {mo:02d}/{d:02d} transaction does not match the running balance"
        states = nxt
    if end not in states:
        return None, "does not reconcile: the last running balance is not the Ending Balance"
    if states[end] is None:
        return None, "more than one reading of the amounts fits the running balance"
    out = []
    for mo, d, desc, notes, amount in states[end]:
        year = closing.year - 1 if (mo, d) > (closing.month, closing.day) else closing.year
        out.append((f"{year:04d}-{mo:02d}-{d:02d}", desc, " ".join(notes), amount, None))
    return {"rows": out, "skipped": 0, "recon": (begin, end),
            "period": (opening.isoformat(), closing.isoformat())}, None


def convert_pdf(path):
    try:
        import pypdf  # noqa: F401
    except ImportError:
        return None, None, "PDF support needs pypdf (pip install pypdf) — or use Bank2Actual.html, which needs nothing"
    try:
        lines = pdf_lines(path)
    except Exception as e:
        return None, None, f"could not read PDF: {e}"
    bank = "chase-card-pdf"
    result, err = parse_chase_pdf(lines)
    if err and err.startswith("not a recognized"):
        bank = "chase-bank-pdf"
        result, err = parse_chase_checking_pdf(lines)
    if err:
        return None, None, f"{err}. Only Chase credit-card and checking statement PDFs are supported; for other banks download the CSV export."
    return bank, result, None


def convert(path):
    if path.suffix.lower() == ".pdf":
        return convert_pdf(path)
    text = path.read_text(encoding="utf-8-sig")
    src_rows = lenient_csv(text)
    bank, idx, header = detect(src_rows)
    if bank is None:
        return None, None, "unrecognized format (no known header in first 25 lines)"
    # Rows are (date, payee, notes, amount, ref) internally; ref is the bank's own
    # transaction reference where the export carries one, else None. Only the first
    # four columns are ever written out.
    out, skipped = [], 0
    for r in records_after(src_rows, idx, header):
        if bank == "bofa-bank":
            amt = parse_amount(r["Amount"])
            if amt is None:  # balance rows carry no amount
                skipped += 1
                continue
            out.append((parse_date(r["Date"]), r["Description"], "", amt, None))
        elif bank == "bofa-card":
            amt = parse_amount(r["Amount"])
            if amt is None:
                skipped += 1
                continue
            out.append((parse_date(r["Posted Date"]), r["Payee"], "", amt, clean_ref(r.get("Reference Number"))))
        elif bank == "chase-card":
            amt = parse_amount(r["Amount"])
            if amt is None:
                skipped += 1
                continue
            notes = " / ".join(x for x in (r.get("Category", ""), r.get("Memo", "")) if x)
            out.append((parse_date(r["Transaction Date"]), r["Description"], notes, amt, None))
        elif bank == "chase-bank":
            amt = parse_amount(r["Amount"])
            if amt is None:
                skipped += 1
                continue
            out.append((parse_date(r["Posting Date"]), r["Description"], r.get("Type", ""), amt, None))
        elif bank == "citi-card":
            if r.get("Status", "").lower() == "pending":  # pending rows change on settle; re-import would duplicate
                skipped += 1
                continue
            debit = parse_amount(r["Debit"]) or Decimal(0)
            credit = parse_amount(r["Credit"]) or Decimal(0)
            if debit == 0 and credit == 0:
                skipped += 1
                continue
            out.append((parse_date(r["Date"]), r["Description"], "", credit - debit, None))
        elif bank == "amex-card":
            amt = parse_amount(r["Amount"])
            if amt is None:
                skipped += 1
                continue
            notes = r.get("Category", "") or r.get("Extended Details", "")[:80]
            out.append((parse_date(r["Date"]), r["Description"], notes, -amt, None))  # Amex: positive = charge
    bad = [t for t in out if t[0] is None]
    if bad:
        return None, None, f"{len(bad)} rows had unparseable dates"
    return bank, {"rows": out, "skipped": skipped, "src_rows": src_rows}, None


def verify_bofa(src_rows, rows):
    totals = bofa_summary(src_rows)
    if not totals:
        return None
    credits = sum(r[3] for r in rows if r[3] > 0)
    debits = sum(r[3] for r in rows if r[3] < 0)
    ok = credits == totals.get("credits") and debits == totals.get("debits")
    return ok, credits, debits, totals


def merge_rows(per_file_rows):
    """Cross-file dedupe in two passes. Rows carrying a bank reference dedupe on it —
    first file wins — so the same charge survives once even when the bank rewrote the
    description between exports (pending vs. posted). Rows without one keep the max
    count of each identical txn seen in any single file, so cross-file overlap dedupes
    but legit same-day duplicates within a file survive."""
    seen_refs, with_ref, without = set(), [], Counter()
    for rows in per_file_rows:
        counts = Counter()
        for row in rows:
            if row[4] is None:
                counts[row[:4]] += 1
            elif row[4] not in seen_refs:
                seen_refs.add(row[4])
                with_ref.append(row)
        without |= counts
    merged = with_ref + [r + (None,) for r in without.elements()]
    return sorted(merged, key=lambda r: r[:4])


def balance_chain_notes(statements):
    """Informational notes on (start, end, beginning balance, ending balance) statements:
    the dates covered and every place one Ending Balance isn't the next Beginning Balance.
    Non-consecutive inputs are legitimate, so breaks are reported, never enforced."""
    stmts = sorted(statements)
    breaks = [f"NOTE  balance chain breaks between the statement ending {a[1]} and the one starting {b[0]}"
              " (expected if those months come from other files; otherwise a statement is missing)"
              for a, b in zip(stmts, stmts[1:]) if a[3] != b[2]]
    status = f"{len(breaks)} break(s) in the balance chain" if breaks else "balances chain with no gaps"
    return [f"NOTE  {len(stmts)} checking PDF statements cover {stmts[0][0]} to {stmts[-1][1]}; {status}"] + breaks


def shape_row(row, fmt):
    date, payee, notes, amount, ref = row
    if fmt == "generic":
        return [date, payee, notes, amount, ref or ""]
    if fmt == "ynab":  # YNAB wants positive amounts in split Outflow/Inflow columns
        return [date, payee, notes, -amount, ""] if amount < 0 else [date, payee, notes, "", amount]
    return [date, payee, notes, amount]


def write_out(path, rows, fmt="actual"):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(FORMAT_HEADERS[fmt])
        for row in rows:
            w.writerow(shape_row(row, fmt))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--version", action="version", version="bank2actual 1.3.1")
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument("--outdir", type=Path, help="output directory (default: next to each input)")
    ap.add_argument("--merge", metavar="NAME", help="also merge all converted rows into one file, deduped across files")
    ap.add_argument("--format", choices=["actual", "generic", "ynab"], default="actual",
                    help="output layout: actual (default), generic spreadsheet, or ynab (experimental)")
    args = ap.parse_args()

    if args.outdir:
        args.outdir.mkdir(parents=True, exist_ok=True)

    per_file_rows, chain, failures = [], [], 0
    for path in args.files:
        if not path.exists():
            print(f"SKIP  {path}: not found")
            failures += 1
            continue
        bank, result, err = convert(path)
        if err:
            print(f"SKIP  {path.name}: {err}")
            failures += 1
            continue
        rows = sorted(result["rows"], key=lambda r: r[:4])
        outdir = args.outdir or path.parent
        out_path = outdir / f"{path.stem}-{args.format}.csv"
        write_out(out_path, rows, args.format)
        line = f"OK    {path.name} -> {out_path}  [{bank}] {len(rows)} txns"
        if result["skipped"]:
            line += f", {result['skipped']} non-transaction rows skipped"
        if bank == "bofa-bank":
            v = verify_bofa(result["src_rows"], rows)
            if v:
                ok, credits, debits, totals = v
                line += f" | totals {'MATCH' if ok else 'MISMATCH'} vs statement summary ({credits} cr / {debits} db)"
        elif bank == "chase-card-pdf":
            prev, new_bal = result["recon"]
            line += f" | reconciled: previous balance {prev / 100:.2f} -> new balance {new_bal / 100:.2f}"
        elif bank == "chase-bank-pdf":
            begin, end = result["recon"]
            line += f" | reconciled: beginning balance {begin} -> ending balance {end}"
            chain.append((*result["period"], begin, end))
        print(line)
        per_file_rows.append(rows)

    if args.merge and per_file_rows:
        rows = merge_rows(per_file_rows)
        outdir = args.outdir or args.files[0].parent
        out_path = outdir / f"{args.merge}-{args.format}.csv"
        write_out(out_path, rows, args.format)
        print(f"MERGE -> {out_path}  {len(rows)} txns from {len(per_file_rows)} files")
        if len(chain) > 1:
            print("\n".join(balance_chain_notes(chain)))

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
