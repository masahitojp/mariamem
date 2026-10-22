"""Real source-function before/after order oracle, not a guest PASS."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('version,wasi,expected',[
    ('before',True,0),('after',True,8),('after',False,0)])
@pytest.mark.parametrize('sanitize',[False,True])
def test_extracted_parameter_descriptor_order(tmp_path,version,wasi,expected,sanitize):
    cc=shutil.which('clang++') or shutil.which('c++')
    if not cc:
        if os.environ.get('MARIAMEM_REQUIRE_PREPARED_C')=='1':pytest.fail('C++ compiler required')
        pytest.skip('C++ compiler unavailable')
    fixture=json.loads((ROOT/'tests/fixtures/prepared-param-order-functions.json').read_text())
    (tmp_path/'param-functions.inc').write_text('\n\n'.join(fixture[version].values())+'\n')
    binary=tmp_path/'param-order'
    command=[cc,'-std=c++17','-Wall','-Wextra','-Werror','-Wno-unused-parameter']
    if wasi:command+=['-D__wasi__']
    if sanitize:command+=['-fsanitize=address,undefined','-fno-omit-frame-pointer']
    subprocess.run(command+['-I',str(tmp_path),str(ROOT/'tests/fixtures/prepared_param_order_harness.cc'),'-o',str(binary)],check=True,capture_output=True,text=True)
    result=json.loads(subprocess.check_output([str(binary)],text=True))
    print(json.dumps(dict(version=version,wasi=wasi,sanitizers=sanitize,result=result)))
    assert result['matching_descriptors']==expected


def test_common_type_native_controls_have_complete_oracles():
    import v06_prepared_unsigned_probe as probe
    native=json.loads((ROOT/'tests/fixtures/prepared-unsigned-native.json').read_text())
    assert set(probe.scenarios())==set(native['cases']) and len(native['cases'])==2
    assert native['result']=='PASS'
    assert all(case['healthy_following_query'] and len(case['trace'])==12 for case in native['cases'].values())
