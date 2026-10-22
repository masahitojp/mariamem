# P5 real consumers and regressions — candidate, acceptance still open

Continue the approved P5 row from source_commit
`371641c8df48f7593b3e008d711b9ad546a03b37`, after
[P4 finite acceptance](v06x-prepared-p4-failures.md).
No production runtime, guest/experimental patch, canonical patch, converter,
Generated Go, public API or package version is changed.

The next decision is **not yet whether to accept two new consumer constraints**.
First obtain both-OS actual guest observations and the canonical Python3.14
native control. Recommend completing that bounded comparison and the existing
regression anchors. The strongest objection is that native parity alone cannot
make a failing or shortened result useful to an application: prospective
functional failures remain FAIL and need a separate Human disposition. Neither
CI success nor the accepted syntax-error presentation exception grants that
new disposition. No pure-mode forcing, server emulation or driver patch is used.

## Current CI status

The table below preserves the initial candidate state. The subsequent
[CI diagnosis and corrected comparison boundary](v06x-prepared-p5-ci-diagnosis.md)
records CI39760963205: Ubuntu actual guest/installed regressions/ORM anchors PASS;
macOS observations captured but missing C-native reference blocked matching and
later regressions. Both-OS units/source build PASS. Mac Python3.14 native
reference now exists; the revised CI remains pending. These diagnostic outcomes
do not resolve the functional failures or complete P5.

## Initial finite matrix and evidence

| Item | Local fixed native12.3.3 control | Actual guest / canonical environment |
| --- | --- | --- |
| Go driver1.9.3, explicit Prepare with interpolation enabled | PASS; engine prepare counter advances | Pending both-OS CI |
| Go parameterized Query with interpolation disabled | PASS; implicit prepare counter advances | Pending both-OS CI |
| Go NULL/int64/Unicode/binary, commit/rollback, duplicate error/recovery, prepared two-result CALL, statement/pool cleanup | PASS in both interpolation modes; final counters0 | Pending both-OS CI |
| Connector/Python26.7.0 pure/default/explicit C, repeated parameters, typed VARBINARY commit/rollback/read, duplicate error, following SQL, ordinary text multi | PASS in all three local modes | Pending both-OS Python3.14 CI |
| Connector prepared syntax error | Raw1064/42000; pure1064; C/default2006/HY000; following SQL usable | Pending fresh guest confirmation of the existing approved exception |
| Untyped prepared SELECT of NUL-containing bytes | pure returns all3 bytes; default/C returns only A as a character value: functional FAIL | Pending guest observation; new disposition not accepted |
| Connector prepared CALL with two results via nextset | first result7 received; pure fails at nextset, C/default2014; subsequent query also fails: functional FAIL | Pending guest observation; new disposition not accepted |
| Existing text/auth/options/routine/SQL/transaction/Snapshot/Fork/isolation/Start/Close controls | Existing assets reused | Pending actual installed Go/Python CI |
| Existing SQLAlchemy2.0.54/GORM1.31.1 anchors | Applications unchanged | Pending actual installed/source-bound CI, start/fork modes |
| Scoped Python/C/tooling tests |149 PASS on local Python3.11, including normal/sanitizer C sweep and new15 controls | Python3.14 both-OS units pending |
| Go protocol/owner race packages |4 PASS locally | Both-OS units pending |

Local reference means **Linux/arm64 MariaDB12.3.3 in the pinned container,
controlled by Python3.11/Go1.26.8 on macOS arm64**, not a macOS-native server and
not canonical Python3.14 acceptance. The receipt pins image digest, actual image
ID, engine version, source/binary hashes and environment. Local Python3.14 has
OpenSSL4.0.3 without PROTOCOL_TLSv1; Connector import is not worked around or
counted as PASS. CI explicitly uses Python3.14 and captures its own Linux x86_64
native reference before either guest job. Missing pure/default blocks; only the
additional explicit C mode may SKIP with a reason. A default that selects C must
have a matching native C control; unavailable evidence is not inferred.

## Two newly observed native constraints

### NUL in an untyped character projection

The exact same prepared query is:

```sql
SELECT ?, HEX(?), OCTET_LENGTH(?), CAST(? AS BINARY)
```

All four parameters contain bytes410042. Native pure returns A-NUL-B,
410042,3 and binary410042. Native default/C returns A,410042,3 and binary410042.
The engine therefore received and retained all3 bytes; the shortened character
projection is observed on receipt through this C-extension combination.
This does not identify the precise C implementation line, establish the same
behavior against MySQL, or imply that typed binary columns are truncated.
The typed VARBINARY insert/read assertion succeeds with all3 bytes in every mode.
The practical harm is a shortened Python value/assertion when an application
uses that untyped character projection. The incorrect value is retained verbatim,
not normalized into a native-parity success.

### Prepared CALL result traversal

The minimal procedure emits SELECT x and SELECT x+1. With x7 the first set is7;
nextset fails before the second can be used. Native pure raises ProgrammingError
about affected_rows; native default/C raises2014/HY000. The separate minimal
capture preserves the primary error, subsequent-query error and cleanup errors.
On this connection a following SELECT1 also fails. This is a concrete native
combination result, not a prediction that mariamem itself corrupts data.

Installed26.7.0 sources show prepared cursors inherit ordinary nextset: pure
uses MySQLCursor.nextset and C uses CMySQLCursor.nextset. The latter calls the
connection's ordinary next_result, rather than a dedicated prepared successor
in that cursor method. Source method hashes are stored with the minimal capture.
This is a plausible explanation, not a proven root cause or a support statement
for every server. Official [prepared cursor documentation](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlcursorprepared.html)
and [nextset documentation](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlcursor-nextset.html)
provide the API context; neither was used to override the observed failures.

Go prepared CALL succeeds against the same native server, and P3's raw protocol
matrix already passed both actual guest platforms. That establishes separate
working paths; it does not repair the Python consumer's failure.

## Oracle and CI boundaries

The prospective full consumer program remains exit1 / result FAIL at the native
CALL failures. The original strict reference gate still rejects a failed native
fixture, and a unit test pins that rejection. The initial failure captures remain
under their original context. No existing P1–P4 or release oracle is weakened.

A **separate observation matcher** compares complete case values, raw syntax
packets, flags/counters, client error and stage against the native fixture.
Its receipt has matching PASS/FAIL and always retains functional_acceptance FAIL
and human_disposition PENDING for these known failures. Expected process exit1
is required; missing modes, new errors, wrong values, pool leaks or incomplete
CRUD/text controls fail matching. The default connect call is unmodified; its
selected implementation chooses the appropriate native observation. Only run
metadata/lifecycle fields and the mode label are excluded, never values/errors.
Do not report a successful capture/match as full P5 acceptance.

CI adds a fresh native Python3.14 control and both-OS development runtime gates.
The full previous P1–P4 runtime gates remain. P5 additionally runs:

1. Formal development generation and the existing exact installed binding gate.
2. New Go/Python consumer observation and separate native matching receipts;
   minimal edge capture, preserving functional failures.
3. A private wheel from the bound development host and unchanged SDK. Host hash,
   guest identity, clean source commit, complete SDK inventory and fresh output
   are checked. Manifest explicitly says public_release_ready false and records
   the development contract. Canonical release inventory is not rewritten.
4. Installed Python lifecycle/plugin/routine controls, including required default
   Connector text behavior; Go integration/routine/auth controls using the actual
   installed development-source module.
5. Existing SQLAlchemy and GORM application runners, unchanged. Their wheel/source
   paths select the new bound host, not the old canonical generated runtime.

A private wheel here is a test fixture with the existing package version; it is
not published or granted release eligibility. Source/build/install provenance
remains UNQUALIFIED. Go consumer race instrumentation cannot establish guest
mmap/assembly or general shared-memory correctness. P6 retains independent
canonical rebuild/regeneration/J1/licenses/provenance and release guards.

## Reproduction and next report

Use the pinned image in the [receipt](v06x-prepared-p5-evidence/receipt.json),
Python with Connector26.7.0/PyMySQL1.2.3 and Go1.26.8. Credentials stay in the
consumer environment, not command arguments or logs. Example native controls:

```sh
python scripts/git_identity.py inspect HEAD
go build -race -trimpath -buildvcs=false -o /tmp/p5-consumer ./tests/prepared_consumer
python tests/v06_prepared_consumers.py --native-port 3307 --consumer /tmp/p5-consumer --output /tmp/p5-native.json
# The prospective consumer oracle currently exits1; retain that FAIL.
python tests/v06_prepared_consumer_edges.py --native-port 3307 --output /tmp/p5-edges.json
python -m pytest -q tests/test_prepared_consumers_probe.py
```

The next report must state separately: normal consumer/regression results,
exact native matching or new guest differences, functional failures, platform
SKIPs and required Human disposition. A newly different guest behavior remains
a blocker to diagnose, not a new implicit native exception. Even if all CI jobs
succeed, P5 stays open until its functional constraints are explicitly resolved
or accepted. No main integration, target version, Qualification or release.
