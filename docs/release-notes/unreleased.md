# Unreleased changes

No unreleased product changes are recorded after 0.6.2.

This is the sole staging source for future release notes. Add only changes
merged after the latest published release; a planning issue or experiment is
not a shipped change. During an explicitly versioned release, transfer the
applicable content to `release/NOTES-vX.Y.Z.md`. Release CI consumes that
versioned file, not this staging document. Once published, remove the transferred
entries here so they are not accidentally presented as new changes again.

Published notes: [0.6.2](../../release/NOTES-v0.6.2.md),
[0.6.1](../../release/NOTES-v0.6.1.md), [0.6.0](../../release/NOTES-v0.6.0.md).
The superseded drafts remain in Git history; release receipts keep their
original source identities.

- Candidate: reuse an immutable initial-memory image within each host process.
  A bounded shared backing file remains until process exit; DB Close still
  releases all per-instance resources. Generated layout checks protect guest
  updates. This does not share application data or retain a live engine.
