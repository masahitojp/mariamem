"""Generate and verify static-image metadata against the selected installed tree."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = 'image/layout.json'


def source_hashes(runtime):
    return {'internal/generatedgo/'+p.relative_to(runtime).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((runtime/'code').rglob('*'))
            if p.is_file() and p.suffix in ('.go', '.s') and not p.name.endswith('_test.go')}


def verify_sources(runtime):
    value = json.loads((runtime/LAYOUT).read_text())
    if value.get('source_sha256') != source_hashes(runtime):
        raise ValueError('static image layout source drift; regenerate selected runtime image/layout.json')


def generate(runtime, go):
    """Compile the selected output, never the old checkout's generated code.

    A disposable module supplies the canonical import paths without modifying the
    output's provenance or importing its host adapter. Only constructor bytes run.
    """
    runtime = Path(runtime).resolve()
    with tempfile.TemporaryDirectory(prefix='mariamem-image-layout-') as temporary:
        root = Path(temporary)
        staged = root/'internal/generatedgo'
        staged.mkdir(parents=True)
        for name in ('code', 'imagelayout', 'layoutgen'):
            shutil.copytree(runtime/name, staged/name)
        # Base ownership/types depend on these handwritten host helpers only.
        for name in ('prepared', 'timing'):
            shutil.copytree(ROOT/'internal'/name, root/'internal'/name)
        (root/'go.mod').write_text('module github.com/masahitojp/mariamem\n\ngo 1.26.0\n')
        env = dict(os.environ, GOTOOLCHAIN='local', GOENV='off', GOWORK='off', GOFLAGS='', GOEXPERIMENT='', CGO_ENABLED='0')
        subprocess.run([str(go), 'run', '-p', '1', './internal/generatedgo/layoutgen',
                        '-root', str(root), '-output', str(runtime/LAYOUT)],
                       cwd=root, env=env, check=True)
    verify_sources(runtime)
