import json
import os
from pathlib import Path
import subprocess
import sys
w=Path(sys.argv[1]).resolve()
t=w/'temp'
src=w/'worktree'
recipe=Path(__file__).resolve().parent
manifest=json.loads((t/'overlay.json').read_bytes())
dest=src/'internal/generatedgo/code/base/shim_experiment_test.go'
manifest['Replace'][str(dest)]=str(recipe/'bounds_test.go.txt')
m=t/'test-overlay.json'
m.write_text(json.dumps(manifest))
env=dict(os.environ,CGO_ENABLED='0',GOCACHE=str(t/'gocache'),GOTOOLCHAIN='local',
         GOWORK='off',GOPROXY='off',GOFLAGS='',TMPDIR=str(t/'gotmp'),GOMAXPROCS='8')
subprocess.run(['go','test','-trimpath','-p','1','-overlay',m,'-count=1','-run','^TestCheckedMemory32Shim$',
                '-v','./internal/generatedgo/code/base'],env=env,cwd=src,check=True)

subprocess.run(['go','test','-trimpath','-p','1','-overlay',m,'-tags=integration','-count=1',
                '-run','^TestPureMemory32GeneratedTraps$','-v','./tests/generatedmemory'],
               env=env,cwd=src,check=True)
