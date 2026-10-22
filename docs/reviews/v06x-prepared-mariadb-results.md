# MariaDB Connector/Python replay — both actual guest platforms PASS

The two requested cases **work with MariaDB Connector/Python1.1.14 against the
actual prepared guest on macOS arm64 and Ubuntu x86_64**. Both match the fresh
native MariaDB12.3.3 control. This is positive evidence for a working Python
prepared path, not a conclusion that all Python drivers work or that the exact
Oracle Connector/Python defect has been located.

[CI39776208952](https://github.com/masahitojp/mariamem/actions/runs/39776208952)
passes all six jobs on source_commit
`4ce9422e8b5a49727f9a1e3ee81706545e4a8f0d`.
The [original replay plan and local native result](v06x-prepared-mariadb-replay.md)
and its initial pending matrix remain historical context.
[CI receipts and raw JSON](v06x-prepared-mariadb-ci-evidence/receipt.json)
record artifact names, original/stored hashes, job IDs and exact client profiles.

| Named boundary | Fresh native Linux x86_64 | Actual guest macOS arm64 | Actual guest Ubuntu x86_64 |
| --- | --- | --- | --- |
| NUL bytes410042 through untyped projection / HEX / length / binary cast | PASS: bytes410042 / 410042 / 3 / bytes410042 | PASS, same values and types | PASS, same values and types |
| binary prepared CALL with result sets7 and8 | PASS, both sets and terminal drained | PASS, native matching | PASS, native matching |
| Following SELECT1 after each case | PASS | PASS | PASS |
| Cursor/connection cleanup | PASS, no errors | PASS, no errors | PASS, no errors |
| Server PREPARE and EXECUTE counters increase for each case | PASS | PASS | PASS |

The API is MariaDB cursor(binary=True), using ? placeholders. This is verified
binary execution, not a text-query replacement. The native/guest gate compares
complete case results except engine-version suffixes and absolute status
counter values; it rejects failed native controls or missing binary witnesses.
All case assertions passed; there is no accepted-failure conversion in this
MariaDB replay.

## What changed in the judgment

Earlier, the remaining failures were only demonstrated with Oracle's
mysql-connector-python26.7.0, and other Python drivers were unverified for the
same purposes. This replay adds a successful official MariaDB-driver path on
both supported guest platforms. Thus it would be inaccurate to describe the
two failures as Python-wide, or as proof that the guest cannot execute prepared
CALL/multiple results or preserve these binary bytes.

The original Oracle control remains unchanged: both runtime jobs still report
native-matching PASS, prospective functional_acceptance FAIL and
human_disposition PENDING. The new driver PASS does not fix those observations
or authorize forcing an application to change drivers. The
[P5 Human Review](v06x-prepared-p5-human-review.md) remains the decision boundary
for accepting the two exact Oracle-connector limitations before P6. Its
recommendation now has this additional positive Python evidence; there is still
no Human acceptance, main adoption or release decision.

## Environment and limits

Driver1.1.14 is pinned by official sdist hash. The actual compiled extensions
and Connector/C versions are saved, rather than claimed identical:

| Profile | Python | Connector/C |
| --- | --- | --- |
| Fresh native client/server control, Linux x86_64 | 3.14.8 | 3.3.17 |
| Actual guest Mac client | 3.14.7 | 3.4.9 |
| Actual guest Ubuntu client | 3.14.9 | 3.3.17 |

Each client's exact extension hash is in its JSON. The native database is a
pinned Linux container, not a Mac-native MariaDB server. This functional
comparison does not claim identical whole client builds across platforms.
The replay does not cover all scalar types, OUT/INOUT with this driver,
callproc, asynchronous execution, pooling, ORM adapters, Connector/Python2.0 RC,
or MySQL-server behavior. No broader support statement follows from two cases.

Both unit jobs, guest source build, development runtime and pre-existing
P1–P5/installed/ORM gates also succeeded. No production runtime, guest,
converter or generated source was changed for the replay. It is not P6's
independent canonical generation/J1/provenance, Qualification or release.

This follow-up saves evidence and current state only. Its later documentation
commit does not relabel the tested source SHA or require repeating runtime tests.
