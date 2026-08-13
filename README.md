<p align="center">
  <a href="https://ildana.ai">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset=".github/assets/ildana-lockup-white-512.png">
      <img src=".github/assets/ildana-lockup-black-512.png" alt="Ildana — Augmented Intelligence" width="260">
    </picture>
  </a>
</p>

# Bank → Actual

Convert the statement exports US banks actually produce — CSV files, and
Chase credit-card PDF statements — into files
[Actual Budget](https://actualbudget.org) imports cleanly, in your browser or
from the command line. Nothing is uploaded anywhere; both tools run entirely on
your own machine.

## Get it

**Most people need exactly one file:**
**[⬇ Download Bank2Actual.html](https://github.com/Ildana-ai/bank2actual/releases/latest/download/Bank2Actual.html)**
(from the latest [release](https://github.com/Ildana-ai/bank2actual/releases)).
Everything is embedded in it — open it in any browser on any OS, no install.

Prefer the command line? `bank2actual.py` lives in this repository — same
converter, same output. See [Command line](#command-line) below.

## How to use

1. **Download** [`Bank2Actual.html`](https://github.com/Ildana-ai/bank2actual/releases/latest/download/Bank2Actual.html)
   and keep it anywhere — Desktop is fine. It's one self-contained file;
   opening it is the whole install.
2. **Export a statement from your bank.** CSV from Bank of America, Chase,
   Citi, or Amex — or the PDF statement for Chase cards that offer no CSV
   download.
3. **Open `Bank2Actual.html`** (double-click) and click **Select statement…**,
   or drag the file onto the page.
4. **Read the summary.** The tool names the bank format it detected, counts the
   transactions, and — for Bank of America CSVs and Chase PDFs — proves the
   math against the statement's own totals. If it doesn't reconcile, it refuses
   to produce a file.
5. **First import into a new account?** Tick **Include a Starting Balance row**
   and convert the account's *earliest* statement, so the account balance
   starts where the bank says it should. Skip the checkbox for every later
   statement.
6. **Name the output file and Save** — the save dialog lets you choose where it
   lands.
7. **In Actual:** select the account → **Import** → pick the converted file.
   The columns and dates are named exactly what Actual expects, so the defaults
   import correctly as-is — confirm and done. If anything ever looks off, the
   settings are: date format `YYYY-MM-DD`, columns mapped
   Date / Payee / Notes / Amount, "flip amount" off.

### Suggested workflow

Keep a folder per account (`statements/checking`, `statements/travel card`, …)
and drop each month's export into its folder before converting.

Where the converted file lands is the browser's choice, not the page's — a web
page can neither see where an input file came from nor write anywhere on its
own. To control the destination:

- **Chrome / Edge:** the **Save** button opens a save dialog — pick the
  account's folder there. It reopens in the last-used folder next time.
- **Safari / Firefox:** saves go to the download folder by default. In Safari,
  **Settings → General → File download location → Ask for each download** gives
  you a save dialog instead.
- **Command line:** outputs land next to the input files automatically —
  `python3 bank2actual.py statements/travel-card/*.pdf` writes each converted
  file into that same folder.

> **Tip:** Chase, Citi, and Amex also offer QFX ("Quicken") downloads, which
> Actual imports natively with no converter needed. This tool is for the
> accounts and date ranges where CSV or PDF is what you can get.

## What is Actual?

[Actual Budget](https://actualbudget.org) is a free, open-source, local-first
personal finance app built around envelope budgeting. Your financial data stays
on your own computer (with optional end-to-end-encrypted sync).
**Download it at [actualbudget.org/download](https://actualbudget.org/download/)**
— desktop apps for macOS, Windows, and Linux, or a self-hostable server.

Actual imports QIF/OFX/QFX natively, but bank **CSV** exports are messier:
summary preambles before the header, balance rows mixed into transactions,
split debit/credit columns, inverted sign conventions, and (in Bank of
America's case) malformed quoting. This tool normalizes all of that into a
four-column CSV — `Date, Payee, Notes, Amount` — that maps straight into
Actual's import dialog.

Some Chase cards offer no CSV download at all — only PDF statements. The tool
reads those too: text is extracted locally, and the output is refused unless
every transaction reconciles against the statement's own balances.

## Supported formats

| Bank | Export | Quirks handled |
|---|---|---|
| Bank of America | checking / savings | summary preamble, balance rows, unescaped quotes in descriptions |
| Bank of America | credit card | — |
| Chase | credit card | category + memo → Notes |
| Chase | checking | — |
| Citi | credit card | split Debit/Credit columns merged into one signed amount; **Pending rows dropped** (they change when they settle and would duplicate on re-import) |
| American Express | credit card | sign convention flipped (Amex exports charges as positive) |
| Chase | credit card **PDF statement** | for accounts where Chase offers no CSV download: text is extracted locally (embedded [PDF.js](https://github.com/mozilla/pdf.js) in the browser tool, [pypdf](https://pypi.org/project/pypdf/) for the CLI), transaction year is derived from the statement period, and the output is **refused unless every transaction reconciles** against the statement's own Previous → New Balance |

The format is auto-detected from the header row. Output convention: negative =
money out, dates are `YYYY-MM-DD`.

Every format above is **verified against real statements**, not just bank
documentation, and the maintainer uses this tool for all of their own
statements. The output needs no adjustment in Actual's import dialog: columns
and dates match what Actual auto-detects, so it's a straight import, every time.

For Bank of America checking exports, the converter also cross-checks its
output against the "Total credits / Total debits" summary inside the statement
itself and refuses to hand you a file that doesn't reconcile.

## Browser tool (no install)

Open **`Bank2Actual.html`** in any modern browser on any OS. Drop a statement
on it — CSV, or a Chase PDF statement — review the summary, then name the
output file and choose where to save it. The optional *Starting Balance*
checkbox adds an opening-balance row for the first import into a new account —
from the "Beginning balance" line of a Bank of America CSV, or from the
Previous Balance of a Chase PDF statement (negated, since card debt is a
negative balance in Actual). Use it with the account's earliest statement only.

Everything happens locally in the page — the file never leaves your computer.
The PDF engine (Mozilla PDF.js, Apache-2.0) is embedded in the file and loads
only when a PDF is dropped.

## Command line

Python 3.8+, standard library only, any OS:

```bash
python3 bank2actual.py statement.csv
python3 bank2actual.py chase-statement.pdf
python3 bank2actual.py *.csv --outdir converted --merge my-checking
```

Each input becomes `<name>-actual.csv`. `--merge` additionally combines all
inputs into one file, deduplicating transactions that appear in overlapping
statements while preserving legitimate same-day duplicate charges.

CSV conversion needs nothing beyond the standard library. Chase PDF statements
additionally need [pypdf](https://pypi.org/project/pypdf/) (`pip install pypdf`).

**macOS note:** the system may block Terminal from reading files in Downloads
or Desktop (`Operation not permitted` — even with `sudo`). Grant Terminal
access under System Settings → Privacy & Security → Files & Folders, or move
the statement to an unprotected folder first.

## License & disclaimer

Code is [MIT](LICENSE) — provided as-is, without warranty of any kind. The
embedded Michroma typeface is licensed under the
[SIL Open Font License 1.1](OFL.txt). The Ildana name, logo, and brand artwork
are not covered by the MIT license.

This project is not affiliated with or endorsed by Actual Budget, Bank of
America, JPMorgan Chase, Citi, or American Express; their names are used only
to describe file-format compatibility. Spot-check your first import against
your statement before relying on it. Download this tool only from this
repository — copies obtained elsewhere may have been modified.

---

<p align="center">
  <a href="https://ildana.ai">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset=".github/assets/ildana-lockup-white-512.png">
      <img src=".github/assets/ildana-lockup-black-512.png" alt="Ildana — Augmented Intelligence" width="200">
    </picture>
  </a>
</p>
