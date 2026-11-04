# Loan payment split

To record a business loan payment, split it: principal reduces the loan
liability, interest goes to interest expense, and any fee goes to its own
expense line, all credited to the bank account the money left. This repo has a
script that builds the amortization schedule from the amount, rate and term,
a second script that turns each payment into a balanced journal entry, and a
sample 36-month schedule for a fictional equipment loan.

## Files

| File | What it is |
|---|---|
| `amortization_schedule.py` | Builds the schedule: payment, interest, principal and balance after each payment. Interest is balance owed x annual rate / 12. The last payment is adjusted so the loan ends at 0.00. |
| `sample-schedule.csv` | The schedule for the worked example: 36,000.00 at 7.20% over 36 months. |
| `loan_journal_entries.py` | Reads a schedule and prints one journal entry per payment, with an optional fee and actual paid date. Checks every entry balances and the loan balance follows the schedule. |
| `sample-journal-entries.csv` | The entries for the first three payments of the example, with the March late fee. |

Both scripts are Python 3, standard library only.

## How to use it

1. Build the schedule from the loan agreement:

   ```
   python3 amortization_schedule.py 36000 7.20 36 2026-01-02 sample-schedule.csv
   ```

2. Turn the payments you made into entries. Add a fee or a different paid date
   where the lender's statement shows one:

   ```
   python3 loan_journal_entries.py sample-schedule.csv 1 3 --fee 3=35.00 --paid 3=2026-03-13 --out sample-journal-entries.csv
   ```

3. Each month, compare the loan payable balance in your books with the
   principal balance on the lender's statement. When the statement and the
   schedule differ, the statement wins. Many lenders work out interest by the
   day, so a late payment can carry a little more interest than the monthly
   figure.

## The worked example

Kestrel Print Co. is a fictional print shop. On December 1, 2025 it borrowed
36,000.00 for a press at 7.20% fixed over 36 months. The level payment is
1,114.87. Monthly interest on the first payment is 36,000.00 x 7.20% / 12 =
216.00, and the rest is principal. The March payment was late and carried a
35.00 fee.

| Paid | Total paid | Interest | Principal | Fee | Loan balance after |
|---|---|---|---|---|---|
| Balance at funding, Dec 1, 2025 | | | | | 36,000.00 |
| 01/02/2026 | 1,114.87 | 216.00 | 898.87 | 0.00 | 35,101.13 |
| 02/02/2026 | 1,114.87 | 210.61 | 904.26 | 0.00 | 34,196.87 |
| 03/13/2026 | 1,149.87 | 205.18 | 909.69 | 35.00 | 33,287.18 |
| **Three payments** | **3,379.61** | **631.79** | **2,712.82** | **35.00** | |

The proof: 36,000.00 - 2,712.82 = 33,287.18. Over all 36 payments the loan
costs 4,135.34 in interest, and the last payment is 1,114.89 to clear the
rounding.

The entry for the March payment:

| Account | Debit | Credit |
|---|---|---|
| Loan payable | 909.69 | |
| Interest expense | 205.18 | |
| Bank and loan fees | 35.00 | |
| Cash: checking | | 1,149.87 |
| **Totals** | **1,149.87** | **1,149.87** |

When the loan was funded, the lender kept a 1.5% origination fee (540.00), so
35,460.00 arrived in checking. The loan payable account still starts at the
full 36,000.00 owed: debit cash 35,460.00 and the fee 540.00, credit loan
payable 36,000.00. Many small businesses expense a small origination fee when
it is paid. Under U.S. GAAP, loan costs are shown as a reduction of the loan
and spread over its life as interest, so ask your accountant which way your
books should go.

The business and figures are fictional.

## Lines of credit and car loans

**Line of credit.** The balance goes up when you draw and down when you repay,
so there is no fixed schedule. A draw is debit cash, credit line of credit. A
repayment is debit line of credit, credit cash. Interest is charged on what
you have drawn, usually worked out by the day, so take each month's interest
from the lender's statement and book it to interest expense. A minimum payment
that only covers interest has no principal line.

**Car, truck and equipment loans.** Same entries as above, using the schedule
or the lender's statement. The vehicle itself is a separate entry: it goes on
the balance sheet as an asset at its purchase price and is written off over
its life. If you also use the vehicle personally, ask your accountant how the
interest and the vehicle costs are split.

## FAQ

### Is a loan payment an expense?

Only the interest and any fees are. The principal pays back money you
borrowed, so it reduces the loan liability and never appears on the profit and
loss.

### Is the money from a business loan income?

No. Borrowed money is a liability: debit the bank account, credit loan
payable. It raises cash without raising profit, which is why a business can
have money in the bank and still show a loss.

### What if I don't have the lender's statement?

Work out the interest from the balance and the rate: balance owed x annual
rate / 12. The rest of the payment is principal. That is what
`amortization_schedule.py` does. Ask the lender for an amortization schedule or
year-end interest statement and correct the split when it arrives.

## Learn more

Full guide: [How to record loan payments](https://www.zerabooks.com/how-to-record-loan-payments). Related: [ZeraBooks general ledger software](https://www.zerabooks.com/general-ledger-software).

## License

The content and data in this repository are licensed under
[CC BY 4.0](LICENSE). Free to use and adapt with credit to ZeraBooks.
The code (`*.py`) is licensed under [MIT](LICENSE-CODE).

Maintained by [ZeraBooks](https://www.zerabooks.com).
