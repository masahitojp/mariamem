# v0.5.0 exact-width narrow writer integration

The maintainer approved formal adoption after the
[design and bounded verification](v050-exact-writers-design.md). This change
removes the extra neighboring-byte memory operands from generated 8/16-bit
atomic stores, RMW and cmpxchg. For users, it removes one implementation cause
of interference between independent adjacent flags/counters. Earlier SQL
corruption was **not** demonstrated, so this is not evidence that a measured
SQL corruption rate has decreased. Same-target ordinary/atomic overlaps and
general shared-memory correctness remain unresolved.

Local formal regeneration and focused runtime/consumer checks passed. Native
Ubuntu x86_64 verification is handed to the branch-only development workflow;
it is **pending, not PASS**, in this report. This is not RELEASE READY, final
Qualification, Product Validation, a new race census or a publication decision.
No main merge, tag or publication is performed.

## Source and ownership

The approved design baseline is source commit
`a64d8b78d38f4047793b6d2f3f9e7f80bc4edf76`. Earlier bounded fixes are
`82f3c2bcef1518dadf5138a03e11dcfeb3db2de6`, and the
[impact study](v050-shared-impact.md) records the real-guest paths. Runtime
implementation and all tests/workflow are committed at
`f66727dda49d1b4ca2c7e814e218587c051f7f97` on
`experiment/v050-exact-writers-integration`. Subsequent report commits do not
change that runtime. Main at task start was
`098b0144ed50835da792ba811d11e0a1c8b000b2`; concurrent documentation work
advanced it to `920fb99ca2de5ac2e07863e39365749098ac122f` before cleanup.
Those changes are separate from this branch and were not overwritten or merged.
Source identities were checked as
commit objects with `scripts/git_identity.py`, rather than inferred from tag
objects. The tested private host's VCS stamp is the implementation commit with
`vcs.modified=false`; the control host is the clean design baseline.

Ownership remains in `scripts/runtime_atomic_loads.py` (historical filename),
`scripts/runtime_correctness/narrow_write_*` and `scripts/generate_runtime.py`.
Generated Go was adopted from the formal generator, never edited manually.
The installer strictly matches original converter bodies, rejects missing or
duplicate referenced definitions, changed shapes and repeated adaptation.
All emitted i32/i64 narrow load/store wrappers and generic narrow RMW/cmpxchg
cores are adapted; absent guest wrappers are exercised by a real-opcode fixture.
Full-width atomics, ordinary accesses, guest data layouts, public API, minimum
Go version and supported platforms remain unchanged.

On macOS arm64, stores use STLRB/H with DMB ISH, and compare-exchange uses
LDAXRB/H and STLXRB/H with retry, CLREX on mismatch and DMB boundaries. On
Linux amd64, stores use memory XCHGB/W and cmpxchg uses LOCK CMPXCHGB/W.
RMW loops use existing exact-width reads and these width-specific compare
primitives. AtomicEA still checks logical bounds/alignment first. Operands are
truncated and old values zero-extended. Unsupported platforms fail explicitly.
The [actual host disassembly](v050-exact-writers-integration-evidence/native-disassembly.txt)
confirms 1/2-byte guest operands on the tested native arm64 binary; ABI stack
loads/stores are separate. ARM exclusive monitor granules can still cause
retries from nearby writes. On x86, failed cmpxchg can write the observed target
value back: target-width CAS does not promise readonly-memory support or no
physical write. Cache/bus traffic is not measured by operand width.

The fixed guest has 147 generated narrow writer call sites, mapped in the
earlier impact study. It contains no narrow cmpxchg instruction. The generic
core remains covered for other valid converter inputs; this does not introduce
another guest or a converter upgrade.

## Formal build and independent regeneration

The guest was rebuilt through `build_generated_guest.py --development-output`
from an immutable clean clone of the design baseline, using the pinned builder
image `sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f`.
Its receipt correctly names source **a64d8b**, not the later runtime commit.
This is one development guest build, contract `development-unqualified-v1`,
not the two independent guest builds required for release qualification.
The existing source, ordered guest patches, SDK/Binaryen inputs and build
options are retained in the [guest receipt](v050-exact-writers-integration-evidence/guest.json).

| Identity | Result |
| --- | --- |
| MariaDB guest | 12.3.3; Wasm `7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c` |
| Linked Wasm | `3b63079109c895f3e90895f86b57e48d9f8e14f13ce945021c88e20c4f4fd9ba`, unchanged |
| goccy converter | `730057c146463f663e8774587bc96fb2bea91af8`, unchanged |
| Converter archive | `1adc74bb1594ed1d300d9382b9da27402728939fc021024d977e9c98afd2467f` |
| Native patched converter | `2e127643180dbf5f7c96875497b7e8a080d93bbb7b8b3711c55165d8828146a6` |
| Converter patches | Existing 9 plus prior Fd_allocate/bulk fixes = 11; all unchanged |
| Generated base before / after | `2f336d438520c1fabae86b4aaf2de014c334425d88e038da839442cdb793010b` / `b43554887688b079987c77ed954dd62ad75ec9616c7df0f5979d81e4cc5c8932` |
| Canonical provenance | `98e389d019f4a2d09350bace9c8c691de8926bcffb9d1781c9d9ce1880b64a97` |
| Tested private host | `0d858ac5a3d2d88e7f6bd923657ef1ccc89bbe321d8d6f824855e8b0cee68703`, clean f66727d |

First translation used `translate_guest.py`, then `setup_candidate.py
--source-only`, then `generate_runtime.py`. Its raw translation manifest equals
`release/generated-go-translation.json` exactly. Independent
`regenerate_release_guest.py --guest-dir ... --output ...` repeated translation,
the unchanged memory32 oracle, adaptation and installation in another tree.
Every output byte, including handwritten ownership glue, matched canonical
source: [proof and complete inventory](v050-exact-writers-integration-evidence/regeneration.json).
There are 62 translated files; handwritten inventory grows from 21 to 26.
The only translated-file delta is `code/base/base.go`; five new owned files and
provenance complete the [exact output delta](v050-exact-writers-integration-evidence/generated-delta.json).
Guest function bodies/data and raw converter output are unchanged.

License evidence records source-only continuity and the new provenance hash.
Historical linked-library audit/host facts are retained as historical facts,
not relabeled as a new audit. Distribution and Python inventory mirrors bind
the updated evidence; notice/license contents and dependencies are unchanged.
A pre-existing tracked `.log` was renamed `.txt` byte-for-byte to restore the
public-source boundary, with its saved hash index updated. No guard or failure
oracle was relaxed.

## Verification results

Local environment: macOS 27.0.1 arm64, Go 1.26.8, Python 3.14, Node 26.9.0;
exact receipts are in [platform.txt](v050-exact-writers-integration-evidence/platform.txt)
and [python-tools.txt](v050-exact-writers-integration-evidence/python-tools.txt).
The private wheel uses the existing 0.4.7 package label because no release
preparation/version bump is part of this change. It is never published.

| Check | Result / evidence |
| --- | --- |
| Formal guest build | PASS; unchanged accepted hashes, guest receipt and build/phase records |
| First translation + independent regeneration | PASS; exact inventories and provenance match |
| Existing memory32 negative/positive oracle | PASS; 2,472 cases including 1,693 expected traps, independent regeneration log |
| Canonical source, ownership/provenance/license/mirror negative checks | PASS; 22 focused source tests; `source-oracles.txt` |
| Canonical `verify.py check` | PASS; Go tests/compile/vet, public-source check, Python 582 PASS / 37 SKIP / 18 subtests PASS; `canonical-check.txt` preserves reasons and scopes |
| Native base primitives | PASS; `native-base-tests.txt` plus focused integration `-race`; ASM silence is not a race proof |
| Real converted Wasm narrow-family oracle | PASS; 44 exported operations (36 narrow + 8 full-width controls), 1,305 cases, heap/mmap with/without `-race`; `narrow-results.json` and reference/cases receipts |
| Old 26-case probe | 24 PASS, **2 diagnostic FAIL** preserved; `probe-results.json` and individual logs |
| Bounded shared feasibility matrix | 80 executions, values/forbidden-value checks passed; **2 expected heap ordinary-race FAIL**; `feasibility-results.json` and individual logs |
| SQL/transactions, concurrent sessions, independent DBs, Start/Close/cleanup | PASS; existing Go integration/default/generatedmemory suites; `native-integration.txt` |
| Snapshot/Fork/LoadSnapshot and integrity rejection | PASS; 28 Python integration tests including owned-Snapshot rejection, plus 49 Snapshot checks; `snapshots.json` |
| Installed-wheel Python consumer | PASS, 7 tests; `python-consumer.txt` |
| SQLAlchemy installed-wheel dogfood | PASS, 44 tests across 2 Start / 2 Fork runs; summary and per-run logs/XML |
| GORM zero-options source-module dogfood | PASS, 32 cases across 2 Start / 2 Fork runs; summary and per-run JSON/TXT |
| Real guest control versus final host | PASS; 5 scenarios × 2 hosts × AHI OFF/ON; outputs agree, `guest-comparison.json` |
| Native Ubuntu 24.04 x86_64 | PENDING CI handoff, not local PASS. Prior emulated spike evidence is not native verification |
| Runtime on minimum macOS 15 | SKIP; local OS is newer. Private wheel label/minimum binary checks do not substitute for execution on macOS 15 |
| Final Qualification / Product Validation / full race census | NOT RUN, outside this approved integration task |

The new real-Wasm oracle executes actual i32/i64 load/store, all six RMW kinds
and cmpxchg at 8/16 bits plus full-width controls. It compares trap/value and
whole-memory hashes against Node's WebAssembly engine. It covers all valid
lanes/endpoints, unsigned address wrap, misalignment/OOB, operand truncation,
zero extension and compare success/mismatch; concurrent same-target increments
exercise the converted wrapper. Generic runtime tests also cover adjacent
ordinary writes, shared RMW operations and ordering with wider atomics.
Finite ordering tests and instruction review supplement the approved design;
they do not prove the entire Wasm-to-Go memory model.

The two original diagnostic failures are unchanged: an explicitly rejected
wide-read neighbor control under `-race`, and conflicting ordinary heap
accesses. The feasibility matrix likewise retains its ordinary shadow-overlap
positive controls (one report each for 8/16-bit heap cases). Native narrow ASM
has no detector instrumentation, so previously visible wide-Go CAS conflicts
become invisible even on heap. Mmap also has observability limits. Neither
absence of reports nor functional PASS establishes general safety. Initial
fixture/probe/matrix invocations used a relative GOCACHE and failed before
semantic execution; absolute-cache retries supply all verdicts. Initial network
restriction during independent regeneration was retried with required access.
Setup failures are retained and are never counted as semantic failures/PASS.

The guest comparison exercises four connections with 120 commits, conflicting
update/rollback/commit, repeatable-read visibility, 32 parallel connection
lifecycles and 1,000 indexed reads, at default AHI OFF and explicit ON. Both
hosts report `12.3.3-MariaDB-embedded`. These are bounded regression scenarios,
not instrumentation of every writer site, a performance benchmark or evidence
that every schedule is safe. Handshake behavior remains covered by the existing
wire/consumer checks and the earlier A–D implementation.

## Reproduction and remaining boundary

Use source identity inspection before every build. From the implementation
commit, build the accepted guest with the canonical pinned builder and explicit
development output; run the first translation/adaptation/generator sequence
above, then independently regenerate with `regenerate_release_guest.py`.
The guest JSON contains complete fixed inputs and all phase logs retain commands.
For the new fixture, run:

```sh
python3 scripts/runtime_correctness/narrow_fixture.py \
  --converter-archive /absolute/path/to/pinned/wasm2go-upstream.tar.gz \
  --output /absolute/path/to/fresh/narrow-fixture
python3 benchmarks/spikes/v050-correctness/probe.py --output /absolute/path/to/fresh/probe
python3 benchmarks/spikes/v050-shared-feasibility/run.py \
  --converter /absolute/path/to/independently-built/wasm2go \
  --output /absolute/path/to/fresh/feasibility
python3 verify.py check
python3 verify.py integration
```

Set `GOTOOLCHAIN=go1.26.8` and an **absolute** task-local GOCACHE. The fixture's
archive path builds/validates the same pinned converter and ordered 11 patches;
an existing converter instead requires its independently verified manifest.
`build_alpha.py --ci-candidate` from a clean implementation clone builds a
private host/wheel; existing SQLAlchemy/GORM runners and installed consumer
tests exercise it. See receipts for exact commands and artifact hashes.
The branch-only `narrow-atomic-native.yml` checks a native Ubuntu x86_64 runner,
fixed Go, real-Wasm oracle, heap/mmap/race, canonical source and focused actual
guest regression. It has read-only permissions and publishes no product.
CI owns execution after submission; review its receipt when requesting status.

Guest identity and Snapshot format are unchanged by this writer-only change.
Previously valid 12.3.3 Snapshots do not require recreation for it. Snapshots
from the older differing guest still fail identity validation; the guest-ID
tamper negative test was rerun. This task does not rebuild a historical v0.4.7
Snapshot; the actual saved old-guest rejection evidence remains in the A–D
report. No compatibility relaxation or snapshot migration is introduced.

Remaining limits: genuine same-target ordinary/atomic conflicts, wider or
misaligned ordinary accesses spanning narrow targets, bulk/SIMD/host overlaps,
compiler behavior and mixed-size native/Go ordering still need broader analysis
if general shared-memory correctness is required. Legitimate contention/retries,
ARM reservation-granule interference and detector blind spots remain. No
specific new SQL result error, hang or crash was reproduced by these scenarios.
There is no measured risk probability or performance/resource benefit claim.

The accepted three bounded fixes remain verified; this adds formal narrow-writer
adoption. **General shared-memory correctness: NOT ESTABLISHED.** Native Ubuntu
receipt review, final exact-candidate Qualification, performance/Product
Validation and Human release decision remain. Any broader correctness work
must keep these failure controls and exact source identities. Stop at this
verification handoff; release approval has not been given.

Evidence is compact: saved raw/sanitized log identities are in
[saved-files.json](v050-exact-writers-integration-evidence/saved-files.json);
the full guest-build log is represented by a marked final excerpt, phase/input
receipts and its raw hash. Recreated source/download/build/cache/wheel trees
are disposable after preserving committed source and these receipts.
