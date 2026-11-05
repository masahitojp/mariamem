# Prepared UCA tables — candidate preparation review

The next adoption decision is whether to accept a **production candidate** for
prepared UCA tables. **Recommendation: prepare that candidate, rather than adopt
the experimental branch as-is.** The Human has already authorized this next
preparation step after reviewing the experiment; this record adds no approval
barrier to that work. The decisive evidence is lower Fork CPU/elapsed and whole
fixture time while the measured ASCII comparison speed is retained.

The strongest objection is that immutable generated data creates a maintenance
obligation and changes the guest image/worker binding. One-host experimental
success does not close that obligation. A version-bound input package, a dedicated
verification path, canonical regeneration and finite both-platform acceptance
address it; they remain unfinished. No main adoption, Qualification, version or
publication decision is made by this preparation review.

## Reviewed object and independently checked evidence

Inputs were reconstructed from the preceding Human-approved report/request:

- Artifact/source: `e33fc6ce3bae390c6dda0fd92d024d8094df8731`,
  [report](https://github.com/masahitojp/mariamem/blob/e33fc6ce3bae390c6dda0fd92d024d8094df8731/benchmarks/ucaboosterreuse/README.md).
- Experiment product base: `bc00b8e66e5fd57bc9b2127001faf8e05952b417`.
- Actual guest origin: `f24c308bb6758e97722f4cb26bcb1de7c2df16b9`;
  [host-stage identity](https://github.com/masahitojp/mariamem/blob/e33fc6ce3bae390c6dda0fd92d024d8094df8731/benchmarks/ucaboosterreuse/results/inputs.json)
  is recorded separately. The report commit is not a newly executed runtime head.
- Candidate-preparation base: current main
  `676515eb9244fc501b5a600791b0cf0a6174fecd`. Preserve its prepared-execute,
  last-statement-alias, bounded-pipeline and newly adopted opt-in Go Pipe changes.
  Preparation initially used c27061f1; current main was merged before submission. Do not merge exploratory history.

All result files were checked against the artifact's committed SHA256SUMS.json.
The saved read-only reducers independently rederived the ten-process summary,
replayed the nineteen-body/TLS relocation proof and its semantic rejection
controls, and rederived the supplementary MemoryInit copy summary. No timing
trial, guest execution, build or CI run was repeated for this review.

| Prior condition | Disposition and evidence |
|---|---|
| Original comparison consumers retained | SATISFIED in artifact: experimental patch changes constructor/data, not the four UTF8 consumer gates |
| Actual resolved tables equal original producer | SATISFIED for artifact's fixed profile: checks.json.gz / guest-table-verification.json contains all six full-table matches in root and Fork |
| Native SQL/Snapshot/isolation/cleanup | SATISFIED bounded artifact corpus: primary records and semantic/negative controls; not arbitrary application/collation support |
| CPU, elapsed, RSS, SQL and whole fixture retained together | SATISFIED: five alternating process pairs, all records retained; no parallel-scaling inference |
| Larger initial image accounted for | SATISFIED as standalone component only: 2,754,112 extra bytes and copy measurements; not an exclusive Fork phase decomposition |
| Exact worker ownership binding | SATISFIED for experiment only: full19 bodies, explicit Fn219 package move/Fn4068→Fn4069 mapping, proven BSS relocation, identical505 TLS bytes; canonical candidate binding remains UNVERIFIED |
| Source/tool identities and cleanup | SATISFIED for artifact: original/host-stage inventories, hashes and post-cleanup replay retained; no receipt relabel |
| Both supported OSes / production candidate | UNVERIFIED; macOS27.2 arm64 is the only new runtime/performance host; prior baseline Ubuntu evidence does not qualify this guest |

The reviewed source-to-main delta preserves the same baseline guest identity
`96129c…`, but changes host/wire code. This permits carrying the hypothesis and
input data forward, not relabelling the measured experiment as a current-main run.

## Gaps and detection net

1. **Diagnostic side effect in the spike.** The experimental constructor uses
   `getenv("MARIAMEM_GUEST_TIMING")` to allocate/rebuild/memcmp the original table.
   Ordinary profiling of that guest therefore includes extra work. This was
   correctly excluded from primary measurements, but must not become the product
   timing contract. Existing ordinary CI has no prepared-table verification-vs-
   profiling separation oracle. Required: dedicated private verification trigger,
   supplied only by a package-local runtime test through the existing constructor
   seam; ordinary `guestEnvironment` and timing behaviour stay unchanged.

2. **Generated data is not yet a maintained input.** The artifact's experimental
   patch directly includes a5.49MB generated header. This PR prepares three
   JSON text u16le inputs (77,038 bytes;57,661-byte compressed payload before base64), pinned to the exact prototype and
   source/Unicode/archive hashes. The codec recreates the exact original header
   SHA `ce55cdcc…`; normal guest preparation does not consume it yet.
   The existing public-source guard rejected binary gzip files; the explicit
   source-text container preserves that boundary without a new allowlist exception.
   `tests/test_uca_prepared_input.py` detects corruption, rehashed wrong numeric
   data, framing/size errors, wrong source/archive/layout/level, unsafe paths and
   accidental output overwrite. It does **not** independently prove Unicode
   semantics or replace the original MariaDB generator/runtime oracle.

3. **Canonical source/regeneration/binding outstanding.** Integration must follow
   [guest patch policy](../decisions/guest-patch-management.md): keep
   guest/source.patch canonical, emit the numeric header deterministically during
   preparation, hash actual source inputs/header in provenance and reject source
   drift. Validate against the pristine source before applying the canonical
   constructor patch. Do not keep the development manifest bypass or promote a
   one-build UNQUALIFIED receipt. Existing build/regeneration/source inventory
   guards detect stale guest/Go/metadata; they do not update pins automatically.

4. **Native platform acceptance outstanding.** Candidate-specific macOS arm64 and
   Ubuntu x86_64 checks must verify actual table bytes, SQL/Snapshot/cleanup and
   changed ownership bindings. Native unit ASan checks and baseline's old Ubuntu
   receipt cannot fill this row. Existing product CI only exercises the committed
   guest; it cannot establish a future guest's correctness before regeneration.
   Run a bounded candidate workflow/test selection after concrete canonical inputs
   exist. Release CI/Qualification and publication remain separate decisions.

5. **Current-main performance is unmeasured.** The experiment's five-pair result
   supports selecting this mechanism; its exact speedup is not a guarantee for
   the future canonical candidate. Repeat the same small paired fixture once
   canonical code/data identities are fixed, retaining SQL and RSS as well as
   Fork CPU/wall. Do not grow this into a pgmem/P4/resource campaign.

## Candidate implementation and finite exit

The already-authorized preparation keeps:

- Three immutable pointer-free numeric tables and the original optimized readers.
- Exact known builtin default UCA1400 selector/shared-level identity; original
  construction for all unmatched identities. No charset/collation support removal.
- A single explicit generated-data owner/input manifest and maintenance recipe
  using the original pinned MariaDB generator, not a second Unicode algorithm.
- Verification-only full original-vs-prepared memcmp, with negative corruption
  control and an assertion that normal timing never enables verification work.

A package-local runtime test can supply the private verification environment in
`startInstance`'s existing `construct` callback, before `newMemoryModule` runs.
That avoids a new public SDK/API or ambient-environment pass-through. A concrete
test must also prove startup/Fork/cleanup and unsupported-identity fallback; the
experiment's private installer must not ship as product support.

Candidate exit is finite: canonical prepared-source equivalence; required
independent regeneration/identity checks; exact worker fixture update; bounded
both-host correctness and negative controls; one same-fixture performance
comparison. Stop and report a specific missing input if this requires new worker
ownership semantics, a generic ABI matcher or cloning live guest state. InnoDB
settings, buffer size, prewarming and unrelated wire/resource work stay outside.

This PR's deliverable is **the reviewed implementation boundary and tested input
package**, not a guest implementation or runtime adoption. No concrete candidate
runtime SHA, new both-platform PASS or merge readiness is claimed here.

## No additional gap found in these boundaries

- Input table re-expression preserves all original numeric bytes and exact typed
  header identity; no evidence files are rewritten by the check command.
- Main's host/wire/Go Pipe changes are retained by the preparation base.
- No Go/Python public API, guest/source.patch, generated runtime, release ledger,
  version or existing historical receipt changes in this PR.
- Historical measurements remain at their original source/cohort identities.

Review limits: source/evidence replay and packaging/tooling tests only. No new
C compiler, native DB, guest runtime, profiling or hosted CI result is asserted.
