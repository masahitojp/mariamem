# Within-call validation reuse under prepared RSA keys

Branch: `experiment/prepared-auth-keys`. Experiment only; nothing is merged or
productionized. Measurements are pending CI. No performance result is claimed.

## Exact conditions

- A: existing test RSA keys, current validation path.
- B: the same keys and native bytes, with the **existing**
  `benchmarks/validation_reuse.py::patch` applied only to a disposable source copy.

The probe skips two redundant AOT digests: sidecar validation consumes the digest
already checked by artifact resolution, and host startup receives that same
verified build identity within the current call. Initial manifest/native artifact
hashes, sidecar/build identity and snapshot inventory checks remain. No persistent
cache, new trust scope, restore change or MariaDB setting change is introduced.

`benchmarks/prepared_validation_reuse.py` archives the same exact committed source
twice, applies the existing patch to B only, runs artifact/snapshot/host tests on
both copies, and builds both Go canonical benchmark runners once before timing.
Both conditions use **one shared read-only native path** and one generated,
checked, disposable 2048-bit RSA pair. This avoids the previous control-original
versus reuse-private native-path confounder. No private PEM is uploaded; key hashes
are recorded and temporary material is deleted. Native/key hashes must be unchanged
after all trials. Public SQL probes check plugin ACTIVE and exact public-key match;
all 14 recorded Start/Fork diagnostics per invocation must prove successful loading
without key generation. Existing grant-bypass semantics remain unchanged; this is
not a full caching_sha2_password authentication exchange test.

## Paired measurement and immutable reuse

Dispatch `guest-build-boundary.yml` on this branch with
`prepared_validation_experiment=true`. Both macOS 15 arm64 and Ubuntu 24.04 x86_64
jobs reuse the existing identity/hash/provenance-verified experimental WASM/AOT
when their input identities match. No guest source/runtime/CPU settings changed.
The workflow verifies the AOT again after measurement. It does not release anything.

Two warmup pairs and 20 measured pairs alternate A/B and B/A ordering. Each runner
uses the canonical 1,000-row fixture, first COUNT readiness, and ×1/4/8 worker order.
Fixtures are separately prepared with identical logical contents. Memory diagnostics
are **off**; initialization events and sampled CPU/RSS remain. Separate-process
runs retain normal process/runtime lifecycle, not a prewarmed Database or cache.

Results are workflow artifacts named `initialization-<platform>-<source-sha>`,
under `benchmarks/results/init-prepared-validation/`: raw pair JSONs,
`summary.json`, `summary.md`, plus platform AOT provenance/manifest. The summary
records exact source SHA, modified-copy source hashes, both runner binary hashes,
native/key hashes, platform identity and paired differences. Raw files retain Go
version/server/CPU environment, CPU samples and structured guest counters.

The waterfall includes Fork→SQL, public-outside-host, host validation, combined
preparation, restore, embedded init and launch-envelope residual. Public-outside-host
includes preparation before host startup **and** trace/write/return tail afterward;
these are not separately timed. Combined preparation is calculated per DB before
quantiles. Launch residual starts at spawn-begin to avoid mistaking guest execution
overlapping `cmd.Start` for negative runtime overhead. It still includes unobserved
runtime/CRT setup and ready/diagnostic delivery; it is not pure Wasmer time.

Each parallel trial contributes one within-batch median to paired-difference
statistics; per-DB quantiles and batch completion quantiles are also retained.
Do not sum medians, treat parallel DB observations as independent batches, or call
historical hypothetical subtraction a new measurement. CPU collection has startup
and shutdown blind spots; process CPU includes other guest threads and Unix `ps`
has platform-dependent precision. No thresholds gate informational performance.

## Results to complete after CI

For each platform ×1/4/8, report control/reuse p50/p95 for the waterfall and
paired differences, especially combined preparation and end-to-end latency.
Compare restore/init/launch residual to check whether they remain stable rather
than attributing every observed delta to digest reuse. Summarize guest CPU and
sampled whole-run CPU; host hash CPU is not directly stage-instrumented.

Answer how much repeated validation is causally removed, whether it reaches first
SQL, whether concurrency degradation improves, what initial artifact/sidecar and
snapshot work remains, and whether restore becomes the next dominant bucket.
The prior baseline is [prepared-key lifecycle](prepared-key-lifecycle-baseline.md).
No current result permits asserting that restore is the next target yet.

## Ready for main?

**Prepared RSA keys:** the prior experiment provides strong latency/CPU evidence,
but the disposable mapped-key approach is not production-ready. Before integration,
decide key lifetime/location and test-only security behavior; verify key load
failures and clean startup, Snapshot/Fork/multi-client/timeout cleanup on both
platforms, packaged key/runtime identity and license/provenance, and clarify the
authentication-exchange boundary. No production provisioning design is selected
or implemented here. This validation experiment does not waive those checks.

**Validation reuse:** no integration decision until this paired measurement and
integrity tests pass; any future change must keep initial artifact/sidecar/snapshot
validation and make the within-call immutable-input assumption explicit. Do not
merge the exploratory context-string/variadic prototype as a finished API design.

## Recommended next 0.2 FAST step

Exactly one next step: analyze the completed paired CI artifact and determine
whether measured preparation savings reach end-to-end Fork readiness. The choice
of a subsequent product/storage probe remains pending those data; none is
implemented or selected prematurely.
