from pathlib import Path
import sys,json,subprocess,hashlib
s,o=map(lambda p:Path(p).resolve(),sys.argv[1:]);subprocess.run(['python3',str(s/'benchmarks/issue140admission/overlay.py'),str(s),str(o)],check=True)
m=json.loads((o/'overlay.json').read_text());d=s/'benchmarks/issue140readsetting'
m['Replace'][str(s/'internal/generatedgo/code/base/pool_selector.go')]=str(d/'selector.go.txt')
m['Replace'][str(s/'internal/generatedgo/code/base/read_observe.go')]=str(d/'read_observe.go.txt')
m['Replace'][str(s/'internal/generatedgo/code/base/read_setting_test.go')]=str(d/'selector_test.go.txt')
records=[]
for name,edit in [('benchmarks/issue88modelcase/maria/store/backend_test.go','settings'),('benchmarks/issue88modelcase/maria/store/fixture_test.go','rss')]:
 p=s/name;text=p.read_text()
 if edit=='settings':
  needle='var v string';assert text.count(needle)==1
  text=text.replace(needle,'''var key string;var actual int
 must(p.QueryRow("SHOW VARIABLES LIKE 'innodb_read_io_threads'").Scan(&key,&actual))
 wanted,e:=strconv.Atoi(os.Getenv("ISSUE140_READ_THREADS"));must(e)
 if actual!=wanted {panic("read setting mismatch")};r.Set("innodb_read_io_threads",fmt.Sprint(actual))
 var v string''',1)
 else:
  needle='fx.rec.Set("cpu_ms", fmt.Sprint(cost()-before))';assert text.count(needle)==1
  text=text.replace(needle,needle+'\n var usage syscall.Rusage;must(syscall.Getrusage(syscall.RUSAGE_SELF,&usage));fx.rec.Set("maxrss_bytes_darwin",fmt.Sprint(usage.Maxrss))',1)
 out=o/(edit+'.go');out.write_text(text);m['Replace'][str(p)]=str(out)
(o/'overlay.json').write_text(json.dumps(m,indent=2)+'\n')
for original,replacement in sorted(m['Replace'].items()):
 p=Path(original);r=Path(replacement);records.append({'path':str(p.relative_to(s)),'before_sha256':hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else None,'after_sha256':hashlib.sha256(r.read_bytes()).hexdigest()})
(o/'setting-hashes.json').write_text(json.dumps(records,indent=2)+'\n')
