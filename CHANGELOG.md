# Changelog

## 1.1.0 (2026-11-06)

- `SPEC.md`: the schedule, lender statement and journal entry layouts, the payment formula, the reconciliation and the year-end split.
- JSON Schemas for one row of each file in `schema/`.
- Nine rules with IDs in `rules/loan-rules.csv`.
- `cli/loan_check.py` with four commands: `schedule`, `entries`, `reconcile` (books against the lender, with the likely cause of a difference) and `split` (current and long-term portions). `--json` output and exit codes.
- Samples: three fictional loans (one at 0%), lender statements, Kestrel's first quarter booked four ways, seven invalid files with `expected.json`.
- `scripts/generate_samples.py`, tests, CI, `MANIFEST.json`, `checksums.txt` and a release zip.
- The original scripts and root sample files are unchanged.

## 1.0.0 (2026-11-04)

- `amortization_schedule.py`, `loan_journal_entries.py` and the Kestrel Print Co. sample schedule and entries.
