# W3 Django standard-runner candidate

Recommend coordinator submission of this selected candidate to the proposed
exact-source Django CI before considering main adoption. The recipe preserves
ordinary Django ownership and discards a failed migration's entire server while
returning the original test-process exit; no product adapter is required. The
strongest limitation is that all fresh functional cells are not run: static and
pure checks cannot establish current native/guest behavior, and donor local Mac
receipts cannot qualify Ubuntu or this main-based source.

## Identities and preserved scope

- Branch: `masahitojp/v06-django-recipe-main`.
- Base source_commit: `250bceb80be4cfc9f7c844d888af864fc1d38d25`.
- Candidate source_commit: `f08abc10e65fa75ba33c4b991607b1033e119555` (one direct child of base).
- Donor source_commit: `ac2cf6b5bc6b6e8a8066e5986f6000648523cb50`.
- `python3 scripts/git_identity.py inspect` confirmed all three are commit objects;
  the candidate additionally passed existing `linux_acquisition.source_identity`
  exact clean HEAD validation. No tag object was used as source identity.
- Original lifecycle proof source: `92dc7faddd16ad330a080b52a0a01614600eed66`.
- Original mixed/recipe proof source: `903e68cc021d894e56afdf6fba0bb70030de972e`.
  Both reports were read with `git show` from the donor, without modifying their
  receipts. They observed macOS arm64 clients and Docker Desktop emulated
  Linux-amd64 MariaDB, not an Ubuntu guest host or native Mac server acquisition.
- No build, real guest execution, Docker/native execution, CI submission/poll,
  push, PR, adoption, release or subworker was started; no heavy lease was requested.

The 13 existing authored app files and two original migrations are byte-identical
to the manifest. All pinned requirements are byte-identical to the donor.
The parent CLI/settings and test workloads are selected directly; experimental
Fork campaigns/preparation are excluded. Original donor metadata is retained in
the manifest alongside an explicit candidate-selection record. The only donor
oracle strengthening is exact expected failure identity and the original
ProgrammingError chain; no failure is suppressed or converted into a raw pass.

## Changed paths

26 added files, only inside assigned ownership:

- `.github/workflows/django-lifecycle.yml` (new workflow proposal).
- `docs/django-testing.md`.
- `docs/examples/django/{README.md,example_settings.py,run_tests.py}`.
- `tests/django_lifecycle/{README.md,admission_cases.py,cases.py,ci.py,input-manifest.json,lifecycle_settings.py,mixed_cases.py,observation.py,order_probe.py,probe_recipe.py,requirements.txt,run.py,run_mixed.py,test_mixed_cases.py,test_pytest_cases.py}`.
- `tests/django_lifecycle/failure_migrations/{__init__.py,0001_initial.py,0002_status.py,0003_partial_failure.py}`.
- `tests/django_lifecycle/fixtures/orders_seed.json`.
- `tests/test_django_recipe_unit.py`.

`git diff --name-only BASE HEAD` was checked against this exact ownership;
`git rev-parse HEAD^` equals the requested base. Product APIs/SDK, internal runtime,
guest/generated files, dependencies, version/release ledgers, protection,
historical receipts, common guides, root README and project-status have no delta.

Proposed navigation only, for coordinator selection: add a link named
“Django standard-runner recipe” to `docs/django-testing.md` from the Python guide's
testing section and the root README's test-framework examples. Neither shared
file was edited.

## Confirmed checks

Local host is macOS27.2 arm64; Python3.11.17/OpenSSL3.6.5 and
Python3.14.9/OpenSSL4.0.3. These are pure checks on a newer local OS, not the
supported macOS15 functional matrix.

| Status | Command/input | Result |
| --- | --- | --- |
| PASS | Git identity inspect for base, donor and candidate; candidate source_identity | exact commit and clean source |
| PASS | task Python3.11 `-m pytest tests/test_django_recipe_unit.py -q -p no:cacheprovider` | 24 passed |
| PASS | task Python3.14 same focused suite | 24 passed |
| PASS / SKIP | task Python3.14 focused suite plus `tests/django_lifecycle/test_pytest_cases.py tests/django_lifecycle/test_mixed_cases.py` | 24 passed, 2 explicit module skips without W3_RUN |
| PASS | `ast.parse` for all selected Python inputs | 19 sources parse |
| PASS | PyYAML BaseLoader workflow parse and matrix checks | two native minor cells, four guest OS/minor cells |
| PASS | `PYTHONPATH=python python3.14 docs/examples/django/run_tests.py --help`; `python3.14 tests/django_lifecycle/ci.py --help` | runnable argument interfaces, no owner started |
| PASS | `python3 scripts/check_public.py` | 5454 public files |
| PASS | source-bound manifest hashes + unchanged donor CLI/settings/requirements comparison | original inputs preserved |
| PASS | `git diff --check BASE HEAD`, owned-boundary audit, clean status | no whitespace or prohibited delta |
| FAIL (tool availability, resolved) | initial default `python3 -m pytest ...` | system Python3.9.6 has no pytest; replaced with task-owned pinned pytest environments |
| Historical FAIL retained, not rerun | Python3.14/OpenSSL4 Oracle Connector/Python26.7.0 import | existing PROTOCOL_TLSv1 AttributeError remains; this mysqlclient recipe does not resolve or qualify it |
| NOT RUN | actionlint / GitHub workflow execution | YAML parse is not an Actions execution result |

Pure checks cover child exit0/1/5 preservation, inherited stdout/stderr,
endpoint/settings wiring, owner closure on timeout/spawn failure/interruption,
and twelve native-receipt mutations (source/input/minor/host/image/program,
missing/failed suite/failure, cleanup and top result). They use no database,
Django or Go execution. A task-owned workspace was prepared with 8GiB minimum
free and 1GiB budget; only small pytest/PyYAML dependencies were downloaded.

Original donor expected raw test failures and the acquisition STOP remain under
their historical identities. The lifecycle report's 16 deliberate failures are
not 16 raw passes, and its original acquisition version-prefix STOP is not
rewritten. Original mixed migration setup failures retain their nonzero exits,
errno1146, partial-DDL observation and zero-admission policy. No new functional
PASS is inferred from those records.

## Concrete remaining CI inputs and owner

Coordinator owns submission/review of `.github/workflows/django-lifecycle.yml` on
the exact reviewed candidate or a separately named synthesis source. The workflow
uses pinned existing Actions, Go1.26.10, Python3.11/3.14 and unchanged framework
requirements, normal native client headers, and the existing native MariaDB
image digest/program/startup guard (`tests/dump_import_acceptance/linux_acquisition.py`
and its pin). Hosted runners' exact Python/OpenSSL/client environments remain
recorded in each new report/dependency artifact. Linux acquisition has its own
full guard results; no Docker-emulation receipt is substituted.

Required fresh cells, all NOT RUN:

1. Ubuntu24.04 x86_64 native reference, Python3.11.
2. Ubuntu24.04 x86_64 native reference, Python3.14.
3. Ubuntu24.04 x86_64 guest + public recipe, Python3.11.
4. Ubuntu24.04 x86_64 guest + public recipe, Python3.14.
5. macOS15 arm64 guest + public recipe, Python3.11.
6. macOS15 arm64 guest + public recipe, Python3.14.

Per route/minor, 10 lifecycle and eight mixed suites plus two failed-migration
suites run. Guest cells also run four normal/broken public-entry checks. Native
references are matched by exact source, tracked input hashes, packages, Python
minor and complete case inventory. Guest host binary stamping must independently
match exact clean candidate source and Go1.26.10; a linked-worktree binary with
parent-repository stamping is rejected, never relabelled. Raw exception messages,
tracebacks and generated schema names remain in artifacts; comparisons omit only
host-specific paths/schema identifiers while retaining semantic identity.
Failed migrations get fresh owners, no Snapshot/reuse, and closure/reaping/temp
removal checks. The native parent drops only its unique schemas after inspection.

The workflow is a reviewable proposal, not product adoption or release approval.
No browser installation, duplicate broad xdist census, multi-alias/parallel/async,
persistence, session continuity, automatic routing or worker/job fencing is added.
Arbitrary projects and independent multi-module application evidence remain
unverified. Any future local native/guest run still needs a concrete exclusive
lease, exact source identity and bounded prepared workspace.

## Cleanup and retained state

The task-owned `django-recipe-checks` helper workspace was finalized after checks;
dry-run classified its 379527168 bytes as completed recreatable DELETE with no
cleanup debt. Cleanup apply and final audit are recorded below. The Orca worktree
and unpushed candidate commit remain intentionally for coordinator review; the
worker does not remove that worktree. This compact report and public-source hash
receipt remain under build as durable evidence, not caches.

Final cleanup apply reported 379527168 bytes before and 33239040 bytes after, no cleanup debt. The remaining 32MiB were inspected exported dependency/venv reproductions, then deleted with their package checksums; only the small helper receipt/cleanup note remain. The helper-created disposable check worktree was removed, while the assigned Orca worktree and candidate branch remain. Final build usage is below 2MiB, no task path exceeds 1GiB, Git status is clean, and final exact-source public scan again passed5454 files.
