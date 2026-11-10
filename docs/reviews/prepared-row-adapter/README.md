# Prepared raw-row adapter: connected candidate

Recommendation: continue to one formal generated-guest validation if the Human
chooses to invest further. The bounded implementation removes C output bindings,
column refetch, and numeric/temporal reconstruction while keeping existing input
ownership. It adds no upstream engine patch or independent type registry. The
strongest objection is the new cached-row layout/lifetime dependency and modest
net source reduction; total MariaDB upgrade-cost improvement remains unproven.
This recommendation is for validation, not main integration or release.

Base source_commit: b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50.
Initial validator commit: d7f8fc1935b9da5a14deb89cc0aea6ed5279369c.
Candidate branch: experiment/prepared-row-integration (commit containing this report).

## What now runs

Production ps_capture_result calls store_result, traverses MYSQL_STMT.result,
copies the original binary rows to raw_rows JSON/hex before free_result, and
preserves metadata/status/affected/insert_id ordering. Row/list/count/packet/frame
bounds are checked. Output MYSQL_BIND buffers, ps_result_bindings, ps_cell,
ps_time_output and ps_little are removed from the production adapter.

Private prepared protocol is v2 in Ready/open/request/response. Host startup
rejects unsupported nonzero versions; request decoder and session advertisement
checks reject v1. Text SQL and explicit prepared-unsupported v0 remain supported.
Host validates each borrowed raw row using shared value rules, before whole-chain
OUT filtering and any response. Legacy rows/null/mixed fields and malformed
raw payloads are rejected. PREPARE and LONG_DATA ACK reject raw rows too.

C ownership harness emits the production adapter's real JSON, which a Go
integration test decodes and sends through the production result/OUT serializer.
The engine API underneath the C adapter is mocked: this is not a MariaDB/WASIX
runtime result. Existing native packet expectations and the historical encoder
remain independent oracles; legacy C conversion tests are preserved in the
test-only prepared_output_oracle.inc, not linked into production.

## Verified

- go test ./internal/preparedproto ./internal/mysqlwire ./internal/guest: PASS.
- python -m pytest -q tests/native/test_prepared_api.py: 2 PASS (normal and
  address/undefined sanitizers). Each exercises ownership and failure sweeps,
  LONG_DATA, metadata, private v2 golden request, multiple results and later error.
- C failure sweep: 16859 allocation/append points; cleanup leaves zero handles,
  metadata and owner allocations. Ten API/raw failures include short length,
  cycle/extra node, short list, excessive row length/count and bitmap minimum.
- C-to-Go integration: ordinary/OUT/terminal chain and later SQL error pass with
  unchanged packet assertions; malformed hidden OUT returns no packet prefix.
- Existing all-type encoder comparison, NULL/bitmap and length boundaries,
  temporal/header/prefix/suffix corruption, raw field presence/null/mixing and
  old protocol rejection PASS. See retained test output in evidence/.
- git diff --check PASS. Source identity checked before builds/tests.

Missing pytest in system interpreters was resolved using a disposable dedicated
venv; no project dependency or user environment changed. Initial test failures
were old v1 fixtures/advertisements, default null raw_rows on JSON-marshaled
mock results, and legacy test representation. Native expected bytes were not
changed to obtain PASS.

## Maintenance comparison against the same main

Across nine changed/added production C/Go files (excluding tests and reports),
physical source shrinks by13 lines: C prepared adapter -80; guest JSON receiver
+13; startup version check +4; host row assembly -5; shared row validator +55;
remaining four production files net0. Counts include the initial validator.
This is source accounting, not a measured time saving.

Removed repeating obligations: output MYSQL_BIND sizing/lifetime, variable-column
refetch/truncation handling, C float/endian and MYSQL_TIME-to-binary conversion.
Retained obligations: input decoder/bind/ID/type cache/LONG_DATA; metadata,
OK/ERR/EOF/status/OUT contracts; all current upstream/WASIX patches; generation,
binding, consumer and both-platform acceptance.
New repeating obligation: inspect cached-row producer, transfer, length and free
ownership per engine version. This remains inside one C function; Go sees neither
pointers nor native layouts. Existing 12.3.3/13.2 source comparison found no
change in this dependency; it does not establish future stability or upgrade time.
One-time costs: private v2/presence checks, test fixtures and failure-model update.
No duplicated type table or additional controller was introduced. The old Go
EncodeBinaryRow remains as a comparison oracle with no production caller.
#150 common-preparation benefits are not credited to this candidate.

Judgment: output-conversion responsibilities are concretely reduced. This supports
one generated-guest validation rather than more architectural exploration, but
is insufficient to claim lower total upgrade cost. It is not a broad maintenance
win solely because13 lines disappear. Stop/reconsider if real guest integration
needs another upstream hook, independent type rules or weakened public oracles.

## Remaining before adoption

The existing generated guest is still v1 and intentionally rejected by the new
host. No guest regeneration, formal receipt/binding or CI was performed. The
candidate is therefore not usable as a published product yet. WASIX/wasm2go,
actual patched MariaDB, changing result metadata, maximum-size old/new acceptance,
Snapshot/Fork/Live, both OS public paths, consumers and performance remain with
#134/#132. Existing patch comments describing output rebind must be reconciled
when preparing the formal candidate inputs. No contract exclusion was approved;
#138 remains stopped. Actual generation/acceptance costs must feed #128.
