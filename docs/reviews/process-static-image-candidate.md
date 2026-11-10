# Issue123 product candidate checkpoint

The Human accepted lazy process-lifetime immutable-image retention on 2026-11-10,
prioritizing whole-suite execution time. This checkpoint implements that direction
from main `279fa530`, without importing the experimental branches. Adoption/main
integration and release are not approved by this record.

The current candidate initializes one readonly unlinked image lazily, maps only
initialized pages privately into each DB, and retains the image until process exit.
Per-DB Close still joins workers and releases its full mapping. No application
schema/rows or live InnoDB state is shared. Cache creation failure is latched;
unconfirmed cleanup retains retry authority and stops subsequent admission even
after cleanup settles. Go/Python ownership boundaries are recorded in the
[decision](../decisions/process-static-image-cache.md).

## Local verification

[Compact receipt](process-static-image-candidate/local.json), with
[checksum](process-static-image-candidate/SHA256SUMS.json), binds each source.
Observed host: macOS 27.2 arm64; Go 1.26.10; source checks on Python 3.14.10,
real runtime on Python 3.11.18 / OpenSSL 3.5.9.

| Check | Result |
| --- | --- |
| `scripts/verify.py check --scope full --profile daily` | PASS at `563f098d`; 68 source-owner tests, 1891 other tests, 114 subtests; 98 explicitly skipped; Go unit/vet and public-source checks PASS |
| Canonical ownership race packages including image factory | PASS at `563f098d` |
| Real Go integration/default/guest memory/worker-trap targets | PASS at `563f098d` |
| Go and Python Live; real Python SQL/routines/Snapshot | PASS at `563f098d`; 54 Python tests and 33 Snapshot checks |
| Full local `verify.py integration` | **FAIL at its final fixed-client comparison**, not full integration PASS |
| `go run -p 1 ./internal/generatedgo/layoutgen -check` | PASS at `16a7460c`; all 256 MiB initial bytes and 71 source identities match |
| `go test -p 1 -tags=integration ./tests/godefault -run TestProcessImageSurvivesIndependentRootsAndSnapshots -count=1 -v` | PASS at `16a7460c` |
| Product candidate macOS15/Ubuntu24.04 CI | PASS at `be08dac36194442d3cbbd95f0add7c002753ffa4`; see source-bound receipt below |

The final local comparison reported exactly `native C client profile differs:
python_minor`: its historical C-extension oracle requires Python 3.14, while the
local runtime is 3.11. Homebrew 3.14 here uses OpenSSL4 and cannot import the pinned
Connector/Python. No profile assertion or accepted exception was weakened.
The candidate CI runs portable core ownership/real SQL checks explicitly; it does
not claim this fixed-client native comparison, Qualification or performance.
Changes between `563f098d` and `16a7460c` are only the candidate workflow and its
test; runtime and generation sources are identical.

The real-DB lifetime case observed one image build for four acquisitions, one
retained FD, zero active child mappings and no cleanup debt. Initialized mapped
pages: 8,929,280 bytes (8.5 MiB rounded). The file has a sparse logical size of
2 GiB; this host allocated 27,000,832 bytes (25.75 MiB). These are file/page counts,
**not RSS**. Neither the sparse-file allocation nor timing from this single test
is a portable resource/performance promise.

## Both-platform candidate CI and review follow-up

[Run42673922578](https://github.com/masahitojp/mariamem/actions/runs/42673922578)
passed at source_commit `be08dac36194442d3cbbd95f0add7c002753ffa4`.
The [compact receipt](process-static-image-candidate/ci-42673922578.json)
records both job IDs/names, artifact IDs/ZIP digests, original member hashes,
structured results and retained-resource observations. Original ZIP and member
checksums were verified before reduction; routine logs are not copied into Git.
Both hosts ran Go1.26.10 / Python3.14.10: 64 source tests passed and the Python
runtime suite had 53 PASS / 1 SKIP on each host. The process-image case confirmed
one build, four acquisitions, one retained FD, zero child mappings and no cleanup
debt. macOS file allocation was27,000,832 bytes and Ubuntu8,392,704 bytes; neither
number is RSS. Development run42673923630 also passed at that same source.

The adoption review then found two external-consumer boundary defects that the
source-tree matrix did not cover: the private module ZIP and its source identity
omitted embedded `image/layout.json`, and the copied `tests/godefault` suite
imported private packages forbidden from its external module. The Human approved
these bounded fixes. Module inventory now includes the layout, with missing and
changed installed-byte checks and a source-identity mutation test. Public SQL /
Snapshot isolation stays in `tests/godefault`; internal image/FD/mapping assertions
move to `tests/generatedmemory`. A source check rejects private imports in the
copied external suite, and the candidate workflow runs both test boundaries.

The follow-up changes only packaging tooling, tests, candidate workflow and
records. Production Go/Python, `internal/`, `guest/`, generation inputs and
`release/` remain byte-identical to `be08dac3`; reuse the earlier both-host runtime
receipt only for that unchanged boundary. It is not a new exact-head matrix or
proof of the repaired installed-consumer path. Focused follow-up results are
recorded below; full final-artifact acceptance remains a Release responsibility.

### Focused follow-up verification

On the local macOS arm64 host, Python3.14.10 and Go1.26.10:

- `pytest tests/test_consumer_acceptance.py tests/test_static_image_workflow.py tests/test_go_fixture_completion.py tests/test_generated_release.py -q`:103 PASS.
- `pytest tests/test_e2e_installed.py tests/test_usability_examples.py -q`:23 PASS,
  3 SKIP (opt-in real-host examples),4 subtests PASS.
- Actual `prepare_proxy` output, loaded from an unrelated
  `example.com/release-consumer` module with all `tests/godefault/*.go` copied:
  `go list -mod=mod -tags=integration -e -deps -test -json .` has no package errors;
  the image package resolves `EmbedFiles: ["layout.json"]`. This checks package
  loading, not full installed runtime acceptance.
- `go test -p 1 -tags=integration ./tests/godefault ./tests/generatedmemory -run '^(TestIndependentRootsAndSnapshotsRemainIsolated|TestProcessImageSurvivesIndependentRootsAndSnapshots)$' -count=1 -timeout=3m -v`:both PASS.
  The first sandbox attempt was blocked at localhost bind; the same command
  passed with that restriction lifted. SQL/isolation assertions remain intact;
  internal diagnostics confirm one build, four acquisitions, one FD, zero active
  child mappings and no cleanup debt. No timing conclusion is drawn.
- Generated inventory, public-source boundary, local document references,
  compact-receipt checksums and `git diff --check`:PASS.

## Evidence and regeneration boundaries

The earlier prototype [CI42657516361](https://github.com/masahitojp/mariamem/actions/runs/42657516361)
remains bound to `378f8490`. It is not relabelled as this product candidate.
The previous five-pair Mac experiment's small whole-suite gain and Fresh/RSS
tradeoffs remain their original observations; this checkpoint adds no benchmark.

Canonical generation now produces the layout from the selected generated tree
in a disposable module. Old generated Go bytes and guest/release pins are unchanged;
only derived `image/layout.json` is added to generated provenance. Whole-memory,
omission, sibling isolation, TLS/grow, cleanup failure and latched-admission tests
cover the mapping boundary. Historical library attribution is reused only after
reconstructing its old provenance byte-for-byte without that metadata entry.
This is not a new linked-symbol audit or independent full C/WASM regeneration.

Raw local logs/caches are not repository results. Commands and sources above
reproduce the checks; GitHub artifacts retain compact CI logs/checksums. The
bounded candidate matrix uses manual `.github/workflows/issue123-layout.yml`;
normal PR Development checks retain their existing responsibility.

## Main synchronization after the bounded fixes

Development [CI42723709945](https://github.com/masahitojp/mariamem/actions/runs/42723709945)
passed `check`, `integration` and `Live required gate` at source_commit
`845aeedb185e8aa10746e75c67c68709347d6458`. The PR then incorporates main
`c375edbc1e77bf078f50abc75c9de32ce23a641a`, which already adopted Issue145's
shutdown mode selection. The only textual conflict was in project status;
both decisions/evidence sections are retained. Automatic merges preserve both
workflow classifications, static-image race targets and the new existing
shutdown/Snapshot/reSnapshot smoke in `scripts/verify.py`.

The earlier statement of unchanged runtime applies to the bounded packaging/test
follow-up through `845aeedb`, not this main synchronization. The combined host
runtime includes main's shutdown change; old platform receipts are historical
component evidence, not an exact-head combined matrix PASS. Normal Development
CI owns the combined source/smoke checks. No new performance measurement,
Qualification or release is claimed by this synchronization.
