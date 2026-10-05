from support import *
import shutil,tarfile,fcntl
lock=Path(os.environ['MARIAMEM_TOOLING_REPO'])/'build/experiment-measurement.lock';lock.parent.mkdir(parents=True,exist_ok=True);lane=lock.open('a+');fcntl.flock(lane,fcntl.LOCK_EX|fcntl.LOCK_NB)
run('build-counter',['cc','-O2',R/'benchmarks/tools/process_cost.c','-o',helper])
refs={'released':'547fb1a6c01e5edb0daa27de273a2e94e66eb098','semantics':'56be628bf2d976048c5ea6d1949879781ed75342'}
for mode,ref in refs.items():
 source=T/mode;source.mkdir();archive=T/(mode+'.tar')
 with archive.open('wb') as dest:subprocess.run(['git','archive',ref],cwd=R,stdout=dest,check=True)
 with tarfile.open(archive) as tar:tar.extractall(source,filter='data')
 archive.unlink()
refs['mmap']='current'
record['sources']=refs;record['binary_sha256']={};save()
for mode in refs:
 source=R if mode=='mmap' else T/mode
 for kind in ['fresh','lifecycle']:
  project=T/(mode+'-'+kind);project.mkdir();(project/'go.mod').write_text('module github.com/masahitojp/mariamem/memoryprobe\n\ngo 1.26.0\nrequire github.com/masahitojp/mariamem v0.0.0\nreplace github.com/masahitojp/mariamem => '+str(source)+'\n')
  shutil.copyfile(R/'benchmarks/spikes/mmap-integration'/(kind+'.go.txt'),project/'main.go')
  if mode=='mmap':(project/'counter.go').write_text('package main\nimport "github.com/masahitojp/mariamem/internal/generatedgo/code/base"\nfunc init(){ mappingStats=base.MemoryMappingStats }\n')
  binary=T/(mode+'-'+kind+'-probe');run('build-'+mode+'-'+kind,['go','build','-mod=mod','-p','1','-trimpath','-o',binary,'.'],cwd=project)
  import hashlib;record['binary_sha256'][mode+'-'+kind]=hashlib.sha256(binary.read_bytes()).hexdigest();save()
extras={'MARIAMEM_PROCESS_COUNTER':str(helper)}
for trial in range(12):
 modes=['released','semantics','mmap'];modes=modes[trial%3:]+modes[:trial%3]
 for mode in modes:run('fresh-%02d-%s'%(trial,mode),[T/(mode+'-fresh-probe')],extras=extras,timeout=60)
for mode in refs:run('one20-'+mode,[T/(mode+'-fresh-probe'),'-generations=20'],extras=extras,timeout=180)
import statistics
rows=[json.loads(line) for line in (E/'one20-mmap.log').read_text().splitlines() if line.startswith('{')]
assert len(rows)==20
for metric in ['start_sql_ms','total_cpu_s']:
 first=statistics.median(v[metric] for v in rows[:5]);last=statistics.median(v[metric] for v in rows[-5:])
 assert last<=first*2,('early regression',metric,first,last)
record['one20_mmap_stable_before_expansion']=True;save()
run('one50-mmap',[T/'mmap-fresh-probe','-generations=50'],extras=extras,timeout=240)
for mode in refs:
 record[mode+'_four_completed']=run('four12-'+mode,[T/(mode+'-lifecycle-probe'),'-databases=4','-generations=12'],extras=extras,timeout=240,allow_budget=mode!='mmap');save()
for mode in refs:run('fork20-'+mode,[T/(mode+'-lifecycle-probe'),'-fork','-generations=20'],extras=extras,timeout=240)
record['measurement_pass']=True;save()
