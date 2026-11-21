"""Run the pinned guest producer with container and workspace storage accounting."""
import json
from pathlib import Path
import shutil
import subprocess
import time

root = Path(__file__).resolve().parents[1]
name = 'mariamem-issue233-phase1'
image = 'ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3'
out = root / 'temp' / 'output'
out.mkdir(exist_ok=True)
command = ['docker', 'run', '--name', name, '--rm', '--platform', 'linux/arm64',
           '-v', str(root / 'temp/source.git') + ':/pin.git:ro',
           '-v', str(root / 'evidence/regenerate.sh') + ':/recipe.sh:ro',
           '-v', str(out) + ':/out', image, 'bash', '/recipe.sh']
deadline = json.loads((root / 'experiment.json').read_text())['created'] + 7200
with (root / 'evidence' / 'builder.log').open('w') as log:
    proc = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
    try:
        while proc.poll() is None:
            try:
                proc.wait(10)
                break
            except subprocess.TimeoutExpired:
                pass
            size = subprocess.run(['docker', 'inspect', '--size', '--format',
                                   '{{.SizeRw}}', name], text=True, capture_output=True)
            if size.returncode and proc.poll() is not None:
                break
            size.check_returncode()
            host = int(subprocess.check_output(['du', '-sk', str(root)]).split()[0]) * 1024
            total = host + int(size.stdout)
            free = shutil.disk_usage(root).free
            print(json.dumps(dict(time=time.time(), owned_bytes=total, free_bytes=free)), flush=True)
            if total > 8 * 2**30 or free < 8 * 2**30 or time.time() >= deadline:
                raise SystemExit('Phase 1 budget reached')
    finally:
        if proc.poll() is None:
            subprocess.run(['docker', 'stop', '-t', '3', name], check=True)
            proc.wait()
    raise SystemExit(proc.returncode)
