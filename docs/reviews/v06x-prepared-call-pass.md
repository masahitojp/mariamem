# P3 minimal CALL: actual guest PASS on both OSes

[CI39631360824](https://github.com/masahitojp/mariamem/actions/runs/39631360824)
passes all five jobs on exact source_commit
`42be2b598b4b1a1047f7e9d3787d12fec11aa760`. The actual generated-Go guest's
minimal prepared CALL matches pinned native12.3.3 on macOS arm64 and Ubuntu
x86_64. [Receipt and saved raw results](v06x-prepared-call-pass-evidence/receipt.json)
bind source/guest identities, job/artifact IDs and original/stored file hashes.

The new gueste6d6021a passes formal installation/compilation, reviewed binding
and18 mutation tests, SQL/transaction/Snapshot/Fork/Close smoke, P1 controls and
all72 P2 typed/native scenarios per OS. No expected fixture or failure oracle
was relaxed. Development provenance remains UNQUALIFIED; canonical Generated Go
is still the prior routine guest pending P6.

The minimal CALL has an OUT INT parameter and two ordinary results. Complete
PREPARE descriptors, result metadata, binary row bytes, EOF/status and terminal
OK match the saved native reference:

| Result | Values | Status on both OSes/native |
| --- | --- | ---: |
| First ordinary result |11|10|
| Second ordinary result |22,33|10|
| OUT result |44|4106, includes SERVER_PS_OUT_PARAMS|
| Terminal OK |No columns|2, no MORE_RESULTS|

SELECT1 on the same connection, CLOSE immediately followed by PING, and DB/host
cleanup all PASS. The recorded host/source/guest identities match the single reviewed
Wasm; the64-byte layout relocation was not normalized away by the installer.
The native comparison retains its Linux aarch64 Docker reference provenance;
the actual generated-Go jobs themselves run on the named native host platforms.

This closes the first P3 feasibility gate: **embedded public mysql_stmt_* APIs
can deliver two ordinary results, OUT and completion through this actual guest
and host bridge.** It does not establish full P3 support or ordinary-driver
acceptance. The raw probe deliberately requests PS_MULTI_RESULTS while the host
still does not advertise it. Internal guest capability, requested client flags
and truthful external capability negotiation remain separate concerns.

Next execute the approved full P3 matrix:0/1/several/129 results where native
accepts, IN/OUT/INOUT, later SQL errors, changing metadata, following QUERY,
truthful PS_MULTI_RESULTS negotiation and no pending-result leaks. A minimal
PASS does not waive any of those cases. Required prepared consumers are P5;
P4 lifetime/failure/resource coverage and P6 canonical independent generation/
J1/license/provenance/release guards remain open too. Main adoption, target
version, Qualification and release are separate decisions.

This entry changes evidence/state only. No new runtime tests were rerun locally;
the report verifies completed CI artifacts. Public-source/diff checks and saved
checksums are verified after writing the complete evidence tree.
