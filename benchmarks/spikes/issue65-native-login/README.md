# Issue65 step3A — native protocol with embedded bootstrap

**PASS in the tested native Linux/arm64 profile.** One coherent embedded library
can retain its C API/bootstrap and serve native MySQL handshake, text results and
prepared binary results over a memory Vio. The final run passed16 checks with two
sequential physical sessions. Recommend the separately scoped3B concurrency,
flow-control and admission proof next; no WASIX build or product adoption yet.

The decisive evidence is real packet input/output through upstream login,
NET/Protocol and SQL, while product routine bootstrap and MYSQL_BIND execution
work before and after those sessions. Native parameter decoding was entered
three times (two successes and one rejected truncated integer); wire entry and
decode checks require client_params to remain null. No host SQL/result decoder
or replacement server packet encoder was added.

The strongest qualification is the remaining lifecycle/control work and patch
breadth:13 upstream paths, including constructor/layout, Protocol, prepared input,
login and Vio. The resulting experimental.patch is1,047 lines including context,
not a production-ready extraction. Failure cleanup, bounded admission and WASIX
remain material unknowns; a native arithmetic/result proof cannot qualify them.

## Scope and identities

The Human selected3A after [the design](../../../docs/design/issue65-native-protocol/README.md).
This does not authorize stages3B/C/D, main integration, product contract changes,
version selection or release.

- Harness/design starting source_commit:
  `429ce325f0449674968c98f9c264999cafa708fc`.
- MariaDB12.3.3 source_commit:
  `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`.
- Source, Connector/C and fmt archives are checked against release/inputs.lock.json.
  Product reference remains0.6.2 source_commit47121e1be0b399ba4e2270ce3e25c411ade0e2eb.
- All upstream inputs are pristine plus this experiment patch. Product
  portability/alignment/prepared patches are not applied. Canonical
  guest/source.patch and generated-Go source are unchanged.
- Existing image:
  `sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f`.
  Ubuntu24.04 Linux/aarch64, GCC13.3, system OpenSSL3.0.13, zlib1.3, PCRE2 10.42,
  pinned fmt12.2.0. Linux/arm64 is a probe platform, not a supported-product
  host-qualification claim.
- Native static mysqlserver target; Release configuration with
  `-O0 -DNDEBUG -DMARIAMEM_NATIVE_WIRE`. EMBEDDED_LIBRARY stays enabled for every
  embedded translation unit. Runtime checks use abort/need, not disabled asserts.
  No ASan/UBSan or performance comparison. InnoDB and unrelated optional engines
  are disabled; actual proc bootstrap uses the pinned Aria schema.
- This patch requires the experiment flag. A macro-off patched build is not
  implemented or tested. The flag alone is not a production integration guard;
  the isolated experiment branch/experimental.patch is the boundary.
- Budget:2 active hours from05:15 UTC, tooling30min, heavy CI0, owned6GiB,
  free-space floor8GiB. CPU2/memory4GiB container. Individual builds bounded at
  2400s initially,1800s for resumed compilation and300s for small rebuilds.
  Runtime fixture has a45s container timeout and bounded host I/O waits.

## Actual path

```text
Test client fixture -- raw stdin/stdout pipes -- bounded C++ memory queues
                                           -- memory Vio -- server NET
                                           -- native authentication/command loop
                                           -- native Protocol -- embedded SQL
```

No OS socket listener or cgo is used by this probe. The memory Vio has its own
VIO_TYPE_MEMORY and invalid socket descriptor, mapping plugin transport info to
unencrypted TCP semantics. The driver, not MariaDB, pumps OS pipe bytes into/out
of memory queues. This is not yet a Go relay or generated-Go/WASIX experiment.
There was no full syscall trace; the source/normal-run evidence does not claim
a complete audit of every unused Vio/helper branch.

THD's mode is const, supplied to its constructor before its direct Protocol
objects. Existing C API callers default to embedded mode. The factored embedded
THD factory supplies the common query initialization once; wire sessions then
use actual acl_authenticate and upstream blocking do_command. No native listener,
accept loop or connection threadpool was enabled. Owner-side teardown erases the
registered THD, frees NET and destroys the THD before the next session is started.
The driver joins its input/output pumps before final engine shutdown completes.

## What the patch changes

- Retains embedded public Protocol entries with mode branches to named native
  helpers. Binary low-level encoders remain shared. Metadata-created local
  Protocol_text objects and direct thd->protocol_binary observe the same mode.
- Ten native response helper bodies match the pinned upstream byte-for-byte.
  [Reuse verification](evidence/reuse-verification.json) binds their hashes.
  net_send_ok alone adds a fail-closed guard for SESSION_TRACK's unavailable
  embedded store routine. That capability is not advertised; the guard does not
  supply a replacement serializer. Source framing and all ordinary native
  response encodings remain upstream implementations.
- Prepared input keeps both native packet and embedded MYSQL_BIND strategies,
  including mode selection for scalar/temporal representation, PREPARE response
  and long-data forks. Only the tested value/command subset is accepted as evidence.
- Uses server NET semantics despite embedded layouts. Restores the upstream
  native command wrapper; no custom dispatch framing/decoder is substituted.
- Native login looks up its existing auth plugin by name instead of relying on
  the empty ACL-init cached plugin references. Enables the existing initial
  handshake decoder, its non-SSL constants and secure-transport helper. The
  no-access-checks profile retains upstream skip-grants success and excludes
  unreachable ACL-user/attribute lookup code that is absent from this build.
- Advertises the existing base plus prepared-result capability set (1024525),
  not upstream's broader defaults. Native skip-grants clears host identity, so
  the entry restores fixed root/localhost identity after parsing placeholder
  credentials. This is not account authentication or TLS support.

## Final observed checks

All16 entries in [the final result](evidence/run-3/result.json) passed:

| Boundary | Confirmed observation |
| --- | --- |
| Bootstrap | Existing product routine_bootstrap fresh path creates/validates the pinned proc schema before wire admission |
| Embedded prepared | MYSQL_BIND signed integer and embedded-NUL string execute/fetch correctly before and after native sessions; neither increments native decode count |
| Native login | Real greeting/version/capabilities and placeholder-password login; first connection uses the length-prefixed secure-response encoding |
| Text output | Three native column descriptors, text integer/string and SQL NULL arrive as native packets |
| Identity / initial DB | CURRENT_USER and USER are root@localhost, initial DB is test after placeholder login |
| SQL error | Missing table returns native1146/42S02, then a following SELECT succeeds |
| Prepared output | Native PREPARE header/parameter/result metadata; EXECUTE returns42, exact bytes a-NUL-b and NULL in a binary row |
| Type reuse | EXECUTE without new type descriptors returns100, empty string and NULL |
| Bad integer input | Truncated int64 returns native1210; no replacement parameter decoder |
| No-response close | STMT_CLOSE emits no packet; next PING produces the next expected OK; executing that closed ID returns1243 |
| Session retirement | QUIT ends the first session, then a second native greeting/login has a new connection ID |
| Fresh second session | Empty placeholder username and legacy NUL-terminated password encoding connect; prior @leak value is absent |
| Final cleanup | Both native session entries return0; product routine structure validates afterward, MYSQL_BIND still works, pumps join and engine shutdown returns0 |

Input/output queue payload budgets are64KiB in this single-session fixture.
Vio returns at most2 input bytes and3 output bytes per callback, exercising partial
headers, payloads and writes in the actual library. Observed queue payload peaks
were89 and122 bytes. These are tiny-fixture observations, not a backpressure,
16-session, RSS, throughput or deadline result. The CLIENT_SECURE_CONNECTION
password encoding in the check name does **not** mean TLS or authenticated users.

## Original failures retained

- build.txt: experiment entry const-pointer cleanup mismatch; fixed without
  changing protocol behavior.
- build-2.txt: embedded Session_tracker has no store; the undeclared capability
  remains outside this profile with a fail-closed guard.
- run-1: embedded bootstrap/BIND passed, native login returned1524 because the
  ACL-init cached auth-plugin reference was null. It is a failed diagnostic run.
- build-4.txt: restored handshake references constants and ACL helpers omitted
  by no-access-checks. Enable native constants and exclude the already unreachable
  grant lookup tail, retaining the upstream skip-grants branch.
- run-2: native login/text passed; USER returned root@ because upstream skip_grants
  clears host_or_ip. The entry now restores the product's fixed host identity.
- run-3: final successful run; its identity.json pins the final experimental patch,
  client and driver, and source-files.json pins all13 modified upstream inputs.
  Earlier failed runs retain their packets/logs as diagnostic observations, not
  exact-candidate acceptance or a PASS for the final source.

The pinned malformed-string-to-empty behavior from step2 was not repaired. This
run checks a truncated integer only, not parser fuzzing or general malformed
input safety. No existing product test/contract was changed to label the spike PASS.

## Reproduction

Prepare an owned workspace mounted as /exp in the exact image above. Keep all
source/build/data under temp and run commands through scripts/experiment_disk.py
with6GiB budget,8GiB free floor and the timeouts above.

1. Use ../issue65-prepared-native/inputs.py to fetch/verify MariaDB, Connector/C
   and fmt into temp (Python3.12+).
2. Run patch.py `<workspace>/temp/source` `<workspace>/worktree/guest/experimental.patch`
   `<workspace>/evidence/source-files.json`. It reads the verified archive and
   generates the complete new patch, replacing the old step2 delta rather than
   applying on top of it. Existing identical patched files are not rewritten.
3. Run prepare_routine.py --source `<workspace>/temp/source` --receipt
   `<workspace>/evidence/routine-header.json`. This calls the unchanged
   scripts/routine_schema.py prepare function with that source and worktree root. It generates wasm/routine_schema_sql.inc from the pinned
   source/metadata contract; evidence/routine-header.json pins the actual output.
4. Start the fixed CPU2/memory4GiB image with this workspace mounted as /exp;
   container name mariamem-issue65-login. Run configure.sh, then
   `cmake --build /exp/temp/native --target mysqlserver -j2`.
5. Run compile.sh in the container. Start with a fresh temp/data directory, after
   confirming no prior probe is active. The fixture intentionally requires a fresh
   mysql.proc bootstrap; do not reuse a failed run's DB state.
6. On the host run client.py --evidence `<workspace>/evidence/<run-name>`.
   It invokes the bounded /exp/temp/probe with stdin/stdout raw bytes and records
   packets, stderr, identity and results. The stdlib packet client is a fixture,
   not a proposed server/host protocol implementation.

## Limits and next decision

This is an experimental native entry, not a complete endpoint or a merge-ready
patch. Its init-failure cleanup, Vio wait/timeout/shutdown callbacks and EOF
classification are incomplete. Callback registration/normal partial transfers are
observed; cancellation wakeup and deadline behavior are not. It omits the new
control envelope, instance/session generations, concurrent sessions, authoritative
admission gate, reserved control capacity, accepted pending-input accounting,
warm NET buffer size guard and output-limit policy. A native command handler's
presence does not approve that command under the product's declared scope.

Only native quit/close and sequential session isolation are proved. No actual
Snapshot/Fork/Live, rollback capture, stopped-root quiescence, forced worker trap,
16-session retirement/capacity, all prepared types, cursors/long-data/bulk,
reprepare, aggregate-result budget, driver/ORM matrix, WASIX/wasm2go or supported
host matrix is qualified. The product's auth-key bootstrap/l4m_open/WASIX startup
is not run here; actual product routine SQL/bootstrap validation code is run in
the minimal native library. No claim of improved speed or reduced memory follows.

Next recommendation is3B: two concurrent native sessions with bounded queues and
control/admission, slow-client output, overflow/EOF/deadline and stale-generation
controls before any WASIX investment. The fatal-cause wire diagnostic and native
malformed-string compatibility choices from the design remain unresolved adoption
conditions. If control cannot make progress under blocked data I/O, or commands
can pass the stop fence, stop/reassess rather than moving a second MySQL parser
into Go or C. Integration and release require later Human decisions and evidence.
