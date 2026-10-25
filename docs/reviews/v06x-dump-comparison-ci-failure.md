# Dump comparison CI failure — bounded runtime scope decision

Decision needed: authorize a separate, bounded host status-decoding correction,
then repeat the unchanged comparison. Recommend continuing with that correction:
the same valid MariaDB internal status terminates both guest import routes on
both observed hosts. Choosing a reader or external-client recipe is premature.
The strongest objection is that truncating status blindly could conceal invalid
input or lose protocol flags. Require an explicit unsigned 32-bit input domain,
preservation of the low 16 protocol bits and regression tests before re-entry.
No runtime correction is implemented or approved by this report.

## Reviewed candidate and evidence

Candidate source_commit `5a9661d821150b3992466fa49a071a213cbaab78`, based on
`353bf9291d96785f8dcaa3585cec00e56242256e`, branch `experiment/dump-import`.
[CI40188523035](https://github.com/masahitojp/mariamem/actions/runs/40188523035)
failed: native reference job121154342229 succeeded; Ubuntu job121154528092 and
Mac job121154528063 failed. This is a failure diagnosis, not adoption review.
The [assessment](v06x-dump-comparison-failure-evidence/assessment.json), selected
raw campaign/events/pytest evidence and native observations are saved with
[file checksums](v06x-dump-comparison-failure-evidence/SHA256SUMS.json).

Artifacts: native12597192561, Ubuntu12596883218, Mac12597387608. GitHub reports
their ZIP digests respectively as
`df0d4b79c43b9eebcf3182d87aafdb08f0d9446bd16438bfe6d65b334988e6d9`,
`870841f10943d9604d53e374c902fde850c6b0d1fab0dcde7c0d62350cd137f5`,
`391518f498b48fc9ea98619e77f374a04a3e83df67618c510674c044c4e9c77d`.
These are API-reported archive hashes; the saved selected-file checksums were
computed locally. This bundle does not claim a separately verified ZIP receipt.

## Observed matrix

| Boundary | Ubuntu x86_64 | macOS arm64 |
| --- | --- | --- |
| Exact-candidate canonical production/binding | PASS | Same bound input verified |
| Native reference | PASS | PASS; observations equal Ubuntu |
| Guest native client import completion | PASS | PASS |
| Guest reader import completion | PASS, 90 statements | PASS, 90 statements |
| Subsequent routine/comparison query, both routes | FAIL | FAIL |
| Two-child success cases, Python3.11 and3.14, both routes | FAIL in setup | FAIL in setup |
| Invalid SQL / malformed framing / SOURCE controls | PASS, 12 scenarios | PASS, 12 scenarios |

The fresh candidate producer reproduced canonical application.sql SHA256
`081ef0273c3625cb1d2a143415b90e9845bc2132312853a047eed09c8807e87c` exactly;
the original6d81a2f manifest remains unchanged. Both import routes restored the
observed session state. Import completion does not establish semantic equality:
the observation function raised before its complete result could be compared.
All eight positive lifecycle cohorts had two setup errors, zero child test
bodies and zero Snapshot attempts. They are failed/not reached, not pytest
SKIP. The24 negative scenarios were accepted by their existing classifiers;
cleanup closed/reaped/removed each source. No original endpoint contacts were
recorded. This is negative-control evidence, not successful child lifecycle proof.

## Blocker and detection net

The failing query is `SELECT app.app_user_rating(1,3), app.app_user_rating(2,-2)`
(`tests/dump_import_spike/oracles.py:72` in the candidate). The function reads
the application table using SELECT INTO. The host aborts with errno2013 and
`json: cannot unmarshal number 65538 into Go struct field Result.result.server_status of type uint16`.

`guest/wire_core.inc:7` serializes the full internal `g_mysql->server_status`.
`internal/guest/guest.go:55` decodes it into uint16; the Unmarshal failure at
line186 aborts the guest process. In the exact pinned MariaDB source,
[mysql_com.h](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/include/mysql_com.h#L414)
defines SERVER_STATUS_RETURNED_ROW as 1<<16 and AUTOCOMMIT as2: the observed
65538 is their sum. MariaDB's native
[protocol.cc](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/protocol.cc)
writes two-byte status via q_append2b. Our network packet functions also accept
uint16 (`internal/mysqlwire/wire.go:207`). This identifies the internal JSON
boundary as the correction candidate; its fix remains unverified.
[Pinned-source hashes](v06x-dump-comparison-failure-evidence/upstream-proof.json)
preserve the source inspection identity.

The new data-reading function oracle detects this on both routes/hosts; the
positive lifecycle setups also detect it before Snapshot admission. The earlier
353bf92 producer probe used constant-returning routines against native MariaDB,
so it cannot establish guest decoding of this flag. Existing local framing and
binding checks likewise do not exercise that runtime boundary. Re-running the
same unchanged candidate would repeat a detected runtime failure.

Prior conditions: same application/canonical bytes, retained definer routines,
producer/normalization policy and observed-host acquisition are satisfied for
this run. Complete guest semantic equality and two-child behavior remain
unsatisfied. Failure controls were exercised as above. Views/triggers, cold Mac,
setup-cost, arbitrary legacy/MySQL/Django support remain outside scope. Earlier
40169643384/d19ab2e,40172057245/f94a2d4 and40173427178/353bf92 receipts retain
their original meaning and source identities.

## Proposed bounded continuation, requiring Human approval

1. Correct host-only internal JSON decoding to accept the legitimate unsigned
   32-bit server status and explicitly project its protocol low16 bits. Keep
   guest/generated inputs, SQL corpus, routines and comparison oracles unchanged.
   Reject negative, fractional and out-of-range values; cover nested results.
2. Add focused decoding and wire regression checks for65538, ordinary status,
   transaction/autocommit/more-results/prepared flags and invalid numeric input.
   Run the affected guest-decoder/mysqlwire tests; expand only for a concrete
   dependency or failure.
3. Explicitly record and pin the approved host delta in input binding. The
   current binding guard requires runtime equality with the original producer;
   do not silently bypass it. Rebind a new exact candidate, reproduce the same
   canonical dump, rebuild the host on both OSes and rerun the unchanged matrix.

The design's [stopping condition](v06x-dump-import-design.md#completion-and-stopping-conditions)
requires a separate decision for runtime/guest changes. No product/API/guest/
generated/release files were changed in this diagnosis. No user guide contract
or generated ownership change is proposed here; no inconsistencies found in
that unchanged boundary. This review inspects the failing boundary and saved
campaign evidence, not broad release acceptance or performance. Productization,
main integration, Qualification and release remain separate gates.
