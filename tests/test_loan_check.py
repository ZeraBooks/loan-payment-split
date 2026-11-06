import csv
import glob
import json
import os
import re
import subprocess
import sys
import unittest
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "cli"))
sys.path.insert(0, ROOT)
import loan_check as lc  # noqa: E402
from amortization_schedule import schedule  # noqa: E402

S = os.path.join(ROOT, "samples")


def errors(issues):
    return [i for i in issues if i.severity == "error"]


def rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


class Schedules(unittest.TestCase):
    def test_every_sample_schedule_passes_with_its_rate(self):
        for r in rows(os.path.join(S, "loans.csv")):
            issues, summary = lc.check_schedule(os.path.join(S, "schedules", r["Loan"] + ".csv"), r["Annual rate %"])
            self.assertEqual(errors(issues), [], r["Loan"])
            self.assertEqual(summary["amount"], r["Amount"])
            self.assertEqual(summary["total_interest"], r["Total interest"])
            self.assertEqual(summary["payments"], int(r["Months"]))

    def test_root_sample_is_the_kestrel_schedule(self):
        a = open(os.path.join(ROOT, "sample-schedule.csv"), encoding="utf-8").read()
        b = open(os.path.join(S, "schedules", "kestrel-press.csv"), encoding="utf-8").read()
        self.assertEqual(a, b)

    def test_kestrel_figures_match_the_guide(self):
        payment, sched = schedule(Decimal("36000"), Decimal("7.20"), 36, __import__("datetime").date(2026, 1, 2))
        self.assertEqual(payment, Decimal("1114.87"))
        self.assertEqual([str(r["Interest"]) for r in sched[:3]], ["216.00", "210.61", "205.18"])
        self.assertEqual(str(sum(r["Principal"] for r in sched[:3])), "2712.82")
        self.assertEqual(str(sched[2]["Balance after"]), "33287.18")
        self.assertEqual(str(sched[-1]["Total paid"]), "1114.89")
        self.assertEqual(str(sum(r["Interest"] for r in sched)), "4135.34")

    def test_zero_rate_loan_spreads_rounding_to_last_payment(self):
        sched = rows(os.path.join(S, "schedules", "cobalt-oven.csv"))
        self.assertTrue(all(r["Interest"] == "0.00" for r in sched))
        self.assertEqual(sched[0]["Total paid"], "520.83")
        self.assertEqual(sched[-1]["Total paid"], "520.87")
        self.assertEqual(sum(Decimal(r["Principal"]) for r in sched), Decimal("6250.00"))

    def test_lender_mode_turns_interest_errors_into_warnings(self):
        path = os.path.join(S, "invalid", "interest-not-balance-times-rate.csv")
        issues, _ = lc.check_schedule(path, "7.20", "lender")
        self.assertEqual(errors(issues), [])
        self.assertTrue(any(i.rule == "LOAN-002" for i in issues))


class Invalid(unittest.TestCase):
    def test_each_invalid_file_fails_only_its_rule(self):
        expected = json.load(open(os.path.join(S, "invalid", "expected.json"), encoding="utf-8"))
        files = sorted(os.path.basename(p) for p in glob.glob(os.path.join(S, "invalid", "*.csv")))
        self.assertEqual(sorted(expected), files)
        for name, exp in expected.items():
            out = subprocess.run([sys.executable, os.path.join(ROOT, "cli", "loan_check.py"), "--json", exp["command"],
                                  os.path.join(S, "invalid", name)] + exp["args"], capture_output=True, text=True)
            self.assertEqual(out.returncode, 1, name)
            got = {i["rule"] for i in json.loads(out.stdout)["issues"] if i["severity"] == "error"}
            self.assertEqual(got, {exp["rule"]}, name)

    def test_unreadable_file_exits_2(self):
        out = subprocess.run([sys.executable, os.path.join(ROOT, "cli", "loan_check.py"), "schedule", "nope.csv"],
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 2)


class Entries(unittest.TestCase):
    def test_every_books_file_balances(self):
        for p in glob.glob(os.path.join(S, "books", "*.csv")) + [os.path.join(ROOT, "sample-journal-entries.csv")]:
            issues, _ = lc.check_entries(p)
            self.assertEqual(errors(issues), [], p)


class Reconcile(unittest.TestCase):
    LENDER = os.path.join(S, "lender-statements", "kestrel-press-2026-q1.csv")

    def run_books(self, name):
        return lc.reconcile(self.LENDER, os.path.join(S, "books", f"kestrel-press-{name}.csv"))

    def test_correct_books_tie_every_month(self):
        issues, summary = self.run_books("correct")
        self.assertEqual(issues, [])
        self.assertEqual([m["books_balance"] for m in summary["months"]], ["35101.13", "34196.87", "33287.18"])
        self.assertEqual(summary["opening_principal"], "36000.00")

    def test_whole_payment_expensed_is_diagnosed(self):
        issues, summary = self.run_books("whole-payment-expensed")
        self.assertEqual(summary["months"][-1]["difference"], "2712.82")
        self.assertIn("booked as an expense", errors(issues)[-1].message)
        self.assertTrue(any(i.rule == "LOAN-008" for i in issues))

    def test_whole_payment_to_loan_is_diagnosed(self):
        issues, summary = self.run_books("whole-payment-to-loan")
        # 631.79 interest + 35.00 late fee went to the loan.
        self.assertEqual(summary["months"][-1]["difference"], "-666.79")
        self.assertIn("interest and fees to date", errors(issues)[-1].message)

    def test_missing_payment_is_found_in_its_month(self):
        issues, summary = self.run_books("march-not-recorded")
        self.assertEqual(summary["first_difference"], "2026-03-13")
        self.assertEqual(summary["months"][-1]["difference"], "909.69")

    def test_alder_creek_ties_through_october(self):
        issues, summary = lc.reconcile(os.path.join(S, "lender-statements", "alder-creek-van-2026.csv"),
                                       os.path.join(S, "books", "alder-creek-van-correct.csv"))
        self.assertEqual(issues, [])
        self.assertEqual(summary["statements"], 8)


class Split(unittest.TestCase):
    def test_kestrel_year_end_split(self):
        _, s = lc.current_split(os.path.join(S, "schedules", "kestrel-press.csv"), "2026-12-31")
        self.assertEqual((s["balance"], s["current_portion"], s["long_term_portion"]), ("24850.39", "11979.42", "12870.97"))
        self.assertEqual(Decimal(s["current_portion"]) + Decimal(s["long_term_portion"]), Decimal(s["balance"]))

    def test_split_before_first_payment_uses_full_amount(self):
        _, s = lc.current_split(os.path.join(S, "schedules", "cobalt-oven.csv"), "2026-01-15")
        self.assertEqual((s["balance"], s["current_portion"], s["long_term_portion"]), ("6250.00", "6250.00", "0.00"))


class Schemas(unittest.TestCase):
    def check(self, schema_name, paths):
        schema = json.load(open(os.path.join(ROOT, "schema", schema_name), encoding="utf-8"))
        for p in paths:
            with open(p, newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                self.assertEqual(reader.fieldnames, schema["required"], p)
                for row in reader:
                    for k, v in row.items():
                        pat = schema["properties"][k].get("pattern")
                        if pat:
                            self.assertRegex(v, re.compile(pat), f"{p} {k}")

    def test_samples_match_schemas(self):
        self.check("amortization-schedule.schema.json", glob.glob(os.path.join(S, "schedules", "*.csv")))
        self.check("lender-statement.schema.json", glob.glob(os.path.join(S, "lender-statements", "*.csv")))
        self.check("journal-entry-line.schema.json", glob.glob(os.path.join(S, "books", "*.csv")))


if __name__ == "__main__":
    unittest.main()
