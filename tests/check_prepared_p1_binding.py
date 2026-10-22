"""Check the exact reviewed prepared binding against newly installed development Go.

Not a substitute for P6's full closure and forced-schedule J1 failure oracle.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import runtime_thread_lifetime as binding


def check_memory_initialization(runtime, identity):
    pin=identity['memory_init']
    body=binding.function((runtime/pin['file']).read_text(),pin['function'])
    normalize=lambda text:re.sub(r'\s+','',text)
    assert hashlib.sha256(normalize(body).encode()).hexdigest()==pin['normalized_sha256'],'memory initialization changed'
    fixture=(ROOT/'tests/fixtures/prepared-p2-binding/memory-init.txt').read_text()
    assert normalize(body)==normalize(fixture),'memory initialization fixture changed'


def check(runtime):
    identity=json.loads((ROOT/'tests/fixtures/prepared-p2-binding/identity.json').read_text())
    provenance=json.loads((runtime/'provenance.json').read_text())
    assert provenance['guest_sha256']==identity['guest_sha256']==binding.GUEST_SHA256
    generated=(runtime/'code/generated.go').read_text()
    literal=re.search(r'var wasm2goData_data_bin = \[\]byte\("((?:\\x[0-9a-f]{2})+)"\)',generated)
    assert literal,'installed guest data literal missing'
    data=bytes.fromhex(literal[1].replace('\\x',''))
    assert hashlib.sha256(data).hexdigest()==identity['data_sha256']
    segments=identity['data_segments']
    declaration='m.DataSegs = [][]byte{'+', '.join(f'wasm2goData_data_bin[{s["start"]}:{s["end"]}]' for s in segments)+'}'
    assert declaration in generated,'reviewed passive segment ranges changed'
    tls=segments[2]
    assert tls['end']-tls['start']==identity['tls_bytes']==505
    assert hashlib.sha256(data[tls['start']:tls['end']]).hexdigest()==identity['tls_sha256']
    check_memory_initialization(runtime,identity)
    for name,(function,expected) in binding.FUNCTIONS.items():
        body=binding.function((runtime/name).read_text(),function)
        if function=='Fn153':
            hook='\tif base.DeferThreadAllocationFree(m, l0) {\n\t\treturn\n\t}\n'
            assert body.count(hook)==1,'missing/changed installer handoff'
            body=body.replace(hook,'',1)
        digest=hashlib.sha256(re.sub(r'\s+','',body).encode()).hexdigest()
        assert digest==expected==identity['functions'][name]['normalized_sha256']
        fixture=(ROOT/'tests/fixtures/prepared-p2-binding'/(function+'.txt')).read_text()
        assert re.sub(r'\s+','',body)==re.sub(r'\s+','',fixture)
    print('PASS: installed prepared functions match the reviewed exact preimages and handoff')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--runtime',type=Path,required=True)
    check(p.parse_args().runtime)
