# Prepared UCA numeric source input

These three explicitly formatted JSON text inputs re-express the exact numeric tables from experiment
`e33fc6ce3bae390c6dda0fd92d024d8094df8731`. They store gzip/base64-encoded uint16 values in77,038 bytes of source text
(57,661 compressed payload bytes), expand to2,754,048 numeric bytes and reproduce the5,494,313-byte typed header
SHA `ce55cdcc72e0c0545e4f736d711b420fb3be07c72511e6ff4b142ad767b39274`.
`scripts/prepare_guest.py` validates the pristine source and expands this input before applying the canonical guest patch. The runtime reads typed immutable C data; it does not decode JSON or gzip.

The committed candidate guest uses these tables. Independent source/Go regeneration and both-host acceptance are pending; this input check alone does not prove them.

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
proves a fresh MariaDB derivation, guest correctness or product qualification. Source preparation records the five input hashes and emitted header hash in `uca_prepared` provenance.

Compression is a source-storage representation only: no runtime decoder or
product dependency is added. Gzip re-encoding across zlib versions need not have
identical container bytes; decompressed numeric/header hashes must be exact.
Do not edit numeric values or update their hashes without rerunning the original
pinned MariaDB generation and actual resolved-table comparison. The prototype
maintenance tools/inputs remain at their original immutable experimental commit.

See the [candidate review](../../docs/reviews/uca-prepared-candidate-review.md)
for verification separation and native-platform conditions. The private `MARIAMEM_UCA_VERIFY_INTERNAL` trigger is supplied only by package-local tests; normal timing never enables it.
The values derive from the existing MariaDB12.3.3 UCA14 input already used by the
guest; upstream input provenance is retained in input.json and the experiment.

`validation.json` preserves the input-only preparation result from d7fa5537;
its old scope text is historical and is not a current guest/platform PASS.
Current implementation evidence is in the canonical candidate checkpoint.
