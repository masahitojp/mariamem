# Prepared spike continuation — default Python and multi-statements

2026-10-19. Human authorized continuing the spike from
`c6337f2237717ab7cb593e2dd34a6dd2ab49865b`, with MULTI_STATEMENTS support and
Connector/Python 26.7.0. This is not approval for production implementation,
main adoption or publication. Preserve the [first spike](v06x-prepared-spike.md)
as historical evidence; do not rewrite its FAIL/SKIP results.

## Scope and stopping point

- Enable negotiated multi-statement execution in resident sessions, not merely
  acceptance of the client bit. Preserve unflagged single-statement sessions.
- Preserve ordered results, status/MORE_RESULTS flags, intermediate errors and
  connection reuse; compare with the same pinned MariaDB 12.3.3 reference.
- Test Connector/Python 26.7.0 on Python 3.14 with default connection flags,
  prepared=True, pure and C extension. No flag workaround, SSL monkeypatch or
  SQL interpolation as a substitute for success.
- Rebuild the guest from fixed inputs, use the existing converter/patch series,
  independently regenerate, review the exact J1 allocation/lifetime bindings
  and retain its negative oracle. No generated Go hand edits.
- Keep bounded spike type/row/statement limits explicit; do not claim full
  prepared/cursor/multi-result conformance. Native Ubuntu remains a separate
  acceptance condition unless actually executed.
- Return PASS/FAIL/SKIP evidence and revised feasibility judgment for Human Review.

Initial environment finding: the specified 26.7.0 still imports removed
ssl.PROTOCOL_TLSv1 under local Homebrew Python 3.14.8/OpenSSL 4.0.3. Retain this
failure. Compare an unmodified standalone Python 3.14 distribution to separate
Python version from TLS-library/build effects; do not inject deprecated constants.

Status: in progress; no new success claim yet.
