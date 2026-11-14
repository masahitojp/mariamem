# Prepared-output bounded measurement — regression found

Fixed main eb175ae23292c1c40cfbeb4b9b73132873c4cc6f and candidate
d0aca17352708c5cb85812e0f4c11b228d3006e7 use the same MariaDB12.3.3,
Go1.26.10/CGO0 and unchanged Python SDK. Both standalone clean-source binaries
carry verified VCS revision/modified=false build metadata. This single Apple M1
comparison uses Python3.11, pure Connector/Python26.7.0 and PyMySQL1.2.3 seed.
Five fresh-DB pairs alternate baseline/candidate order. Execute+fetch is timed;
every result and column name/type is checked against known expected values and
its peer. One warmup per case is excluded. Retained RSS is an end observation,
not peak RSS or a demonstrated memory improvement.

| Case | 7 iterations, median paired candidate/main ratio | 101 iterations, median paired ratio |
| --- | --- | --- |
| One row | 1.334 | 1.004 |
| 1,000 rows | 0.855 | 0.870 |
| One64KiB binary value | 1.044 | 1.275 |

The second run increased iterations because the first had large variance;
both complete results are retained. All five101-iteration bulk pairs favor the
candidate, but all five64KiB pairs regress. There is no predeclared numerical
PASS threshold, universal speedup or total upgrade-time saving. **Do not declare
performance clear or proceed to adoption on this evidence.**

Five-second stack samples retain the original whole-host observations. Counts
are not normalized CPU-cost attribution. Both old/new C serializers append hex
nibbles individually; the initial hypothesis that only the new one does this was
incorrect. Samples show JSON scanning, guest MemoryEA and serializer execution.
The candidate added a second complete JSON map decode solely to detect row-field
presence. A host-only fix removes that extra parse while retaining absent/null/[]
distinctions and rejecting mixed representations. Focused tests and an isolated
before/after decoder benchmark are retained separately; actual-guest performance
must be repeated on its committed binary before claiming the regression fixed.
No guest/C/runtime-generation input changed for this fix.

## Functional observations on both exact binaries

P2 vectors22, additional P2 matrix20, P2 repair15 and P3 chain/OUT14 all match
their original native fixtures, on both main and candidate (71 scenarios each).
These are current real-guest observations; prior native reference packets are
unchanged. Metadata add/drop/type changes, one execution per reprepare, reuse,
SQL errors/recovery,129 results and PS_MULTI_RESULTS advertisement are exercised.
They are not full-native factory/lifecycle acceptance or unrestricted driver
support. Detailed per-case results retain original oracle comparisons.

Frame probe:65535/65536/65537 and16MiB−1024 byte values match expected bytes,
metadata and following SELECT on both binaries.16MiB−1 triggers the same fatal
Proc_exit2/ERR2013 and loss of that SQL connection on both; this existing limit
behavior is not relabeled recoverable or repaired here. This is a finite sample,
not an exact maximum search. The first probe mistakenly assumed recovery after
oversize; its partial observations survive, and the revised probe records each
error/following-query/owner-close independently before comparing old/new.

## Reproduction and measurement setup failures

Use the runner on the pushed `experiment/output-product-performance` branch,
`benchmarks/prepared_output_compare.py`; each result pins its complete runner SHA
and file hash. Prepare a budgeted4GiB workspace with8GiB free reserve. Clone clean
standalone baseline/candidate repositories at the above SHAs; use Go1.26.10,
CGO_ENABLED=0 and `go build -p 1 -trimpath -buildvcs=true` for each host. Create a
Python3.11 venv with the above client pins. Invoke the runner with explicit host,
SDK root, source SHA, output path and iterations7/101. No absolute local folder
is a product input. Saved probe tools accept `--workspace` with baseline/candidate
clones and artifacts/hosts arranged as their named paths show. For packet probes,
use the same candidate SDK and unchanged tests/fixtures against each binary.

Before these valid measurements: one helper run used a relative script path;
one used Python3.14 whose local SSL lacks the client's TLSv1 import constants;
one rejected binaries without VCS stamps because Go1.26.10 does not detect a
linked-worktree .git file. These produced no accepted timing results. Absolute
entrypoints, Python3.11 preflight and standalone .git directories resolved setup;
no source-identity assertion or client contract was weakened. Compiler cache and
clones are active temporary inputs until final comparison, then must be removed.
Raw evidence hashes and path substitutions are recorded in normalization.json.

## Host-only repair follow-up

Candidate ef4d5cd97f718ebaaa5b2fa0d7999e3e6b169b9e was rebuilt from a clean
standalone clone with exact VCS metadata. The same101-iteration/five-pair runner,
main baseline, clients and workloads observed median candidate/main ratios:
one row0.987;1,000 rows0.827;64KiB0.998. All five bulk pairs improve;64KiB pairs
range0.950–1.140, so the earlier all-pairs regression does not repeat, but there
is no universal improvement or tight no-regression bound. All values/metadata
still match. Retained RSS remains noisy; no peak or resource-saving claim.

The isolated JSON decoder benchmark median changed from2.103ms/280KiB/~35
allocations to1.523ms/140KiB/18 allocations. This isolates removal of a redundant
whole-message parse, not attribution of all end-to-end effects. No guest rebuild,
upstream patch, generated-code edit or new engine hook was needed.

The71 unchanged native-reference scenarios pass again on this exact fixed host.
The same five frame cases match main. An initial saved-reference comparison
reported false differences because live Python column tuples were compared with
JSON-loaded arrays. Both original FAIL assessment and corrected saved-JSON
assessment are retained; values were not changed. Changed-hash/error-code negative
controls still differ. The revised comparator normalizes only JSON container
representation before comparison. The oversize fatal Proc_exit2/ERR2013 remains
identical to main and is not a new output-route change.

Same-source follow-up submissions: Development43530112119, public43530115529,
installed43530119031. All three passed on the fixed host; final-ci.json and the per-run directories
retain their evidence. No prior run is relabeled. Main adoption, the selected-route
disposition and release remain unapproved.

## Retention update (#158, 2026-11-14)

This text preserves the original investigation sequence; adoption subsequently
occurred under [the ADR](../../docs/decisions/prepared-output-reuse.md). Compact
results, partial/failure frame observations and comparison summaries remain here.
Raw stack samples, duplicate packet matrices, build inventories and CI bundles
were deleted from the current tree. References above to those saved payloads
describe [the original record](https://github.com/masahitojp/mariamem/tree/a45604e848ff8f58c684f05016b994b7e6e6f7eb/docs/reviews/prepared-output-product/performance-20261114),
not additional files promised here. These remain historical measurements.
