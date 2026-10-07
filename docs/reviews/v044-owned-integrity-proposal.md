# Owned Snapshot integrity

Status: experimental contract under product review, October 7, 2026.
Audit Decision 5 has not been adopted; this document does not authorize
productionization. The fixed PoC contract and measured evidence remain valid
inputs to the discussion. The existing spike is not merged, and its CI does not
qualify a different production candidate. Shipped v0.4.3 still validates
inventory and content on each Fork.

## Fixed PoC contract; product adoption remains open

Snapshot creation/import performs complete integrity validation. mariamem then
owns the exact validated backing, which supported operations do not mutate.
Fork uses that same resource to create an isolated mutable database; it does
not recompute all content hashes. Cheap structural, lifetime and guest checks
may remain. Silent media corruption arising after ownership is established is
not promised to be detected on every Fork. This is not a hostile same-user
process security boundary.

An external import must validate format, inventory, content and guest compatibility
before succeeding. Later source-path changes or deletion must not affect the
owned Snapshot. Trust must bind to the verified resource, not a path string,
mtime or verified flag. A readonly descriptor does not by itself prevent another
writer from changing a named file: ownership must eliminate those supported
write aliases or import into independent internal backing.

Supported child writes, file growth, DDL and transactions must stay private.
Fork/Close admission pins resources through startup. Successful children can
continue after Snapshot Close. Failed/partial startup and repeated Close must
release descriptors/mappings without process or goroutine accumulation.

## Evidence supporting the proposal

The independently qualified spike passed macOS arm64 and Ubuntu x86_64 import,
isolation, generations/order, concurrency, growth, commit/rollback and tested
failure cleanup. It retains exact readonly file descriptors and maps those
resources privately, without a persistent manager process or different OS models.

Across minimal/10/100 MiB payloads, measured ready p50 improved 54–74% in Go and
72–83% in Python. Python's preparation-inclusive 16-child suites improved 39–62%.
The entire 100 MiB Go suites improved 8–20%; broad SQL scans remain workload cost.
These are spike measurements, not a promise for a future release.

The price is one retained descriptor per prepared file, extra acquisition/handoff
code, and the explicit later-corruption contract. Python external import copies
input into independent backing, adding roughly 90 ms in the tested 100 MiB case;
subsequent children amortize that work. This copy is distinct from per-child copies.

## Possible bounded productionization boundary, if approved

Start from current main; integrate the smallest reviewed acquisition, descriptor
handoff, private mapping and lifecycle changes. Do not merge experiment history
or carry its benchmarks/CI/version edits wholesale. Keep guest identity unchanged.
Use the spike's focused tests as source evidence, adapt them to the actual
production boundaries and qualify the new exact candidate on both platforms.

The concrete changed dependency is acquisition → Snapshot handle → host startup
→ generated runtime mapping → teardown, including Python inherited descriptors.
It warrants focused content/inventory/guest rejection, independence/order/growth,
parallel startup/use/Close and failure-resource acceptance. It does not warrant a
new MariaDB upgrade, broad performance campaign or full guest race redesign.
Run current handwritten race checks where the changed synchronization depends on
them. No new canonical release benchmark or publication is authorized here.

Product adoption and productionization require an explicit future decision.
Decision 4 explores public path/alias/introspection/fixture migration. Ownership
can be introduced while preserving the existing signatures; those removals are
not an automatic prerequisite or consequence of this decision. If compatibility
writers temporarily remain, their exported artifact and owned Fork backing must
be separate, as demonstrated by the spike. Do not expose owned backing as a
mutable filesystem path merely to preserve an old Path accessor.

## Exact evidence

- CI code: `730b64db7059d0374e2e00680416de77cdb346eb`.
- Report/evidence: `09443d4de999b833cddc2ca536d43f9120130c79`.
- Comparison baseline: `b83dd2c8bcda6d57def2cbbe9f9b9226d93cd2ca`, not the release tag.
- [Both-platform CI](https://github.com/masahitojp/mariamem/actions/runs/37541652530).
- [Compact review and measurement limits](https://github.com/masahitojp/mariamem/blob/09443d4de999b833cddc2ca536d43f9120130c79/benchmarks/v044-owned-ci-review.md).
- [Product model proposal](v044-product-model-proposal.md).
