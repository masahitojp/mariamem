# Independent Django dogfood input — source investigation and proposed experiment

2026-10-28. Base source_commit `cc00ccd98e29a1f5d5088a082be90a3cdaa4f469`.
This is the next input/acceptance proposal after PR3/PR4 adoption, not a new
runtime result, adapter design or execution approval.

Decision next: use Django Oscar4.2.1's sandbox as the first independent Django
project for a bounded, native-first experiment. Recommend it because it retains
ordinary connection configuration, real multi-app migrations and authored
catalogue/partner data while adding a workload independent of our orders app.
The strongest objection is attribution: upstream tests use PostgreSQL, its old
fixture may not load on today's schema, and the selected Django5.2/Python3.14
pair is excluded from upstream CI. Native MariaDB preflight must settle those
questions before guest differences can be judged. A failure there stops the
experiment; it is not automatically a mariamem defect.

## What is already complete and what this adds

[Existing adoption](v06x-dogfood-main-adoption.md) covers our authored orders app,
ordinary manage.py/pytest-django ownership, partial migration failures, Live
browser/HTTP scenarios and static serial/parallel guides. Do not repeat that
whole campaign or reopen its accepted limitations. This input adds a separately
maintained multi-app project and its business models. It is not a generic Django
adapter, proof of arbitrary projects or a replacement for existing regression
anchors. The [north star](../project-status.md#v060--dogfood-and-fixture-ergonomics)
still distinguishes first-test setup, adding a second test and repeated execution.

This task only read upstream source. No dependencies were installed, source
build hooks imported, migration executed, DB/server started or CI submitted.

## Compared inputs

All inspected upstream references were fixed on 2026-10-28. These are source
observations, not compatibility results.

| Input | Fixed source_commit | Findings / disposition |
| --- | --- | --- |
| Oscar development head | `88b8c9d454533b9cfeba655fa0e9c092bf043df0` | Multi-app sandbox, conventional DB environment variables and BSD license. Prefer its available stable4.2.1 below over this moving development line. |
| Wagtail Bakery Demo | `c9b38d7a7170dba8bb84254beb7e5dc5a955e024` | Multiple apps and full demo seed/media; requirements demand Django6.0 and Wagtail8.0. This adds framework/Python-version and media/search axes to the first experiment. Keep as a later candidate. |
| django-wiki | `a5b10b19beac77270893fa878f0085567395f7a7` | Multi-plugin testproject, Django4.2–6.0 dependency range, default SQLite settings and SCSS packaging hook; GPLv3 source. Not rejected as incompatible, but not the first input. No source is vendored here. |

Primary inspected sources:
[Bakery requirements](https://github.com/wagtail/bakerydemo/blob/c9b38d7a7170dba8bb84254beb7e5dc5a955e024/requirements/base.txt),
[Bakery seed command](https://github.com/wagtail/bakerydemo/blob/c9b38d7a7170dba8bb84254beb7e5dc5a955e024/bakerydemo/base/management/commands/load_initial_data.py),
[wiki dependency/build metadata](https://github.com/django-wiki/django-wiki/blob/a5b10b19beac77270893fa878f0085567395f7a7/pyproject.toml).

## Selected fixed input and source integrity

Select [Oscar4.2.1](https://github.com/django-oscar/django-oscar/releases/tag/4.2.1),
source_commit `d0a70850abf8e4229d4971aa7e8f4643326ec9f3`, tree
`8e43e354546512e94ed86b86c2351d8d3cc25a84`. The tag is lightweight: the ref
object type is commit, and `tag_object_sha` is null, not a copied source SHA.
Remote ref and commit APIs establish this selection; they do not replace local
`scripts/git_identity.py` checks before any future build.

The [input manifest](v06x-independent-django-input/input-manifest.json) records
Git blob IDs, SHA256 and byte sizes for inspected inputs, and all134 numbered
core Oscar migration blobs. Those migrations must remain unchanged. The count
is a source inventory, not a claim that all134 are applied in a fresh DB;
Django's migration graph/squash replacement determines the execution plan.
Dependency-package migrations must also be inventoried after locking.
Read-only source snapshots under ignored build were checked against their Git
blob identities; no Oscar model, migration or source file was copied into product
source. Retain upstream LICENSE when acquiring/distributing source later.

Use the unchanged authored `sandbox/fixtures/multi-stockrecord-product.json`:
8 records across6 model types, including two products and two stockrecords.
Its stock inputs are a1/GBP20/stock5 and a2/GBP10/stock15. These are parsed input
facts, not successful import observations. This is a bounded catalogue/partner
seed, not `make build_sandbox` or full-site population. The fixture's age makes
native import a gate; do not silently rewrite fields to force it through.

## Settings and dependency boundary

[Sandbox settings](https://github.com/django-oscar/django-oscar/blob/d0a70850abf8e4229d4971aa7e8f4643326ec9f3/sandbox/settings.py)
read DATABASE_ENGINE/NAME/USER/PASSWORD/HOST/PORT and retain ATOMIC_REQUESTS=True.
Its registered applications include catalogue, partner, basket and the rest of
the normal sandbox. Keep that app list and application logic intact. A test-only
settings overlay translates the public recipe's E2E_DB_* endpoint to these DB
fields and assigns a unique test-schema name; reject any SQLite fallback or
unexpected DB destination before migration. Preserve SQL-affecting settings and
record engine, charset/collation, SQL_MODE and timezone observations.

Non-DB writable paths also require explicit isolation: Whoosh index PATH,
MEDIA_ROOT and STATIC_ROOT live inside the owned run directory. Preserve the
Whoosh backend, realtime signal processor, transaction behavior and locmem cache
backend. Do not disable search or thumbnail apps to make SQL pass. Record a
settings delta allowlist, prevent local .env/settings_local contamination, and
keep file/index state separate between runner invocations. DB rollback does not
rollback a search index; compare DB test isolation separately and do not promise
complete external-state reset. Browser/image/search correctness is not asserted
by this first ordinary-runner experiment.

Core comparison targets retain existing pins: Django5.2.8, mysqlclient2.2.7,
pytest9.0.2 and pytest-django4.12.0 on Python3.11/3.14. Oscar's declared bounds
permit these targets, but that is not successful resolution or compatibility.
Its [upstream test matrix](https://github.com/django-oscar/django-oscar/blob/d0a70850abf8e4229d4971aa7e8f4643326ec9f3/.github/workflows/test.yml)
uses PostgreSQL and explicitly excludes Django5.2/Python3.14. Preserve that fact;
classifiers are not test evidence. Native3.14 remains required for our proposed
matrix, not silently omitted or counted as supported upstream.

**Missing before execution:** a full transitive version/hash lock for each
Python/OS, including the sandbox's Whoosh, django-environ, whitenoise and both
thumbnail packages. Inspect packaging/build hooks before acquiring the source
package. Record the Python/OpenSSL/client ABI and all distribution hashes. No
whole `[test]` extra, Node asset build, images archive, external search service
or browser installation is required by the proposed DB-level cases. This bounds
the new scenario; it does not claim the full upstream suite or sandbox is tested.
If dependencies cannot resolve without changing core pins, stop for an input
decision instead of quietly upgrading Django or changing the product.

## Proposed experiment order and acceptance

Use `experiment/independent-django` and a disposable bounded workspace. Keep
product API/runtime, guest/generated inputs, dependency pins, main and release
ledgers unchanged. The experiment's own dependencies are isolated inputs.

1. **Input preflight:** acquire the exact clean source, validate the release ref
   versus source commit, resolve/hash complete dependency locks, inventory actual
   migration inputs, and fix settings/test/seed hashes before execution. Runtime
   evidence is NOT_RUN until these gates close.
2. **Native reference first:** Ubuntu24.04 x86_64, exact MariaDB12.3.3 image and
   existing per-program acquisition guard, Python3.11 then3.14. Run the unchanged
   sandbox migration graph and selected fixture. Mac Docker emulation is not
   substituted for a native Ubuntu observation. Stop on dependency, migration or
   fixture failure; retain original error and no guest PASS.
3. **Author and freeze the small business-test overlay against native:** one
   ordinary TestCase mutates catalogue/stock and uses the application's basket
   operation; a second confirms original seeded product/stock values and no
   prior basket mutation. Run each alone, normal/reverse order and together.
   Run a separate deliberate post-write test failure with an exact marker,
   preserved nonzero runner exit, subsequent clean test and owner cleanup.
   Fix explicit expected results before guest comparisons, not after seeing them.
4. **Guest comparison:** same source/locks/seed/test bytes, public parent-owner
   recipe with manage.py and pytest-django, macOS arm64 and Ubuntu x86_64 on
   Python3.11/3.14. Compare schema/migration inventory, exact selected rows,
   decimal and FK/basket behavior, test order/outcomes, original error identity
   and completed child/server/temp cleanup against matched-minor native receipts.
5. **Report:** PASS/FAIL/SKIP per route/OS/minor/runner; failed inputs remain
   failed. Record the settings/import-path edits and commands needed to establish
   the first test and add the second. Separate dependency acquisition,
   migration/seed, runner/test and cleanup timing; do not call a warm local
   run cold setup or infer broad developer-effort savings.

Normal Django owns per-test isolation. No Snapshot, Live takeover, new backend,
automatic routing, multi-alias, async or Django parallel-runner behavior is added.
Existing authored partial-DDL failure/native and Live campaigns remain regression
anchors, not newly rerun evidence for this external app. If a native-PASS/guest-FAIL
difference appears, first retain and minimize it; a runtime fix, guest patch or
adapter is a separate design decision. Do not weaken constraints, normalize away
business differences, turn failed tests into skips or continue test admission
after failed preparation.

## Detection net, budget and stopping point

Existing Django recipe unit checks cover owner closure and original exits;
existing authored native/guest CI covers the earlier one-app lifecycle. Neither
checks this external project's migrations, fixture or dependencies until this
new experiment exists. Source identity, lock/input hashes, explicit nonzero
oracles, destination assertions and both-runner native comparison are the
proposed mechanical gates. First-test learning burden and usefulness of error
advice remain observations, not something an ordinary green CI proves.

Proposed execution budget: one heavy campaign at a time,8GiB owned storage,
16GiB minimum free; input/native/guest phases individually time-bounded, with
20-minute native and30-minute guest cell limits. These are proposed ceilings,
not measured setup costs or promises of total duration. Preserve compact logs,
source/lock/settings hashes and outcomes; remove recreated source, wheels,
venvs, containers and caches after settlement. Hosted-runner admission and total
matrix cost are part of the execution review, not an automatic CI fan-out here.

This source-selection task ends with a reviewable input and finite acceptance
proposal. Source inventory and JSON parsing passed; dependency resolution,
native/server acquisition for this workload, all migrations/tests and all guest
cells remain NOT_RUN. No candidate/spike/main/release PASS is claimed. The next
Human decision is whether to execute this bounded native-first experiment under
these gates, not whether to productize an adapter or promise Oscar support.
