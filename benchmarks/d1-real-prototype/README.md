# Experimental real-mariamem D1 adapter

Not a product API. See docs/reviews/d1-v061-real-prototype.md for semantic differences and evidence.

Use Python3.11 with Django5.2.8, pytest9.0.2, pytest-django4.12.0, mysqlclient2.2.7 and the published mariamem0.6.0 wheel. The report pins the exact macOS wheel/host hashes. mysqlclient needs Connector/C (observed3.4.11). Do not put repo/python before the installed wheel on PYTHONPATH.

Set MARIAMEM_EXPERIMENT_TEMP to a new empty scratch directory, run `python benchmarks/d1-real-prototype/run_probe.py` under a finite timeout/disk guard. D1_PILOT=1 selects the two healthy cases only. Each runner process owns an SDK shared host. Migration/seed uses the authored orders app on disposable schema test_d1.

RealOwner uses public SDK snapshot/fork/wait_disconnected/close. boot.py reads private session reap/root fields for diagnostics only. The inherited remaining_databases=[] field is a compatibility placeholder, not a schema census. Expected failures remain nonzero; harness PASS means the specified control matched.
