import json,os,subprocess,sys
from pathlib import Path
w=Path(sys.argv[1]).resolve();t=w/'temp';rec=w/'evidence/timer/recipe'
mp=json.loads((t/'diag-ring.overlay.json').read_text())
mp['Replace'][str(w/'worktree/internal/generatedgo/code/base/futex_observer_test.go')]=str(rec/'control_test.go.txt')
overlay=t/'control.overlay.json';overlay.write_text(json.dumps(mp))
env=dict(os.environ,GOCACHE=str(t/'gocache'),TMPDIR=str(t/'gotmp'),GOMAXPROCS='8',GOTOOLCHAIN='local',GOPROXY='off',
    GOWORK='off',GOFLAGS='',FUTEX_OUT=str(t/'control.json'))
subprocess.run(['go','test','-mod=readonly','-trimpath','-p','1','-vet=off','-overlay',overlay,
                'github.com/masahitojp/mariamem/internal/generatedgo/code/base','-run','^TestFutexObserverControls$','-v','-count=1'],cwd=t/'diag',env=env,check=True)
