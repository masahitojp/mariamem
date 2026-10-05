from support import *
import shutil,hashlib,platform
run('build-counter',['cc','-O2',R/'benchmarks/tools/process_cost.c','-o',helper])
project=T/'worker-native';project.mkdir();(project/'go.mod').write_text('module github.com/masahitojp/mariamem/memoryprobe\n\ngo 1.26.0\nrequire github.com/masahitojp/mariamem v0.0.0\nreplace github.com/masahitojp/mariamem => '+str(R)+'\n');shutil.copyfile(R/'benchmarks/spikes/mmap-integration/worker-native.go.txt',project/'main.go')
binary=T/'worker-native-probe';run('build-worker-native',['go','build','-mod=mod','-p','1','-trimpath','-o',binary,'.'],cwd=project)
results=[]
for atomic in [False,True]:
 p=subprocess.run([str(binary),*(['-atomic'] if atomic else [])],env=env,cwd=R,capture_output=True,text=True,timeout=30,preexec_fn=limits)
 name='worker-native-'+('atomic' if atomic else 'scalar');(E/(name+'.log')).write_text(p.stdout+p.stderr)
 results.append({'family':'atomic' if atomic else 'scalar','exit_code':p.returncode,'host_survived_guest_trap':p.returncode==0 and 'HOST_SURVIVED_TRAP' in p.stdout,'access_succeeded':'ACCESS_SUCCEEDED' in p.stdout,'fatal_go_panic':'panic:' in p.stderr,'sigbus_or_sigsegv':p.returncode in (-10,-11)})
proof={'source_sha':record['source_sha'],'platform':platform.platform(),'arch':platform.machine(),'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'required_host_survival_pass':all(x['host_survived_guest_trap'] for x in results),'cases':results}
if Path('/etc/os-release').exists():proof['os_release']=Path('/etc/os-release').read_text()
(E/'worker-native.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof,indent=2),flush=True)
record['worker_native_host_survival_pass']=proof['required_host_survival_pass'];save()
