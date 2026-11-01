# D1 lifecycle prototype (not a product entry)

See `docs/reviews/d1-v061-prototype.md` for evidence and semantic differences.
Uses the repository's authored orders model/migrations, Django5.2.8 and pytest-django4.12.0 on Python3.11 and SQLite file copies. No MariaDB/guest execution.

Install requirements in a disposable Python3.11 venv. Set MARIAMEM_EXPERIMENT_TEMP to a new empty scratch directory and run `python benchmarks/d1-prototype/run_probe.py` from the repo. It starts the two framework runners with per-case file-backed SQLite databases, runs expected failures and a no-restore control, and writes campaign/assessment.json and raw logs/events. Exit0 means all expected outcomes matched, including raw FAILs; it is not a D1 acceptance result.

The script requires a fresh campaign directory. Use a finite timeout and disk budget. Do not import these classes from product code. Prototype changes class setup to committed/materialized data instead of Django's class-wide atomic. Normal per-test TestCase transactions, once-per-class setUpTestData and TestData copying remain; transaction behavior during class setup is different.
