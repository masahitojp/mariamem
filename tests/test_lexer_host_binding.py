"""Single-guest dev binding is exact, opt-in, and leaves canonical guards intact."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import runtime_development_binding as binding
import runtime_thread_lifetime as canonical
import dev_guest


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT/file)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def test_exact_profile_and_canonical_binding_remain_separate():
    old = canonical.GUEST_SHA256
    p = binding.profile(ROOT, binding.NAME)
    thread, crc = binding.adapters(ROOT, binding.NAME, p['guest_sha256'])
    assert canonical.GUEST_SHA256 == old != thread.GUEST_SHA256
    assert crc.TABLE_OFFSET == 7180928
    for path, (name, _) in thread.FUNCTIONS.items():
        body = (ROOT/'benchmarks/lexerbinding/ci-42433100335/functions'/(name+'.go.txt')).read_text()
        thread.apply(path, body)
        if name != 'Fn131':
            with pytest.raises(ValueError): canonical.apply(path, body)
    with pytest.raises(ValueError): binding.adapters(ROOT, binding.NAME, old)
    with pytest.raises(ValueError): binding.profile(ROOT, 'unknown')


def test_full_translation_and_origin_must_match():
    p = binding.profile(ROOT, binding.NAME)
    guest = {'source_identity':{'commit':p['source_commit']},'guest_sha256':p['guest_sha256']}
    raw = {'files_sha256':p['raw_files_sha256']}
    binding.verify_raw(ROOT,binding.NAME,guest,raw)
    for change in ('origin','guest','missing','extra','hash'):
        g, r = copy.deepcopy(guest), copy.deepcopy(raw)
        if change == 'origin': g['source_identity']['commit'] = 'f'*40
        elif change == 'guest': g['guest_sha256'] = 'f'*64
        elif change == 'missing': r['files_sha256'].pop(next(iter(r['files_sha256'])))
        elif change == 'extra': r['files_sha256']['extra.go'] = 'f'*64
        else: r['files_sha256']['data.bin'] = 'f'*64
        with pytest.raises(ValueError): binding.verify_raw(ROOT,binding.NAME,g,r)


def test_profile_adapter_and_layout_mutations_are_rejected(tmp_path):
    files = ['benchmarks/lexerhost/binding.json','benchmarks/lexerhost/worker-layout.json',
             'scripts/runtime_thread_lifetime.py','scripts/runtime_crc32c.py']
    for name in files:
        target = tmp_path/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((ROOT/name).read_bytes())
    binding.profile(tmp_path, binding.NAME)
    for name in files:
        path = tmp_path/name; original = path.read_bytes(); path.write_bytes(original+b' ')
        with pytest.raises(ValueError): binding.profile(tmp_path, binding.NAME)
        path.write_bytes(original)


@pytest.mark.parametrize('file', ['guest/experimental.patch','scripts/build_generated_guest.py',
    'benchmarks/lexercandidate/c_source.py','benchmarks/lexerhost/not-reviewed.py'])
def test_guest_reuse_rejects_changes_outside_named_host_stage(tmp_path, file):
    root = tmp_path/'repo';root.mkdir()
    def git(*args): return subprocess.check_output(['git',*args],cwd=root,text=True).strip()
    git('init','-q');git('config','user.name','Test');git('config','user.email','test@example.invalid')
    path = root/file;path.parent.mkdir(parents=True);path.write_text('old')
    git('add','.');git('commit','-qm','origin');origin = dev_guest.source_identity(root)
    path.write_text('new');git('add','.');git('commit','-qm','changed')
    with pytest.raises(ValueError, match='fresh guest build'): dev_guest.verify_source_origin(root,origin)


def test_archive_mismatch_and_traversal_fail_before_extraction(tmp_path):
    acquire = module('lexer_acquire','benchmarks/lexerhost/acquire.py')
    path = tmp_path/'bad.zip'
    with zipfile.ZipFile(path,'w') as archive: archive.writestr('../escape','bad')
    with pytest.raises(ValueError, match='digest'): acquire.extract(path,tmp_path/'out','0'*64)
    with pytest.raises(ValueError, match='unsafe'): acquire.extract(path,tmp_path/'out',hashlib.sha256(path.read_bytes()).hexdigest())
    assert not (tmp_path/'escape').exists()


def test_crc_overlay_only_relocates_exact_test_tokens():
    run = module('lexer_host_run','benchmarks/lexerhost/run.py')
    assert run.crc_test('15555072 155550720 x15555072',{ '15555072':15569536 }) == '15569536 155550720 x15555072'


def test_binding_cli_cannot_enter_canonical_route(tmp_path):
    for script, args in [('regenerate_release_guest.py',[]),('generate_runtime.py',['--source-module',str(tmp_path)])]:
        result = subprocess.run([sys.executable,str(ROOT/'scripts'/script),'--development-binding',binding.NAME,*args],capture_output=True,text=True)
        assert result.returncode == 2 and 'requires' in result.stderr
