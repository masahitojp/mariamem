# Bounded TIME repair reproduction

Use the exact candidate commit and `scripts/git_identity.py inspect HEAD` before
source work. Input hashes, fixed native image and tested owners are in receipt.json.

- Run `python scripts/prepared_time_patch.py` to check the exact patch and pin.
- On the complete checksum-verified pinned source, before other edits to
  sql/sql_prepare.cc, call `prepared_time_patch.apply(source_dir)`. It requires
  the complete pristine hash, applies `patch --batch --forward --fuzz=0`, then
  requires the complete postimage hash. Reapplication and changed inputs fail.
  scripts/prepare_guest.py invokes it only for the explicitly pinned experimental
  patch and records the result separately in prepared-source.json. The branch
  experiment constraint and release rejection remain in force.
- Python3.14, pytest8.4.2, PyMySQL1.2.3: run the five named suites in local-tests.txt.
  Native reference: start the receipt's exact image with test database, empty
  root password, loopback port only. Run `tests/v06_prepared_time_probe.py
  --native-port <port> --output <time.json>` and compare all cases with the saved
  fixture. Run `tests/v06_prepared_p2_probe.py --native-port <port>
  --reference tests/fixtures/prepared-p2-native.json --output <original.json>`.
- The13 additional cases cover zero encodings, with/without fractional seconds,
  negative, >24h, maximum/range clipping, TIME column, CAST expression, mixed
  field/parameter and multiple parameters. Parameter descriptors are reused for
  all nine direct parameter cases. Compare full column/row/terminal bytes; no
  native value or metadata exception is normalized away.
- Submit the source/unit preflight branch. Unknown new guest identity is expected;
  do not execute it with an old binding pin. Review fresh translation/functions/
  data/TLS and explicitly bind a single new identity before returning to the
  existing prepared-product full development gate. That gate includes the original
  P1/P2 comparison and the extra TIME fixture. Full P2-P6 remains unfinished.

Local network permission failures occurred before native access/package download;
the authorized retries succeeded. These are not engine failures. The temporary
native container, source download and venv are disposable after compact evidence
preservation. No generated Go is hand-edited, no main integration or publication.
