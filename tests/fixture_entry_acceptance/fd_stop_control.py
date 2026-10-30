"""Bounded real-guest FD stop control, not the full resource campaign."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import xml.etree.ElementTree as ET


HOOK = r'''
import importlib.util as _fd_import, resource as _fd_resource
_fd_spec=_fd_import.spec_from_file_location('p1_guard',os.environ['P1_GUARD_PATH'])
_fd_guard=_fd_import.module_from_spec(_fd_spec);_fd_spec.loader.exec_module(_fd_guard)
_fd_spec=_fd_import.spec_from_file_location('p1_probe',os.environ['P1_PROBE_PATH'])
_fd_probe=_fd_import.module_from_spec(_fd_spec);_fd_spec.loader.exec_module(_fd_probe)
_fd_original_limit=None
@pytest.hookimpl(hookwrapper=True,specname='pytest_fixture_setup')
def pytest_fd_fixture_setup(fixturedef,request):
    outcome=yield
    if outcome.excinfo is not None or fixturedef.argname!='mariamem_snapshot':return
    saved=outcome.get_result();original=saved.fork;calls=0
    def guarded_fork():
        nonlocal calls
        global _fd_original_limit
        calls+=1
        observed,_=_fd_probe.collect({os.getpid()})
        count=observed['fd_total']
        soft,hard=_fd_resource.getrlimit(_fd_resource.RLIMIT_NOFILE)
        if calls==2:
            _fd_original_limit=(soft,hard)
            # The real worker limit is lowered, not an invented FD count.
            # 63 remaining descriptors is safely below the required 64.
            target=count+63
            if soft != _fd_resource.RLIM_INFINITY:target=min(target,soft)
            _fd_resource.setrlimit(_fd_resource.RLIMIT_NOFILE,(target,hard))
            soft,hard=_fd_resource.getrlimit(_fd_resource.RLIMIT_NOFILE)
        if soft==_fd_resource.RLIM_INFINITY:soft=2**62
        record({'event':'fd_observation','call':calls,'count':count,'soft':soft})
        # Only FD is observed in this bounded control. Other values are fixed
        # neutral test inputs and are not resource-campaign observations.
        sample=dict(process_tree_rss_bytes=1,available_memory_bytes=1,linked_allocated_bytes=0,
                    unlinked_allocated_bytes=0,disk_free_bytes=1,active_children=0,
                    physical_connections=0,fd_by_process={str(os.getpid()):dict(count=count,soft_limit=soft)})
        limits=dict(incremental_rss_ceiling_bytes=1,owned_disk_ceiling_bytes=1,
                    min_free_disk_bytes=0,min_fd_headroom=64,active_children_ceiling=2,
                    physical_connections_ceiling=4)
        def child():
            record({'event':'fork_invoked','call':calls})
            return original()
        if os.environ.get('P1_TEST_BYPASS_GUARD')=='1':return child()
        return _fd_guard.admit(lambda:sample,limits,1,child)
    saved.fork=guarded_fork
@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):
    if _fd_original_limit is not None:
        _fd_resource.setrlimit(_fd_resource.RLIMIT_NOFILE,_fd_original_limit)
'''

CASES = '''
from pathlib import Path
def test_first(mariamem_fork):
    assert mariamem_fork.status()['active_connections']==0
    Path('first-body').touch()
def test_blocked(mariamem_fork):
    Path('blocked-body').touch()
def test_after(mariamem_fork):
    Path('after-body').touch()
'''


def run(root, output, host, source, installed, base_conf, *, bypass_guard=False):
    output.mkdir(); project=output/'consumer';project.mkdir()
    (project/'conftest.py').write_text(base_conf+HOOK)
    (project/'test_fd_stop.py').write_text(CASES)
    events=output/'owners.jsonl'
    env={k:v for k,v in os.environ.items() if not k.startswith(('PYTEST_','PYTHON','MARIAMEM_','MYSQLMEM_'))}
    if not installed:env['PYTHONPATH']=str(root/'python')
    env.update(PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               MARIAMEM_TEST_HOST=str(Path(host).absolute()),P1_METHOD='command',
               P1_COMMAND_SCRIPT=str(root/'tests/fixture_entry_acceptance/p1_migrate.py'),
               P1_MIGRATION_SOURCE=str(root/'tests/preparation_migration_acceptance/migrations'),
               P1_GUARD_PATH=str(root/'tests/fixture_entry_acceptance/resource_guard.py'),
               P1_PROBE_PATH=str(root/'tests/fixture_entry_acceptance/resource_probe.py'),
               P1_EVENT_FILE=str(events),P1_TEST_BYPASS_GUARD='1' if bypass_guard else '0')
    argv=[sys.executable,'-m','pytest','-p','mariamem.pytest_plugin','test_fd_stop.py',
          '-q','--tb=short','--junitxml='+str(output/'results.xml')]
    process=subprocess.Popen(argv,cwd=project,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    try:stdout,stderr=process.communicate(timeout=180)
    except BaseException:
        for sig in (signal.SIGTERM,signal.SIGKILL):
            try:os.killpg(process.pid,sig)
            except ProcessLookupError:pass
            try:process.communicate(timeout=5);break
            except subprocess.TimeoutExpired:continue
        raise
    (output/'stdout.txt').write_bytes(stdout);(output/'stderr.txt').write_bytes(stderr)
    output_text=stdout.decode(errors='replace')+'\n'+stderr.decode(errors='replace')
    suites=ET.parse(output/'results.xml').getroot().findall('.//testsuite')
    counts={k:sum(int(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
    assert events.exists(), 'no owner events; inspect original pytest output:\n'+output_text
    rows=[json.loads(line) for line in events.read_text().splitlines()]
    observations=[r for r in rows if r.get('event')=='fd_observation']
    forks=[r for r in rows if r.get('event')=='fork_invoked']
    final=[r for r in rows if r.get('event')=='final']
    assert process.returncode==1 and counts==dict(tests=3,failures=0,errors=2,skipped=0),output_text
    assert 'FD headroom guard; admission stopped' in output_text and 'dependent admission stopped' in output_text
    assert (project/'first-body').exists() and not (project/'blocked-body').exists() and not (project/'after-body').exists()
    assert len(observations)==2 and observations[0]['soft']-observations[0]['count']>=64
    assert observations[1]['soft']-observations[1]['count']<64
    assert len(forks)==1 and forks[0]['call']==1
    assert sum(r.get('event')=='close' and r.get('kind')=='mariamem_fork' for r in rows)==1
    assert sum(r.get('event')=='close' and r.get('kind')=='mariamem_snapshot' for r in rows)==1
    assert sum(r.get('event')=='close' and r.get('kind')=='mariamem_server' for r in rows)==1
    assert len(final)==1 and all(final[0][k] is True for k in ('closed','host_reaped','directory_removed'))
    result=dict(result='PASS_BOUNDED_REAL_GUEST_FD_STOP',source_commit=source,installed_wheel=installed,
                counts=counts,fd_observations=observations,final_owner=final[0],
                scope='Actual pytest and guest; real worker FD limit and lsof FD count only; other resource counters are synthetic.',
                remaining='Full P1 resource/retention and physical-connection campaign; production admission guard not implied.')
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
