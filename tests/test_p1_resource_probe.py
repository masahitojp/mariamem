"""OS-counter controls before the expensive full P1 campaign."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import platform
import select
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('p1_resource_probe', ROOT/'tests/fixture_entry_acceptance/resource_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

VALID = b'p123\0\nf3\0tREG\0D0x1\0i42\0k0\0s8192\0\nf4\0tREG\0D0x1\0i42\0k0\0s8192\0\n'


def test_duplicate_descriptors_do_not_duplicate_unlinked_file_bytes():
    result = probe.parse_lsof(VALID, {123})
    assert result['fd_total'] == 2
    assert result['fd_backed_unlinked_logical_bytes'] == 8192
    assert len(result['unlinked_files']) == 1


@pytest.mark.parametrize('raw,pids', [
    (b'', {123}), (VALID[:-2], {123}), (VALID, {123,456}),
    (VALID.replace(b'k0\0', b''), {123}),
    (VALID.replace(b's8192\0', b's-1\0'), {123}),
    (VALID.replace(b'f4\0', b'f3\0'), {123}),
    (VALID.replace(b's8192\0', b's4096\0', 1), {123}),
    (VALID.replace(b'tREG\0', b''), {123}),
])
def test_missing_partial_or_unstable_counters_are_not_zero(raw, pids):
    with pytest.raises(ValueError):
        probe.parse_lsof(raw, pids)


def test_tool_warning_is_not_partial_success(monkeypatch):
    monkeypatch.setattr(probe.shutil, 'which', lambda _: '/tool/lsof')
    monkeypatch.setattr(probe.subprocess, 'run', lambda *a, **kw:
                        subprocess.CompletedProcess(a, 0, VALID, b'permission denied'))
    with pytest.raises(RuntimeError, match='UNVERIFIED'):
        probe.collect({123})


CHILD = '''
import json,os,sys
from pathlib import Path
fds=[]
print(json.dumps({'pid':os.getpid()}),flush=True)
for line in sys.stdin:
    if line.strip() in ('open','open_sparse'):
        path=Path(sys.argv[1])/'owned-file'
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600)
        if line.strip()=='open_sparse':
            os.ftruncate(fd,4*1048576)
            os.write(fd,b'x'*4096)
        else:
            os.write(fd,b'x'*1048576)
        os.fsync(fd)
        os.unlink(path)
        fds=[fd,os.dup(fd)]
        st=os.fstat(fd)
        print(json.dumps({'device':st.st_dev,'inode':st.st_ino,'size':st.st_size,'blocks':st.st_blocks}),flush=True)
    elif line.strip()=='close':
        for fd in fds: os.close(fd)
        fds=[]
        print('{}',flush=True)
    else: break
for fd in fds: os.close(fd)
'''


def test_actual_child_fd_and_unlinked_file_census(tmp_path):
    process = subprocess.Popen([sys.executable,'-c',CHILD,str(tmp_path)],
                               stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                               text=True,start_new_session=True)
    def response(command=None):
        if command:
            process.stdin.write(command+'\n'); process.stdin.flush()
        assert select.select([process.stdout],[],[],10)[0], 'probe child readiness timeout'
        value = process.stdout.readline()
        assert value, 'probe child exited before readiness'
        return json.loads(value)
    try:
        assert response()['pid'] == process.pid
        baseline, raw_before = probe.collect({process.pid})
        owned = response('open')
        held, raw_held = probe.collect({process.pid})
        assert held['fd_total'] == baseline['fd_total'] + 2
        assert held['fd_backed_unlinked_logical_bytes'] == baseline['fd_backed_unlinked_logical_bytes'] + owned['size']
        matches = [f for f in held['unlinked_files'] if f['device']==owned['device'] and f['inode']==owned['inode']]
        assert len(matches)==1 and matches[0]['logical_bytes']==1048576
        response('close')
        final, raw_final = probe.collect({process.pid})
        assert final['fd_total']==baseline['fd_total']
        assert final['unlinked_files']==baseline['unlinked_files']
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=5)
        process.stdout.close(); process.stderr.close()
    assert process.returncode == 0
    receipt = dict(result='PASS_COUNTER_FEASIBILITY_ONLY',python=sys.version,platform=platform.platform(),
                   source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                   source_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),
                   code_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in [Path(__file__),ROOT/'tests/fixture_entry_acceptance/resource_probe.py']},
                   baseline=baseline,held=held,final=final,owned=owned,child_reaped=True,
                   excluded='No P1 workload, RSS/available-memory, retained baselines, physical connections, timing or guard acceptance')
    directory = Path(os.environ.get('P1_RESOURCE_EVIDENCE', str(tmp_path/'evidence')))
    directory.mkdir(parents=True,exist_ok=False)
    for name, raw in [('baseline',raw_before),('held',raw_held),('final',raw_final)]:
        (directory/(name+'.lsof')).write_bytes(raw)
    (directory/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


def test_workflow_keeps_actual_probe_on_both_host_minor_cells():
    text=(ROOT/'.github/workflows/live-host.yml').read_text()
    segment=text.split('- name: P1 real prepared command and callback on both Python minors',1)[1].split('- name:',1)[0]
    assert 'for py in "$PY311" "$PY314"' in segment
    assert 'tests/test_p1_resource_probe.py' in segment
    assert 'P1_RESOURCE_EVIDENCE="$PWD/build/live-evidence/p1-resource-py$version"' in segment
    assert 'P1 resource observer tool availability' in text


def allocation_data():
    return dict(pid=123,fd_count=2,fds=[dict(fd=fd,regular=True,device=1,inode=42,
                links=0,blocks=8,logical_bytes=4*1048576) for fd in (3,4)])


def test_allocation_is_blocks_not_logical_size_and_is_deduplicated():
    result=probe.summarize_allocated(allocation_data(),123)
    assert result['fd_count']==2 and result['unlinked_allocated_bytes']==4096
    assert result['unlinked_files']==[dict(device=1,inode=42,allocated_bytes=4096,logical_bytes=4*1048576)]


@pytest.mark.parametrize('mutation', ['pid','count','duplicate_fd','missing_blocks','negative_blocks',
                                    'unknown_regular','missing_links','changing_file'])
def test_unverified_allocation_cannot_be_admitted(mutation):
    data=allocation_data()
    if mutation=='pid': data['pid']=456
    elif mutation=='count': data['fd_count']=3
    elif mutation=='duplicate_fd': data['fds'][1]['fd']=3
    elif mutation=='missing_blocks': del data['fds'][0]['blocks']
    elif mutation=='negative_blocks': data['fds'][0]['blocks']=-1
    elif mutation=='unknown_regular': del data['fds'][0]['regular']
    elif mutation=='missing_links': del data['fds'][0]['links']
    else: data['fds'][1]['blocks']=16
    with pytest.raises(ValueError,match='UNVERIFIED'):
        probe.summarize_allocated(data,123)


@pytest.fixture(scope='session')
def allocated_reader(tmp_path_factory):
    if sys.platform=='linux':
        return None, dict(method='Linux procfs stat',kernel=platform.release())
    assert sys.platform=='darwin', 'allocation probe requires Darwin or Linux'
    # Native compilation must follow a checked clean commit identity.
    sys.path.insert(0,str(ROOT/'scripts'))
    from git_identity import require_commit
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    require_commit(ROOT,source)
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip(), 'commit allocation-probe input before native compilation'
    code=ROOT/'tests/fixture_entry_acceptance/fd_allocated_darwin.c'
    directory=tmp_path_factory.mktemp('allocated-native')
    helper=directory/'fd-allocated'
    sdk=Path(subprocess.check_output(['xcrun','--show-sdk-path'],text=True,timeout=10).strip())
    command=['xcrun','clang','-std=c11','-Wall','-Wextra','-Werror','-O2','-isysroot',str(sdk),str(code),'-lproc','-o',str(helper)]
    subprocess.run(command,capture_output=True,text=True,check=True,timeout=30)
    return helper, dict(method='Darwin SDK libproc helper',source_commit=source,
        source_sha256=hashlib.sha256(code.read_bytes()).hexdigest(),
        binary_sha256=hashlib.sha256(helper.read_bytes()).hexdigest(),
        compiler=subprocess.check_output(['xcrun','clang','--version'],text=True,timeout=10).splitlines()[0],
        sdk_version=subprocess.check_output(['xcrun','--show-sdk-version'],text=True,timeout=10).strip(),
        headers_sha256={name:hashlib.sha256((sdk/'usr/include'/name).read_bytes()).hexdigest()
                        for name in ['libproc.h','sys/proc_info.h']})


def test_actual_sparse_child_allocation_matches_its_fstat(tmp_path,allocated_reader):
    helper,build=allocated_reader
    process=subprocess.Popen([sys.executable,'-c',CHILD,str(tmp_path)],stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    def response(command=None):
        if command:
            process.stdin.write(command+'\n');process.stdin.flush()
        assert select.select([process.stdout],[],[],10)[0], 'allocation child readiness timeout'
        line=process.stdout.readline();assert line, 'allocation child exited before readiness'
        return json.loads(line)
    try:
        assert response()['pid']==process.pid
        baseline,raw_before=probe.collect_allocated(process.pid,helper)
        owned=response('open_sparse')
        held,raw_held=probe.collect_allocated(process.pid,helper)
        assert 0 < owned['blocks']*512 < owned['size'], 'fixed sparse control did not distinguish allocation from logical size'
        assert held['fd_count']==baseline['fd_count']+2
        assert held['unlinked_allocated_bytes']==baseline['unlinked_allocated_bytes']+owned['blocks']*512
        matches=[f for f in held['unlinked_files'] if (f['device'],f['inode'])==(owned['device'],owned['inode'])]
        assert len(matches)==1 and matches[0]['allocated_bytes']==owned['blocks']*512
        response('close')
        final,raw_final=probe.collect_allocated(process.pid,helper)
        assert final['fd_count']==baseline['fd_count'] and final['unlinked_files']==baseline['unlinked_files']
    finally:
        process.stdin.close()
        try:process.wait(timeout=5)
        except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
        process.stdout.close();process.stderr.close()
    assert process.returncode==0
    base=Path(os.environ.get('P1_RESOURCE_EVIDENCE',str(tmp_path/'evidence')))
    base.mkdir(parents=True,exist_ok=True);directory=base/'allocated';directory.mkdir()
    receipt=dict(result='PASS_ALLOCATED_COUNTER_FEASIBILITY_ONLY',python=sys.version,platform=platform.platform(),
                 source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                 source_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)),
                 build=build,baseline=baseline,held=held,final=final,owned=owned,child_reaped=True,
                 code_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
                              [Path(__file__),ROOT/'tests/fixture_entry_acceptance/resource_probe.py',ROOT/'tests/fixture_entry_acceptance/fd_allocated_darwin.c']},
                 excluded='Not a P1 workload, process-tree census, RSS/mmap, retained-baseline, timing or admission-guard acceptance')
    for name,raw in [('baseline',raw_before),('held',raw_held),('final',raw_final)]:
        (directory/(name+'.json')).write_bytes(raw)
    (directory/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
