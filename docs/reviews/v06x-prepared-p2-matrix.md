# P2 additional native matrix — actual guest gate pending

This continues the approved P2 scope after the bounded TIME repair passed on both
OSes atf498396. No new implementation approval or adoption decision is requested.
The [receipt](v06x-prepared-p2-matrix-evidence/receipt.json) binds test inputs,
native reference, comparison boundary and pending guest work. Original P1/P2/TIME
oracles remain unchanged. This is not a runtime PASS, completed P2, or Qualification.

## Additional20 scenarios

| Group | Controls |
| --- | --- |
|13 parameter types | DECIMAL, VARCHAR, BIT, ENUM, SET, three blob variants, GEOMETRY, INT24, YEAR, NEWDATE, TIMESTAMP; repeat with descriptor reuse |
| Type changes | Same statement transitions signed integer→uint64→Unicode→empty→NULL→decimal→integer |
| DML/warnings/recovery | INSERT/auto ID, truncation warning, UPDATE changed/unchanged count, duplicate1062/23000, following successful execution, table contents |
| Transaction | Prepared INSERT rollback/commit, status, final table contents |
| SQL modes | Zero/leap/invalid DATE insertion in permissive and strict modes, warnings/errors and stored values |
|3 schema changes | Change result type, increase SELECT * column count, drop referenced column; execute the original statement handle after each ALTER |

All20 pass against the pinned native12.3.3 Linux arm64 image used from macOS.
That is a reference engine, not the actual Wasm→Go guest. The schema-add control
returns three current descriptors instead of two; schema-drop returns1054 and
a healthy following query. The unchanged guest must demonstrate the same behavior.

The wire accepts typecodes which the pinned embedded mysql_stmt_bind_param switch
does not accept directly. The source observation is in the receipt. This matrix
establishes the actual guest outcome before any mapping/fallback is proposed;
matching byte shape alone would not justify changing a parameter type. If actual
results require a new MariaDB-internal change, the existing stop condition applies.

## Oracle and failure evidence

Rows compare complete metadata/binary/terminal bytes. DML compares affected rows,
insert ID, status and warning count without floating-point conversion. Errors
compare errno/SQLSTATE and message bytes. The new matrix records full OK packets
and informational text separately; that informational text is outside this new
matrix's exact-parity assertion. This is explicit scope of this new DML check,
not a normalization of any existing failing fixture. It is not a claim of full
DML wire byte equality; any observed informational-text difference remains visible
for later consumer/P5 assessment.

Every scenario has an independent physical connection. Unexpected errors retain
the preceding trace, trigger a following-query health check where possible and
are aggregated, allowing the other scenarios to execute. Any failure/mismatching
case makes the comparison FAIL. Four deterministic controls cover uint64 parsing,
semantic-field mutations, null/reused-type request framing and evidence retention
following an unexpected failure. No failure is relabelled SKIP or accepted here.

## Reproduction and next gate

Use Python3.14, pytest8.4.2 and PyMySQL1.2.3. Inspect the exact Git source with
scripts/git_identity.py before work. Run:

```sh
python -m pytest -q -rA tests/test_prepared_p2_matrix.py
python tests/v06_prepared_p2_matrix.py --native-port PORT \
  --reference tests/fixtures/prepared-p2-matrix-native.json --output native.json
```

Create the native container from the receipt's image digest, test database, empty
root password and loopback-only port. Fixtures derive from that fixed reference;
the confirming replay passed after failure-recording logic was added. The temporary
container/venv are removed after preserving results. No performance measurements
or new platform claims are made.

Submit on prepared-product at the exact new commit: retain source/unit and actual
P1/original22/TIME13 steps, then run v06_prepared_p2_matrix.py with --host pointing
to that development host and --reference pointing to the new native fixture.
Collect matrix.json even on FAIL. Guest source, experimental patch, converter,
canonical source and single identity binding are unchanged in this continuation.
The changed boundary is probe/test/workflow; no local unchanged Go rebuild is
necessary. Existing generated inventory/public checks and diff checks still run.

Do not declare the whole P2–P6 scope complete from these20 cases. After the actual
gate, disposition any findings against the approved P2 criteria, then continue
P3–P6. Main integration, version placement, Qualification and release remain separate.
