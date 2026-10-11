# v0.4.7 upstream wasm2go migration — qualification in progress

This candidate uses goccy upstream plus nine managed patches, with the exact
v0.4.6 MariaDB Wasm. It does not update the guest, public API, Snapshot format,
minimum Go, mysql driver, VFS, or handshake-version behavior. Publication and
main integration require the final Human decision.

## Input and migration identities

- Pinned main: `386a62c3669e37bb8aaad58cd0aca8da893b3d80`.
- v0.4.6 source: `b56be17206b6beef18f55c8ea39b254638da8590`; annotated tag
  `09d7b82e1900318dde45d08bebd9328ea35e6ef7` (verified separately).
- Track A final evidence: `9a130274bff87d4a814cc1cac6c6cb6c1cc62a5f`, tested
  implementation `c06e908aef1055ca718b6da0212bb578c51a1a48`.
- Upstream: `730057c146463f663e8774587bc96fb2bea91af8`; archive SHA-256
  `1adc74bb1594ed1d300d9382b9da27402728939fc021024d977e9c98afd2467f`.
- Previous fork: `ac98bcf00c17d8531f0c071a9836d0b50975e7ff`.
- Unchanged guest SHA-256:
  `33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`.
- Canonical Go1.26.8, WASIXCC0.4.7/LLVM23.1.0, Binaryen133 pins unchanged.
  No local guest compile or guest patch change. The accepted Wasm was retrieved
  from v0.4.6 Release run 38040418075, artifact 11665901597; ZIP CRC and SHA verified.

[The ordered patch inventory](../../benchmarks/spikes/wasm2go/PATCHES.md) records
all nine responsibilities. Five existing patches remain byte-identical, two are
upstream context ports, and two retain required helper/export capabilities.
The production pipeline downloads upstream only; historical fork pins remain in
historical experiments and attribution, not current generation inputs.

Only generated `code/base/base.go` changes: bulk fill/copy directly load logical
MemSize; the bridge consistently uses logical size and retains contention tests.
All generated MariaDB function bodies, data, mmap owner and Snapshot/Fork source
remain byte-identical. The unused non-shared whole-backing alias contract is not
adopted. Shared memory behavior is verified by fixtures and the concrete guest,
not inferred solely from a small diff.

## Reproduction and source attribution

Use the disposable workspace guard (24 GiB budget, minimum free 20 GiB), pinned
Go1.26.8 and a checksum-verified v0.4.6 guest directory. The initial migration
ran translate_guest.py, the source-only setup_candidate.py adapter and the canonical
generate_runtime.py installer; accepted inventories were reviewed from that output.
Subsequent independent reproduction uses the unchanged canonical entry point:

```sh
python scripts/regenerate_release_guest.py \
  --guest-dir /absolute/accepted-guest \
  --output /absolute/fresh-regeneration
```

Independent extraction, nine patch applications, converter build, memory32
fixtures, translation, adapter and installation reproduced all committed bytes.
The only generated-file delta is recorded with before/after SHA-256 values in
`release/generated-license-evidence.json`. Existing guest/symbol audits remain
historical; upstream MIT text matches the preserved notice. Corresponding source
still includes upstream archive, ordered patches and guest/runtime inputs.
No release guard or evidence trust model has been weakened.

## Qualification status

Local macOS27.0.1 arm64 results (actual execution):

| Boundary | Result | Evidence / limits |
| --- | --- | --- |
| Nine-patch application + converter focused tests | PASS | Clean pinned upstream archive; emitter/SSA/export tests |
| Independent canonical regeneration | PASS | All committed outputs byte-identical; unchanged guest hash |
| Pure memory32 matrix | PASS | 2,472 cases, 1,693 expected traps, grow/max/state; host exit 0 |
| `verify.py check` | PASS | Go tests/vet, 570 Python PASS / 36 SKIP / 18 subtests, public source/oracles |
| `verify.py integration` | PASS | Handwritten/runtime race targets; Go integration/default/generated-memory; 27 Python and 49 Snapshot checks |
| New consumer/guard focused tests | PASS | 131 tests; missing Go1.27 evidence / wrong compiler rejected |
| Actual host-only wheel build | PASS | SHA-bound independent checkout, notices/licenses/archive identity |
| External Go1.26.8 / Go1.27.2 | PASS / PASS | Exact private module proxy, no replace; default/LoadSnapshot failure lifecycle and public smoke |
| Installed Python3.14 wheel / GORM / SQLAlchemy | PASS | 32 GORM and 44 SQLAlchemy cases; runtime cache remains empty |
| Paired production-backed race census | Executed; limited visibility | Both tests PASS / zero reported signatures; see boundary below |
| Paired Product Validation | SQL/cleanup PASS; high-water review open | 118 original +16 bounded follow-up cells; [resource/tail report](../../benchmarks/v047-product-validation.md) |
| Native macOS15 and Ubuntu24.04 artifacts | PENDING CI | Local macOS27 does not satisfy exact macOS15 guard; no cross-compile substituted |
| Public tag / public wheel smoke | NOT RUN | Publication explicitly unauthorized |

The local wheel and external consumer source was
`6097c2cf821a18a445738604675de7c96b814d26`; later changes are benchmark observation,
reports and reproduction only. Final CI must bind final source/artifacts itself.
The wheel SHA-256 was `7e34165214504eba15df4207cfb90ee863d2f1c4e3a75acb84bf0f2317f49258`.
An initial worktree wheel attempt was correctly rejected for absent VCS build
stamping. An independent `.git` directory checkout of the same SHA passed;
the identity guard was not bypassed. Initial offline dependency failures were
retried with network access and are not runtime failures.

Native macOS15 / Ubuntu24.04 final-artifact qualification remains a separate CI
gate. Exact-source corresponding GPL source, both platform artifacts, archive
hashes and guard READY will be evaluated by the existing verify workflow.

The existing zero-length bulk-memory bounds edge case and full-generated-guest
shared-memory race limitation remain known boundaries. Focused race PASS is not
full guest race freedom. No general forced termination/reclaim work is included.

## Race observation boundary

The same `-race` default Fork/isolation and repeated-concurrent-lifecycle tests
were run against exact v0.4.6 and the candidate. Both completed with zero
reported signatures. This does **not** mean the historical 149 guest signatures
were fixed: that old census used a different guest and Go-heap backing.
Go1.26.8 `runtime/race.go:isvalidaddr` accepts heap/data ranges, not arbitrary
syscall mmap memory. A separate positive-control probe performs the same
unsynchronized byte update on Go heap versus anonymous mmap: the heap run
fails with race reports; mmap exits without a report. The difference is
observability, not correctness.

Consequently: no newly reported race in this pair, no resolved historical
signature claimed, and full mmap guest-race coverage remains unproven. The
focused owner/thread tests, controlled-trap fixtures and byte-identical guest
access instructions provide complementary evidence, not a race-freedom proof.
No race suppression, address-specific patch, alternate production backing or
translator race adaptation was introduced.

## Human Review / release boundary

The minimum-maintenance change is upstream + ordered purpose-specific patches,
not a new guest or runtime design. Keep patch responsibilities separate; future
upstream updates must clean-apply, regenerate independently and rerun these
semantics/consumer gates. The export-name collision policy and imported-memory
metadata ordering are explicit integration requirements, not optional patches.
There is no current shibukawa URL/pin in production scripts or generated input
pins; historical diagnostics and attribution intentionally preserve it.

Final release readiness is **BLOCKED pending native Release CI qualification
and Human review of the measured parallel high-water envelope**.
Local PASS supports submission, not publication. The existing workflow will run
`operation=verify` for the final pushed candidate, with no main merge/tag/publish.
It must independently accept macOS15 arm64 and Ubuntu24.04 x86_64 artifacts, both
Go toolchains, installed wheels/ORM, source/NOTICE/provenance and release guard.
The agent stops on successful CI submission per AGENTS.md; no intermediate
acceptance-only or guard-only dispatch is requested.

Known boundaries remain full guest-race observability/freedom, pre-existing
zero-length bulk-memory edge cases and non-cooperative forced termination.
No new correctness defect has been established by the local gates; the historical
race signatures cannot honestly be marked resolved. A Human decision should
retain those limitations explicitly rather than treating a zero-report mmap run
as their removal. The MariaDB guest upgrade, handshake changes, VFS/Snapshot
optimization, memory64 and broader compatibility work remain separate tasks.

## Product/resource decision

[The comparison](../../benchmarks/v047-product-validation.md) preserves original
three-trial normal cells and one large trial. SQL/transactions and mapping release
passed; cumulative allocation and final live heap are unchanged to the measured
precision. Full original data and a separate four-pair tail follow-up are retained.
Do not summarize the result as an unconditional performance/resource PASS:
four-parallel candidate Peak RSS reached about948 MiB versus baseline823 MiB in
the follow-up, despite medians813/815 MiB and equal cumulative allocation. Typical
CPU/wall cost does not show a sustained tax, but peak/tail frequency and causality
remain INCONCLUSIVE. No optimization was attempted.

Human decision after native CI: accept this measured transient upper envelope
with the known race-observation limits, or request a separate bounded resource
investigation before release. Publication remains unauthorized in this task.
