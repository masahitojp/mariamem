# Bounded Python dump reader product candidate

The Human selected the bounded Python library path after the completed comparison
at source_commit c417e21ba7dabefa5d95600ea322091732430c97,
[CI40197606173](https://github.com/masahitojp/mariamem/actions/runs/40197606173).
This candidate starts from main82877a2fc1d87d0d7cfe130c5467d3625bb6e16a and
carries the three-file host status correction in its own experimental prerequisite
commit. Host adoption, main integration, Qualification and release remain separate.
No design/evidence branch merge or old receipt relabeling is involved.

## User contract

Install the `dump` extra and call `mariamem.import_dump(db, path)` explicitly,
usually from mariamem_prepare. It creates/selects the schema declared in the dump
header; `database=` may assert that same name, not remap it. The target schema
must be empty (no tables/views or routines). Success returns the number of SQL
statements executed. It closes its own connection; ordinary preparation then
disconnects and captures the existing independent-child baseline.

Any import failure closes the supplied Database and raises DumpImportError with
route/stage/reason/path, original statement ordinal, half-open byte span and
one-based line span when available, errno/SQLSTATE and chained cause. Default
error text does not echo SQL or values. Source discard is not transactional
rollback. Catching this exception cannot make a partial baseline usable.
No automatic routing, format fallback, live/shared DB mode or native-client
installation is introduced. Normal package import does not require PyMySQL;
the `dump` extra selects the existing supported PyMySQL1.2.3 boundary.

## Initial supported family and limits

Trusted, repository-authored UTF-8 MariaDB12.3.3 dumps with the observed header,
sandbox comment and completed footer. Produce with the completed spike's profile:

```sh
mariadb-dump --no-defaults --protocol=tcp --host=127.0.0.1 --port=PORT --user=root \
  --opt --single-transaction --skip-lock-tables --skip-add-locks \
  --routines --triggers --skip-events --hex-blob \
  --default-character-set=utf8mb4 --tz-utc --order-by-primary \
  --skip-dump-date app > application.sql
```

Use utf8mb4/utf8mb4_unicode_ci InnoDB tables and the routine creation SQL_MODE
STRICT_TRANS_TABLES,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION. The dump's
NO_AUTO_VALUE_ON_ZERO mode and its recorded save/restore statements are accepted.
Schema/table/quoted identifiers are bounded ASCII names; routine DEFINER remains
root@localhost. SQL remains unchanged, including executable/version comments.
Only the observed executable-comment versions and `;`/`;;` DELIMITER framing are
accepted. The bounded statement family is emitted session SET/save/restore,
DROP/CREATE TABLE, INSERT VALUES, ALTER TABLE ENABLE/DISABLE KEYS, COMMIT and
DROP/CREATE FUNCTION/PROCEDURE. Routine bodies go to MariaDB unchanged.

Preflight the complete input before opening an import connection. Reject other
producers/versions, quote-changing SQL_MODE, client commands such as SOURCE,
unsupported executable comments/statements and malformed framing. Limits are
16MiB file,4MiB statement and10000 SQL statements. Bounds are product limits,
not measured performance guarantees. This is a family of schema/data inputs,
not a fixture-hash-only importer. Same-profile variants must be tested.

No views/triggers/events/packages, MySQL dumps, CREATE DATABASE/USE/multiple
schemas, arbitrary legacy apps, Django, arbitrary SQL files or Go dump API claim.
The header/statement checks constrain the supported format, not a SQL security
sandbox; ordinary guest SQL/routine and privilege-context limits still apply.

## Maintained evidence

Unit gates cover exact byte preservation, quote/comment/directive framing,
format and resource rejection, errno/SQLSTATE preservation, connection/DB cleanup
and success without a native executable. Keep the original migration users/
addresses corpus plus native-produced same-profile variants. Installed-package
acceptance must use the public helper through the preparation callback and retain
the two ordinary child tests and no-admission failure oracles on both supported
OSes/Python3.11/3.14. The stable migration owner/census remains unchanged.

Carry the native reference producer and explicit client route only as maintained
test controls. Verify source and host identity, preserve original canonical bytes,
and retain the same native/guest metadata, rows, routine, subsequent SELECT and
constraint comparison. New product evidence must not reuse an old experiment
PASS as an installed helper PASS. If preserving this bounded family requires a
general client implementation, stop and return the concrete unsupported case.

## Candidate verification handoff

Local Python3.14 focused validation:63 tests PASS across `test_dump_import.py`,
`test_dump_import_acceptance.py` and `test_dump_product_binding.py`; the native
acquisition guard's25 unit tests PASS. Python collection found1032 tests without
collection errors. Public-source and staged whitespace checks PASS. These results
cover source-level contracts, not an installed wheel or real guest import.

The productization workflow builds real host-containing wheels on both platforms
and installs each wheel into Python3.11/pytest7 and Python3.14/pytest9. The campaign
checks the installed helper and packaged host, fresh native reference, same-profile
data variant, independent children and failure/admission gates. Ordinary full
development checks and integration are separate jobs because this candidate
changes the Python SDK and carries the isolated host prerequisite. No new CI
result is claimed before that workflow executes.
