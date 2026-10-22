# P4 first lifetime slice — native and both-OS guest PASS

Continue the approved [P4 implementation row](v06x-prepared-product-design.md#7-finite-implementation-and-acceptance-plan)
after [P3 both-OS acceptance](v06x-prepared-p3-pass.md). This change implements one
bounded lifecycle compatibility repair and adds seven native-controlled acceptance
scenarios. It does not declare P4 complete or reduce the approved P4 scope.

The native capture and replay both PASS7/7; complete relevant packet/metadata
traces have no differences. Go1.26.8 with the pinned MySQL driver1.9.3 runs on
macOS arm64 against a Linux arm64 MariaDB12.3.3 container. This is not a
macOS-native reference server. The [receipt](v06x-prepared-p4-lifetime-evidence/receipt.json)
pins image/binary/source inputs and distinguishes the local changed working tree
from a clean exact-commit build. Subsequent
[CI39699613828](https://github.com/masahitojp/mariamem/actions/runs/39699613828)
now passes all seven actual-guest scenarios on macOS arm64 and Ubuntu x86_64 at
source_commit `ecfea4ab6b1e9b665a89ac000c655fb584bfd754`. The
[CI receipt](v06x-prepared-p4-lifetime-evidence/ci/receipt.json) preserves complete
P4 captures and exact source/guest/generated inventories. All five jobs PASS.
This closes the first lifetime slice, not full P4.

## Repair and reason

Previous lifecycle dispatch rejected every CLOSE/RESET payload whose length was
not exactly4. For CLOSE it terminated the connection; RESET returned1835.
Pinned native controls instead accept short IDs with zero extension, ignore
surplus bytes, and keep the connection usable. A short nonzero CLOSE can close
its matching statement, with no response; an empty CLOSE is ignored. RESET of
zero returns1243; RESET of a valid short ID returns OK. Tests cover body sizes
0/1/2/3/4/5, and unit controls extend through8 bytes. These are bounded observations
of malformed packets, not a claim that every malformed MySQL packet has specified
portable semantics. The source dispatcher forwards these lifecycle commands
without an exact-length check; their handlers consume a four-byte ID. The
runtime observations, rather than an inferred guarantee about native buffer
contents, establish the short-body controls here.

`internal/mysqlwire/prepared_session.go` now copies at most4 bytes into a
zero-initialized local header. It never reads beyond the request or consumes the
following command. Existing mapping lookup, generation checks, native CLOSE ack,
no-response monitor exclusion, RESET type reuse and transaction status remain.
No public API, guest, converter, generated Go, canonical patch or binding pins
change. No new product capacity limit is introduced.

## Acceptance controls

| Scenario | Required observation | Native capture/replay | Actual guest |
| --- | --- | --- | --- |
| RESET/type reuse/transaction | Updated value remains visible after RESET; rollback restores seed; descriptors can be reused afterward |PASS|PASS both OSes|
| Short/surplus CLOSE/RESET | Six lengths; CLOSE immediately followed by PING; correct subsequent handle state |PASS|PASS both OSes|
| Closed/cross-session handles | Unknown1243/HY000; same-number handles in another physical session retain their own bindings |PASS|PASS both OSes|
| Native quota/recovery | Temporarily lower engine quota to2, retain exactly2 owners on1461/42000, close one and prepare/execute another, restore quota |PASS|PASS both OSes|
| Idle QUIT cleanup |12 physical sessions,4 unclosed statements each, rollback uncommitted DML, native count returns0 |PASS|PASS both OSes|
| Idle TCP EOF cleanup |Same12-session ownership/rollback test without COM_QUIT |PASS|PASS both OSes|
| Go DB/Tx/Conn/pool |Explicit Prepare with interpolation enabled; Tx.Prepare/Tx.Stmt commit/rollback/end invalidation; Conn.Prepare;16 workers/128 executions with at most4 connections; physical retirement/ErrBadConn reprepare; final statement count and open connections0 |PASS|PASS both OSes|

The raw reader adds no sleeps between CLOSE and PING. Bounded polling is used
only to observe asynchronous disconnect cleanup. Each guest scenario owns a fresh
root; it must also return active_connections to0, remove its temporary directory
and tolerate repeated Close. Failures preserve partial traces and fail the gate.
Test-only global quota changes are restored in finally and do not become a
library limit. The Go consumer keeps DSNs in its environment, not command output.

[Golden capture](../../tests/fixtures/prepared-p4-lifetime-native.json) and
[saved replay](v06x-prepared-p4-lifetime-evidence/native-replay.json) retain full
packet traces. For selected unknown-handle errors the comparator uses errno/state
and handle behavior because IDs are opaque; full error packets/IDs remain in
separate observations. All other selected packet, metadata, counter and consumer
fields are compared without packet rewriting. There is no SQL retry.

The three host packages PASS race tests.114 scoped Python/C checks PASS, including
existing allocation/bind/fetch/serialization cleanup injection and sanitizers;
those mock/component controls are not relabelled as real-guest failure injection.
New Go units prove short/surplus lifecycle dispatch, no-response monitoring,
owner/type release, quota rejection without half-installed mappings, and fatal
metadata unwind when the closing call itself fails.

## Reproduction and CI confirmation

Build the standalone consumer with Go1.26.8:

```sh
go build -o build/p4-consumer ./tests/prepared_lifetime
python tests/v06_prepared_p4_lifetime.py --native-port PORT \
  --consumer build/p4-consumer --output build/p4-native.json
python tests/v06_prepared_p4_lifetime.py --native-port PORT \
  --consumer build/p4-consumer --reference tests/fixtures/prepared-p4-lifetime-native.json \
  --output build/p4-native-replay.json
```

Use the pinned reference image and an isolated database with no other prepared
clients. For a formally generated development host, replace --native-port PORT
with --host HOST and use its product/python directory on PYTHONPATH.
prepared-product.yml builds the same consumer and runs that comparison on each
supported OS, retaining all P1/P2/P3 and installed-binding checks. The host-only
repair leaves guest identity unchanged, so exact guest rebinding is not needed.
CI39699613828 freshly built/generated/compiled the actual candidate normally;
existing origin guards remain. The guest remains e6d6021a. Both OSes pass all
previous P1/all72 P2/all14 P3/minimal CALL controls, SQL/transaction/Snapshot/Fork/
Close smoke,114 Python/C checks, three Go race packages and18 installed-binding
mutations. Every new scenario restores active connections to0 and removes its
temporary directory; the Go consumer restores native statement counts and open
connections to0. Complete P4 packets, unit logs and compact development receipts
are saved with original/stored hashes; only runner home path prefixes are
scrubbed. Original full development receipts are represented by their hashes
and compact summaries, not claimed as byte-identical full copies. These are
development acceptance receipts, not independent release regeneration or
Qualification. The earlier local receipt remains a historical record of its
working-tree tests, with the later CI result recorded separately.

## Remaining P4 scope (not waived)

- SEND_LONG_DATA through the public embedded API, omission/precedence/type reuse,
  empty/large/multiple chunks, native deferred errors and aggregate overflow,
  RESET/CLOSE release, and immediate LONG_DATA→LONG_DATA→EXECUTE.
- Prepared timeout/cancellation/disconnect while executing and unusable-pool
  behavior, with the existing instance-invalidation contract.
- Complete resource/failure matrix: allocation/truncation/serialization failures
  beyond existing component injections; pending state/cleanup counters on those
  exits. Native statement counts and host active-connection checks above do not
  claim general heap/goroutine/worker leak freedom.

Do not close P4 with this first slice. Continue those bounded implementation/tests
under the existing approval; P5 consumers/regressions and P6 canonical/J1/
independent generation remain separate. Main adoption, version placement,
Qualification and release are not started here.
