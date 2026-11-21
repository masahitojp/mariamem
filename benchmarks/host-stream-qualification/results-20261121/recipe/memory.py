"""Build a separate memory probe. Sample current RSS at both P8 barriers and after Close."""
from pathlib import Path
import subprocess,sys,os
w=Path(sys.argv[1]).resolve();t=w/'temp';p=w/'evidence/published';rec=p/'recipe'
src=w/'worktree'
import json
assert json.loads(subprocess.check_output(['python3','scripts/git_identity.py','inspect','HEAD'],cwd=src))['source_commit']=='5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c'
exe=t/'memory'
if sys.argv[2]=='build':
    f=t/'harness/waves.go'
    s=(rec/'waves.go.txt').read_text()
    s=s.replace('"runtime"', '"runtime"\n"os/exec"\n"os"\n"strconv"')
    sample="""func sampleRSS() int64 {
        out,err:=exec.Command("/bin/ps","-o","rss=","-p",strconv.Itoa(os.Getpid())).Output()
        must(err); kib,err:=strconv.ParseInt(strings.TrimSpace(string(out)),10,64);must(err);return kib*1024
    }
    """
    s=s.replace('func wave(',sample+'func wave(')
    s=s.replace('cpu, _ := usage()', 'rssReady:=sampleRSS();cpu, _ := usage()')
    s=s.replace('close(g.finish)', 'rssDone:=sampleRSS();close(g.finish)')
    s=s.replace('joined.Wait()', 'joined.Wait();runtime.GC();rssClosed:=sampleRSS()')
    s=s.replace('"wave": n,', '"rss_ready":rssReady,"rss_done":rssDone,"rss_closed":rssClosed,"wave": n,')
    assert all(s.count(v)==2 for v in ('rssReady','rssDone','rssClosed'))
    f.write_text(s)
    env=dict(os.environ,CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(t/'gocache'),GOTOOLCHAIN='local',GOWORK='off',GOPROXY='off',GOFLAGS='',TMPDIR=str(t/'gotmp'))
    subprocess.run(['go','build','-trimpath','-buildvcs=false','-p','1','-mod=readonly','-overlay',t/'overlay.json','-o',exe,'.'],cwd=t/'harness',env=env,check=True)
else:
    out=p/'memory';out.mkdir(exist_ok=True)
    for b in range(1,7):
        for m in (('os','both') if b%2 else ('both','os')):
            env=dict(os.environ,GOMAXPROCS='8',GOGC='100',TMPDIR=str(t/'gotmp'),MARIAMEM_BENCH_STREAM=m)
            r=subprocess.run([exe,'-work','C','-waves','6'],env=env,text=True,capture_output=True,timeout=90,check=True)
            (out/f'{b}-{m}.jsonl').write_text(r.stdout)
            rows=[json.loads(l) for l in r.stdout.splitlines()]
            assert len(rows)==6 and all(x['rss_ready']>0 and x['rss_done']>0 and x['rss_closed']>0 and x['all_workers_closed'] for x in rows)
