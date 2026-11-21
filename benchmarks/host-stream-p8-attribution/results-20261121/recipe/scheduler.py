"""Recover scheduler states, causal wakeup stacks and symbols for the longest
worker interval in each diagnostic slow sample. Input is go tool trace -d=parsed.
The measured trace and symbol map are checked before decoding."""
import functools,gzip,hashlib,json,re,subprocess,sys
from collections import Counter
from pathlib import Path
w=Path(sys.argv[1]).resolve();out=w/'evidence/published';t=w/'temp';src=w/'worktree'
sha='7c5893b3d5198d2c5087dbb100e631dfe63a58bb'
m=gzip.decompress(subprocess.check_output(['git','show',sha+':benchmarks/trigger-sum-bottleneck/results-20261121/functions.txt.gz'],cwd=src))
proof=json.loads((src/'release/generated-license-evidence.json').read_text())
assert hashlib.sha256(m).hexdigest()==proof['symbol_map_sha256']
assert proof['guest_sha256'] in (src/'internal/generatedgo/guest_identity.go').read_text()
names=dict(line.split(':',1) for line in m.decode().splitlines());assert len(names)==proof['symbol_map_entries']
@functools.cache
def symbol(i):
    return subprocess.check_output(['c++filt','-n',names[i]],text=True).strip()

def headers(path,match):
    """Read matching event headers with their attached stacks."""
    block=[]
    with path.open() as f:
        for line in f:
            if line.startswith('M='):
                if block:yield block
                block=[line.strip()] if match(line) else []
            elif block:block.append(line.rstrip())
    if block:yield block

def event(block):
    h=block[0];at=int(re.search(r'Time=(\d+)',h)[1]);g=int(re.search(r' G=(-?\d+)',h)[1])
    stacks={};key=None
    for l in block[1:]:
        if l.endswith('Stack='):
            key=l[:-1];stacks[key]=[]
        elif key and ' @ ' in l:
            name=l.split(' @ ')[0].strip()
            fn=re.search(r'/p\d+\.Fn(\d+)$',name)
            if fn:name+=' ('+symbol(fn[1])+')'
            stacks[key].append(name)
    return dict(time=at,g=g,event=h,stacks=stacks)
def mark(tail,iv,parsed):
    target=tail['lane']+' '+str(iv['id'])+' '
    keys={}
    for b in headers(parsed,lambda l:'Category="p8req"' in l and 'Message="'+target in l):
        phase=b[0].rsplit(' ',1)[1][:-1];keys[phase]=event(b)
    start=keys['worker'];end=keys['reply'];gid=start['g']
    assert gid==end['g'] and abs((end['time']-start['time'])/1e6-iv['interval_ms'])<1
    states=[];totals=Counter();state='Running';last=start
    tag='GoID='+str(gid)+' '
    for b in headers(parsed,lambda l:tag in l and 'StateTransition' in l):
        ev=event(b)
        if not start['time']<ev['time']<end['time']:continue
        old,new=re.search(r'(\w+)->(\w+)',ev['event']).groups()
        assert state==old
        delta=ev['time']-last['time'];totals[state]+=delta
        states.append(dict(state=state,duration_ms=delta/1e6,begin=last,end=ev))
        state=new;last=ev
    totals[state]+=end['time']-last['time']
    assert state=='Running' and sum(totals.values())==end['time']-start['time']
    longest=max(states,key=lambda x:x['duration_ms'])
    assert longest['state']=='Waiting'
    # Trace goroutine creation from the waker back to the ancestor that
    # already existed when the request entered the worker.
    chain=[];ancestor=longest['end']['g'];until=longest['end']['time']
    pattern=re.compile(r'GoID=(\d+) NotExist->Runnable')
    births={}
    for b in headers(parsed,lambda l:'NotExist->Runnable' in l and 'GoID=' in l):
        h=b[0];tm=int(re.search('Time=(\\d+)',h)[1])
        if start['time']<=tm<=until:
            births[int(pattern.search(h)[1])]=b
    while ancestor in births:
        ev=event(births[ancestor]);chain.append(ev);ancestor=ev['g']
    previous=[]
    ancestor_limit=chain[-1]['time'] if chain else until
    for b in headers(parsed,lambda l:'GoID='+str(ancestor)+' ' in l and 'StateTransition' in l):
        ev=event(b)
        if ev['time']>ancestor_limit:break
        previous.append(ev)
    return dict(file=tail['file'],lane=tail['lane'],id=iv['id'],goroutine=gid,states_ms={k:v/1e6 for k,v in totals.items()},
                worker_start=start['event'],reply=end['event'],longest_wait=longest,creation_chain=chain,
                ancestor=ancestor,ancestor_states=previous[-8:])
result=[]
for tail in json.loads((out/'tails.json').read_text()):
    iv=tail['intervals'][0]
    if iv['phase']!='worker':continue
    trace=t/(tail['file']+'.trace')
    if not trace.exists():continue
    parsed=t/(tail['file']+'.parsed')
    with parsed.open('wb') as f:subprocess.run(['go','tool','trace','-d=parsed',trace],stdout=f,check=True)
    result.append(mark(tail,iv,parsed))
    with trace.open('rb') as srcfile,gzip.open(out/(trace.name+'.gz'),'wb') as dst:
        import shutil
        shutil.copyfileobj(srcfile,dst)
    parsed.unlink()
(out/'scheduler.json').write_text(json.dumps(result,indent=2)+'\n')
