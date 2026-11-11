# Loan payment split

To record a business loan payment, split it. Principal reduces the loan liability, interest goes to interest expense, and any fee goes to its own expense line, all credited to the bank account the money left. [ZeraBooks](https://www.zerabooks.com/how-to-record-loan-payments) books the payment to the loan and moves each month's interest out once it knows the rate. This repo lets you build the schedule, write the entries and prove the loan balance in your books against the lender.

What's here:

- A spec for the three files a loan needs: the schedule, the journal entries and the lender's statements ([`SPEC.md`](SPEC.md), [`schema/`](schema/))
- Nine rules with IDs, each with the reason it matters ([`rules/loan-rules.csv`](rules/loan-rules.csv))
- A checker that validates a schedule, checks entries balance, reconciles the books to the lender and splits current from long term at year end ([`cli/loan_check.py`](cli/loan_check.py))
- Fictional loans that add up, books with the common mistakes in them, and files that fail on purpose ([`samples/`](samples/))
- The original two scripts, unchanged: [`amortization_schedule.py`](amortization_schedule.py) and [`loan_journal_entries.py`](loan_journal_entries.py)

Python 3.8+, standard library only. Download everything as a zip from the [latest release](https://github.com/ZeraBooks/loan-payment-split/releases/latest).

## Is my loan balance right?

Compare the loan payable balance in your books with the principal balance on the lender's statement, on the same date. If they match every month, the payments are split right. If they don't, the size of the difference usually tells you what went wrong:

| Books vs lender | What happened | Fix |
|---|---|---|
| Books still show the full amount borrowed, higher by all the principal paid | Whole payments were booked as an expense | One correcting entry: debit loan payable, credit the expense account, for the principal |
| Books lower than the lender by the interest (and fees) to date | Whole payments were booked to the loan | Debit interest expense and fees, credit loan payable |
| Off by one payment's principal in one month | A payment wasn't recorded, or was dated in the next month | Find that month's withdrawal on the bank statement |
| Off by a few cents or dollars | The lender charges interest by the day | Use the lender's split. The statement wins |

`loan_check.py reconcile` does that comparison and names the likely cause.

```bash
python3 cli/loan_check.py reconcile \
  --lender samples/lender-statements/kestrel-press-2026-q1.csv \
  --books samples/books/kestrel-press-whole-payment-expensed.csv
```

```
ERROR   LOAN-007 2026-03-13: books show 36000.00, the lender shows 33287.18, off by +2712.82. Likely cause: the books still show the full 36000.00: the principal (2712.82) was booked as an expense. Move it back to the loan with a correcting entry
WARNING LOAN-008 file: the lender charged 631.79 interest, but nothing was booked to Interest expense
```

## The worked example

Kestrel Print Co. is a fictional print shop. On December 1, 2025 it borrowed 36,000.00 for a press at 7.20% fixed over 36 months. The level payment is 1,114.87. Interest on the first payment is 36,000.00 x 7.20% / 12 = 216.00, and the rest is principal. The March payment was late and carried a 35.00 fee.

| Paid | Total paid | Interest | Principal | Fee | Loan balance after |
|---|---|---|---|---|---|
| Balance at funding, Dec 1, 2025 | | | | | 36,000.00 |
| 01/02/2026 | 1,114.87 | 216.00 | 898.87 | 0.00 | 35,101.13 |
| 02/02/2026 | 1,114.87 | 210.61 | 904.26 | 0.00 | 34,196.87 |
| 03/13/2026 | 1,149.87 | 205.18 | 909.69 | 35.00 | 33,287.18 |
| **Three payments** | **3,379.61** | **631.79** | **2,712.82** | **35.00** | |

The proof: 36,000.00 - 2,712.82 = 33,287.18. And 631.79 + 2,712.82 + 35.00 = 3,379.61, the total that left checking. Over all 36 payments the loan costs 4,135.34 in interest, and the last payment is 1,114.89 to clear the rounding.

The entry for the March payment:

| Account | Debit | Credit |
|---|---|---|
| Loan payable | 909.69 | |
| Interest expense | 205.18 | |
| Bank and loan fees | 35.00 | |
| Cash: checking | | 1,149.87 |
| **Totals** | **1,149.87** | **1,149.87** |

When the loan was funded, the lender kept a 1.5% origination fee (540.00), so 35,460.00 arrived in checking. The loan payable account still starts at the full 36,000.00 owed: debit cash 35,460.00 and loan fees 540.00, credit loan payable 36,000.00. Many small businesses expense a small origination fee when it is paid. Under U.S. GAAP, loan costs are shown as a reduction of the loan and spread over its life as interest, so ask your accountant which way your books should go.

## Same loan, booked four ways

The [`samples/books/`](samples/books/) folder has Kestrel's first quarter booked four ways. Each one runs against the same lender statements:

| File | March 13 loan balance in the books | Lender | Difference | What the checker says |
|---|---|---|---|---|
| `kestrel-press-correct.csv` | 33,287.18 | 33,287.18 | 0.00 | Ties every month |
| `kestrel-press-whole-payment-expensed.csv` | 36,000.00 | 33,287.18 | +2,712.82 | Principal booked as an expense |
| `kestrel-press-whole-payment-to-loan.csv` | 32,620.39 | 33,287.18 | -666.79 | Interest 631.79 and fee 35.00 went to the loan |
| `kestrel-press-march-not-recorded.csv` | 34,196.87 | 33,287.18 | +909.69 | January and February tie, March is off by its principal |

Check the second row by hand: 36,000.00 - 33,287.18 = 2,712.82, which is 898.87 + 904.26 + 909.69. Check the third: 36,000.00 - 3,379.61 = 32,620.39, and 33,287.18 - 32,620.39 = 666.79.

## What goes on the balance sheet at year end?

Principal due in the next 12 months is a current liability. The rest is long term. Your accountant may ask for this split.

```bash
python3 cli/loan_check.py split samples/schedules/kestrel-press.csv --as-of 2026-12-31
```

```
At 2026-12-31: loan balance 24,850.39 = current 11,979.42 + long term 12,870.97
```

The current part is the principal in payments 13 to 24: 24,850.39 - 12,870.97 = 11,979.42. Interest isn't in either number. It hasn't been charged yet.

## The sample loans

All businesses, lenders and figures are fictional. [`scripts/generate_samples.py`](scripts/generate_samples.py) writes every sample from the terms in [`samples/loans.csv`](samples/loans.csv).

| Loan | Amount | Rate | Months | Level payment | Last payment | Total interest |
|---|---|---|---|---|---|---|
| Kestrel Print Co., print press | 36,000.00 | 7.20% | 36 | 1,114.87 | 1,114.89 | 4,135.34 |
| Alder Creek Catering, refrigerated van | 48,500.00 | 8.40% | 60 | 992.72 | 992.44 | 11,062.92 |
| Cobalt Street Bakery, deck oven at 0% | 6,250.00 | 0% | 12 | 520.83 | 520.87 | 0.00 |

The 0% loan is there for the zero-interest case. 6,250.00 / 12 = 520.833, so eleven payments of 520.83 come to 5,729.13 and the last one is 520.87. Every payment is all principal.

| Folder | What's in it |
|---|---|
| `samples/schedules/` | The full schedule for each loan. |
| `samples/lender-statements/` | Kestrel January to March 2026 (with the late fee) and Alder Creek March to October 2026. |
| `samples/books/` | Journal entries: Kestrel four ways, Alder Creek booked right. |
| `samples/invalid/` | Seven files that each break one rule, and `expected.json` naming the rule. |

## Check your own files

```bash
# A schedule from your lender or from amortization_schedule.py
python3 cli/loan_check.py schedule my-schedule.csv --rate 7.20

# Your lender charges by the day? Interest differences become warnings
python3 cli/loan_check.py schedule my-schedule.csv --rate 7.20 --interest lender

# Every entry balances
python3 cli/loan_check.py entries my-entries.csv

# The loan balance against the lender, with your own account names
python3 cli/loan_check.py reconcile --lender lender.csv --books my-entries.csv \
  --loan-account "Note payable - Valley Bank" --interest-account "Interest expense"
```

Add `--json` before the command for machine-readable output. Exit codes: 0 no errors, 1 errors, 2 a file can't be read. The file layouts are in [`SPEC.md`](SPEC.md).

## How ZeraBooks records loan payments

![ZeraBooks Done by AI list: Autopilot split 237.01 of interest out of a March 2026 SBA EIDL loan payment, with Undo next to each entry](https://zerabooks.github.io/images/app/autopilot-month-end-entries.png)

ZeraBooks works from the bank statements you upload. It has no lender or bank connection. A loan payment on the bank statement goes to the loan account. At month end, Autopilot asks for the loan's rate, then moves each month's interest from the loan to Interest Expense: the balance owed x the rate / 12. It never splits interest from a guessed rate, and later months reuse your answer. Every entry is listed in Done by AI, where you can undo it. Upload the lender's statements with the bank statements and Ask Zera uses them as evidence. At year end, Financials flags any loan that received six or more payments with no interest recorded.

ZeraBooks is $79 a month billed annually or $149 month to month, with a 7-day trial. Setup and a catch-up of your past months are free.

## FAQ

### Is a loan payment an expense?

Only the interest and any fees are. The principal pays back money you borrowed, so it reduces the loan liability and never appears on the profit and loss.

### Is the money from a business loan income?

No. Borrowed money is a liability: debit the bank account, credit loan payable. It raises cash without raising profit, which is why a business can have money in the bank and still show a loss.

### What if I don't have the lender's statement?

Work out the interest from the balance and the rate: balance owed x annual rate / 12. The rest of the payment is principal. That is what `amortization_schedule.py` does. Ask the lender for an amortization schedule or year-end interest statement and correct the split when it arrives.

### How do I fix months of payments booked as an expense?

Run `reconcile` against the lender's statements to get the principal that should have gone to the loan. Book one correcting entry per period: debit loan payable, credit the expense account you used. Run it again. Every month should tie.

### What about a line of credit?

The balance goes up when you draw and down when you repay, so there is no fixed schedule. A draw is debit cash, credit line of credit. A repayment is debit line of credit, credit cash. Interest is charged on what you have drawn, usually by the day, so take each month's interest from the lender's statement.

## Run the tests

```bash
python3 scripts/generate_samples.py
python3 scripts/build_manifest.py
python3 -m unittest discover -s tests -v
```

`MANIFEST.json` lists every sample, schema and rules file with its size, row count and SHA-256. Check the hashes with `shasum -a 256 -c checksums.txt`.

## Learn more

Full guide: [How to record loan payments](https://www.zerabooks.com/how-to-record-loan-payments). Related: [ZeraBooks general ledger software](https://www.zerabooks.com/general-ledger-software) and [loan statement to Excel](https://www.zerabooks.com/loan-statement-to-excel).

## License and citation

The content and data in this repository are licensed under [CC BY 4.0](LICENSE). The code (`*.py`) is licensed under [MIT](LICENSE-CODE). Cite it with [`CITATION.cff`](CITATION.cff) or as: ZeraBooks, *Loan Payment Split*, v1.1.0, 2026, https://github.com/ZeraBooks/loan-payment-split.

ZeraBooks is accounting software that does your books for you, with free setup and a free catch-up of your past months. Maintained by [ZeraBooks](https://www.zerabooks.com).
