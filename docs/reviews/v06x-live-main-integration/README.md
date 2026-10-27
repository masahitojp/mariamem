# Protected PR1 Live main adoption receipt

PR1 was merged without bypass at 2026-10-27T05:34:27Z:

- Starting base: bf3a29c292064ddbbd4c7b9a9c6e712504d0f4e4.
- PR head: fcc6bd856867afdf5909c8fec4abd5c586ec434e.
- Actual CI-tested synthetic merge source: cf3991234efa3897a7a50466b07e29a97af2aa7c.
- Actual squash/main commit: 212bb07ffb8e89669c32d6b5a7ba94fc7aa18b2c.
- Identical tree: 1fa0450ad351833631df4b1079c013604fa10323.

PR before/after, main before/after, run/jobs and post-merge protection JSON retain
authenticated API results. All required check/integration/Live required gate
contexts pass; strict base and admin enforcement remain active, all app 15368.
No admin bypass or protection weakening was used. completion.json records the
adoption result; the prior submission-time policy snapshot remains unchanged.

CI40448056639 Live artifacts are the original ZIP bytes encoded as Base64 and
matched against official digests; every member has a checksum. CI40448056712
Development jobs also succeed. The APIs bind run head to fcc6bd8 while the native,
Go buildinfo and actual runner records bind tested source to cf39912. They are
separate identities. CI is not relabelled as the squash/main source 212bb07.

tested-merge.commit.txt preserves the raw Git commit body. The validator checks
its Git commit-object hash and tree against the landed main and retained PR head.
This permits a future clone to verify the synthetic commit even if GitHub removes
its merge ref. Predicates are read from the landed commit's identical tree;
artifact source/binary checks still require the original tested merge SHA.
Run python3 docs/reviews/v06x-live-main-integration/validate.py from the repository
root; no guest executes and no CI is rerun. SHA256SUMS.json covers receipt files;
artifact-members.json covers uncompressed members.

The product was adopted unreleased; Qualification, version and publication were
not requested or performed. The local OpenSSL4 FAIL and older candidate receipts
retain their original scopes. Guide-only observation versus model acceptance,
docs/reviews skip policy and broader Go/native interruption are explicitly
undecided post-adoption work. Completion-record docs are carried through their
own protected PR; that PR changes no product/CI/runtime inputs.
