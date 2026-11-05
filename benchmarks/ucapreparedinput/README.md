# Prepared UCA numeric input — preparation only

These three explicitly formatted JSON text inputs re-express the exact numeric tables from experiment
`e33fc6ce3bae390c6dda0fd92d024d8094df8731`. They store gzip/base64-encoded uint16 values in77,038 bytes of source text
(57,661 compressed payload bytes), expand to2,754,048 numeric bytes and reproduce the5,494,313-byte typed header
SHA `ce55cdcc72e0c0545e4f736d711b420fb3be07c72511e6ff4b142ad767b39274`.
They are **not used by normal guest preparation or runtime** in this PR.

```sh
python3 benchmarks/ucapreparedinput/check.py
python3 benchmarks/ucapreparedinput/check.py --emit-header /owned/temp/prepared.h
python3 benchmarks/ucapreparedinput/check.py --check-header /owned/temp/prepared.h
```

With the named experimental commit object available locally, verify exact
source correspondence without fetching or building:

```sh
python3 benchmarks/ucapreparedinput/verify_origin.py
```

This additional check compares against the original committed C-header hunk.
It requires a real commit object (not a tag object); shallow checkouts may need
an explicit fetch of the pinned source commit. It is separate from ordinary
packaging unit tests.

Default validation is read-only; output creation refuses an existing file.
Decoding is bounded to918,016 bytes per level. The manifest pins the compressed,
numeric and rendered-header hashes plus source/archive/Unicode input identities.
`--source-dir` optionally verifies the listed actual pristine source files and
Unicode input. Without it, output explicitly says source pins only. Neither mode
proves a fresh MariaDB derivation, guest correctness or product qualification.

Compression is a source-storage representation only: no runtime decoder or
product dependency is added. Gzip re-encoding across zlib versions need not have
identical container bytes; decompressed numeric/header hashes must be exact.
Do not edit numeric values or update their hashes without rerunning the original
pinned MariaDB generation and actual resolved-table comparison. The prototype
maintenance tools/inputs remain at their original immutable experimental commit.

See the [candidate review](../../docs/reviews/uca-prepared-candidate-review.md)
for production integration, verification separation and native-platform conditions.
The values derive from the existing MariaDB12.3.3 UCA14 input already used by the
guest; upstream input provenance is retained in input.json and the experiment.
