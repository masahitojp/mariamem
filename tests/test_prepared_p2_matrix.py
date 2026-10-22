"""Packet/oracle controls for the additional P2 native matrix."""
import copy
import importlib.util

from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
spec=importlib.util.spec_from_file_location('matrix',ROOT/'tests/v06_prepared_p2_matrix.py')
matrix=importlib.util.module_from_spec(spec);spec.loader.exec_module(matrix)


def test_ok_uint64_status_warnings_and_diagnostic_info():
    class Connection:
        def _execute_command(self,command,body):
            assert command==23 and body.hex()=='070000000001000000'
        def _read_packet(self,kind):
            # Fixed independent binary packet: maximum uint64 affected,
            # 2**53+1 insert ID, transaction status3, warnings2 and info text.
            return kind(bytes.fromhex('00fefffffffffffffffffe010000000000200003000200')+b'info', 'utf8')
    diagnostics=[]
    assert matrix.execute(Connection(),7,[],diagnostics)=={
        'kind':'ok','affected':18446744073709551615,'insert_id':9007199254740993,
        'status':3,'warnings':2}
    assert diagnostics[0]['ok_info_hex']=='696e666f'


def test_comparison_preserves_semantics_and_all_failure_evidence():
    baseline={'case':{'trace':[{'kind':'ok','affected':1,'insert_id':7,'status':2,'warnings':1}],
                      'healthy_following_query':True,'ok_observations':[{'ok_info_hex':'aa'}]}}
    expected=copy.deepcopy(matrix.comparable(baseline))
    assert 'ok_observations' not in expected['case']
    diagnostic=copy.deepcopy(baseline)
    diagnostic['case']['ok_observations']=[{'ok_info_hex':'bb'}]
    assert matrix.comparable(diagnostic)==expected
    for field,value in [('affected',2),('insert_id',8),('status',3),('warnings',0)]:
        changed=copy.deepcopy(baseline)
        changed['case']['trace'][0][field]=value
        assert matrix.comparable(changed)!=expected
    failed=copy.deepcopy(baseline)
    failed['case']['failure']={'type':'EOFError','error':'closed'}
    assert matrix.comparable(failed)!=expected
    unhealthy=copy.deepcopy(baseline)
    unhealthy['case']['healthy_following_query']=False
    assert matrix.comparable(unhealthy)!=expected


def test_statement_request_null_and_reused_descriptors():
    assert matrix.payload(1,[(3,False,None),(253,False,b'')]).hex()==(
        '01000000000100000001010300fd0000')
    assert matrix.payload(1,[(3,False,None),(253,False,b'')],True).hex()==(
        '010000000001000000010000')


def test_scenario_failure_keeps_trace_and_attempts_following_query(monkeypatch):
    class Connection:
        def __enter__(self):return self
        def __exit__(self,*args):return False
        def _execute_command(self,*args):pass
        def _read_packet(self,kind):return kind(bytes.fromhex('00010002000000'),'utf8')
    monkeypatch.setattr(matrix.pymysql,'connect',lambda **kwargs:Connection())
    seen=[]
    def query(connection,sql):
        seen.append(sql)
        return (('12.3.3-reference',),) if sql=='SELECT VERSION()' else ((1,),)
    monkeypatch.setattr(matrix,'query',query)
    def fail(connection,call):
        call(7)
        raise RuntimeError('after captured response')
    result=matrix.run_group({},fail)
    assert result['trace']==[dict(kind='ok',affected=1,insert_id=0,status=2,warnings=0)]
    assert result['failure']['error']=='after captured response'
    assert result['healthy_following_query'] and seen[-1]=='SELECT 1'


def test_terminal_db_failure_cannot_poison_later_scenario(monkeypatch):
    from types import SimpleNamespace
    started=[];closed=[]
    class DB:
        def __init__(self):self.number=len(started)+1;started.append(self.number)
        diagnostics=property(lambda self:{'host_pid':self.number})
        logs=property(lambda self:'original fatal logs' if self.number==1 else 'healthy logs')
        def connection_info(self):return {'generation':self.number}
        def close(self):closed.append(self.number)
    monkeypatch.setitem(sys.modules,'mariamem',SimpleNamespace(start=lambda **kwargs:DB()))
    monkeypatch.setattr(matrix,'scenarios',lambda:{'first':object(),'second':object()})
    def run_group(info,scenario):
        if info['generation']==1:
            return {'trace':[], 'ok_observations':[], 'failure':{'type':'OperationalError','error':'terminal DB failure'},'healthy_following_query':False}
        return {'trace':[{'kind':'rows'}], 'ok_observations':[], 'healthy_following_query':True}
    monkeypatch.setattr(matrix,'run_group',run_group)
    result=matrix.exercise(host='test-host')
    assert started==closed==[1,2]
    assert result['result']=='FAIL' and list(result['failures'])==['first']
    assert result['cases']['second']['healthy_following_query']
    assert result['host_diagnostics']['first']['logs']=='original fatal logs'
    assert result['host_diagnostics']['second']['runtime']['host_pid']==2


def test_scenario_teardown_failure_is_not_hidden(monkeypatch):
    from types import SimpleNamespace
    class DB:
        diagnostics={'host_pid':1}
        logs='close evidence'
        def connection_info(self):return {}
        def close(self):raise RuntimeError('failed teardown')
    monkeypatch.setitem(sys.modules,'mariamem',SimpleNamespace(start=lambda **kwargs:DB()))
    monkeypatch.setattr(matrix,'run_group',lambda *args:{'trace':[{'kind':'rows'}],'healthy_following_query':True})
    case,diagnostics=matrix.guest_case('test-host',object())
    assert case['trace']==[{'kind':'rows'}]
    assert case['failure']==case['lifecycle_failure']=={'type':'RuntimeError','error':'failed teardown'}
    assert diagnostics['logs']=='close evidence'
