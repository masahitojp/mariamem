# Native migration recipe acceptance

This stable test owner checks the [preparation recipe](../../docs/preparing-test-data.md).
It is a repository-authored two-revision application, not an imported external
legacy application. It uses the unchanged public preparation/Snapshot/Fork and
routing APIs; observation wrappers and SQL failure injection are test-only.

## Local reproduction

1. Check out a clean exact candidate and run
   `python scripts/git_identity.py inspect HEAD`. Use source_commit, not a tag object.
2. Prepare an owned disposable workspace with at least8GiB free reserve and
   a4GiB build budget. Put venvs/caches/host under temp/, receipts under evidence/.
3. Create Python3.11 and3.14 venvs. In each, install `requirements.txt` from
   this directory, plus pytest7.0.0 for3.11 or pytest9.0.2 for3.14. Save pip's
   `--report` to retain actual platform-specific package/archive identities.
4. Run `python -m pytest tests/test_preparation_migration_acceptance.py -q`.
5. Under the workspace disk/time guard run:

   ```sh
   python tests/preparation_migration_acceptance/run.py \
     --runtime-root <repo> --source-commit <full-commit> \
     --output <workspace>/minimum --pytest-version 7.0.0
   ```

   Use the3.11 interpreter for this invocation. For3.14 use a separate output
   directory, `--pytest-version 9.0.2` and
   `--host-binary <workspace>/minimum/temp/mariamem-host`. The reuse path verifies
   the exact source and Go stamp again; it does not accept an arbitrary host.
6. Preserve input hashes/results/logs before workspace cleanup. Never reuse a
   populated scenario directory: the runner rejects stale event output.

The dedicated [workflow](../../.github/workflows/preparation-migration.yml) runs
both interpreter boundaries per OS, builds one Go1.26.10 host per OS and reuses
it across Python environments. It covers macOS15 arm64 and Ubuntu24.04 x86_64.
Its main trigger retains these tests after adoption; it is not Qualification.

## Six scenarios per interpreter

Serial and two-worker xdist each run success, later-revision failure and seed
failure. Success uses four tests: two commit/next-child pairs. xdist loadgroup
scheduling keeps one pair in each worker, so each worker must reuse its own
prepared baseline. Each source ID must differ, and all four child IDs must
be distinct. Expected prepared rows, schema metadata and FK1452 recovery are
asserted in the tests. A failed chain must not attempt Snapshot or admit a
successful test; exact ProgrammingError1146, statement oracle and stage are
required in each worker. Intentional negative pytest runs have four setup errors
and exit1; arbitrary failures or skips are rejected by the outer gate.

Worker-local JSONL files avoid concurrent event-file writes. Every scenario
requires source host reaping/directory cleanup, one preparation per worker and
zero connections to a controlled original endpoint. Other workers may continue
independently; this is not a global abort promise. Partial DDL state is recorded,
not treated as transactional migration rollback. The receipt includes source,
fixture/SDK hashes, guest identity, verified host identity, actual packages and
raw evidence hashes. It does not report a performance benchmark.
