"""Native ownership/failure tests; do not claim actual embedded API semantics."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]

@pytest.mark.parametrize("sanitize", [False, True], ids=["normal", "address-undefined-sanitizers"])
def test_dynamic_prepared_owner_and_failure_cleanup(tmp_path, sanitize):
    cc=shutil.which('clang') or shutil.which('cc')
    if not cc:
        if os.environ.get('MARIAMEM_REQUIRE_PREPARED_C')=='1':
            pytest.fail('native C compiler is required for this candidate gate')
        pytest.skip('native C compiler unavailable; actual guest build remains required')
    target=tmp_path/'prepared-owner'
    subprocess.run([cc,'-std=c11','-Wall','-Wextra','-Werror',
                    *(['-fsanitize=address,undefined','-fno-omit-frame-pointer'] if sanitize else []),
                    '-I',str(ROOT/'guest'),str(ROOT/'tests/fixtures/prepared_api_harness.c'),
                    '-o',str(target)],check=True,capture_output=True,text=True)
    result=subprocess.run([str(target)],check=True,capture_output=True,text=True)
    record=json.loads(result.stdout)
    assert record==dict(ownership='PASS',more_than_64_handles=True,failure_cleanup=True,
                        generation_rejection=True,live_handles=0,scope='mock API ownership only')

    vector=json.loads((ROOT/'tests/fixtures/prepared-envelope-v1.json').read_text())
    golden=subprocess.run([str(target),vector['hex']],check=True,capture_output=True,text=True)
    reply=json.loads(golden.stdout)
    assert reply['ok'] and reply['prepared_version']==1 and reply['session_generation']==vector['generation']
    assert reply['statement_id']==1 and reply['param_count']==1
