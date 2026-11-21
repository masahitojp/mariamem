"""Keep existing INSERT tracing optional and change only the linked pipe endpoints."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
w=Path(sys.argv[1]).resolve()
mode=sys.argv[2]
src=w/'worktree'
temp=w/'temp'
dst=w/'evidence/published'
recipe=Path(__file__).resolve().parent
overlay=temp/'overlay'
overlay.mkdir(exist_ok=True)
mapping={}
if mode=='trace':
    prior=temp/'prior'
    prior.mkdir(exist_ok=True)
    prefix='a81baaef944c69f67666277ae189422ef76d2c47:benchmarks/trigger-go-timeline/results-20261121/recipe/'
    for name in ('overlay.py','timeline.go.txt','reader_test.go.txt','campaign.py'):
        (prior/name).write_bytes(subprocess.check_output(['git','show',prefix+name],cwd=src))
    subprocess.run([sys.executable,prior/'overlay.py',w],check=True)
    mapping=json.loads((temp/'overlay.json').read_text())['Replace']
linked=src/'internal/guest/linked.go'
s=Path(mapping.get(str(linked),linked)).read_text()
assert s.count('os.')==2 and s.count('"os"')==1
s=s.replace('"os"','').replace('childIn, in, err := os.Pipe()','childIn, in, err := experimentPipe("input")').replace('out, childOut, err := os.Pipe()','out, childOut, err := experimentPipe("output")')
assert s.count('experimentPipe(')==2
out=overlay/'linked-stream.go'
out.write_text(s)
mapping[str(linked)]=str(out)
mapping[str(linked.with_name('experiment_stream.go'))]=str(recipe/'pipe.go.txt')
(temp/'overlay.json').write_text(json.dumps({'Replace':mapping}))
(dst/(mode+'-sources.json')).write_text(json.dumps({str(Path(p).relative_to(w)):hashlib.sha256(Path(o).read_bytes()).hexdigest() for p,o in mapping.items()},indent=2)+'\n')
