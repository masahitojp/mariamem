# Additional MariaDB Connector/Python replay — guest results pending

The Human requested a replay with the official MariaDB driver before disposing
of the two Connector/Python26.7.0 limitations in the
[P5 Human Review](v06x-prepared-p5-human-review.md).
This is a two-case experiment, not a new prepared implementation, adoption,
blanket driver-support claim or exception approval.

**Confirmed:** stable MariaDB Connector/Python1.1.14 successfully retrieves all
NUL-containing bytes and traverses both prepared CALL result sets against the
pinned native MariaDB12.3.3. Both subsequent queries work, and server PREPARE /
EXECUTE counters advance. This demonstrates a working Python driver path for
these purposes against native MariaDB. **Unfinished:** the same driver against
the actual prepared guest on supported macOS arm64 / Ubuntu x86_64; CI now
contains that replay. Do not infer guest PASS or an Oracle-driver root cause
from the local native result.

## Inputs and exact scope

Baseline/source_commit: `e8897ddb6c1be9d508b88523e07556433882e3df`.
New authored probe hashes, source distribution URL/hash, image digests,
versions, compiled C-extension hash and raw results are in
[the receipt](v06x-prepared-mariadb-evidence/receipt.json).
The local native result is **Linux arm64 Python3.14.8 / ConnectorC3.4.9 in
containers on a Mac**, not a macOS-native or Ubuntu x86_64 client test.
The server is the same pinned native12.3.3 image used by the P5 controls.

The [requested guide](https://mariadb.com/docs/connectors/connectors-quickstart-guides/connector-python-guide)
distinguishes stable1.1 from2.0 RC. PyPI currently identifies1.1.14 as stable;
we pin its sdist SHA256, not a floating/latest/RC install. No2.0, asynchronous,
pooling, ORM or general connector compatibility matrix is added.
The [cursor API](https://mariadb.com/docs/connectors/mariadb-connector-python/api/cursor)
describes binary execution. Because that page also includes2.0 behavior,
the actual1.1.14 source was inspected: cursors.py accepts binary=True and its
force-binary branch selects _execute_binary. The probe also requires server
counters to prove actual PREPARE/EXECUTE rather than assuming from an API name.

| Case | Native Linux/arm64 local | Actual guest macOS/arm64 | Actual guest Ubuntu/x86_64 |
| --- | --- | --- | --- |
| binary=True: SELECT ?, HEX(?), OCTET_LENGTH(?), CAST(? AS BINARY), four bytes410042 parameters | PASS: returned first value bytes410042, hex410042, length3, cast bytes410042 | PENDING CI | PENDING CI |
| binary=True: CALL p(?), two SELECTs7/8, nextset through terminal | PASS: both result sets, terminal drained | PENDING CI | PENDING CI |
| SELECT1 after each case and clean cursor/connection close | PASS, no cleanup errors | PENDING CI | PENDING CI |
| PREPARE and EXECUTE counter increases for each case | PASS | PENDING CI | PENDING CI |

Both input/query purposes match the original P5 edge cases. Driver spelling is
MariaDB cursor(binary=True) and ? markers, rather than Oracle
cursor(prepared=True) and %s. Returned types are saved verbatim. Byte-integrity
assertions permit str A-NUL-B or bytes410042 for the untyped first column; neither
permits shortened A. Native/guest comparison then requires identical retained
case objects, including types, results, following SQL and cleanup. Only engine
version suffix and absolute counter values are excluded; binary witnesses are
mandatory. This is not an accepted-failure matcher.

## CI boundary and reproduction

The existing experiment/prepared-consumers workflow adds:

1. Native control after the unchanged Oracle controls: install the pinned stable
   sdist, run both cases and upload full PASS/FAIL receipts.
2. On each supported actual-guest runner, after the existing P1–P5 and ORM gates:
   install the same stable sdist, connect to the exact development host already
   checked by installed binding, then compare with the native receipt.
3. Focused negative controls: reject shortened values, altered hex/length/binary,
   missing second result/terminal, missing binary witness, failed subsequent SQL,
   cleanup failure, failed native reference and missing case. Text-only or
   incomplete counters cannot establish binary execution. Three unit methods
   cover11 content/status and3 negative counter variants.

The CI installer uses runner Connector/C packages (apt on Ubuntu, Homebrew on
Mac), records their actual versions, and pins the Python driver source hash.
It runs after existing consumer probes to avoid changing their environment
before they execute. C-library builds are not claimed identical across these
platforms; the native reference and actual-driver profiles remain explicit.
No runtime dependency or canonical source/toolchain pin is changed.
A failed install is a missing required replay, not a PASS or silent pure fallback.

```sh
python scripts/git_identity.py inspect HEAD
# Provision Connector/C >=3.3.1 in an isolated environment, then install the
# exact sdist/hash in the receipt (the CI helper is for disposable CI runners).
python tests/v06_prepared_mariadb_probe.py --native-port 3307 --output /tmp/mariadb-native.json
python tests/v06_prepared_mariadb_probe.py --host /path/to/bound-development-host --reference /tmp/mariadb-native.json --output /tmp/mariadb-guest.json
python -m unittest discover -s tests -p test_mariadb_prepared_probe.py -v
```

Local helper syntax, negative controls and workflow YAML checks pass. No local
actual-guest build was run: the disposable tested hosts from the previous CI
were not retained as downloadable binaries. CI uses formal generation of the
same guest/converter inputs and existing binding/oracle checks. Runtime, guest,
converter, generated source and original Oracle failure oracles remain unchanged.
After CI, report the two drivers separately and return to Human Review. This
experiment does not change the pending limitation decision or authorize P6,
main adoption, a release version, Qualification or publication.
