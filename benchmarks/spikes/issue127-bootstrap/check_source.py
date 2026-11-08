#!/usr/bin/env python3
"""Check actual prepared entry exclusion and unchanged engine seams."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import shutil


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    repo = Path(__file__).resolve().parents[3]
    source = a.source.resolve()
    cmake = (source/'wasm/CMakeLists.txt').read_text()
    controller = (source/'wasm/issue65_control.cc').read_text()
    glue = (source/'wasm/lite4mariadb.c').read_text()
    assert 'COMPILE_DEFINITIONS "MARIAMEM_BOOTSTRAP_ONLY"' in cmake
    assert '--export=l4m_' not in cmake
    assert 'main=issue65_legacy_main' not in cmake
    assert 'mysql_stmt_' not in controller and 'MYSQL_BIND' not in controller
    assert '#include <mysql.h>' in controller  # thread init/end and COM_QUIT
    assert '#include "routine_bootstrap.inc"' not in controller
    assert '#include "prepared_auth_keys.inc"' in glue
    assert '#include "routine_bootstrap.inc"' in glue
    assert 'routine_bootstrap(g_mysql, restore)' in glue
    assert 'mariamem_spike_control_session' in controller
    # Compare complete live bootstrap and controller owner bodies with the
    # pre-candidate prepared files, not merely names or line counts.
    base_patch = subprocess.check_output(['git','show','a5ee1ed9cc2c6932d317fba77c339b364acd48df:guest/experimental.patch'], cwd=repo)
    current_patch = (repo/'guest/experimental.patch').read_bytes()
    assert current_patch.startswith(base_patch)
    scratch = tempfile.TemporaryDirectory()
    before = Path(scratch.name)/'wasm'
    before.mkdir()
    for name in ('lite4mariadb.c','issue65_control.cc','CMakeLists.txt'):
        shutil.copy2(source/'wasm'/name, before/name)
    subprocess.run(['patch','--batch','--fuzz=0','-R','-p1'],cwd=before.parent,input=current_patch[len(base_patch):],check=True,capture_output=True)
    old = (before/'lite4mariadb.c').read_text()
    def open_close(s):
        return s[s.index('int l4m_open(void)'):s.index('EMSCRIPTEN_KEEPALIVE\nvoid l4m_free')].replace('#ifndef MARIAMEM_BOOTSTRAP_ONLY\n', '')
    assert open_close(old) == open_close(glue)
    assert old[old.index('int issue65_bootstrap(void)'):] == glue[glue.index('int issue65_bootstrap(void)'):]
    old_control = (before/'issue65_control.cc').read_text()
    start = 'struct Manager'
    end = 'static MYSQL *connect()'
    assert old_control[old_control.index(start):old_control.index(end)] == controller[controller.index(start):controller.index('extern "C" int issue65_bootstrap')]
    fixed = ('guest/source.patch', 'guest/patches/12.3.3-prepared.patch', 'guest/input.json', 'scripts/prepare_guest.py')
    for name in fixed:
        expected = subprocess.check_output(['git','show','a5ee1ed9cc2c6932d317fba77c339b364acd48df:'+name], cwd=repo)
        assert hashlib.sha256(expected).hexdigest() == sha(repo/name), name
    result = {'result':'PASS source-only', 'source_files': {str(f.relative_to(source)):sha(f) for f in (source/'wasm/lite4mariadb.c', source/'wasm/issue65_control.cc', source/'wasm/CMakeLists.txt')}, 'canonical_inputs':{n:sha(repo/n) for n in fixed}, 'limits':['Not compilation/link/runtime evidence','Existing prepared patch and engine/internal conversion dependencies remain']}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
