"""Manual resource-meter process/census controls; not product acceptance."""
import hashlib
import json
import os
from pathlib import Path
import platform
import select
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tests'))
from test_p1_resource_probe import probe

CHILD = '''
import json,os,sys
from pathlib import Path
fds=[]
print(json.dumps({'pid':os.getpid()}),flush=True)
for line in sys.stdin:
    if line.strip() in ('open','open_tiny'):
        path=Path(sys.argv[1])/'owned-file'
        fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600)
        if line.strip()=='open_tiny':
            os.write(fd,b'x')
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

def test_actual_tiny_child_allocation_matches_its_fstat(tmp_path,allocated_reader):
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
        owned=response('open_tiny')
        held,raw_held=probe.collect_allocated(process.pid,helper)
        assert owned['size']==1 and owned['blocks']*512 > owned['size'], 'fixed tiny control did not distinguish allocation from logical size'
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

SHARED_CHILD = '''
import json,os,subprocess,sys
from pathlib import Path
path=Path(sys.argv[1])/'shared-owned-file'
fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_RDWR,0o600)
os.write(fd,b'x');os.fsync(fd);os.unlink(path)
st=os.fstat(fd)
child=subprocess.Popen([sys.executable,'-u','-c',
    "import os,sys; os.fstat(int(sys.argv[1])); print('ready',flush=True); sys.stdin.readline()",str(fd)],
    pass_fds=(fd,),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
try:
    assert child.stdout.readline().strip()=='ready'
    print(json.dumps({'parent':os.getpid(),'child':child.pid,'device':st.st_dev,
                      'inode':st.st_ino,'blocks':st.st_blocks}),flush=True)
    sys.stdin.readline()
finally:
    child.stdin.write('close\\n');child.stdin.flush();child.stdin.close()
    child.wait(timeout=5);child.stdout.close();child.stderr.close();os.close(fd)
'''


def test_actual_shared_unlinked_allocation_is_counted_once(tmp_path,allocated_reader):
    helper,_=allocated_reader
    parent=subprocess.Popen([sys.executable,'-u','-c',SHARED_CHILD,str(tmp_path)],
                            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                            text=True,start_new_session=True)
    try:
        assert select.select([parent.stdout],[],[],10)[0], 'shared allocation readiness timeout'
        info=json.loads(parent.stdout.readline())
        assert info['parent']==parent.pid and info['child']>0 and info['blocks']>0
        observations={pid:probe.collect_allocated(pid,helper)[0] for pid in (parent.pid,info['child'])}
        combined=probe.merge_process_allocations(observations)
        for result in observations.values():
            assert len([f for f in result['unlinked_files'] if (f['device'],f['inode'])==
                        (info['device'],info['inode'])])==1
        matches=[f for f in combined['unlinked_files'] if (f['device'],f['inode'])==
                 (info['device'],info['inode'])]
        assert len(matches)==1 and matches[0]['allocated_bytes']==info['blocks']*512
    finally:
        if parent.poll() is None:
            parent.stdin.write('close\n');parent.stdin.flush()
        parent.stdin.close()
        try:parent.wait(timeout=10)
        except subprocess.TimeoutExpired:
            import signal
            os.killpg(parent.pid,signal.SIGKILL);parent.wait(timeout=5)
        parent.stdout.close();parent.stderr.close()
    assert parent.returncode==0
