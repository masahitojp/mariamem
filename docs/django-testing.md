# Django standard-runner recipe

Use an explicit parent process and ordinary Django MySQL settings. The parent
starts one disposable mariamem server, supplies its endpoint before Django loads
settings, runs `manage.py test` or pytest-django, and closes the server afterward.
Django retains ownership of test database creation, migrations, transactions,
flush and serialization. See the [runnable example](examples/django/README.md).
This is a source recipe for a single database alias, with no new adapter API.

The parent owns one server **per runner invocation**. It returns the test
process's exit code after closing the owner and inherits its original stdout and
stderr. In particular, failed migration setup can leave partially committed DDL
before Django reaches normal test teardown. Discard that whole owner; do not
capture it as a Snapshot or reuse it for another invocation. The recipe's owner
context also exits if spawning the test process fails or it times out.

Django owns per-test isolation inside that invocation:

- `TestCase` uses class/test atomic rollback and `setUpTestData`.
- `TransactionTestCase` and pytest-django transactional tests can commit. Default
  flush empties application tables; it does not replay migration SEED data.
- Use ordinary Django `fixtures` or an explicit pytest fixture when each
  transactional test needs seed. `serialized_rollback=True` (or the equivalent
  pytest-django marker) is a separate framework policy and is tested separately.

The selected tests retain the existing 13 authored orders app/migration files,
Django5.2.8, mysqlclient2.2.7, pytest9.0.2 and pytest-django4.12.0.
They check SQL database identity, migration records, an untouched original-schema
sentinel, HTTP operations, duplicate errno1062 recovery, real commits visible
through an independent connection, default flush, serialized seed restoration,
mixed class/function orders and exact expected failure after commit. A third
migration intentionally creates partial DDL then fails with errno1146. Both
runners must retain the Django/MySQLdb ProgrammingError chain, admit no test
bodies, and discard the failed guest owner. These expected failures are kept as
raw failures; a parent assessment can PASS only when the specified failure and
cleanup are observed.

## Evidence and maintained CI

The selected donor is source_commit
`ac2cf6b5bc6b6e8a8066e5986f6000648523cb50`. Its local lifecycle receipt belongs to
`92dc7faddd16ad330a080b52a0a01614600eed66`; its mixed/entry receipt belongs to
`903e68cc021d894e56afdf6fba0bb70030de972e`. Those observations used macOS arm64
clients and a Linux amd64 native server under Docker Desktop emulation. They
are historical evidence, not Ubuntu acceptance or fresh results for this
candidate. Read the original reports with `git show ac2cf6b5:docs/reviews/v06x-django-lifecycle-results.md`
and `git show ac2cf6b5:docs/reviews/v06x-django-mixed-results.md`.

The [workflow](../.github/workflows/django-lifecycle.yml) passed fresh native
MariaDB12.3.3 references on Ubuntu24.04 x86_64 for Python3.11 and3.14, followed by
guest/entry comparisons on Ubuntu24.04 x86_64 and macOS15 arm64 for both minors.
All six cells passed in [CI40492425975](https://github.com/masahitojp/mariamem/actions/runs/40492425975).
The approved candidate is `d389306f9ae0514824f79fccbe2800776786a7ac`; the actual
PR CI source_commit is `3ed2c8e0790499c215869e33154272b062c35a88`, with an identical
tree. See the [adoption record](reviews/v06x-dogfood-main-adoption.md) for exact
identities and limitations. This is bounded recipe evidence, not a claim that
arbitrary Django projects are supported.

The existing native acquisition guard binds the image,
server/client executable hashes, startup identity and current source. Guest
jobs reject mismatched sources, tracked inputs, package pins, Python minors,
missing suites and missing failed-migration or cleanup results. Host binaries
must pass `scripts/git_identity.py`'s exact clean source/toolchain check. No old
receipt is renamed as candidate evidence. CI retains raw outputs and source-bound
JSON in artifacts; it installs no browser and repeats no broad xdist census.
The six-cell results include partial-migration failure, original nonzero exits,
no test admission after failed setup and owner disposal. Pure ownership and
receipt mutation checks supplement these real database comparisons. This
workflow reports CI results but is not currently a branch-protection required
context; required-check policy is a separate decision.

The local Homebrew Python3.14/OpenSSL4 Oracle Connector/Python26.7.0 import FAIL
remains as documented in [local verification](development.md#local-verification).
This mysqlclient recipe neither exercises nor resolves that connector gap;
OpenSSL3 CI would not qualify OpenSSL4.

Multiple aliases/routers, Django parallel/xdist workers, async, retained external
connections, independent multi-module applications and arbitrary projects remain
unverified. No setup-cost, performance, persistence, session continuity or
automatic routing claim is made. Candidate adoption and release remain separate
Human decisions.
