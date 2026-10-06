"""Current guest input identity remains independent of retired runtime images."""
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import benchmark_artifacts as reuse
from common import ROOT

def inputs_tree(tmp_path):
    root = tmp_path / 'checkout'
    for name in (*reuse.RECIPE, 'release/inputs.lock.json'):
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    shutil.copytree(ROOT / 'guest', root / 'guest')
    return root


def test_guest_identity_ignores_harness_but_changes_for_patch_recipe_and_pins(tmp_path):
    root = inputs_tree(tmp_path)
    before = reuse.guest_inputs(root)
    (root / 'README.md').write_text('measurement-only change')
    assert reuse.guest_inputs(root) == before
    for name in ('guest/source.patch', 'guest/test-auth-keypair.json',
                 'scripts/prepare_guest.py', 'scripts/guest_auth_hooks.py',
                 'scripts/prepared_auth_keys.py', 'release/inputs.lock.json'):
        path = root / name
        original = path.read_bytes()
        if name == 'release/inputs.lock.json':
            changed = json.loads(original)
            changed['toolchain']['wasixcc'] = 'changed'
            path.write_text(json.dumps(changed))
        else:
            path.write_bytes(original + b'\nchange')
        assert reuse.guest_inputs(root) != before
        path.write_bytes(original)
    lock_path = root / 'release/inputs.lock.json'
    lock = json.loads(lock_path.read_text())
    lock['toolchain']['wasmer'] = 'runtime-only-change'
    lock_path.write_text(json.dumps(lock))
    assert reuse.guest_inputs(root) == before
    (root / 'guest/experimental.patch').write_text('temporary source change')
    assert reuse.guest_inputs(root) != before
