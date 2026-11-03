# Wire inventory reconciliation for Issue #78

2026-11-03. Inspected source_commit
`9a66765666ff602d5efec48b6481ae73c104b904`, the credential-change candidate in
[PR #79](https://github.com/masahitojp/mariamem/pull/79). This is the active wire
source for the fixture contract. The prior
[G1 reconciliation](v06x-wire-main-437d74d.md) and its source
`437d74d9d11d8dc2a03dc94bba0d37346131ebff` retain their original evidence context.
The [older inventory](v06x-wire-current-inventory.md) remains a historical
account of source `cc00ccd98e29a1f5d5088a082be90a3cdaa4f469`.

## Reconciled boundary

Only `internal/mysqlwire/wire.go` differs from the prior four-file wire baseline.
It parses and consumes the username and password response without checking their
values. Arbitrary test credentials such as `test/test` and `root/root` are
accepted; they do not select a guest account or change SQL privileges. Returned
connection information still defaults to root with an empty password.

The greeting still advertises `mysql_native_password`. Both the length-prefixed
secure response and the legacy NUL-terminated response are parsed. The existing
short-handshake, malformed-string, truncated-response and unsupported-capability
checks remain. Required SSL requests are rejected. Credential bypass does not
implement account authentication, alternate authentication plugins or TLS.

Supported commands remain QUIT1, INIT_DB2, QUERY3, PING14, Prepared22–26 and
SET_OPTION27. Base advertised capability bits remain
`1|4|8|512|8192|32768|65536|131072|524288`; PS_MULTI_RESULTS `1<<18` is still
conditional on validated prepared support. Prepared session handling and
`guest/wire_core.inc` / `guest/resident.inc` are byte-identical to the prior
baseline. The remaining command/capability gaps and observation obligations in
the historical inventory are unchanged except for its root/empty-only
credential restriction, which this reconciliation supersedes.

## Evidence and detection

`TestDefaultTestCredentials` exercises the credential matrix with actual SQL
reads/writes, both password-response encodings, an empty username and malformed
handshakes. `test_placeholder_credentials_accept_normal_queries` covers the
PyMySQL credential matrix. Both test owners belong to the existing integration
entry point; the daily source-check result alone does not imply they ran in CI.
The [PR description](https://github.com/masahitojp/mariamem/pull/79) distinguishes
original-candidate local runtime results from the rebased candidate's focused
checks.

The first PR CI failed its fixture-contract lint because the contract still
pinned the previous wire source/hash. Its dependent gates failed and its runtime
smoke was skipped. This reconciliation updates the active inventory, wire source
commit and hash; it does not turn that failed run into acceptance evidence.
The lint continues to compare all four working files against the inspected
commit, check dispatch/capability sets and reject source/hash mutations. It grants
no new runtime, fixture-entry or release acceptance.
