# P2 typed-execution development gate PASS

[CI39616628715](https://github.com/masahitojp/mariamem/actions/runs/39616628715)
completed successfully on source_commit
`5146d8aa62a9132a31e53363fe6710bd756f20b1`. Guest-source, both unit jobs and both
native-platform development-runtime jobs PASS. [Receipt and saved results](v06x-prepared-p2-pass-evidence/receipt.json)
bind job/artifact IDs, exact host/guest identities and raw/stored file hashes.

On macOS arm64 and Ubuntu x86_64, formal generation/installation/compilation,
SQL/transaction/Snapshot/Fork/Close smoke, installed binding and17 mutation tests,
and the existing P1 lifecycle/native metadata probe all PASS. Development
provenance correctly remains UNQUALIFIED, not a production acceptance receipt.
The canonical checked-in runtime remains the routine guest pending P6.

## Typed execution and former failures

| Gate on each OS | Result | Cases |
| --- | --- | ---: |
| Original raw EXECUTE/native packet vectors | PASS |22|
| TIME width/native boundary controls | PASS |13|
| Extended types, DML/warnings, transaction, schema and SQL modes | PASS |20|
| Raw type NULL/unsigned transitions and single-execution metadata | PASS |15|
| Numeric/text unsigned NULL transition controls | PASS |2|

There are72 named typed scenarios per OS, with repeated execution/descriptor
reuse inside scenarios. This is not72 independent trials of each scenario.
Full packet metadata, row bytes and terminal statuses match the fixed native
references. The last three groups have empty failure/difference sets. The
original eight failures and later seven unsigned/NULL metadata failures no longer
reproduce in these same controls; their previous failing captures are retained
in the earlier reports. No expected native fixture/oracle was relaxed.

Disposition against the approved P2 row:

| Required property | Evidence |
| --- | --- |
| NULL/numeric boundaries and exact decimal/binary/Unicode/empty values | Original22 plus extended20, repair15 and unsigned2 native comparisons |
| Temporal cases | Original vectors, TIME13 and SQL-mode DATE controls |
| Repeated type/descriptor reuse | Original22 and transition/reuse controls in extended20/repair15/unsigned2 |
| Cells larger than4KiB and more than1,024 rows without truncation | Original22 includes8,194-byte binary value and1,500 rows; exact native packet comparisons |
| Unit packet vectors plus native differential | Both unit jobs PASS; all five actual guest/native groups PASS on both OSes |
| DML/warnings/schema coverage previously left pending | Extended20 and single-execution schema grow/shrink controls in repair15 PASS |

This closes the specified **P2 development acceptance row for this candidate**.
It does not close P3 multiple results, P4 lifetime/failures, P5 required prepared
consumers/regressions or P6 canonical independent generation/J1/provenance guards.
Those later combined gates may still discover interactions requiring P2 changes.
The native reference vectors retain their original engine/environment provenance;
a native Ubuntu/macOS host job is not a claim that the reference MariaDB engine
was built on that same platform.

## Next boundary

Proceed to the approved P3 work with the [source preflight and minimal CALL case](v06x-prepared-p3-source.md):
one OUT plus two ordinary result sets, exact ordered native comparison, terminal
OK/completion and following SELECT1. Current single-result transport deliberately
rejects MORE_RESULTS; it must not silently discard results to make this case pass.
Then retain the full P3 matrix. No new architecture exploration, main adoption,
version decision, Qualification or release is authorized by this CI result.
