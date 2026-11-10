"""Selected producer routing and fail-closed receipts; no compiler downloads.

Synthetic builds test orchestration only. The selected workflow performs the
actual independent preparation/build/translation before any binding review.
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import build_generated_guest as builder
import dev_guest as dev
from common import digest
from guest_preparation_context import resolve
import selected_guest as selected


@pytest.fixture
def inputs(tmp_path):
    root = tmp_path/'repo'
    shutil.copytree(ROOT/'guest', root/'guest')
    shutil.copytree(ROOT/'release', root/'release')
    resolved = resolve(ROOT, '13.2.0', 'native-text')
    for ref in resolved['files'].values():
        target = root/ref['file']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT/ref['file'], target)
    prepared = json.loads((ROOT/'docs/design/issue134-1320/evidence/prepared-source.json').read_text())
    # Synthetic producer fixture, not a rewrite of the historical receipt.
    # Real preparation equality is checked separately against its exact producer.
    prepared['guest_input'] = copy.deepcopy(resolved['guest_input'])
    prepared['resolved_input_sha256'] = hashlib.sha256(selected.encoded(resolved)).hexdigest()
    prepared['overlays']['input.json'] = hashlib.sha256(selected.encoded(resolved['guest_input'])).hexdigest()
    native = resolved['guest_input']['native_overlay']
    prepared['overlays']['experimental.patch'] = native['sha256']
    prepared['experimental_patch'] = {'file': native['file'], 'sha256': native['sha256']}
    prepared['native_glue'] = copy.deepcopy(resolved['guest_input']['native_glue'])
    # This is a synthetic receipt for the current staged inputs, not the
    # historical producer. Keep the verifier's actual postimage check intact.
    for destination, reference in prepared['native_glue'].items():
        prepared['modified_files'][destination] = digest(root/reference['file'])
    assert resolve(root, '13.2.0', 'native-text') == resolved
    selected.verify_preparation(resolved, prepared)
    return root, resolved, prepared


@pytest.fixture
def receipt(inputs, tmp_path, monkeypatch):
    root, resolved, prepared = inputs
    out = tmp_path/'guest'
    out.mkdir()
    (out/'mariamem.wasm').write_bytes(b'new-selected-guest')
    (out/'linked.wasm').write_bytes(b'new-selected-linked')
    (out/'flags.make').write_text('exact flags')
    identity = {'commit': 'a'*40, 'files_sha256': {'input': 'b'*64}}
    monkeypatch.setattr(dev, 'source_identity', lambda _: copy.deepcopy(identity))
    pins = json.loads((root/'release/generated-go-toolchain.json').read_text())
    record = {'contract': selected.CONTRACT, 'result': 'UNQUALIFIED',
              'source_commit': identity['commit'], 'source_identity': identity,
              'selected_inputs': resolved, 'prepared_source': prepared,
              'toolchain': {'pins_sha256': digest(root/'release/generated-go-toolchain.json'),
                            'archives_sha256': {k:v['sha256'] for k,v in pins['archives'].items()}},
              'source_builds': [{'trial': i, 'allocator_contract': 'PASS', 'prepared_source': prepared,
                                'prepared_tree': {'members': 32835, 'sha256': 'c'*64}} for i in range(2)],
              'guest_sha256': digest(out/'mariamem.wasm'), 'guest_bytes': (out/'mariamem.wasm').stat().st_size,
              'repetitions': [{'guest_sha256': digest(out/'mariamem.wasm'),
                               'linked_sha256': digest(out/'linked.wasm')} for _ in range(2)],
              'artifacts_sha256': dev.inventory(out)}
    dev.write(out/'guest.json', record)
    return root, out, record


def verify(root, out):
    return dev.verify_guest(root, out, engine='13.2.0', profile='native-text')


def test_selected_receipt_requires_caller_selection(receipt):
    root, out, record = receipt
    assert verify(root, out) == record
    with pytest.raises(ValueError, match='explicit expected'):
        dev.verify_guest(root, out)
    for engine, profile in [('13.0.2', 'native-text'), ('12.3.3', 'legacy-full')]:
        with pytest.raises(ValueError, match='version/profile/input'):
            dev.verify_guest(root, out, engine=engine, profile=profile)


@pytest.mark.parametrize('damage', ['schema', 'legacy-contract', 'resolved', 'origin', 'lock',
    'overlay', 'patch-order', 'native', 'selection', 'prepare-schema', 'eligible',
    'glue', 'glue-file', 'one-build', 'wrong-build', 'tree', 'allocator', 'wasm', 'linked', 'extra-file', 'flags'])
def test_selected_receipt_rejects_mixed_or_incomplete_build(receipt, damage):
    root, out, record = receipt
    prepared = record['prepared_source']
    if damage == 'schema': record['contract'] = 'selected-development-guest-v99'
    if damage == 'legacy-contract': record['contract'] = dev.CONTRACT
    if damage == 'resolved': record['selected_inputs']['resolved_sha256'] = 'f'*64
    if damage == 'origin': record['source_commit'] = 'b'*40
    if damage == 'lock': prepared['inputs_lock_sha256'] = digest(root/'release/inputs.lock.json')
    if damage == 'overlay': prepared['overlays']['source.patch'] = 'f'*64
    if damage == 'patch-order': prepared['portability_series'].reverse()
    if damage == 'native': prepared.pop('experimental_patch')
    if damage == 'glue': prepared.pop('native_glue')
    if damage == 'glue-file': prepared['modified_files'][next(iter(prepared['native_glue']))] = 'f'*64
    if damage == 'selection': prepared['selection'] = '13.0.2/native-text'
    if damage == 'prepare-schema': prepared['schema'] = 'unknown'
    if damage == 'eligible': prepared['release_eligible'] = True
    if damage == 'one-build': record['source_builds'].pop(); record['repetitions'].pop()
    if damage == 'wrong-build': record['repetitions'][1]['guest_sha256'] = 'f'*64
    if damage == 'tree': record['source_builds'][1]['prepared_tree']['sha256'] = 'f'*64
    if damage == 'allocator': record['source_builds'][1]['allocator_contract'] = 'SKIP'
    if damage == 'wasm': (out/'mariamem.wasm').write_bytes(b'old-guest')
    if damage == 'linked': (out/'linked.wasm').write_bytes(b'old-linked')
    if damage == 'extra-file': (out/'stale.json').write_text('{}')
    if damage == 'flags': (out/'flags.make').write_text('different flags')
    dev.write(out/'guest.json', record)
    with pytest.raises(ValueError): verify(root, out)


def test_unknown_or_selected_receipt_cannot_be_installed_without_binding(receipt, tmp_path):
    _, _, record = receipt
    with pytest.raises(ValueError, match='not dev installation'):
        dev.install_inputs(record, tmp_path)


def test_selected_producer_routes_each_fresh_source_and_rejects_fallback(inputs, tmp_path, monkeypatch):
    root, resolved, prepared = inputs
    work = tmp_path/'work'; work.mkdir()
    out = tmp_path/'out'; out.mkdir()
    calls = []
    def run(command, **kwargs):
        phase = kwargs['phase']; calls.append(phase)
        if phase.startswith('guest:prepare:'):
            args = list(map(str, command))
            assert args[args.index('--engine')+1] == '13.2.0'
            assert args[args.index('--profile')+1] == 'native-text'
            target = Path(args[args.index('--work-dir')+1])
            assert not target.exists()
            (target/'source').mkdir(parents=True)
            (target/'unpack').mkdir()
            (target/'source/new-engine').write_bytes(b'prepared selected source')
            pin = copy.deepcopy(prepared)
            from guest_native_glue import install
            for destination in resolved['guest_input']['native_glue']:
                (target/'source'/destination).parent.mkdir(parents=True, exist_ok=True)
            install(root, target/'source', resolved['guest_input'])
            pin['modified_files'] = {'new-engine': digest(target/'source/new-engine'),
                **{name: ref['sha256'] for name, ref in resolved['guest_input']['native_glue'].items()}}
            dev.write(target/'prepared-source.json', pin)
        elif phase.startswith('guest:allocator-contract:'):
            assert Path(command[command.index('--source')+1]).name == 'source'
        elif phase.startswith('guest:compile-link:'):
            assert not (work/'artifact').exists(), 'stale compiler output must not survive'
            assert (work/'source/new-engine').read_bytes() == b'prepared selected source'
            (work/'artifact').mkdir()
            for name in ('link.txt','flags.make','CMakeCache.txt','mariamem-legacy-eh.wasm'):
                (work/'artifact'/name).write_text(name)
        elif phase.startswith('guest:wasm-postopt:'):
            (work/'artifact/mariamem-legacy-eh-O2-compatible.wasm').write_bytes(b'new-guest')
        else: raise AssertionError(phase)
    monkeypatch.setattr(builder, 'observed_run', run)
    results, actual, builds = builder.build_sources(root, out, work, {}, {'versions': {}},
        repetitions=2, development=True, expected='unused canonical hash', selection=resolved)
    assert len(builds) == len(results) == 2
    assert calls == [f'guest:{stage}:{i}' for i in range(2) for stage in
                     ('prepare','allocator-contract','compile-link','wasm-postopt')]
    assert actual['selection'] == '13.2.0/native-text'
    assert not (root/'build/source').exists()
    assert not (root/'build/selected-source-0').exists()
    assert not (root/'build/selected-source-1').exists()
    def wrong_prepare(command, **kwargs):
        run(command, **kwargs)
        if kwargs['phase'].startswith('guest:prepare:'):
            args = list(map(str, command)); target=Path(args[args.index('--work-dir')+1])
            pin=json.loads((target/'prepared-source.json').read_text())
            pin['selection']='12.3.3/legacy-full'
            dev.write(target/'prepared-source.json',pin)
    monkeypatch.setattr(builder, 'observed_run', wrong_prepare)
    with pytest.raises(ValueError, match='input identity'):
        builder.build_sources(root, out, work, {}, {'versions': {}},
            repetitions=2, development=True, expected='unused', selection=resolved)
    assert not (work/'artifact').exists()


def test_tree_inventory_covers_modes_links_and_unlisted_files(tmp_path):
    (tmp_path/'file').write_text('data')
    original=selected.tree_identity(tmp_path)
    (tmp_path/'file').chmod(0o755)
    assert selected.tree_identity(tmp_path) != original
    (tmp_path/'link').symlink_to('file')
    linked=selected.tree_identity(tmp_path)
    (tmp_path/'link').unlink(); (tmp_path/'link').symlink_to('elsewhere')
    assert selected.tree_identity(tmp_path) != linked


def test_failed_translation_emits_no_binding_success(receipt, tmp_path, monkeypatch):
    root, guest, _ = receipt
    import build_feedback
    monkeypatch.setattr(builder, 'download', lambda *_: tmp_path/'converter')
    monkeypatch.setattr(build_feedback, 'go_environment', lambda env: env)
    def fail(*args, **kwargs): raise subprocess.CalledProcessError(23, args[0])
    monkeypatch.setattr(build_feedback, 'run', fail)
    out=tmp_path/'failed'
    with pytest.raises(subprocess.CalledProcessError):
        selected.translate_for_binding(root, guest, out, engine='13.2.0', profile='native-text')
    assert json.loads((out/'failure.json').read_text())['result']=='FAILED'
    assert not (out/'binding-inputs.json').exists()


def test_combined_budget_counts_sdk_and_builds(tmp_path):
    from selected_guest_ci import ProducerBudget
    from experiment_disk import DiskLimit
    a, b = tmp_path/'sdk', tmp_path/'build'
    a.mkdir(); b.mkdir()
    (a/'x').write_bytes(b'x'*8192)
    (b/'x').write_bytes(b'x'*8192)
    guard = ProducerBudget([a,b], 0.001, 12288/(1<<30))
    with pytest.raises(DiskLimit, match='combined'):
        guard.check()
    with pytest.raises(ValueError, match='overlapping'):
        ProducerBudget([a,a/'child'], 1, 1)


def test_selected_cli_rejects_single_build_before_download(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, 'argv', ['build_generated_guest.py', '--engine', '13.2.0',
        '--profile', 'native-text', '--development-output', str(tmp_path/'out'), '--repetitions', '1'])
    monkeypatch.setattr(builder.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(builder.platform, 'machine', lambda: 'aarch64')
    monkeypatch.setattr(builder.os, 'geteuid', lambda: 0)
    def forbidden(*args, **kwargs): pytest.fail('invalid input reached downloads')
    monkeypatch.setattr(builder, 'download', forbidden)
    with pytest.raises(SystemExit) as exc: builder.main()
    assert exc.value.code == 2


@pytest.mark.parametrize('wrong_guest', [False, True])
def test_default_formal_build_retains_canonical_hash_gate(tmp_path, monkeypatch, wrong_guest):
    root, work, out = (tmp_path/n for n in ('repo','work','out'))
    for path in (root, work, out): path.mkdir()
    def run(command, **kwargs):
        phase=kwargs['phase']
        if phase.startswith('guest:prepare:'):
            assert list(command)==[sys.executable,root/'scripts/prepare_guest.py']
            (root/'build/source').mkdir(parents=True)
            (root/'build/unpack').mkdir()
            dev.write(root/'build/prepared-source.json', {'canonical': True})
        elif phase.startswith('guest:compile-link:'):
            assert not (work/'artifact').exists()
            (work/'artifact').mkdir()
            for name in ('link.txt','flags.make','CMakeCache.txt','mariamem-legacy-eh.wasm'):
                (work/'artifact'/name).write_text(name)
        elif phase.startswith('guest:wasm-postopt:'):
            (work/'artifact/mariamem-legacy-eh-O2-compatible.wasm').write_bytes(b'canonical')
    monkeypatch.setattr(builder, 'observed_run', run)
    import hashlib
    expected='f'*64 if wrong_guest else hashlib.sha256(b'canonical').hexdigest()
    if wrong_guest:
        with pytest.raises(ValueError, match='canonical WASM differs'):
            builder.build_sources(root, out, work, {}, {'versions':{}}, repetitions=2,
                                  development=False, expected=expected)
        assert not (out/'mariamem.wasm').exists()
    else:
        results, prepared, builds=builder.build_sources(root, out, work, {}, {'versions':{}},
                                   repetitions=2, development=False, expected=expected)
        assert len(results)==2 and results[0]==results[1]
        assert prepared=={'canonical':True} and builds==[]
        assert not (out/'linked.wasm').exists()


@pytest.mark.parametrize('route', ['canonical', 'development', 'selected'])
def test_builder_entrypoint_keeps_sdk_and_artifact_inventories_distinct(inputs, tmp_path, monkeypatch, route):
    """Exercise main through SDK metadata and receipt emission with tiny tool fixtures.

    No network/compiler is used. The real inventory functions and selected
    receipt verifier run: a late local import must not shadow the SDK function.
    """
    import hashlib
    from types import SimpleNamespace
    import git_identity
    from install_guest_toolchain import inventory as sdk_inventory
    root, resolved, prepared = inputs
    sdk, work = tmp_path/'sdk', tmp_path/'work'
    output = tmp_path/'output'
    commit = 'a'*40
    identity = {'commit': commit, 'files_sha256': {'fixture': 'b'*64}}
    monkeypatch.setattr(builder, 'ROOT', root)
    monkeypatch.setattr(builder, 'PIN', root/'release/generated-go-toolchain.json')
    monkeypatch.setattr(builder, 'Path', lambda value: {'/work': work, '/root/.wasixcc': sdk}.get(str(value), Path(value)))
    monkeypatch.setattr(builder.platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(builder.platform, 'machine', lambda: 'aarch64')
    monkeypatch.setattr(builder.os, 'geteuid', lambda: 0)
    monkeypatch.setattr(git_identity, 'inspect_ref', lambda *_: SimpleNamespace(source_commit=commit))
    monkeypatch.setattr(git_identity, 'require_commit', lambda *_: None)
    monkeypatch.setattr(dev, 'source_identity', lambda _: copy.deepcopy(identity))
    def command_output(command, **kwargs):
        if '--show-current' in command: return 'experiment/test\n'
        if 'rev-parse' in command: return commit+'\n'
        return 'fixture tool version\n'
    monkeypatch.setattr(builder.subprocess, 'check_output', command_output)
    pins = json.loads(builder.PIN.read_text())
    for pin in pins['archives'].values():
        pin['sha256'] = hashlib.sha256(pin['file'].encode()).hexdigest()
    dev.write(builder.PIN, pins)
    def download(pin, directory):
        directory.mkdir(parents=True, exist_ok=True)
        target = directory/pin['file']; target.write_text(pin['file'])
        return target
    monkeypatch.setattr(builder, 'download', download)
    def extract(archive, target):
        target.mkdir(parents=True)
        if target.name.startswith('sysroot-'):
            variant = target.name.removesuffix('-unpack')
            libc = target/('wasix-'+variant)/'sysroot/lib/wasm32-wasi/libc.a'
            libc.parent.mkdir(parents=True); libc.write_bytes(b'fixture libc')
        elif target.name == 'binaryen-unpack':
            (target/'binaryen-fixture').mkdir()
    monkeypatch.setattr(builder, 'extract', extract)
    def tool_stage(command, **kwargs):
        if kwargs['phase'] == 'guest:llvm-prepare':
            (sdk/'llvm/LLVM-fixture').mkdir(parents=True)
    monkeypatch.setattr(builder, 'observed_run', tool_stage)
    def build_sources(root, out, work, env, tools, **kwargs):
        assert tools['sysroot'] == sdk_inventory(sdk/'sysroot')
        assert tools['sysroot']['entries'] == 2
        assert kwargs['repetitions'] == (1 if route == 'development' else 2)
        assert kwargs['selection'] == (resolved if route == 'selected' else None)
        (out/'mariamem.wasm').write_bytes(b'fixture guest')
        if route != 'canonical': (out/'linked.wasm').write_bytes(b'fixture linked')
        trial = {'guest_sha256': digest(out/'mariamem.wasm'),
                 'linked_sha256': hashlib.sha256(b'fixture linked').hexdigest()}
        builds = [{'trial': i, 'allocator_contract': 'PASS', 'prepared_source': prepared,
                   'prepared_tree': {'members': 1, 'sha256': 'c'*64}} for i in range(kwargs['repetitions'])]
        return [trial.copy() for _ in builds], prepared, builds
    monkeypatch.setattr(builder, 'build_sources', build_sources)
    argv = ['build_generated_guest.py']
    if route != 'canonical': argv += ['--development-output', str(output)]
    if route == 'selected': argv += ['--engine', '13.2.0', '--profile', 'native-text']
    monkeypatch.setattr(sys, 'argv', argv)
    builder.main()
    if route == 'canonical': output = root/'build/generated-release'
    record = json.loads((output/'guest.json').read_text())
    assert record['toolchain']['sysroot'] == sdk_inventory(sdk/'sysroot')
    if route == 'selected':
        assert record['artifacts_sha256'] == {name: digest(output/name) for name in ('mariamem.wasm','linked.wasm')}
        assert verify(root, output) == record
    else:
        assert 'artifacts_sha256' not in record
