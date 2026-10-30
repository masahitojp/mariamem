# P1 wire source reconciliation after main update

Current inspected main source_commit: `2ad041cd8ec9f8c66d49f34200d36b0a07875099`.
This updates the active source hash baseline for P1/G1 design lint, not the
historical approvals, claims or receipts in the
[cc00ccd inventory](v06x-wire-current-inventory.md). Its capability/path table
remains the starting coverage map, with the main change below explicitly added.
No new protocol support or new native/workload PASS is claimed here.

Comparing the four pinned host/guest wire files at cc00ccd and this main shows
only three added lines in internal/mysqlwire/wire.go: before command dispatch,
check p.Err() and return commandFailure for a terminal worker error. The prepared
session, guest wire core and resident source files are unchanged. No dispatch
case or advertised capability expression changed. The contract retains QUIT1,
INIT_DB2, QUERY3, PING14, Prepared22-26 and SET_OPTION27; the existing unsupported
paths remain separate and are not relabelled supported.

This main also contains approved TEXT FD duplication and terminal-worker failure
repairs plus their detection net. They are inherited product prerequisites, not
P1 engine patches. Existing worker-failure unit/integration owners and Issue13
records retain their original scope. P1 must rerun against this new host source;
its earlier local bdda0cf/a81f91d results remain bound to the older host and must
not be relabelled as this candidate.

The contract keeps its original design source_commit and G1 reviewed design
unchanged, while wire.source_commit independently pins the source being compared.
check_fixture_design.py verifies both current bytes and that Git commit's bytes,
and still recomputes dispatch/capability inventories. A new negative condition
rejects substitution of the old source SHA for the changed host file. The
Human-approved P1 input/diagnostic/admission definitions remain unchanged.

| File | SHA256 at inspected main |
| --- | --- |
| internal/mysqlwire/wire.go | 8a2991512654e9efcf4d15af010f013e6caddbe4f1ff078c7bb62a79881daa5f |
| internal/mysqlwire/prepared_session.go | 3591c671a67b87e1fed52eef27638006626e28c0d99437014b332d01abecd0bf |
| guest/wire_core.inc | c2d26e0829967fa916498046d9a88f7042677ea6c8ebcb7ab67055612ab38d7a |
| guest/resident.inc | 9ef6a75f9f4146f4842829fdf1dba7fed0a923e45daf89fbcd2c4d31b1e94a4c |
