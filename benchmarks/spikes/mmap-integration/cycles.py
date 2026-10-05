from support import *
import shutil,json
inputs=Path(os.environ['MARIAMEM_MEASURE_INPUT']);prior=json.loads((inputs/'evidence/campaign.json').read_text());assert prior['one20_mmap_stable_before_expansion']
run('build-counter',['cc','-O2',R/'benchmarks/tools/process_cost.c','-o',helper])
run('final-ownership',['go','test','-p','1','-v','-count=1','-run=^TestMappedMemory','./internal/generatedgo'])
record['prior_measurement_sha']=prior['source_sha'];save()
for mode in ['released','semantics','mmap']:
 source=R if mode=='mmap' else inputs/'temp'/mode
 project=T/mode;project.mkdir();(project/'go.mod').write_text('module github.com/masahitojp/mariamem/memoryprobe\n\ngo 1.26.0\nrequire github.com/masahitojp/mariamem v0.0.0\nreplace github.com/masahitojp/mariamem => '+str(source)+'\n')
 shutil.copyfile(R/'benchmarks/spikes/mmap-integration/snapshot.go.txt',project/'main.go')
 if mode=='mmap':(project/'counter.go').write_text('package main\nimport "github.com/masahitojp/mariamem/internal/generatedgo/code/base"\nfunc init(){mappingStats=base.MemoryMappingStats}\n')
 binary=T/(mode+'-cycles');run('build-'+mode,['go','build','-mod=mod','-p','1','-trimpath','-o',binary,'.'],cwd=project)
 run('snapshot20-'+mode,[binary,'-generations=20'],extras={'MARIAMEM_PROCESS_COUNTER':str(helper)},timeout=300)
record['complete_cycles_pass']=True;save()
