"""Fast regressions for fail-closed guest reproducibility tooling."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'benchmarks/spikes/generated-go-integration'


def load_comparator():
    spec = importlib.util.spec_from_file_location('guest_comparator', TOOLS/'compare_guest_builds.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wasm(body=b'\x00\x0b'):
    # One empty function body; synthetic sections need not be executable.
    payload = b'\x01' + bytes([len(body)]) + body
    return b'\0asm\x01\0\0\0' + b'\x0a' + bytes([len(payload)]) + payload


def test_code_body_difference_is_not_metadata(tmp_path):
    compare = load_comparator()
    a, b = tmp_path/'a.wasm', tmp_path/'b.wasm'
    a.write_bytes(wasm())
    b.write_bytes(wasm(b'\x00\x01\x0b'))
    x, y = compare.sections(a), compare.sections(b)
    assert x[0]['id'] == y[0]['id'] == 10
    assert x[0]['function_bodies'] != y[0]['function_bodies']
    assert x[0]['sha256'] != y[0]['sha256']


def test_artifact_comparison_ignores_host_paths_not_contents(tmp_path):
    roots = [tmp_path/'left', tmp_path/'right']
    for work in roots:
        build = work/'source/build-legacy-no-postopt'
        build.mkdir(parents=True)
        (build/'unit.o').write_bytes(b'object')
        (build/'unit.a').write_bytes(b'archive')
        artifact = work/'artifact'
        artifact.mkdir()
        for name in ['link.txt', 'flags.make', 'CMakeCache.txt']:
            (artifact/name).write_text('same configuration')
        for name in ['mariamem-legacy-eh.wasm', 'mariamem-legacy-eh-O2-compatible.wasm']:
            (artifact/name).write_bytes(wasm())
    output = tmp_path/'comparison.json'
    argv = [sys.executable, str(TOOLS/'compare_guest_builds.py'), *map(str, roots), '--output', str(output)]
    subprocess.run(argv, check=True, capture_output=True)
    result = json.loads(output.read_text())
    assert result['differences']['objects'] == {}
    assert result['differences']['mariamem-legacy-eh.wasm'] == []
    (roots[1]/'source/build-legacy-no-postopt/unit.o').write_bytes(b'changed')
    subprocess.run(argv, check=True, capture_output=True)
    result = json.loads(output.read_text())
    assert list(result['differences']['objects']) == ['unit.o']


def test_toolchain_bootstrap_rejects_unpinned_inputs(tmp_path):
    bad = tmp_path/'bad'
    bad.write_bytes(b'not the pinned toolchain')
    output = tmp_path/'output'
    result = subprocess.run([sys.executable, str(TOOLS/'prepare_llvm23.py'), '--llvm-archive', str(bad), '--icu-package', str(bad), '--output', str(output)], capture_output=True, text=True)
    assert result.returncode == 2
    assert 'checksum mismatch' in result.stderr
    assert not output.exists()


def test_compiler_override_cannot_silently_change_accepted_input(tmp_path):
    output = tmp_path/'output'
    result = subprocess.run([sys.executable, str(TOOLS/'readiness_replay.py'), '--output', str(output), '--downloads', str(tmp_path), '--converter-archive', str(tmp_path/'missing'), '--llvm-dir', str(tmp_path)], capture_output=True, text=True)
    assert result.returncode == 2
    assert 'llvm override requires guest-build-only' in result.stderr
    assert not output.exists()


def test_explicit_manifest_cannot_bypass_generated_inventory(tmp_path):
    module = tmp_path/'module'
    (module/'generated/base').mkdir(parents=True)
    (module/'go.mod').write_text('module example.com/mariamem-spike\n\ngo 1.26.0\n')
    content = b'package base\n'
    (module/'generated/base/base.go').write_bytes(content)
    import hashlib
    manifest = tmp_path/'input.json'
    manifest.write_text(json.dumps({'guest_sha256':'0'*64, 'files_sha256':{'base/base.go':hashlib.sha256(content).hexdigest(), 'missing.go':'0'*64}}))
    output = tmp_path/'output'
    result = subprocess.run([sys.executable, str(TOOLS/'setup_audit.py'), '--source-module', str(module), '--output', str(output), '--input-manifest', str(manifest)], capture_output=True, text=True)
    assert result.returncode == 2
    assert 'inventory differs' in result.stderr
    assert not output.exists()
