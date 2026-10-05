from support import *
import shutil
run('build-counter',['cc','-O2',R/'benchmarks/tools/process_cost.c','-o',helper])
# Same released fixture, mapped before every access; reviewed goldens unchanged.
source=Path(os.environ['MARIAMEM_PREPARED_TEMP'])/'fixture-heap'
fixture=T/'fixture-mmap';shutil.copytree(source,fixture)
p=fixture/'module/fixture/memory_mapping.go';p.write_text((R/'internal/generatedgo/code/base/memory_mapping.go').read_text().replace('package base','package fixture',1))
(fixture/'module/fixture/mapped_fixture.go').write_text('package fixture\nfunc NewMapped() (*Module,func()error) {\n b,err:=NewMemoryMapping(65536,3*65536);if err!=nil{panic(err)}\n m:=NewWithMemory(b.Bytes(),65536);m.prepareMemoryGrow=b.Grow\n return m,b.Close\n}\n')
p=fixture/'module/main.go';s=p.read_text().replace('m := fixture.New()','m, release := fixture.NewMapped()')
s=s.replace('\t}\n\tm, release := fixture.NewMapped()', '\t\tif err:=release();err!=nil{panic(err)}\n\t}\n\tm, release := fixture.NewMapped()')
s=s.replace('\tbase := &m.Memory()[0]','\tdefer release()\n\tbase := &m.Memory()[0]');p.write_text(s)
run('fixture-mmap',['go','run','.',fixture/'inputs/matrix.json'],cwd=fixture/'module')
actual=[json.loads(line) for line in (E/'fixture-mmap.log').read_text().splitlines() if line.startswith('{')]
golden=json.loads((R/'benchmarks/spikes/memory-candidate/reference-results.json').read_text());keys=golden['keys']
assert [[v[k] for k in keys] for v in actual]==golden['rows']
record['mapped_fixture_cases']=len(actual);record['mapped_fixture_traps']=sum(v['trap'] for v in actual);save()
run('gofmt',['gofmt','-w',R/'internal/generatedgo/memory_backing_unix.go',R/'internal/generatedgo/memory_backing_other.go',R/'internal/generatedgo/memory_backing_test.go',R/'internal/generatedgo/runtime_instance.go',R/'internal/generatedgo/code/base/memory_mapping.go',R/'internal/generatedgo/code/base/memory_mapping_test.go'])
run('owner-tests',['go','test','-race','-count=1','-v','memory_mapping.go','memory_mapping_test.go'],cwd=R/'internal/generatedgo/code/base',extras={'CGO_ENABLED':'1'})
run('mapped-contract',['go','test','-p','1','-count=1','-v','-run=^TestMappedMemory','-timeout=90s','-gcflags=github.com/masahitojp/mariamem/internal/generatedgo=-d=checkptr=2','./internal/generatedgo'])
run('product',['go','test','-p','1','-tags=integration','-count=1','-v','-run=^(TestPureMemory32(CRUDSessionsAndFork|Auth|RepeatedClose)|TestDefaultNoBundleAndForkIsolation|TestDefaultRepeatedConcurrentLifecycle|TestClosedDatabaseRetainedPipeLifetime)$','-timeout=180s','./tests/godefault'],timeout=240)
run('focused-runtime-race',['go','test','-race','-p','1','-count=1','./internal/generatedgo/code/base'],extras={'CGO_ENABLED':'1'})
run('focused-adapter-race',['go','test','-race','-p','1','-count=1','-run=^(TestMappedMemoryWorkerGrowAndFutex|TestMappedMemoryInitializationFailure|TestMappedMemoryFailedExecutionJoinsBeforeRelease|Test[^M].*)$','./internal/generatedgo','./internal/guest','./internal/host','./internal/mysqlwire','./internal/snapshot'],timeout=900,extras={'CGO_ENABLED':'1'})
record['acceptance_pass']=True;save()
