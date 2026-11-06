"""Write every file in samples/ from the loan terms below.

Run from the repository root:  python3 scripts/generate_samples.py
The output is deterministic: the same terms give the same files, byte for byte.
All businesses, lenders and figures are fictional.
"""
import csv
import json
import os
import sys
from datetime import date
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from amortization_schedule import schedule  # noqa: E402

S = os.path.join(ROOT, "samples")
LOANS = [
    # file stem, business, what it financed, amount, rate %, months, first payment
    ("kestrel-press", "Kestrel Print Co.", "print press", "36000.00", "7.20", 36, date(2026, 1, 2)),
    ("alder-creek-van", "Alder Creek Catering", "refrigerated van", "48500.00", "8.40", 60, date(2026, 3, 15)),
    ("cobalt-oven", "Cobalt Street Bakery", "deck oven, 0% dealer financing", "6250.00", "0", 12, date(2026, 2, 1)),
]
SCHED_COLS = ["Payment", "Date", "Total paid", "Interest", "Principal", "Balance after"]
LENDER_COLS = ["Statement date", "Payment received", "Applied to principal", "Applied to interest", "Fees", "Principal balance after"]
ENTRY_COLS = ["Date", "Memo", "Account", "Debit", "Credit"]


def f2(x):
    return f"{x:.2f}"


def write(rel, header, rows):
    path = os.path.join(S, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def sched_rows(rows):
    return [[r["Payment"], r["Date"], f2(r["Total paid"]), f2(r["Interest"]), f2(r["Principal"]), f2(r["Balance after"])] for r in rows]


def funding(when, amount, fee):
    return [[when, "Loan funded", "Cash: checking", f2(amount - fee), ""],
            [when, "Loan funded", "Loan fees", f2(fee), ""] if fee else None,
            [when, "Loan funded", "Loan payable", "", f2(amount)]]


def main():
    index = []
    schedules = {}
    for stem, biz, what, amount, rate, months, first in LOANS:
        payment, rows = schedule(Decimal(amount), Decimal(rate), months, first)
        schedules[stem] = rows
        write(f"schedules/{stem}.csv", SCHED_COLS, sched_rows(rows))
        index.append([stem, biz, what, amount, rate, months, first.isoformat(), f2(payment),
                      f2(rows[-1]["Total paid"]), f2(sum(r["Interest"] for r in rows))])
    write("loans.csv", ["Loan", "Business", "Financed", "Amount", "Annual rate %", "Months", "First payment",
                        "Level payment", "Last payment", "Total interest"], index)

    # Kestrel, first quarter: March paid late on the 13th with a 35.00 late fee.
    k = schedules["kestrel-press"][:3]
    paid_on = ["2026-01-02", "2026-02-02", "2026-03-13"]
    fees = [Decimal("0"), Decimal("0"), Decimal("35.00")]
    write("lender-statements/kestrel-press-2026-q1.csv", LENDER_COLS,
          [[paid_on[i], f2(r["Total paid"] + fees[i]), f2(r["Principal"]), f2(r["Interest"]), f2(fees[i]), f2(r["Balance after"])]
           for i, r in enumerate(k)])
    fund = [x for x in funding("2025-12-01", Decimal("36000.00"), Decimal("540.00")) if x]

    def book(name, lines_for):
        out = list(fund)
        for i, r in enumerate(k):
            out.extend(lines_for(i, r))
        write(f"books/{name}.csv", ENTRY_COLS, out)

    def right(i, r):
        memo = f"Loan payment {r['Payment']}"
        lines = [[paid_on[i], memo, "Loan payable", f2(r["Principal"]), ""],
                 [paid_on[i], memo, "Interest expense", f2(r["Interest"]), ""]]
        if fees[i]:
            lines.append([paid_on[i], memo, "Bank and loan fees", f2(fees[i]), ""])
        lines.append([paid_on[i], memo, "Cash: checking", "", f2(r["Total paid"] + fees[i])])
        return lines

    def all_expensed(i, r):
        memo = f"Loan payment {r['Payment']}"
        total = f2(r["Total paid"] + fees[i])
        return [[paid_on[i], memo, "Loan payment expense", total, ""], [paid_on[i], memo, "Cash: checking", "", total]]

    def all_to_loan(i, r):
        memo = f"Loan payment {r['Payment']}"
        total = f2(r["Total paid"] + fees[i])
        return [[paid_on[i], memo, "Loan payable", total, ""], [paid_on[i], memo, "Cash: checking", "", total]]

    book("kestrel-press-correct", right)
    book("kestrel-press-whole-payment-expensed", all_expensed)
    book("kestrel-press-whole-payment-to-loan", all_to_loan)
    book("kestrel-press-march-not-recorded", lambda i, r: right(i, r) if i < 2 else [])

    # Alder Creek: lender statements March to October 2026 and books that tie.
    a = schedules["alder-creek-van"][:8]
    write("lender-statements/alder-creek-van-2026.csv", LENDER_COLS,
          [[r["Date"], f2(r["Total paid"]), f2(r["Principal"]), f2(r["Interest"]), "0.00", f2(r["Balance after"])] for r in a])
    out = [x for x in funding("2026-02-13", Decimal("48500.00"), Decimal("0")) if x]
    for r in a:
        memo = f"Van loan payment {r['Payment']}"
        out += [[r["Date"], memo, "Loan payable", f2(r["Principal"]), ""],
                [r["Date"], memo, "Interest expense", f2(r["Interest"]), ""],
                [r["Date"], memo, "Cash: checking", "", f2(r["Total paid"])]]
    write("books/alder-creek-van-correct.csv", ENTRY_COLS, out)

    # Invalid schedules: each one breaks exactly one rule. Built from Kestrel's first six payments.
    base = sched_rows(schedules["kestrel-press"][:6])
    expected = {}

    def bad(name, rows, rule, cmd="schedule", args=None):
        write(f"invalid/{name}.csv", ENTRY_COLS if cmd == "entries" else SCHED_COLS, rows)
        expected[f"{name}.csv"] = {"command": cmd, "args": args or [], "rule": rule}

    def tail_fixed(rows):
        # Six payments don't clear a 36-payment loan, so add one closing row that does.
        last_bal = Decimal(rows[-1][5])
        interest = (last_bal * Decimal("0.006")).quantize(Decimal("0.01"))
        n = int(rows[-1][0]) + 1
        return rows + [[str(n), "2026-07-02", f2(last_bal + interest), f2(interest), f2(last_bal), "0.00"]]

    r = [list(x) for x in base]
    r[1][2] = "1141.87"
    bad("total-not-interest-plus-principal", tail_fixed(r), "LOAN-001")
    r = [list(x) for x in base]
    r[2][3], r[2][4] = "215.18", "899.69"
    bal = Decimal(r[1][5])
    for row in r[2:]:
        bal -= Decimal(row[4])
        row[5] = f2(bal)
    bad("interest-not-balance-times-rate", tail_fixed(r), "LOAN-002", args=["--rate", "7.20"])
    r = [list(x) for x in base]
    r[3][5] = f2(Decimal(r[3][5]) + Decimal("100.00"))
    bad("balance-chain-broken", tail_fixed(r), "LOAN-003")
    bad("does-not-clear", [list(x) for x in base], "LOAN-005")
    r = [list(x) for x in base]
    r = r[:2] + [[str(int(x[0]) + 1)] + x[1:] for x in r[2:]]
    bad("payment-number-gap", tail_fixed(r), "LOAN-004")
    r = [list(x) for x in base]
    r[0][2] = "$1,114.87"
    bad("currency-symbol-in-amount", tail_fixed(r), "LOAN-009")
    e = [x for x in fund] + [["2026-01-02", "Loan payment 1", "Loan payable", "898.87", ""],
                             ["2026-01-02", "Loan payment 1", "Interest expense", "261.00", ""],
                             ["2026-01-02", "Loan payment 1", "Cash: checking", "", "1114.87"]]
    bad("entry-does-not-balance", e, "LOAN-006", cmd="entries")
    with open(os.path.join(S, "invalid", "expected.json"), "w", encoding="utf-8") as fh:
        json.dump(expected, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print("samples written")


if __name__ == "__main__":
    main()
