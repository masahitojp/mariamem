# Issue65 — remaining native protocol limits, observation only

Human continuation,2026-11-07: proceed after the three compatibility fixes passed
[CI42260991841](https://github.com/masahitojp/mariamem/actions/runs/42260991841)
at source_commit `2ffa5c3428a4b40c211c9f4ace1379253d337588`.
The [saved baseline receipt](evidence/baseline-ci.json) retains that result and
cleanup attribution. The current task changes tests/tooling only. It does not
repair guest policy, relocate the controller, adopt native wire or release it.

## First CI result: real profile gaps plus an invalid test configuration

[CI42266736265](https://github.com/masahitojp/mariamem/actions/runs/42266736265)
at source_commit `b08c3c938660ca74885b8e967e7a2adb71cdccaf` fails with
**INCOMPLETE**, not a complete output/aggregate judgment.
[The saved result](evidence/ci-42266736265.json) has26/38 observations,
18 passing,8 mismatches and12 missing observations. All6 top-level groups ran.
The unchanged baseline22 lifecycle/88 compatibility observations, both controls,
supporting checks and279-file comparison still pass.

Confirmed gaps: RESET_CONNECTION and STATISTICS return success; PROCESS_INFO
returns a result set; STMT_FETCH returns1243/HY000 and BINLOG_DUMP1047/08S01
instead of the declared1235/42000 rejection. TLS flags and missing PROTOCOL_41
are accepted. This does not establish working TLS, cursors or replication.
PROCESS_INFO's following-PING sequence mismatch is a secondary result of unread
result metadata after the unexpected result set, not separate evidence of native
wire corruption. Compression/DEPRECATE_EOF masking and old-style EOF pass.
Cold/warm oversize/continuation headers and Pipe overflow/EOF pass.

Six output/aggregate subcases used30000ms when the fixed guest OPEN envelope is
100..10000ms. They fail before login with `deadline configuration`; their12
required observations never ran. Their `join incomplete` errors must not be
relabeled native cleanup success. Both CI workspace cleanups and transit deletion
are separately confirmed. This test configuration error is corrected to10000ms;
an added source-contract guard checks every fixture OPEN against the pinned
patch. Local observer/source tests now pass11/11. The corrected native cases
remain unexecuted; this commit is not a rerun PASS.

Recommendation: retain the approved profile and reject OUT commands/invalid
handshake flags at the guest's native decoded boundary, not a host parser.
BINLOG_DUMP needs rejection-error parity, not a replication implementation.
The output/aggregate cases still need one corrected fixed-guest execution before
an output-policy repair can be designed. A rerun of this guest alone will still
fail the already confirmed command/handshake oracles; do not treat it as an
expected green retry. The initial single-CI observation budget has been consumed.
Obtaining the12 missing observations costs one additional fixed-source guest
build/translation plus Linux execution (roughly20min in this run; no timing or
performance guarantee). Preserve the original failure when choosing that next
step or a separately identified guest-policy repair.

## Fixed inputs and bounded work

Guest and checked host source_commit remain
`a1e3b8a0d7f3750e684610e273a28b802a7135d0`, including the frozen prepared-UCA
main61973daa. Guest SHA256 remains
`0531ff4f348670dd5e2065a4a25fe9012ed278bd346a12093b97ff1cdfdd67e9`.
Guest patches, reviewed binding, host runtime/relay and old test fixtures are
unchanged. No pins are refreshed automatically.

Reuse the existing experimental workflow file `issue65-compat-fixes.yml` on
`experiment/issue65-native-limits`, named **Issue65 native remaining limits**.
One new heavy CI submission; active2h/tooling30min initial envelope, builder and
runtime each12GiB with free floor12GiB; the local tooling workspace is2GiB.
CI rebuilds the same guest and first executes the unchanged22 lifecycle cases,
7 compatibility groups/88 observations,2 supplemental controls and supporting
checks. Its strict279-file macOS reference guard is unchanged.
Then add exactly `cmd/issue65-wire/limits_test.go` to the checked product and build
a separate binary with Go1.26.10/CGO_ENABLED=0. Bidirectional whole-inventory
comparison rejects changed baseline files or extra code. The second binary has
280 Go/assembly/data inputs; this is not a280-file macOS execution claim.

Local verification covers evidence/source guards, Python imports/syntax,
workflow lint and Go fixture type checking using nonexecuted helper stubs.
No local native execution of the new cases is claimed. CI provides the actual
Linux execution; do not reuse the prior native PASS as this new suite's result.

## Named matrix (6 groups,38 required observations)

- **Commands:** RESET_CONNECTION31, STMT_FETCH28, STATISTICS9, PROCESS_INFO10,
  BINLOG_DUMP18. Require the old endpoint's ERR1235/42000 and following PING.
  These are representative explicitly OUT paths, not every possible opcode/body.
- **Capabilities:** TLS and missing PROTOCOL_41 require ERR1235/42000. For
  compression/DEPRECATE_EOF, the old endpoint does not advertise the bits and
  ignores them: require ordinary uncompressed login and a text result with legacy
  EOF. Do not silently strengthen that behavior into rejection of all unknown
  bits. Supported negotiated caps already have their separate baseline test.
- **Input headers:** payload1,048,578 (max+1) and continuation0xffffff, cold and
  immediately after PING in one write. Send no body; require bounded rejection
  instead of a body read/deadline. This is not every command-specific input bound.
- **Output packets:** text and binary rows with exact0xfffffe payload, exact value,
  terminal EOF and following PING. At max+1 require ERR1153/08S01 or early EOF,
  never a continuation header. Read and validate each header before allocation;
  do not inject a host ERR into a partial packet or count a command timeout as
  successful rejection.
- **Aggregate:** text and zero-parameter prepared paths each return40 exact1MiB
  rows (40MiB value bytes), crossing the removed32MiB envelope. A Pipe reader
  deliberately holds output until native outstanding credit is65536; an
  independent session must PING while blocked. Validate every row/value and EOF,
  native output queue peak<=65536 and following PING. Queue peaks are not engine
  allocations or RSS, and one-shot functional timings are not performance data.
- **Pipe full window:** same barrier and budget as the earlier TCP fixture,
  overflow and EOF while SLEEP is executing, abort within750ms before the10s
  deadline, original cause and independent-instance PING. No transport sleeps
  stand in for the native executing/full-window barriers.

Oracles follow [the native contract](../../../docs/design/issue65-native-protocol/contracts.md),
[wire decisions](../../../docs/decisions/v060-wire-contract.md) and the fixed
legacy implementation (`internal/mysqlwire/wire.go`: handshake/default command,
packet and read-ahead limits). Preserve all observations, failed setup and raw
logs. The analyzer requires every named identity once; missing/duplicate/skipped
execution cannot become PASS. NOT_READY is a contract mismatch, INCOMPLETE means
execution evidence is missing. Both fail CI. Cleanup/upload/transit disposal run
on failure too. Starting CI ends supervision: return URL/SHA/operation and stop.

## Remaining scope

No full protocol/client-profile acceptance follows from these representative
vectors. Oversized metadata, multi-result terminal/aggregate limits, every
command-specific EXECUTE/LONG_DATA bound and full prepared/fatal vectors remain
UNVERIFIED. Public integration, both supported OS product gates, controller
ownership relocation, race, matched performance and adoption/release remain later
work. If this fixed guest leaks native protocol features or output continuation,
report the exact failure; policy repairs need a separately identified guest and
new correctness evidence. Do not mix that repair into this observation campaign.
