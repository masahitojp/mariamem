"""Full P3 scenario inventory and terminal-error reader oracle."""
import json
from pathlib import Path
import struct
import pytest
import pymysql
from v06_prepared_call_probe import result_chain
from v06_prepared_p3_matrix import specifications, request, comparable

ROOT=Path(__file__).resolve().parents[1]


def test_full_matrix_has_complete_pinned_native_controls():
    r=json.loads((ROOT/'tests/fixtures/prepared-p3-native.json').read_text())
    assert r['result']=='PASS' and not r['failures']
    assert set(r['cases'])==set(specifications()) and len(r['cases'])==14
    for name,c in r['cases'].items():
        assert c['result']==c['following_query']==c['close_ping']=='PASS'
        assert [len(parts) for parts in c['trace']]==specifications()[name]['counts']
    assert len(r['cases']['129-results']['trace'][0])==130
    for name in ('no-PS-flag-OUT','no-PS-flag-multiple'):
        c=r['cases'][name]
        assert not c['advertisement']['client_PS_MULTI_RESULTS']
        assert all(not p.get('status',0)&4096 for p in c['trace'][0])
    assert 'error_packet' in r['cases']['later-error']['trace'][0][-1]
    before,after=r['cases']['metadata-change']['trace']
    assert len(before[0]['columns'])==2 and len(after[0]['columns'])==3


@pytest.mark.parametrize('prefix',[False,True])
def test_expected_terminal_sql_error_preserves_complete_prefix(prefix):
    packet=b'\xff'+struct.pack('<H',1644)+b'#45000P3 later error'
    pending=([b'\x00\x00\x00\x0a\x00\x00\x00'] if prefix else [])+[packet]
    class Connection:
        def _execute_command(self,op,payload):assert op==23
        def _read_packet(self,cls=pymysql.protocol.MysqlPacket):
            assert pending,'read past terminal SQL error'
            return cls(pending.pop(0),'utf8')
    result=result_chain(Connection(),b'request',allow_error=True)
    assert len(result)==(2 if prefix else 1)
    assert result[-1]=={'error_packet':packet.hex(),'errno':1644,'sqlstate':'45000'}
    assert not pending


def test_reuse_preserves_bitmap_and_values_without_repeating_descriptors():
    first=request(7,[2,None,5]);again=request(7,[3,None,9],reuse=True)
    assert first[:9]==again[:9]==struct.pack('<IBI',7,0,1)
    assert first[9:11]==b'\x02\x01' and again[9:11]==b'\x02\x00'
    assert first[11:17]==b'\x03\x00'*3
    assert again[11:]==struct.pack('<ii',3,9)


def test_comparison_keeps_errors_metadata_status_and_following_query():
    case=json.loads((ROOT/'tests/fixtures/prepared-p3-native.json').read_text())['cases']['later-error']
    assert comparable(case)['trace'][-1][-1]['sqlstate']=='45000'
    assert set(comparable(case))=={'prepare','trace','following_query','close_ping'}
