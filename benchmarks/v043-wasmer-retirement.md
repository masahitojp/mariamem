# v0.4.3 Track A — Wasmer retirement

Independent review candidate from `fa6ef5355ecb93f7e1cabbedf5caa74fe4210870`.
Branch: `experiment/v043-wasmer-retirement`. Not merged or released.
Generated-Go remains the same guest/memory32/mmap model; retirement is not a
new runtime, hard-failure containment or MariaDB upgrade.

## Dependency inventory and decisions

| Remaining baseline piece | Classification | Candidate treatment |
| --- | --- | --- |
| Public Go `Options.NativeDir`, native/runtime environment selection | remove | Deprecated source-compatibility field retained; nonempty legacy overrides fail before allocating or launching. No Wasmer fallback. |
| `internal/artifacts` resolver, download/cache, metadata capture/verified-bundle token; root native-version embed | remove | Delete; keep only supported-platform checks and their tests. |
| Host `Start`/`StartVerified`, Wasmer module/argv/env; guest subprocess/killpg | remove | Linked generated-Go only. No runtime executable lookup, native materialization, bundle download or subprocess force-kill. |
| Python runtime/module/wasmer_dir overrides and host CLI flags | remove | Explicit rejection with migration guidance; signature names retained for useful errors. Host-only artifact verification remains. |
| Legacy Python/native executable image packaging | remove | `build_alpha.py`/setup accept generated-Go only; old native packaging CLI is retired. v0.4.1 already removed unused generated executable images. |
| Wasmer guest-build-boundary, native-platform, Ubuntu-product workflows | remove | Removed from current workflow catalog; old exact tags preserve them. Current development integration uses compiled guest, never alpha.2 bundle. |
| Wasmer-specific unit/release fixtures | historical/reference | `tests/historical` outside normal check/pytest collection. Current generated acceptance, module identity, authenticated artifact/hash validation and publication tests remain active. |
| Legacy AOT/build/package/acceptance/notices scripts | historical/reference | Source retained for audit, CLI refuses current execution with old-tag guidance. No current build/release gate imports them. Shared clean-consumer helpers extracted. |
| Wasmer notices/license/source pins and historical review inventories | historical/reference | Original reference bytes/pins retained; no Wasmer engine wheel/runtime dependency (five historical notice texts). Historical terms are not removed or relabeled. |
| MariaDB/lite4mariadb GPL corresponding source, WASIX libc/sysroot, LLVM runtime/headers, converter source/notices | still required by generated-Go tooling | Unchanged; source filtering still excludes external Wasmer engine source while retaining guest/sysroot/runtime/headers/converter. |
| Generated source, WASM intermediate, canonical build/translation recipes/pins | still required by generated-Go tooling | Byte-identical. “WASIX” and legacy-EH compiler encoding do not mean Wasmer execution. |
| Benchmark/stage/resource diagnostics and prior reports | historical/reference or shared current tooling | Preserve mechanics/reports. Current Go lifecycle launcher now works without native directory; verification probe measures current prepared-file hash contract. Historical report comparison retained. |
| Supported-platform metadata, exact module origin, clean env, GitHub artifact API | still required by generated-Go tooling | Retain generic helpers/tests; remove legacy READY interpretation. Publication permits generated-go-v1 aggregate version 3 only. |
| Unclear dependencies | unclear | None identified in current startup/build/release dependency closure; unrelated historical source remains conservatively retained. |

## Scope and tradeoff

Normal Go Start/SQL/auth/sessions/Snapshot/Fork/Close and normal host-only Python
behavior are preserved. Intentionally legacy-only public inputs now fail: callers
using NativeDir or Python runtime/module/cache overrides must remove them or pin
an old release. The empty Go compatibility field avoids breaking historical
benchmark source compilation; it never selects another runtime.

Framed transport fixture tests now use in-memory pipes instead of a fake Wasmer
command. The same reader and cooperative completion join own linked execution;
no runtime-specific process factory or function/address patches remain.
Non-cooperative root/worker reclamation remains explicitly out of scope.

## Verification

Local macOS arm64 integration passed: focused race checks for generated base,
handwritten generated runtime, guest transport, host and snapshot packages;
SQL/auth/reconnect/sessions; Snapshot/Fork; repeated Start/Close; pure-memory32
traps/grow/max/failed-grow; mmap ownership/cleanup. The mysqlwire package currently
contains no standalone tests and is exercised through product integration.
Normal Python Close/idempotence and multi-client acceptance passed (2 cases).
The first sandboxed product run failed at localhost listen with EPERM; the same
suite passed with the required localhost execution permission. This was not a
product failure.

Initial normal check passed Go tests/vet and generated identity. Three old
publisher-fixture expectations initially failed (old six-asset versus current
four-asset contract, old native corruption filename, helper mock binding).
Fixtures were adapted to the existing generated-Go guard without weakening it;
the final current check passed 285 Python cases, 6 intentional skips and the
public-source inventory (604 files), including the restored shared provenance
and current WASM input-key checks. All Go tests/vet and generated identity passed.

The local wheel build passed host-only manifest/hash/Mach-O/notice checks. It
retains `public_release_ready=false`; local packaging is not release approval.
Installed host-only wheel smoke passed outside the checkout: serial 7, parallel
7, migration 2, intentional failure cleanup 2, and reaped-process audit all passed.
The installed platform contract passed 2 cases. SQLAlchemy passed 44 cases
(Start/Fork/Fork/Start, 11 each); external GORM passed 32 cases (8 each in the
same mode order). Tiny baseline/candidate sanity completed successfully in an
exclusive slot. No canonical campaign or new Ubuntu exact-artifact acceptance has been run. Full generated-guest Go race
adaptation and forced non-cooperative termination remain out of scope.

## Small runtime sanity

Three trials per state/case, sequential baseline then candidate, no concurrent
benchmark or compile work. This detects gross accidental regressions; it is not
a canonical campaign or a statistical equivalence claim.

| Median metric | Common baseline | Retirement candidate | Delta |
| --- | ---: | ---: | ---: |
| Start → SQL | 53.05 ms | 53.80 ms | +0.75 ms / +1.42% |
| Start ready CPU | 61.84 ms | 67.28 ms | +5.44 ms / +8.80% |
| Fork → first query | 118.71 ms | 121.75 ms | +3.04 ms / +2.56% |
| Fork ready CPU | 136.97 ms | 138.93 ms | +1.96 ms / +1.43% |

First Start observations were 66.61 versus 87.82 ms; the remaining observations
were 51.04/53.05 versus 53.80/53.34 ms. Peak observed ready physical footprint
was about 143 MiB at Start and 519 MiB at Fork in both states. No gross runtime
regression was observed, with only three samples and no tail conclusion.
The existing harness labels contain obsolete image-provisioning wording and a
`runtime_pid=0` counter placeholder. Normal generated-Go provisions no image;
only valid owning-parent process CPU/memory counters were used here.

## Current versus historical gates

Fifteen Python legacy fixture files (106 test functions, before parameter
expansion) and two Go fixture files are retained under `tests/historical`;
normal pytest excludes the directory and Go fixtures require
`historical_wasmer`. They document retired AOT/bundle behavior, not a second
supported runtime or current gate. Three Wasmer-era CI workflows were removed.
The old runtime can be reproduced from its exact historical tag.

Active shared guards include exact module/tag/origin and isolated environment
checks (`test_consumer_acceptance`), guest source/sysroot/archive identity
(`test_guest_provenance`, 9 tests), current WASM input keys
(`test_benchmark_inputs`), authenticated artifact transport/hash/retention,
generated wheel/aggregate identity, one-shot release planning and fail-closed
publication dry runs. The current check/build/release dependency closure contains
zero Wasmer engine executables, downloads, bundle caches or runtime startup.
Generic platform metadata and explicit rejection of retired inputs remain.

## Disk/resource lifecycle

All long local commands used the experiment guard with minimum 12 GiB free and
4 GiB owned budget; shared Go cache was reused with bounded compile parallelism.
Owned scratch was about 1 GiB during validation, below the budget. Preserve the
worktree/branch for review, compact inventory/results/checksums and raw validation
logs under the owned evidence directory. Reproducible `temp/pytest-of-*`, wheel
venv/consumer copies, local wheel/host staging, setuptools build/egg-info and
pytest caches are disposable once the final tests have ended. Do not delete the
shared Go cache, old experiments, reusable toolchains or another track's files.

## Retained material / residual risk

Repository/module/GPL-source reference files retain five Wasmer notice texts and
historical pins/inventories. Normal wheel selects 20 distributed generated-Go notice texts and the three
root LICENSE/NOTICE/THIRD_PARTY_LICENSES files; it excludes all five engine notice
payloads. Its root NOTICE still explains historical engine attribution without
claiming that the engine is present. WASIX/LLVM runtime and upstream GPL closure remain required, independently
of retiring the engine. Historical tests/retired CLI scripts are source/reference material,
not a second supported or continuously accepted runtime.

Exact-source macOS/Ubuntu immutable artifact release acceptance remains mandatory
before a later release. Local smoke does not stand in for a fresh release READY.

## Review evidence and remaining release work

Compact evidence and checksum manifest:
[`v043-retirement-evidence/`](v043-retirement-evidence/).
Raw logs and XML remain in the owned experiment evidence directory, separate
from reproducible binaries, wheel/venv staging and pytest scratch. The commit
retains the branch/worktree for independent Human Review; it does not merge,
change canonical version, dispatch Release CI, tag or publish.

Recommendation: approve the bounded retirement for Track A integration review.
There is no remaining live Wasmer product/runtime dependency; deprecated input
names, exact historical source/pins/notices and reference harnesses remain
intentionally. The real compatibility downside is removal of explicit legacy
runtime overrides. The released pure-memory32 mmap/guest path is byte-identical.

Fresh Ubuntu execution on a new retirement artifact and full exact-source GPL
source/build/provenance packaging/Release CI READY are still required for a later
release; current deterministic archive/source/identity/license guards remain
active. Local macOS product acceptance does not claim those release gates.
