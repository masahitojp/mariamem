# Issue65 G1: fixed-guest prepared input observations

Human continuation of the [compatibility scope review](../../../docs/reviews/issue65-native-compatibility-scope.md),2026-11-07:
start with G1. This campaign observes the existing contract; it does not repair
the guest, approve new malformed-input exceptions, adopt native wire or release.
Budget: active2h/tooling30min, local native plus at most one Linux CI,
owned builder/runtime12GiB each, free floor12GiB.

## Fixed inputs and executable scope

Guest/checked host source_commit: `8f3e440ab78af570e489dd8d463cab1ed4c5aed8`.
Guest SHA256: `4caa85d299410467f2656d6611df5dbeb518351927ac30b0216e516d277bf094`.
Binding remains the [reviewed policy binding](../issue65-policy-fix/binding/identity.json).
Frozen main remains61973daa; no source/binding/host adapter change is permitted.

The existing policy probe first repeats22 lifecycle cases,88 compatibility and
38 limit observations,2 prior controls,3 policy controls and supporting checks.
The281 Go/assembly/data source files must exactly match the accepted macOS
reference d1504d0c0138da6e033f4cd937a90fde63c2750b25ea5d8a3e1a244f480cefbb.
These are staged files, not a claim that all281 compile on both operating systems.
D2's named malformed string acceptance stays in that unchanged baseline.

Only after it passes does G1 add one pinned test file and compile a separate
binary. Full source inventory must equal baseline plus that file (282 staged
Go/assembly/data files); baseline binary and source hashes remain unchanged.
The added fixture does not replace production code or the baseline test binary.

| Group | Cases and observations |
| --- | --- |
| EXECUTE header | zero/one parameter × cursor1,flags8,iteration0/2; reply,PING,cached handle; one-parameter seed/fresh recovery (32) |
| Zero-parameter suffix | none,boolean0/1,invalid2,surplus; reply,PING,handle (15) |
| Descriptor/truncation | newtypes2,type17,typeflags1,short/surplus fixed scalar,all21 prefixes of the existing21-byte integer body; seed,reply,PING,cached/fresh types (130) |
| SQL/PREPARE bounds | each empty/exact1MiB plus following PING; exact PREPARE execution; shared max+1 header and peer isolation (11) |
| SET_OPTION body | empty,short,on,off,unknown,surplus plus following PING (12) |
| Failed PREPARE | seed,SQL error,invalidated last-handle alias,explicit old handle cached/fresh/PING (6) |
| LONG_DATA header | body lengths0..6; seed,no-response/PING,state,fresh recovery (28) |

Total:7 groups,234 required named observations. Cursor acceptance ends at metadata
EOF with CURSOR_EXISTS; the fixture must not wait for a nonexistent row. Raw reply
receipts preserve packet prefixes (up to64 bytes each),errno/state,value and
transport errors. All result fixtures have one column. This is a finite vector
set, not a claim to cover every malformed packet or cursor behavior.

SQL max+1 cannot reach SQL dispatch: the global command-header bound rejects
1048578 bytes (command plus SQL). The shared capture sends that header without a
body, confirms bounded rejection and probes a same-root peer. It does not claim
to have sent a complete oversized SQL/PREPARE body. The prior limit fixture
separately tests cold/warm oversized input headers.

The expected errno/state are inherited from the existing preparedproto/mysqlwire
contracts and their vectors, not inferred from this guest's output. Complete
contract mismatches yield NOT_READY; absent observations, timeout,SKIP,duplicate
IDs or missing groups never become PASS. Preserve discrepancies for a separately
approved minimal guest-boundary repair. G2 metadata/result chains and P1 public
APIs,30s timeout,resource ownership remain outside this campaign.

## Reproduction and handoff

Use owned workspaces at the pinned source with the existing policy probe's
`build` stage in native Linux arm64. Transfer its verified development artifact
to the checked host workspace. Then run:

```sh
python3 benchmarks/spikes/issue65-prepared-input/probe.py local --workspace "$HOST_WORK"
# CI uses native Linux x86_64 instead:
python3 benchmarks/spikes/issue65-prepared-input/probe.py runtime --workspace "$HOST_WORK"
```

The workflow is `.github/workflows/issue65-compat-fixes.yml`, on branch
`experiment/issue65-prepared-input`. CI retains raw baseline/G1 evidence even on
failure and deletes the disposable guest transit. Cleanup uses the existing
policy probe's `cleanup` stage; local container mount records require confirming
the container has exited before disposing its namespace-only mount receipt.
After successful CI submission, hand off URL,exact candidate SHA,operation and
stop; a failing observation run is not repaired or retried automatically.
