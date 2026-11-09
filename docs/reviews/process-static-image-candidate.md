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
| Product candidate macOS15/Ubuntu24.04 CI | Not yet observed; no product matrix PASS claimed |

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
