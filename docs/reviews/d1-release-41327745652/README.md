# Deferred startup / routing exclusion — verified and adopted

[Release41327745652](https://github.com/masahitojp/mariamem/actions/runs/41327745652)
completed successfully with operation `verify` on source_commit
`90e7ed5f631533929000f390b67847b9549c3ab8`. The aggregate receipt and both platform
receipts say READY. Core, independent guest generation, runtime qualification
and all declared feature jobs passed. Publication/public smoke were skipped;
no tag/release/publication operation was requested.

The existing Django installed-wheel campaign passed all four cells, each with
20 scenario assessments, `installed=true`, a clean checkout and the same
host/adapter source SHA. The guarded backend is included in both wheel records
and in the recursive campaign input hashes.

| Cell | Python | Result |
| --- | --- | --- |
| macOS15 arm64 | 3.11.9 | installed,20 PASS |
| macOS15 arm64 | 3.14.10 | installed,20 PASS |
| Ubuntu24.04 x86_64 | 3.11.17 | installed,20 PASS |
| Ubuntu24.04 x86_64 | 3.14.9 | installed,20 PASS |

`receipt.json` binds three downloaded ZIPs to their GitHub artifact digests and
retains raw/saved file hashes. It preserves a compact aggregate READY summary and eight
input/result JSONs. The full wheel/source-file inventories are omitted; guarded
backend presence is derived from the original wheel records. The original READY
file hash and artifact digest remain recorded. Home prefixes are normalized. Per-case stdout, component
logs and the older/native campaign output remain in GitHub artifacts with finite
retention; this directory does not claim to preserve all of those raw logs.

Normal Development41325683292 also passed `check`, `integration` and
`Live required gate` at the same head. Following the Human's status request and
the previously agreed pre-merge condition, PR #70 squash-merged through normal
protection to main source_commit `c4742390cf4553636ceaa23c6732d48f76a37c9c`.
The merged tree matches the reviewed head. No bypass was used.

This accepts the requested declaration-only settings / DB-setup-time startup,
early-SQL guard, collection rejection of mixed routing, and zero-routed warning
within the documented finite profile. The old local-only checkpoint remains
historical; it is not edited or relabelled as hosted evidence. No blanket custom
hook compatibility, mysqlclient routing, unified entry, resource or performance
claim is added.

READY belongs to90e7ed5f only; the squash commit and subsequent documentation
are not a new exact-SHA READY. Version metadata is still0.6.0 and the run's
candidate assets have that existing name, but they were not published. Selecting
a later release version and submitting operation `release` remain separate.
