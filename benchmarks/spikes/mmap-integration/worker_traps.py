from support import *
import shutil,hashlib
run('build-counter',['cc','-O2',R/'benchmarks/tools/process_cost.c','-o',helper])
inputs=Path(os.environ.get('MARIAMEM_MEASURE_INPUT',str(T.parent)))
modes=['mmap'] if os.environ.get('MARIAMEM_ONLY_CANDIDATE')=='1' else ['released','semantics','mmap']
results=[]
for mode in modes:
 source=R if mode=='mmap' else inputs/'temp'/mode
 project=T/('worker-'+mode);project.mkdir();(project/'go.mod').write_text('module github.com/masahitojp/mariamem/memoryprobe\n\ngo 1.26.0\nrequire github.com/masahitojp/mariamem v0.0.0\nreplace github.com/masahitojp/mariamem => '+str(source)+'\n');shutil.copyfile(R/'benchmarks/spikes/mmap-integration/worker-trap.go.txt',project/'main.go')
 if mode=='mmap':(project/'mapping.go').write_text('package main\nimport(generated "github.com/masahitojp/mariamem/internal/generatedgo/code";"github.com/masahitojp/mariamem/internal/generatedgo/code/base")\nfunc init(){makeModule=func()(*base.Module,func()error){b,e:=base.NewMemoryMapping(generated.InitialMemoryBytes,2<<30);if e!=nil{panic(e)};m:=generated.NewWithMemory(nil,nil,nil,b.Bytes(),generated.InitialMemoryBytes);m.PrepareMemoryGrow=b.Grow;return m,b.Close}}\n')
 binary=T/(mode+'-worker');run('build-worker-'+mode,['go','build','-mod=mod','-p','1','-trimpath','-o',binary,'.'],cwd=project)
 for atomic in [False,True]:
  name='worker-'+mode+('-atomic' if atomic else '-scalar')
  # Small isolated diagnostics, CPU/FD/core/timeout limits; fatal Go panic must
  # remain evidence, never be counted as a host-surviving trap.
  p=subprocess.run([str(binary),*(['-atomic'] if atomic else [])],env=env,cwd=R,capture_output=True,text=True,timeout=30,preexec_fn=limits)
  (E/(name+'.log')).write_text(p.stdout+p.stderr)
  results.append({'mode':mode,'family':'atomic' if atomic else 'scalar','exit_code':p.returncode,'host_survived':p.returncode==0 and 'HOST_SURVIVED' in p.stdout,'access_succeeded':'ACCESS_SUCCEEDED' in p.stdout,'wasm_oob_trap':'out of bounds' in p.stderr,'fatal_go_panic':'panic:' in p.stderr,'sigbus_or_sigsegv':p.returncode in (-10,-11),'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest()})
(E/'worker-traps.json').write_text(json.dumps({'cases':results,'required_host_survival_pass':all(x['host_survived'] and not x['access_succeeded'] for x in results if x['mode']=='mmap')},indent=2)+'\n')
print(json.dumps(results,indent=2),flush=True)
record['worker_trap_host_survival_pass']=all(x['host_survived'] and not x['access_succeeded'] for x in results if x['mode']=='mmap');save()
