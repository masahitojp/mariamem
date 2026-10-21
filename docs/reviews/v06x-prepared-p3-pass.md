# P3 development acceptance — both OSes PASS

[CI39686154515](https://github.com/masahitojp/mariamem/actions/runs/39686154515)
completed successfully at source_commit
`6fc594a39ecc27fd92dc798208a02c53748a79b9`. All five jobs PASS.
The approved full P3 development acceptance row is now complete.

| Gate | macOS arm64 (macos-15) | Ubuntu x86_64 (ubuntu-24.04) |
| --- | --- | --- |
| Full P3 actual guest/native comparison |14/14 PASS, no differing cases|14/14 PASS, no differing cases|
| PS_MULTI_RESULTS advertisement and negotiated on/off |PASS|PASS|
| Following QUERY, CLOSE/PING and per-case root cleanup |PASS in all14 cases|PASS in all14 cases|
| Previous P1 / P2 / minimal CALL |PASS /72 cases PASS / PASS|PASS /72 cases PASS / PASS|
| Formal development generation, compile and SQL/transaction/Snapshot/Fork/Close smoke |PASS|PASS|
| Installed binding mutations |18 PASS|18 PASS|
| Python/C checks; three Go race packages |112 PASS; PASS|112 PASS; PASS|

The14 cases cover0/1/several/129 ordinary results, IN/OUT/INOUT and repeated
binding use, errors before/after results, same-handle metadata changes, and
paired capability states. Complete metadata/rows/status/error packet traces
match the pinned native oracle. See the [coverage and repair](v06x-prepared-p3-matrix.md)
for the approved row and the original two failures; those failures and original
native expectations remain preserved. The fix validates the entire guest chain
before selecting dedicated OUT results according to the external client's flag.
Ordinary results and errors are retained; malformed hidden OUT is still rejected.

Both actual hosts use guest SHA256
`e6d6021a5753492169aeacbbc787e693e1730026b6da9960ef8c6ace296ac37a`.
Fresh exact-candidate CI generation replaces the earlier local composite-host
limitation for this acceptance gate. It does not constitute independent release
regeneration or Qualification. Converter commit and13 patches remain unchanged;
canonical checked-in Generated Go is not adopted by this staged gate.

[Saved evidence receipt](v06x-prepared-p3-pass-evidence/receipt.json) records
artifact IDs, original file hashes, preserved file hashes, prior control summaries,
and exact source identities. Full14-case captures, installed binding checks,
unit/race logs and compact development identity inventories are retained per OS.
Runner path prefixes are scrubbed; original and stored hashes distinguish that
transformation. Full development receipts are represented by their original
hashes and summaries, not falsely labelled as preserved byte-identical originals.

P4 lifetime/failure/resource/long-data work, P5 real consumer/regression acceptance,
and P6 canonical/J1/independent generation remain unfinished. These finite P3
controls establish the approved P3 row, not general lifetime safety or production
readiness. Continue with P4 under the existing implementation approval. Main
integration, version placement, Qualification and release remain separate decisions.
