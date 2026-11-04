"""Release native compiler controls for the prepared source repair."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]

@pytest.mark.parametrize('version,wasi,expected', [
    ('before', True, (0, False)),
    ('after', True, (7, True)),
    ('after', False, (0, False)),
])
@pytest.mark.parametrize('sanitize', [False, True])
def test_real_source_functions(tmp_path, version, wasi, expected, sanitize):
    cc = shutil.which('clang') or shutil.which('cc')
    if not cc:
        if os.environ.get('MARIAMEM_REQUIRE_PREPARED_C') == '1':
            pytest.fail('C compiler required')
        pytest.skip('C compiler unavailable')
    fixture = json.loads((ROOT / 'tests/fixtures/prepared-p2-source-functions.json').read_text())
    (tmp_path / 'functions.inc').write_text('\n\n'.join(fixture[version].values())+'\n')
    binary = tmp_path / 'source-proof'
    command = [cc, '-std=c11', '-Wall', '-Wextra', '-Werror', '-DEMBEDDED_LIBRARY']
    if wasi:
        command += ['-D__wasi__']
    if sanitize:
        command += ['-fsanitize=address,undefined', '-fno-omit-frame-pointer']
    subprocess.run(command + ['-I', str(tmp_path), str(ROOT / 'tests/fixtures/prepared_p2_source_harness.c'),
                              '-o', str(binary)], check=True, capture_output=True, text=True)
    result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
    record = json.loads(result.stdout)
    print(json.dumps(dict(version=version,wasi=wasi,sanitizers=sanitize,result=record)))
    assert (record['accepted_types'], record['metadata_refreshed']) == expected
