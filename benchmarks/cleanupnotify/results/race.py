from pathlib import Path
import os,sys
w=Path(__file__).resolve().parents[1];s=w/'worktree';t=w/'temp';e=w/'evidence';sys.path.insert(0,str(s/'scripts'));from experiment_disk import DiskGuard,run_guarded
env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','GODEBUG','ISSUE117_','UPDATE_'))};env.update(CGO_ENABLED='1',GOTOOLCHAIN='local',GOENV='off',GOWORK='off',GOFLAGS='',GOEXPERIMENT='',GOMAXPROCS='8',GOCACHE=str(t/'cache'),GOMODCACHE=str(t/'modcache'),GOTMPDIR=str(t/'gotmp'),TMPDIR=str(t/'scratch'),GOMEMLIMIT='3GiB',GOGC='50')
with (e/'notification-race.log').open('w') as log:code=run_guarded(['go','test','-race','-p','1','-count=1','-gcflags=github.com/masahitojp/mariamem/internal/generatedgo/code/...=-race=false','-run','TestIssue117|TestWaitDisconnected|TestWorkerTrapFailsPendingCallsBeforeCompletion','-overlay',str(t/'overlay/overlay.json'),'.','./internal/host','./internal/guest'],DiskGuard(w,12,6),cwd=s,env=env,output=log,timeout=1200)
assert code==0,code
print('NOTIFICATION RACE PASS',flush=True)
