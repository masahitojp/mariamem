# SQL, drivers and protocol compatibility

Applies to 0.6.2. For installation and a first test, see the
[README](../README.md).

## SQL and prepared statements

Stored procedures
and functions are supported through ordinary SQL, including
CALL result chains and Snapshot/Fork retention. Packages/package bodies are
outside product support and compatibility testing; events remain unavailable
in the embedded build (1235). DEFINER clauses and SQL SECURITY metadata are
accepted and retained, but `--skip-grant-tables` means account existence and
privileges are not enforced. See the [approved scope](decisions/routine-support-scope.md).
Since 0.6.0, the endpoint supports real server-side execution for Go explicit/implicit
Prepare and Python prepared cursors.
`DELIMITER` is a client directive, not server SQL. Python provides
an explicit [bounded dump reader](importing-dump.md); this is not a general
SQL-script importer or a Go dump API.

Oracle mysql-connector-python 26.7.0 has two named, accepted consumer exceptions:

- For the tested prepared CALL emitting two result sets via nextset, advancing
  after the first set can fail and leave that connection unusable. This affects
  pure mode on both supported guest platforms and macOS C/default in the fixed
  native-matched observations; it is not a claim about every CALL or driver.
- macOS C/default can shorten an untyped prepared character projection of
  A-NUL-B to A without a useful error. Typed binary columns preserve all bytes;
  pure mode preserves that projection. This is not evidence of file corruption.

Separately, in the native-matched macOS C-extension prepared syntax-error
case, the client reports `2006/HY000` although raw wire returns `1064/42000`
and subsequent SQL succeeds. This is the native-parity error-presentation
disposition, not a third exception under the CALL/NUL decision. It does not
make other `2006` errors safe or recoverable.

See the [CALL/NUL boundaries](decisions/prepared-consumer-exceptions.md)
and [syntax-error presentation](reviews/v06x-prepared-product-design.md#c-extension-syntax-error).
MariaDB Connector/Python 1.1.14 passes the two CALL/NUL cases on both supported
guest platforms; this is not blanket driver compatibility or a repair to Oracle
Connector/Python. Ubuntu's additional explicit C-extension mode may be unavailable
and is an allowed SKIP, not C-mode compatibility PASS; required default/pure modes
have their own executed evidence. No driver mode is silently substituted.
Server-side cursors / COM_STMT_FETCH remain unsupported.

<a id="wire-scope-for-current-source-builds"></a>

### Wire scope

Connection information defaults to root/empty password; placeholder credentials
are also accepted without authentication. TLS/SSL, compression,
DEPRECATE_EOF and alternate authentication are not advertised/supported in this
profile. COM_RESET_CONNECTION, server-side cursors/COM_STMT_FETCH, LOCAL INFILE
transfer, CHANGE_USER, STATISTICS, PROCESS_INFO and binlog/replication streaming
are outside0.6.2 support. Multi-packet continuation is also outside this profile.
SQL-file import is not LOCAL INFILE; metadata SQL is not an administrative wire
command. Per-entry uncaptured paths remain unverified;
passing application/Release tests is not evidence of additional protocol coverage.
See the [bounded wire contract and reopening rule](decisions/v060-wire-contract.md).




See [bounded pipelining](mysql-protocol.md), [Go toolchains](go-compatibility.md)
and the [Python lifecycle reference](python-reference.md) for further limits.
