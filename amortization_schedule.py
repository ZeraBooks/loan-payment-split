"""Build a loan amortization schedule: the principal and interest in every payment.

Monthly interest is the balance owed x annual rate / 12, rounded to the cent.
The rest of the payment reduces the principal. The payment is the standard
level payment for the amount, rate and term, rounded to the cent, and the last
payment is adjusted so the loan ends at exactly 0.00.

Usage:
  python3 amortization_schedule.py AMOUNT RATE_PERCENT MONTHS FIRST_PAYMENT_DATE [out.csv]
  python3 amortization_schedule.py 36000 7.20 36 2026-01-02 sample-schedule.csv
Python 3, standard library only.
"""
import csv
import sys
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, getcontext

getcontext().prec = 28
CENT = Decimal("0.01")


def add_months(start, n):
    y, m = divmod(start.month - 1 + n, 12)
    return date(start.year + y, m + 1, min(start.day, 28))


def schedule(amount, rate_percent, months, first):
    r = rate_percent / Decimal(100) / Decimal(12)
    if r == 0:
        payment = (amount / months).quantize(CENT, ROUND_HALF_UP)
    else:
        payment = (amount * r / (1 - (1 + r) ** -months)).quantize(CENT, ROUND_HALF_UP)
    balance = amount
    rows = []
    for n in range(1, months + 1):
        interest = (balance * r).quantize(CENT, ROUND_HALF_UP)
        principal = payment - interest
        if n == months:
            principal = balance
        balance -= principal
        rows.append({"Payment": n, "Date": add_months(first, n - 1).isoformat(),
                     "Total paid": principal + interest, "Interest": interest,
                     "Principal": principal, "Balance after": balance})
    return payment, rows


def main(argv):
    if len(argv) < 4:
        print(__doc__)
        return 2
    amount, rate, months = Decimal(argv[0]), Decimal(argv[1]), int(argv[2])
    first = date.fromisoformat(argv[3])
    payment, rows = schedule(amount, rate, months, first)
    total_interest = sum(r["Interest"] for r in rows)
    total_principal = sum(r["Principal"] for r in rows)
    print(f"Loan {amount:,.2f} at {rate}% for {months} months: payment {payment:,.2f}")
    print(f"{'No.':>4}  {'Date':<10} {'Total paid':>11} {'Interest':>10} {'Principal':>11} {'Balance after':>14}")
    for r in rows:
        print(f"{r['Payment']:>4}  {r['Date']:<10} {r['Total paid']:>11,.2f} {r['Interest']:>10,.2f} {r['Principal']:>11,.2f} {r['Balance after']:>14,.2f}")
    print(f"Total interest {total_interest:,.2f}, total principal {total_principal:,.2f}")
    if total_principal != amount or rows[-1]["Balance after"] != 0:
        print("The schedule doesn't pay the loan down to zero. Check the inputs.")
        return 1
    if len(argv) > 4:
        with open(argv[4], "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["Payment", "Date", "Total paid", "Interest", "Principal", "Balance after"])
            for r in rows:
                w.writerow([r["Payment"], r["Date"], f"{r['Total paid']:.2f}", f"{r['Interest']:.2f}",
                            f"{r['Principal']:.2f}", f"{r['Balance after']:.2f}"])
        print(f"Written to {argv[4]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
