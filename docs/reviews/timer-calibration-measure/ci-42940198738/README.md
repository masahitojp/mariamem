# Timer candidate: Ubuntu/native confirmation PASS

[Run42940198738](https://github.com/masahitojp/mariamem/actions/runs/42940198738),
[job130259901965 (runtime)](https://github.com/masahitojp/mariamem/actions/runs/42940198738/job/130259901965)
completed successfully, attempt1. Artifact13821256248 has ZIP SHA256
`238e6415a2fa2dbcb29a26c996ebbc3f36fd81f2701aae368857c26e53b6e356`.
The downloaded ZIP and all33 internal file checksums were verified.

| Identity | Exact source |
| --- | --- |
| CI orchestration | `6c654011508f9480a6fc2fecb44e42b02909b4fc` |
| Host / SQL and lifecycle harness | `f225968c332a692f5bce189b31aed1fab26e642a` |
| Development guest | `1731c394031b781ff813190bf9c42bee63516044` |
| Guest bytes | `a64b581154d7d1ca2ca8aae9a552c9433f7f1354b7c7f5a36d600b62a32d2c18` |

The host was regenerated on Ubuntu24.04 x86_64 using Go1.26.10; Python3.12,
PyMySQL1.1.2 and pytest9.0.2 are the selected CI clients.
The host/guest source split is intentional. Original source inventories and
CRC/data/thread bindings were verified by the unchanged development route.
This record commit only adds documentation/evidence and is not the measured source.

| Bounded check | Result |
| --- | --- |
| Existing real-guest transaction/Snapshot smoke | PASS |
| PyMySQL TCP: Fresh +2 isolated children, 18 ordinary/delayed SQL observations | PASS |
| Native MariaDB12.3.3: matching 18 SQL observations / following SELECT | PASS |
| Go Pipe: 3 ordinary/delayed pairs / following SELECT / zero mappings | PASS |
| Go lifecycle: 8 Fresh +16 isolated Forks / zero mappings | PASS |
| Native identity and schema disposal | PASS |
| Ubuntu before/after performance | NOT RUN |
| Product adoption / Qualification / release | NOT AUTHORIZED |

Delayed SQL reports22.387–22.494ms in the guest and20.209–20.280ms in native.
Every report meets the predeclared18ms minimum and client-wall-plus5ms upper
bound. Timing equality is not required; SQL text, rows/loops and subsequent
SELECT agree. Native phases recreate a two-row table and do not claim native
Snapshot equivalence. The guest oracle independently checks isolation,
host exit0, zero references and removal of its session directory.

The one lifecycle batch is correctness evidence, not a paired benchmark.
The existing Mac six-pair startup improvement and inconclusive whole-shop
performance remain unchanged. The next timer step is a separate adoption review,
including that whole-suite limitation and nominal1ms resolution metadata.
Do not merge this experimental history as a product candidate.

## Retained evidence

`receipt.json` preserves run/job/artifact identity and digest.
The original assessment, source identity, all bounded SQL observations and
lifecycle observations are retained byte-for-byte. Development/native summaries
retain original-file hashes and the facts used for this conclusion.
`artifact-file-sha256.json` is the original artifact's full33-file manifest.
`SHA256SUMS.json` covers the compact retained set.

The3MB development inventory, compiler logs, container inspection and redundant
producer probe traces remain represented by the artifact digest/file hashes;
they are not copied into Git. No binaries, Wasm, caches or build trees are retained.
The raw artifact can be downloaded with:

```sh
gh api repos/masahitojp/mariamem/actions/artifacts/13821256248/zip > receipt.zip
```

Verify its ZIP digest before extracting and then verify the internal manifest.
For replay of the bounded SQL assertions, use `semantic_rows` and `check_pipe`
from `tests/timer_runtime/ubuntu.py` at the orchestration source above.
Full rerun uses that commit's `timer-ubuntu-native.yml`; it is not needed merely
to verify this documentation update.
