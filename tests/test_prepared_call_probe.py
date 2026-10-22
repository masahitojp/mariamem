"""Native capture completeness and raw CALL reader error oracle."""
import json
from pathlib import Path
import struct
import pytest
import pymysql
from v06_prepared_call_probe import CallWireError, result_chain

ROOT=Path(__file__).resolve().parents[1]


def test_minimal_reference_has_two_results_out_and_terminal():
    ref=json.loads((ROOT/'tests/fixtures/prepared-call-native.json').read_text())
    assert ref['result']=='PASS' and ref['following_select']=='PASS' and ref['close_ping']=='PASS'
    parts=ref['results']
    assert len(parts)==4
    assert [len(p.get('columns',[])) for p in parts]==[1,2,1,0]
    assert [p['status'] for p in parts]==[10,10,4106,2]
    assert [p['rows'] for p in parts[:3]]==[['00000b000000'],['00001600000021000000'],['00002c000000']]
    assert parts[-1]['ok_packet']=='00000002000000'


@pytest.mark.parametrize('after_result',[False,True])
def test_raw_reader_preserves_error_and_does_not_read_past_it(after_result):
    error=b'\xff'+struct.pack('<H',1644)+b'#45000later failure'
    packets=([b'\x00\x00\x00\x0a\x00\x00\x00'] if after_result else [])+[error]
    class Connection:
        def _execute_command(self,op,payload):assert op==23
        def _read_packet(self,cls=pymysql.protocol.MysqlPacket):
            assert packets,'read past terminal error'
            return cls(packets.pop(0),'utf8')
    with pytest.raises(CallWireError) as caught:result_chain(Connection(),b'payload')
    assert caught.value.errno==1644 and caught.value.sqlstate=='45000'
    assert not packets
