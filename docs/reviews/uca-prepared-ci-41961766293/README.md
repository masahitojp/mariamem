# Prepared UCA canonical candidate — CI41961766293

Original [run41961766293](https://github.com/masahitojp/mariamem/actions/runs/41961766293)
passes on source_commit `cbd25f027e804bbd529a85208589ba2dd2899b86`.
Guest SHA256 is `6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`.

All five original ZIP bytes were downloaded and checked against the GitHub
artifact API digest. `download-checks.json` records the original ZIP/member
hashes, IDs and sizes. `artifacts.json`, `run.json` and `jobs.json` retain API
metadata. The guest WASM member hash was independently computed; two source
builds have identical linked/optimized hashes. No single-build receipt is relabelled.

| Boundary | macOS15 arm64 | Ubuntu24.04 x86_64 |
|---|---|---|
| Independent Go regeneration:106 files equal the tested Git tree | PASS | PASS |
| Actual six-table memcmp / one-cell corruption rejection | PASS | PASS |
| Ordinary/ambient/profiling separation | PASS | PASS |
| Actual worker trap / healthy peer / complete disposal | PASS | PASS |
| Six heap/mmap ownership controls, including two expected unsafe failures | PASS | PASS |
| Native SQL / two independent children / cleanup | PASS | PASS |
| Snapshot transaction/three-child smoke | PASS | PASS |

Native reference job127029530126; source build job127029530332;
macOS job127034132821; Ubuntu job127034132834. Every relevant step completed
successfully, rather than being skipped. The native control is12.3.3 and its
original JSON hash is checked by both platform results. Raw regeneration
inventories were compared to SHA256 of the106 actual Git files independently
of the workflow's PASS output. Exact declared UCA input provenance was rechecked.

`guest.json`, each platform's source/regeneration/ownership records and the
small test logs are retained verbatim. SQL summaries omit duplicate row vectors
but retain their original file and semantic hashes; the complete verified ZIP
member JSON/text observations remain in compact local evidence. Compiled WASM,
ZIP/build staging and source clones are disposable. `SHA256SUMS.json` covers
all retained receipt members except itself; it does not sign or qualify a release.

This is bounded candidate acceptance. No performance benchmark ran in this CI;
the existing five-pair performance cohort remains Mac-only and at its original
source. Candidate adoption, protected main integration, Qualification and release
remain separate. GitHub currently reports no usual required PR checks at this
head; do not substitute these four candidate jobs for `check`, `integration`
and `Live required gate` before integration.
