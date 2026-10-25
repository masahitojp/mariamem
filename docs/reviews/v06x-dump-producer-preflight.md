# Explicit TCP producer preflight and direct boundary tests

2026-10-25. Implements the Human's two follow-up requests after observed-host
acquisition acceptance. This is a bounded native preflight change; the stopped
application dump comparison, productization, main integration, Qualification,
release and cold Mac/setup-cost work remain separate.

Base source_commit: `f94a2d4895a838faca3e3bfcafa3aa4ce3a18033`.
Candidate source_commit: `353bf9291d96785f8dcaa3585cec00e56242256e`.
Branch: `experiment/dump-import`. Three files changed: the existing native
workflow, Linux helper and its tests. Product/runtime/guest/converter inputs
remain unchanged.

## What the previous evidence proves

[CI40172057245](https://github.com/masahitojp/mariamem/actions/runs/40172057245),
job121104788865, passed on exact f94a2d4. The saved
[observed receipt](v06x-dump-producer-preflight-evidence/previous-ci-observed.json)
and [PASS result](v06x-dump-producer-preflight-evidence/previous-ci-result.json)
confirm source/program/image identities and the socket startup query. Neither
the health check nor that socket query is asserted producer TCP/root evidence.
No mariadb-dump connection or definer routine creation was part of that guard.

The earlier six local methods called `validate` and `architecture`. Their
source commit/tag/abbreviation checks mutated parsed receipt fields. They did
not exercise Git checkout inspection or Docker collection. The original guard
record now explicitly states that distinction.

## Added native probe

After the unchanged exact native identity checks,
[`producer_probe`](https://github.com/masahitojp/mariamem/blob/353bf9291d96785f8dcaa3585cec00e56242256e/tests/dump_import_spike/linux_acquisition.py)
performs the following on the existing ephemeral Ubuntu native control:

1. Explicit client flags select `--protocol=tcp --host=127.0.0.1 --port=3306
   --user=root`; socket fallback is not used. Record USER()/CURRENT_USER() and
   require root authentication. The authenticated host account may be root@%;
   that is distinct from the selected routine definer.
2. Require the dedicated `mariamem_acquisition_probe` schema to be absent.
   Create only that probe schema, one constant-return procedure and one
   deterministic function, both explicitly `DEFINER='root'@'localhost'
   SQL SECURITY DEFINER`. Compare both metadata rows exactly and execute them
   over TCP, requiring results17 and19.
3. Connect mariadb-dump over the same explicit TCP/root path with the fixed
   producer options, including routines/triggers, events off, hex-blob,
   utf8mb4, single transaction and the selected lock settings. The database
   argument is the probe schema. A unit check compares the option vector with
   the existing producer's literal OPTIONS, excluding its application schema
   argument. Require successful exit and both unchanged definer routine
   definitions in the diagnostic SQL output.
4. Save argv, login, routine metadata/results, diagnostic dump bytes/SHA256 and
   cleanup observations. Finally drop the owned probe schema and assert its
   absence. Existing schemas are not overwritten. Creation/query/dump failure
   still triggers cleanup; failure or failed cleanup cannot emit PASS.

The output is explicitly a **diagnostic routine-only dump**, not a new canonical
application dump, parser input corpus or import result. It is not imported.
The full application producer job remains absent. These assertions target the
chosen Ubuntu canonical producer; no Mac TCP/definer path or cold installation
is established by a Linux probe.

## Direct local verification and its limits

The [25 local methods](https://github.com/masahitojp/mariamem/blob/353bf9291d96785f8dcaa3585cec00e56242256e/tests/dump_import_spike/test_linux_acquisition.py)
passed normally and with Python3.14 `-O`:

| Methods | Execution boundary and coverage |
| --- | --- |
| 6 original assertion/header methods | `validate` mutations and ELF decoding; parsed-record checks only |
| 6 `ActualSourceIdentity` methods | Real temporary Git repos and the actual `source_identity`: clean, tracked/untracked dirty, different HEAD, actual annotated tag object, abbreviated source |
| 6 `CaptureBoundary` methods | Actual `capture` with mocked Docker subprocess responses: complete wiring, inspect manifest/ref mismatch, running-container image mismatch, startup mismatch, process failure, source change on final recheck |
| 7 `TCPProducerProbe` methods | Actual probe with mocked Docker responses: exact option/TCP flags, login/definer separation, existing schema preservation, bad definer/security/results, dump connection failure, omitted routines and cleanup |

Syntax checks, YAML/single-preflight-job/source-SHA wiring checks, public-source
boundary (5250 files) and diff formatting passed. No unchanged product runtime
acceptance was run. The
[verification record](v06x-dump-producer-preflight-evidence/verification.json)
and [checksums](v06x-dump-producer-preflight-evidence/SHA256SUMS.json) preserve
this scope and previous CI receipts.

The Git tests directly exercise real Git. The Docker tests use fixture binaries
and subprocess outputs; they prove rejection/wiring/cleanup logic, not native
Docker behavior or successful TCP routine creation. **Actual TCP/root dump and
definer execution on353bf92 is pending the next native CI submission.** The
handoff returns that exact source and run URL. No old receipt is relabelled;
neither local mocks nor an acquisition PASS proves the stopped dump-import
comparison. A future successful probe closes only this bounded native producer
path on its observed host, before any separately authorized producer resumption.
