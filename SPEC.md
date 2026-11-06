# Loan payment split spec, v1.1.0

This spec defines three CSV files that together let anyone check how a business loan is booked: the amortization schedule, the lender's statements and the journal entries. The checker in `cli/loan_check.py` applies the rules in `rules/loan-rules.csv` to them. JSON Schemas for one row of each file are in `schema/`.

Conventions for every file:

- UTF-8, comma separated, one header row, column names exactly as below.
- Dates are `YYYY-MM-DD`.
- Amounts are plain numbers with two decimals: `1114.87`. No `$`, no thousands comma, no parentheses (LOAN-009).
- Amounts in these files are positive. Direction comes from the column (Debit or Credit, Principal or Interest), not from a sign.

## 1. Amortization schedule

`schema/amortization-schedule.schema.json`. One row per payment.

| Column | Meaning |
|---|---|
| Payment | 1 to N, no gaps (LOAN-004) |
| Date | Due date. Each one later than the last (LOAN-004) |
| Total paid | Interest + Principal (LOAN-001) |
| Interest | Balance before x annual rate / 12, rounded half up to the cent (LOAN-002) |
| Principal | Total paid - Interest |
| Balance after | Balance before - Principal (LOAN-003). 0.00 on the last row (LOAN-005) |

The amount borrowed is not a column. It is worked out from the first row: Balance after + Principal. The principal column must add up to it (LOAN-005).

How the level payment is found, for a monthly rate r = annual rate / 12 and n payments:

```
payment = amount x r / (1 - (1 + r)^-n), rounded to the cent
payment = amount / n, rounded to the cent, when the rate is 0
```

Rounding the payment leaves a few cents over or short by the end, so the last payment is whatever clears the balance. For the Kestrel sample that is 1,114.89 instead of 1,114.87.

Lenders that charge interest by the day (actual days between payments) will differ from LOAN-002 by small amounts, more when a payment is late. Run the checker with `--interest lender` and those differences become warnings. When the lender's statement and the schedule disagree, the statement wins.

## 2. Lender statement

`schema/lender-statement.schema.json`. One row per payment, copied from the lender's monthly statement. Use the figures for this payment, not the year-to-date column.

| Column | Meaning |
|---|---|
| Statement date | Date the lender applied the payment |
| Payment received | Matches the withdrawal on the bank statement |
| Applied to principal | |
| Applied to interest | |
| Fees | Late or other fees in this payment. Blank means 0.00 |
| Principal balance after | What loan payable in the books should show on this date |

Payment received = principal + interest + fees (LOAN-001). The opening principal is the first row's Principal balance after + Applied to principal.

## 3. Journal entries

`schema/journal-entry-line.schema.json`. One row per line. Lines with the same Date and Memo are one entry.

| Column | Meaning |
|---|---|
| Date | Date the cash left the bank |
| Memo | Same on every line of the entry, e.g. `Loan payment 3` |
| Account | Account name. Defaults the checker expects: `Loan payable`, `Interest expense` |
| Debit | Amount, or blank |
| Credit | Amount, or blank |

Every entry balances and no line has both a debit and a credit (LOAN-006).

The standard loan payment entry:

```
Debit  Loan payable          principal
Debit  Interest expense      interest
Debit  Bank and loan fees    fee, if any
Credit Cash: checking        total that left the bank
```

The funding entry when the lender keeps a fee:

```
Debit  Cash: checking        amount received
Debit  Loan fees             fee withheld (or follow your accountant's treatment)
Credit Loan payable          full amount owed
```

## 4. Reconciliation (LOAN-007, LOAN-008)

For each lender statement date D:

```
books balance(D)  = credits - debits to the loan account on or before D
difference(D)     = books balance(D) - lender's Principal balance after(D)
```

Every difference must be 0.00. When one isn't, the checker names a likely cause by matching the difference to a pattern:

| Pattern | Cause |
|---|---|
| Books balance still equals the opening principal, and the difference equals the principal applied to date | Whole payments booked as an expense |
| Difference equals minus the interest to date, or minus interest plus fees | Whole payments booked to the loan |
| Anything else | A missing payment, a payment dated in the wrong month, or a split different from the lender's |

LOAN-008 warns when the lender charged interest and nothing was debited to the interest account.

## 5. Current and long-term portions

At a date D, the loan balance is the Balance after of the last payment on or before D (or the full amount if none). The current portion is the principal in payments dated after D and on or before the same date a year later. Long term is the balance minus the current portion. Interest not yet charged is in neither.

## Versioning

The spec follows semantic versioning. A new rule or column that old files still pass is a minor version. A change that makes old valid files fail is a major version. See `CHANGELOG.md`.
