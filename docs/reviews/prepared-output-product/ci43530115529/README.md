# Fixed host public source43530115529 — PASS

Exact ef4d5cd97f718ebaaa5b2fa0d7999e3e6b169b9e passed existing full verify.py
integration on macOS15 arm64 and Ubuntu24.04 x86_64. Both logs include component
race checks, public Go/default-memory/OOB, actual dictionary/worker regression,
Go/Python Live smoke,54 Python runtime cases,33 Snapshot checks, prepared
consumers/native matching and exact accepted-exception tripwires. Known Python
functional FAILs remain FAILs under the Human's accepted disposition.

Source identity, complete integration output and generated inventory check are
retained with original and normalized hashes in acquisition.json. As before,
the existing helper removes temporary detailed consumer captures; the complete
execution summary is retained, and missing original captures are not invented.
Normal Development43530112119 and installed43530119031 also pass the same host
SHA. Guest/C/generated source stays identical to canonical43450619130.
This does not publish a release or decide the old-native applicability proposal.
