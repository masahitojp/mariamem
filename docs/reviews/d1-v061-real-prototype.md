# D1 real-mariamem local prototype

2026-11-01. Recommendation: the explicit Django adapter is feasible enough for product design, subject to an explicit class-setup semantics decision. This experiment is not a finished product entry or completion of Issue43.

## Result and principal objection

The class-materialization/per-test-Fork model executed with real mariamem0.6.0 and mysqlclient under both DiscoverRunner and pytest-django. Existing SDK capture/fork/disconnect/close operations were sufficient; no guest, wire or production SDK change was needed.

The principal objection remains a semantic change: standard TestCase class setup is inside a class-wide atomic transaction; this prototype materializes it into the class baseline. setUpTestData runs once and TestData object-copying/per-test atomics remain, but class-setup transaction/on_commit assumptions may differ. Recommend an explicit opt-in prepared test base rather than silently changing standard TestCase. Human agreement is needed before product implementation/adoption.

## Fixed identity and environment

- Published product source_commit: b3b3b46a8807482ad3f96725af86e031fe369b01, v0.6.0.
- [Published macOS wheel](https://github.com/masahitojp/mariamem/releases/tag/v0.6.0) SHA256:0c49fcd9f571851d8d37c6ec0fd089fad45609b281dc4fb0e8479819752e1519; download matched the GitHub asset digest before installation.
- Host SHA256:b467baece270d6d3cb0770781695c1960de2c0d9c4bd536d6aac2c14f37c1e2a, matching the wheel manifest. Go1.26.10 build metadata has the exact product vcs.revision above and vcs.modified=false.
- Executed final prototype source_commit:5b84cbdf71f0898b2f4c27a0c3fd11a7eca5caee. Git identity was checked; assessment binds all six executed Python source hashes. Pilot was before this commit and is separate diagnostic evidence.
- Local macOS27.2 arm64, Python3.11.18, Django5.2.8, pytest9.0.2, pytest-django4.12.0, mysqlclient2.2.7, Connector/C3.4.11. Environment, native extension hash and installed dependency records are saved.
- Authored orders model and two migrations reused unchanged. Prepared state includes migration SEED and a non-model SQL sentinel table containing17. Each test checks SELECT DATABASE() returns test_d1.

## Implementation boundary

[Prototype/reproduction](../../benchmarks/d1-real-prototype/README.md) retains the explicit Django class mixin and runner/pytest seam. RealOwner wraps public SDK objects instead of copying SQLite files. Endpoint activation now updates the real MySQL host/port while retaining the test schema. Framework connections close before wait_disconnected and capture/database retirement. Snapshot consumes the source.

The SDK source starts before Django reads settings. Django creates/migrates test_d1 and preparation adds the sentinel before run-baseline capture. Each class prepares a source child; capture waits until user setUpClass has returned. Test methods get independent children. Final Django database teardown uses another disposable child before final SDK close. Private session fields in boot.py are diagnostic observations, not control operations.

Close/capture failure controls are injected immediately before the SDK operation: they exercise adapter error/admission policy, not every actual guest failure mode. The prepare failure occurs after partial sentinel DDL and before capture.

## Finite results

[Final assessment](d1-v061-real-prototype-evidence/final/assessment.json), [logs/events/environment/checksums](d1-v061-real-prototype-evidence/).

Each runner matched all10 cases,20 assessed outcomes total:

| Case | Observed |
| --- | --- |
| Healthy / reverse |4 bodies each; migration/seed/raw sentinel restored; class data once and user class setup after super retained; exit0 |
| Commit plus deliberate assertion failure |on_commit fired and an independent physical mysqlclient connection saw the committed row; next case restored prepared schema/seed; original raw FAIL retained |
| Class setup failure / skip |No body from rejected/skipped class; later class ran; original error/SKIP retained |
| Close failure / combined test+close failure |Owner unclosed at injection; next body refused by cleanup debt; original assertion and cleanup error retained; final cleanup retires owners |
| Partial preparation / capture failure |No test bodies; original injected errors retained; owners disposed |
| Restoration disabled control |Next transactional case fails baseline assertions; functional failure remains FAIL |

All final cases recorded no open tracked owners, SDK host reap and temporary-root removal. The parent harness also checked host PID disappearance. This is lifecycle evidence in one local profile, not a process-tree memory/FD census. The inherited empty remaining_databases field is not an enumeration and is not used as proof.

The healthy pilot ran4 test bodies per runner and completed final Django DB teardown. No product build, guest regeneration or heavy CI was started. Timing printed by the framework is not a performance claim.

## Evidence correction

While recording this run, the evidence collector resolved a venv interpreter symlink to its global Python executable. That command failed importing mariamem before writing environment.json. It was corrected to invoke the venv path directly; current environment.json and requirements.txt come from the executing environment. This also exposed that the earlier SQLite prototype's freeze artifact is empty. Its raw outcome/source hashes remain valid, but that file is not a complete dependency record. The earlier top-level versions were fixed by installation commands; its reproduction requirements now state those core pins explicitly, without inventing a historical transitive freeze.

## Remaining scope and next decision

Not tested: hosted Ubuntu24.04/macOS15 profiles, Python3.14, native MariaDB parity, function-style pytest, parallel/xdist/async/multiple aliases, arbitrary class transactions, serialized rollback/available_apps, unregistered retained connections and actual SDK fault modes beyond adapter injections. Existing engine release acceptance is separate from this adapter evidence.

Next decide whether a bounded prepared entry may materialize class setup, or full standard class-transaction semantics must be retained. If selected, reduce prototype duplication into a maintained adapter, fix the public API/docs/unsupported-option rejection, strengthen real failure controls, and add targeted supported-profile acceptance under the current Release-only policy. Do not merge this exploratory branch as product code. Issue43 remains open.
