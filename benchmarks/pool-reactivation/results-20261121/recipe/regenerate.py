"""Replay the canonical post-gofmt pass from a fresh pinned Git object read."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

workspace = Path(sys.argv[1]).resolve()
source = workspace/'worktree'
sys.path.insert(0, str(source/'scripts'))
from runtime_pool_period import INPUTS, GUEST, install

base = 'a1ce4a7d568fbf6eac7bee032a7fdfbe464544fb'
assert json.loads(subprocess.check_output([sys.executable,source/'scripts/git_identity.py','--root',source,'inspect',base]))['source_commit']==base
output = Path(sys.argv[2]).resolve()
output.mkdir(parents=True, exist_ok=True)
def original(relative):
    return subprocess.check_output(['git','show',base+':internal/generatedgo/'+relative],cwd=source)
for name in INPUTS:
    file = output/name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(original(name))
install(output,GUEST)
inventory = json.loads(original('provenance.json'))
for name in INPUTS:
    inventory['files_sha256'][name] = hashlib.sha256((output/name).read_bytes()).hexdigest()
(output/'provenance.json').write_text(json.dumps(inventory,indent=2)+'\n')
