# Issue123: generated layout and explicit-owner platform check

This bounded experiment replaces the manually pinned scan window with metadata
produced from **all initial constructor bytes**. It does not adopt the prototype,
change public APIs or select a product-wide cache lifetime. Parent measurements
remain bound to their original source; this change has not been benchmarked.

The generator scans the complete initial memory outside Start/Fork. It emits a
4KiB-granular nonzero envelope, the complete memory hash, globals, DataEnd,
dropped-segment state and hashes of every generated code/base source. Runtime
aligns the envelope to its actual OS page size and retains only nonzero pages.
Anonymous memory supplies the zero pages. This includes state beyond DataEnd,
without knowing the address or meaning of an initialization flag.

`go run ./benchmarks/staticlayout/cmd -check` is a read-only drift gate.
Generate intentionally with `-output <path>`, inspect the metadata change, then
repeat full-memory/mapping/engine checks. The ordinary generation script is
**not modified** in this spike: adoption must wire this step into regeneration
and its mandatory CI, not rely on a developer remembering it. Runtime metadata
checks do not replace the complete-image/source gate. Some existing semantic
oracles still name addresses in the current guest; a future guest needs their
review even though the envelope itself is generated automatically.

## Owner contract verified here

| Resource/event | Owner and behavior |
|---|---|
| Image creation | One explicit factory; serialized first acquisition; a build failure latches and never silently retries/falls back |
| Unpublished writer/read FD, temp path, failed mapping cleanup | Factory retains each unresolved owner until confirmed disposal; Close retries retained debt |
| Published image | Unlinked readonly FD owned by the factory; private child mappings do not retain its Go host object |
| Factory Close | Stops future admission and closes image resources; existing child mappings remain valid; no hidden reopening |
| Child mapping | Child execution owner; worker join precedes unmap; never disposed by factory Close |
| New explicit factory after Close | New image/owner, independent of old live children |

The runtime adapter still uses a benchmark-controlled global factory and explicit
final close. It is **not** a finished product lifetime design. A process cache
would retain one FD/image until process exit; a lineage/Snapshot owner would
need internal ownership propagation and may share less across independent roots.
Neither retention policy nor a new public close API is approved here. Resolve
this boundary before product adoption; do not weaken DB/Snapshot cleanup claims.

## Finite verification and handoff

- macOS arm64 / Ubuntu x86_64, actual OS pages; CI Go1.26.10, local Go1.27.3.
- Clean exact source; source_commit validated before builds; generator and probe
  embedded VCS revision/clean status and binary hashes recorded.
- Deterministic complete-image regeneration; negative omitted-flag/hash/segment/
  source-metadata cases; pure envelope tests for4KiB/16KiB and new distant data.
- Existing complete256MiB equality/isolation, protection/Grow, concurrent
  acquisition/Close and forced-failure ownership tests, plus explicit owner epochs.
- Real DB Pipe Fresh/Fork × P1/P4,8 children each, and2 expected wrong-seed failures.
  Admission cap, row isolation, image count, FD/mapping/scratch disposal checked.
- No performance repetitions, native-server differential, product qualification,
  release, race-detector claim or automatic integration. CI logs/results retain
  exact source identity and checksums as artifacts, not thousands of repo files.

Run `python3 benchmarks/issue123layout/verify.py --work <owned-output>
--go-version go1.27.3` locally, inside the experiment disk/workspace guard.
CI uses the same script on both OSes. PASS is only claimed from actual receipts;
submission itself is not acceptance. Stop after submitting CI and return its URL.
