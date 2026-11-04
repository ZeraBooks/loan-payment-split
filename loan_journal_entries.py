"""Turn amortization schedule rows into balanced journal entries, one per payment.

Each payment becomes one entry:
  Debit  Loan payable          principal
  Debit  Interest expense      interest
  Debit  Bank and loan fees    any fee paid with it
  Credit Cash: checking        total that left the bank

The script checks every entry balances and that the loan balance after the
payment equals the schedule's balance.

Usage:
  python3 loan_journal_entries.py SCHEDULE.csv [FIRST LAST] [--fee N=AMOUNT] [--paid N=YYYY-MM-DD] [--out entries.csv]
  python3 loan_journal_entries.py sample-schedule.csv 1 3 --fee 3=35.00 --paid 3=2026-03-13 --out sample-journal-entries.csv
Python 3, standard library only.
"""
import csv
import sys
from decimal import Decimal

LOAN, INTEREST, FEES, CASH = "Loan payable", "Interest expense", "Bank and loan fees", "Cash: checking"


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    path, rest = argv[0], argv[1:]
    fees, paid, out, nums = {}, {}, None, []
    i = 0
    while i < len(rest):
        if rest[i] in ("--fee", "--paid", "--out"):
            flag, val = rest[i], rest[i + 1]
            i += 2
            if flag == "--out":
                out = val
            else:
                n, v = val.split("=", 1)
                (fees if flag == "--fee" else paid)[int(n)] = Decimal(v) if flag == "--fee" else v
        else:
            nums.append(int(rest[i]))
            i += 1

    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    first = nums[0] if nums else 1
    last = nums[1] if len(nums) > 1 else (nums[0] if nums else len(rows))
    rows = [r for r in rows if first <= int(r["Payment"]) <= last]
    if not rows:
        print("No payments in that range.")
        return 1

    # Balance before the first payment = its balance after + its principal.
    balance = Decimal(rows[0]["Balance after"]) + Decimal(rows[0]["Principal"])
    ok = True
    lines = []
    tot = {"paid": Decimal(0), "interest": Decimal(0), "principal": Decimal(0), "fee": Decimal(0)}
    print(f"Loan balance before payment {first}: {balance:,.2f}\n")
    for r in rows:
        n = int(r["Payment"])
        principal, interest = Decimal(r["Principal"]), Decimal(r["Interest"])
        fee = fees.get(n, Decimal("0"))
        total = principal + interest + fee
        when = paid.get(n, r["Date"])
        entry = [(LOAN, principal, Decimal(0)), (INTEREST, interest, Decimal(0))]
        if fee:
            entry.append((FEES, fee, Decimal(0)))
        entry.append((CASH, Decimal(0), total))
        debits = sum(e[1] for e in entry)
        credits = sum(e[2] for e in entry)
        balance -= principal
        print(f"{when}  Loan payment {n}")
        for acct, dr, cr in entry:
            print(f"    {acct:<22}{(f'{dr:,.2f}' if dr else ''):>12}{(f'{cr:,.2f}' if cr else ''):>12}")
            lines.append([when, f"Loan payment {n}", acct, f"{dr:.2f}" if dr else "", f"{cr:.2f}" if cr else ""])
        status = "balances" if debits == credits else "DOES NOT BALANCE"
        print(f"    {'Totals':<22}{debits:>12,.2f}{credits:>12,.2f}  {status}")
        if debits != credits:
            ok = False
        if balance != Decimal(r["Balance after"]):
            ok = False
            print(f"    Loan balance {balance:,.2f} doesn't match the schedule's {Decimal(r['Balance after']):,.2f}")
        print(f"    Loan balance after: {balance:,.2f}\n")
        tot["paid"] += total
        tot["interest"] += interest
        tot["principal"] += principal
        tot["fee"] += fee

    print(f"Payments {first} to {last}: paid {tot['paid']:,.2f} = interest {tot['interest']:,.2f}"
          f" + principal {tot['principal']:,.2f} + fees {tot['fee']:,.2f}")
    if out:
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["Date", "Memo", "Account", "Debit", "Credit"])
            w.writerows(lines)
        print(f"Written to {out}")
    print("All entries balance." if ok else "Some entries need a look; see above.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
