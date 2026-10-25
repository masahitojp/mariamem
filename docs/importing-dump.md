# Prepare tests from a MariaDB dump

This helper is adopted on main and available in unreleased source builds.
Install a wheel built from current source with the `pytest`, `dump` and
`routing-pymysql` extras. It is not available in published v0.5.3.

`import_dump` loads a supported SQL dump into a fresh mariamem database. The pytest
plugin then prepares a baseline once per worker. Each marked test gets an
independent child, so commits in one test do not change the next test's data.
Importing needs no native MariaDB executable; generating the dump needs the
pinned MariaDB 12.3.3 `mariadb-dump` producer described below.

```python
# conftest.py
from pathlib import Path
import pytest
from mariamem import import_dump

@pytest.fixture(scope="session")
def mariamem_prepare():
    def prepare(db):
        import_dump(db, Path(__file__).parent / "data/application.sql")
    return prepare
```

Declare the original endpoint used by your application before importing it:

```toml
# pyproject.toml
[tool.pytest.ini_options]
mariamem_route_profiles = ["app = 127.0.0.1:3306/app"]
mariamem_route_drivers = ["pymysql"]
```

Mark the application's tests with `@pytest.mark.shadow_maria` or set
`pytestmark = pytest.mark.shadow_maria` in their module. See the
[preparation guide](preparing-test-data.md) for application entry points,
SQLAlchemy engine registration, connection teardown and worker-local baselines.
Preparation uses an explicit temporary connection; automatic preparation routing
is not involved.

## Produce a supported dump

The initial profile is UTF-8 MariaDB 12.3.3, InnoDB tables using
`utf8mb4_unicode_ci`, and procedures/functions with `root@localhost` DEFINER.
Use the strict routine creation mode
`STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION`.
Replace `PORT` and `app` with your source's port and schema:

```sh
mariadb-dump --no-defaults --protocol=tcp --host=127.0.0.1 --port=PORT --user=root \
  --opt --single-transaction --skip-lock-tables --skip-add-locks \
  --routines --triggers --skip-events --hex-blob \
  --default-character-set=utf8mb4 --tz-utc --order-by-primary \
  --skip-dump-date app > application.sql
```

This profile excludes views, triggers and events; the source must contain none.
The helper rejects their emitted statements. It preserves routine definitions,
row values, engine and collation. Schema and quoted object identifiers use bounded
ASCII letters, digits, underscores and dollar signs; the schema begins with a
letter or underscore. Accepted framing uses `;` and `;;` delimiters and the
producer's observed executable comments. See the exact
[candidate format contract](reviews/v06x-dump-reader-product-contract.md).

Use trusted, repository-authored test inputs. This reader is not a SQL security
sandbox. MySQL dumps, arbitrary legacy application dumps, Django, multiple schemas,
`CREATE DATABASE`/`USE`, external `SOURCE` commands and arbitrary SQL scripts are
outside this profile. Limits are 16 MiB per file, 4 MiB per statement and 10,000
statements; these are bounds, not performance guarantees.

## Return value and failures

`import_dump(db, path, database=None)` returns the number of SQL statements
executed. It takes the schema name from the dump header, creating it if absent;
an existing target schema must be empty with the required charset/collation.
Optional `database="app"` asserts the header name and never renames a schema.
The helper closes its connection after success and leaves the database open.

An import failure raises `DumpImportError` and closes the supplied database.
Do not catch the error to continue preparation: partial DDL is discarded with
the source database, and no baseline should be created. Start a fresh database
after correcting the input. Errors expose `reason`, `stage`, `path`, `route`,
`location`, `errno`, `sqlstate` and the original chained exception. Locations,
when available, contain the statement ordinal, one-based line span and zero-based
half-open byte span in the original file. `closed` reports whether discard
succeeded; `cleanup_error` retains a cleanup failure. The error's own text omits
SQL values, but the chained driver exception can contain database details.
