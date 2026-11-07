#!/usr/bin/env python3
"""Run actual public consumers and factory-disabled negative controls."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    w = args.workspace.resolve()
    out = w / "temp/public"
    product = out / "product"
    env = dict(os.environ, GOCACHE=str(w / "temp/gocache"), GOMODCACHE=str(w / "temp/gomodcache"),
               GOTOOLCHAIN="go1.26.10", CGO_ENABLED="0", GOMAXPROCS="2", GOGC="50", GOWORK="off", GOFLAGS="")
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    sys.path.insert(0, str(ROOT / "scripts"))
    from dev_guest import inventory
    from native_target import current_target, platform_fields
    receipt = json.loads((w / "evidence/public-source.json").read_text())
    assert receipt["source_inventory"] == inventory(product)
    def run(argv, name, cwd=product, environment=env, expected_fail=False):
        result = subprocess.run([str(x) for x in argv], cwd=cwd, env=environment, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
        (w / "evidence" / (name + ".txt")).write_text(result.stdout)
        if expected_fail:
            assert result.returncode != 0 and "native factory disabled" in result.stdout, result.stdout
        else:
            assert result.returncode == 0, result.stdout
        return result.stdout
    run([out / "public.test", "-test.v", "-test.run=^TestNativePublic", "-test.timeout=120s"], "public-go")
    # Package the exact tested host into an ordinary local wheel. No release
    # inputs, version, approval state or canonical guest manifest is edited.
    package = out / "python"
    shutil.copytree(product / "python", package)
    native = package / "mariamem/_native"
    native.mkdir(exist_ok=True)
    shutil.copy2(out / "mariamem-host", native / "mariamem-host")
    target = current_target(ROOT)
    version = {}
    exec((package / "mariamem/_version.py").read_text(), version)
    manifest = dict(version=1, package_version=version["PYTHON_VERSION"], **platform_fields(target),
                    runtime_kind="generated-go", guest_sha256=receipt["guest_sha256"], public_release_ready=False,
                    sha256={"mariamem-host": sha(out / "mariamem-host")})
    (native / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for name in ("LICENSE", "NOTICE", "THIRD_PARTY_LICENSES"):
        shutil.copy2(ROOT / name, package / name)
    shutil.copytree(ROOT / "licenses", package / "licenses", dirs_exist_ok=True)
    python = w / "temp/venv/bin/python"
    run([python, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--no-cache-dir",
         "--wheel-dir", out / "wheels", package], "public-wheel")
    wheel, = (out / "wheels").glob("*.whl")
    run([python, "-m", "pip", "install", "--no-deps", "--no-cache-dir", wheel], "public-wheel-install")
    external = out / "consumer"
    external.mkdir()
    shutil.copy2(HERE / "python_public.py", external / "consumer.py")
    pyenv = {k: v for k, v in env.items() if k != "PYTHONPATH"}
    run([python, "-I", external / "consumer.py"], "public-python", external, pyenv)
    # Overlay only the factory; identical generated runtime/guest/public fixture.
    disabled = '''package host
import("context";"errors";"io";"time";"github.com/masahitojp/mariamem/internal/snapshot")
func Start(context.Context,*snapshot.Owned,time.Duration,io.Writer)(Service,error){return nil,errors.New("native factory disabled")}
'''
    with tempfile.TemporaryDirectory(dir=w / "temp", prefix="factory-control-") as directory:
        control = Path(directory)
        replacement = control / "factory.go"
        replacement.write_text(disabled)
        overlay = control / "overlay.json"
        overlay.write_text(json.dumps({"Replace": {str(product / "internal/host/factory.go"): str(replacement)}}))
        run(["go", "test", "-c", "-p", "1", "-trimpath", "-buildvcs=false", "-overlay="+str(overlay),
             "-o", control / "public.test", "."], "public-factory-control-build")
        run([control / "public.test", "-test.v", "-test.run=^TestNativePublicGoRoutes$"],
            "public-go-factory-control", expected_fail=True)
        run(["go", "build", "-p", "1", "-trimpath", "-buildvcs=false", "-overlay="+str(overlay),
             "-o", control / "mariamem-host", "./cmd/mariamem-host"], "public-python-control-build")
        code = 'import mariamem; mariamem.start(host_binary='+repr(str(control / "mariamem-host"))+')'
        run([python, "-I", "-c", code], "public-python-factory-control", external, pyenv, expected_fail=True)
    assert receipt["source_inventory"] == inventory(product)
    (w / "evidence/public-result.json").write_text(json.dumps(dict(
        result="PASS scoped macOS public C2", host_source_commit=receipt["host_source_commit"],
        guest_sha256=receipt["guest_sha256"], source_receipt_sha256=sha(w / "evidence/public-source.json"),
        binary_receipt_sha256=sha(w / "evidence/public-binaries.json"), wheel_sha256=sha(wheel),
        public_go_tests=4, public_python="installed wheel default managed/control", factory_disabled_controls=2,
        legacy_wire_tripwire="present in all positive artifacts; no invocation",
        not_verified=["Linux public path", "full C3 Snapshot/Fork/Live/fault oracles", "all declared consumers", "performance", "canonical adoption", "release"]), indent=2) + "\n")


if __name__ == "__main__":
    main()
