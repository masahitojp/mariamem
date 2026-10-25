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

**Native producer preflight: PASS on exact source_commit
`353bf9291d96785f8dcaa3585cec00e56242256e`.**
[Run40173427178](https://github.com/masahitojp/mariamem/actions/runs/40173427178),
[job121108944640](https://github.com/masahitojp/mariamem/actions/runs/40173427178/job/121108944640),
and [artifact12591445500](https://github.com/masahitojp/mariamem/actions/runs/40173427178/artifacts/12591445500)
are archived with their metadata in
[ci-40173427178/](v06x-dump-producer-preflight-evidence/ci-40173427178/).
The [assessment](v06x-dump-producer-preflight-evidence/ci-40173427178/assessment.json)
and [checksums](v06x-dump-producer-preflight-evidence/ci-40173427178/SHA256SUMS.json)
bind the receipts to this source and observed Ubuntu x86_64 control. Application
dump production/comparison, guest import and parser execution remain stopped;
resumption requires a separate Human decision. Views/triggers, cold Mac and
setup-cost evidence are outside this result.

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
and subprocess outputs; they prove rejection/wiring/cleanup logic. The separate
native CI receipt now proves successful TCP routine creation/execution and
diagnostic dump connection on353bf92 for the observed Ubuntu host only:

| Native assertion | Saved result |
| --- | --- |
| Overall result / producer probe | PASS / PASS |
| Exact source | observed.source.source_commit =353bf9291d96785f8dcaa3585cec00e56242256e |
| TCP login | USER()=root@127.0.0.1; CURRENT_USER()=root@% |
| Routine metadata | Both procedure/function use root@localhost and SQL SECURITY DEFINER |
| Routine results | 17 /19 |
| Diagnostic dump | Both CREATE DEFINER markers present;3347 bytes; SHA2566ab704ff278acc72fc8bb807c9c57eaf908957892d86e9c371d421be81a09b1f |
| Probe schema after cleanup | schema_count_after=0 |
| Application dump generated / dump imported / reader executed | false / false / false |

The authenticated ZIP digest is
`sha256:4339934709a3e928310ffebc721281bbbd697ef130da17af8c9515335a664be6`,
matching artifacts.json. All18 extracted artifact members matched their ZIP
bytes before the local assessment/checksum files were added. The archive did
not contain producer-probe.stderr.txt: successful-command stderr is not saved
by this helper. The local file of that name is explicitly an archival absence
note, not captured stderr or proof of empty stderr; assessment.json distinguishes
it from original artifact members.

No old receipt is relabelled:40169643384 remains d19ab2e acquisition,
40172057245 remains f94a2d4 socket-only acquisition, and40173427178 is353bf92
bounded producer preflight. Neither these local tests nor the native PASS proves
the stopped application dump/import comparison. This result closes only the
bounded native producer path on its observed host; no productization, main
integration, Qualification or release was performed.
