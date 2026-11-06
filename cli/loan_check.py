#!/usr/bin/env python3
"""Check loan schedules, loan journal entries and the loan balance in your books.

    python3 cli/loan_check.py schedule FILE.csv [--rate 7.20] [--interest monthly|lender]
    python3 cli/loan_check.py entries FILE.csv
    python3 cli/loan_check.py reconcile --lender LENDER.csv --books ENTRIES.csv
    python3 cli/loan_check.py split FILE.csv --as-of 2026-12-31

Every check has a rule ID from rules/loan-rules.csv. Add --json to any command
for machine-readable output. Exit code 0 means no errors, 1 means at least one
error, 2 means a file could not be read.

Python 3.8+, standard library only.
Part of https://github.com/ZeraBooks/loan-payment-split
(ZeraBooks, https://www.zerabooks.com/how-to-record-loan-payments).
"""
import argparse
import csv
import datetime as dt
import json
import re
import sys
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
AMOUNT_RE = re.compile(r"^-?(0|[1-9][0-9]*)\.[0-9]{2}$")
SCHEDULE_COLS = ["Payment", "Date", "Total paid", "Interest", "Principal", "Balance after"]
ENTRY_COLS = ["Date", "Memo", "Account", "Debit", "Credit"]
LENDER_COLS = ["Statement date", "Payment received", "Applied to principal",
               "Applied to interest", "Fees", "Principal balance after"]


class Issue:
    def __init__(self, rule, severity, where, message):
        self.rule, self.severity, self.where, self.message = rule, severity, where, message

    def as_dict(self):
        return {"rule": self.rule, "severity": self.severity, "where": self.where, "message": self.message}

    def __str__(self):
        return f"{self.severity.upper():7} {self.rule} {self.where}: {self.message}"


class ReadError(Exception):
    pass


def money(text, issues, where, blank_ok=False):
    """Parse a plain two-decimal amount. Adds LOAN-009 and returns None if it isn't one."""
    text = (text or "").strip()
    if text == "" and blank_ok:
        return ZERO
    if not AMOUNT_RE.match(text):
        issues.append(Issue("LOAN-009", "error", where, f"'{text}' is not a plain amount like 1114.87"))
        return None
    return Decimal(text)


def read_csv(path, columns):
    try:
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            header = reader.fieldnames or []
            rows = list(reader)
    except (OSError, UnicodeDecodeError) as exc:
        raise ReadError(f"can't read {path}: {exc}")
    missing = [c for c in columns if c not in header]
    if missing:
        raise ReadError(f"{path} is missing column(s): {', '.join(missing)}")
    return rows


def parse_date(text, issues, where):
    try:
        return dt.date.fromisoformat((text or "").strip())
    except ValueError:
        issues.append(Issue("LOAN-004", "error", where, f"'{text}' is not a YYYY-MM-DD date"))
        return None


# ---------------------------------------------------------------- schedule

def check_schedule(path, rate=None, interest_mode="monthly"):
    """Rules LOAN-001 to LOAN-005 and LOAN-009 on an amortization schedule."""
    rows = read_csv(path, SCHEDULE_COLS)
    issues = []
    if not rows:
        issues.append(Issue("LOAN-004", "error", "file", "the schedule has no payment rows"))
        return issues, {}
    parsed = []
    for i, r in enumerate(rows, start=2):
        where = f"line {i}"
        vals = {c: money(r[c], issues, where) for c in SCHEDULE_COLS[2:]}
        try:
            n = int(r["Payment"])
        except ValueError:
            issues.append(Issue("LOAN-004", "error", where, f"payment number '{r['Payment']}' is not a whole number"))
            n = None
        parsed.append((where, n, parse_date(r["Date"], issues, where), vals))
    if any(i.rule == "LOAN-009" for i in issues):
        return issues, {}

    first = parsed[0][3]
    amount = first["Balance after"] + first["Principal"]
    balance = amount
    monthly = None if rate is None else Decimal(str(rate)) / Decimal(100) / Decimal(12)
    prev_n, prev_date = 0, None
    tot_int = tot_pri = ZERO
    for where, n, when, v in parsed:
        if n is not None and n != prev_n + 1:
            issues.append(Issue("LOAN-004", "error", where, f"payment {n} follows payment {prev_n}; numbers must run 1, 2, 3 with no gaps"))
        if when and prev_date and when <= prev_date:
            issues.append(Issue("LOAN-004", "error", where, f"date {when} is not after the previous payment's {prev_date}"))
        prev_n, prev_date = (n if n is not None else prev_n + 1), (when or prev_date)
        if v["Interest"] + v["Principal"] != v["Total paid"]:
            issues.append(Issue("LOAN-001", "error", where,
                                f"interest {v['Interest']} + principal {v['Principal']} = {v['Interest'] + v['Principal']}, but total paid is {v['Total paid']}"))
        if monthly is not None:
            expected = (balance * monthly).quantize(CENT, ROUND_HALF_UP)
            if v["Interest"] != expected:
                sev = "warning" if interest_mode == "lender" else "error"
                issues.append(Issue("LOAN-002", sev, where,
                                    f"interest should be {balance} x {rate}% / 12 = {expected}, the file has {v['Interest']}"))
        if balance - v["Principal"] != v["Balance after"]:
            issues.append(Issue("LOAN-003", "error", where,
                                f"{balance} - principal {v['Principal']} = {balance - v['Principal']}, but balance after is {v['Balance after']}"))
        balance = v["Balance after"]
        tot_int += v["Interest"]
        tot_pri += v["Principal"]
    if balance != ZERO:
        issues.append(Issue("LOAN-005", "error", parsed[-1][0], f"the last payment leaves {balance} owing; it should clear the loan to 0.00"))
    if tot_pri != amount:
        issues.append(Issue("LOAN-005", "error", "file", f"principal adds to {tot_pri}, but the loan was {amount}"))
    summary = {"amount": str(amount), "payments": len(parsed), "total_interest": str(tot_int),
               "total_principal": str(tot_pri), "total_paid": str(tot_int + tot_pri)}
    return issues, summary


# ---------------------------------------------------------------- entries

def load_entries(path):
    rows = read_csv(path, ENTRY_COLS)
    issues, lines = [], []
    for i, r in enumerate(rows, start=2):
        where = f"line {i}"
        dr = money(r["Debit"], issues, where, blank_ok=True)
        cr = money(r["Credit"], issues, where, blank_ok=True)
        when = parse_date(r["Date"], issues, where)
        if dr is None or cr is None or when is None:
            continue
        if dr and cr:
            issues.append(Issue("LOAN-006", "error", where, "a line has both a debit and a credit; use one or the other"))
        lines.append({"line": i, "date": when, "memo": r["Memo"].strip(), "account": r["Account"].strip(), "debit": dr, "credit": cr})
    return issues, lines


def check_entries(path):
    """LOAN-006: every entry (same date and memo) balances."""
    issues, lines = load_entries(path)
    groups = {}
    for ln in lines:
        groups.setdefault((ln["date"], ln["memo"]), []).append(ln)
    for (when, memo), grp in groups.items():
        dr = sum(g["debit"] for g in grp)
        cr = sum(g["credit"] for g in grp)
        if dr != cr:
            issues.append(Issue("LOAN-006", "error", f"{when} {memo}",
                                f"debits {dr} and credits {cr} differ by {dr - cr}"))
    return issues, {"entries": len(groups), "lines": len(lines)}


# ---------------------------------------------------------------- reconcile

def reconcile(lender_path, books_path, loan_account="Loan payable", interest_account="Interest expense"):
    """LOAN-007 and LOAN-008: the books' loan balance against the lender's statements."""
    rows = read_csv(lender_path, LENDER_COLS)
    issues = []
    stmts = []
    for i, r in enumerate(rows, start=2):
        where = f"lender line {i}"
        vals = {c: money(r[c], issues, where, blank_ok=(c == "Fees")) for c in LENDER_COLS[1:]}
        when = parse_date(r["Statement date"], issues, where)
        if None in vals.values() or when is None:
            continue
        applied = vals["Applied to principal"] + vals["Applied to interest"] + vals["Fees"]
        if applied != vals["Payment received"]:
            issues.append(Issue("LOAN-001", "error", where,
                                f"principal + interest + fees = {applied}, but the lender received {vals['Payment received']}"))
        stmts.append((when, vals))
    entry_issues, lines = load_entries(books_path)
    issues.extend(entry_issues)
    if not stmts:
        issues.append(Issue("LOAN-007", "error", "file", "no lender statement rows to compare"))
        return issues, {}
    stmts.sort(key=lambda s: s[0])
    first = stmts[0][1]
    opening = first["Principal balance after"] + first["Applied to principal"]

    months = []
    cum_pri = cum_int = cum_fee = ZERO
    first_bad = None
    for when, v in stmts:
        cum_pri += v["Applied to principal"]
        cum_int += v["Applied to interest"]
        cum_fee += v["Fees"]
        upto = [ln for ln in lines if ln["date"] <= when]
        books = sum(ln["credit"] - ln["debit"] for ln in upto if ln["account"] == loan_account)
        booked_int = sum(ln["debit"] - ln["credit"] for ln in upto if ln["account"] == interest_account)
        lender = v["Principal balance after"]
        diff = books - lender
        row = {"date": when.isoformat(), "lender_balance": str(lender), "books_balance": str(books),
               "difference": str(diff), "interest_lender_to_date": str(cum_int), "interest_booked_to_date": str(booked_int)}
        if diff != ZERO:
            if books == opening and diff == cum_pri:
                why = (f"the books still show the full {opening}: the principal ({cum_pri}) was booked as an expense. "
                       "Move it back to the loan with a correcting entry")
            elif diff == -(cum_int + cum_fee) or diff == -cum_int:
                why = (f"the books are {-diff} below the lender, which is the interest"
                       f"{' and fees' if diff == -(cum_int + cum_fee) and cum_fee else ''} to date: whole payments went to the loan. "
                       "Move the interest, and any fee, out of the loan account")
            else:
                why = "look for a payment that is missing, dated in the wrong month, or split differently from the lender's statement"
            issues.append(Issue("LOAN-007", "error", when.isoformat(),
                                f"books show {books}, the lender shows {lender}, off by {diff:+}. Likely cause: {why}"))
            first_bad = first_bad or when.isoformat()
        row["ties"] = diff == ZERO
        months.append(row)
    if cum_int > ZERO and not any(ln["account"] == interest_account and ln["debit"] for ln in lines):
        issues.append(Issue("LOAN-008", "warning", "file",
                            f"the lender charged {cum_int} interest, but nothing was booked to {interest_account}"))
    summary = {"opening_principal": str(opening), "statements": len(months), "first_difference": first_bad, "months": months}
    return issues, summary


# ---------------------------------------------------------------- split

def current_split(path, as_of):
    """Year-end split: principal due in the 12 months after as_of is current, the rest long term."""
    issues, _ = check_schedule(path)
    errors = [i for i in issues if i.severity == "error"]
    if errors:
        return issues, {}
    rows = read_csv(path, SCHEDULE_COLS)
    as_of = dt.date.fromisoformat(as_of)
    try:
        year_later = as_of.replace(year=as_of.year + 1)
    except ValueError:  # February 29
        year_later = dt.date(as_of.year + 1, 2, 28)
    paid = [r for r in rows if dt.date.fromisoformat(r["Date"]) <= as_of]
    first = rows[0]
    balance = Decimal(paid[-1]["Balance after"]) if paid else Decimal(first["Balance after"]) + Decimal(first["Principal"])
    current = sum((Decimal(r["Principal"]) for r in rows if as_of < dt.date.fromisoformat(r["Date"]) <= year_later), ZERO)
    summary = {"as_of": as_of.isoformat(), "balance": str(balance), "current_portion": str(current),
               "long_term_portion": str(balance - current), "payments_in_next_12_months":
               sum(1 for r in rows if as_of < dt.date.fromisoformat(r["Date"]) <= year_later)}
    return issues, summary


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description="Check loan schedules, entries and balances.")
    ap.add_argument("--json", action="store_true", help="print the result as JSON")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("schedule", help="check an amortization schedule")
    s.add_argument("file")
    s.add_argument("--rate", help="annual rate in percent, e.g. 7.20, to check each month's interest")
    s.add_argument("--interest", choices=["monthly", "lender"], default="monthly",
                   help="'lender' turns interest mismatches into warnings, for lenders that charge by the day")
    e = sub.add_parser("entries", help="check that every journal entry balances")
    e.add_argument("file")
    r = sub.add_parser("reconcile", help="compare the books' loan balance with the lender's statements")
    r.add_argument("--lender", required=True)
    r.add_argument("--books", required=True)
    r.add_argument("--loan-account", default="Loan payable")
    r.add_argument("--interest-account", default="Interest expense")
    p = sub.add_parser("split", help="current and long-term portions at a date")
    p.add_argument("file")
    p.add_argument("--as-of", required=True)
    args = ap.parse_args(argv)

    try:
        if args.cmd == "schedule":
            issues, summary = check_schedule(args.file, args.rate, args.interest)
        elif args.cmd == "entries":
            issues, summary = check_entries(args.file)
        elif args.cmd == "reconcile":
            issues, summary = reconcile(args.lender, args.books, args.loan_account, args.interest_account)
        else:
            issues, summary = current_split(args.file, args.as_of)
    except ReadError as exc:
        print(f"ERROR   {exc}", file=sys.stderr)
        return 2

    has_error = any(i.severity == "error" for i in issues)
    if args.json:
        print(json.dumps({"ok": not has_error, "issues": [i.as_dict() for i in issues], "summary": summary}, indent=2))
    else:
        for i in issues:
            print(i)
        if args.cmd == "reconcile" and summary:
            for m in summary["months"]:
                mark = "ties" if m["ties"] else f"off by {Decimal(m['difference']):+,.2f}"
                print(f"{m['date']}  lender {Decimal(m['lender_balance']):>12,.2f}  books {Decimal(m['books_balance']):>12,.2f}  {mark}")
        elif args.cmd == "split" and summary:
            print(f"At {summary['as_of']}: loan balance {Decimal(summary['balance']):,.2f} = current "
                  f"{Decimal(summary['current_portion']):,.2f} + long term {Decimal(summary['long_term_portion']):,.2f}")
        elif summary:
            print("Summary: " + ", ".join(f"{k} {v}" for k, v in summary.items()))
        print("No errors." if not has_error else "Errors found; see above.")
    return 1 if has_error else 0


if __name__ == "__main__":
    sys.exit(main())
