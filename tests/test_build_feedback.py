"""Observer correctness and task env boundaries; no MariaDB guest required."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import build_feedback as feedback
import verify


def observed_env(tmp_path):
    return dict(os.environ, MARIAMEM_PHASE_TRACE=str(tmp_path/'trace.jsonl'))


def records(tmp_path):
    return [json.loads(line) for line in (tmp_path/'trace.jsonl').read_text().splitlines()]


def test_off_delegates_without_metadata_or_extra_commands(monkeypatch):
    monkeypatch.delenv(feedback.TRACE, raising=False)
    monkeypatch.setattr(feedback, '_context', lambda *a: pytest.fail('observer ran'))
    seen = []
    sentinel = object()
    monkeypatch.setattr(feedback.subprocess, 'run', lambda *a, **kw: seen.append((a,kw)) or sentinel)
    assert feedback.run(['cmd'], phase='off', check=True, timeout=7, text=True) is sentinel
    assert seen == [((['cmd'],), {'check':True, 'input':None, 'capture_output':False,
                                'timeout':7, 'text':True})]


def test_on_preserves_streams_input_resources_and_hashes(tmp_path):
    source, output = tmp_path/'input', tmp_path/'output'
    source.write_bytes(b'input')
    code = ('import sys,pathlib; print(sys.stdin.read()); print("stderr",file=sys.stderr); '
            'pathlib.Path(sys.argv[1]).write_bytes(b"output")')
    result = feedback.run([sys.executable, '-c', code, str(output)],
        env=observed_env(tmp_path), input='stdin', capture_output=True, text=True, check=True,
        phase='focused-python', inputs=[source], outputs=[output])
    assert result.stdout == 'stdin\n' and result.stderr == 'stderr\n'
    row, = records(tmp_path)
    assert row['returncode']==0 and row['wall_seconds']>0
    assert row['kind']=='diagnostic-not-qualification'
    assert row['inputs'][str(source)]['sha256']==hashlib.sha256(b'input').hexdigest()
    assert row['outputs'][str(output)]['sha256']==hashlib.sha256(b'output').hexdigest()
    if hasattr(os,'wait4'):
        assert row['resources']['status']=='Available'
        assert row['resources']['peak_rss_bytes']>0
        assert row['resources']['user_seconds']>=0 and row['resources']['system_seconds']>=0


def test_inherited_streams_not_redirected(tmp_path, capfd):
    feedback.run([sys.executable,'-c','print("out"); import sys; print("err",file=sys.stderr)'],
                 env=observed_env(tmp_path), check=True)
    out, err = capfd.readouterr()
    assert out == 'out\n' and err == 'err\n'


@pytest.mark.parametrize('checked', [False,True])
def test_nonzero_preserved_and_stale_output_not_claimed(tmp_path,checked):
    output=tmp_path/'stale'; output.write_bytes(b'old')
    argv=[sys.executable,'-c','import sys; print("failure"); sys.exit(17)']
    if checked:
        with pytest.raises(subprocess.CalledProcessError) as caught:
            feedback.run(argv,env=observed_env(tmp_path),check=True,capture_output=True,text=True,outputs=[output])
        assert caught.value.returncode==17 and caught.value.stdout=='failure\n'
    else:
        assert feedback.run(argv,env=observed_env(tmp_path),outputs=[output]).returncode==17
    row,=records(tmp_path)
    assert row['returncode']==17 and row['outputs']=={}


def test_timeout_keeps_partial_output_and_reaps_child(tmp_path):
    pid=tmp_path/'pid'
    code='import os,sys,time,pathlib; pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); print("partial",flush=True); time.sleep(30)'
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        feedback.run([sys.executable,'-c',code,str(pid)],env=observed_env(tmp_path),
                     capture_output=True,timeout=0.25)
    assert caught.value.stdout==b'partial\n'
    with pytest.raises(ProcessLookupError): os.kill(int(pid.read_text()),0)
    row,=records(tmp_path)
    assert row['exception']=='TimeoutExpired' and row['returncode']==-signal.SIGKILL


def test_signal_returncode_and_spawn_failure_preserved(tmp_path):
    code='import os,signal; os.kill(os.getpid(),signal.SIGTERM)'
    result=feedback.run([sys.executable,'-c',code],env=observed_env(tmp_path))
    assert result.returncode==-signal.SIGTERM
    with pytest.raises(FileNotFoundError):
        feedback.run([str(tmp_path/'missing')],env=observed_env(tmp_path))
    first,second=records(tmp_path)
    assert first['returncode']==-signal.SIGTERM
    assert second['exception']=='FileNotFoundError' and second['resources']['status']=='Unavailable'


def test_keyboard_interrupt_matches_standard_run_and_leaves_no_child(tmp_path):
    for enabled in (False,True):
        pid=tmp_path/('child-'+str(enabled))
        code='import os,pathlib,sys,time; pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)'
        driver=('import sys; sys.path.insert(0,sys.argv[1]); import build_feedback as f; '
                'f.run([sys.executable,"-c",sys.argv[2],sys.argv[3]])')
        env=dict(os.environ)
        env.pop(feedback.TRACE,None)
        if enabled:env=observed_env(tmp_path)
        process=subprocess.Popen([sys.executable,'-c',driver,str(ROOT/'scripts'),code,str(pid)],
                                 env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        try:
            deadline=time.monotonic()+5
            while not pid.exists() and process.poll() is None and time.monotonic()<deadline:
                time.sleep(0.01)
            assert pid.exists()
            os.killpg(process.pid,signal.SIGINT)
            process.communicate(timeout=5)
            assert process.returncode==-signal.SIGINT
            with pytest.raises(ProcessLookupError):os.kill(int(pid.read_text()),0)
        finally:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGKILL);process.communicate()
    row,=records(tmp_path)
    assert row['exception']=='KeyboardInterrupt'


def test_trace_write_failure_does_not_change_command(tmp_path,capfd):
    blocked=tmp_path/'blocked';blocked.mkdir()
    env=dict(os.environ,MARIAMEM_PHASE_TRACE=str(blocked))
    assert feedback.run([sys.executable,'-c','pass'],env=env).returncode==0
    assert 'phase observation unavailable' in capfd.readouterr().err


def test_resource_units_and_unavailability(monkeypatch):
    usage=SimpleNamespace(ru_utime=1,ru_stime=2,ru_maxrss=123)
    for system,multiplier in [('Darwin',1),('Linux',1024)]:
        monkeypatch.setattr(feedback.platform,'system',lambda:system)
        assert feedback._resources(usage)['peak_rss_bytes']==123*multiplier
    assert feedback._resources(None)['peak_rss_bytes'] is None
    monkeypatch.setattr(feedback.platform,'system',lambda:'unsupported')
    assert feedback._resources(usage)['status']=='Unavailable'


def test_no_wait4_falls_back_without_changing_result(tmp_path,monkeypatch):
    monkeypatch.delattr(os,'wait4')
    result=feedback.run([sys.executable,'-c','print("ok")'],env=observed_env(tmp_path),capture_output=True,text=True)
    assert result.stdout=='ok\n' and result.returncode==0
    assert records(tmp_path)[0]['resources']['status']=='Unavailable'


def owned_workspace(tmp_path):
    work=tmp_path/'task';root=work/'worktree';root.mkdir(parents=True)
    (work/'experiment.json').write_text(json.dumps({'owner':'mariamem-experiment-v1','state':'prepared'}))
    return work,root


def test_task_cache_explicit_consistent_and_default_unchanged(tmp_path,monkeypatch):
    monkeypatch.delenv(feedback.WORKSPACE,raising=False)
    assert feedback.go_environment({})=={} and feedback.go_environment(None) is None
    work,root=owned_workspace(tmp_path)
    base={feedback.WORKSPACE:str(work)}
    env=feedback.go_environment(base,root=root)
    assert env['GOTOOLCHAIN']=='go1.26.8'
    assert env['GOCACHE']==str(work/'temp/gocache')
    assert env['GOMODCACHE']==str(work/'temp/modcache')
    assert env['GOPATH']==str(work/'temp/gopath')
    assert feedback.go_environment(env,root=root)==env
    assert base=={feedback.WORKSPACE:str(work)}
    assert feedback.go_environment(dict(base,GOTOOLCHAIN='go1.27.1'),root=root)['GOTOOLCHAIN']=='go1.27.1'


@pytest.mark.parametrize('failure',['other-checkout','completed','conflict','symlink'])
def test_task_cache_rejects_unsafe_or_inactive_ownership(tmp_path,failure):
    work,root=owned_workspace(tmp_path);env={feedback.WORKSPACE:str(work)}
    if failure=='other-checkout':root=tmp_path
    if failure=='completed':
        (work/'experiment.json').write_text(json.dumps({'owner':'mariamem-experiment-v1','state':'completed'}))
    if failure=='conflict':env['GOCACHE']=str(tmp_path/'other-task')
    if failure=='symlink':
        (tmp_path/'other').mkdir();(work/'temp').symlink_to(tmp_path/'other')
    with pytest.raises(ValueError):feedback.go_environment(env,root=root)


def test_verify_routes_real_commands_and_tool_environment(tmp_path,monkeypatch):
    work,root=owned_workspace(tmp_path)
    monkeypatch.setattr(verify,'ROOT',root)
    monkeypatch.setattr(verify,'go_environment',lambda env=None:feedback.go_environment(env,root=root))
    monkeypatch.setenv(feedback.WORKSPACE,str(work))
    for name in ('GOCACHE','GOPATH','GOMODCACHE'):monkeypatch.delenv(name,raising=False)
    seen=[]
    monkeypatch.setattr(verify,'observed_run',lambda argv,**kw:seen.append((argv,kw)))
    verify.run(['go','build','-p','1','-o',str(tmp_path/'host'),'./cmd/mariamem-host'])
    argv,kw=seen[0]
    assert kw['env']['GOCACHE']==str(work/'temp/gocache')
    assert kw['outputs']==[str(tmp_path/'host')]
    assert kw['check'] and argv[-1]=='./cmd/mariamem-host'


def test_release_builder_still_rejects_single_pass(monkeypatch):
    import build_generated_guest as builder
    monkeypatch.setattr(builder.platform,'system',lambda:'Linux')
    monkeypatch.setattr(builder.platform,'machine',lambda:'aarch64')
    monkeypatch.setattr(builder.os,'geteuid',lambda:0)
    monkeypatch.setattr(sys,'argv',['build_generated_guest.py','--repetitions','1'])
    monkeypatch.setattr(builder,'download',lambda *a:pytest.fail('downloaded single-pass guest'))
    with pytest.raises(SystemExit) as caught:builder.main()
    assert caught.value.code==2


@pytest.mark.parametrize('failure',['dev-contract','single-pass','wrong-hash'])
def test_release_guard_rejects_unqualified_receipts(tmp_path,failure):
    import generated_release as release
    directory=tmp_path/'build/generated-release';directory.mkdir(parents=True)
    (directory/'mariamem.wasm').write_bytes(b'wasm')
    sha=hashlib.sha256(b'wasm').hexdigest();commit='a'*40
    guest={'contract':release.CONTRACT,'source_commit':commit,'guest_sha256':sha,
           'guest_bytes':4,'repetitions':[{'guest_sha256':sha,'linked_sha256':'b'*64}]}
    regen={'contract':release.CONTRACT,'source_commit':commit,'guest_sha256':sha}
    if failure=='dev-contract':guest['contract']='development-unqualified'
    if failure=='wrong-hash':guest['guest_sha256']='c'*64
    for name,data in [('guest.json',guest),('regeneration.json',regen)]:
        (directory/name).write_text(json.dumps(data))
    pins=tmp_path/'release';pins.mkdir()
    for name,data in [('generated-go-inputs.json',{'guest_sha256':sha}),
                      ('generated-go-toolchain.json',{}),
                      ('generated-go-build.json',{'guest_sha256':sha,'guest_size':4})]:
        (pins/name).write_text(json.dumps(data))
    reason={'dev-contract':'wrong build contract','single-pass':'independent rebuild',
            'wrong-hash':'guest identity differs'}[failure]
    with pytest.raises(ValueError,match=reason):release.verify_build(tmp_path,commit)
