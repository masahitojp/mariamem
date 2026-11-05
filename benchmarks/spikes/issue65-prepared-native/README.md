# Issue 65 — native prepared input in a real embedded engine

**Step 2: native prepared input reuse is feasible in the tested real embedded
build.** The final execution passed with `client_params` null throughout and
seven witnessed native decode entries. Recommend retaining the Vio/native-input
approach for a separately scoped step 3 design. The decisive evidence is actual
SQL execution with upstream decoding, rather than a mocked parameter fixture.

One material qualification: a truncated length-encoded string was accepted as an
empty string. This matches the unchanged upstream length decoder, not the initial
expectation of rejection. Native decoder reuse does not establish strict rejection
of every malformed packet. The full session/output/lifecycle patch remains the
strongest architectural objection; its size and WASIX feasibility are unmeasured.

Final receipts: `evidence/result.json` and `evidence/run.txt`.

## Question and method

Can upstream COM_STMT_EXECUTE parameter decoding compile and run in an actual
embedded MariaDB session without supplying `THD::client_params`?

Build the real static embedded library, not extracted functions, mocked THD or a
standalone network server. Keep `EMBEDDED_LIBRARY` enabled in every embedded
translation unit. Enable the native parameter branches inside `sql_prepare.cc`
with one experiment feature flag. The local Prepared_statement definition and its
uses are compiled together; THD and Protocol layouts remain embedded throughout.

A single-threaded experiment entry supplies an EXECUTE body (9-byte statement
header followed by null bitmap, new-types flag, type descriptors and values) to
`emb_advanced_command`. It dispatches through upstream `mysqld_stmt_execute`,
packet sanity checks, conversion setup, native parameter assignment and real SQL.
The probe never calls `mysql_stmt_bind_param`. Runtime checks abort if
`client_params` is non-null before dispatch, at native decode entry or afterward;
a counter witnesses actual native decode entry on every tested execution.

Preparing/closing statements, initializing sessions and reading results still use
the embedded C API. This intentionally leaves result marshalling unchanged. The
SET tests verify actual SQL variables through a separate SELECT, including no
variable changes on the rejected integer argument. Another parameterized SELECT verifies
42 and a three-byte string containing NUL via normal embedded binary result fetch.

## Identity and profile

- MariaDB 12.3.3 source_commit:
  `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`.
- Harness base source_commit: `a796ea01cef3950d9835d001ef40d20b0a93020f`.
- Pristine upstream archive plus the experiment patch only; product portability,
  WASIX and prepared patches are not applied. Canonical guest/source.patch is unchanged.
- Source, Connector/C and fmt archives are SHA256 checked against
  release/inputs.lock.json by inputs.py. Patch generation additionally checks the
  two original upstream files' SHA256. The actual upstream delta is preserved in
  guest/experimental.patch on this experiment branch.
- Existing Linux ARM64 build image:
  `sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f`.
- Native GCC 13.3, system OpenSSL/zlib/PCRE2; pinned fmt 12.2.0 headers. Exact
  versions and selected CMake configuration are preserved in evidence.
- Library Release profile with `-O0 -DNDEBUG`, explicit runtime witnesses using
  abort rather than disabled assertions. No ASan/UBSan, optimization benchmark or
  full storage/runtime qualification is claimed. InnoDB and unrelated optional
  engines are disabled; the tested SQL uses no persistent tables. Extra charsets
  are disabled; the probe explicitly sets the default-collation override map to
  the compiled utf8mb3/utf8mb4 charsets. The first run used the upstream default
  map and emitted a missing-ucs2 warning, retained in the original run log.
- CPU2, memory4 GiB; owned disk6 GiB, free-space floor8 GiB; build timeout2400s.
  No CI run. Containers and large recreatable inputs/builds are disposable.

## Reproduction

Use Python 3.12+ for the archive data filter. Prepare an owned workspace and run
its commands with scripts/experiment_disk.py (6 GiB budget, 8 GiB free floor).
With that workspace bind-mounted as `/exp` in the exact image above:

1. Run `inputs.py <workspace>/temp` from this spike directory on the host.
2. Run `patch.py <workspace>/temp/source <workspace>/worktree/guest/experimental.patch`.
3. In the container, run `sh /exp/worktree/benchmarks/spikes/issue65-prepared-native/configure.sh`.
4. Run `cmake --build /exp/temp/native --target mysqlserver -j2`.
5. Run `sh /exp/worktree/benchmarks/spikes/issue65-prepared-native/execute.sh`.

A pristine source tree is required for patch.py. An initial configure attempted
an irrelevant DuckDB submodule; the final configuration disables that plugin.
The first compile exposed the unsigned parameter-flag constant under a separate
embedded guard; the final patch enables that existing constant too.

## Actual observations

| Input / operation | Observed result |
| --- | --- |
| Signed int64 -42, string hello, NULL | SQL variables match all three values |
| Types omitted on repeat; string containing NUL | Stored types reused; exact three bytes retained |
| Unsigned int64 max; 300-byte length-encoded string | Exact integer and string retained |
| Declared string length5 with only two value bytes | Accepted as empty string; numeric variable changed to3 |
| Truncated int64 (three of eight bytes) | Rejected with ER_WRONG_ARGUMENTS1210; prior variables unchanged |
| Valid execution after rejection | Same prepared handle succeeds with99 and recovered |
| Prepared SELECT ?+1, ? | Fetch returns42 and the exact string containing NUL |

The first run deliberately expected string rejection and failed that assertion
(`evidence/run-first-expected-reject.txt`). It is not counted as a passing run.
After source inspection the final probe records the observed acceptance explicitly;
no parser logic was changed to make this pass. In upstream sql/sql_prepare.cc,
get_param_length returns0 for an overlong declared value after consuming its
length prefix, and set_param_str uses that value as an empty string. Both function
bodies are unchanged in the patch. A separately built standalone-server reference
was not run; attribution is grounded in the preserved source and embedded run.
Future adoption must decide how to handle upstream malformed-input semantics and
verify them in the full native packet endpoint. This spike makes no compatibility
promise for malformed packets.

## Interpretation and limits

The input-only experiment is deliberately not a production patch. The flag
selects native parameter semantics for the entire experimental library; existing
MYSQL_BIND prepared execution is not preserved alongside it. Its raw entry uses
a global borrowed packet and is single-threaded, with no ownership, concurrency,
reconnect, cancellation or transport safety contract.

No handshake/authentication, native result packets, Vio-to-dispatch integration,
wire PREPARE metadata, long-data/cursor/bulk commands, all parameter types,
reprepare, multi-session lifecycle, WASIX compilation, generated-Go execution,
Snapshot/Fork or performance acceptance is established. The truncated integer case
is a focused rejection check, not parser fuzzing or a memory-safety proof. The
truncated string case is explicitly an accepted upstream behavior observation.

A successful result removes the specific concern that embedded THD inherently
prevents reuse of the upstream prepared input decoder. It supports continuing
with a separately scoped step 3 design; it does not authorize implementation or
adoption of the full protocol architecture. The strongest remaining objection is
still the breadth of a coherent native output/session/lifecycle patch, together
with preserving the embedded bootstrap and WASIX constraints.

Committed text logs strip trailing whitespace only; raw/normalized hashes are in
`evidence/log-sha256.json`. The patch keeps upstream context bytes, using the
repository's existing patch-specific whitespace attribute convention.
