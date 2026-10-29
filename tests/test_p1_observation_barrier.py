"""Cooperative barrier controls with real subprocesses; not guest evidence."""
import importlib.util
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/'tests/fixture_entry_acceptance/observation_barrier.py'
spec=importlib.util.spec_from_file_location('p1_observation_barrier',MODULE)
barrier=importlib.util.module_from_spec(spec);spec.loader.exec_module(barrier)

OWNER=r'''
import importlib.util,os,socket,sys,time
from pathlib import Path
spec=importlib.util.spec_from_file_location('barrier',sys.argv[1]);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
channel=socket.socket(fileno=int(sys.argv[2]));path=Path(sys.argv[3]);mode=sys.argv[4]
if mode=='exit':sys.exit(2)
if mode=='timeout':time.sleep(5);sys.exit(0)
if mode=='wrong':
    command=module._receive(channel,time.monotonic()+3)
    module._send(channel,{'action':'parked','token':'0'*32},time.monotonic()+3)
    time.sleep(1);sys.exit(0)
try:
    module.owner_checkpoint(channel,lambda:path.write_text('parked'),timeout_seconds=4)
except module.BarrierError:
    path.with_suffix('.aborted').write_text('abort');sys.exit(3)
path.write_text('released')
'''


def start_owner(tmp_path,name,mode='normal'):
    parent,child=socket.socketpair()
    path=tmp_path/name
    process=subprocess.Popen([sys.executable,'-c',OWNER,str(MODULE),str(child.fileno()),str(path),mode],
                             pass_fds=(child.fileno(),),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    child.close()
    return process,parent,path


def cleanup(owners):
    for process,channel,_ in owners:
        channel.close()
        if process.poll() is None:process.terminate()
    for process,_,_ in owners:
        try:process.communicate(timeout=3)
        except subprocess.TimeoutExpired:process.kill();process.communicate(timeout=3)


def test_real_processes_are_parked_until_observation_returns(tmp_path):
    owners=[start_owner(tmp_path,'one'),start_owner(tmp_path,'two')]
    try:
        def observe():
            assert all(path.read_text()=='parked' for _,_,path in owners)
            assert all(process.poll() is None for process,_,_ in owners)
            return 'observed'
        assert barrier.observe_parked({p:s for p,s,_ in owners},observe,timeout_seconds=3)=='observed'
        for process,_,path in owners:
            assert process.wait(timeout=3)==0
            assert path.read_text()=='released'
    finally:cleanup(owners)


@pytest.mark.parametrize('mode',['exit','timeout','wrong'])
def test_failed_owner_never_invokes_observation(tmp_path,mode):
    owners=[start_owner(tmp_path,'healthy'),start_owner(tmp_path,'bad',mode)]
    calls=[]
    try:
        with pytest.raises(barrier.BarrierError):
            barrier.observe_parked({p:s for p,s,_ in owners},lambda:calls.append('observe'),timeout_seconds=.5)
        assert not calls
        healthy=owners[0]
        assert healthy[0].wait(timeout=3)==3
        assert healthy[2].read_text()=='parked' and healthy[2].with_suffix('.aborted').exists()
    finally:cleanup(owners)


def test_failed_sampler_aborts_parked_owners_and_preserves_error(tmp_path):
    owners=[start_owner(tmp_path,'one'),start_owner(tmp_path,'two')]
    original=OSError('sample failure')
    def fail():raise original
    try:
        with pytest.raises(OSError) as caught:
            barrier.observe_parked({p:s for p,s,_ in owners},fail,timeout_seconds=3)
        assert caught.value is original
        for process,_,path in owners:
            assert process.wait(timeout=3)==3
            assert path.read_text()=='parked' and path.with_suffix('.aborted').exists()
    finally:cleanup(owners)


def test_sampling_deadline_exceeded_never_releases(tmp_path):
    owners=[start_owner(tmp_path,'one')]
    try:
        with pytest.raises(barrier.BarrierError,match='deadline'):
            barrier.observe_parked({p:s for p,s,_ in owners},lambda:time.sleep(.2),timeout_seconds=.15)
        assert owners[0][0].wait(timeout=3)==3
        assert owners[0][2].read_text()=='parked'
    finally:cleanup(owners)


def test_owner_exit_during_observation_aborts_peers(tmp_path):
    owners=[start_owner(tmp_path,'one'),start_owner(tmp_path,'two')]
    def observe():
        owners[1][0].terminate()
        owners[1][0].wait(timeout=3)
        return 'must not be returned'
    try:
        with pytest.raises(barrier.BarrierError,match='exited during sampling'):
            barrier.observe_parked({p:s for p,s,_ in owners},observe,timeout_seconds=3)
        assert owners[0][0].wait(timeout=3)==3
        assert owners[0][2].read_text()=='parked' and owners[0][2].with_suffix('.aborted').exists()
    finally:cleanup(owners)


@pytest.mark.parametrize('timeout',[0,-1,float('inf'),float('nan'),True])
def test_nonfinite_or_invalid_timeout_is_rejected(tmp_path,timeout):
    owners=[start_owner(tmp_path,'one')]
    try:
        with pytest.raises(ValueError,match='finite positive'):
            barrier.observe_parked({p:s for p,s,_ in owners},lambda:None,timeout_seconds=timeout)
        assert not owners[0][2].exists()
    finally:cleanup(owners)


def test_required_hosts_run_cooperative_barrier_controls():
    workflow=(ROOT/'.github/workflows/live-host.yml').read_text()
    step=workflow.split('- name: P1 real prepared command and callback on both Python minors',1)[1].split('- name:',1)[0]
    assert 'for py in "$PY311" "$PY314"' in step
    assert 'tests/test_p1_observation_barrier.py' in step
