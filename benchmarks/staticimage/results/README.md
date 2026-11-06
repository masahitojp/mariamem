# Issue123 — static initial-image constructor proof

Conclusion: **PASS for the bounded local Mac constructor/mapping proof**. The initial data image can be reused with private file mappings while keeping fresh per-child module/worker/TLS ownership. This does not establish engine/SQL correctness, performance, physical page sharing amounts, or product readiness.

Recommended next: a separately bounded real-engine A/B using unchanged guest bytes. Check SQL/isolation first, then Fork-to-ready, first SQL and full lifecycle, CPU and image-inclusive held-child memory. There is no reason to regenerate the guest to attempt that next step. Do not integrate this experimental helper directly.

The main objection remains that constructor savings can move to CoW faults later, and that most current Fork time belongs to server_init, which this change does not skip. A process-wide image also needs an explicit ownership/lifetime contract before productization; this proof uses a private factory with explicit Close.

## Identity and scope

- Baseline source_commit: `66f2fe9d4bbde9b20323e9ee9b1562f3af16b8a4`.
- Final tested source_commit: `85a714920baf99d1048ef95bc7d561db6034982c`.
- Unchanged guest SHA256: `6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`.
- Host: macOS27.2 arm64, Go1.27.3, CGO0, GOMAXPROCS4. This is not the macOS15 acceptance host or Ubuntu evidence.
- No MariaDB Start, constructors for engine startup, SQL, guest C build, CI, release or performance campaign. Generated data initialization and generated TLS helpers are executed.
- All existing generated code/guest input bytes unchanged. Experimental additions: one base mapping helper and its fault test, plus standalone factory/tests/runner under benchmarks/staticimage. The helper delegates growth, counters and ownership to the existing MemoryMapping implementation. No automatic fallback.
- Git source object kind and clean checkout checked with scripts/git_identity.py before builds. result.json records test binary hashes and source file hashes. Runtime logs are bound to their original source, not the later report commit.

## Results

| Check | Result |
|---|---|
| Normal vs image: all initial256MiB bytes, mutable globals, DataEnd and data-segment/drop state | PASS |
| Distinct Module, ThreadPool, MemMu, MemSize and function table owners | PASS |
| Static/data1/TLS/BSS/init-flag writes private to child; sibling and file bytes unchanged | PASS |
| Read-only backing FD; child A Close leaves B usable | PASS |
| Factory Close rejects new acquisition but existing mappings survive | PASS |
| Eight concurrent acquisitions create exactly one image | PASS |
| Factory Close vs eight concurrent acquisitions; subsequent admission stays closed | PASS |
| Worker shared linear memory with private TLS/stack globals; join before unmap | PASS |
| Failed grow preserves logical size; growth stays at same address and exposes zero bytes through maximum | PASS |
| Write beyond enabled initial memory hits PROT_NONE (controlled subprocess) | PASS |
| Mapping/protection/unmap failures retain retryable ownership and correct counters | PASS |
| Build/read-open/writer-close/map/cache-close/metadata failure controls | PASS |
| Short backing and bad FD rejected before mapping | PASS |
| Final active mappings/reserved/RW counters | PASS: 0 / 0 / 0 |
| Ubuntu, real-engine/SQL, performance/RSS, production cache lifetime | NOT RUN |

Eight top-level tests plus six factory subtests pass on the final source. Four negative oracle controls cover dropped segment metadata, TLS global, DataEnd and initial-byte mutations (five byte locations). Guard rejection is an expected subprocess fatal fault, not an ignored test failure. Fault injection is controlled; this does not claim reproduction of OS exhaustion in a real MariaDB workload or a full generated-engine race test.

Full initial256MiB SHA256:
`a742525b94f94000341a4bdbd3136623a763a0c7c982035a5e97d065c8d3b2f7`

Mutable globals `[8388608,17998464]`, DataEnd17998969, completion flag2 at26981552. The retained TLS segment is505bytes. Copying only up to DataEnd would omit the completion flag; the experiment captures all nonzero pages of the full initial range instead. The image file has a fixed sparse2GiB logical length, not a2GiB resident-memory claim.

## Design boundaries

The factory runs normal NewWithMemory once without Start, writes nonzero initial pages, opens a read-only FD, closes the writable FD and unlinks the path before publishing. Each child maps it MAP_PRIVATE/PROT_NONE, enables the original256MiB range, calls NewFromSnapshot and restores globals/DataEnd/drop metadata. Each child runs future engine startup independently. Fn numbers/layout checks are pinned to this guest, not a general portable image format.

The image owner is explicitly closed. Acquisition is serialized with Close; cleanup failure never reopens admission. Actual child disposal still waits for workers and uses existing MemoryMapping.Close. First-build failures are sticky, with owned files retained until cleanup. This prototype does not settle product cache lifetime, arbitrary constructor-panic recovery, backing I/O failures while faulting pages, hostile external modification, or future generated layouts. Those are not hidden behind a product-ready claim.

MAP_PRIVATE behavior is validated by isolation/unchanged backing, not OS per-page physical accounting. Only constructor correctness is established; test durations are not benchmark results.

## Attempts and reproduction

Initial source5b74a303 passed. Its original receipts are under initial-5b74a303. Final source adds the concurrent Close/admission oracle and final-zero ownership assertion; the focused suite was rerun on that changed source. No failed runtime result was discarded or relabelled. The first rerun invocation was rejected by experiment_workspace because a completed workspace is not fresh; no process started from that invocation. The actual final run used experiment_disk with the same12GiB free /8GiB owned limits and600s timeout.

For reproduction, create an experiment workspace at the **tested source commit above**, set the normal owned evidence/temp environment, and run `python3 -B benchmarks/staticimage/run.py` under experiment_workspace (fresh workspace) or experiment_disk (existing owned workspace). The plan fixes scope. The runner compiles the two packages, records exact source/binary identities and invokes the focused tests once; the saved result contains exact command arguments. No release acceptance is involved.

After collection, retain the branch/source, report, compact logs/JSON and checksums; remove the worktree, binaries, Go caches and sparse files. Completion/cleanup receipt is recorded separately after cleanup.
