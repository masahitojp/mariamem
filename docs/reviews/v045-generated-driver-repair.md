# v0.4.5 generated driver repair

[Run 37967738446](https://github.com/masahitojp/mariamem/actions/runs/37967738446)
failed for `505f60a603355361e1fc8152acbd9dcb518b5144` on both platforms at
`verify_generated_runtime.py`: `generated source inventory changed; regenerate`.
Neither platform reached runtime integration. This was a source/provenance error,
not a SQL/isolation failure or a runner problem. Fail-closed behavior worked.
[Compact failed receipts and reproduction identities](v045-generated-driver-repair.json).

The diagnostic edit to `internal/generatedgo/main.go` omitted the deterministic
installer transformation and corresponding provenance. Although this driver is
host glue, it is an installer output, not an exempt handwritten file. The
checkpoint report now corrects that classification. Synthetic inventory tests
passed locally but did not exercise the actual edited repository inventory.

Repair:

- Move the existing driver normalization into `generate_runtime.adapt_driver` and
  make export attribution an explicit exact-fragment transformation there.
- Preserve the original pinned candidate driver input. Its fixture SHA256 is
  checked against the existing release input pin; unknown driver shapes fail.
- Reconstruct the original driver using the existing candidate recipe/template,
  format with Go1.26.8 and verify its pinned SHA256. Apply the actual installer
  transformation, format again and compare the whole driver byte-for-byte with
  the candidate. It matches; update only that generated inventory entry.
- Add a real-repository inventory assertion to the existing canonical inventory
  test suite, plus a pinned-driver/export-adaptation regression oracle. Python
  source checks keep working without Go/runtime prerequisites.

No input pin, guest, transpiled core, runtime semantics or guard is relaxed.
The generated driver itself is unchanged from the failed candidate. This narrow
source-adapter proof is not a fresh source-to-WASM regeneration claim; final
release reproduction remains a separate gate.

Focused generated inventory/inclusion/release/runtime-proof/version tests: 115
PASS. Actual generated inventory, public-source, version and diff checks PASS. Actual native runtime qualification is still required
for the diagnostic candidate because the failed run stopped before all Go and
integration checks. Use the same qualification workflow, without a new framework,
and retain previous successful evidence only under its actual tested identity.

Reproduce the narrow driver proof from this checkout (no guest build):

```sh
GOTOOLCHAIN=go1.26.8 PYTHONPATH=scripts python3 - <<'PY'
import hashlib, os, subprocess, tempfile
from pathlib import Path
from generate_runtime import adapt_driver, OLD, NEW
raw = Path('tests/fixtures/generated-driver.go.txt').read_text()
with tempfile.TemporaryDirectory() as directory:
    output = Path(directory)/'main.go'
    output.write_text(adapt_driver(raw.replace(OLD, NEW)))
    go_root = subprocess.check_output(['go', 'env', 'GOROOT'], text=True).strip()
    subprocess.run([str(Path(go_root)/'bin/gofmt'), '-w', str(output)], check=True)
    assert output.read_bytes() == Path('internal/generatedgo/main.go').read_bytes()
    print(hashlib.sha256(output.read_bytes()).hexdigest())
PY
python3 scripts/verify_generated_runtime.py
```
