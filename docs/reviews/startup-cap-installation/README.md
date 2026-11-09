# Normal startup concurrency: canonical installation

The bootstrap input is verified and the canonical Go candidate is installed.
Independent two-build reproduction and both-platform acceptance remain pending;
this is not main adoption, Qualification, a version decision or publication.

- Base/product: `a3b2b6457147e2b8edbd31fec77ab6ec04f11b22`.
- C bootstrap origin: `8d3da071015f4b6a3b0e77197e12648850d3d910`,
  [run42509593737](https://github.com/masahitojp/mariamem/actions/runs/42509593737).
  [Authenticated compact receipt](../startup-cap-ci-42509593737/README.md).
- New guest: `8e3761eaf65df842191c98cfc4bf493ae08df9374204774f453b9349e21711df`.
- The initial static data, CRC validator full body/table and19 bound worker/J1
  function bodies match the previous guest. One bound function changes generated
  partition file; its full normalized body hash is unchanged. Binding remains
  exact, with no alternate guest or wildcard accepted.
- Across21688 generated Fn definitions,1412 have literal textual differences.
  All1024 fused SIMD helper bodies have the same multiset, after replacing only
  each helper's own name. Substituting those **verified full-body identities**
  at call sites leaves differences only in Fn17499(load) and Fn18569(recovery).
  This analysis does not rewrite generated code or weaken byte-for-byte CI
  regeneration. Partition moves/helper numbering account for the larger diff.
- Binaryen133 reproduces the exact CI guest while emitting the function map;
  the map hash itself is unchanged. `function-map-proof.json` records that check.
  Actual native host attribution passed at1b446e53 and is recorded in the license ledger.

## Verification boundary

`binding-comparison.json`, `generated-delta.json` and `function-map-proof.json`
record exact identities/counts. `local-result.json` binds local native checks to
its clean installed-source commit. Later receipt/documentation edits do not
relabel that run. The unit controls include source regions, CRC/worker binding,
workflow inventory and candidate workflow requirements. The dedicated candidate
workflow requires two independent C builds, macOS15 arm64/Ubuntu24.04 x86_64
independent Go regeneration, native normal/binary-prepared SQL, two pristine
children, cleanup, actual UCA/lexer/CRC/worker controls and forced J1 controls.
Build-evidence mutations include missing/changed startup-concurrency records.

The single bootstrap's UNQUALIFIED record is preserved. `completed=false` and
`full_guest_regeneration=false` remain in the current build ledger until the
canonical campaign succeeds. Old lexer acceptance stays under its old source.
No performance campaign or additional setting was introduced;16MiB/read1 remains.
The [decision](../../decisions/startup-global-concurrency.md) owns the fixed exit.

## Reproduction and retention

Build from the pinned canonical source using `scripts/build_generated_guest.py`.
Use the explicitly unqualified bootstrap route before selecting a new guest hash;
its receipt must pass `dev_guest.verify_guest` against its original clean source.
Translate with the pinned `translate_guest.py`, adapt with `setup_candidate.py
--source-only`, compare complete CRC/thread bodies/static data, then install with
`scripts/generate_runtime.py`. Inputs, raw translation inventory, host identity,
fixtures and license attribution must agree. `scripts/regenerate_release_guest.py`
on both hosts subsequently compares every generated file against the committed
output; no hand-edited generated body is accepted.

Only compact receipt/proofs are committed. WASM archives, native binaries,
compiler caches, conversion output and raw diagnostic diffs remain disposable.
Two early local command setup errors and unsupported system Python3.9 stopped
before usable translation; the successful conversion used a Python3.11 venv.
No failed attempt is promoted into runtime PASS.

The first local host carried the enclosing checkout's VCS stamp and was rejected
by the attribution check. Its results were not promoted. The successful retry
explicitly bound GIT_DIR/GIT_WORK_TREE to this worktree and used buildvcs=true;
the clean binary stamp is1b446e53b8a09a95f96233c02d1211518233be2b. Runtime code
was unchanged. See `local-setup-limitations.json`. CRC832 vector/alignment and80
page-validation cases, actual UCA/638 lexer tables and corruption controls,
worker isolation, Snapshot/Fork/Close, J1 fixture input generation and actual
retained-library attribution passed. J1 execution and native SQL differential
remain in the both-host candidate CI, not claimed by the local input generation.
