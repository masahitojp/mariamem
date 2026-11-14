# Public integration43460417407 — PASS

Candidate febce67403fa762a33f3e95ace8a9bff069c1102 passes the existing full
verify.py integration on macOS15 arm64 and Ubuntu24.04 x86_64. Both logs retain
race/component execution, public Go/default-memory/OOB controls, actual worker
and dictionary regression, Go/Python Live smoke,54 real Python cases,33 snapshot
checks and prepared Go/Python consumer matching with exact accepted-exception
tripwires. Known Python functional FAILs remain FAILs under the accepted policy.
Logs establish execution; they do not manufacture missing detailed captures.

Normal Development43460340200 also passes on this candidate. The candidate's
runtime and guest bytes are those independently reproduced in43450619130; later
repairs reconcile handwritten test fixtures/source metadata. No new C input is
introduced here.

This is source consumption, not installed-wheel/external-module acceptance or
same-condition performance. The next manual installed stage uses existing
build_alpha --ci-candidate and generated_release_acceptance in candidate mode,
without publishing or rebuilding the guest. Its exact wheel/source hashes and
ORM/external-module cases must be recorded before declaring those gates complete.
