"""Keep the fixed native LONG_DATA controls and error timing explicit."""
import copy
import hashlib
import json
from pathlib import Path
import struct

from v06_prepared_long_data_probe import CASES,comparable,streamed

ROOT=Path(__file__).resolve().parents[1]


def fixture():return json.loads((ROOT/'tests/fixtures/prepared-long-data-native.json').read_text())


def test_complete_native_inventory_and_healthy_following_queries():
    r=fixture();assert r['result']=='PASS' and not r['failures']
    assert set(r['cases'])==set(CASES) and len(CASES)==25
    for name,c in r['cases'].items():assert c['result']==c['following_query']==c['no_response_adjacency']=='PASS',name
    recipe=r['cases']['aggregate-over-1MiB']['stream_recipe']
    data=b'A\0B'*233333+b'Z'*700000+b'last'
    assert recipe['bytes_per_parameter']==len(data)>1<<20
    assert recipe['sha256']==hashlib.sha256(data).hexdigest()
    assert len(r['cases']['65-parameters-stream-index-64']['trace'][0][0]['columns'])==65


def test_deferred_native_error_lifetimes_are_not_weakened():
    cases=fixture()['cases']
    invalid=cases['invalid-index-deferred']['trace']
    assert [x[0]['errno'] for x in invalid[:3]]==[1210]*3 and 'rows' in invalid[3][0]
    overflow=cases['native-aggregate-overflow']['trace']
    assert [x[0]['errno'] for x in overflow[:2]]==[1105,1105] and 'rows' in overflow[2][0]
    for name in CASES:
        if name.startswith('wrong-'):
            assert cases[name]['trace'][0][0]['errno']==1210
            assert cases[name]['trace'][0][0]['sqlstate']=='HY000'
            assert cases[name]['trace'][1][0]['rows']==['0000017a']


def test_stream_request_omits_only_marked_inline_values_and_retains_bitmap():
    p=streamed(7,[252,3,252],{1:struct.pack('<i',23)},nulls=(2,))
    assert p==struct.pack('<IBI',7,0,1)+b'\x04\x01\xfc\x00\x03\x00\xfc\x00'+struct.pack('<i',23)
    assert streamed(7,[252],reuse=True)==struct.pack('<IBI',7,0,1)+b'\0\0'


def test_comparison_retains_packets_type_metadata_and_capacity_errors():
    c=fixture()['cases']['native-aggregate-overflow'];changed=copy.deepcopy(c)
    changed['trace'][0][0]['errno']=1153
    assert comparable(c)!=comparable(changed)
    changed=copy.deepcopy(c);changed['trace'][0][0]['error_packet']='00'
    assert comparable(c)!=comparable(changed)
    assert set(comparable(c))=={'prepare','trace','following_query','no_response_adjacency'}


def test_parameter_alias_difference_remains_a_hard_native_failure():
    original=fixture()['cases']['chunks-binary-mixed-parameters']
    changed=copy.deepcopy(original)
    packet=bytes.fromhex(changed['prepare'][0]['parameters'][0])
    # Native parameter name is the SQL alias "a"; replacing it by "?" was the
    # observed guest defect. Keep every other descriptor byte unchanged.
    needle=b'\x01a\x00\x0c'
    assert packet.count(needle)==1
    changed['prepare'][0]['parameters'][0]=packet.replace(needle,b'\x01?\x00\x0c').hex()
    assert comparable(original)!=comparable(changed)
