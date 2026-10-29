"""Require semantic fault detection and a real external-module boundary."""
import json
from pathlib import Path
import shutil
import sys

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
import go_fixture_completion as completion
from consumer_module import source_files, source_identity


@pytest.mark.parametrize('kind', ['passed', 'build_error', 'wrong_test', 'wrong_reason', 'wrong_exit'])
def test_compile_errors_and_unrelated_failures_do_not_count_as_mutation_detection(kind):
    target, marker, code = 'TestOwner/fault', 'descriptor retained', 1
    text = json.dumps({'Action': 'fail', 'Test': target}) + '\n' + marker
    if kind == 'passed': code = 0
    elif kind == 'build_error': text = json.dumps({'Action': 'fail', 'Package': 'owner'}) + marker
    elif kind == 'wrong_test': text = json.dumps({'Action': 'fail', 'Test': 'TestOther'}) + marker
    elif kind == 'wrong_reason': text = json.dumps({'Action': 'fail', 'Test': target})
    elif kind == 'wrong_exit': code = 2
    with pytest.raises(ValueError): completion.semantic_failure(text, target, marker, code)


def test_mutations_have_one_current_anchor_and_a_named_oracle():
    for path, before, after, _, target, marker in completion.MUTATIONS.values():
        text = (REPO / path).read_text()
        assert completion.mutate(text, before, after) != text
        assert target and marker
    with pytest.raises(ValueError): completion.mutate('no anchor', 'missing', 'change')


@pytest.fixture
def root(tmp_path, monkeypatch):
    root = tmp_path / 'source'; root.mkdir()
    inputs = set(completion.INPUTS) | {r[0] for r in completion.MUTATIONS.values()}
    inputs |= {'go.mod', 'go.sum', 'LICENSE', 'release/inputs.lock.json'}
    for name in inputs:
        p = root / name; p.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(REPO / name, p)
    monkeypatch.setattr(completion, 'ROOT', root)
    return root


@pytest.mark.parametrize('mutation', ['none', 'replace', 'version', 'repository', 'changed', 'missing_helper', 'injected'])
def test_resolved_external_module_cannot_be_replaced_or_shadowed(root, tmp_path, mutation):
    installed = tmp_path / 'module'; shutil.copytree(root, installed)
    tag = 'v0.0.0-g1.' + source_identity(root)[:16]
    record = {'Path': completion.MODULE, 'Version': tag, 'Dir': str(installed)}
    if mutation == 'replace': record['Replace'] = {'Dir': str(root)}
    elif mutation == 'version': record['Version'] = 'v0.5.3'
    elif mutation == 'repository': record['Dir'] = str(root)
    elif mutation == 'changed': (installed / 'mariamemtest/fixture.go').write_text('changed')
    elif mutation == 'missing_helper': (installed / 'mariamemtest/fixture.go').unlink()
    elif mutation == 'injected': (installed / 'mariamemtest/injected.go').write_text('injected')
    if mutation == 'none': assert completion.verify_resolved(record, tag, root)
    else:
        with pytest.raises(ValueError): completion.verify_resolved(record, tag, root)


def populate(root, output):
    output.mkdir()
    expected = 'a' * 40
    inputs = {p: completion.digest(root / p) for p in completion.INPUTS}
    faults = {'result': 'PASS', 'physical_cases': sorted(completion.baseline_cases()), 'mutations': []}
    (output / 'physical.jsonl.txt').write_text(''.join(json.dumps({'Action': 'pass', 'Test': t}) + '\n'
                                                   for t in completion.baseline_cases()))
    for name, (path, before, after, _, target, marker) in completion.MUTATIONS.items():
        variant = completion.mutate((root / path).read_text(), before, after)
        faults['mutations'].append(dict(mutation=name, result='DETECTED', target=target, exit_code=1,
            overlay_sha256=__import__('hashlib').sha256(variant.encode()).hexdigest()))
        (output / (name + '.jsonl.txt')).write_text(json.dumps({'Action': 'fail', 'Test': target}) + '\n' + marker)
    consumer = dict(result='PASS', replace=False, outside_repository=True, temporary_cleanup='complete',
                    runtime_target=dict(goos='darwin',goarch='arm64'),
                    toolchain='go1.26.10', GOWORK='off', GOTOOLCHAIN='local', module_path=completion.MODULE,
                    private_module_version='v0.0.0-g1.'+source_identity(root)[:16], module_sum='h1:test',
                    module_files={p.relative_to(root).as_posix(): completion.digest(p) for p in source_files(root)},
                    runs=[dict(mode=mode, result='PASS', cases=list(completion.EXTERNAL_CASES)) for mode in ('normal','shuffle')])
    text = ''.join('--- PASS: ' + name + ' (0.01s)\n' for name in completion.EXTERNAL_CASES)
    text += json.dumps(dict(result='PASS_EXTERNAL_FIXTURE', prepares=1, goos='darwin',goarch='arm64')) + '\n'
    for mode in ('normal','shuffle'): (output / ('consumer-'+mode+'.txt')).write_text(text)
    report = dict(result='PASS', source_commit=expected, toolchain='go1.26.10', source_inventory_sha256=source_identity(root),
                  host=dict(system='Darwin',architecture='arm64',version='15.7'), fault_target=dict(goos='darwin',goarch='arm64'),
                  inputs_sha256=inputs, faults=faults, consumer=consumer)
    return report


def sums(output):
    completion.write(output / 'SHA256SUMS.json', {p.name: completion.digest(p) for p in output.iterdir()
                                               if p.is_file() and p.name != 'SHA256SUMS.json'})


@pytest.mark.parametrize('mutation', ['none', 'source', 'harness', 'census', 'mutation', 'compile_failure',
                                    'overlay', 'replaced', 'consumer_cases', 'missing_file', 'checksum', 'wrong_host', 'wrong_runtime'])
def test_completion_receipt_rejects_missing_or_wrong_evidence(root, tmp_path, mutation):
    output = tmp_path / 'evidence'; r = populate(root, output)
    if mutation == 'source': r['source_commit'] = 'b' * 40
    elif mutation == 'harness': r['inputs_sha256'] = {}
    elif mutation == 'census': r['faults']['physical_cases'] = []
    elif mutation == 'mutation': r['faults']['mutations'].pop()
    elif mutation == 'compile_failure':
        name = next(iter(completion.MUTATIONS)); (output / (name + '.jsonl.txt')).write_text('{"Action":"fail"}')
    elif mutation == 'overlay': r['faults']['mutations'][0]['overlay_sha256'] = 'wrong'
    elif mutation == 'replaced': r['consumer']['replace'] = True
    elif mutation == 'consumer_cases': r['consumer']['runs'][0]['cases'].pop()
    elif mutation == 'wrong_host': r['host']['architecture'] = 'x86_64'
    elif mutation == 'wrong_runtime': r['consumer']['runtime_target']['goarch'] = 'amd64'
    completion.write(output / 'result.json', r); sums(output)
    if mutation == 'missing_file': (output / 'consumer-normal.txt').unlink()
    elif mutation == 'checksum': (output / 'consumer-normal.txt').write_text('changed')
    if mutation == 'none': assert completion.validate(output, 'a' * 40, 'macos-15')['result'] == 'PASS'
    else:
        with pytest.raises((ValueError, FileNotFoundError)): completion.validate(output, 'a' * 40, 'macos-15')


def test_both_host_workflow_executes_and_requires_completion_receipts():
    text = (REPO / '.github/workflows/live-host.yml').read_text()
    assert '--output build/live-evidence/g1/completion' in text
    required = text.split('  required:\n', 1)[1]
    assert 'scripts/go_fixture_completion.py --expected-source-commit "$GITHUB_SHA" --validate-matrix build/g1-matrix' in required


def test_valid_linux_completion_cannot_substitute_for_mac(root, tmp_path):
    output = tmp_path / 'linux'; r = populate(root, output)
    r['host'] = dict(system='Linux',architecture='x86_64',version='24.04')
    r['fault_target'] = r['consumer']['runtime_target'] = dict(goos='linux',goarch='amd64')
    for mode in ('normal','shuffle'):
        p=output/('consumer-'+mode+'.txt')
        p.write_text(p.read_text().replace('darwin','linux').replace('arm64','amd64'))
    completion.write(output/'result.json',r);sums(output)
    assert completion.validate(output,'a'*40,'ubuntu-24.04')['result']=='PASS'
    with pytest.raises(ValueError,match='host mismatch'):
        completion.validate(output,'a'*40,'macos-15')
