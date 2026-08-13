<p align="center">
  <a href="https://ildana.ai">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset=".github/assets/ildana-lockup-white-512.png">
      <img src=".github/assets/ildana-lockup-black-512.png" alt="Ildana — Augmented Intelligence" width="260">
    </picture>
  </a>
</p>

# Bank → Actual

Convert the CSV statement exports that US banks actually produce into files
[Actual Budget](https://actualbudget.org) imports cleanly — in your browser or
from the command line. Nothing is uploaded anywhere; both tools run entirely on
your own machine.

## Get it

**Most people need exactly one file:**
**[⬇ Download Bank2Actual.html](https://github.com/Ildana-ai/bank2actual/releases/latest/download/Bank2Actual.html)**
(from the latest [release](https://github.com/Ildana-ai/bank2actual/releases)).
Everything is embedded in it — open it in any browser on any OS, no install.

Prefer the command line? `bank2actual.py` lives in this repository — same
converter, same output. See [Command line](#command-line) below.

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
python3 bank2actual.py *.csv --outdir converted --merge my-checking
```

Each input becomes `<name>-actual.csv`. `--merge` additionally combines all
inputs into one file, deduplicating transactions that appear in overlapping
statements while preserving legitimate same-day duplicate charges.

CSV conversion needs nothing beyond the standard library. Chase PDF statements
additionally need [pypdf](https://pypi.org/project/pypdf/) (`pip install pypdf`).

## Importing into Actual

1. Select the account → **Import** → choose the converted `-actual.csv` file.
2. Set the date format to `YYYY-MM-DD`, map Date / Payee / Notes / Amount.
3. Leave "flip amount" off — the converter already outputs negative-for-outflow.

Actual remembers the mapping per account, so this is one-time setup.

> **Tip:** Chase, Citi, and Amex also offer QFX ("Quicken") downloads, which
> Actual imports natively with no mapping at all. This converter is for the
> accounts and date ranges where CSV is what you can get.

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
