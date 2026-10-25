# Bounded dump comparison — observed matrix PASS

Decision for the next Human Review: whether to productize a bounded library
path. Recommend that direction for the fixed MariaDB-produced format: the
reader preserved the same canonical bytes/semantics as the native reference
through ordinary two-child preparation on both supported hosts/interpreters,
without requiring a native executable for that route. The strongest objection
remains maintenance of a second client parser. Keep the producer/options and
supported framing contract explicit, fail closed outside it, and retain native
differential tests. If that bounded contract cannot be maintained, prefer the
working optional external-client recipe. This report recommends direction;
it performs no productization or main adoption.

## Exact evidence and original conditions

Reviewed experiment source_commit `9494e755a5e7d79a9702e1d1dc7c1caae993e801`,
parent `5a9661d821150b3992466fa49a071a213cbaab78`, experiment/dump-import.
The Human separately authorized the host status-decoding correction after the
[failed comparison](v06x-dump-comparison-ci-failure.md). Its approved before/after
file hashes are included in the new binding. No guest/generated/SDK/release,
canonical input, producer or SQL oracle changes accompanied that correction.

[CI40192797648](https://github.com/masahitojp/mariamem/actions/runs/40192797648)
passed all three jobs: native121167203643, Ubuntu121167409567,
Mac121167409586. The [saved receipt](v06x-dump-comparison-evidence/ci-40192797648/assessment.json)
includes metadata and all three original artifact ZIPs, each independently
SHA256-verified against GitHub's artifact digest. The
[checksum manifest](v06x-dump-comparison-evidence/ci-40192797648/SHA256SUMS.json)
covers the archives, metadata and assessments. The archives retain full raw
inputs, output, observations, events and failure diagnostics; no synthetic PASS
replaces an earlier receipt.

The fresh producer on this exact candidate reproduced canonical application.sql
SHA256 `081ef0273c3625cb1d2a143415b90e9845bc2132312853a047eed09c8807e87c`.
The original source6d81a2f and original manifest remain unchanged; the new
candidate manifest and BOUND receipt are separate. Users/addresses migrations
and seed were reused and extended with exact decimal, binary, Unicode, NULL,
empty and escaped data, a procedure and a data-reading function. Retained
root@localhost DEFINER/SQL SECURITY, fixed producer options and normalization
policy were exercised. No routines were removed or engine/collation rewritten.
Observed-host acquisition passed. These close the executable prerequisites
from the [design](v06x-dump-import-design.md) for this fixed input.

## PASS / FAIL / SKIP matrix

| Observed host | Python / pytest | Guest native client | Guest library reader |
| --- | --- | --- | --- |
| Ubuntu24.04 x86_64 | 3.11.17 / 7.0.0 | PASS | PASS |
| Ubuntu24.04 x86_64 | 3.14.8 / 9.0.2 | PASS | PASS |
| macOS15.7.9 arm64 | 3.11.9 / 7.0.0 | PASS | PASS |
| macOS15.7.9 arm64 | 3.14.7 / 9.0.2 | PASS | PASS |

No exercised comparison cell failed or skipped. Ubuntu's Mac-only acquisition
workflow steps were skipped by platform condition; that is not a skipped
comparison cell. Native references passed on both hosts and their observations
were equal. The direct guest native-client probe precedes the reader probe;
both matched the native observations. The reader executed90 statements with
four DELIMITER directives. Per-cell lifecycle runs then matched the native
reference and passed two ordinary child tests: first commit, second retained
the imported baseline. Eight positive scenarios yielded16 child test passes.

Comparison covers table/column/key/FK/index metadata, engine/collation and
AUTO_INCREMENT, exact typed rows, routine metadata/behavior and subsequent
SELECT. Session settings were restored. All24 negative scenarios passed:
missing-table SQL1146/42S02 after partial DDL, malformed framing, and forbidden
SOURCE. Reader diagnostics preserve stage/ordinal/original line and byte span;
native diagnostics preserve client error and original line-derived span, with
ordinal explicitly unavailable. Reader preflight rejects framing/SOURCE before
any application tables; the native client can leave imported tables before its
failure. Both discard the source, with no Snapshot/test admission. All source
cleanup records confirm closure, process reaping and directory removal;
original endpoint contacts are zero. Expected failing pytest setups are negative
controls, not successful test bodies. No xdist census was repeated.

## OpenSSL warning on the Mac job

Homebrew installed openssl@4/4.0.2 while openssl@3 retained the global link.
The [loader/dependency assessment](v06x-dump-comparison-evidence/ci-40192797648/openssl-assessment.json)
records all three native executables explicitly referencing
`/opt/homebrew/opt/openssl@4/lib/libssl.4.dylib` and `libcrypto.4.dylib`, and the
resolved Cellar path and library hashes. Thus the global link warning has no
observed impact on this run. No `brew link` change is needed. Native startup,
reference and comparison passed with that arrangement. This does not establish
TLS handshake behavior, clean-machine reproducibility or setup cost.

## Productization conditions and detection limits

The spike answers the bounded comparison question, not arbitrary dump support.
Before productization approval, specify the maintained reader format/options,
SQL-mode/quote/comment/DELIMITER boundaries, rejection behavior and ownership.
The fixed-input differential campaign and local framing mutation tests detect
regressions in the exercised corpus; they do not prove arbitrary future producer
output. Reader SQL failure classification currently asserts errno/cause/span but
does not assert SQLSTATE in run.py; this receipt independently checked42S02 in
all reader SQL-failure event records. Promote that assertion into the maintained
gate rather than relying on manual receipt inspection.

The native client is a demonstrated alternative with its own acquisition and
dependency upkeep; its diagnostics lack statement ordinal. The reader adds
test-only framing/command rejection and avoids the native executable for import.
Neither route has measured setup-cost or parser-maintenance cost. No runtime
speed, cold Mac or user-time advantage is inferred from job duration.

Views/triggers, events/packages, MySQL-produced dumps, arbitrary legacy apps and
Django remain outside scope. No new public guide contract or generated ownership
change was found in this candidate: those boundaries are unchanged. The host
decoder correction remains experimental and needs its own adoption assessment
before main. Prior40169643384/d19ab2e,40172057245/f94a2d4,
40173427178/353bf92 and failed40188523035/5a9661d retain their original meaning.
No design branch merge, automatic preparation routing, product dependency/API,
productization, main integration, Qualification or release has been performed.
