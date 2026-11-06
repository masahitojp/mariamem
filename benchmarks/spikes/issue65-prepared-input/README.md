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

## Local result: complete observations, contract mismatches

Native macOS arm64 execution at tooling source_commit
`3ef202123c137dcba5d6996cfac2e1dfec3cb92b` completed all7 groups:
**234 observations,195 PASS,39 mismatches,missing0 — NOT_READY**.
[Raw observations](evidence/macos-raw.txt), [parsed result](evidence/macos-result.json)
and [identity/disposal receipt](evidence/macos-receipt.json) preserve attribution.
The fixture SHA256 is804f48fa64a4467a879c3fcd65eb14b6a2b8dda53cf4bade570e163eabc0fd77.

The unchanged baseline passes22 lifecycle,88+38 observations,2 existing and3
policy controls,supporting checks including22 installer tests. Its281-file
macOS reference comparison has no differences, and its binary SHA is again
7ca5c6389e8c9980aa50709161781a462befd79afc8fea3254b70f9031250af1.
G1 adds exactly the one fixture:282 staged Go/assembly/data files, with a full
7346-file inventory checked before/after execution. Separate G1 binary SHA:
da6cad640523699214de7ec797082868051a975941a0da0ea3be601f9c1592dd.
These results do not qualify public APIs or a different guest.

| Group | PASS / all | Observed discrepancy |
| --- | --- | --- |
| EXECUTE header | 24/32 | cursor1 yields CURSOR_EXISTS metadata EOF; flags8 and iteration0/2 execute normally, for zero/one parameter (8) |
| Zero-param suffix | 13/15 | invalid boolean2 and surplus bytes execute normally (2) |
| Descriptors/truncation | 106/130 | errno1210 instead of1835 for type17/typeflags1/short scalar and prefixes9,10,13..20; surplus scalar executes42 (14 reply differences). Cached type reuse subsequently fails in10 cases; fresh descriptors recover in all26 cases |
| SQL/PREPARE bounds | 9/11 | empty QUERY/PREPARE give1065/42000 instead of1153/08S01 (2). Both exact1MiB cases,prepared execution,shared max+1 header and same-root peer pass |
| SET_OPTION | 9/12 | empty/one-byte/surplus bodies return EOF success instead of1835/HY000 (3) |
| Failed PREPARE/alias | 6/6 | SQL error,invalidated alias,explicit old handle cached/fresh and PING all pass |
| LONG_DATA header | 28/28 | short bodies0..5 remain no-response; empty chunk at6 bytes and following state/recovery pass |

All following-PING observations pass. The10 cached-reuse failures occur for
short_scalar,extra_scalar,prefix13..20,after a successfully consumed response;
they are not unread-result sequence errors. Wire evidence shows failed cached
reuse and successful fresh recovery; it does not directly inspect native type
cache fields. The39 observations are not39 independent bugs. D2's named malformed
string remains accepted in the passing baseline; it is not a blanket exception
for these scalar/descriptor/body cases.

Recommendation: preserve the contract and use guest decoded entry/type-commit
boundaries for a minimal repair proposal after the one Linux repeat. In
particular, errno-only remapping would not fix acceptance of invalid bodies or
cached-state recovery. Do not rebuild a Go parameter decoder to conceal these
differences. Guest repair/new exceptions need a separate decision and identity;
G2/P1/P2 remain as recorded in the scope review.

Python3.14 is required for this reproduction (the system Python3.9 initial
attempt stopped before translation; a restart also encountered the nonfresh
empty output parent). Those original setup errors are retained separately and
are not counted as native mismatches. Builder/runtime SDKs,converter checkout,
archives,generated code,binaries,Go caches and worktrees were disposed; all3
local disposal receipts have cleanup debt0. Only compact evidence and Git refs
remain. The approved Linux observation CI has not yet returned a result.
