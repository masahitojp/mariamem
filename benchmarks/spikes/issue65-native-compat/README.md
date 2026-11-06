# Issue65 — fixed-guest compatibility observations: NOT_READY

2026-11-06. The Human selected continuing after the approved
[D1–D3 contract](../../../docs/decisions/issue65-native-wire-contract.md) and
requested recording decisions in [Issue65](https://github.com/masahitojp/mariamem/issues/65).
That issue owns current actionable tracking. The goal is maintainability: remove
host MySQL semantic duplication, not promise a performance gain. Changes to the
C++ controller and product integration remain later work.

This campaign observes the **unchanged** guest already used for native Linux and
Live. No policy patch, host admission fix, reference refresh or guest-index change
is allowed in this observation step. Source_commit
`5d9915d9940ff691249361aafb6ea39551f29a87`, SHA256
`c4c72644cd3fa4605a936a7eafe8d622ab4f670e5b7bdbfbdf30f0a351e8dfcf`;
host base `ecd5d2b7ceff2085cac59f629c36d688007fc6bc` with the previously
inventoried templates. The exact triggering tooling commit supplies the one new
`compat_test.go` source. Client path: pinned Go mysql1.9.3 plus the small raw
MySQL4.1 test client in that file; these are not all declared consumers.

## Observed result,2026-11-07

**NOT_READY: actual compatibility mismatches, not a build failure.**
[CI42238921778](https://github.com/masahitojp/mariamem/actions/runs/42238921778)
executed source_commit `4d45d5445fe65f66237653e3bbfb5a7d6137cebb`. The guest
build, prior22-case Linux/Live repeat and274-file macOS comparison pass. The
compatibility run completes all7 groups and88 observations, with6 mismatches.
[The compact receipt](evidence/ci-42238921778.json) pins the executed binary and
templates and retains expected/actual values; original logs/inventories are saved
in owned evidence. Neither contract nor expectations were changed after execution.

| Group | Result | Actual observation |
| --- | --- | --- |
| Credentials | PASS | Credential matrix and canonical root; secure/legacy/empty username and following PING |
| Capabilities | FAIL | Greeting matches; FOUND_ROWS requested on unchanged UPDATE returns affected rows0, expected1 |
| PreparedState | PASS | Tested alias, type reuse/NUL, LONG_DATA/RESET and deferred-error recovery, D2 malformed string, CLOSE/unknown CLOSE and unknown RESET/following PING |
| Capacity | FAIL | Mixed16 sessions, existing PING and retirement/reuse pass;17th TCP/Pipe return EOF instead of1040/08004 |
| LiveCapacity | FAIL | Stable relay also returns EOF for17th; existing session remains usable |
| FatalEOF | PASS | Actual native deadline closes idle peer; owner and cleanup retain deadline cause; independent instance usable |
| FullWindow | FAIL | Exact pending-input budget reached while executing; no overflow/EOF cause observed within750ms, before10s command deadline |

Recommend retaining the approved contract and fixing three named boundaries:
FOUND_ROWS negotiation, pre-login capacity rejection and full-window overflow/EOF
monitoring. The latter observation is bounded to750ms, not a claim that no later
failure occurs. Source shows the relay pauses reads at a full window; native
negotiation still needs source-level diagnosis before selecting its patch.
Use new guest identity if a guest policy changes, keep lifecycle regressions and
original failures. Do not combine controller relocation or benchmarks with fixes.
Both owned CI workspaces and transfer WASM were disposed; cleanup debt is empty.
The7-group PASS/FAIL labels retain exactly the vector scope below. No full-profile,
public API, large-result or performance acceptance follows from passing subsets.

## Question and bounded scope

Can the present native route meet the selected contract in the following groups,
and which concrete mismatches need a subsequent policy/host correction?
The [dedicated workflow](../../../.github/workflows/issue65-native-compat.yml)
first repeats all source equality/binding controls and the Linux/Live22 cases.
Then it adds exactly one inventoried test file, compiles a distinct binary and
executes the seven compatibility groups. It does not change the22-case bundle.

| Group | Observation and oracle |
| --- | --- |
| Credentials | Driver placeholder credential matrix and canonical USER()/CURRENT_USER(); raw secure/legacy/empty-user login and following PING |
| Capabilities | Exact greeting bit set including validated prepared multi-result bit; negotiated FOUND_ROWS on unchanged UPDATE, not just the advertised bit |
| PreparedState | Explicit statement and alias0xffffffff, NUL/string type reuse, LONG_DATA without response, execute and RESET clearing, deferred invalid-index error/recovery, D2 malformed string, CLOSE/unknown CLOSE without reply and unknown RESET with following PING |
| Capacity | Sixteen mixed TCP/Pipe native physical connections; 17th on each transport must receive pre-login1040/08004 independently of native SQL slots; existing SQL continues and a retired slot is reusable |
| LiveCapacity | Sixteen connections through the unchanged stable relay; its17th rejection must also preserve the declared pre-login error and existing session usability |
| FatalEOF | An actual native command deadline closes an idle peer transport, preserves the owner-side deadline cause through cleanup, joins the runtime, and leaves an independent instance usable |
| FullWindow | Deterministically observe executing SLEEP before filling the raw input window with valid future PING-frame prefixes; at exact1,048,581 bytes test EOF, at max+1 test overflow. Require cause-specific abort within750ms of setup, well before the10s command deadline; record the complete input counters. This initial full-window probe is TCP only. |

The full-window fixture executes SLEEP8 only as a controlled pending-work holder,
not a benchmark. It waits on native state/counters before checking bounded
failure; no sleep-only race oracle. This timing budget is part of the probe,
not a new configurable product deadline promise.

The existing native input window can backpressure instead of detecting overflow
or EOF, and direct/Live rejection can close without a capacity ERR. Those are
**suspected gaps**, not assertions already executed on this guest. An observed
failure is retained as NOT_READY, never redefined as acceptable merely to green CI.
The unknown prepared/capability paths may expose further differences.

This scope does not claim every credential/malformed-login/capability variant,
command allowlist/negative path, zero-param/temporal/numeric/prepared edge, output
packet policy, >32MiB aggregate streaming, full-window Pipe, public owner API,
all client versions, real storage failure, race freedom or performance. D3 is
approved but its large-result/output acceptance remains a later focused probe.
Existing native source and step2 anchors remain distinct from this campaign's
actual raw observations. No paired native-network reference run is claimed.

## Evidence and qualification

`compat-build.json` pins source inventory, template/analyzer/probe/tooling identities,
Go build information and binary hash. Before/after inventory must match the prior
Live bundle plus exactly one test file. `compat-suite.txt` preserves all original
output, including failures. Each raw observation records test identity, expected
value, actual value and pass/fail. `result.json` reports missing execution and
contract mismatches separately; failed tests still yield these records.

A scoped PASS requires all seven groups, observations for each, no skips/missing/
duplicated groups, terminal Go PASS, exit0 and no mismatched observation. A green
Linux/Live repeat does not substitute for compatibility execution. Build failure,
timeout or incomplete output stays INCOMPLETE; complete mismatches are NOT_READY
and fail the CI job. Original failures are retained without refreshing expectations.
The original22-case result is saved separately as `live-repeat-result.json`.

Initial budget:2h active/tooling30min, at most2 heavy CI submissions. Local prep
is documentation/test tooling only: owned1GiB/free floor4GiB. Hosted builder and
runtime each own12GiB/free floor12GiB; exact guest recipe Ubuntu24.04 arm64,
actual runtime native Ubuntu24.04 x86_64. A fresh full guest build is needed since
prior disposable transfers were deleted. Local checks are Go formatting/parser,
Python AST, exact raw-helper controls (standard-library Go1.27.3; no native runtime),
seven evidence-accounting tests plus the existing eight acceptance
guards, actionlint1.7.12, public-source/links/diff checks. They do not compile or
execute the native compatibility binary locally.

The existing cleanup verifier disposes SDK, archives, converter, generated source,
binaries, Go caches and worktrees even after failure. Save compact evidence only;
delete the one-day transfer artifact with the always-run final job; evidence7days.
A mismatched guest remains diagnostic, never accepted/reused. After submission,
hand off URL, SHA and operation=`native-compat-experiment`; do not supervise CI.

After observations, make the smallest source-bound fix for each demonstrated gap
with a new guest/build identity if necessary, then rerun its oracle and lifecycle
regressions. Do not combine policy repair, wholesale controller relocation and
performance comparisons. Performance remains later matched old/new measurement;
SQL/storage work, synchronization and startup/Fork have no measured speedup here.
