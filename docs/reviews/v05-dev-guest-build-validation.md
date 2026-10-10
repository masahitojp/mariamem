# v0.5.x single-pass dev guest — Human Review

## Decision packet

**Accepted for main integration on 2026-10-11.** The current guest completed
one C/WASM build, fresh translation/installation/native compilation, SELECT 1,
commit/rollback and three isolated Fork generations. This is **UNQUALIFIED**, not
Release evidence. MariaDB stable-version exploration can be the next separate task.

Phase 1 is already integrated/pushed to main
`70ac70ce0a4ccda403aa290dffa1d0bac0d8728b` (approved fast-forward from `b1666e4`).
Canonical Python check: **563 passed, 35 skipped, 18 subtests passed**; generated
inventory/input/guest identity passed. Its 19 changed files and check-log hash are
in [integration evidence](v05-dev-guest-build-evidence/phase1-integration.json).
Phase 2 was fast-forwarded into main at
`ee48a2a50fe71e79564ab1dde42c45594f220438` after explicit Human approval.
Integration introduces no new implementation delta. The exact guest/native
execution identities below remain the tested identities; this approval/status
update is documentation only. Release qualification is unchanged.

## What changed

| File | Responsibility |
| --- | --- |
| `scripts/build_generated_guest.py` | Explicit external single-build output; reuse the pinned recipe and source preparation |
| `scripts/regenerate_release_guest.py` | Explicit development branch before the existing Release route |
| `scripts/dev_guest.py` | Bind source/tools/WASM/translation/installation/binary; fresh disposable host copy; SQL smoke |
| `scripts/generate_runtime.py` | Verify development installation inputs; mark dev provenance; retain default canonical checks |
| `tests/test_dev_guest_tools.py` | Identity, namespace, stale generation, failed-stage and existing guard rejection regressions |
| `tests/test_dev_guest_smoke.py` | Explicit new host/SDK; SQL transactions, three Forks, child/parent/process/thread cleanup |
| `docs/development.md`, this report/evidence | Usage, stage boundaries, exact results and limitations |

No canonical guest, generated runtime, runtime compatibility constant, tool pins,
release receipt, workflow, guard, version or public API was changed. A fresh product
copy excludes existing generated code/native binaries and installs the newly
translated runtime. Its compatibility constant is bound to the actual WASM hash.
Generated source and handwritten overlays from this trial are byte-identical to
the canonical runtime; only disposable `provenance.json` differs (UNQUALIFIED).

## Exact execution identities

- Guest build source: `594edd37723f625ae9726766ba6b1ec806e2faaa`.
- Successful native pipeline source: `62a6f95709f1ebfd0153f10d7c68f3221741f9e0`.
- Actual optimized WASM: `33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`,
  **18,560,271 bytes**. Matches the current accepted guest, but one build provides
  no independent reproducibility evidence.
- Final documentation commits do not retroactively acquire that runtime evidence.
  [Guest summary](v05-dev-guest-build-evidence/guest-summary.json) and
  [native summary](v05-dev-guest-build-evidence/native-summary.json) retain original
  receipt hashes, input/output hashes, tool identities and complete-inventory digests.
  Source inventories are reconstructible from the exact Git commits.

### Guest origin versus native-stage origin

The original guest receipt remains unchanged. A later clean native-stage commit
may reuse it only if changes are confined to docs/tests and three host-stage
scripts: `dev_guest.py`, `generate_runtime.py`, `regenerate_release_guest.py`.
Original changed bytes are checked against the actual historical Git commit;
unchanged bytes against the current tree. Native inputs are separately recorded
and checked again after smoke. All other changes, including source preparation,
C recipe, tool pins, guest patches and Go source, require a fresh guest build.
This is a narrow stage boundary, not a general artifact cache or receipt promotion.

## Correctness and failure checks

| Check | Result |
| --- | --- |
| Focused dev/helper, observer/cache, generated inventory, guest recipe and Release tools | **119 passed**, 8.24 s |
| Actual newly compiled host: SELECT 1, commit/rollback, three independent Forks and Close | **1 passed**, 1.75 s |
| Existing owned-lifetime tests: concurrent Close/FD handoff, surviving child, spawn/startup failures, new baseline from child | **3 passed**, 5.02 s combined invocation |
| Existing multiclient/reconnect tests with explicit integration flag | **3 passed**, 1.46 s |
| Canonical generated inventory/pins/guest identity | PASS |
| Actual wrong source, WASM, tool identity, missing provenance | Rejected before native work |
| Stale/mixed generated source, missing installation bindings, partial generation, output/symlink/Release namespace mistakes | Rejected by focused tests |
| Existing Release guard on actual dev receipt | Rejected: wrong build contract |
| Same scratch receipt deceptively relabeled as Release | Rejected: independent rebuild evidence missing/different |

The first session-test invocation skipped three tests because the explicit
integration flag was absent; they were rerun and passed, not counted as executed
in the first invocation. Normal and failure paths reap host processes (therefore
release their OS mappings/FDs); the owned-lifetime oracle checks FD return and
handoff, and the smoke checks SDK reader-thread shutdown. This does not claim
broad guest-race/goroutine qualification or native Ubuntu acceptance.

Two initial attempts failed/stopped before C compilation: a writable build mount
omitted tracked `build/go.mod` (clean-tree rejection), and a downloads-only attempt
was stopped to improve provenance binding. Neither produced a guest build.
The first native attempt completed translation but rejected installation into a
reserved `internal` namespace: **97.93 s**, no success receipt. The fix installs
into a fresh external staging directory then moves into the disposable product,
without relaxing namespace protection. Source-stage binding permits this fix
without rebuilding the unchanged C guest. Failure cost is preserved separately.

## Measured development cost

Environment: Apple M1, 8 logical CPUs, 16 GiB; macOS 27.0.1 arm64; Go 1.26.8;
Python 3.14.8, pytest 9.1.1, PyMySQL 1.2.3. Guest built in Docker Linux arm64,
Ubuntu 24.04.5, VM 8 CPUs/~7.75 GiB, existing image `mariamem-wasix-build:0.4.7`.
Empty task-owned `/root` and `/work`; pinned SDK/LLVM downloaded/verified anew;
existing C recipe uses 3 jobs. Image identity is retained in evidence. One successful
trial, with the native retry described above; no statistical speedup claim.

| Observed phase | Wall s | User CPU s | System CPU s | RSS high-water MiB |
| --- | ---: | ---: | ---: | ---: |
| LLVM preparation | 142.718 | 135.018 | 3.473 | 105.5 |
| Guest source preparation | 40.368 | 7.345 | 4.439 | 46.8 |
| Guest compile/link | 436.090 | 494.765 | 159.055 | 235.3 |
| WASM postoptimization | 12.126 | 56.953 | 0.635 | 539.9 |
| wasm2go conversion | 67.980 | 77.010 | 9.088 | 3732.0 |
| Source adaptation | 15.483 | 18.039 | 0.333 | 950.7 |
| Installation | 17.364 | 19.804 | 0.546 | 957.7 |
| Generated Go compilation | 126.575 | 195.401 | 4.199 | 2434.0 |
| SQL smoke (command boundary) | 1.981 | 0.623 | 0.281 | 525.9 |
| Native pipeline total (contains the preceding native phases) | **236.523** | **341.536** | **41.265** | **3732.0** |

Guest whole-route wall is approximately **919.254 s**, from Docker start to receipt
publication. This is a wall-clock timestamp estimate, not a monotonic measurement;
it includes downloads/checks/extraction not covered by all named phases. Whole-route
CPU/RSS is unavailable. Successful guest plus native boundaries total approximately
**19 min 16 s**; including the failed native attempt approximately **20 min 54 s**
of processing, excluding human/debug gaps. Parent/child phases overlap: do not sum
all records or treat wait4 RSS as simultaneous container/process-tree footprint.

Converter compilation (0.841 s) used the task cache populated by the failed native
attempt; generated runtime compilation was new. Go cache speeds compatible native
work, not C guest compilation. Raw normalized phase records include actual tools,
exit statuses and explicit inputs/outputs. Artifact sizes are in native summary.

Historical `release/generated-go-build.json` reports compile/link 658.249 s and
postoptimization 15.928 s under different conditions. It is not a controlled
comparison. The demonstrated reduction is structural: one independent C/WASM
build for a development trial instead of the Release recipe's two. No measured
percentage improvement or equivalent Release guarantee is claimed.

## Use and Release boundary

Follow [developer commands](../development.md#single-pass-unqualified-guest-development).
The existing pinned Linux arm64/root build recipe remains required. The normalized
[actual Docker launcher](v05-dev-guest-build-evidence/guest-command.txt) shows its
mounts; if overriding `build/`, copy the tracked `build/go.mod` unchanged first.
Use a committed clean checkout, fresh external outputs and task cache paths.

Native stage:

```sh
python3 scripts/regenerate_release_guest.py --development \
  --guest-dir "$MARIAMEM_DEV_WORKSPACE/temp/dev-guest" \
  --output "$MARIAMEM_DEV_WORKSPACE/temp/dev-native"
```

Supply pytest/PyMySQL and the documented Go environment. The tool invokes translation,
adaptation, installer, fresh host compilation, binary identity and SQL smoke once.
Success publishes `development.json`; failures publish `failure.json` where output
creation has begun, or fail before output exists. Missing success proof is failure.
No long-lived manager or new workflow/orchestrator/cache manager is introduced.

Release still requires accepted inputs, independent clean builds, canonical generation,
platform correctness/race/trap checks and final source/license/artifact/consumer guards.
Dev output cannot substitute for these checks. No Release guard was changed.

## Cleanup and remaining limits

Task-owned downloaded SDK/toolchains, sources/objects, translation/product copies,
private hosts, logs, venv and Go caches are disposable after compact evidence and
pushed commits. Cleanup removed 6,365,577,216 bytes (approximately 5.93 GiB),
including the completed worktree and task caches. Compact evidence and the
completed workspace receipt remain; no task-owned path over 1 GiB remains.
Existing user Docker image/global Go toolchain are
protected; no Docker/global cache pruning is authorized.

This validates the current guest and build route, not a new MariaDB version.
The Linux builder restriction remains; native smoke ran on macOS arm64 only.
The next task is stable MariaDB exploration; candidate adoption still needs its own
Human decision and full Release qualification. No canonical artifact, v0.4.6 tag
or published asset changes are included here.
