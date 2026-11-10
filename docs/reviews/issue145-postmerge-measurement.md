# Issue145 post-merge Close measurement

PR146 was squash-merged after Human approval on2026-11-10. Merged source_commit
`8eded3625ebc22a3a52280bf7647a1056e3183af` has the same tree as accepted candidate
`b4e9bc4c6988ae2d1a2ea6ffc6151b395c59553e`. Normal CI42673914153 attempt2 and
macOS401def4e CI42670536897 retain their original sources; they are not relabeled
as new qualification at the merge commit. No version or release was approved.

The merged implementation retains a clear Close benefit after1MiB writes in this
bounded cohort: every one of six alternating pairs improves for both fresh and
Fork databases. No-write and10MiB cells show no useful Close reduction. Complete
lifecycle timing does not establish a universal speedup; the read-only Fork cell
is slower in this cohort. Keep these workload limits explicit.

## Matched results

Each number is the median of six samples, in milliseconds. Each condition uses
six alternating before/after pairs; all72 DBs complete Close-error checks.
Every populated cell validates its data.

| Database / writes | Before Close | Merged Close | Merged Close pair wins | Before lifecycle | Merged lifecycle |
| --- | ---: | ---: | ---: | ---: | ---: |
| fresh, empty | 7.911 | 7.836 | 4/6 | 45.502 | 45.631 |
| fresh, 1MiB | 7.658 | 4.252 | 6/6 | 111.144 | 105.098 |
| fresh, 10MiB | 4.385 | 4.346 | 2/6 | 580.074 | 581.951 |
| fork, read-only1MiB baseline | 2.073 | 2.082 | 2/6 | 31.870 | 38.594 |
| fork, 1MiB | 7.744 | 2.165 | 6/6 | 60.248 | 52.469 |
| fork, 10MiB | 2.155 | 2.245 | 1/6 | 296.754 | 292.360 |

The1MiB Close medians decrease44.5% for fresh and72.0% for Fork. The before10MiB
Close was already short (fresh4.385ms / Fork2.155ms), unlike the1MiB cells.
Earlier flushing is a possible explanation, not a measured finding: dirty-page
counts, internal flush phases, CPU and RSS were not measured. No causal claim
about that difference or a general large-database benefit is made.

Read-only Fork lifecycle rises31.870→38.594ms (merged wins2/6 pairs). Its startup
medians are19.510→19.258ms and Close2.073→2.082ms; the larger difference lies in
work/SQL/disconnect timing. Its cause is unassigned. The raw phase samples below
are retained without retries or exclusions; do not hide this cell behind the
write-heavy Close result or call the complete suite uniformly faster.

## Workload and limits

- macOS27.2 arm64, Apple M1,8 logical CPUs,16GiB RAM; Go1.26.10, Python3.14.10,
  PyMySQL1.2.3. GOMAXPROCS/GOGC use defaults. Canonical guest8e3761ea is identical
  in both binaries. This cohort is separate from the earlier Go1.27.3 experiment.
- Fresh: Start→empty, or insert1024/10240 rows of1024-byte BLOBs (exact1/10MiB).
  Fork: immutable1/10MiB baseline, validate data, optionally update every row.
  No-write Fork reads the1MiB baseline; it is not an empty database.
- Validate COUNT, byte count, maximum id and representative payload; disconnect
  clients and wait for cleanup before timing Close. No caller SET is added.
  The merged host selects its mode internally. Observe db_close exceptions before
  Python public disposal can consume a closed error; common observer overhead
  is included for both binaries. No retries, filtering or added warmup campaign.
- Lifecycle includes startup/Fork, SQL/validation/disconnect and Close. Snapshot
  preparation is outside child lifecycle. Fresh includes final host-process
  disposal; Fork retains a Snapshot owner. Compare binaries within a row, not
  fresh against Fork absolute times.
- Build/cache preparation completes before timing. This is serial, warm-file-cache
  measurement on a shared host, not an isolated cold/scaling test. A background
  Virtualization process was observed at about24% of one CPU before the campaign.
  Six pairs and this workload do not establish stable tails, RSS or Linux gains.
- All72 samples and parent handles complete successfully. Source and workspace
  are unchanged during timing. No broad integration/guest regeneration was rerun
  for this measurement; accepted relevant CI correctness is reused.

## Source and binary identity

The main binary is built from an independent clean checkout with an actual
Go1.26.10 clean VCS stamp. A cheap dry-run caught Go1.26.10 picking up an outer
repository identity for a linked worktree; that path was not used for binaries
or measurement. The independent checkout fixes source discovery without manually
overriding a stamp. Both Git objects are verified as commits with git_identity.py.

The before binary uses a Go overlay containing only the two changed production
Go files from main-before279fa530. All other production Go/assembly/module inputs
and the public Python SDK match the merged checkout. Both actual VCS stamps say
8eded362, while the before runtime is279fa530. **Its stamp is not relabeled as an
independently clean baseline checkout.** Overlay-file hashes and both binary
hashes are retained separately below.

```json
{
  "identities": {
    "merged": {
      "object_sha": "8eded3625ebc22a3a52280bf7647a1056e3183af",
      "object_type": "commit",
      "source_commit": "8eded3625ebc22a3a52280bf7647a1056e3183af"
    },
    "baseline": {
      "object_sha": "279fa530d03cab1bd025df91bf5130bbf845a721",
      "object_type": "commit",
      "source_commit": "279fa530d03cab1bd025df91bf5130bbf845a721"
    }
  },
  "go": "go version go1.26.10 darwin/arm64",
  "overlay_files": {
    "internal/host/server.go": "5749c751c84c854c429423dad72f02cdfc7c8333213a22937340aa71382185f6",
    "internal/host/heap_snapshot.go": "07d5ce9173d5aa3b2dd014a5250214bc5a904f6dc0c3115d77ba547d4d220e45"
  },
  "binaries": {
    "merged": {
      "runtime_source_commit": "8eded3625ebc22a3a52280bf7647a1056e3183af",
      "stamped_source_commit": "8eded3625ebc22a3a52280bf7647a1056e3183af",
      "sha256": "84a563b88c73255dd14ea119bb92b20601e55ad6709d5cf117bb8add36c4c6e5",
      "bytes": 103366514,
      "overlay": false
    },
    "baseline": {
      "runtime_source_commit": "279fa530d03cab1bd025df91bf5130bbf845a721",
      "stamped_source_commit": "8eded3625ebc22a3a52280bf7647a1056e3183af",
      "sha256": "af2e8e0ac56d91f45a3c4c967d3feac18ab4df119456d2a804bce2acfc0772c3",
      "bytes": 103349874,
      "overlay": true
    }
  },
  "guest_sha256": "8e3761eaf65df842191c98cfc4bf493ae08df9374204774f453b9349e21711df",
  "production_go_delta": [
    "internal/host/heap_snapshot.go",
    "internal/host/server.go"
  ],
  "public_python_sdk_unchanged": true
}
```

## Runtime environment

```json
{
  "python": "3.14.10 (main, Oct 25 2026, 17:12:00) [Clang 21.0.0 (clang-2100.3.34.2)]",
  "pymysql": "1.2.3",
  "system": "Darwin",
  "machine": "arm64",
  "macos": "27.2",
  "cpu_count": 8,
  "cpu_brand": "Apple M1",
  "memory_bytes": 17179869184,
  "GOMAXPROCS": "default",
  "GOGC": "default"
}
```

## Raw samples

No rows are excluded. Timing fields are in milliseconds. `baseline_mib` denotes
the Fork source Snapshot size (zero for fresh), not the before-binary identity.

```csv
binary,origin,written_mib,baseline_mib,repeat,startup_ms,work_and_disconnect_ms,close_ms,lifecycle_ms
baseline,fresh,0,0,0,37.261958,0.011375,7.78575,45.066583
merged,fresh,0,0,0,37.84975,0.010833,7.862375,45.730708
merged,fresh,0,0,1,38.773792,0.00975,7.810125,46.60125
baseline,fresh,0,0,1,38.695167,0.009,8.323375,47.035958
baseline,fresh,0,0,2,37.834625,0.012167,8.036458,45.893167
merged,fresh,0,0,2,37.585667,0.009583,7.926791,45.530792
merged,fresh,0,0,3,38.091833,0.010167,7.9255,46.035833
baseline,fresh,0,0,3,36.94425,0.009333,7.775583,44.735583
baseline,fresh,0,0,4,37.625875,0.0085,8.05625,45.698458
merged,fresh,0,0,4,37.720833,0.009209,7.242167,44.978542
merged,fresh,0,0,5,37.230875,0.009,7.594375,44.8445
baseline,fresh,0,0,5,37.580833,0.010542,7.707541,45.3065
baseline,fresh,1,0,0,38.237042,61.236792,7.682667,107.167292
merged,fresh,1,0,0,37.966166,60.636959,4.323833,102.936833
merged,fresh,1,0,1,39.335541,69.306334,4.250791,112.904208
baseline,fresh,1,0,1,40.738917,61.120375,7.633833,109.500833
baseline,fresh,1,0,2,40.499166,60.517167,7.772375,108.799916
merged,fresh,1,0,2,36.916458,67.867792,4.249333,109.045458
merged,fresh,1,0,3,37.946792,61.639083,4.33425,103.93075
baseline,fresh,1,0,3,46.218084,67.927625,7.59075,121.74375
baseline,fresh,1,0,4,39.971167,69.238541,7.681333,116.902333
merged,fresh,1,0,4,41.043167,61.0385,4.173791,106.264792
merged,fresh,1,0,5,37.706708,61.307958,4.253042,103.277666
baseline,fresh,1,0,5,36.772709,68.405375,7.600083,112.787625
baseline,fresh,10,0,0,37.274583,539.941459,4.443375,581.668292
merged,fresh,10,0,0,37.549709,539.013041,4.445417,581.019209
merged,fresh,10,0,1,38.004459,540.65,4.221125,582.883584
baseline,fresh,10,0,1,37.898917,543.185792,7.999958,589.09425
baseline,fresh,10,0,2,39.67,535.062375,4.306167,579.049666
merged,fresh,10,0,2,39.499041,544.385917,4.328042,588.22475
merged,fresh,10,0,3,39.15825,543.654792,4.349708,587.170917
baseline,fresh,10,0,3,39.522583,535.538375,4.359042,579.431166
baseline,fresh,10,0,4,37.180209,521.665041,4.285875,563.139459
merged,fresh,10,0,4,37.811666,535.019542,4.342375,577.185625
merged,fresh,10,0,5,37.618667,536.617208,4.585958,578.834167
baseline,fresh,10,0,5,37.753333,538.545417,4.410833,580.717375
baseline,fork,0,1,0,21.59675,17.609333,2.046458,41.255708
merged,fork,0,1,0,19.444166,17.623542,2.168042,39.23925
merged,fork,0,1,1,18.84875,17.596375,2.262584,38.711417
baseline,fork,0,1,1,19.166375,10.152166,2.099167,31.420708
baseline,fork,0,1,2,20.497542,9.710458,2.108041,32.319208
merged,fork,0,1,2,19.072125,17.32875,2.072209,38.476125
merged,fork,0,1,3,19.818375,17.1475,2.064708,39.033167
baseline,fork,0,1,3,18.651292,9.656417,2.114958,30.425959
baseline,fork,0,1,4,18.402208,9.491333,2.003,29.899458
merged,fork,0,1,4,19.658292,9.406208,2.062084,31.129584
merged,fork,0,1,5,18.383292,17.145333,2.092042,37.623583
baseline,fork,0,1,5,19.8535,17.448125,1.993584,39.298083
baseline,fork,1,1,0,20.757042,29.855458,7.716959,58.333458
merged,fork,1,1,0,19.467959,29.394166,2.1515,51.016584
merged,fork,1,1,1,18.854666,28.750084,2.178167,49.785958
baseline,fork,1,1,1,18.934,29.454667,7.929042,56.3215
baseline,fork,1,1,2,24.449709,29.730041,7.978542,62.16225
merged,fork,1,1,2,20.538125,31.022167,2.3565,53.921042
merged,fork,1,1,3,18.910584,38.181125,2.188708,59.283584
baseline,fork,1,1,3,19.067459,30.457666,7.771542,57.300959
baseline,fork,1,1,4,21.918584,37.481916,7.58275,66.987375
merged,fork,1,1,4,18.557792,29.433375,2.130625,50.125167
merged,fork,1,1,5,23.768209,36.571916,2.1375,62.48075
baseline,fork,1,1,5,18.632,36.911,7.57675,63.123833
baseline,fork,10,10,0,20.895375,271.821375,2.119125,294.839625
merged,fork,10,10,0,19.716583,280.611959,2.130084,302.461917
merged,fork,10,10,1,20.974583,266.528042,2.241458,289.747541
baseline,fork,10,10,1,20.814958,282.437708,2.230375,305.486333
baseline,fork,10,10,2,19.153958,274.205292,2.146625,295.509041
merged,fork,10,10,2,20.176917,272.543083,2.2495,294.972708
merged,fork,10,10,3,19.04375,268.29975,2.206625,289.553416
baseline,fork,10,10,3,18.818042,264.651292,2.227,285.699667
baseline,fork,10,10,4,20.713709,275.11675,2.164292,297.998292
merged,fork,10,10,4,20.305292,262.471583,2.252125,285.032584
merged,fork,10,10,5,21.055209,273.296041,2.286083,296.640459
baseline,fork,10,10,5,20.084208,280.91525,2.132958,303.135583
```

## Reproduction

Prepare disposable scratch with `temp/`, `evidence/` and a checkout for record
bookkeeping. Create `temp/source` as an independent clone (a `.git` directory,
not a linked-worktree `.git` file), checkout exact main8eded362 and inspect its
identity. Save the two scripts below as `evidence/build.py` and `evidence/probe.py`.
Run the build under the experiment disk/time guard with8GiB free and2GiB owned
scratch limits. Use the recorded Go toolchain; `build.py` owns its compiler cache.
After build exits, run `probe.py` with PYTHONDONTWRITEBYTECODE=1, PyMySQL1.2.3 and
PYTHONPATH pointing at `temp/source/python`, under the same guard. Do not measure
while either binary is compiling. Reduce/save results before deleting the clone,
binaries and owned compiler cache. Local guards observed build peak1,930,956,800
owned bytes and minimum free39,114,440,704 bytes; no limit was breached.

### Build and verify

```python
import hashlib,json,os,subprocess,sys
from pathlib import Path
work=Path(__file__).resolve().parent.parent
src=work/'temp/source';out=work/'evidence';temp=work/'temp'
main='8eded3625ebc22a3a52280bf7647a1056e3183af'
base='279fa530d03cab1bd025df91bf5130bbf845a721'
os.environ.update(GOTOOLCHAIN='go1.26.10',GOCACHE=str(temp/'gocache'),PYTHONDONTWRITEBYTECODE='1')
sys.path.insert(0,str(src/'scripts'))
from git_identity import inspect_ref,verify_go_binary
identities={n:inspect_ref(src,s).__dict__ for n,s in [('merged',main),('baseline',base)]}
assert all(r['object_type']=='commit' for r in identities.values())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=src,text=True).strip()==main
assert not subprocess.check_output(['git','status','--porcelain'],cwd=src,text=True).strip()
meta=dict(identities=identities,go=subprocess.check_output(['go','version'],text=True).strip(),overlay_files={},binaries={})
import re
meta['guest_sha256']=re.search(r'GuestSHA256\s*=\s*"([0-9a-f]{64})"',(src/'internal/generatedgo/entry.go').read_text()).group(1)
replace={}
for f in ('internal/host/server.go','internal/host/heap_snapshot.go'):
 data=subprocess.check_output(['git','show',base+':'+f],cwd=src)
 target=temp/('baseline-'+Path(f).name);target.write_bytes(data)
 replace[str(src/f)]=str(target)
 meta['overlay_files'][f]=hashlib.sha256(data).hexdigest()
(temp/'overlay.json').write_text(json.dumps({'Replace':replace},indent=2)+'\n')
with (out/'build.txt').open('w') as log:
 for name,flags,runtime in [('merged',[],main),('baseline',['-overlay',str(temp/'overlay.json')],base)]:
  binary=temp/(name+'-host')
  cmd=['go','build','-buildvcs=true','-p','1',*flags,'-o',str(binary),'./cmd/mariamem-host']
  print('Building',name,flush=True)
  subprocess.run(cmd,cwd=src,stdout=log,stderr=subprocess.STDOUT,check=True)
  info=verify_go_binary(src,binary,main,toolchain='go1.26.10')
  (out/(name+'-build-info.txt')).write_text(info)
  digest=hashlib.sha256()
  with binary.open('rb') as stream:
   for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
  meta['binaries'][name]={'runtime_source_commit':runtime,'stamped_source_commit':main,'sha256':digest.hexdigest(),'bytes':binary.stat().st_size,'overlay':bool(flags)}
(out/'inputs.json').write_text(json.dumps(meta,indent=2)+'\n')
print('PASS: both actual binary stamps identify clean merged checkout; baseline overlay/runtime identity is separate',flush=True)
```

### Measure

```python
import csv,json,statistics,time,os,platform,sys,subprocess,importlib.metadata
from pathlib import Path
import mariamem,pymysql
work=Path(__file__).resolve().parent.parent;out=work/'evidence'
inputs=json.loads((out/'inputs.json').read_text())
bins={name:str(work/'temp'/(name+'-host')) for name in ('baseline','merged')}
rows=[];parents={};completed=False
runtime_environment={'python':sys.version,'pymysql':importlib.metadata.version('PyMySQL'),'system':platform.system(),'machine':platform.machine(),'macos':platform.mac_ver()[0],'cpu_count':os.cpu_count(),'cpu_brand':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),'memory_bytes':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True)),'GOMAXPROCS':os.environ.get('GOMAXPROCS','default'),'GOGC':os.environ.get('GOGC','default')}
(out/'environment.json').write_text(json.dumps(runtime_environment,indent=2)+'\n')

def connect(db):
 return pymysql.connect(**db.connection_info(),autocommit=True)

def check_data(q,n,letter):
 q.execute('SELECT COUNT(*),SUM(OCTET_LENGTH(payload)),MAX(id) FROM items')
 assert q.fetchone()==(n,n*1024,n-1)
 q.execute('SELECT payload FROM items WHERE id=0')
 assert q.fetchone()==(letter*1024,)

def seed(db,mib):
 n=mib*1024;c=connect(db)
 try:
  with c.cursor() as q:
   q.execute('CREATE TABLE items(id INT PRIMARY KEY,payload BLOB) ENGINE=InnoDB')
   q.executemany('INSERT INTO items VALUES(%s,%s)',[(i,b'x'*1024) for i in range(n)])
   check_data(q,n,b'x')
 finally:c.close()
 db.wait_disconnected()

def close_checked(db):
 # Observe errors before the public Python closed/disposal handler can consume
 # them. Identical observer overhead applies to both binaries; no retry/reset.
 original=db._request;failures=[]
 def observe(op,*args,**kw):
  try:return original(op,*args,**kw)
  except BaseException as exc:
   if op=='db_close':failures.append(repr(exc))
   raise
 db._request=observe
 try:
  start=time.perf_counter_ns();db.close();ms=(time.perf_counter_ns()-start)/1e6
  assert not failures,failures
  return ms
 finally:db._request=original

try:
 for name,binary in bins.items():
  for mib in (1,10):
   src=mariamem.Database(host_binary=binary)
   try:
    assert src._session.guest_identity==inputs['guest_sha256']
    seed(src,mib);parents[name,mib]=src.snapshot()
   finally:src.close()
 for origin in ('fresh','fork'):
  for written_mib in (0,1,10):
   for repeat in range(6):
    order=('baseline','merged') if repeat%2==0 else ('merged','baseline')
    for name in order:
     start=time.perf_counter_ns()
     db=mariamem.Database(host_binary=bins[name]) if origin=='fresh' else parents[name,max(1,written_mib)].fork()
     started=time.perf_counter_ns();startup_ms=(started-start)/1e6
     try:
      assert db._session.guest_identity==inputs['guest_sha256']
      if origin=='fresh' and written_mib:seed(db,written_mib)
      if origin=='fork':
       n=max(1,written_mib)*1024;c=connect(db)
       try:
        with c.cursor() as q:
         check_data(q,n,b'x')
         if written_mib:
          q.execute("UPDATE items SET payload=REPEAT('y',1024)")
          check_data(q,n,b'y')
       finally:c.close()
       db.wait_disconnected()
      ready=time.perf_counter_ns()
      close_ms=close_checked(db);finish=time.perf_counter_ns()
      row=dict(binary=name,origin=origin,written_mib=written_mib,baseline_mib=max(1,written_mib) if origin=='fork' else 0,repeat=repeat,startup_ms=startup_ms,work_and_disconnect_ms=(ready-started)/1e6,close_ms=close_ms,lifecycle_ms=(finish-start)/1e6)
      rows.append(row)
      with (out/'samples.jsonl').open('a') as stream:stream.write(json.dumps(row)+'\n')
      print(json.dumps(row),flush=True)
     finally:db.close()
 completed=True
finally:
 for snap in parents.values():snap.close()
 (out/'completion.json').write_text(json.dumps({'complete':completed,'samples':len(rows),'all_parent_handles_closed':True},indent=2)+'\n')
assert len(rows)==72
summary=[]
for origin in ('fresh','fork'):
 for written_mib in (0,1,10):
  result=dict(origin=origin,written_mib=written_mib,n=6)
  for name in bins:
   group=[r for r in rows if (r['origin'],r['written_mib'],r['binary'])==(origin,written_mib,name)]
   result[name]={key:statistics.median(r[key] for r in group) for key in ('startup_ms','work_and_disconnect_ms','close_ms','lifecycle_ms')}
  summary.append(result)
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
with (out/'samples.csv').open('w',newline='') as stream:
 writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
print(json.dumps(summary,indent=2),flush=True)
```

## Actual build-info records

Only the disposable workspace path is normalized; source stamps/flags remain
verbatim. These records are not substituted into candidate/runtime identity fields.

### merged

```text
<WORKSPACE>/temp/merged-host: go1.26.10
	path	github.com/masahitojp/mariamem/cmd/mariamem-host
	mod	github.com/masahitojp/mariamem	v0.6.3-0.20261109225925-8eded3625ebc	
	build	-buildmode=exe
	build	-compiler=gc
	build	CGO_ENABLED=1
	build	CGO_CFLAGS=
	build	CGO_CPPFLAGS=
	build	CGO_CXXFLAGS=
	build	CGO_LDFLAGS=
	build	GOARCH=arm64
	build	GOOS=darwin
	build	GOARM64=v8.0
	build	vcs=git
	build	vcs.revision=8eded3625ebc22a3a52280bf7647a1056e3183af
	build	vcs.time=2026-11-09T22:59:25Z
	build	vcs.modified=false
```

### baseline

```text
<WORKSPACE>/temp/baseline-host: go1.26.10
	path	github.com/masahitojp/mariamem/cmd/mariamem-host
	mod	github.com/masahitojp/mariamem	v0.6.3-0.20261109225925-8eded3625ebc	
	build	-buildmode=exe
	build	-compiler=gc
	build	CGO_ENABLED=1
	build	CGO_CFLAGS=
	build	CGO_CPPFLAGS=
	build	CGO_CXXFLAGS=
	build	CGO_LDFLAGS=
	build	GOARCH=arm64
	build	GOOS=darwin
	build	GOARM64=v8.0
	build	vcs=git
	build	vcs.revision=8eded3625ebc22a3a52280bf7647a1056e3183af
	build	vcs.time=2026-11-09T22:59:25Z
	build	vcs.modified=false
```
