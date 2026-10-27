# CI40417099015 receipt

Exact source_commit: 6edcd29e65d3a669d5be6520abf6be2e61fa3445.
run.json, jobs.json and artifacts.json preserve authenticated GitHub API results.
The four zip.base64 files losslessly preserve the original artifact ZIP bytes;
the decoded SHA256 equals each artifact's GitHub digest. artifact-members.json
records every uncompressed member hash. SHA256SUMS.json covers saved files.

Run python3 docs/reviews/v06x-live-main-evidence/ci-40417099015/validate.py from
the repository root to verify the source/run/jobs/digests, fresh native reference,
raw browser XML/events, exact failures, real controls and installed consumers.
The validator evaluates assessment predicates from the pinned candidate source.
It also checks the canonical counts, all three adapter race packages and the
prepared-consumer integration tripwire. It does not execute a guest or rerun CI.

CI PASS is scoped to the observed hosts and interpreter versions in assessment.
The earlier local Python3.14.9/OpenSSL4 import failure remains a separate failure;
these CI receipts do not establish support for that environment. Main adoption,
Qualification and release remain separate decisions. Original a1baaad receipts
and references are unchanged.
