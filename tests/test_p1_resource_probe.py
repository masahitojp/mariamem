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
    if line.strip()=='open':
        path=Path(sys.argv[1])/'owned-file'
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600)
        os.write(fd,b'x'*1048576)
        os.fsync(fd)
        os.unlink(path)
        fds=[fd,os.dup(fd)]
        st=os.fstat(fd)
        print(json.dumps({'device':st.st_dev,'inode':st.st_ino,'size':st.st_size}),flush=True)
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
