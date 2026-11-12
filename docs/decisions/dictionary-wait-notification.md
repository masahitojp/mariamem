# Dictionary eviction wait notification — candidate implementation approved

On2026-11-12 the Human approved proceeding to the product candidate and requested
early performance comparison. This approves implementation and verification,
not main integration, Qualification, release or closing#140/#156.

The product baseline is source_commit
`8df45792a927e440972266ee799d6f7223713e14`. Extract only the reviewed patch from
`7de45ac19718f37d1552824acfd6477dea6caf17`; do not merge experimental history.
The [fixed comparison and review basis](https://github.com/masahitojp/mariamem/tree/385df263443ade49cf8ee5f0155be2879e35deb6/benchmarks/pool-dict-measure)
retains all30 suites and exact original identities. P4 wall median546.3→552.4ms;
P8 506.6→469.0ms,3/5 pairs faster. Separate PREPARE timing has4/189→0/189 calls
over100ms, but typical PREPARE and P8 Fork are not faster. Accept these limits as
the reason to test a narrow correction, not as a guaranteed speedup.

## Authorized change

In `dict_sys_t::evict_table_LRU`, retain the original try-lock, slow lock and
unlock behavior; only bracket a contended slow wait with TLS-aware
`tpool_wait_begin/end`. A pool worker reports that it cannot make progress while
waiting, so other queued work may run. Uncontended acquisition bypasses the
notification. Pool-external calls keep notification's upstream no-op behavior.
Keep the canonical patch in guest/source.patch and current12.3.3 preparation pins
consistent. No experimental.patch or relaxed guest/body/table binding guard is
allowed in the installed product. No host/API, read count, timer interval,
buffer-pool default, purge shared-latch wrapper or global pool policy change.

The upstream API is not nesting-safe. Preserve the audited master-call boundary;
regressions must assert balanced WAITING state and the applicable caller
preconditions, rather than treating every dictionary wait as interchangeable.
Normal slow lock acquisition is noexcept. Exceptional termination, LONG/nested
input and arbitrary new callers are not covered by the previous controlled
prototype. Check concrete callable paths when binding the product regression;
do not introduce a general notification wrapper.

## Finite completion and ordering

1. Canonical source bootstrap: exact patch/base/profile guard, prepared dictionary
   file hash, source commit, no experimental overlay, reviewed guest and linked
   hashes. Use the existing UNQUALIFIED single-build route; neither old CI nor
   old benchmarks become receipts for this new source. Stage1 requires guest
   SHA2565f8b711f8efe31529c12847a093e92b8f962598e035cb1d5e253e41093feee20
   and linked SHA2567f34f46793406df2e7fbfec293ffbba3bb1491d07a714439d963dc1c49d06e12.
2. Install through the normal generator, preserving exact thread/CRC body/table
   validation. Update provenance, selected-source pins and required mirrors.
   Keep historical receipts bound to their original source; bootstrap success
   alone is not completed canonical regeneration or runtime acceptance.
3. Add a regression that exercises the actual patched guest's notification,
   not a test overlay supplying the missing begin/end. Reuse the controlled
   contention/queue harness for progress, exclusion, balanced accounting,
   uncontended/non-pool callers and disposal. Assert the actual notification
   is present; a removed begin/end must fail the regression. No new observer
   framework or open-ended natural-tail search.
4. Existing canonical two-build/full-regeneration and both-platform runtime
   verification (macOS15 arm64/Ubuntu24.04 x86_64), with SQL/lifecycle/ownership
   controls and the new regression, must pass before integration review.
5. Measure the installed candidate on the same Mac against8df45792 using the
   existing shop70 Go Pipe runner,16MiB/read1,GOMAXPROCS8/GOGC100,cap=P+1.
   Reuse the same fixed30-suite comparison:4 warmups,20 observer-off primary
   suites at P4/P8 (5pairs each),6 separate P8 SQL timing suites (3pairs).
   No tail exclusions or rerolls. Report wall/CPU/RSS, Fork/sample/cleanup,
   PREPARE p50/p95/max/>100ms. Do not delay this comparison for unrelated work;
   it can follow local candidate correctness while hosted acceptance is pending.

Submission hands CI off; resume on a Human result/status request. A failed
correctness/source gate stops that candidate for diagnosis. At the fixed exit,
report inconclusive or slower cases honestly and request the separate integration
judgment. No numerical speedup requirement or full natural-causality proof is
added as an adoption gate. Purge and the unobserved owner/pending/read-generation/
recovery sequence stay explicit limitations/backlog, not silent fixes.

## Initial checkpoint

Canonical patch migration, current12.3.3 profile and source/receipt mutation
controls are prepared on a branch from main. The old UCA source guard still
checks its exact original base and delta; only the exact reviewed dictionary
suffix is additionally accepted. The dictionary guard also checks the complete
prior canonical patch, so unrelated engine changes cannot hide in that suffix.
Normal verify/release-preparation source tests own this guard; the C builder
checks the actual prepared dictionary file before canonical compilation. The
UNQUALIFIED bootstrap checks the resulting prepared-source record; generic
development builds keep their existing experimental-input contract.

Generated/runtime/release pins still describe the old product until step2. This
intermediate branch is not merge-ready, and no new performance result exists.
The manual workflow retains its previously registered filename
`dict-wait-experiment.yml` solely for dispatch; it now builds canonical source
with no experimental overlay. CI receipts retain their own displayed name,
source and scope. Keep only compact receipts and reports in the candidate;
raw artifacts/generated scratch remain disposable or in CI artifact storage.

Local source checkpoint:125 focused tests plus25 subtests pass (dictionary/UCA
source guards, Development scope, preparation context/resolver and reproduction
tooling). Exact pinned upstream application, complete prepared-file hash and
reversal pass. Python/YAML/embedded-shell syntax, public-source boundary and diff
checks pass. The initial workflow assertion used a file-path spelling instead
of unittest's discovery spelling; the profile test also caught the registry's
stale descriptor hash. Both are corrected before CI submission. No guest/Go
runtime build or candidate benchmark has run locally at this checkpoint.

The current12.3.3 selected-preparation comparison producer is rebound to
`0d71a05918f99b90a233acf124c5fb81b23fdff4`, the exact canonical source checkpoint.
The13.0.2 producer and historical comparison receipts remain unchanged. This
updates the reproducible comparison target; full selected-tree comparison is
not newly claimed by the source-unit PASS.
The generic development-build boundary was additionally checked:21 dev-guest
tooling tests pass. The prepared-source precompile assertion applies only to
canonical builds; the bootstrap validates its exact prepared source in the
resulting UNQUALIFIED record. Experimental build support is preserved.

## Bootstrap failure and receipt repair — 2026-11-13

[CI43240513507](https://github.com/masahitojp/mariamem/actions/runs/43240513507)
at `ef956a759ed446fbd21db5c7a46a69101aaa961d` completed the single guest build
with both reviewed guest/linked hashes, then correctly failed the dictionary
source-record guard. The [compact diagnosis](../reviews/dictionary-bootstrap-43240513507.json)
binds the original source, artifact and build-log digest. `modified_files` omitted
`storage/innobase/dict/dict0dict.cc`: the canonical migration removed its former
experimental-patch inventory path without adding a normal preparation entry.
This is missing provenance, not an observed compiled-guest byte mismatch.
The failed run remains failed; its guest artifact was not uploaded.

The repair records the dictionary file's actual final digest in the common
preparation manifest. A regression invokes that producer with stubbed archives
and source helpers through default and selected preparation, checking both the
returned and saved records. Both cases fail before the repair and pass after it.
The receipt guard additionally tests a missing entry, alongside wrong hashes.
No expected hash or runtime/source-patch behavior is changed. Resubmit the same
UNQUALIFIED bootstrap; installation, actual-guest controls, platform acceptance
and the fixed comparison remain the subsequent authorized steps.

Local repair verification:89 tests and28 subtests pass across dictionary/UCA
guards, guest input/resolver/preparation, dev-guest tooling and preparation
reproduction controls. Touched Python syntax, both source-only guards,
public-source boundary and clean diff checks pass. No local compiler/runtime
or performance campaign was run for this manifest-only repair.

## Installed candidate checkpoint — 2026-11-13

Bootstrap43246097319 passed at e3d020e5. The [installation evidence](../reviews/dictionary-installation/README.md)
records normal generated installation, unchanged full worker/CRC/data guards,
the21-case actual-guest regression, normal local verification and the completed
fixed30 performance comparison. These are new receipts for this installed
candidate; the earlier prototype evidence remains historical. The canonical
two-build/full-regeneration and both-OS workflow is prepared for handoff.
Its acceptance and a separate integration judgment remain outstanding.
