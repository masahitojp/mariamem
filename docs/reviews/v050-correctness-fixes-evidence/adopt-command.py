"""Explicit adoption of measured fixed input through existing canonical adapters.

Run from the A-D checkout after its canonical two-build guest receipt completes.
Independent verification remains regenerate_release_guest.py, not this adoption.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

root = Path.cwd().resolve()
task = root.parent
sys.path.insert(0, str(root / 'scripts'))
from build_generated_guest import download
from common import digest

guest = task / 'temp/builder-build/generated-release'
partial = '--adopt-source-only' in sys.argv
record = (json.loads((guest / 'guest.json').read_text()) if not partial else None)
source_commit = (record['source_commit'] if record else
    subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip())
pins_file = root / 'release/generated-go-inputs.json'
pins = json.loads(pins_file.read_text())
if record:
    assert record['contract'] == 'generated-go-v1'
    assert len(record['repetitions']) == 2 and record['repetitions'][0] == record['repetitions'][1]
    assert record['guest_sha256'] == pins['guest_sha256']
assert pins['guest_sha256'] == digest(guest / 'mariamem.wasm')
tools = json.loads((root / 'release/generated-go-toolchain.json').read_text())
archive = download(tools['archives']['converter'], root / 'build/downloads')
env = dict(os.environ, GOTOOLCHAIN='go1.26.8', GOMAXPROCS='2',
           MARIAMEM_DEV_WORKSPACE=str(task),
           MARIAMEM_PHASE_TRACE=str(task / 'evidence/native-phases.jsonl'))
for key in ('GOCACHE', 'GOPATH', 'GOMODCACHE'):
    env[key] = str(task / 'temp' / {'GOCACHE':'gocache', 'GOPATH':'gopath', 'GOMODCACHE':'modcache'}[key])
spike = root / 'benchmarks/spikes/generated-go-integration'
out = task / 'temp/adoption-3'
out.mkdir()
def run(*args):
    subprocess.run([sys.executable, *map(str, args)], cwd=root, env=env, check=True)
run(spike / 'translate_guest.py', '--guest', guest / 'mariamem.wasm',
    '--guest-sha256', pins['guest_sha256'], '--converter-archive', archive,
    '--output', out / 'translation')
raw = json.loads((out / 'translation/input-manifest.json').read_text())
(root / 'release/generated-go-translation.json').write_text(json.dumps(raw, indent=2) + '\n')
run(root / 'benchmarks/spikes/memory-candidate/check_fixture.py',
    '--converter', out / 'translation/wasm2go', '--output', out / 'memory32-regression')
run(spike / 'setup_candidate.py', '--source-only', '--source-module', out / 'translation/module',
    '--guest', guest / 'mariamem.wasm', '--input-manifest', root / 'release/generated-go-translation.json',
    '--output', out / 'candidate')
module = out / 'candidate/module'
pins.update(source_sha=source_commit,
            candidate_files_sha256={p.relative_to(module).as_posix(): digest(p)
                for suffix in ('*.go', '*.s') for p in sorted(module.rglob(suffix))},
            data_sha256=digest(module / 'generated/data.bin'))
pins_file.write_text(json.dumps(pins, indent=2) + '\n')
run(root / 'scripts/generate_runtime.py', '--source-module', module, '--output', out / 'generatedgo')
shutil.rmtree(root / 'internal/generatedgo')
shutil.copytree(out / 'generatedgo', root / 'internal/generatedgo')
if partial:
    print('Source adoption only; independent canonical guest build and regeneration still pending')
    sys.exit(0)
canonical = {'source_commit':record['source_commit'], 'completed':True,
    'full_guest_regeneration':True, 'guest_sha256':record['guest_sha256'],
    'guest_size':record['guest_bytes'], 'linked_guest_sha256':record['repetitions'][0]['linked_sha256'],
    'prepared_source':record['prepared_source'], 'repetitions':record['repetitions'],
    'toolchain':record['toolchain'], 'compiled_guest_source_scope':'MariaDB 12.3.3 canonical portability series; no experimental.patch'}
(root / 'release/generated-go-build.json').write_text(json.dumps(canonical, indent=2) + '\n')
run(root / 'scripts/regenerate_release_guest.py', '--guest-dir', guest, '--output', task / 'temp/independent-regeneration-3')
run(root / 'scripts/verify_generated_runtime.py')
print('PASS: canonical adoption and independent generated source identity')
