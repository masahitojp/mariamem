# CI40435625453 correction receipt

Exact source_commit: c1ee8d32e309dbef514d45db37f12fbb53acb7a9.
All six jobs pass: scope, two native references, two guest host platforms and
Live required gate. run/jobs/artifacts JSON preserves authenticated API results.
Four zip.base64 files preserve original ZIP bytes, each checked against GitHub's
artifact digest. scope/required job logs are separately preserved as Base64,
including original ANSI bytes without rendering them. assessment records hashes.
SHA256SUMS.json covers every saved file except itself; artifact-members.json
covers each uncompressed ZIP member.

Run python3 docs/reviews/v06x-live-main-evidence/ci-40435625453/validate.py from the
repository root. It verifies source/job/digest binding, raw native/browser/SQL
and installed outcomes, actual scope output and actual aggregate NEEDS_JSON
through the exact candidate's verify_gate. It does not execute a guest or rerun CI.
The observed aggregate route is run_live=true with all dependencies successful;
a guide-only GitHub skip is not claimed.

Canonical check runs once per host using default Python3.14:1083 PASS,45 SKIP,
76 subtests. It includes the12 new existing-operation interruption cases. The
per-interpreter focused Live loop remains53 cases per OS/Python cell (212 total),
not99. The separate local99-case runs on both interpreters and24 deliberate
mutation failures remain in v06x-live-review-fixes under their original context.

protection-readback.json is a separate administrative observation. main still
requires check/integration, strict/app15368/admin enforcement. Live required gate
is NOT yet a repository requirement; activate/read it back during Human-approved
adoption, preserving any intervening settings. CI does not prove external policy.
Local OpenSSL4 FAIL, prior CI40417099015/6edcd29 and older a1baaad evidence retain
their original identities. This receipt does not authorize integration or release.
