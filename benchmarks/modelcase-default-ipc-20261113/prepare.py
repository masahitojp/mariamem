from pathlib import Path
import subprocess,shutil,json
r=Path(__file__).resolve().parents[1];d=r/'temp/maria';prefix='benchmarks/pgmem-modelcase-20261113/maria-harness/'
for f in subprocess.check_output(['git','ls-tree','-r','--name-only','experiment/pgmem-modelcase',prefix],text=True).splitlines():
 p=d/f[len(prefix):];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(subprocess.check_output(['git','show','experiment/pgmem-modelcase:'+f]))
p=d/'store/fixture_test.go';s=p.read_text().replace('cfg.InterpolateParams=false;','if !cfg.InterpolateParams {panic("benchmark must inherit mariamem DSN interpolateParams=true")};');p.write_text(s)
(r/'evidence/plan.json').write_text(json.dumps({'source_commit':'0f5b26f370875d26bd337031f48856d8f57c10db','pgmem_source_commit':'a61005d37d01e6671f814fe8ca828222e8147df4','phase1':'native mariamem DSN interpolation true vs official pgmem pgx cache; warmup1 +5 alternating pairs, 70 assertions each, parallel8','phase2':'same maria benchmark binary with Go overlay; IPC counters off/on3 alternating pairs, per-process/per-DB reads/writes/bytes/frame sizes/request opcodes, profiled separate3 scenarios; preserve transport unchanged','budget_gib':10,'min_free_gib':12,'build_timeout':1800,'per_process_timeout':130,'measurement_timeout':900,'no_architecture_implementation':True},indent=2))
