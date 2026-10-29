# Issue #5 — bounded host repair candidate

2026-10-29 JST. Implementation authorized by the Human after the
[investigation](issue5-text-dedup.md). This candidate remains
on `experiment/issue5-text-dedup`; main adoption and release are separate.

The implementation binds `Fd_dup` and reports a fatal worker trap promptly,
without releasing memory before every worker has joined. Local macOS results
support submission to both-platform Development CI. Ubuntu acceptance and the
exact submitted-source CI result remain pending; no adoption is recommended
before those results. The material concern is worker/descriptor lifetime during
failure: component ownership controls and an actual generated SQL worker trap
exercise this on macOS, while CI repeats it on both supported hosts.

## Scope and resulting behavior

The approved implementation scope is recorded in `docs/project-status.md`.
No guest source, canonical guest hash, translated guest function body, converter
input, public API, connection limit or Live/Snapshot product contract changed.

- The canonical `generate_runtime.py` driver adaptation delegates `host.Fd_dup`
  to `WasiStubs.Fd_dup`. The duplicate shares the open file and offset, while
  the host records its independent close-on-exec flag as cleared. Descriptor
  closing retains the existing final-reference ownership rule.
- The canonical `runtime_failure.py` helper adaptation retains the first worker
  trap and sends one notification before joining. Its handwritten owner is
  `code/base/runtime_failure.go`, carried through clean installation. Indefinite
  and timed atomic/futex waits can observe the fatal state and exit through the
  ordinary Go panic recovery boundary. Workers starting after failure are
  refused at their entry boundary. Original non-shared/no-pool wait behavior is
  retained by a focused compatibility control.
- `StartInstance` sends that early failure to the linked framed-transport owner.
  `Process.Abort` marks the affected DB unusable, fails pending calls with the
  retained cause and closes transport endpoints. Completion/Done still means
  joined workers and completed resource cleanup. No caller may interpret the
  early notification as permission to unmap a running worker's memory.
- SQL uses the existing fatal wire error2013/HY000 with the original cause,
  rather than reporting a query timeout for the injected import trap. New calls
  are refused; idle sessions also fail locally handled PING on their next
  command. Idle sockets need not receive an unsolicited packet at failure time.
  Independent DB instances have separate failure state.
- Arbitrary non-cooperative Go execution is not forcibly stopped. Such a worker
  retains its resources until it exits; early failure notification still does
  not imply joined cleanup. The controlled running-owner test preserves this
  limitation rather than hiding it with early memory release.

The remaining14 unimplemented host imports stay fail-closed, including `Fd_dup2`.
Only `Fd_dup` was enabled. The finite SQL matrix is not a reachability proof for
all remaining imports or general WASIX compatibility.

## Deterministic acceptance owners

| Boundary | Maintained oracle |
| --- | --- |
| Actual host import, invalid FD/output pointer, shared offset, either close order, per-FD flags | `internal/generatedgo/host_dup_test.go` |
| Underlying file closed exactly once at final alias, no second cleanup close | `code/base/fd_dup_test.go` |
| Prompt single notification, timed/indefinite wait cancellation, remaining owner delays join | `code/base/runtime_failure_test.go` |
| Actual generated OOB worker, root waits for notification, mapping release | `memory_controlled_test.go` |
| Actual MariaDB TEXT DISTINCT hits injected Fd_dup trap, early callback, joined cleanup, independent DB survival | integration-tagged `worker_trap_integration_test.go` |
| Two pending sessions fail before a one-minute deadline and before held completion; next call refused | `internal/guest/worker_failure_test.go` |
| Healthy PING positive control, failed PING2013/HY000/original cause, prompt session close | `internal/mysqlwire/worker_failure_test.go` |
| VARCHAR(1000)/TEXT/BLOB DISTINCT/UNION/GROUP BY/CTAS plus subsequent/sibling SQL | existing `tests/test_python_wire.py` regression |
| Repeated mapped temporary-table use, consuming Snapshot and independent/later Forks | new `test_owned_snapshot.py` case |
| Fresh native28-case reference and guest equality, including CTAS/DML materialization and following SQL | `tests/text_dedup_acceptance.py` |
| Result multiplicity/bytes/affected count/materialization negative controls; adapter preimage drift | new Python unit tests |

The native reference is captured anew per workflow SHA, rather than accepting
the diagnostic patch as the oracle. Guest acceptance verifies a clean built
binary's VCS stamping and the reference's commit/spec/completeness. JSON retains
rows, affected counts and materialized CTAS/INSERT results. SQL row order is not
assumed where the query did not specify it; row multiplicity and binary bytes
are retained. The input data remain intentionally tiny.

## Generation and provenance

The generated output changes are exactly `main.go` and `code/base/base.go`.
The full adapted host driver reproduces from the pinned driver preimage after
gofmt; the changed helper declarations reproduce from their retained preimage.
Changed preimages are rejected. Clean-installer inclusion independently checks
the new handwritten files, including the integration-tagged test.

The provenance changes have an explicit source-only continuity record in
`release/generated-license-evidence.json`, with the distribution hash and Python
mirror updated. Historical attribution/host audit identities and notice bytes
are retained. This is not a new guest/library audit or release qualification.

Historical investigation logs are renamed `.log` → `.txt` without byte changes
so the public-source allowlist accepts them; checksums and local report links
follow the names. The original investigation commit remains immutable and its
GitHub issue links still bind the original evidence.

## Local evidence and CI handoff

Runtime source_commit: `f3ccbb3b0d14784f562a909941a5ec75676dd198`.
The main repair is `e76423d95d7afb1785cf4617559aa0af64ae8ca2`; the final follow-up
retains non-shared/no-pool wait compatibility. Local comparison JSON and the host
build identity bind the runtime SHA explicitly. Later report-only commits must
not relabel these as a new runtime execution.

Local verification receipts and the CI handoff state are recorded with the final
evidence collection. The completed ordinary integration used stock CPython3.14.8/OpenSSL3.5.9,
expanded privately from the repository-pinned actions Python archive. Its C-client
ABI, extension bytes and Python sources match the existing native reference.
An earlier3.11 run correctly failed that profile guard; it is retained as FAIL.
No driver patch, synthetic ssl constant or weakened oracle was used.

Development CI retains its existing check/integration ownership and adds fresh
native-reference and both-host worker-failure jobs for runtime changes. The new
jobs run ownership races, actual guest trap injection, clean-host28-case parity
and SQL/Snapshot/Fork controls. The actual generated guest injection stays out of
race instrumentation, consistent with the existing generated-memory race limit.
No branch-protection change is included.

No dbt replay, performance campaign, blanket SQL compatibility, release
qualification or publication is claimed.

Local results:28/28 native equality; final canonical integration exit0, including
all11 ownership race packages, Go API/default/generated-memory acceptance, actual
SQL worker-trap injection,36 Python runtime tests,33 Snapshot checks, prepared
native matching with the exact existing accepted exceptions, and routing positive/
negative controls. The development-stage canonical check passed1150 Python tests
with51 explicit skips and76 subtests. The final compatibility guard was then
covered by its focused test and the final integration.

See the [source/binary identity](issue5-host-repair-evidence/runtime-identity.json),
[native](issue5-host-repair-evidence/native.json) and
[guest](issue5-host-repair-evidence/guest.json) observations,
[full integration log](issue5-host-repair-evidence/integration314.txt),
[prepared matching](issue5-host-repair-evidence/prepared-matching.json),
[development check](issue5-host-repair-evidence/development-check.txt),
[trial classifications](issue5-host-repair-evidence/trials.json) and
[summary](issue5-host-repair-evidence/summary.json). Authoring path prefixes are
scrubbed; original/stored hashes are recorded. No SQL/oracle value was normalized.

The shared authoring checkout changed to another task's documentation branch.
That state was preserved; verification was stopped and the exact retained candidate
was re-run in an isolated clone. The other branch's run is excluded from evidence.
Both-platform CI remains the next handoff; no CI success is claimed here.

## Cleanup

After confirming no owned host, compiler or verification process remained,
6,233,452,544 bytes of temporary Go caches, binaries, stock Python archives/
frameworks and venvs were removed. Raw consumer binaries were also removed;
source, commands, hashes and compact observations are preserved. The native
container was stopped and removed. See the [cleanup record](issue5-host-repair-evidence/cleanup.json)
and [evidence checksums](issue5-host-repair-evidence/SHA256SUMS). The isolated
source clone is retained only until this committed result is pushed and fetched
back, then removed. Other tasks' source/workspaces and the shared authoring
checkout are outside this cleanup scope and remain preserved.
