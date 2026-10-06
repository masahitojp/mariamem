# v0.4.3 Track A — current-main integration review

- Baseline: `a23e450af19fd2086a008cc85ed35173f0103801`.
- Original reviewed retirement: `6ea2bcf0d0106b6f821109c50b417b819b65f1b6`.
- Rebased retirement: `c2ebc0a`; branch `experiment/v043-retirement-current`.
- Main is unchanged; no release/version change or benchmark campaign.

Existing implementation was cherry-picked, not recreated. The sole conflict was
`docs/development.md`: retain current scope-matched verification policy and
replace retired Wasmer development instructions. Also remove obsolete advice
to retain expensive shared caches. Current disposable-workspace policy survives.

The complete original architecture cleanup remains confined to Wasmer startup,
NativeDir/bundle resolver/cache, legacy packaging/release gates, their tests,
docs/notices/provenance. Deprecated public inputs reject legacy selection;
generated-Go is the only supported production path. Historical reference scripts
refuse current execution; required MariaDB/WASIX/LLVM/converter source remains.

## Evidence validity and focused reruns

Product runtime, Python SDK, packaging, current release helpers/workflows are
byte-identical to the independently validated retirement commit. Differences
from that commit are current-main workspace policy/helper/tests and documentation.
Guest inputs/generated Go, WASIX/mmap and Snapshot implementation are unchanged
from main. Therefore the original macOS SQL/lifecycle/Snapshot/Fork, focused race,
wheel/SQLAlchemy44/GORM32 evidence remains relevant; repeating full runtime or
release acceptance has no new dependency here. It is evidence reuse, not fresh
exact-final-SHA release READY or new Ubuntu qualification.

Focused reruns after conflict resolution:

- Generated runtime inventory/pinned input identity: PASS.
- Public source inventory: PASS, 613 files, clean isolated worktree.
- Version consistency: PASS, still v0.4.2 (no release requested).
- Original four compact retirement evidence hashes: PASS.
- Changed SDK, packaging, provenance/publication/CI, benchmark input and workspace
  boundaries: **176 passed**, 25.95 s, using Python3.14 with `PYTHONPATH=python`.
- `GOTOOLCHAIN=go1.26.8 go test ./internal/artifacts ./internal/runtimekind -count=1`:
  PASS (runtimekind has no test files).
- Disposable-experiment skill validator: PASS.
- Diff whitespace and intended scope: PASS.

Reproduction: run the commands above and the following focused Python selection:

```sh
PYTHONPATH=python python3 -m pytest tests/test_generated_default.py tests/test_generated_release.py tests/test_native_target.py tests/test_python_diagnostics.py tests/test_benchmark_inputs.py tests/test_consumer_acceptance.py tests/test_ci_release_publish.py tests/test_ci_release_reuse.py tests/test_release_docs.py tests/test_v04_verification_scope.py tests/test_go_isolation.py tests/test_guest_provenance.py tests/test_experiment_workspace.py tests/test_release_tools.py tests/test_development_cleanup.py -q
python3 scripts/verify_generated_runtime.py
python3 scripts/check_public.py
python3 scripts/check_version.py
(cd benchmarks/v043-retirement-evidence && shasum -a 256 -c SHA256SUMS)
```

Recommendation: merge retirement after Human Review. Compatibility downside:
callers explicitly selecting legacy runtime/bundle inputs must remove overrides
or pin historical releases. Release-only exact-artifact acceptance remains for a
later authorized release. No guest upgrade, containment/race redesign, hashing
removal or Snapshot/Fork optimization is included.

Original details and compact acceptance: [retirement report](v043-wasmer-retirement.md)
and [evidence](v043-retirement-evidence/). Its workspace/cache retention language
is historical and superseded by current disposable-workspace policy. This task
preserves compact committed evidence and disposes its completed worktree/cache.
