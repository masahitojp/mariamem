# Issue65 step3B — native concurrent control

**PASS for the bounded native probe:** all11 final cases pass with real embedded
SQL, native NET/Protocol and independently scheduled sessions. Recommend a
separate3C WASIX/link/import preflight next. No product adoption or implementation
of3C/3D is implied. The decisive result is progress on another connection and the
control channel while one connection has65536 unacknowledged output bytes,
combined with an admission fence that prevents an already queued INSERT.

The strongest concern is portability and remaining embedded-only forks. Native
query cancellation initially crashed in an embedded result collector; this probe
needed one more per-THD mode branch. Native pthread cancellation/wakeup success
does not establish WASIX/generated-Go lifecycle correctness or porting cost.

## Scope, identities and build

The Human selected continuation after [3A](../issue65-native-login/README.md).
This follows the separately budgeted3B stage in the
[design](../../../docs/design/issue65-native-protocol/README.md), not main adoption,
Snapshot capture, release or an external issue update.

- Starting source_commit:712e45edc1464e2ca9f4a41290d046168364fd6b.
- MariaDB12.3.3 source_commit:83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e.
  The same three checked inputs from release/inputs.lock.json are used.
- Exact existing image:
  sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f.
  Ubuntu24.04 Linux/aarch64, GCC13.3, system PCRE2 10.42/OpenSSL3.0.13/zlib1.3,
  pinned fmt12.2.0. CPU2/memory4GiB, no image rebuild or heavy CI.
- Native mysqlserver static library: coherent EMBEDDED_LIBRARY build,
  -O0 -DNDEBUG -DMARIAMEM_NATIVE_WIRE. Mandatory experiment flag; no macro-off
  support. Driver additionally uses -g -rdynamic and warnings as errors.
  InnoDB and optional engines are disabled. No performance or sanitizer claim.
- Pristine upstream plus guest/experimental.patch only; canonical
  guest/source.patch, product generated code and runtime are unchanged.
  Product routine_bootstrap.inc and generated pinned proc schema are used;
  full product l4m_open/auth-key startup is not run.
- Budget:2h active from2026-11-05 05:53 UTC, measurement tooling30min, CI0,
  owned6GiB/free floor8GiB. This native prototype is the experiment itself,
  not a broad measurement campaign. Owned peak about1.63GiB. Builds were guarded;
  final suite about7s, each native process bounded30s, host waits4s/stop8s.

[Final identity](evidence/run-final/identity.json) pins pre/post-run source,
actual executable/static-library hashes and the unchanged3A test client.
[Upstream file hashes](evidence/source-files.json) cover all14 patched paths.
The source files were verified against this manifest before the final run.
The workspace helper receipt's base is its invoking checkout; the actual reused
branch/build base is the source_commit above. No tag object is used as a source.

## Actual mechanism

The host test fixture sends a private length-prefixed DATA/control envelope over
pipes. DATA is opaque MySQL bytes. The C++ owner demultiplexes it into one memory
Vio per native worker; upstream NET parses packets and Protocol encodes responses.
Only the test client parses SQL responses. No Go relay, cgo, OS database listener
or replacement MySQL server serializer is introduced.

A shared gate protects admission, command identity, state and transaction status.
The first command byte acquires a lease before reaching NET. Completion waits
for the cumulative final output acknowledgement; no-response CLOSE completes on
native dispatch return. Under the same gate, quiesce checks busy/transaction
preconditions and irrevocably fences new commands. A test-only HOLD immediately
before admission exposes the queued-command race; a fixed read-only embedded
COUNT(*) oracle confirms that the queued INSERT never reached the engine.

Each session has1048581 pending input bytes and65536 outstanding output bytes
(queue plus sent/unacknowledged). DATA chunks are at most65536 bytes; Vio moves
at most4096 per callback. Input credit tracks actual NET consumption. Controls
have a separate64KiB queue, coalesced state/credit notices, reserved fatal notice,
and an8-control fairness quota before DATA. These are payload/accounting bounds,
not total allocator/RSS or aggregate SQL-result bounds. The host fixture keeps
reading the mux while deliberately withholding one client's output ACK; it does
not simulate a host that stops reading the entire private channel.

Sixteen slots use instance epochs and monotonic session generations. Native THD
handles are pinned for real THD::awake(KILL_CONNECTION); a separate killer avoids
holding the admission gate through native engine locks. Closing queues wakes
read/write waits. The worker unpublishes its THD before cleanup, and the reaper
joins before releasing a slot. Fatal command/input/output failures poison the
whole instance with a sticky cause. An uncompleted handshake timeout retires only
that session. STOP closes/wakes sessions, joins owners, validates bootstrap/BIND
again and calls mysql_server_end.

## Observations

All11 [final cases](evidence/run-final/result.json) passed; each native process
exited0 with started==joined. Packets, control events, final counters and native
stderr are retained per case.

| Case | Confirmed result |
| --- | --- |
| concurrency | SLEEP on A overlaps successful B SQL; A blocked at64KiB does not block B/control; output ACK retains lease; pipeline results ordered; two native prepared sessions overlap; CLOSE has no response; stale command timer ignored |
| gates | Busy and transaction rejection preserve usability; a partial header is busy; queued INSERT is denied after fence, actual row count remains0; later command is denied |
| rollback_fence | Active-transaction rejection can be explicitly overridden to acquire the fence; storage rollback/capture is **not** tested |
| query_deadline | SLEEP(10) is cancelled, both workers join, original deadline cause persists and later OPEN is rejected |
| input_deadline | Partial header timeout poisons instance and both workers join |
| output_deadline | Withheld ACK stalls output; another connection progresses before timeout; both workers then join |
| handshake_deadline | Unauthenticated stalled session retires; healthy connection remains usable |
| full_input_EOF | Control EOF is observed behind exactly1048581 queued input bytes during SLEEP; both workers join |
| input_overflow | One extra input byte poisons without exceeding the payload limit; both workers join |
| capacity_generation |16 authenticated native sessions;17th rejected without worker; slot reused only after join; prior user variable absent; old-generation DATA/ACK/EOF and wrong-epoch EOF rejected; all17 workers join |
| native_framing |1MiB SQL accepted; after warming NET buffer, oversized header rejected1153 before payload; wrong sequence never dispatches; previous-sequence ERR rejected1156; healthy connection continues |

A guard at upstream NET's already decoded length enforces the1MiB+1 command-body
limit on every header, including reuse of a larger allocated buffer. It does not
add a second header parser in Vio. Native response helper source is unchanged
from3A (see evidence/reuse-verification.json). This guard's zero-length policy and
its limited tested framing subset are not general fuzz/compatibility acceptance.

## Discovered failure and correction

Attempts2/3 failed on query_deadline. The diagnostic build exited139; its stack
shows Protocol_text::remove_last_row called after select_send aborts a cancelled
SLEEP row. The embedded override assumes cur_data points to a MYSQL_DATA collector;
wire mode has none. The fix delegates to upstream Protocol::remove_last_row (a
no-op) for native-wire THDs and retains the embedded collector for C API THDs.
This is a mode fork, not a new packet encoder. Attempt4 passed that case; attempt5
passed the whole suite. run-final repeats it with source/binary identity capture.

Original failed logs/events remain diagnostic evidence, not acceptance of the
final candidate. build.txt is the first full build; build-2/3 are incremental,
with build-3 including this correction. driver-compile-2 adds fault backtraces.
Log normalization removes trailing text whitespace and compacts event/packet JSON
without changing parsed values; raw and saved hashes are in
evidence/log-hashes.json. Native fault tracing is diagnostic, not crash recovery.

## Reproduction

Use Python3.12+, the exact image above and an owned workspace bound at /exp.
Run preparation/build/runtime via scripts/experiment_disk.py with6GiB/8GiB limits.
Source identity must be checked with scripts/git_identity.py before building.

1. Run ../issue65-prepared-native/inputs.py with temp as its argument.
2. Run patch.py --source temp/source --evidence evidence. It regenerates the full
   pristine-to3B patch, using the preserved3A generator first. Do not stack patches.
3. Run ../issue65-native-login/prepare_routine.py --source temp/source --receipt
   evidence/routine-header.json.
4. Start the image as mariamem-issue65-control, CPU2/memory4GiB/pids512,
   bind workspace:/exp; keep it alive for the bounded run.
5. In the container run ../issue65-native-login/configure.sh from this directory,
   then cmake --build /exp/temp/native --target mysqlserver -j2, then compile.sh.
6. On the host run run.py --evidence evidence/run-final. It creates a fresh
   temp/data for each case; no concurrent invocation against the same container.
   --only permits a focused diagnostic. Keep source-files.json in evidence for
   pre-run verification. Stop the owned container and remove scratch afterward.

## Remaining conditions

Recommend only the costed3C preflight next: enumerate required WASIX imports,
thread/callback/wait support, build/link recipe, and generated-Go bridge costs
before a full rebuild. This result makes option4 plausible; it does not remove
custom lifecycle/flow-control work or prove its production implementation.

There is no real TCP slow reader, generated-Go worker, cross-DB isolation/fatal
acceptance, non-cooperative worker proof, interrupted private-output pipe recovery,
control-flood campaign, ASan/TSan, systematic schedule exploration, full prepared
value/command matrix or supported-host qualification. Broken outer output exits
the native fixture with80; that is not a product ownership policy. Fatal original
cause delivery to an idle wire client and malformed-string-to-empty semantics
remain unresolved design/adoption choices. Output envelope/aggregate-result policy
also needs a product decision. Existing product tests were not relaxed.

Quiesce here proves authoritative admission and precondition semantics, not
stopped-root capture, transaction rollback durability, restored child independence,
Live replacement or Snapshot/Fork correctness. Those remain3D after3C and require
real storage/runtime evidence. Main integration and release remain Human decisions.
