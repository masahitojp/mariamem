# v0.4.4 release regeneration failure and scoped fix

[Release CI 37914496989](https://github.com/masahitojp/mariamem/actions/runs/37914496989)
qualified source `fc5811324c3cc72b277023d95550bbfd85d73935` and stopped before
wheel/consumer/publication jobs. The runtime reuse proof passed; two independent
source-to-WASM builds passed. The first failure was the generated-source equality
guard. Aggregate NOT READY was a consequence of missing upstream artifacts.

The canonical tree has 14 handwritten integration files outside transpilation
provenance. `generate_runtime.py` carried only 12 into a fresh regenerated tree;
`code/base/owned_prepared.go` and `code/base/owned_prepared_test.go` were omitted.
The fix adds those exact existing files to the copy list. Generated code, guest,
input pins, production runtime/API and corresponding-source checks are unchanged.

The regression exercises the real installer/copy path using a small synthetic
translation, derives required handwritten files from canonical provenance, and
requires all copied bytes to match. It does not invoke Go compilation or MariaDB.
The focused release check now includes this regression before expensive builds.

Runtime reuse does not blanket-exempt the generator. Its AST must differ from
the tested source only by this exact pair of copy-list additions; the rest of the
recipe, formatting/import transformations, compiler and provenance logic remain
identical. Missing/extra/duplicate additions and unrelated recipe changes are
rejected. Genuine later changes keep normal development checks; release reuse
still fails closed. The final regenerated-source equality guard remains intact.

Focused result: 195 pytest tests plus 6 Product tooling tests PASS; committed
transpilation identity, version/public-source and diff checks PASS. No broad
runtime acceptance or benchmarks were repeated. Existing macOS/Ubuntu runtime
basis remains `c5f43106a8054bb59a2da9184a1c2103fe1a1d9f`.

Full translation/reproduction after this fix is deliberately left to Release CI;
this report does not claim that later source/artifact/consumer gates passed.
No automatic redispatch is performed by the diagnosis task. See the
[compact failure receipt](v044-regeneration-failure.json).
