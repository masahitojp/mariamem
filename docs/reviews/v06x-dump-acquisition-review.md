# Dump native acquisition preflight — Human Review

2026-10-25. **Decision now: accept the native acquisition preflight evidence.**
Recommend acceptance: actual MariaDB12.3.3 server/client/dump executables have
recorded hashes and architecture, and temporary native servers returned version,
the selected root definer account and SELECT1 on macOS arm64 and Ubuntu x86_64.
This closes acquisition condition4 of the dump design for the observed hosts.
The strongest objection is reproducibility on a clean Mac: this run reused
installed Homebrew libraries and relocated a bottle; it did not demonstrate a
dependency-free or cold-install recipe. That limits later setup comparisons,
but does not invalidate the observed native executable acquisition/startup.

The Human requested stopping at preflight before the next review. No further
comparison is authorized by accepting this report. Route selection,
productization, main integration, Qualification and release are separate.

## Reviewed object and source identity

The request did not name an evidence artifact SHA; these inputs are reconstructed
from the executed preflight and retained source:

- Base source_commit: `b5accce74e3a7e1347ef0cd2abad63cab493b122`.
- Preflight candidate source_commit: `d19ab2efbd3badf7b2d69d5061fd8788ae836daa`.
  Its diff contains only
  [`preflight_macos.py`](https://github.com/masahitojp/mariamem/blob/d19ab2efbd3badf7b2d69d5061fd8788ae836daa/tests/dump_import_spike/preflight_macos.py)
  and the
  [native-acquisition workflow](https://github.com/masahitojp/mariamem/blob/d19ab2efbd3badf7b2d69d5061fd8788ae836daa/.github/workflows/dump-import-spike.yml).
- Branch: `experiment/dump-import`. Its later producer commit is not the
  reviewed preflight candidate; do not substitute branch HEAD for this SHA.
- [Evidence manifest](v06x-dump-acquisition-evidence/manifest.json) and
  [file checksums](v06x-dump-acquisition-evidence/SHA256SUMS.json) pin this bundle.
  macOS execution recorded the design base before the harness was committed;
  the unchanged harness bytes were subsequently committed as d19ab2e. Its hash
  is recorded separately. This is local execution evidence, not exact-SHA CI.
- [Ubuntu CI40169643384](https://github.com/masahitojp/mariamem/actions/runs/40169643384),
  job121097696314, completed successfully on exact d19ab2e. Artifact12590042717
  has archive digest
  `sha256:b1eff87b61233e188a1090994ead12c66754000c5e0bdc408a37d92bae02694e`.
  Archive digest and extracted-file checksums are distinct identities.

## Native receipts

| Observation | macOS | Ubuntu |
| --- | --- | --- |
| Actual host | macOS27.0.1 arm64 | Ubuntu24.04 x86_64 hosted runner |
| Acquisition | Homebrew12.3.3_1 arm64_golden_gate bottle; formula source_commit1db0348859ae3b2e0de9babe91dfb3673bdfb729 | MariaDB OCI linux/amd64 child manifest2f4f46f80e7251990bfdc601ae3f7f2964ddb4dc1868f7deca699fc1ece8c35e |
| Server version/query | 12.3.3-MariaDB, arm64 | 12.3.3-MariaDB-ubu2404, x86_64 |
| Client/dump version | Both12.3.3; client15.2 / dump10.20 | Both12.3.3; client15.2 / dump10.20 |
| Definer account / query | root@localhost exists; SELECT1 returns1 | root@localhost exists; SELECT1 returns1 |
| Shutdown | Local process waited/reaped; see receipt | Service stopped in CI; completed job records container teardown |

The native MariaDB **server release** is12.3.3; client15.2 and dump10.20 are
their program-format versions, not substituted server releases. See the raw
[macOS query](v06x-dump-acquisition-evidence/macos/macos-native-query.stdout.txt),
[macOS receipt](v06x-dump-acquisition-evidence/macos/macos-preflight.json),
[Ubuntu tools](v06x-dump-acquisition-evidence/ubuntu/tools.txt),
[Ubuntu query](v06x-dump-acquisition-evidence/ubuntu/startup-query.txt) and
[Ubuntu image](v06x-dump-acquisition-evidence/ubuntu/image.json).

| Executable SHA256, as executed | macOS (after loader relocation) | Ubuntu |
| --- | --- | --- |
| mariadbd | 7f0185bbedf51cb8a86795f89127226cfc7ab31212fc8726bb74fe764a5cf10f | 5ff0bff4f2391b3fffcb9cfee95546fd5ad37e835c20a5e4f75a168f22b68b90 |
| mariadb | 2718db53701be9f77d8326c842116f4f5bfc3e3b62934cfc4220ce54ff289a99 | d720d1f98dea0e2c8806aac985d2b159da8b36f838043512ea788de077dabbda |
| mariadb-dump | 03af95aabf797659468ae3e2fcb8237875919dbc5744b369878a4108c3849879 | f9fc38479694c3a27260281e09fccb5c6e8788361f3e72d54ad36ac8a03cec05 |

macOS bottle archive SHA256 is
`6c25ed808b4270ee2dc80093895c3ffc71bc92e591c78aa1fe3ccf37cc10f74f`.
The receipt records original and relocated executable hashes, loader edits,
ad-hoc signing, actual dylib hashes and installed dependency receipts. Initial
environment-only relocation failed during bootstrap; that
[failed setup receipt](v06x-dump-acquisition-evidence/macos-initial-attempt/macos-preflight.json)
is retained rather than counted as a PASS. The unused external `rcmysql`
service symlink was excluded from scratch extraction; no service was installed.
The pinned Homebrew formula also contains its own OpenSSL compatibility patch;
this is identified native packaging, not an unpatched-vendor-build claim.

The Ubuntu child manifest was resolved from the prior multi-platform index
`805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5dbf2db714f9ed1`.
The local cached Linux arm64 image was not used as either native-platform receipt.

## Prior conditions and detection limits

Cross-check: [prior same-source condition](v06x-preparation-import-design.md#human-review),
[dump fixed input](v06x-dump-import-design.md#fixed-input-and-scope-before-execution),
and [routine contract](../decisions/routine-support-scope.md).

| Condition | Judgment at this gate | Detection / remaining boundary |
| --- | --- | --- |
| 1. Reuse users/addresses and seed; extend the same app | Fixed in design; execution excluded from this review | Native acquisition checks do not inspect application schema/data. No application-equivalence PASS inferred. |
| 2. Aligned root@localhost DEFINER; retain SQL SECURITY | Account prerequisite satisfied on native servers; import semantics unverified here | Query receipts detect absent selected native account. Guest privileges/security context remain bounded by the adopted contract. |
| 3. Listed producer options and normalization | Fixed in design; selected option names present in both help captures | Help availability does not establish import behavior or session restoration. No such CI coverage in this preflight. |
| 4. Both native12.3.3 toolchains, hashes/architecture/startup | Satisfied for the observed hosts | macOS harness asserts archive/formula hash, three versions/architectures and startup query. Linux CI records hashes/versions and asserts server version plus x86_64 output; see assertion gap below. |
| 5. Views/triggers | Explicitly deferred in design | No views/triggers compatibility is established. Final route recommendation must retain these exclusions. |

Two material limits remain visible:

1. **Linux version assertions are weaker than its receipts.** CI captures
   server/client/dump versions but its final guards only search the server query
   for12.3.3 and tool output for x86_64. A future changed client/dump version could
   escape those guards; current receipts independently show all three12.3.3.
   Tighten exact per-program/version/architecture and source-SHA assertions before
   treating this workflow as a reusable automatic input gate. This is a detector
   gap, not evidence that the observed tools had a different version.
2. **Cold Mac setup is unverified.** Formula/bottle, installed dependencies and
   bootstrap commands are pinned in evidence, but a clean machine was not used.
   Neither current CI nor this local receipt detects all missing-dependency or
   relocation issues on another macOS version. A later setup-cost comparison
   must account for acquisition/relocation and label warm versus cold setup.

No missing native target was found for this narrow gate. No new product/API,
guest/converter/generated source, baseline pin, public guide or release-ledger
change is in the candidate diff. No contradictory changed usage contract was
found. Dump routing, parser failure classification, partial-import behavior,
Snapshot admission, child isolation, benchmarks and cold-host installation are
outside the proof reached here; the unchanged runtime checks are not substitutes.

## Stop boundary and preserved additional work

Before the Human narrowed the task, the original spike authorization had also
led to canonical dump generation, macOS native-reference success/three failure
inputs, one Go host build, comparison scaffolding and17 Python3.14 framing/
classifier unit tests. **No guest dump import or library-to-guest run occurred.**
Those additional observations are not used to close this preflight gate.

The producer history remains at source_commit
`6d81a2f99d0b5bd09bb5ab48dbf1ae23ca27e149`; incomplete comparison source/input
is parked on local branch `experiment/dump-import-parked`, source_commit
`03cad716fd3a0a44558ef0133566b85f6ec8b1ba`. Compact additional logs/input remain
under `build/experiment-work/dump-import/evidence/outside-preflight-review/`.
This preserves unfinished work without presenting it as an accepted importer.

Reproduction: acquire the exact bottle/formula and dependency libraries recorded
in the macOS receipt, use a fresh budgeted workspace, and invoke the candidate's
`preflight_macos.py --workspace <absolute-workspace>` with Python3.14. The script
expects the named bottle in temp/ and formula JSON in evidence/; exact URLs are
in the receipt/formula JSON. The candidate CI workflow performs Ubuntu native
acquisition/startup only. No rerun or broader acceptance was started for this
review. Scratch/data/builds are disposable; evidence and retained refs preserve
the result. The next action is the Human's review of this preflight, followed
by a separate instruction if comparison should resume.

## Retention and verification

Owned scratch was finalized after process/container inactivity checks. The
workspace helper removed1,589,198,848 bytes of native datadirs/binaries,
environments, Go host/cache and the completed worktree; retained evidence and
branch refs preserve unique work. No owned path over1GiB or owned cleanup debt
remains. Existing unrelated worktrees and the pre-existing shared Go cache
(observed2.8GiB; not used for this build) were left untouched. The latter is
outside this owned cleanup, not a new KEEP claim; shared-cache ownership/activity
inspection remains separate cleanup work.

The final checks cover source identities, receipt checksums, local link targets,
selected option names in the retained native help, unchanged product boundaries,
and authored Markdown diff formatting. Verbatim native help/bootstrap outputs
retain their original trailing whitespace and blank lines; the unrestricted
diff whitespace check flags these raw receipts. They are preserved byte-for-byte
under the evidence checksums rather than reformatted. No runtime tests or new
CI runs were added for this documentation review. Root documentation changes
are preserved separately from the experiment source branches.
